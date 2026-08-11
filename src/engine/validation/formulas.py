"""Formula-catalog and derived-output validation."""

from __future__ import annotations

from ..registry.formulas import formulas as formula_catalog
from .result import ValidationFinding, ValidationResult

_VALID_STATUSES = {"available", "unavailable", "calculation_blocked", "not_comparable", "not_applicable"}


def validate_derived_output(derived_data: dict, file_label: str) -> ValidationResult:
    result = ValidationResult()
    catalog = formula_catalog()
    for category in ("growth", "margins", "liquidity", "leverage", "returns", "cash_generation"):
        for m in derived_data.get(category, []):
            formula_id = m.get("formula_id")
            if formula_id not in catalog:
                result.add(ValidationFinding("unknown_formula_id", "error", f"{m['metric_id']}: formula_id {formula_id!r} is not registered.", file_label, m["metric_id"]))
                continue
            if m.get("formula_version") != catalog[formula_id]["version"]:
                result.add(ValidationFinding("formula_version_mismatch", "warning", f"{m['metric_id']}: formula_version {m.get('formula_version')} does not match registered version {catalog[formula_id]['version']}.", file_label, m["metric_id"]))
            status = m.get("status", "available")
            if status not in _VALID_STATUSES:
                result.add(ValidationFinding("invalid_status", "error", f"{m['metric_id']}: unrecognized status {status!r}.", file_label, m["metric_id"]))
            if status == "available" and m.get("value") is None:
                result.add(ValidationFinding("available_with_null_value", "error", f"{m['metric_id']}: status is available but value is null.", file_label, m["metric_id"]))
            if status != "available" and m.get("value") is not None:
                result.add(ValidationFinding("unavailable_with_value", "error", f"{m['metric_id']}: status {status!r} but value is not null.", file_label, m["metric_id"]))
            if status != "available" and not m.get("reason"):
                result.add(ValidationFinding("unavailable_without_reason", "warning", f"{m['metric_id']}: status {status!r} has no reason.", file_label, m["metric_id"]))
    return result
