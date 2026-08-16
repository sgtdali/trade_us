"""Loading the capital policy.

Sizing and band arithmetic lives in a later phase; this module only gets the
document into memory with its guarantees intact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import schemas
from .errors import SchemaViolation

DEFAULT_RELATIVE_PATH = Path("config") / "fund" / "capital-policy.json"


def resolve_pointer(document: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer, raising if it leads nowhere."""
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise SchemaViolation(f"JSON Pointer must start with '/': {pointer!r}")
    current = document
    for raw_token in pointer.split("/")[1:]:
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise SchemaViolation(f"JSON Pointer {pointer!r} does not resolve: no key {token!r}")
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit() or int(token) >= len(current):
                raise SchemaViolation(f"JSON Pointer {pointer!r} does not resolve: bad index {token!r}")
            current = current[int(token)]
        else:
            raise SchemaViolation(f"JSON Pointer {pointer!r} does not resolve: {token!r} into a scalar")
    return current


def check_provisional_pointers(policy: dict[str, Any]) -> None:
    """Every provisional_fields pointer must name a field that exists.

    A pointer left behind by a renamed field marks nothing, which is worse than
    not marking at all: the calibration review would report full coverage while
    silently skipping the value it was meant to watch.
    """
    for pointer in policy.get("provisional_fields", []):
        resolve_pointer(policy, pointer)


def load(path: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    policy_path = path or (root or schemas.repo_root()) / DEFAULT_RELATIVE_PATH
    if not policy_path.is_file():
        raise SchemaViolation(f"capital policy not found: {policy_path}")
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaViolation(f"capital policy is not valid JSON: {policy_path}: {exc}") from exc
    schemas.validate(policy, schemas.CAPITAL_POLICY, root)
    check_provisional_pointers(policy)
    return policy


def is_sentinel(value: Any) -> bool:
    return isinstance(value, str) and value in {
        "disabled",
        "unbounded_by_policy",
        "not_applicable",
        "monitor_only",
    }
