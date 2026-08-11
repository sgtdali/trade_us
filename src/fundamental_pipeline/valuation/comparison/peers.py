"""Sector peer comparison engine (T74-B;
docs/valuation-t74-04-pairwise-historical-peer-engine-specification.md
Sections 13-17, 20, 22; docs/valuation-t68-07-comparison-strategy-applicability-matrix.md
Sections 8-9, 11-12, 20-21; VAL-COMP-008/009/010/011/012).

Resolves one company's position within an *authored, approved* peer
universe for one method: approval/effective-date verification, exact
member/observation join, subject exclusion (exactly once, defensively
even if a data-entry error leaves the subject un-flagged), approved-
primary-cohort coverage, count/coverage gating, and (only when the gate
allows) exact percentile/midrank/median/range/quartile statistics.
Nothing here can search a provider, infer a peer from a ticker name, add
a member to reach a threshold, or approve a universe (T74.4 Section 15).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Any, Sequence

from ..methods.numeric import to_exact_rational
from .eligibility import classify_observation_status, select_gate_outcome
from .observations import ComparisonObservation
from .policies import RankingPolicy
from .statistics import attractiveness_percentile, median, ordinal_midrank, raw_percentile, to_canonical_decimal, type7_quantile
from .universe import PeerUniverse, PeerUniverseMember


@dataclass(frozen=True)
class PeerEngineResult:
    statistics_or_matrix: dict[str, Any]
    eligibility_state: str
    eligible_member_ids: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]  # (member_id, reason_code)
    approved_primary_cohort_count: int


def evaluate_peer(
    *,
    subject_ticker: str, subject_value: str, universe: PeerUniverse, method_family_id: str,
    member_observations: Sequence[ComparisonObservation], ranking_policy: RankingPolicy, as_of_date: str,
) -> PeerEngineResult:
    """Pure: build the full ``peerStatistics`` variant shape from an
    already-approval-verified :class:`~.universe.PeerUniverse` (caller
    must have already called
    :func:`~.universe.verify_universe_canonical_eligible`) and its exact
    joined member observations. ``member_observations`` is the full
    candidate set for this method/as-of; observations for members outside
    the approved primary cohort are ignored (they never inflate N)."""
    candidates: tuple[PeerUniverseMember, ...] = universe.primary_members_at(as_of_date, method_family_id=method_family_id, exclude_subject=True)
    approved_primary_cohort_count = len(candidates)
    candidate_ids = {m.member_id for m in candidates}

    excluded: list[tuple[str, str]] = []
    by_member_id: dict[str, ComparisonObservation] = {}
    for obs in member_observations:
        if obs.company_or_member_id not in candidate_ids:
            continue  # not primary/not applicable/subject/out-of-window -- never a sample member at all
        if obs.ticker == subject_ticker:
            excluded.append((obs.company_or_member_id, "comparison.subject_in_peer_sample"))
            continue
        if obs.company_or_member_id in by_member_id:
            excluded.append((obs.company_or_member_id, "comparison.tier_mixing"))
            continue
        by_member_id[obs.company_or_member_id] = obs

    members_output: list[dict[str, Any]] = []
    eligible_values: list[str] = []
    eligible_ids: list[str] = []
    for member in candidates:
        obs = by_member_id.get(member.member_id)
        if obs is None:
            excluded.append((member.member_id, "comparison.rank_ineligible_value"))
            members_output.append({"member_ref": member.member_id, "eligibility_state": "excluded_insufficient_data", "value": None, "reason_codes": [{"code": "comparison.rank_ineligible_value", "severity": "info"}]})
            continue
        can_enter, reason = classify_observation_status(obs.status)
        if not can_enter:
            excluded.append((member.member_id, reason or "comparison.rank_ineligible_value"))
            members_output.append({"member_ref": member.member_id, "eligibility_state": "excluded_insufficient_data", "value": None, "reason_codes": [{"code": reason or "comparison.rank_ineligible_value", "severity": "info"}]})
            continue
        value = obs.value["value"]
        eligible_values.append(value)
        eligible_ids.append(member.member_id)
        members_output.append({"member_ref": member.member_id, "eligibility_state": "eligible", "value": value, "reason_codes": []})

    eligible_peer_count = len(eligible_values)
    # Exact rational coverage -- 5/7 has no exact terminating decimal, so
    # this must never be computed via Decimal division (which would
    # silently round) before comparing it against a 0.70 gate threshold.
    coverage_ratio = (
        Fraction(eligible_peer_count, approved_primary_cohort_count) if approved_primary_cohort_count > 0 else Fraction(0)
    )

    rule = select_gate_outcome(
        ranking_policy.gate_table,
        {"eligible_peer_count": eligible_peer_count, "coverage_ratio": coverage_ratio},
    )

    raw_pct: str | None = None
    attractiveness: str | None = None
    midrank: str | None = None
    median_value: str | None = None
    range_low: str | None = None
    range_high: str | None = None
    quartiles: dict[str, Any] | None = None

    if eligible_values:
        if "raw_percentile" in rule.statistics_allowed:
            raw_fraction = raw_percentile(subject_value, eligible_values)
            raw_pct = to_canonical_decimal(raw_fraction)
            if "attractiveness_percentile" in rule.statistics_allowed:
                attractiveness_fraction = attractiveness_percentile(raw_fraction, direction=ranking_policy.direction)
                attractiveness = to_canonical_decimal(attractiveness_fraction) if attractiveness_fraction is not None else None
        if "midrank" in rule.statistics_allowed and ranking_policy.direction in ("higher_is_more_attractive", "lower_is_more_attractive"):
            midrank_fraction = ordinal_midrank(subject_value, eligible_values, direction=ranking_policy.direction)
            midrank = to_canonical_decimal(midrank_fraction)
        if "median" in rule.statistics_allowed:
            sorted_values = sorted(eligible_values, key=lambda v: Decimal(v))
            median_value = to_canonical_decimal(median(sorted_values))
        if "range" in rule.statistics_allowed:
            range_low = to_canonical_decimal(to_exact_rational(min(eligible_values, key=lambda v: Decimal(v))))
            range_high = to_canonical_decimal(to_exact_rational(max(eligible_values, key=lambda v: Decimal(v))))
        if "quartiles" in rule.statistics_allowed:
            sorted_values = sorted(eligible_values, key=lambda v: Decimal(v))
            q1 = to_canonical_decimal(type7_quantile(sorted_values, "0.25"))
            q3 = to_canonical_decimal(type7_quantile(sorted_values, "0.75"))
            quartiles = {"q1": q1, "q3": q3, "method": "type_7"}

    statistics_or_matrix = {
        "variant_kind": "sector_peer", "approved_primary_cohort_count": approved_primary_cohort_count,
        "eligible_peer_count": eligible_peer_count, "members": members_output,
        "coverage_ratio": to_canonical_decimal(coverage_ratio), "subject_value": {"status": "available", "value": subject_value},
        "raw_percentile": raw_pct, "attractiveness_percentile": attractiveness, "midrank": midrank,
        "median": median_value, "range_low": range_low, "range_high": range_high, "quartiles": quartiles,
    }

    return PeerEngineResult(
        statistics_or_matrix=statistics_or_matrix, eligibility_state=rule.eligibility_state,
        eligible_member_ids=tuple(eligible_ids), excluded=tuple(excluded),
        approved_primary_cohort_count=approved_primary_cohort_count,
    )
