"""Validation rules and structural checks for technical analysis artifacts."""

from __future__ import annotations

from typing import Any

from ..valuation.schemas import iter_schema_errors
from ..valuation.validation.findings import Finding

REQUIRED_INDICATORS = (
    "sma_50",
    "sma_200",
    "price_vs_sma_50",
    "price_vs_sma_200",
    "sma_50_vs_sma_200",
    "rsi_14",
    "avg_volume_20d",
    "avg_volume_60d",
    "volume_trend",
    "support_63d",
    "resistance_63d",
)


def validate_technical_snapshot(data: dict[str, Any], relative_path: str = "") -> list[Finding]:
    """Validate a candidate technical_snapshot artifact against its schema and invariants."""
    findings: list[Finding] = []

    # 1. JSON Schema validation
    try:
        schema_errors = iter_schema_errors("technical-snapshot", data)
        for err in schema_errors:
            json_ptr = "/" + "/".join(str(p) for p in err.path) if err.path else ""
            findings.append(
                Finding(
                    rule_id="TECH-SCHEMA-001",
                    severity="error",
                    scope="schema",
                    message=f"JSON schema violation: {err.message}",
                    reason_code="schema.violation",
                    artifact_type=data.get("artifact_type"),
                    artifact_id=data.get("artifact_id"),
                    relative_path=relative_path,
                    json_pointer=json_ptr,
                )
            )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            Finding(
                rule_id="TECH-SCHEMA-000",
                severity="blocker",
                scope="schema",
                message=f"Schema resolution/validation failed: {exc}",
                reason_code="schema.unresolvable",
                relative_path=relative_path,
            )
        )
        return findings

    # If schema validation produced blockers/errors, return early
    if any(f.severity in ("blocker", "error") for f in findings):
        return findings

    # 2. Artifact identity check
    ticker = data.get("ticker", "")
    as_of_date = data.get("as_of_date", "")
    expected_artifact_id = f"technical-snapshot:{ticker}:{as_of_date}"
    actual_artifact_id = data.get("artifact_id", "")
    if actual_artifact_id != expected_artifact_id:
        findings.append(
            Finding(
                rule_id="TECH-ID-001",
                severity="error",
                scope="artifact",
                message=f"artifact_id mismatch: expected {expected_artifact_id!r}, got {actual_artifact_id!r}",
                reason_code="artifact.id_mismatch",
                artifact_type="technical_snapshot",
                artifact_id=actual_artifact_id,
                relative_path=relative_path,
            )
        )

    # 3. Indicators completeness check
    indicators = data.get("indicators", {})
    for name in REQUIRED_INDICATORS:
        if name not in indicators:
            findings.append(
                Finding(
                    rule_id="TECH-IND-001",
                    severity="error",
                    scope="field",
                    message=f"missing required indicator: {name!r}",
                    reason_code="indicator.missing",
                    artifact_type="technical_snapshot",
                    artifact_id=actual_artifact_id,
                    relative_path=relative_path,
                    json_pointer=f"/indicators/{name}",
                )
            )

    return findings
