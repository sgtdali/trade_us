"""Bounded, duplicate-key-safe JSON parsing for untrusted valuation
resources (artifacts, schemas, catalogs).

This is deliberately separate from :mod:`engine.io`'s ordinary
``json.load``, which silently keeps the last value of a duplicate key and
enforces no resource bounds -- acceptable for the existing, already-trusted
fundamental data tree, but not for valuation resources that this module
treats as untrusted input.

Named resource limits are declared as module constants (not hidden inside
call sites) so they can be referenced from tests and from CLI ``--max-*``
overrides. All limits are deterministic: they depend only on the input
bytes, never on host memory or timing.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from .errors import DuplicateKeyError, ResourceLimitError

#: Maximum bytes for a single valuation JSON resource (schema, catalog, or
#: artifact). Chosen to comfortably fit any T70-A resource with headroom,
#: while bounding worst-case memory for a malicious oversized file.
MAX_BYTES = 5 * 1024 * 1024

#: Maximum object/array nesting depth.
MAX_DEPTH = 64

#: Maximum number of members in any single JSON object.
MAX_OBJECT_MEMBERS = 10_000

#: Maximum length of any single JSON array.
MAX_ARRAY_LENGTH = 100_000


def parse_safe_json(
    text: str,
    *,
    label: str = "(in-memory)",
    max_depth: int = MAX_DEPTH,
    max_object_members: int = MAX_OBJECT_MEMBERS,
    max_array_length: int = MAX_ARRAY_LENGTH,
) -> Any:
    """Parse ``text`` as JSON, rejecting duplicate object keys (raw or
    NFC-normalization-colliding) and enforcing bounded nesting depth, object
    member count, and array length. Never falls back to ordinary
    ``json.loads`` semantics on a rejected input."""

    def object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: dict[str, Any] = {}
        for raw_key, value in pairs:
            normalized_key = unicodedata.normalize("NFC", raw_key)
            if normalized_key in seen:
                raise DuplicateKeyError(
                    f"{label}: duplicate object key after NFC normalization: {normalized_key!r}"
                )
            seen[normalized_key] = value
        if len(seen) > max_object_members:
            raise ResourceLimitError(
                f"{label}: object member count {len(seen)} exceeds max_object_members={max_object_members}"
            )
        return seen

    try:
        value = json.loads(text, object_pairs_hook=object_pairs_hook)
    except RecursionError as exc:
        raise ResourceLimitError(f"{label}: maximum nesting depth exceeded") from exc
    except json.JSONDecodeError as exc:
        raise ResourceLimitError(f"{label}: malformed JSON: {exc}") from exc

    _check_bounds(value, label=label, max_depth=max_depth, max_array_length=max_array_length, depth=0)
    return value


def _check_bounds(value: Any, *, label: str, max_depth: int, max_array_length: int, depth: int) -> None:
    if depth > max_depth:
        raise ResourceLimitError(f"{label}: nesting depth exceeds max_depth={max_depth}")
    if isinstance(value, dict):
        for member in value.values():
            _check_bounds(member, label=label, max_depth=max_depth, max_array_length=max_array_length, depth=depth + 1)
    elif isinstance(value, list):
        if len(value) > max_array_length:
            raise ResourceLimitError(f"{label}: array length {len(value)} exceeds max_array_length={max_array_length}")
        for item in value:
            _check_bounds(item, label=label, max_depth=max_depth, max_array_length=max_array_length, depth=depth + 1)


def read_safe_json(
    path: Path,
    *,
    label: str | None = None,
    max_bytes: int = MAX_BYTES,
    max_depth: int = MAX_DEPTH,
    max_object_members: int = MAX_OBJECT_MEMBERS,
    max_array_length: int = MAX_ARRAY_LENGTH,
) -> Any:
    """Read and safely parse a JSON file. ``label`` is a sanitized
    diagnostic label (never an absolute path) used in error messages; it
    defaults to the file's name only."""
    diagnostic_label = label if label is not None else path.name
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise ResourceLimitError(f"{diagnostic_label}: byte size {len(raw)} exceeds max_bytes={max_bytes}")
    text = raw.decode("utf-8")
    return parse_safe_json(
        text,
        label=diagnostic_label,
        max_depth=max_depth,
        max_object_members=max_object_members,
        max_array_length=max_array_length,
    )
