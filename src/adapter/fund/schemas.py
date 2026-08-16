"""Loading and validating the fund JSON Schemas.

The fund schemas reference each other by ``$id`` across files, which the
default jsonschema resolver will not follow -- it would try to fetch
``fund:schemas/...`` over the network. Every schema in ``schemas/fund/`` is
therefore registered up front, and validators are built against that registry.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .errors import SchemaViolation

SCHEMA_DIR_NAME = "fund"

COMMON = "fund:schemas/fund/common.schema.json"
INSTRUMENT_MASTER = "fund:schemas/fund/instrument-master.schema.json"
ACCOUNT_EVENT = "fund:schemas/fund/account-event.schema.json"
CAPITAL_POLICY = "fund:schemas/fund/capital-policy.schema.json"
ASSESSMENT_RECORD = "fund:schemas/fund/assessment-record.schema.json"
DECISION_RECORD = "fund:schemas/fund/decision-record.schema.json"
THESIS = "fund:schemas/fund/thesis.schema.json"
THESIS_EVENT = "fund:schemas/fund/thesis-event.schema.json"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def schema_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "schemas" / SCHEMA_DIR_NAME


@lru_cache(maxsize=8)
def _load_registry(directory: str) -> tuple[Registry, tuple[tuple[str, str], ...]]:
    resources: list[tuple[str, Resource]] = []
    index: list[tuple[str, str]] = []
    for path in sorted(Path(directory).glob("*.schema.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        schema_id = contents.get("$id")
        if not schema_id:
            raise SchemaViolation(f"schema without $id: {path}")
        resources.append((schema_id, Resource.from_contents(contents, default_specification=DRAFT202012)))
        index.append((schema_id, str(path)))
    if not resources:
        raise SchemaViolation(f"no fund schemas found under {directory}")
    return Registry().with_resources(resources), tuple(index)


def registry(root: Path | None = None) -> Registry:
    return _load_registry(str(schema_dir(root)))[0]


def load_schema(schema_id: str, root: Path | None = None) -> dict[str, Any]:
    reg = registry(root)
    try:
        return reg.contents(schema_id)
    except Exception as exc:  # noqa: BLE001 -- referencing raises several types
        raise SchemaViolation(f"unknown schema id: {schema_id}") from exc


def validator(schema_id: str, root: Path | None = None) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(
        load_schema(schema_id, root),
        registry=registry(root),
    )


def schema_errors(document: Any, schema_id: str, root: Path | None = None) -> list[str]:
    """Return every validation message, deepest path first.

    Sorted by path so the reported error points at the offending field rather
    than at whichever ``allOf`` branch happened to fail first -- with
    conditional schemas the top-level message is almost always the useless one.
    """
    errors = sorted(validator(schema_id, root).iter_errors(document), key=lambda e: list(e.absolute_path))
    messages = []
    for error in errors:
        location = "/".join(str(part) for part in error.absolute_path) or "(root)"
        messages.append(f"{location}: {_readable(error)}")
    return messages


_FORBIDDEN_SUFFIX = "should not be valid under {}"


def _readable(error: jsonschema.ValidationError) -> str:
    """Turn the one unreadable jsonschema message into a usable sentence.

    A ``$defs/forbidden`` hit reads '<the whole value> should not be valid
    under {}', which tells the reader nothing about why. The interesting fact
    is that this field is not allowed in this branch, and the branch is what
    the schema_path names.
    """
    if error.message.endswith(_FORBIDDEN_SUFFIX):
        field = error.absolute_path[-1] if error.absolute_path else "value"
        return f"{field!r} is not allowed here"
    return error.message


def validate(document: Any, schema_id: str, root: Path | None = None) -> None:
    errors = schema_errors(document, schema_id, root)
    if errors:
        raise SchemaViolation(f"{schema_id} validation failed: " + "; ".join(errors))
