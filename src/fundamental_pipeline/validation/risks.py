"""Risk-record validation."""

from __future__ import annotations

from .result import ValidationFinding, ValidationResult

_VALID_SEVERITIES = {"low", "medium", "high"}
_VALID_DIRECTIONS = {"positive", "negative", "mixed"}


def validate_risks(risks_data: dict, file_label: str) -> ValidationResult:
    result = ValidationResult()
    seen_ids: set[str] = set()
    for r in risks_data.get("risks", []):
        risk_id = r.get("risk_id")
        if risk_id in seen_ids:
            result.add(ValidationFinding("duplicate_risk_id", "error", f"Duplicate risk_id: {risk_id}", file_label))
        seen_ids.add(risk_id)

        if r.get("severity") not in _VALID_SEVERITIES:
            result.add(ValidationFinding("invalid_risk_severity", "error", f"{risk_id}: severity {r.get('severity')!r} is not in {_VALID_SEVERITIES}.", file_label, risk_id))
        if r.get("direction") not in _VALID_DIRECTIONS:
            result.add(ValidationFinding("invalid_risk_direction", "error", f"{risk_id}: direction {r.get('direction')!r} is not in {_VALID_DIRECTIONS}.", file_label, risk_id))
        if not r.get("evidence"):
            result.add(ValidationFinding("risk_missing_evidence", "warning", f"{risk_id}: no evidence entries.", file_label, risk_id))
        if not r.get("title") or not r.get("description"):
            result.add(ValidationFinding("risk_missing_title_or_description", "error", f"{risk_id}: title or description missing.", file_label, risk_id))
    return result
