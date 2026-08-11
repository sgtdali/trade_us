"""Controlled formula evaluators.

Every evaluator here is a pure function over Decimal-safe numeric inputs
that returns a structured ``FormulaResult``. There is no expression
evaluation from configuration and no ``eval()`` anywhere in this module;
the formula catalog only ever selects one of these functions by name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def _d(x: Any) -> Decimal:
    if x is None:
        raise ValueError("cannot convert None to Decimal")
    return Decimal(str(x))


def _round(value: Decimal, places: int) -> float:
    quant = Decimal("1." + "0" * places) if places > 0 else Decimal("1")
    return float(value.quantize(quant, rounding=ROUND_HALF_UP))


@dataclass
class FormulaResult:
    status: str  # "available" | "unavailable" | "calculation_blocked" | "not_comparable"
    value: float | None
    reason: str | None = None
    components: dict = field(default_factory=dict)


def linear_combination(terms: list[tuple[float | None, int]], rounding: int) -> FormulaResult:
    """Sum of ``sign * value`` over ``terms``; unavailable if any term is None."""
    if any(v is None for v, _ in terms):
        return FormulaResult("unavailable", None, "one or more input values are unavailable")
    total = sum(_d(v) * sign for v, sign in terms)
    return FormulaResult("available", _round(total, rounding))


def ratio(
    numerator_terms: list[tuple[float | None, int]],
    denominator_terms: list[tuple[float | None, int]],
    rounding: int,
    require_positive_denominator: bool = False,
) -> FormulaResult:
    if any(v is None for v, _ in numerator_terms) or any(v is None for v, _ in denominator_terms):
        return FormulaResult("unavailable", None, "one or more input values are unavailable")
    denominator = sum(_d(v) * sign for v, sign in denominator_terms)
    if denominator == 0:
        return FormulaResult("calculation_blocked", None, "zero denominator")
    if require_positive_denominator and denominator < 0:
        return FormulaResult("not_comparable", None, "ratio undefined against a negative denominator")
    numerator = sum(_d(v) * sign for v, sign in numerator_terms)
    return FormulaResult("available", _round(numerator / denominator, rounding))


def margin_pct(numerator_terms: list[tuple[float | None, int]], denominator_terms: list[tuple[float | None, int]], rounding: int = 2) -> FormulaResult:
    result = ratio(numerator_terms, denominator_terms, rounding=rounding + 2)
    if result.status != "available":
        return result
    return FormulaResult("available", _round(_d(result.value) * 100, rounding))


def abs_ratio_pct(numerator: float | None, denominator: float | None, rounding: int = 1) -> FormulaResult:
    if numerator is None or denominator is None:
        return FormulaResult("unavailable", None, "one or more input values are unavailable")
    if _d(denominator) == 0:
        return FormulaResult("calculation_blocked", None, "zero denominator")
    return FormulaResult("available", _round(abs(_d(numerator)) / _d(denominator) * 100, rounding))


def growth_pct(current: float | None, previous: float | None, rounding: int = 1) -> FormulaResult:
    if current is None or previous is None:
        return FormulaResult("unavailable", None, "current or comparison value is unavailable")
    c, p = _d(current), _d(previous)
    if p == 0:
        return FormulaResult("calculation_blocked", None, "zero denominator")
    if (c >= 0 > p) or (c < 0 <= p):
        return FormulaResult("not_comparable", None, "sign transition between periods is not ordinary percentage growth")
    return FormulaResult("available", _round((c - p) / abs(p) * 100, rounding))


def transition_kind(current: float | None, previous: float | None) -> str | None:
    """Classify a period-over-period sign transition, or None if it's ordinary growth."""
    if current is None or previous is None:
        return None
    c, p = _d(current), _d(previous)
    if p < 0 and c >= 0:
        return "loss_to_profit"
    if p >= 0 and c < 0:
        return "profit_to_loss"
    if p < 0 and c < 0:
        narrowed = abs(c) < abs(p)
        pct_change = (abs(p) - abs(c)) / abs(p) * 100 if p != 0 else Decimal(0)
        if narrowed and pct_change >= 20:
            return "loss_narrowing"
        return "loss_widening" if not narrowed else "loss_narrowing_minor"
    return None


def standard_fcf(operating_cash_flow: float | None, signed_capex: float | None, rounding: int = 1) -> FormulaResult:
    if operating_cash_flow is None or signed_capex is None:
        return FormulaResult("unavailable", None, "operating cash flow or capex is unavailable")
    return FormulaResult("available", _round(_d(operating_cash_flow) + _d(signed_capex), rounding))


def add_signed(values: list[float | None], rounding: int = 1) -> FormulaResult:
    if any(v is None for v in values):
        return FormulaResult("unavailable", None, "one or more input values are unavailable")
    return FormulaResult("available", _round(sum(_d(v) for v in values), rounding))


def passthrough_with_percent_change(current: float | None, previous: float | None, rounding: int = 1) -> FormulaResult:
    """Return ``current`` as-is (already the intended output), attaching a
    percent-of-prior change component rather than recomputing the value."""
    if current is None:
        return FormulaResult("unavailable", None, "value is unavailable")
    growth = growth_pct(current, previous, rounding=rounding) if previous is not None else FormulaResult("unavailable", None)
    return FormulaResult(
        "available",
        _round(_d(current), rounding),
        components={"percent_change_vs_prior": growth.value if growth.status == "available" else None},
    )
