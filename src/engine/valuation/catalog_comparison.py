"""Authored valuation catalog definitions.

Kept by domain so catalog content remains reviewable without changing its
canonical structure.
"""

from __future__ import annotations

from typing import Any

def _ranking_gate_rule(when: dict[str, Any], *, eligibility_state: str, statistics_allowed: list[str]) -> dict[str, Any]:
    return {"when": when, "eligibility_state": eligibility_state, "statistics_allowed": statistics_allowed}


def _cmp(field: str, comparator: str, threshold: str) -> dict[str, Any]:
    return {"op": "compare", "field": field, "comparator": comparator, "threshold": threshold}


def _all_of(*children: dict[str, Any]) -> dict[str, Any]:
    return {"op": "all", "of": list(children)}


def _ranking_policy_entry(
    variant: str, *, direction: str, eligible_statuses: list[str], gate_table: list[dict[str, Any]],
    cadence: str | None = None, subject_exclusion: bool = False, method_family: str | None = None,
) -> dict[str, Any]:
    return {
        "entry_id": f"val.policy.comparison.ranking.{variant}",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": f"T74 {variant} ranking policy",
        "source_contract_refs": [
            "docs/valuation-t66-08-comparison-specification.md",
            "docs/valuation-t67-06-comparison-ranking-policy-catalog.md",
        ],
        "body": {
            "policy_id": f"val.policy.comparison.ranking.{variant}@1.0.0",
            "policy_version": "1.0.0",
            "variant": variant,
            "direction": direction,
            "method_family": method_family,
            "cadence": cadence,
            "subject_exclusion": subject_exclusion,
            "eligible_statuses": eligible_statuses,
            "gate_table": gate_table,
            "percentile_formula_ref": "val.formula.comparison.raw_percentile",
            "quantile_method": "type_7",
            "tie_policy": "midrank",
            "outlier_policy": "none",
            "duplicate_precedence": "latest_cutoff_wins" if variant == "historical_self" else "not_applicable",
            "reason_code_order": [
                "comparison.insufficient_history",
                "comparison.history_span_below_minimum",
                "comparison.financial_anchor_concentration",
                "comparison.method_regime_mismatch",
                "comparison.insufficient_peer_count",
                "comparison.method_coverage_below_threshold",
                "comparison.subject_in_peer_count",
                "comparison.tier_mixing",
                "comparison.rank_ineligible_value",
                "comparison.outlier_quarantined",
                "comparison.excluded_ranked_bottom",
                "comparison.tie_break_changes_rank",
                "comparison.rank_context_missing",
            ],
        },
    }


_RANKING_POLICY_ENTRIES: list[dict[str, Any]] = [
    _ranking_policy_entry(
        "historical_self", direction="higher_is_more_attractive", eligible_statuses=["available"], cadence="canonical_monthly",
        gate_table=[
            _ranking_gate_rule(
                _all_of(_cmp("eligible_count", ">=", "24"), _cmp("calendar_span_months", ">=", "24"), _cmp("distinct_financial_anchor_count", ">=", "4")),
                eligibility_state="eligible", statistics_allowed=["raw_percentile", "attractiveness_percentile"],
            ),
            _ranking_gate_rule(
                _all_of(_cmp("eligible_count", ">=", "24"), _cmp("calendar_span_months", ">=", "24")),
                eligibility_state="provisional", statistics_allowed=["median", "range"],
            ),
            _ranking_gate_rule(_cmp("eligible_count", ">=", "12"), eligibility_state="provisional", statistics_allowed=["median", "range"]),
            _ranking_gate_rule(_cmp("eligible_count", ">=", "0"), eligibility_state="excluded_insufficient_data", statistics_allowed=[]),
        ],
    ),
    _ranking_policy_entry(
        "sector_peer", direction="higher_is_more_attractive", eligible_statuses=["available"], subject_exclusion=True,
        gate_table=[
            _ranking_gate_rule(
                _all_of(_cmp("eligible_peer_count", ">=", "5"), _cmp("coverage_ratio", ">=", "0.70")),
                eligibility_state="eligible", statistics_allowed=["raw_percentile", "attractiveness_percentile", "midrank", "median", "range", "quartiles"],
            ),
            _ranking_gate_rule(_cmp("eligible_peer_count", ">=", "3"), eligibility_state="provisional", statistics_allowed=["median", "range"]),
            _ranking_gate_rule(_cmp("eligible_peer_count", ">=", "0"), eligibility_state="excluded_insufficient_data", statistics_allowed=[]),
        ],
    ),
]
