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


def _piotroski_component(component_id: str, *, formula_ref: str, comparator: str, requires_opening_balance: bool = False) -> dict[str, Any]:
    return {"component_id": component_id, "formula_ref": formula_ref, "comparator": comparator, "requires_opening_balance": requires_opening_balance}


_PIOTROSKI_DIAGNOSTIC_ENTRY: dict[str, Any] = {
    "entry_id": "val.diagnostic.piotroski_f_score.standard_9",
    "entry_version": "1.0.0",
    "lifecycle_status": "approved",
    "label": "Piotroski F-Score, standard nine-component variant",
    "source_contract_refs": ["docs/valuation-t67-07-piotroski-magic-formula-catalog.md"],
    "body": {
        "diagnostic_kind": "piotroski",
        "diagnostic_id": "val.diagnostic.piotroski_f_score.standard_9",
        "policy_version": "1.0.0",
        "company_type_applicability": ["standard_corporate"],
        "components": [
            _piotroski_component("piot.roa_positive", formula_ref="val.formula.piotroski.roa", comparator=">"),
            _piotroski_component("piot.cfo_positive", formula_ref="val.formula.piotroski.cfo", comparator=">"),
            _piotroski_component("piot.delta_roa_positive", formula_ref="val.formula.piotroski.delta_roa", comparator=">", requires_opening_balance=True),
            _piotroski_component("piot.accrual_quality", formula_ref="val.formula.piotroski.accrual_quality", comparator=">"),
            _piotroski_component("piot.leverage_decreased", formula_ref="val.formula.piotroski.long_term_leverage", comparator="<"),
            _piotroski_component("piot.current_ratio_increased", formula_ref="val.formula.piotroski.current_ratio", comparator=">"),
            _piotroski_component("piot.no_external_equity_issuance", formula_ref="val.formula.piotroski.external_equity_issuance", comparator="=="),
            _piotroski_component("piot.gross_margin_increased", formula_ref="val.formula.piotroski.gross_margin", comparator=">"),
            _piotroski_component("piot.asset_turnover_increased", formula_ref="val.formula.piotroski.asset_turnover", comparator=">", requires_opening_balance=True),
        ],
        "equity_issuance_ledger_ref": "val.policy.comparison.piotroski.equity_issuance_ledger@1.0.0",
        "reason_code_order": [
            "strategy.piotroski_period_pair_incompatible",
            "strategy.piotroski_component_missing",
            "strategy.piotroski_equity_issuance_ledger_incomplete",
            "strategy.piotroski_standard_not_applicable",
        ],
    },
}

_MAGIC_FORMULA_DIAGNOSTIC_ENTRY: dict[str, Any] = {
    "entry_id": "val.diagnostic.magic_formula.greenblatt_compatible",
    "entry_version": "1.0.0",
    "lifecycle_status": "approved",
    "label": "Magic Formula, Greenblatt-compatible EBIT/EV and tangible-operating-capital ROC",
    "source_contract_refs": ["docs/valuation-t67-07-piotroski-magic-formula-catalog.md"],
    "body": {
        "diagnostic_kind": "magic_formula",
        "diagnostic_id": "val.diagnostic.magic_formula.greenblatt_compatible",
        "policy_version": "1.0.0",
        "earnings_yield_formula_ref": "val.formula.magic.earnings_yield.ebit_to_ev",
        "return_on_capital_formula_ref": "val.formula.magic.return_on_tangible_operating_capital",
        "denominator_floor_ratio": "0.01",
        "combined_min_intersection_n": 5,
        "combined_min_intersection_coverage": "0.70",
        "reason_code_order": [
            "strategy.magic_ebit_nonpositive",
            "strategy.magic_enterprise_value_nonpositive",
            "strategy.magic_operating_capital_nonpositive",
            "strategy.magic_operating_capital_near_zero",
            "strategy.magic_lease_basis_mismatch",
            "strategy.magic_family_double_count",
            "strategy.magic_combined_component_missing",
            "strategy.magic_universe_gate_failed",
        ],
    },
}
