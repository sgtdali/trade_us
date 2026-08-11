"""Accounting-metadata validation: every required accounting-context field
must be explicit (not merely inferred or defaulted) on a normalized
direct-financial file, controlled-vocabulary values must be respected, and
the current-period context must be compatible with whatever context
applies to the file's comparison-period figures before any growth/change
calculation may trust them."""

from __future__ import annotations

from ..accounting_context import (
    ACCOUNTING_BASIS_VALUES,
    AUDIT_STATUS_VALUES,
    INFLATION_STATUS_VALUES,
    RESTATEMENT_STATUS_VALUES,
    SCALE_VALUES,
    comparison_context_from_direct_financials,
    context_from_direct_financials,
)
from .result import ValidationFinding, ValidationResult

_REQUIRED_TOP_LEVEL = ("currency", "scale", "consolidation", "audit_status", "accounting_basis", "period_type")

_MISMATCH_CODES = (
    ("currency", "currency_mismatch"),
    ("scale", "scale_mismatch"),
    ("consolidation", "consolidation_mismatch"),
    ("accounting_basis", "accounting_basis_mismatch"),
    ("inflation_adjustment_status", "inflation_basis_mismatch"),
    ("restatement_status", "restatement_mismatch"),
)


def _mismatch_code(problem: str) -> str:
    for field, code in _MISMATCH_CODES:
        if problem.startswith(field):
            return code
    return "incompatible_comparison"


def validate_accounting_context(direct_financials: dict, file_label: str) -> ValidationResult:
    result = ValidationResult()

    for field in _REQUIRED_TOP_LEVEL:
        if not direct_financials.get(field):
            result.add(ValidationFinding("missing_accounting_metadata", "error", f"Required accounting-context field {field!r} is missing or empty.", file_label, field))

    inflation = direct_financials.get("inflation_adjustment")
    if not inflation or not inflation.get("status"):
        result.add(ValidationFinding("missing_accounting_metadata", "error", "Required accounting-context field 'inflation_adjustment.status' is missing or empty.", file_label, "inflation_adjustment.status"))
    elif inflation["status"] not in INFLATION_STATUS_VALUES:
        result.add(ValidationFinding("invalid_inflation_status", "error", f"inflation_adjustment.status {inflation['status']!r} is not in the controlled vocabulary {sorted(INFLATION_STATUS_VALUES)}.", file_label))

    restatement = direct_financials.get("restatement")
    if not restatement or not restatement.get("status"):
        result.add(ValidationFinding("missing_accounting_metadata", "error", "Required accounting-context field 'restatement.status' is missing or empty.", file_label, "restatement.status"))
    elif restatement["status"] not in RESTATEMENT_STATUS_VALUES:
        result.add(ValidationFinding("invalid_restatement_status", "error", f"restatement.status {restatement['status']!r} is not in the controlled vocabulary {sorted(RESTATEMENT_STATUS_VALUES)}.", file_label))

    scale = direct_financials.get("scale")
    if scale is not None and scale not in SCALE_VALUES:
        result.add(ValidationFinding("invalid_scale", "error", f"scale {scale!r} is not in the controlled vocabulary {sorted(SCALE_VALUES)}.", file_label))

    accounting_basis = direct_financials.get("accounting_basis")
    if accounting_basis is not None and accounting_basis not in ACCOUNTING_BASIS_VALUES:
        result.add(ValidationFinding("invalid_accounting_basis", "error", f"accounting_basis {accounting_basis!r} is not in the controlled vocabulary {sorted(ACCOUNTING_BASIS_VALUES)}.", file_label))

    audit_status = direct_financials.get("audit_status")
    if audit_status is not None and audit_status not in AUDIT_STATUS_VALUES:
        result.add(ValidationFinding("invalid_audit_status", "warning", f"audit_status {audit_status!r} is outside the documented controlled vocabulary {sorted(AUDIT_STATUS_VALUES)}; treated as informational free text, not blocking.", file_label))

    # Current-vs-comparison compatibility: a genuine, known disagreement
    # blocks (mirrors what derivation/engine.py itself refuses to compute a
    # growth/change figure across); "undetermined" values are reported
    # separately below so they are never silently read as compatible.
    current_ctx = context_from_direct_financials(direct_financials)
    comparison_ctx = comparison_context_from_direct_financials(direct_financials)
    for problem in current_ctx.compatible_with(comparison_ctx):
        result.add(ValidationFinding(
            _mismatch_code(problem), "error",
            f"Current vs comparison accounting context is incompatible: {problem}. Growth/change "
            "calculations against this comparison are blocked by the derivation engine.",
            file_label,
        ))

    for name, current_value, comparison_value in (
        ("accounting_basis", current_ctx.accounting_basis, comparison_ctx.accounting_basis),
        ("inflation_adjustment_status", current_ctx.inflation_adjustment_status, comparison_ctx.inflation_adjustment_status),
        ("restatement_status", current_ctx.restatement_status, comparison_ctx.restatement_status),
    ):
        if current_value == "undetermined":
            result.add(ValidationFinding(
                "undetermined_accounting_metadata", "info",
                f"{name} is 'undetermined' for the current period; comparability with other filings "
                "cannot be established from this file alone.",
                file_label, name,
            ))
        if comparison_value == "undetermined" and current_value not in (None, "undetermined"):
            result.add(ValidationFinding(
                "undetermined_accounting_metadata", "warning",
                f"{name} is 'undetermined' for the comparison period while the current period declares "
                f"{current_value!r}; comparability is reduced even though it is not a known disagreement.",
                file_label, name,
            ))

    return result
