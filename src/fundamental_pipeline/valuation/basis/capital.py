"""Generic, allowlisted evaluator over the accepted capital-basis formula
AST (``config/valuation/capital-basis-formulas.json``,
docs/valuation-t70-05-financial-basis-input-resolver-specification.md
Section 10).

No ``eval``/``exec``/dynamic import/embedded Python expression is used.
Only the AST operations actually present in the locked catalog are
allowlisted: ``add``, ``subtract``, ``multiply``, ``divide`` (n-ary,
binary-recursive arithmetic over named scalar operands) and ``sum``
(ledger-aggregate reduction over a *sequence* of same-role components,
used only by ``val.formula.capital.eligible_cash_total``). Rounding is
never applied here: ``shared.policy.rounding_default`` is explicit that
"canonical/intermediate arithmetic values are never rounded ... a
display-rounded value is never fed back into a formula" -- this module
always returns full-precision :class:`decimal.Decimal` results, isolated
from the ambient process :class:`decimal.Context` via a local context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Context, Decimal
from typing import Any, Mapping, Sequence, Union

_ALLOWED_OPS = frozenset({"add", "subtract", "multiply", "divide", "sum"})

#: Named literal constants an AST leaf may reference when the name is not
#: one of the formula's declared operands (e.g. ``val.formula.capital.
#: implied_return_vs_spot``'s ``{"ref": "one"}`` leaf).
_NAMED_CONSTANTS = {"one": Decimal(1)}

_CONTEXT = Context(prec=50)

#: Formulas whose output must be strictly positive per their own catalog
#: ``missing_data_behavior`` -- a non-positive result is ``calculation_blocked``,
#: never a silently-negative or zero market-facing quantity.
_RESULT_MUST_BE_POSITIVE = frozenset({"val.formula.capital.spot_basic_shares"})

#: Formula -> named input operand that must itself be strictly positive per
#: the formula's own catalog ``missing_data_behavior`` (found 2026-07-26,
#: ARCLK: both fcf_*_parent_share entries document "total_net_income == 0
#: (or non-positive) is calculation_blocked, not unavailable", but the
#: generic divide op below only ever guards against exactly zero -- a
#: negative total_net_income silently produced a numerically well-formed
#: but economically meaningless "ownership share" outside [0, 1], e.g. a
#: >100% or negative parent attribution when parent/total net income carry
#: different signs). Checked before the AST is evaluated at all, since the
#: bad divisor is a named operand, not the formula's own output.
_DIVISOR_MUST_BE_POSITIVE = {
    "val.formula.capital.fcf_standard_equity_parent_share": "total_net_income",
    "val.formula.capital.fcf_after_lease_equity_parent_share": "total_net_income",
}


@dataclass(frozen=True)
class Operand:
    """One resolved input value for a formula: an availability status plus
    (only when ``status == "available"``) a :class:`~decimal.Decimal`
    value. Never a bare number -- an absent/blocked operand stays absent."""

    status: str
    value: Decimal | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status == "available" and self.value is None:
            raise ValueError("Operand(status='available') requires a value")
        if self.status != "available" and self.value is not None:
            raise ValueError(f"Operand(status={self.status!r}) forbids a value")


OperandInput = Union[Operand, Sequence[Operand]]


@dataclass(frozen=True)
class FormulaOutcome:
    """The result of evaluating one catalog formula entry: an explicit
    availability envelope, never a bare number. ``operand_snapshot``
    preserves exactly which named operands were consulted and their own
    status, for lineage/diagnostics."""

    status: str
    value: Decimal | None = None
    reason_codes: tuple[str, ...] = ()
    formula_id: str = ""
    formula_version: str = ""
    output_id: str = ""
    operand_snapshot: Mapping[str, str] = field(default_factory=dict)


def evaluate_formula(entry: Mapping[str, Any], operands: Mapping[str, OperandInput]) -> FormulaOutcome:
    """Evaluate one locked catalog formula ``entry`` (as returned by
    ``CatalogRegistry.select_entry(...).entry``) against a caller-supplied
    ``operands`` mapping (``input_id -> Operand`` for scalar inputs, or
    ``input_id -> Sequence[Operand]`` for a ledger-aggregate "sum" input).

    Never raises for ordinary domain-invalid input (missing/blocked
    operand, division by zero, unknown AST shape) -- those all become an
    explicit non-``available`` :class:`FormulaOutcome`. Malformed operand
    values that are programmer errors (wrong Python type in ``operands``)
    still raise, since those can never come from validated JSON input.
    """
    body = entry.get("body", {})
    formula_id = entry.get("entry_id", "")
    formula_version = entry.get("entry_version", "")
    output = body.get("output", {})
    output_id = output.get("output_id", "")
    ast = body.get("ast")
    inputs_spec = {i["input_id"]: i for i in body.get("inputs", ())}

    operand_snapshot = {
        input_id: _status_of(operands.get(input_id))
        for input_id in inputs_spec
    }

    if not isinstance(ast, Mapping):
        return FormulaOutcome(
            status="calculation_blocked",
            reason_codes=("capital.formula_ast_invalid",),
            formula_id=formula_id, formula_version=formula_version, output_id=output_id,
            operand_snapshot=operand_snapshot,
        )

    divisor_input_id = _DIVISOR_MUST_BE_POSITIVE.get(formula_id)
    if divisor_input_id is not None:
        divisor_operand = operands.get(divisor_input_id)
        if (
            isinstance(divisor_operand, Operand)
            and divisor_operand.status == "available"
            and divisor_operand.value is not None
            and divisor_operand.value <= 0
        ):
            return FormulaOutcome(
                status="calculation_blocked",
                reason_codes=("capital.nonpositive_total_net_income",),
                formula_id=formula_id, formula_version=formula_version, output_id=output_id,
                operand_snapshot=operand_snapshot,
            )

    try:
        value, reasons = _eval_node(ast, operands, inputs_spec)
    except _BlockedFormula as exc:
        return FormulaOutcome(
            status="calculation_blocked",
            reason_codes=exc.reason_codes,
            formula_id=formula_id, formula_version=formula_version, output_id=output_id,
            operand_snapshot=operand_snapshot,
        )

    if value is None:
        return FormulaOutcome(
            status="unavailable",
            reason_codes=reasons or ("capital.required_operand_missing",),
            formula_id=formula_id, formula_version=formula_version, output_id=output_id,
            operand_snapshot=operand_snapshot,
        )

    if formula_id in _RESULT_MUST_BE_POSITIVE and value <= 0:
        return FormulaOutcome(
            status="calculation_blocked",
            reason_codes=("capital.nonpositive_basic_shares",),
            formula_id=formula_id, formula_version=formula_version, output_id=output_id,
            operand_snapshot=operand_snapshot,
        )

    return FormulaOutcome(
        status="available",
        value=value,
        reason_codes=reasons,
        formula_id=formula_id, formula_version=formula_version, output_id=output_id,
        operand_snapshot=operand_snapshot,
    )


class _BlockedFormula(Exception):
    def __init__(self, *reason_codes: str) -> None:
        super().__init__(reason_codes)
        self.reason_codes = reason_codes


def _status_of(operand: OperandInput | None) -> str:
    if operand is None:
        return "unavailable"
    if isinstance(operand, Operand):
        return operand.status
    statuses = {o.status for o in operand}
    if not statuses:
        return "unavailable"
    return "available" if "available" in statuses else "unavailable"


def _eval_node(node: Any, operands: Mapping[str, OperandInput], inputs_spec: Mapping[str, Any]) -> tuple[Decimal | None, tuple[str, ...]]:
    """Returns ``(value_or_None, reason_codes)``. ``value is None`` means
    the subtree is unavailable (missing/blocked operand), not an error --
    the caller decides whether that makes the whole formula unavailable."""
    if not isinstance(node, Mapping):
        raise _BlockedFormula("capital.formula_ast_invalid")

    if "ref" in node:
        name = node["ref"]
        if name in operands:
            operand = operands[name]
            if isinstance(operand, Operand):
                if operand.status != "available":
                    return None, operand.reason_codes
                return operand.value, ()
            raise _BlockedFormula("capital.formula_ast_invalid")
        if name in inputs_spec:
            # Declared as a valid operand for this formula, but the caller
            # simply did not supply a value -- missing, never a fabricated
            # zero and never treated as a catalog/AST corruption.
            return None, ("capital.required_operand_missing",)
        if name in _NAMED_CONSTANTS:
            return _NAMED_CONSTANTS[name], ()
        raise _BlockedFormula("capital.unknown_operand")

    op = node.get("op")
    if op not in _ALLOWED_OPS:
        raise _BlockedFormula("capital.unknown_operation")
    args = node.get("args")
    if not isinstance(args, (list, tuple)) or not args:
        raise _BlockedFormula("capital.formula_ast_invalid")

    if op == "sum":
        if len(args) != 1 or "ref" not in args[0]:
            raise _BlockedFormula("capital.formula_ast_invalid")
        name = args[0]["ref"]
        components = operands.get(name)
        if components is None:
            raise _BlockedFormula("capital.unknown_operand")
        if isinstance(components, Operand):
            components = (components,)
        available = [c.value for c in components if c.status == "available"]
        excluded = [c for c in components if c.status != "available"]
        if not available:
            reasons = tuple(sorted({rc for c in excluded for rc in c.reason_codes})) or ("capital.cash_component_unresolved",)
            return None, reasons
        total = _CONTEXT.create_decimal(0)
        for value in available:
            total = _CONTEXT.add(total, value)
        reasons = ("capital.cash_component_unresolved",) if excluded else ()
        return total, reasons

    if op == "add":
        # Each leaf ref's own declared requiredness governs whether a
        # missing value blocks the whole sum or is simply excluded from it
        # (docs/valuation-t70-05-financial-basis-input-resolver-specification.md
        # Section 12, "Optional absent component behavior comes from
        # formula metadata"): a "required" operand missing always blocks;
        # a "conditional"/"optional_diagnostic" operand missing is
        # excluded from the sum and flagged, never fabricated as zero and
        # never allowed to block components that *are* known.
        total: Decimal | None = None
        reasons: list[str] = []
        any_included = False
        for arg in args:
            requiredness = None
            if isinstance(arg, Mapping) and "ref" in arg and arg["ref"] in inputs_spec:
                requiredness = inputs_spec[arg["ref"]].get("requiredness")
            if requiredness in ("conditional", "optional_diagnostic"):
                operand = operands.get(arg["ref"])
                if isinstance(operand, Operand) and operand.status == "available":
                    total = operand.value if total is None else _CONTEXT.add(total, operand.value)
                    any_included = True
                else:
                    reasons.extend(operand.reason_codes if isinstance(operand, Operand) else ("capital.required_operand_missing",))
                continue
            value, sub_reasons = _eval_node(arg, operands, inputs_spec)
            reasons.extend(sub_reasons)
            if value is None:
                return None, tuple(reasons)
            total = value if total is None else _CONTEXT.add(total, value)
            any_included = True
        if not any_included:
            return None, tuple(reasons) or ("capital.required_operand_missing",)
        return total, tuple(reasons)

    values: list[Decimal] = []
    reasons = []
    for arg in args:
        value, sub_reasons = _eval_node(arg, operands, inputs_spec)
        reasons.extend(sub_reasons)
        if value is None:
            return None, tuple(reasons)
        values.append(value)

    if op == "subtract":
        if len(values) != 2:
            raise _BlockedFormula("capital.formula_ast_invalid")
        return _CONTEXT.subtract(values[0], values[1]), tuple(reasons)
    if op == "multiply":
        result = values[0]
        for v in values[1:]:
            result = _CONTEXT.multiply(result, v)
        return result, tuple(reasons)
    if op == "divide":
        if len(values) != 2:
            raise _BlockedFormula("capital.formula_ast_invalid")
        if values[1] == 0:
            raise _BlockedFormula("capital.division_by_zero")
        return _CONTEXT.divide(values[0], values[1]), tuple(reasons)

    raise _BlockedFormula("capital.unknown_operation")
