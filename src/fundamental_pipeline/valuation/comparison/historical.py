"""Historical self comparison engine (T74-B;
docs/valuation-t74-04-pairwise-historical-peer-engine-specification.md
Sections 8-12, 20, 22; docs/valuation-t68-07-comparison-strategy-applicability-matrix.md
Sections 6-7, 10; VAL-COMP-003/004/006/007/012).

Builds one company's position within its own governed monthly history for
one method: canonical monthly sample construction, span/anchor counters,
eligibility gating, and (only when the gate allows) exact percentile/
median/range statistics. The engine never interpolates a missing month,
never copies today's scalar backward into the comparator distribution,
and never mixes incompatible formula/policy regimes into one silently
blended series (T74.4 Section 10).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence

from ..methods.numeric import to_exact_rational
from .eligibility import classify_observation_status, one_observation_per_calendar_month, select_gate_outcome
from .observations import ComparisonObservation
from .policies import RankingPolicy
from .statistics import attractiveness_percentile, median, raw_percentile, to_canonical_decimal


@dataclass(frozen=True)
class HistoricalEngineResult:
    statistics_or_matrix: dict[str, Any]
    eligibility_state: str
    kept_observation_ids: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]  # (observation_id, reason_code)
    candidate_count: int


def _calendar_span_months(months: Sequence[str]) -> int:
    """Inclusive calendar-month distance from the earliest to the latest
    ``YYYY-MM`` string -- distinct from ``len(months)``: a sample with
    gaps spans more months than it has observations (T68-07 Section 6's
    N/span being independently gated, not derived from one another)."""
    if not months:
        return 0
    years_months = [(int(m[:4]), int(m[5:7])) for m in months]
    start = min(years_months)
    end = max(years_months)
    return (end[0] * 12 + end[1]) - (start[0] * 12 + start[1]) + 1


def _methodology_regimes(kept: Sequence[ComparisonObservation]) -> list[dict[str, Any]]:
    """One regime segment per distinct ``(formula_ref, policy_version)``
    pair actually present in the kept sample -- old and new formula/policy
    generations are never silently concatenated into one series (T74.4
    Section 10)."""
    by_regime: dict[tuple[str, str], list[str]] = {}
    for obs in kept:
        key = (obs.formula_ref, obs.policy_version)
        by_regime.setdefault(key, []).append(obs.observation_id)
    return [
        {"regime_id": f"regime:{formula_ref}:{policy_version}", "formula_or_policy_version": policy_version, "observation_ids": sorted(obs_ids)}
        for (formula_ref, policy_version), obs_ids in sorted(by_regime.items())
    ]


def evaluate_historical(
    *,
    current_observation_ref: str, current_value: str, comparator_observations: Sequence[ComparisonObservation],
    ranking_policy: RankingPolicy, as_of_date: str,
) -> HistoricalEngineResult:
    """Pure: build the full ``historicalStatistics`` variant shape from an
    already-loaded, already-schema-verified set of candidate monthly
    observations. ``current_value``/``current_observation_ref`` describe
    the subject's own *current* observation, which is never itself a
    member of the comparator sample (T68-07 Section 6; VAL-COMP-004)."""
    excluded: list[tuple[str, str]] = []
    status_ok: list[ComparisonObservation] = []
    for obs in comparator_observations:
        if obs.observation_id == current_observation_ref:
            excluded.append((obs.observation_id, "comparison.current_observation_self_reference"))
            continue
        if obs.as_of_date >= as_of_date:
            excluded.append((obs.observation_id, "comparison.not_point_in_time"))
            continue
        can_enter, reason = classify_observation_status(obs.status)
        if not can_enter:
            excluded.append((obs.observation_id, reason or "comparison.rank_ineligible_value"))
            continue
        status_ok.append(obs)

    by_id = {obs.observation_id: obs for obs in status_ok}
    month_candidates = [
        {"observation_id": obs.observation_id, "calendar_month": obs.calendar_month, "cutoff_instant": obs.cutoff_instant}
        for obs in status_ok
    ]
    kept_candidates, month_excluded = one_observation_per_calendar_month(month_candidates)
    excluded.extend((c["observation_id"], reason) for c, reason in month_excluded)

    kept = [by_id[c["observation_id"]] for c in kept_candidates]
    kept.sort(key=lambda o: o.calendar_month)

    eligible_count = len(kept)
    span_months = _calendar_span_months([obs.calendar_month for obs in kept])
    distinct_anchors = len({obs.financial_anchor_ref for obs in kept if obs.financial_anchor_ref is not None})

    rule = select_gate_outcome(
        ranking_policy.gate_table,
        {"eligible_count": eligible_count, "calendar_span_months": span_months, "distinct_financial_anchor_count": distinct_anchors},
    )

    values = [obs.value["value"] for obs in kept if obs.value.get("status") == "available"]

    raw_pct: str | None = None
    attractiveness: str | None = None
    median_value: str | None = None
    range_low: str | None = None
    range_high: str | None = None

    if values:
        if "raw_percentile" in rule.statistics_allowed:
            raw_fraction = raw_percentile(current_value, values)
            raw_pct = to_canonical_decimal(raw_fraction)
            if "attractiveness_percentile" in rule.statistics_allowed:
                attractiveness_fraction = attractiveness_percentile(raw_fraction, direction=ranking_policy.direction)
                attractiveness = to_canonical_decimal(attractiveness_fraction) if attractiveness_fraction is not None else None
        if "median" in rule.statistics_allowed:
            sorted_values = sorted(values, key=lambda v: Decimal(v))
            median_value = to_canonical_decimal(median(sorted_values))
        if "range" in rule.statistics_allowed:
            range_low = to_canonical_decimal(to_exact_rational(min(values, key=lambda v: Decimal(v))))
            range_high = to_canonical_decimal(to_exact_rational(max(values, key=lambda v: Decimal(v))))

    window_start = kept[0].as_of_date if kept else as_of_date
    window_end = kept[-1].as_of_date if kept else as_of_date

    statistics_or_matrix = {
        "variant_kind": "historical_self", "sampling_cadence": "canonical_monthly",
        "window_start": window_start, "window_end": window_end,
        "eligible_count": eligible_count, "calendar_span_months": span_months, "distinct_financial_anchor_count": distinct_anchors,
        "methodology_regimes": _methodology_regimes(kept),
        "current_observation_ref": current_observation_ref, "current_value": {"status": "available", "value": current_value},
        "raw_percentile": raw_pct, "attractiveness_percentile": attractiveness,
        "median": median_value, "range_low": range_low, "range_high": range_high, "quartiles": None,
    }

    return HistoricalEngineResult(
        statistics_or_matrix=statistics_or_matrix, eligibility_state=rule.eligibility_state,
        kept_observation_ids=tuple(obs.observation_id for obs in kept), excluded=tuple(excluded),
        candidate_count=len(comparator_observations),
    )
