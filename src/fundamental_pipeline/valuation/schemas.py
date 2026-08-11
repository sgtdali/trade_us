"""Offline JSON Schema registry for the allowlisted valuation schema
resources.

Only the schemas listed in :data:`SCHEMA_FILES` are ever loaded.
`$ref` resolution is bounded to this preloaded, in-memory registry -- no
network, `file://`, or absolute-path resolution is ever attempted, and an
unknown `$id` fails closed with :class:`SchemaError`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jsonschema
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable

from ..paths import repo_path
from .errors import SchemaError
from .safe_json import read_safe_json

#: The only schema resources the valuation namespace will ever load.
SCHEMA_FILES: dict[str, str] = {
    "valuation-common": "valuation-common.schema.json",
    "valuation-catalog": "valuation-catalog.schema.json",
    "market-source-manifest": "market-source-manifest.schema.json",
    "market-snapshot": "market-snapshot.schema.json",
    "valuation-inputs": "valuation-inputs.schema.json",
    "valuation-results": "valuation-results.schema.json",
    "valuation-comparison": "valuation-comparison.schema.json",
    "valuation-peer-universe": "valuation-peer-universe.schema.json",
    "valuation-comparison-observations": "valuation-comparison-observations.schema.json",
    "eod-provider-extract": "eod-provider-extract.schema.json",
    "eod-price-series": "eod-price-series.schema.json",
    "eod-ingestion-validation": "eod-ingestion-validation.schema.json",
    "eod-ingestion-bundle": "eod-ingestion-bundle.schema.json",
    "market-observation-bundle": "market-observation-bundle.schema.json",
    "eod-close-promotion-policy": "eod-close-promotion-policy.schema.json",
    "eod-close-promotion-validation": "eod-close-promotion-validation.schema.json",
    "eod-close-promotion-manifest": "eod-close-promotion-manifest.schema.json",
    "share-count-ledger": "share-count-ledger.schema.json",
    "corporate-action-bundle": "corporate-action-bundle.schema.json",
    "share-count-promotion-policy": "share-count-promotion-policy.schema.json",
    "share-count-promotion-validation": "share-count-promotion-validation.schema.json",
    "share-count-promotion-manifest": "share-count-promotion-manifest.schema.json",
    "fx-provider-extract": "fx-provider-extract.schema.json",
    "fx-rate-series": "fx-rate-series.schema.json",
    "fx-ingestion-validation": "fx-ingestion-validation.schema.json",
    "fx-ingestion-bundle": "fx-ingestion-bundle.schema.json",
    "fx-close-promotion-policy": "fx-close-promotion-policy.schema.json",
    "fx-close-promotion-validation": "fx-close-promotion-validation.schema.json",
    "fx-close-promotion-manifest": "fx-close-promotion-manifest.schema.json",
    "market-observation-merge-manifest": "market-observation-merge-manifest.schema.json",
    "market-observation-merge-validation": "market-observation-merge-validation.schema.json",
    "technical-snapshot": "technical-snapshot.schema.json",
    "holding-assets": "holding-assets.schema.json",
    "holding-valuation-inputs": "holding-valuation-inputs.schema.json",
    "holding-valuation-results": "holding-valuation-results.schema.json",
}

#: Artifact-bearing schema keys (as opposed to supporting-definition schemas).
ARTIFACT_SCHEMA_KEYS = (
    "market-snapshot", "valuation-inputs", "valuation-results",
    "valuation-comparison", "valuation-peer-universe", "valuation-comparison-observations",
    "eod-provider-extract", "eod-price-series", "eod-ingestion-validation", "eod-ingestion-bundle",
    "market-observation-bundle", "eod-close-promotion-policy", "eod-close-promotion-validation",
    "eod-close-promotion-manifest", "share-count-ledger", "corporate-action-bundle",
    "share-count-promotion-policy", "share-count-promotion-validation", "share-count-promotion-manifest",
    "fx-provider-extract", "fx-rate-series", "fx-ingestion-validation", "fx-ingestion-bundle",
    "fx-close-promotion-policy", "fx-close-promotion-validation", "fx-close-promotion-manifest",
    "market-observation-merge-manifest", "market-observation-merge-validation",
    "technical-snapshot", "holding-assets", "holding-valuation-inputs",
    "holding-valuation-results",
)

_ALLOWED_ID_SCHEME = "valuation-pipeline"


def _load_schema_document(key: str) -> dict[str, Any]:
    filename = SCHEMA_FILES[key]
    path = repo_path("schemas", filename)
    if not path.exists():
        raise SchemaError(f"unknown or missing schema resource: {key!r}")
    document = read_safe_json(path, label=f"schemas/{filename}")
    schema_id = document.get("$id")
    if not isinstance(schema_id, str) or not schema_id.startswith(f"{_ALLOWED_ID_SCHEME}:"):
        raise SchemaError(
            f"schema {filename!r} has an unsupported $id (must use the local "
            f"{_ALLOWED_ID_SCHEME!r} scheme, never http/https/file/absolute-path): {schema_id!r}"
        )
    return document


@lru_cache(maxsize=None)
def _registry_and_documents() -> tuple[Registry, dict[str, dict[str, Any]]]:
    documents: dict[str, dict[str, Any]] = {}
    resources = []
    for key in SCHEMA_FILES:
        document = _load_schema_document(key)
        documents[key] = document
        resources.append((document["$id"], Resource.from_contents(document)))
    registry = Registry().with_resources(resources)
    return registry, documents


def load_schema(schema_key: str) -> dict[str, Any]:
    """Return the raw (already safely parsed) schema document for
    ``schema_key``. Raises :class:`SchemaError` for any key outside the
    fixed allowlist."""
    if schema_key not in SCHEMA_FILES:
        raise SchemaError(f"unknown schema resource key: {schema_key!r}")
    _, documents = _registry_and_documents()
    return documents[schema_key]


@lru_cache(maxsize=None)
def _validator(schema_key: str) -> jsonschema.protocols.Validator:
    if schema_key not in SCHEMA_FILES:
        raise SchemaError(f"unknown schema resource key: {schema_key!r}")
    registry, documents = _registry_and_documents()
    schema = documents[schema_key]
    validator_cls = jsonschema.validators.validator_for(schema)
    try:
        validator_cls.check_schema(schema)
    except jsonschema.exceptions.SchemaError as exc:
        raise SchemaError(f"schema {schema_key!r} fails its own meta-schema check: {exc}") from exc
    return validator_cls(schema, registry=registry)


def iter_schema_errors(schema_key: str, data: Any):
    """Yield ``jsonschema`` validation errors for ``data`` against
    ``schema_key``, sorted by JSON pointer path. Raises
    :class:`SchemaError` (never a raw ``referencing``/``jsonschema``
    exception) if a `$ref` inside the schema cannot be resolved within the
    offline registry -- e.g. an unknown `$id`, or (structurally
    impossible here, since no schema in the allowlist declares one) a
    remote `http(s)://`/`file://` reference."""
    validator = _validator(schema_key)
    try:
        errors = list(validator.iter_errors(data))
    except Unresolvable as exc:
        raise SchemaError(f"unresolvable $ref while validating against {schema_key!r}: {exc}") from exc
    return sorted(errors, key=lambda e: [str(p) for p in e.path])


def iter_definition_errors(schema_key: str, definition_name: str, data: Any):
    """Yield validation errors for one named $defs member in an allowlisted schema."""
    if schema_key not in SCHEMA_FILES:
        raise SchemaError(f"unknown schema resource key: {schema_key!r}")
    registry, documents = _registry_and_documents()
    schema = documents[schema_key]
    if definition_name not in schema.get("$defs", {}):
        raise SchemaError(f"schema {schema_key!r} has no $defs/{definition_name!r}")
    validator_cls = jsonschema.validators.validator_for(schema)
    definition_schema = {"$schema": schema.get("$schema"), "$ref": f"{schema['$id']}#/$defs/{definition_name}"}
    validator = validator_cls(definition_schema, registry=registry)
    try:
        errors = list(validator.iter_errors(data))
    except Unresolvable as exc:
        raise SchemaError(f"unresolvable $ref while validating {schema_key!r} $defs/{definition_name!r}: {exc}") from exc
    return sorted(errors, key=lambda e: [str(p) for p in e.path])


def validate_against_schema(schema_key: str, data: Any) -> list[str]:
    """Return a list of human-readable jsonschema violation messages
    (empty if valid)."""
    return [f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}" for e in iter_schema_errors(schema_key, data)]


def preload_all_schemas() -> None:
    """Eagerly load and meta-validate every allowlisted schema. Used by the
    CLI/tests to fail fast on a broken schema resource before any other
    work happens."""
    for key in SCHEMA_FILES:
        _validator(key)
