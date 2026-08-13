"""Closed comparison-ranking-policy compiler (docs/valuation-t74-02-*.md
Sections 14-16; docs/valuation-t67-06-*.md).

Structural, compile-time-only validation of the T74 ranking policy catalog:
closed gate-operator allowlist, resource bounds,
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
from .policies import (
    ALLOWED_OPERATORS,
    COMPARATORS,
    COMPOSITE_OPERATORS,
    COMPARISON_VARIANTS,
    DIRECTIONS,
    ELIGIBILITY_STATES,
    GATE_FIELDS,
    RankingPolicy,
    parse_ranking_policy,
)

RANKING_CATALOG_ID = "valuation.policies.comparison_ranking"

MAX_RULE_NODES = 32
MAX_RULE_DEPTH = 6

_KNOWN_PERCENTILE_FORMULA_REFS = frozenset({"val.formula.comparison.raw_percentile"})
_KNOWN_QUANTILE_METHODS = frozenset({"type_7"})
_KNOWN_TIE_POLICIES = frozenset({"midrank"})
_KNOWN_OUTLIER_POLICIES = frozenset({"none"})
_KNOWN_DUPLICATE_PRECEDENCE = frozenset({"latest_cutoff_wins", "not_applicable"})


@dataclass(frozen=True)
class CompiledComparisonPlan:
    ranking_policies: Mapping[str, RankingPolicy]  # keyed by variant


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


def compile_comparison_policies(registry: CatalogRegistry) -> CompiledComparisonPlan:
    """Compile the T74 ranking policy catalog from ``registry`` (loaded via
    :func:`~..catalogs.load_comparison_catalog_registry`) into a
    :class:`CompiledComparisonPlan`. Raises
    :class:`~..errors.ComparisonPolicyCompileError` on the first
    structural violation -- never a partial/best-effort plan."""
    ranking_catalog = registry.catalog(RANKING_CATALOG_ID)

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

    return CompiledComparisonPlan(ranking_policies=ranking_policies)
