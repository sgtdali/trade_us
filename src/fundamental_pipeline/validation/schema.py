"""JSON Schema validation, actually invoking the Draft 2020-12 schemas in
``schemas/`` via the ``jsonschema`` library."""

from __future__ import annotations

from functools import lru_cache

import jsonschema

from ..io import read_json
from ..paths import repo_path
from .result import ValidationFinding, ValidationResult

_SCHEMA_FILES = {
    "company": "company.schema.json",
    "source-manifest": "source-manifest.schema.json",
    "financial-direct": "financial-direct.schema.json",
    "financial-derived": "financial-derived.schema.json",
    "financial-series": "financial-series.schema.json",
    "operational": "operational.schema.json",
    "financial-operational": "financial-operational.schema.json",
    "debt-profile": "debt-profile.schema.json",
    "signals": "signals.schema.json",
    "risks": "risks.schema.json",
    "summaries": "summaries.schema.json",
}


@lru_cache(maxsize=None)
def _validator(schema_key: str) -> jsonschema.protocols.Validator:
    schema = read_json(repo_path("schemas", _SCHEMA_FILES[schema_key]))
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    return validator_cls(schema)


def validate_against_schema(schema_key: str, data: dict, file_label: str) -> ValidationResult:
    result = ValidationResult()
    validator = _validator(schema_key)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        json_path = "/".join(str(p) for p in error.path) or "(root)"
        result.add(ValidationFinding("schema_violation", "error", error.message, file_label, json_path))
    return result
