"""Exact numeric primitives for the T71 method engine.

Three levels are kept deliberately separate (docs/valuation-t71-02-formula-ast-catalog-compilation-specification.md
Section 7):

1. **Source Decimal**: a validated finite base-10 canonical decimal string
   (:func:`engine.valuation.canonical.normalize_decimal`).
2. **Exact internal ratio**: an exact :class:`fractions.Fraction` built from
   a source Decimal -- division and reconciliation happen here, never on a
   binary float and never on a display-rounded string.
3. **Canonical scalar**: a Decimal projection of an exact ratio, computed
   under the locked, ambient-context-independent
   :data:`METHOD_ARITHMETIC_CONTEXT` (50 significant digits,
   ``ROUND_HALF_EVEN``) -- this is a display/output-boundary operation and
   is never fed back into another formula.

Binary ``float`` never appears anywhere in this module.
"""

from __future__ import annotations

from decimal import Context, Decimal, DivisionByZero, InvalidOperation, Overflow, Underflow
from fractions import Fraction

from ..canonical import normalize_decimal
from ..errors import CanonicalizationError

#: docs/valuation-t71-02-*.md Section 8 / config/valuation shared-catalog.json
#: entry ``val.numeric.context.method.v1``. This :class:`decimal.Context` is
#: constructed explicitly and used only via its own ``.divide``/``.plus``
#: methods -- it is never installed as the ambient
#: :func:`decimal.getcontext`/``setcontext`` context, so no other code path
#: (and no ambient-context mutation by a caller) can ever influence a
#: projection made through it.
METHOD_ARITHMETIC_CONTEXT = Context(
    prec=50,
    rounding="ROUND_HALF_EVEN",
    Emin=-1000,
    Emax=1000,
    traps=[InvalidOperation, DivisionByZero, Overflow, Underflow],
)


def to_exact_rational(decimal_string: str) -> Fraction:
    """Convert a canonical (or canonicalizable) decimal string to an exact
    :class:`fractions.Fraction`. Rejects binary float, NaN, infinity, and
    negative zero via :func:`normalize_decimal` first -- the ``Fraction``
    is always built from the *normalized* string, never from a raw,
    unvalidated one."""
    canonical = normalize_decimal(decimal_string)
    return Fraction(Decimal(canonical))


def add_exact(*values: Fraction) -> Fraction:
    total = Fraction(0)
    for value in values:
        total += value
    return total


def subtract_exact(left: Fraction, right: Fraction) -> Fraction:
    return left - right


def multiply_exact(*values: Fraction) -> Fraction:
    product = Fraction(1)
    for value in values:
        product *= value
    return product


def divide_exact(numerator: Fraction, denominator: Fraction) -> Fraction:
    """Exact rational division. The caller is responsible for having
    already run the ``denominator_nonzero`` guard -- this function raises
    :class:`ZeroDivisionError` on a zero denominator rather than silently
    producing an infinite/undefined result, but guard evaluation (and its
    mapping to a ``not_meaningful`` method status) is a T71-B concern."""
    if denominator == 0:
        raise ZeroDivisionError("divide_exact: denominator is exactly zero")
    return numerator / denominator


def negate_exact(value: Fraction) -> Fraction:
    return -value


#: docs/valuation-t67-09-units-reasons-rounding-traceability.md Section 4 /
#: config/valuation shared-catalog.json entry ``shared.vocab.scale``.
SCALE_MULTIPLIERS: dict[str, Fraction] = {
    "units": Fraction(1),
    "thousands": Fraction(1_000),
    "millions": Fraction(1_000_000),
    "billions": Fraction(1_000_000_000),
}


def scale_convert_exact(value: Fraction, *, from_scale: str, to_scale: str) -> Fraction:
    """Exact power-of-ten scale conversion. Unknown scale IDs are a
    programmer/catalog error, never a best-effort no-op."""
    if from_scale not in SCALE_MULTIPLIERS:
        raise CanonicalizationError(f"unknown source scale: {from_scale!r}")
    if to_scale not in SCALE_MULTIPLIERS:
        raise CanonicalizationError(f"unknown target scale: {to_scale!r}")
    return value * SCALE_MULTIPLIERS[from_scale] / SCALE_MULTIPLIERS[to_scale]


def project_canonical_scalar(value: Fraction) -> str:
    """Project an exact rational to its canonical decimal-string form under
    the locked :data:`METHOD_ARITHMETIC_CONTEXT` -- a terminating ratio
    projects to its exact value; a non-terminating (repeating) ratio is
    rounded once, here, at this single output boundary, under
    ``ROUND_HALF_EVEN``. This value is a *display/output* projection: it is
    never itself converted back to a ``Fraction`` and fed into another
    formula step -- callers that need to reconcile two ratios (e.g. an
    inverse-method identity) must do so on the exact ``Fraction`` values via
    :func:`exact_cross_product_equal`, never on this projected string.
    """
    numerator, denominator = value.numerator, value.denominator
    quotient = METHOD_ARITHMETIC_CONTEXT.divide(Decimal(numerator), Decimal(denominator))
    return normalize_decimal(quotient)


def exact_cross_product_equal(n1: Fraction, d1: Fraction, n2: Fraction, d2: Fraction) -> bool:
    """Exact inverse/reconciliation check for two ratios ``n1/d1`` and
    ``n2/d2`` via integer-coefficient cross products (``n1*d2 == n2*d1``).
    Never multiplies a canonical *projected* (rounded) scalar string -- a
    repeating decimal must never appear to "mismatch" its own exact
    inverse merely because two independent roundings of it differ in their
    last digit."""
    return n1 * d2 == n2 * d1
