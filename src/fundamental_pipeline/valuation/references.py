"""Exact artifact reference verification and safe relative-path handling.

An exact artifact reference is a mapping with three required fields:
``artifact_id``, ``artifact_type``, ``relative_path``. Verification checks
all three against the actual referenced artifact and its resolved
location -- never just the path, and never just the ID.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Mapping

from .errors import ArtifactReferenceError

REQUIRED_REFERENCE_FIELDS = ("artifact_id", "artifact_type", "relative_path")


def safe_relative_path(root: Path, relative_path: str) -> Path:
    """Resolve ``relative_path`` (a ``/``-separated, root-relative path)
    against ``root`` and verify it cannot escape the root -- no leading
    ``/``, no ``.``/``..`` components, no symlink escape. Returns the
    resolved absolute path. Raises :class:`ArtifactReferenceError`
    (without echoing the untrusted raw path payload) on any violation.
    """
    if not isinstance(relative_path, str) or not relative_path:
        raise ArtifactReferenceError("relative_path must be a non-empty string")
    if "\\" in relative_path:
        raise ArtifactReferenceError("relative_path must use '/' separators, not '\\'")
    if relative_path.startswith("/"):
        raise ArtifactReferenceError("relative_path must not be absolute")
    # Split the raw string ourselves rather than relying on PurePosixPath's
    # .parts: pathlib silently collapses "." segments and repeated "/"
    # before we would ever see them, which would defeat this check.
    raw_parts = relative_path.split("/")
    if not raw_parts or any(part in (".", "..", "") for part in raw_parts):
        raise ArtifactReferenceError("relative_path must not contain '.', '..', empty, or repeated-slash components")

    resolved_root = root.resolve()
    candidate = (resolved_root / PurePosixPath(relative_path)).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ArtifactReferenceError("relative_path escapes the governed root")
    return candidate


def verify_artifact_reference(
    reference: Mapping,
    artifact: Mapping,
    path: str,
    *,
    root: Path | None = None,
) -> None:
    """Verify that ``reference`` exactly matches ``artifact`` and its
    on-disk location.

    Checks, in order: all three required fields are present on
    ``reference``; ``artifact`` itself declares both ``artifact_type`` and
    ``artifact_id`` (an artifact missing either is fail-closed rejected,
    never treated as "no claim to check against"); those two fields match
    the reference exactly; ``reference['relative_path']`` matches ``path``
    exactly; and, when ``root`` is given, that ``path`` is a safe,
    contained, resolvable relative path. Raises
    :class:`ArtifactReferenceError` on any mismatch or omission; never
    returns a partial/best-effort success.
    """
    missing = [f for f in REQUIRED_REFERENCE_FIELDS if f not in reference]
    if missing:
        raise ArtifactReferenceError(f"reference missing required field(s): {sorted(missing)}")

    artifact_missing = [f for f in ("artifact_type", "artifact_id") if f not in artifact]
    if artifact_missing:
        raise ArtifactReferenceError(
            f"artifact is missing required identity field(s) {sorted(artifact_missing)}; "
            "an artifact without a declared type/ID can never satisfy an exact reference"
        )

    if reference["artifact_type"] != artifact["artifact_type"]:
        raise ArtifactReferenceError(
            f"reference artifact_type {reference['artifact_type']!r} does not match artifact "
            f"artifact_type {artifact['artifact_type']!r}"
        )

    if reference["artifact_id"] != artifact["artifact_id"]:
        raise ArtifactReferenceError("reference artifact_id does not match artifact artifact_id")

    if reference["relative_path"] != path:
        raise ArtifactReferenceError("reference relative_path does not match the artifact's actual relative path")

    if root is not None:
        safe_relative_path(root, path)
