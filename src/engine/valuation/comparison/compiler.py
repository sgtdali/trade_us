"""Closed comparison/diagnostic-policy compiler (docs/valuation-t74-02-*.md
Sections 14-16; docs/valuation-t67-06-*.md; docs/valuation-t67-07-*.md).

Structural, compile-time-only validation of the two T74 policy catalogs
(ranking/diagnostic): closed gate-operator allowlist, resource bounds,
and closed-vocabulary membership for every variant/direction/eligibility-
state/formula-ref/reason-code a policy declares. Never evaluates a gate
against real sample counts -- that is T74-B's engines. No ``eval``,
``exec``, dynamic import, or arbitrary Python callback is reachable from
any policy entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from ..catalogs import CatalogRegistry
from ..errors import ComparisonPolicyCompileError
from .models import PIOTROSKI_COMPONENT_ORDER
from .policies import (
    ALLOWED_OPERATORS,
    COMPARATORS,
    COMPOSITE_OPERATORS,
    COMPARISON_VARIANTS,
    DIRECTIONS,
    ELIGIBILITY_STATES,
    GATE_FIELDS,
    MagicFormulaDiagnosticPolicy,
    PiotroskiDiagnosticPolicy,
    RankingPolicy,
    parse_magic_formula_policy,
    parse_piotroski_policy,
    parse_ranking_policy,
)

RANKING_CATALOG_ID = "valuation.policies.comparison_ranking"
DIAGNOSTIC_CATALOG_ID = "valuation.policies.strategy_diagnostic"

MAX_RULE_NODES = 32
MAX_RULE_DEPTH = 6

_KNOWN_PERCENTILE_FORMULA_REFS = frozenset({"val.formula.comparison.raw_percentile"})
_KNOWN_QUANTILE_METHODS = frozenset({"type_7"})
_KNOWN_TIE_POLICIES = frozenset({"midrank"})
_KNOWN_OUTLIER_POLICIES = frozenset({"none"})
_KNOWN_DUPLICATE_PRECEDENCE = frozenset({"latest_cutoff_wins", "not_applicable"})
_MAGIC_EARNINGS_YIELD_FORMULA_ID = "val.formula.magic.earnings_yield.ebit_to_ev"
_MAGIC_RETURN_ON_CAPITAL_FORMULA_ID = "val.formula.magic.return_on_tangible_operating_capital"


@dataclass(frozen=True)
class CompiledComparisonPlan:
    ranking_policies: Mapping[str, RankingPolicy]  # keyed by variant
    piotroski_policy: PiotroskiDiagnosticPolicy
    magic_formula_policy: MagicFormulaDiagnosticPolicy


def _walk_gate_rule(node: Any, *, scope: str, depth: int, node_counter: list[int]) -> None:
    node_counter[0] += 1
    if node_counter[0] > MAX_RULE_NODES:
        raise ComparisonPolicyCompileError(f"{scope}: gate rule tree exceeds MAX_RULE_NODES={MAX_RULE_NODES}")
    if depth > MAX_RULE_DEPTH:
        raise ComparisonPolicyCompileError(f"{scope}: gate rule tree exceeds MAX_RULE_DEPTH={MAX_RULE_DEPTH}")
    if not isinstance(node, Mapping):
        raise ComparisonPolicyCompileError(f"{scope}: gate rule node must be an object, got {type(node).__name__}")
    op = node.get("op")
    if op not in ALLOWED_OPERATORS:
        raise ComparisonPolicyCompileError(f"{scope}: unknown or missing gate operator: {op!r}")

    if op == "compare":
        field = node.get("field")
        if field not in GATE_FIELDS:
            raise ComparisonPolicyCompileError(f"{scope}: unknown gate field: {field!r}")
        comparator = node.get("comparator")
        if comparator not in COMPARATORS:
            raise ComparisonPolicyCompileError(f"{scope}: unknown comparator: {comparator!r}")
        if "threshold" not in node:
            raise ComparisonPolicyCompileError(f"{scope}: 'compare' node requires a 'threshold'")
        try:
            Decimal(str(node["threshold"]))
        except InvalidOperation as exc:
            raise ComparisonPolicyCompileError(f"{scope}: 'compare' threshold is not a valid decimal: {node['threshold']!r}") from exc

    if op in COMPOSITE_OPERATORS:
        children = node.get("of")
        if not isinstance(children, (list, tuple)) or not children:
            raise ComparisonPolicyCompileError(f"{scope}: {op!r} requires a nonempty 'of' list of child rule nodes")
        for child in children:
            _walk_gate_rule(child, scope=scope, depth=depth + 1, node_counter=node_counter)


def _compile_ranking_policy(entry: Mapping[str, Any]) -> RankingPolicy:
    policy = parse_ranking_policy(entry)
    scope = f"ranking policy {policy.policy_id!r}"
    if policy.variant not in COMPARISON_VARIANTS:
        raise ComparisonPolicyCompileError(f"{scope}: unknown variant {policy.variant!r}")
    if policy.direction not in DIRECTIONS:
        raise ComparisonPolicyCompileError(f"{scope}: unknown direction {policy.direction!r}")
    if not policy.gate_table:
        raise ComparisonPolicyCompileError(f"{scope}: gate_table must not be empty")
    for rule in policy.gate_table:
        _walk_gate_rule(rule.when, scope=f"{scope}.gate_table", depth=0, node_counter=[0])
        if rule.eligibility_state not in ELIGIBILITY_STATES:
            raise ComparisonPolicyCompileError(f"{scope}: unknown gate eligibility_state {rule.eligibility_state!r}")
    if policy.percentile_formula_ref not in _KNOWN_PERCENTILE_FORMULA_REFS:
        raise ComparisonPolicyCompileError(f"{scope}: unknown percentile_formula_ref {policy.percentile_formula_ref!r}")
    if policy.quantile_method not in _KNOWN_QUANTILE_METHODS:
        raise ComparisonPolicyCompileError(f"{scope}: unknown quantile_method {policy.quantile_method!r}")
    if policy.tie_policy not in _KNOWN_TIE_POLICIES:
        raise ComparisonPolicyCompileError(f"{scope}: unknown tie_policy {policy.tie_policy!r}")
    if policy.outlier_policy not in _KNOWN_OUTLIER_POLICIES:
        raise ComparisonPolicyCompileError(f"{scope}: unknown outlier_policy {policy.outlier_policy!r} (T74 default is 'none' -- no winsorization/trimming/removal)")
    if policy.duplicate_precedence not in _KNOWN_DUPLICATE_PRECEDENCE:
        raise ComparisonPolicyCompileError(f"{scope}: unknown duplicate_precedence {policy.duplicate_precedence!r}")
    return policy


def _compile_piotroski_policy(entry: Mapping[str, Any]) -> PiotroskiDiagnosticPolicy:
    policy = parse_piotroski_policy(entry)
    scope = f"piotroski policy {policy.diagnostic_id!r}"
    if policy.diagnostic_id != "val.diagnostic.piotroski_f_score.standard_9":
        raise ComparisonPolicyCompileError(f"{scope}: standard variant must use the exact T67.7 diagnostic_id")
    declared_ids = tuple(c.component_id for c in policy.components)
    if declared_ids != PIOTROSKI_COMPONENT_ORDER:
        raise ComparisonPolicyCompileError(
            f"{scope}: components must declare exactly the nine canonical component_id values in canonical order, got {declared_ids!r}"
        )
    for component in policy.components:
        if component.comparator not in COMPARATORS:
            raise ComparisonPolicyCompileError(f"{scope}.{component.component_id}: unknown comparator {component.comparator!r}")
        if not component.formula_ref:
            raise ComparisonPolicyCompileError(f"{scope}.{component.component_id}: formula_ref must not be empty")
    if not policy.equity_issuance_ledger_ref:
        raise ComparisonPolicyCompileError(f"{scope}: equity_issuance_ledger_ref must not be empty")
    return policy


def _compile_magic_formula_policy(entry: Mapping[str, Any]) -> MagicFormulaDiagnosticPolicy:
    policy = parse_magic_formula_policy(entry)
    scope = f"magic formula policy {policy.diagnostic_id!r}"
    if policy.earnings_yield_formula_ref != _MAGIC_EARNINGS_YIELD_FORMULA_ID:
        raise ComparisonPolicyCompileError(f"{scope}: earnings_yield_formula_ref must be the exact T67.7 formula ID {_MAGIC_EARNINGS_YIELD_FORMULA_ID!r}")
    if policy.return_on_capital_formula_ref != _MAGIC_RETURN_ON_CAPITAL_FORMULA_ID:
        raise ComparisonPolicyCompileError(f"{scope}: return_on_capital_formula_ref must be the exact T67.7 formula ID {_MAGIC_RETURN_ON_CAPITAL_FORMULA_ID!r}")
    try:
        floor = Decimal(policy.denominator_floor_ratio)
    except InvalidOperation as exc:
        raise ComparisonPolicyCompileError(f"{scope}: denominator_floor_ratio is not a valid decimal: {policy.denominator_floor_ratio!r}") from exc
    if floor <= 0:
        raise ComparisonPolicyCompileError(f"{scope}: denominator_floor_ratio must be strictly positive")
    if policy.combined_min_intersection_n < 1:
        raise ComparisonPolicyCompileError(f"{scope}: combined_min_intersection_n must be >= 1")
    try:
        coverage = Decimal(policy.combined_min_intersection_coverage)
    except InvalidOperation as exc:
        raise ComparisonPolicyCompileError(f"{scope}: combined_min_intersection_coverage is not a valid decimal: {policy.combined_min_intersection_coverage!r}") from exc
    if not (0 < coverage <= 1):
        raise ComparisonPolicyCompileError(f"{scope}: combined_min_intersection_coverage must be in (0,1]")
    return policy


def compile_comparison_policies(registry: CatalogRegistry) -> CompiledComparisonPlan:
    """Compile the two T74 policy catalogs from ``registry`` (loaded via
    :func:`~..catalogs.load_comparison_catalog_registry`) into a
    :class:`CompiledComparisonPlan`. Raises
    :class:`~..errors.ComparisonPolicyCompileError` on the first
    structural violation -- never a partial/best-effort plan."""
    ranking_catalog = registry.catalog(RANKING_CATALOG_ID)
    diagnostic_catalog = registry.catalog(DIAGNOSTIC_CATALOG_ID)

    ranking_policies: dict[str, RankingPolicy] = {}
    for entry in ranking_catalog["entries"]:
        policy = _compile_ranking_policy(entry)
        if policy.variant in ranking_policies:
            raise ComparisonPolicyCompileError(f"duplicate ranking policy for variant {policy.variant!r}")
        ranking_policies[policy.variant] = policy
    required_ranking_variants = {"historical_self", "sector_peer"}
    missing_variants = required_ranking_variants - set(ranking_policies)
    if missing_variants:
        raise ComparisonPolicyCompileError(f"comparison-ranking-policies catalog is missing policy(ies) for {sorted(missing_variants)}")

    piotroski_entries = [e for e in diagnostic_catalog["entries"] if e["body"].get("diagnostic_kind") == "piotroski"]
    magic_entries = [e for e in diagnostic_catalog["entries"] if e["body"].get("diagnostic_kind") == "magic_formula"]
    if len(piotroski_entries) != 1:
        raise ComparisonPolicyCompileError(f"strategy-diagnostic-policies catalog must declare exactly one piotroski entry, found {len(piotroski_entries)}")
    if len(magic_entries) != 1:
        raise ComparisonPolicyCompileError(f"strategy-diagnostic-policies catalog must declare exactly one magic_formula entry, found {len(magic_entries)}")

    piotroski_policy = _compile_piotroski_policy(piotroski_entries[0])
    magic_formula_policy = _compile_magic_formula_policy(magic_entries[0])

    return CompiledComparisonPlan(
        ranking_policies=ranking_policies, piotroski_policy=piotroski_policy, magic_formula_policy=magic_formula_policy,
    )
