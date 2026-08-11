"""Immutable policy record models for the two T74 comparison catalogs
(ranking/diagnostic) plus the closed gate-predicate grammar those catalogs
author their sample/eligibility gates in (docs/valuation-t74-02-comparison-schema-policy-universe-specification.md
Sections 14-16; docs/valuation-t67-06-comparison-ranking-policy-catalog.md;
docs/valuation-t67-07-piotroski-magic-formula-catalog.md).

These are pure structuring/typing helpers over the raw catalog-entry
dicts :mod:`.compiler` walks and validates -- this module does not itself
validate anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

#: The closed gate-predicate operator allowlist a ranking policy's
#: ``gate_table[].when`` rule tree may use -- an unknown ``op`` is always a
#: compile-time :class:`~..errors.ComparisonPolicyCompileError`, never
#: silently ignored.
ALLOWED_OPERATORS = frozenset({"compare", "any", "all"})
COMPOSITE_OPERATORS = frozenset({"any", "all"})
COMPARATORS = frozenset({">", ">=", "<", "<=", "==", "!="})

#: The only sample-shape fields a gate rule may compare against -- closed,
#: not an arbitrary field-path lookup into the candidate evidence.
GATE_FIELDS = frozenset({
    "eligible_count", "calendar_span_months", "distinct_financial_anchor_count",
    "eligible_peer_count", "coverage_ratio", "approved_primary_cohort_count",
})

ELIGIBILITY_STATES = ("eligible", "provisional", "excluded_insufficient_data")
DIRECTIONS = ("higher_is_more_attractive", "lower_is_more_attractive", "neutral_contextual", "not_rankable")
COMPARISON_VARIANTS = ("historical_self", "sector_peer", "piotroski_diagnostic", "magic_formula_diagnostic")


@dataclass(frozen=True)
class RankingGateRule:
    when: Mapping[str, Any]
    eligibility_state: str
    statistics_allowed: tuple[str, ...]


@dataclass(frozen=True)
class RankingPolicy:
    policy_id: str
    policy_version: str
    variant: str
    direction: str
    eligible_statuses: tuple[str, ...]
    gate_table: tuple[RankingGateRule, ...]
    percentile_formula_ref: str
    quantile_method: str
    tie_policy: str
    outlier_policy: str
    duplicate_precedence: str
    reason_code_order: tuple[str, ...]
    method_family: str | None = None
    method_variant: str | None = None
    cadence: str | None = None
    subject_exclusion: bool = False


@dataclass(frozen=True)
class PiotroskiComponentPolicy:
    component_id: str
    formula_ref: str
    comparator: str
    requires_opening_balance: bool


@dataclass(frozen=True)
class PiotroskiDiagnosticPolicy:
    diagnostic_id: str
    policy_version: str
    company_type_applicability: tuple[str, ...]
    components: tuple[PiotroskiComponentPolicy, ...]
    equity_issuance_ledger_ref: str
    reason_code_order: tuple[str, ...]


@dataclass(frozen=True)
class MagicFormulaDiagnosticPolicy:
    diagnostic_id: str
    policy_version: str
    earnings_yield_formula_ref: str
    return_on_capital_formula_ref: str
    denominator_floor_ratio: str
    combined_min_intersection_n: int
    combined_min_intersection_coverage: str
    reason_code_order: tuple[str, ...]


def parse_ranking_policy(entry: Mapping[str, Any]) -> RankingPolicy:
    body = entry["body"]
    gate_table = tuple(
        RankingGateRule(when=g["when"], eligibility_state=g["eligibility_state"], statistics_allowed=tuple(g["statistics_allowed"]))
        for g in body["gate_table"]
    )
    return RankingPolicy(
        policy_id=body["policy_id"], policy_version=body["policy_version"], variant=body["variant"], direction=body["direction"],
        eligible_statuses=tuple(body["eligible_statuses"]), gate_table=gate_table, percentile_formula_ref=body["percentile_formula_ref"],
        quantile_method=body["quantile_method"], tie_policy=body["tie_policy"], outlier_policy=body["outlier_policy"],
        duplicate_precedence=body["duplicate_precedence"], reason_code_order=tuple(body["reason_code_order"]),
        method_family=body.get("method_family"), method_variant=body.get("method_variant"), cadence=body.get("cadence"),
        subject_exclusion=body.get("subject_exclusion", False),
    )


def parse_piotroski_policy(entry: Mapping[str, Any]) -> PiotroskiDiagnosticPolicy:
    body = entry["body"]
    components = tuple(
        PiotroskiComponentPolicy(
            component_id=c["component_id"], formula_ref=c["formula_ref"], comparator=c["comparator"],
            requires_opening_balance=c.get("requires_opening_balance", False),
        )
        for c in body["components"]
    )
    return PiotroskiDiagnosticPolicy(
        diagnostic_id=body["diagnostic_id"], policy_version=body["policy_version"],
        company_type_applicability=tuple(body["company_type_applicability"]), components=components,
        equity_issuance_ledger_ref=body["equity_issuance_ledger_ref"], reason_code_order=tuple(body["reason_code_order"]),
    )


def parse_magic_formula_policy(entry: Mapping[str, Any]) -> MagicFormulaDiagnosticPolicy:
    body = entry["body"]
    return MagicFormulaDiagnosticPolicy(
        diagnostic_id=body["diagnostic_id"], policy_version=body["policy_version"],
        earnings_yield_formula_ref=body["earnings_yield_formula_ref"], return_on_capital_formula_ref=body["return_on_capital_formula_ref"],
        denominator_floor_ratio=body["denominator_floor_ratio"], combined_min_intersection_n=body["combined_min_intersection_n"],
        combined_min_intersection_coverage=body["combined_min_intersection_coverage"], reason_code_order=tuple(body["reason_code_order"]),
    )
