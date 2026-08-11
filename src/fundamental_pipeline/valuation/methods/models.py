"""Immutable compiled-plan value types (docs/valuation-t71-01-method-engine-architecture-file-plan.md
Section 8).

A :class:`CompiledMethodPlan` is the immutable output of
:func:`fundamental_pipeline.valuation.methods.compiler.compile_method_catalog`
for one ``valuation.formulas.methods`` catalog entry. It carries everything
T71-B's operand binder and evaluator will need, but this package itself
never binds a real operand or runs an evaluation -- T71-A produces no
valuation-results artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .ast import MethodExpr
from .guards import GuardStep


@dataclass(frozen=True)
class OperandDeclaration:
    operand_id: str
    requiredness: str
    unit_family: str
    allowed_sign: str
    claim_rule: str | None
    period_rule: str | None


@dataclass(frozen=True)
class CompiledMethodPlan:
    formula_id: str
    formula_version: str
    method_id: str
    economic_family_id: str
    variant_dimensions: Mapping[str, Any]
    operand_declarations: tuple[OperandDeclaration, ...]
    guard_plan: tuple[GuardStep, ...]
    expression: MethodExpr
    unit_equation: Mapping[str, Any]
    output_semantics: Mapping[str, Any]
    sign_policy: Mapping[str, Any]
    arithmetic_context_ref: str
    display_policy_ref: str
    reason_mapping: tuple[Mapping[str, Any], ...]
    source_contract_refs: tuple[str, ...]

    @property
    def operand_symbols(self) -> tuple[str, ...]:
        return tuple(decl.operand_id for decl in self.operand_declarations)


@dataclass(frozen=True)
class CompiledMethodRegistry:
    """An immutable, verified collection of every compiled formula entry in
    ``valuation.formulas.methods``, keyed by exact ``formula_id`` (several
    formula IDs -- e.g. the TTM and FY variants of P/E -- may share one
    ``method_id``)."""

    plans_by_formula_id: Mapping[str, CompiledMethodPlan]

    def __post_init__(self) -> None:
        object.__setattr__(self, "plans_by_formula_id", MappingProxyType(dict(self.plans_by_formula_id)))

    def plan(self, formula_id: str) -> CompiledMethodPlan:
        from ..errors import MethodCatalogError

        if formula_id not in self.plans_by_formula_id:
            raise MethodCatalogError(f"unknown or uncompiled formula_id: {formula_id!r}")
        return self.plans_by_formula_id[formula_id]

    def plans_for_method(self, method_id: str) -> tuple[CompiledMethodPlan, ...]:
        return tuple(plan for plan in self.plans_by_formula_id.values() if plan.method_id == method_id)

    @property
    def formula_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.plans_by_formula_id))
