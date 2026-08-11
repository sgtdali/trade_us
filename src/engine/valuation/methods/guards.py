"""The ordered method guard plan (docs/valuation-t71-02-formula-ast-catalog-compilation-specification.md
Section 4).

Risk and economic-policy behavior (missing-input handling, zero/negative
denominators, claim/currency/scale/period/accounting/lease compatibility,
required capabilities, reconciliation requirements) lives in an ordered,
typed guard plan -- never as a hidden branch inside the AST itself. This
module defines and structurally verifies that plan at compile time; it does
not evaluate guards against real bound operands (that is a T71-B concern,
once real ``valuation-inputs`` operand binding exists).
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ..errors import FormulaCompileError
from .ast import DivideNode, MethodExpr, divide_nodes, iter_operand_symbols

#: docs/valuation-t71-02-*.md Section 4 / config/valuation shared-catalog.json
#: entry ``shared.vocab.guard_type``.
ALLOWED_GUARD_TYPES = frozenset({
    "required_available", "denominator_nonzero", "denominator_positive",
    "claim_match", "currency_match", "scale_match", "period_match",
    "accounting_match", "lease_match", "capability_required",
    "reconciliation_required", "sign_constraint",
})

#: Guard types that establish a symbol is a safe, checked division
#: denominator once satisfied. Ordering-wise, at least one of these must
#: precede any AST division whose denominator resolves to that symbol.
_DENOMINATOR_SAFETY_GUARDS = frozenset({"denominator_nonzero"})


@dataclass(frozen=True)
class GuardStep:
    guard_type: str
    target_symbol: str | None
    extra: Mapping[str, Any]

    @property
    def against_symbol(self) -> str | None:
        return self.extra.get("against_symbol")


def parse_guard_plan(raw: Sequence[Any]) -> tuple[GuardStep, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise FormulaCompileError("guard_plan must be an array")
    steps: list[GuardStep] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise FormulaCompileError(f"guard_plan[{index}]: guard step must be an object")
        guard_type = item.get("guard_type")
        if guard_type not in ALLOWED_GUARD_TYPES:
            raise FormulaCompileError(f"guard_plan[{index}]: unknown or disallowed guard_type: {guard_type!r}")
        target_symbol = item.get("target_symbol")
        if target_symbol is not None and not isinstance(target_symbol, str):
            raise FormulaCompileError(f"guard_plan[{index}]: target_symbol must be a string when present")
        extra = {k: v for k, v in item.items() if k not in ("guard_type", "target_symbol")}
        steps.append(GuardStep(guard_type=guard_type, target_symbol=target_symbol, extra=MappingProxyType(dict(extra))))
    return tuple(steps)


def check_division_guarded(expr: MethodExpr, guard_plan: Sequence[GuardStep]) -> None:
    """Every :class:`~.ast.DivideNode` in ``expr`` must have its exact
    denominator operand symbol covered by a preceding
    ``denominator_nonzero`` guard step. An unguarded division -- one whose
    denominator symbol never appears as the ``target_symbol`` of a
    ``denominator_nonzero`` guard anywhere in the plan -- is a compile-time
    :class:`FormulaCompileError`, not a runtime surprise."""
    guarded_symbols = {step.target_symbol for step in guard_plan if step.guard_type in _DENOMINATOR_SAFETY_GUARDS}
    for node in divide_nodes(expr):
        denominator_symbols = set(iter_operand_symbols(node.denominator))
        if not denominator_symbols:
            # A constant/derived (non-operand) denominator subtree carries
            # no symbol to guard; T71's 13 formulas never do this, but
            # nothing here forbids it structurally -- it simply has no
            # guard-coverage obligation.
            continue
        unguarded = denominator_symbols - guarded_symbols
        if unguarded:
            raise FormulaCompileError(f"division denominator symbol(s) {sorted(unguarded)} have no preceding denominator_nonzero guard")


def check_guard_targets_declared(guard_plan: Sequence[GuardStep], declared_symbols: Sequence[str]) -> None:
    declared = set(declared_symbols)
    for step in guard_plan:
        if step.target_symbol is not None and step.target_symbol not in declared:
            raise FormulaCompileError(f"guard_plan targets undeclared operand symbol: {step.target_symbol!r}")
        against = step.against_symbol
        if against is not None and against not in declared:
            raise FormulaCompileError(f"guard_plan references undeclared operand symbol via against_symbol: {against!r}")
