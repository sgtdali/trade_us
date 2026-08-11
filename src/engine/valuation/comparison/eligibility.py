"""Exact observation-eligibility classification (T74-A;
docs/valuation-t74-03-eligibility-statistics-ranking-specification.md
Section 2, docs/valuation-t67-06-comparison-ranking-policy-catalog.md
Section 3, docs/valuation-t68-07-comparison-strategy-applicability-matrix.md
Section 4).

Eligibility always runs *before* statistics (T74 invariant 11): nothing in
this module computes a percentile, rank, or quantile -- it only decides,
for one candidate observation at a time, whether it becomes an eligible
sample member, a provisional-only member, or an excluded observation with
a stable reason. ``missing``/``not_applicable``/``not_meaningful``/
``calculation_blocked``/``not_comparable`` never become a sample value
(T74 invariant 13-16).
"""

from __future__ import annotations

import operator as _operator
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping

from ..errors import ComparisonStatisticsError
from .policies import RankingGateRule

ELIGIBILITY_STATES = ("eligible", "provisional", "excluded_insufficient_data")

_COMPARATORS = {
    ">": _operator.gt, ">=": _operator.ge, "<": _operator.lt, "<=": _operator.le, "==": _operator.eq, "!=": _operator.ne,
}

#: Candidate ``availabilityStatus`` values that can never enter a sample,
#: regardless of any other gate (docs/valuation-t67-06-*.md Section 3's
#: "missing, not_applicable, not_meaningful, calculation_blocked,
#: not_comparable is not a sample value").
_NEVER_SAMPLE_STATUSES = frozenset({
    "unavailable", "not_applicable", "not_meaningful", "calculation_blocked", "not_comparable",
})


@dataclass(frozen=True)
class EligibilityDecision:
    observation_id: str
    eligibility_state: str
    reason_codes: tuple[str, ...]
    included_in_statistic: bool



def classify_observation_status(status: str) -> tuple[bool, str | None]:
    """Return ``(can_enter_sample, reason_code)`` for one raw
    ``availabilityStatus`` value alone (before any duplicate/cadence/
    coverage gate is applied). ``status == 'available'`` is the only
    status that can ever proceed to a sample; every other status is
    excluded here with a stable reason, never coerced to zero."""
    if status == "available":
        return True, None
    if status in _NEVER_SAMPLE_STATUSES:
        return False, "comparison.rank_ineligible_value"
    if status in ("provisional", "insufficient_data"):
        return False, "comparison.insufficient_history"
    return False, "comparison.rank_ineligible_value"


def deduplicate_by_canonical_key(
    candidates: list[Mapping[str, object]], *, key_fields: tuple[str, ...],
) -> tuple[list[Mapping[str, object]], list[tuple[Mapping[str, object], str]]]:
    """Exact-key deduplication for observations sharing the same
    company/method/as-of/basis identity (docs/valuation-t74-03-*.md
    Section 12: "Duplicate same company/method/as-of/basis cannot both
    enter sample"). Returns ``(kept, excluded_with_reason)``; the first
    candidate under each key wins (callers are responsible for having
    already sorted ``candidates`` into the policy's exact precedence
    order before calling this function -- this function never itself
    decides which duplicate is canonical)."""
    seen: dict[tuple[object, ...], Mapping[str, object]] = {}
    excluded: list[tuple[Mapping[str, object], str]] = []
    kept: list[Mapping[str, object]] = []
    for candidate in candidates:
        key = tuple(candidate[field] for field in key_fields)
        if key in seen:
            excluded.append((candidate, "comparison.tier_mixing"))
            continue
        seen[key] = candidate
        kept.append(candidate)
    return kept, excluded


def one_observation_per_calendar_month(
    candidates: list[Mapping[str, object]], *, month_key_field: str = "calendar_month", precedence_field: str = "cutoff_instant",
) -> tuple[list[Mapping[str, object]], list[tuple[Mapping[str, object], str]]]:
    """Canonical monthly cadence selection (docs/valuation-t67-06-*.md
    Section 4: "Aynı ay birden çok observation sample'ı şişiremez").
    Candidates must already carry a precomputed ``calendar_month`` key
    (``YYYY-MM``, derived by the caller from ``as_of_date`` -- this
    function performs no date arithmetic itself, only grouping/selection).
    Within one month, the candidate with the latest ``precedence_field``
    value wins deterministically; every other same-month candidate is
    excluded with a stable reason -- multiple daily observations can
    never inflate ``N`` (T74 invariants 29-30)."""
    by_month: dict[object, list[Mapping[str, object]]] = {}
    for candidate in candidates:
        by_month.setdefault(candidate[month_key_field], []).append(candidate)

    kept: list[Mapping[str, object]] = []
    excluded: list[tuple[Mapping[str, object], str]] = []
    for month in sorted(by_month, key=str):
        group = sorted(by_month[month], key=lambda c: str(c[precedence_field]))
        winner = group[-1]
        kept.append(winner)
        for loser in group[:-1]:
            excluded.append((loser, "comparison.tier_mixing"))
    return kept, excluded


def _evaluate_gate_node(node: Mapping[str, Any], sample_shape: Mapping[str, int | Fraction]) -> bool:
    """Evaluate one compiled ``RankingGateRule.when`` node against a
    sample's actual shape counters (T74-B runtime counterpart of
    :mod:`.compiler`'s compile-time-only structural validation -- this
    function is the only place a gate predicate is ever *evaluated*, never
    just checked for well-formedness). ``sample_shape`` values must
    already be exact ``int``/``fractions.Fraction`` -- never a binary
    ``float`` or a lossy ``Decimal`` division result (a coverage ratio
    like ``5/7`` has no exact terminating decimal, so comparing it against
    a ``0.70`` threshold must happen in exact rational arithmetic, the
    same discipline as every other T74 statistic)."""
    op = node["op"]
    if op == "compare":
        field = node["field"]
        if field not in sample_shape:
            raise ComparisonStatisticsError(f"gate predicate references unset sample field: {field!r}")
        actual = sample_shape[field]
        threshold = Fraction(str(node["threshold"]))
        return _COMPARATORS[node["comparator"]](Fraction(actual) if not isinstance(actual, Fraction) else actual, threshold)
    if op == "all":
        return all(_evaluate_gate_node(child, sample_shape) for child in node["of"])
    if op == "any":
        return any(_evaluate_gate_node(child, sample_shape) for child in node["of"])
    raise ComparisonStatisticsError(f"unknown gate operator at runtime: {op!r}")


def select_gate_outcome(gate_table: tuple[RankingGateRule, ...], sample_shape: Mapping[str, int | Fraction]) -> RankingGateRule:
    """Select the first (in authored gate_table order) rule whose ``when``
    predicate matches ``sample_shape`` -- the single runtime entry point
    both the historical and peer engines use to turn raw sample counters
    into an eligibility_state/statistics_allowed decision (T74.3 Section
    6; T67.6 Sections 5-6). A well-formed policy's last rule is always an
    unconditional catch-all (``eligible_count >= 0``), so this only raises
    :class:`~..errors.ComparisonStatisticsError` for a genuinely malformed
    policy, never for an ordinary undersized sample."""
    for rule in gate_table:
        if _evaluate_gate_node(rule.when, sample_shape):
            return rule
    raise ComparisonStatisticsError("gate_table exhausted without a matching rule -- policy is not total")
