"""Unit-family inference and compatibility checking for the closed method
AST (docs/valuation-t71-02-formula-ast-catalog-compilation-specification.md
Section 11).

Currency conversion and scale normalization are explicit upstream/binding
operations with exact refs (T71-B/operand-binder concerns); this module
only checks that an AST's shape and its formula entry's declared operand
unit families compose into the declared output unit -- it never fetches an
FX rate or resolves a real operand value.
"""

from __future__ import annotations

from typing import Mapping

from ..errors import UnitCompatibilityError
from .ast import AddNode, ConstantNode, DivideNode, MethodExpr, MultiplyNode, NegateNode, OperandNode, ScaleConvertNode, SubtractNode

#: docs/valuation-t67-09-units-reasons-rounding-traceability.md Section 2 /
#: config/valuation shared-catalog.json entry ``shared.vocab.unit_family``.
KNOWN_UNIT_FAMILIES = frozenset({
    "amount", "price_per_share", "shares", "ratio", "percentage_display",
    "multiple", "rate", "per_unit_operating", "duration", "rank", "score_integer",
})


def infer_unit_family(node: MethodExpr, operand_units: Mapping[str, str]) -> str:
    """Infer the unit family of ``node`` given each ``operand`` symbol's
    declared ``unit_family``. Raises :class:`UnitCompatibilityError` on any
    incompatible composition (mismatched add/subtract operands, or a
    multiply/divide combination this closed vocabulary does not define a
    family for)."""
    if isinstance(node, OperandNode):
        if node.symbol not in operand_units:
            raise UnitCompatibilityError(f"operand symbol {node.symbol!r} has no declared unit_family")
        return operand_units[node.symbol]

    if isinstance(node, ConstantNode):
        if node.unit not in KNOWN_UNIT_FAMILIES:
            raise UnitCompatibilityError(f"constant node declares unknown unit family: {node.unit!r}")
        return node.unit

    if isinstance(node, (AddNode, MultiplyNode)) and node.__class__ is AddNode:
        families = {infer_unit_family(arg, operand_units) for arg in node.args}
        if len(families) != 1:
            raise UnitCompatibilityError(f"add requires all operands to share one unit family, got {sorted(families)}")
        return next(iter(families))

    if isinstance(node, SubtractNode):
        left = infer_unit_family(node.left, operand_units)
        right = infer_unit_family(node.right, operand_units)
        if left != right:
            raise UnitCompatibilityError(f"subtract requires matching unit families, got {left!r} and {right!r}")
        return left

    if isinstance(node, MultiplyNode):
        families = [infer_unit_family(arg, operand_units) for arg in node.args]
        return _compose_multiply(families)

    if isinstance(node, DivideNode):
        numerator = infer_unit_family(node.numerator, operand_units)
        denominator = infer_unit_family(node.denominator, operand_units)
        return _compose_divide(numerator, denominator)

    if isinstance(node, NegateNode):
        return infer_unit_family(node.arg, operand_units)

    if isinstance(node, ScaleConvertNode):
        family = infer_unit_family(node.arg, operand_units)
        if family != "amount":
            raise UnitCompatibilityError(f"scale_convert only applies to 'amount' quantities, got {family!r}")
        return family

    raise UnitCompatibilityError(f"cannot infer unit family for node type: {type(node).__name__}")  # pragma: no cover


def _compose_multiply(families: list[str]) -> str:
    non_ratio = [f for f in families if f != "ratio"]
    if len(non_ratio) == 0:
        return "ratio"
    if len(non_ratio) == 1:
        return non_ratio[0]
    raise UnitCompatibilityError(f"multiply cannot compose more than one non-ratio unit family, got {sorted(non_ratio)}")


def _compose_divide(numerator: str, denominator: str) -> str:
    if numerator == denominator == "amount":
        # The two known T71 amount/amount outcomes (multiple vs ratio) are
        # not distinguishable from unit family alone -- the catalog entry's
        # own declared output_semantics.unit is authoritative and is
        # checked separately by check_unit_equation().
        return "amount_ratio"
    if numerator == "price_per_share" and denominator == "price_per_share":
        return "ratio"
    raise UnitCompatibilityError(f"divide has no defined composition for {numerator!r} / {denominator!r}")


def check_unit_equation(
    expr: MethodExpr,
    *,
    operand_units: Mapping[str, str],
    declared_output_unit: str,
) -> None:
    """Verify that ``expr``'s inferred unit composition is compatible with
    the catalog entry's own declared ``output_semantics.unit``
    (``"multiple"`` or ``"ratio"`` for T71's amount/amount and
    price_per_share/price_per_share method formulas)."""
    inferred = infer_unit_family(expr, operand_units)
    if inferred == "amount_ratio":
        if declared_output_unit not in ("multiple", "ratio"):
            raise UnitCompatibilityError(f"amount/amount division must declare output unit 'multiple' or 'ratio', got {declared_output_unit!r}")
        return
    if inferred == "ratio":
        if declared_output_unit != "ratio":
            raise UnitCompatibilityError(f"price_per_share/price_per_share division must declare output unit 'ratio', got {declared_output_unit!r}")
        return
    raise UnitCompatibilityError(f"unhandled inferred unit family for output-unit check: {inferred!r}")
