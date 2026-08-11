"""Financial period model: parsing, comparison compatibility, discrete-period
derivation, and trailing-twelve-month (TTM) assembly.

A period id such as ``2026-Q2`` never tells you, on its own, whether the
underlying data is a *discrete* Q2 figure or a *cumulative* H1 figure. This
module treats cumulative/discrete semantics as an explicit, first-class
property (:attr:`Period.is_cumulative`) rather than something inferred from
the label alone, and refuses to combine periods whose semantics, currency,
scale, consolidation, or accounting basis are not known to be compatible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import PeriodError

_FY_RE = re.compile(r"(\d{4})-FY")
_QUARTER_RE = re.compile(r"(\d{4})-Q([1-4])")
_HALF_RE = re.compile(r"(\d{4})-H1")
_NINE_MONTH_RE = re.compile(r"(\d{4})-9M")
_MONTH_RE = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")

QUARTER_ORDER = {"Q1": 1, "H1": 2, "9M": 3, "FY": 4}


@dataclass(frozen=True)
class Period:
    """A parsed financial reporting period.

    ``kind`` is one of ``annual``, ``quarterly``, ``half_year``,
    ``nine_month``, ``monthly``. ``is_cumulative`` indicates whether the
    period's figures are measured from the start of the fiscal year (True)
    or represent only that discrete window (False). A first quarter is
    cumulative and discrete at once, since "year to date through Q1" and
    "Q1 alone" are the same window.
    """

    id: str
    fiscal_year: int
    kind: str
    quarter: int | None
    duration_months: int | None
    is_cumulative: bool

    @property
    def sort_key(self) -> tuple[int, int]:
        """Monotonic key usable to order periods within/adjacent fiscal years."""
        if self.kind == "monthly":
            return (self.fiscal_year, self.quarter or 0)
        order = {"quarterly": 1, "half_year": 2, "nine_month": 3, "annual": 4}
        sub = self.quarter if self.kind == "quarterly" else 0
        return (self.fiscal_year, order[self.kind] * 10 + sub)


def parse_period(period_id: str) -> Period:
    """Parse a period id into a :class:`Period`. Raises :class:`PeriodError`
    on anything not matching one of the supported forms."""
    if m := _FY_RE.fullmatch(period_id):
        return Period(period_id, int(m.group(1)), "annual", None, 12, True)
    if m := _QUARTER_RE.fullmatch(period_id):
        q = int(m.group(2))
        return Period(period_id, int(m.group(1)), "quarterly", q, 3, q == 1)
    if m := _HALF_RE.fullmatch(period_id):
        return Period(period_id, int(m.group(1)), "half_year", 2, 6, True)
    if m := _NINE_MONTH_RE.fullmatch(period_id):
        return Period(period_id, int(m.group(1)), "nine_month", 3, 9, True)
    if m := _MONTH_RE.fullmatch(period_id):
        return Period(period_id, int(m.group(1)), "monthly", int(m.group(2)), 1, False)
    raise PeriodError(f"Invalid period id: {period_id!r}")


@dataclass(frozen=True)
class AccountingContext:
    """The accounting metadata a value must share with another value before
    the two can be safely compared, subtracted, or summed.

    ``publication_date`` and ``source_revision`` are carried for
    traceability but never gate compatibility on their own -- two figures
    from different publication dates/revisions can still be perfectly
    comparable (e.g. a same-filing current/comparison pair always shares
    one publication date already).

    Compatibility rules (see :meth:`compatible_with`):

    - ``currency``/``scale``/``consolidation``/``accounting_basis``/
      ``inflation_adjustment_status``: a genuine, known disagreement (both
      sides populated and different) blocks. Two unset/``None`` sides are
      never treated as a disagreement (there is nothing to disagree
      about) -- the default rule is that current and comparison figures
      share one file-level context unless the file explicitly overrides
      the comparison side, so trivially unset-vs-unset is the common case
      for perfectly comparable same-filing figures, and structural
      *absence* of these fields is instead caught at the schema/validation
      layer (:mod:`fundamental_pipeline.validation.accounting`), not here.
      Note that once populated, the controlled vocabulary value
      ``"undetermined"`` is treated as a real, comparable value like any
      other -- ``"undetermined"`` vs ``"undetermined"`` matches;
      ``"undetermined"`` vs a known value (e.g. ``"applied"``) is a genuine
      disagreement and blocks, so undetermined metadata is never silently
      treated as compatible with *known* metadata on the other side.
    - ``restatement_status``: a comparative recast (``"original"`` current
      vs ``"restated"`` comparison, or vice versa) is the *expected*,
      compatible combination for a same-filing comparison -- restatement
      existing on one side is the point of the field, not a mismatch.
      ``"not_applicable"`` is compatible with anything. Only an asymmetric
      ``"undetermined"`` (one side genuinely unknown, the other a known,
      different status) blocks.
    """

    currency: str | None = None
    scale: str | None = None
    consolidation: str | None = None
    accounting_basis: str | None = None
    inflation_adjustment_status: str | None = None
    restatement_status: str | None = None
    publication_date: str | None = None
    source_revision: str | None = None

    def compatible_with(self, other: "AccountingContext") -> list[str]:
        problems = []
        for field in ("currency", "scale", "consolidation", "accounting_basis", "inflation_adjustment_status"):
            a, b = getattr(self, field), getattr(other, field)
            if a is not None and b is not None and a != b:
                problems.append(f"{field} mismatch: {a!r} vs {b!r}")
        a, b = self.restatement_status, other.restatement_status
        if a not in (None, "not_applicable") and b not in (None, "not_applicable") and a != b and "undetermined" in (a, b):
            problems.append(f"restatement_status undetermined on one side: {a!r} vs {b!r}")
        return problems


def compatible_comparison(period_a: str, period_b: str) -> bool:
    """Whether two periods may be directly compared as reported (same
    duration, same cumulative semantics, same kind)."""
    pa, pb = parse_period(period_a), parse_period(period_b)
    return (
        pa.kind == pb.kind
        and pa.duration_months == pb.duration_months
        and pa.is_cumulative == pb.is_cumulative
    )


@dataclass(frozen=True)
class PeriodValue:
    """A single metric's value tied to a period and accounting context,
    the unit the value is denominated in, and whether the value is a
    duration metric (income statement / cash flow, accumulates over the
    period) or a point-in-time metric (balance sheet, as-of the period end).
    """

    metric_id: str
    period_id: str
    value: float
    unit: str
    is_point_in_time: bool = False
    accounting: AccountingContext = AccountingContext()
    is_derived: bool = False
    formula_id: str | None = None
    source_periods: tuple[str, ...] = ()


def derive_discrete(current: PeriodValue, previous: PeriodValue) -> PeriodValue:
    """Derive a discrete quarter from two cumulative interim periods of the
    same fiscal year, e.g. Q2 discrete = H1 cumulative - Q1 cumulative.

    Both inputs must be cumulative, duration-based (not point-in-time),
    belong to the same fiscal year, be correctly ordered (``current`` after
    ``previous`` in cumulative sequence), share the same metric id, unit,
    and accounting context.
    """
    if current.metric_id != previous.metric_id:
        raise PeriodError(
            f"Cannot derive discrete period across different metrics: "
            f"{current.metric_id!r} vs {previous.metric_id!r}"
        )
    if current.is_point_in_time or previous.is_point_in_time:
        raise PeriodError(
            f"{current.metric_id}: discrete-period derivation only applies to "
            "duration metrics, not point-in-time (balance sheet) metrics"
        )
    pa, pb = parse_period(current.period_id), parse_period(previous.period_id)
    if not (pa.is_cumulative and pb.is_cumulative):
        raise PeriodError(
            f"{current.metric_id}: both {current.period_id} and {previous.period_id} "
            "must be cumulative interim periods"
        )
    if pa.fiscal_year != pb.fiscal_year:
        raise PeriodError(
            f"{current.metric_id}: {current.period_id} and {previous.period_id} "
            "are not in the same fiscal year"
        )
    current_rank = QUARTER_ORDER.get(pa.id.split("-")[1])
    previous_rank = QUARTER_ORDER.get(pb.id.split("-")[1])
    if current_rank is None or previous_rank is None or current_rank != previous_rank + 1:
        raise PeriodError(
            f"{current.metric_id}: {previous.period_id} -> {current.period_id} "
            "is not a valid consecutive cumulative step (Q1->H1->9M->FY)"
        )
    if current.unit != previous.unit:
        raise PeriodError(f"{current.metric_id}: unit mismatch {current.unit!r} vs {previous.unit!r}")
    problems = current.accounting.compatible_with(previous.accounting)
    if problems:
        raise PeriodError(f"{current.metric_id}: incompatible accounting context: {'; '.join(problems)}")

    discrete_kind = {2: "Q2", 3: "Q3", 4: "Q4"}[current_rank]
    discrete_period_id = f"{pa.fiscal_year}-{discrete_kind}"
    return PeriodValue(
        metric_id=current.metric_id,
        period_id=discrete_period_id,
        value=current.value - previous.value,
        unit=current.unit,
        is_point_in_time=False,
        accounting=current.accounting,
        is_derived=True,
        formula_id="discrete_period_subtraction",
        source_periods=(current.period_id, previous.period_id),
    )


def assemble_ttm(quarters: list[PeriodValue]) -> PeriodValue:
    """Assemble a trailing-twelve-month value from exactly four consecutive,
    compatible, discrete quarterly values. Never accepts cumulative inputs
    (Q1/H1/9M/FY figures) and never annualizes a single quarter.
    """
    if len(quarters) != 4:
        raise PeriodError(f"TTM requires exactly four discrete quarters, got {len(quarters)}")

    metric_ids = {q.metric_id for q in quarters}
    if len(metric_ids) != 1:
        raise PeriodError(f"TTM quarters must all be the same metric, got {sorted(metric_ids)}")
    metric_id = quarters[0].metric_id

    if any(q.is_point_in_time for q in quarters):
        raise PeriodError(f"{metric_id}: TTM only applies to duration metrics, not point-in-time metrics")

    units = {q.unit for q in quarters}
    if len(units) != 1:
        raise PeriodError(f"{metric_id}: TTM quarters have mismatched units: {sorted(units)}")

    parsed = []
    for q in quarters:
        p = parse_period(q.period_id)
        if p.kind != "quarterly":
            raise PeriodError(
                f"{metric_id}: TTM input {q.period_id} is not a discrete quarter period id"
            )
        if p.is_cumulative and p.quarter != 1:
            raise PeriodError(
                f"{metric_id}: TTM input {q.period_id} looks cumulative; only true discrete "
                "quarter values (already derived via derive_discrete for Q2-Q4) are accepted"
            )
        parsed.append(p)

    keys = sorted(p.fiscal_year * 4 + (p.quarter or 0) for p in parsed)
    if len(set(keys)) != 4:
        raise PeriodError(f"{metric_id}: TTM quarters contain a duplicate quarter: {sorted(q.period_id for q in quarters)}")
    for a, b in zip(keys, keys[1:]):
        if b - a != 1:
            raise PeriodError(
                f"{metric_id}: TTM quarters are not four consecutive quarters: "
                f"{sorted(q.period_id for q in quarters)}"
            )

    base = quarters[0]
    for q in quarters[1:]:
        problems = base.accounting.compatible_with(q.accounting)
        if problems:
            raise PeriodError(f"{metric_id}: TTM quarters have incompatible accounting context: {'; '.join(problems)}")

    ordered = [q for _, q in sorted(zip(keys, quarters))]
    return PeriodValue(
        metric_id=metric_id,
        period_id=f"{ordered[-1].period_id}-TTM",
        value=sum(q.value for q in ordered),
        unit=base.unit,
        is_point_in_time=False,
        accounting=base.accounting,
        is_derived=True,
        formula_id="ttm_sum_of_four_discrete_quarters",
        source_periods=tuple(q.period_id for q in ordered),
    )
