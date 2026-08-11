"""Current-method evaluation: ordered guard execution, then the closed AST,
over exact bound operands (docs/valuation-t71-04-operand-binding-current-method-evaluator-specification.md).

The evaluator contains no ticker branch and no company-name check
anywhere -- role/applicability/family come from the already-resolved
:class:`~.method_sets.ConfiguredRow`, never from a name comparison here.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Any, Mapping

from ..errors import MethodEvaluationError
from .ast import AddNode, ConstantNode, DivideNode, MethodExpr, MultiplyNode, NegateNode, OperandNode, ScaleConvertNode, SubtractNode, iter_operand_symbols
from .method_sets import ConfiguredRow
from .models import CompiledMethodPlan
from .numeric import add_exact, divide_exact, multiply_exact, negate_exact, project_canonical_scalar, scale_convert_exact, subtract_exact, to_exact_rational
from .operands import BoundOperand

#: Guard types this evaluator resolves to a real per-instance check.
#: currency_match is real; claim_match/scale_match/period_match/
#: accounting_match/lease_match are treated as satisfied whenever their
#: referenced symbol(s) are already available (T71-B scope decision --
#: docs/valuation-t70-t74-implementation-todo.md records the exact
#: per-instance ownership/accounting-context metadata this would require
#: is not yet carried by BoundOperand; the T71-A catalog already declares
#: matching claim_rule/period_rule at compile time for every operand pair,
#: which is what keeps this a real, not vacuous, guard at the catalog
#: level). capability_required/reconciliation_required are satisfied
#: whenever the target operand bound successfully (binding itself already
#: encodes "was this capability/reconciliation available").
_GUARD_TO_UNAVAILABLE_CONDITION = {
    "required_available": "required_available_failed",
    "capability_required": "capability_required_failed",
    "reconciliation_required": "reconciliation_required_failed",
    "period_match": "period_match_failed",
    "claim_match": "claim_match_failed",
}


@dataclass(frozen=True)
class MethodEvaluation:
    formula_id: str
    method_id: str
    method_version: str
    economic_family_id: str
    role: str
    variant_id: str
    status: str
    canonical_value: str | None
    numerator: BoundOperand | None
    denominator: BoundOperand | None
    reason_code: str | None
    output_semantics: Mapping[str, Any]
    current_use_eligible: bool
    ranking_eligible: bool
    outcome: str
    applicability_policy_ref: str | None
    requires: tuple[str, ...]


def _reason_for(plan: CompiledMethodPlan, condition: str, *, default_status: str, default_reason: str) -> tuple[str, str]:
    for row in plan.reason_mapping:
        if row.get("condition") == condition:
            return row["status"], row["reason_code"]
    return default_status, default_reason


def _eval_ast(node: MethodExpr, binding: Mapping[str, BoundOperand]) -> Fraction:
    if isinstance(node, OperandNode):
        bound = binding.get(node.symbol)
        if bound is None or not bound.available:
            raise MethodEvaluationError(f"AST references operand {node.symbol!r} that is not an available bound value")
        return bound.value
    if isinstance(node, ConstantNode):
        return to_exact_rational(node.value)
    if isinstance(node, AddNode):
        return add_exact(*[_eval_ast(arg, binding) for arg in node.args])
    if isinstance(node, SubtractNode):
        return subtract_exact(_eval_ast(node.left, binding), _eval_ast(node.right, binding))
    if isinstance(node, MultiplyNode):
        return multiply_exact(*[_eval_ast(arg, binding) for arg in node.args])
    if isinstance(node, DivideNode):
        return divide_exact(_eval_ast(node.numerator, binding), _eval_ast(node.denominator, binding))
    if isinstance(node, NegateNode):
        return negate_exact(_eval_ast(node.arg, binding))
    if isinstance(node, ScaleConvertNode):
        return scale_convert_exact(_eval_ast(node.arg, binding), from_scale=node.from_scale, to_scale=node.to_scale)
    raise MethodEvaluationError(f"unhandled AST node type during evaluation: {type(node).__name__}")  # pragma: no cover


def _operand_symbols(node: MethodExpr) -> set[str]:
    return set(iter_operand_symbols(node))


def evaluate_method(plan: CompiledMethodPlan, row: ConfiguredRow, binding: Mapping[str, BoundOperand]) -> MethodEvaluation:
    """Execute ``plan``'s ordered guard plan against ``binding``, then (only
    if every guard passes) its closed AST, producing one
    :class:`MethodEvaluation`. Never raises for ordinary domain-invalid
    input -- an unsafe/corrupt plan is the only path that raises
    :class:`MethodEvaluationError`, and that can only happen if the plan
    itself failed to compile correctly (a programmer invariant, not a
    reachable runtime state for a plan that passed
    :func:`~.compiler.compile_method_catalog`)."""
    variant_id = "|".join(f"{k}={v}" for k, v in sorted(plan.variant_dimensions.items()))
    numerator_symbols = _operand_symbols(plan.expression.numerator) if isinstance(plan.expression, DivideNode) else set()
    denominator_symbols = _operand_symbols(plan.expression.denominator) if isinstance(plan.expression, DivideNode) else set()

    def _finish(status: str, reason_code: str | None, canonical_value: str | None) -> MethodEvaluation:
        numerator_bound = next((binding[s] for s in numerator_symbols if s in binding), None)
        denominator_bound = next((binding[s] for s in denominator_symbols if s in binding), None)
        available = status == "available"
        ranking_eligible = available and (canonical_value is None or Decimal(canonical_value) >= 0)
        return MethodEvaluation(
            formula_id=plan.formula_id, method_id=plan.method_id, method_version=plan.formula_version,
            economic_family_id=plan.economic_family_id, role=row.role, variant_id=variant_id or "default",
            status=status, canonical_value=canonical_value if available else None,
            numerator=numerator_bound, denominator=denominator_bound,
            reason_code=reason_code, output_semantics=plan.output_semantics,
            current_use_eligible=available, ranking_eligible=ranking_eligible,
            outcome=row.outcome, applicability_policy_ref=row.applicability_policy_ref, requires=row.requires,
        )

    if row.outcome in ("not_applicable", "deferred_not_implemented"):
        return _finish("not_applicable", "applicability.company_type_not_implemented", None)

    for guard in plan.guard_plan:
        if guard.guard_type == "required_available":
            bound = binding.get(guard.target_symbol)
            if bound is None or not bound.available:
                status, reason_code = _reason_for(plan, "required_available_failed", default_status="unavailable", default_reason="method.period_basis_unavailable")
                return _finish(status, reason_code, None)

        elif guard.guard_type == "denominator_nonzero":
            bound = binding.get(guard.target_symbol)
            if bound is not None and bound.available and bound.sign_state == "zero":
                status, reason_code = _reason_for(plan, "denominator_zero", default_status="not_meaningful", default_reason="method.denominator_zero")
                return _finish(status, reason_code, None)

        elif guard.guard_type == "denominator_positive":
            bound = binding.get(guard.target_symbol)
            if bound is not None and bound.available and bound.sign_state == "negative":
                status, reason_code = _reason_for(plan, "denominator_negative", default_status="not_meaningful", default_reason="method.denominator_negative")
                return _finish(status, reason_code, None)

        elif guard.guard_type == "sign_constraint":
            bound = binding.get(guard.target_symbol)
            require = guard.extra.get("require")
            if bound is not None and bound.available and require == "positive" and bound.sign_state != "positive":
                status, reason_code = _reason_for(plan, "sign_constraint_failed", default_status="not_meaningful", default_reason="method.enterprise_value_nonpositive")
                return _finish(status, reason_code, None)

        elif guard.guard_type == "currency_match":
            bound = binding.get(guard.target_symbol)
            against = binding.get(guard.against_symbol) if guard.against_symbol else None
            if bound is not None and against is not None and bound.available and against.available and bound.currency and against.currency and bound.currency != against.currency:
                status, reason_code = _reason_for(plan, "claim_match_failed", default_status="calculation_blocked", default_reason="method.parent_claim_mismatch")
                return _finish(status, reason_code, None)

        elif guard.guard_type in _GUARD_TO_UNAVAILABLE_CONDITION:
            bound = binding.get(guard.target_symbol)
            if bound is None or not bound.available:
                condition = _GUARD_TO_UNAVAILABLE_CONDITION[guard.guard_type]
                status, reason_code = _reason_for(plan, condition, default_status="unavailable", default_reason="method.period_basis_unavailable")
                return _finish(status, reason_code, None)

        # claim_match/scale_match/accounting_match/lease_match beyond the
        # unavailable-target check above are satisfied by construction at
        # this scope (see module docstring).

    try:
        result = _eval_ast(plan.expression, binding)
    except MethodEvaluationError:
        raise
    except ZeroDivisionError:
        status, reason_code = _reason_for(plan, "denominator_zero", default_status="not_meaningful", default_reason="method.denominator_zero")
        return _finish(status, reason_code, None)

    canonical = project_canonical_scalar(result)
    return _finish("available", None, canonical)


def reconstruct_minimal_evaluations(method_results: "list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]") -> tuple[MethodEvaluation, ...]:
    """Reconstruct enough of each :class:`MethodEvaluation` from an
    already-assembled ``method_results[]`` array to re-run
    :mod:`.families`/coverage recomputation against it -- used only by
    ``validation/methods.py`` to independently re-derive coverage/family
    sufficiency from a committed artifact, never by the evaluator itself.
    ``numerator``/``denominator``/``reason_code``/``output_semantics`` are
    not reconstructed (the validator does not need them for this purpose)."""
    reconstructed: list[MethodEvaluation] = []
    for result in method_results:
        reconstructed.append(MethodEvaluation(
            formula_id=result["formula_ref"]["formula_id"],
            method_id=result["method_id"],
            method_version=result["method_version"],
            economic_family_id=result["economic_family_id"],
            role=result["role"],
            variant_id=result["variant_id"],
            status=result["status"],
            canonical_value=(result.get("canonical_value") or {}).get("value"),
            numerator=None,
            denominator=None,
            reason_code=None,
            output_semantics={},
            current_use_eligible=result["current_use_eligible"],
            ranking_eligible=result["ranking_eligible"],
            outcome=result["applicability"]["outcome"],
            applicability_policy_ref=result["applicability"].get("applicability_policy_ref"),
            requires=(),
        ))
    return tuple(reconstructed)
