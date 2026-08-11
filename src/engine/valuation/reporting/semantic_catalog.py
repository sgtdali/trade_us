"""Central lookup for report-facing semantic metadata.

Method results, financial metric records, and reason codes carry no
presentation metadata of their own (no display unit, no disambiguated human
label, no status category). This module loads a single small JSON file
(``config/valuation/reporting/labels.json``) and exposes typed lookups so
that knowledge lives in one declarative place instead of being
re-reverse-engineered from raw data on every report fix.

This catalog is presentation-only: it carries no economic meaning and a
missing entry never blocks report generation -- lookups fall back to the
raw id (or a generic default phrase) rather than raising.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from ...paths import repo_path
from ..safe_json import read_safe_json

_CATALOG_PATH = ("config", "valuation", "reporting", "labels.json")


@lru_cache(maxsize=1)
def _load_labels() -> dict[str, Any]:
    return read_safe_json(repo_path(*_CATALOG_PATH))


def display_unit_for_method(method_id: str) -> str | None:
    """Return the catalog's display unit for ``method_id``, or None if absent."""
    return _load_labels()["display_units"].get(method_id)


def label_for_metric(metric_id: str) -> str:
    """Return the Turkish report label for ``metric_id``, falling back to the raw id."""
    return _load_labels()["metric_labels"].get(metric_id, metric_id)


def lease_standard_label(accounting_basis: str) -> str:
    """Return the reporting-standard-specific lease-accounting label."""
    return _load_labels().get("lease_standard_labels", {}).get(
        accounting_basis, "kira muhasebesi"
    )


def status_label_for_reason_codes(reason_codes: list[dict[str, Any]]) -> str:
    """Classify unavailable-status reason codes into a Turkish status phrase."""
    labels = _load_labels()
    codes = [r.get("code", "") for r in reason_codes if r.get("code")]
    if not codes:
        return labels["reason_code_default_label_tr"]
    joined = " ".join(codes)
    for rule in labels["reason_code_rules"]:
        if rule["contains"] in joined:
            return f"{rule['label_tr']} ({', '.join(codes)})"
    return f"{labels['reason_code_default_label_tr']} ({', '.join(codes)})"


def status_label_for_applicability_outcome(outcome: str) -> str:
    """Classify a method's applicability.outcome into a coverage-section label."""
    labels = _load_labels()
    for rule in labels["applicability_outcome_rules"]:
        if rule["contains"] in (outcome or ""):
            return rule["label_tr"]
    return labels["applicability_outcome_default_label_tr"]


def status_label_for_method(outcome: str, reason_records: list[dict[str, Any]]) -> str:
    """Classify a method's coverage-section status label, preferring a
    reason-code-specific override over the generic applicability.outcome
    label (found 2026-07-26, ARCLK: a negative-earnings P/E was labeled
    "VERİ EKSİKLİĞİ NEDENİYLE HESAPLANAMADI" -- data deficiency -- via the
    generic "conditional_data" outcome, when the real reason,
    method.denominator_negative, is that a loss-making company's P/E is
    economically not meaningful, not that data is missing)."""
    labels = _load_labels()
    codes = [r.get("code", "") for r in reason_records if r.get("code")]
    joined = " ".join(codes)
    for rule in labels.get("status_override_by_reason_code_rules", ()):
        if rule["contains"] in joined:
            return rule["label_tr"]
    return status_label_for_applicability_outcome(outcome)


def market_freshness_caveat(freshness: str) -> str:
    """Return a Turkish caveat suffix for a non-fresh market observation
    (empty string for "fresh"/"not_applicable"/unrecognized values --
    never invents a warning for a state the catalog doesn't recognize)."""
    return _load_labels().get("market_freshness_caveat_tr", {}).get(freshness or "", "")


def label_for_method(method_id: str) -> str:
    """Return the Turkish report label for ``method_id``."""
    return _load_labels()["method_labels"].get(method_id, method_id)


def caveat_for_method(method_id: str) -> str:
    """Return a report caveat for ``method_id``, or an empty string."""
    return _load_labels().get("method_caveats", {}).get(method_id, "")


def caveat_for_reconciliation(status: str) -> str:
    """Return a report caveat for a reconciliation state, or an empty string."""
    return _load_labels().get("reconciliation_caveats", {}).get(status, "")


def operand_label(method_id: str, role: str) -> str:
    """Return the Turkish operand label for ``method_id`` and ``role`` ("numerator" or "denominator")."""
    method_labels = _load_labels()["operand_labels"].get(method_id, {})
    return method_labels.get(role, "Pay" if role == "numerator" else "Payda")


def debt_profile_status_label(status: str) -> str:
    """Return the Turkish presentation label for a debt-pressure status."""
    return _load_labels().get("debt_profile_status_labels", {}).get(status, status)


def debt_profile_reason_label(reason_code: str) -> str:
    """Return a Turkish debt-profile reason, falling back to its raw code."""
    return _load_labels().get("debt_profile_reason_labels", {}).get(reason_code, reason_code)


def risk_analysis_status_label(
    analysis_status: str,
    reason_code: str | None,
    *,
    has_risks: bool,
) -> str:
    """Return the report phrase for an available/failed risk-analysis state."""
    labels = _load_labels().get("risk_analysis_status_labels", {})
    if analysis_status == "available":
        return "" if has_risks else labels.get("available_empty", "")
    return labels.get(
        reason_code or "",
        labels.get("unavailable_default", reason_code or analysis_status),
    )
