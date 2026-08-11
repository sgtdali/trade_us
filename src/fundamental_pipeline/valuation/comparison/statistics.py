"""Exact comparison/ranking statistics primitives (T74-A;
docs/valuation-t74-03-eligibility-statistics-ranking-specification.md,
docs/valuation-t67-06-comparison-ranking-policy-catalog.md Sections 7-11,
docs/valuation-t68-07-comparison-strategy-applicability-matrix.md Sections
10-12).

Every formula here operates on exact :class:`fractions.Fraction` values
built from canonical decimal strings via the same
:mod:`~..methods.numeric` module T71/T72 already use -- there is no
second, parallel numeric context for T74 (docs/valuation-implementation.md
Section 6's "no second, parallel numeric context" precedent). Binary
``float`` never appears anywhere in this module. A caller must have
already excluded ineligible/missing/not-meaningful values before calling
any function here: this module has no concept of "excluded" or "missing"
-- it only ever sees an already-eligible sample.
"""

from __future__ import annotations

from fractions import Fraction

from ..errors import ComparisonStatisticsError
from ..methods.numeric import add_exact, divide_exact, project_canonical_scalar, subtract_exact, to_exact_rational

DIRECTIONS = ("higher_is_more_attractive", "lower_is_more_attractive", "neutral_contextual", "not_rankable")

_HALF = Fraction(1, 2)


def _as_fraction(value: Fraction | str) -> Fraction:
    return value if isinstance(value, Fraction) else to_exact_rational(value)


def raw_percentile(subject: Fraction | str, sample: list[Fraction | str]) -> Fraction:
    """``(L + 0.5*E) / N`` for subject value ``x`` against an eligible
    comparator sample (docs/valuation-t67-06-*.md Section 7). ``sample``
    must already be the fully eligible comparator population -- this
    function performs no eligibility filtering of its own. Raises
    :class:`~..errors.ComparisonStatisticsError` for an empty sample
    (a caller must gate on ``N >= 1`` before calling)."""
    if not sample:
        raise ComparisonStatisticsError("raw_percentile: sample must not be empty")
    x = _as_fraction(subject)
    values = [_as_fraction(v) for v in sample]
    less = sum(1 for v in values if v < x)
    equal = sum(1 for v in values if v == x)
    n = len(values)
    return divide_exact(add_exact(Fraction(less), Fraction(equal) * _HALF), Fraction(n))


def attractiveness_percentile(percentile: Fraction, *, direction: str) -> Fraction | None:
    """Apply the registered economic direction to a raw percentile
    (docs/valuation-t67-06-*.md Section 8). ``neutral_contextual``/
    ``not_rankable`` direction always yields ``None`` -- attractiveness is
    never inferred from a method name or value sign, only from this
    explicit, policy-registered direction string."""
    if direction not in DIRECTIONS:
        raise ComparisonStatisticsError(f"unknown direction: {direction!r}")
    if direction == "higher_is_more_attractive":
        return percentile
    if direction == "lower_is_more_attractive":
        return subtract_exact(Fraction(1), percentile)
    return None


def ordinal_midrank(subject: Fraction | str, sample: list[Fraction | str], *, direction: str) -> Fraction:
    """``1 + B + 0.5*E`` within a direction-normalized eligible sample
    (docs/valuation-t67-06-*.md Section 9). ``subject`` is never itself a
    member of ``sample`` -- callers (the peer/Magic engines) are
    responsible for excluding the subject from its own comparator
    population before calling this function (T74 invariant 31/T68's own
    "subject excluded from peer sample" rule). ``B`` counts sample members
    strictly *more attractive* than the subject under ``direction``; ``E``
    counts members economically equal to the subject. Rank 1 is most
    attractive. Alphabetic/ticker/display order never participates."""
    if direction not in ("higher_is_more_attractive", "lower_is_more_attractive"):
        raise ComparisonStatisticsError(f"ordinal_midrank requires a rankable direction, got {direction!r}")
    if not sample:
        raise ComparisonStatisticsError("ordinal_midrank: sample must not be empty")
    x = _as_fraction(subject)
    values = [_as_fraction(v) for v in sample]
    if direction == "higher_is_more_attractive":
        better = sum(1 for v in values if v > x)
    else:
        better = sum(1 for v in values if v < x)
    equal = sum(1 for v in values if v == x)
    return add_exact(Fraction(1), Fraction(better), Fraction(equal) * _HALF)


def type7_quantile(sorted_sample: list[Fraction | str], probability: Fraction | str) -> Fraction:
    """Type-7 linear-interpolation quantile (docs/valuation-t67-06-*.md
    Section 10; ``h = (N-1)*p + 1``, sorted ascending, 1-indexed,
    conventional endpoint handling). ``sorted_sample`` must already be
    sorted ascending by the caller -- this function does not re-sort (a
    caller comparing against a permuted-order property test must control
    sort order explicitly, not rely on this function to fix an unsorted
    input silently)."""
    n = len(sorted_sample)
    if n == 0:
        raise ComparisonStatisticsError("type7_quantile: sample must not be empty")
    p = _as_fraction(probability) if not isinstance(probability, Fraction) else probability
    if p < 0 or p > 1:
        raise ComparisonStatisticsError(f"type7_quantile: probability must be in [0,1], got {p}")
    values = [_as_fraction(v) for v in sorted_sample]
    if n == 1:
        return values[0]

    h = add_exact(Fraction(n - 1) * p, Fraction(1))
    j = int(h)  # floor for a nonnegative h (h is always >= 1 here since p >= 0)
    if j < 1:
        j = 1
    if j >= n:
        return values[n - 1]
    g = subtract_exact(h, Fraction(j))
    lower, upper = values[j - 1], values[j]
    return add_exact((Fraction(1) - g) * lower, g * upper)


def median(sorted_sample: list[Fraction | str]) -> Fraction:
    return project_quantile(sorted_sample, Fraction(1, 2))


def project_quantile(sorted_sample: list[Fraction | str], probability: Fraction | str) -> Fraction:
    """Convenience alias kept distinct from :func:`type7_quantile` only in
    name (median/Q1/Q3 callers read more clearly through this name); same
    exact behavior."""
    return type7_quantile(sorted_sample, probability)


def to_canonical_decimal(value: Fraction) -> str:
    """Project an exact rational statistic to its canonical decimal-string
    output form. The single output boundary for every function in this
    module -- never fed back into another statistic computation (same
    discipline as :func:`~..methods.numeric.project_canonical_scalar`)."""
    return project_canonical_scalar(value)
