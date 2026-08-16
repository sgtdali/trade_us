"""Exact decimal arithmetic and its canonical string form.

Every number that touches money, share counts or weights is a
``decimal.Decimal`` in memory and a canonical string on disk. Binary floats are
never used: 0.1 + 0.2 is not 0.3, and a ledger that drifts by a cent per fill
is a ledger that cannot be reconciled against a broker statement.

Canonical form (matching the ``decimalString`` pattern in the schemas): no
leading zeros beyond a bare "0", no trailing fractional zeros, no exponent
notation, and no negative zero. One value, one spelling -- which is what makes
content digests meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from typing import Any, Mapping

from .errors import FundError

#: Wide enough that intermediate products of realistic share counts and prices
#: never round, narrow enough to keep a bound on pathological input.
PRECISION = 34


class MoneyError(FundError):
    """A monetary or decimal value was malformed, or currencies were mixed."""


def to_decimal(value: str | int | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, int):
        parsed = Decimal(value)
    elif isinstance(value, str):
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise MoneyError(f"not a decimal: {value!r}") from exc
    else:
        raise MoneyError(f"refusing to build a Decimal from {type(value).__name__}: {value!r}")
    if not parsed.is_finite():
        raise MoneyError(f"decimal must be finite: {value!r}")
    return parsed


def to_string(value: Decimal | str | int) -> str:
    """Render a decimal in the one spelling the schemas accept."""
    decimal_value = to_decimal(value)

    if decimal_value == 0:
        return "0"

    normalized = decimal_value.normalize()
    sign, digits, exponent = normalized.as_tuple()
    if isinstance(exponent, int) and exponent > 0:
        # normalize() turns 100 into 1E+2; expand it back to plain digits.
        normalized = normalized.quantize(Decimal(1))

    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def format_display(value: Decimal | str | int, places: int = 2) -> str:
    """Round for a human to read. Never for storage.

    Exact arithmetic produces figures like 2744.444444444444444444; a position
    table needs 2744.44. The rounding lives here, at the edge, so no rounded
    value can travel back into the ledger.
    """
    decimal_value = to_decimal(value)
    quantum = Decimal(1).scaleb(-places)
    return f"{decimal_value.quantize(quantum, rounding=ROUND_HALF_EVEN):,}"


def add(*values: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = PRECISION
        total = Decimal(0)
        for value in values:
            total += value
        return total


def multiply(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return left * right


def divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        raise MoneyError("division by zero")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return numerator / denominator


@dataclass(frozen=True)
class Money:
    """An amount that knows its currency. A bare number is never money."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not (isinstance(self.currency, str) and len(self.currency) == 3 and self.currency.isupper()):
            raise MoneyError(f"currency must be an ISO 4217 alphabetic code: {self.currency!r}")

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "Money":
        try:
            amount, currency = document["amount"], document["currency"]
        except (KeyError, TypeError) as exc:
            raise MoneyError(f"not a money document: {document!r}") from exc
        return cls(to_decimal(amount), currency)

    @classmethod
    def parse(cls, amount: str | int | Decimal, currency: str) -> "Money":
        return cls(to_decimal(amount), currency)

    def to_document(self) -> dict[str, str]:
        return {"amount": to_string(self.amount), "currency": self.currency}

    def _same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise MoneyError(
                f"refusing to combine {self.currency} and {other.currency}: "
                "convert explicitly with a dated rate instead"
            )

    def __add__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(add(self.amount, other.amount), self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(add(self.amount, -other.amount), self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def scaled_by(self, factor: Decimal | str | int) -> "Money":
        return Money(multiply(self.amount, to_decimal(factor)), self.currency)

    def is_zero(self) -> bool:
        return self.amount == 0

    def __str__(self) -> str:
        return f"{to_string(self.amount)} {self.currency}"


def zero(currency: str) -> Money:
    return Money(Decimal(0), currency)


def basis_points_to_fraction(bps: int) -> Decimal:
    """10000 bp is 1. Policy thresholds are integers; the fraction is exact."""
    return divide(Decimal(bps), Decimal(10000))


def fraction_to_basis_points(fraction: Decimal) -> Decimal:
    """Not rounded to an integer: computed weights keep their precision."""
    return multiply(fraction, Decimal(10000))
