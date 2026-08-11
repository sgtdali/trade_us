"""Magic Formula (Greenblatt-compatible) diagnostic engine (T74-B;
docs/valuation-t74-05-piotroski-magic-diagnostic-specification.md
Sections 9-14, 21; docs/valuation-t68-07-comparison-strategy-applicability-matrix.md
Sections 16-18; T67.7's exact formula IDs/denominator-floor formula).

Two independent axes -- earnings yield (``core_EBIT / compatible_EV``)
and return on tangible operating capital (``core_EBIT /
tangible_operating_capital``) -- each with its own eligibility, reasons,
and (only when eligible and a peer sample is supplied) percentile/rank.
One axis failing (negative/near-zero denominator, missing lease adapter)
never suppresses the other (T74.5 Sections 9-13). ``combined`` is a view
over both axes' ordinal mid-ranks, never a new scalar assessment, and is
only ``eligible`` under the same-universe/both-eligible/N/coverage gates
(T74.5 Section 14).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping, Sequence

from ..methods.numeric import add_exact, divide_exact, multiply_exact, to_exact_rational
from .policies import MagicFormulaDiagnosticPolicy
from .statistics import attractiveness_percentile, ordinal_midrank, raw_percentile, to_canonical_decimal

Envelope = Mapping[str, Any]


@dataclass(frozen=True)
class MagicFormulaFacts:
    """Already-exact facts for one company/period (this engine never
    computes EBIT/EV/working-capital/PPE/revenue/assets itself -- T71's
    method-family territory). ``lease_basis_compatible=False`` is the
    "no sector fleet/lease adapter available" gate (e.g. an aviation
    company's aircraft/fleet operating-capital adapter): ROC becomes
    unavailable while EY may remain independently eligible (T74.5
    Section 12)."""

    ebit: Envelope
    enterprise_value: Envelope
    net_working_capital: Envelope
    net_operating_fixed_assets: Envelope
    revenue: Envelope
    total_assets: Envelope
    lease_basis_compatible: bool = True


def _available(envelope: Envelope) -> bool:
    return envelope.get("status") == "available" and "value" in envelope


def _unavailable_axis(formula_ref: str, reason_code: str) -> dict[str, Any]:
    return {
        "formula_ref": formula_ref, "raw_value": {"status": "unavailable", "reason_codes": [{"code": reason_code, "severity": "info"}]},
        "eligibility": "excluded_insufficient_data", "percentile": None, "rank": None,
        "reason_codes": [{"code": reason_code, "severity": "info"}],
    }


def _rank_fields(raw_value: Fraction, *, peer_values: Sequence[str], direction: str) -> tuple[str | None, str | None]:
    """Percentile/rank against an optional peer sample -- absent
    (``None``, ``None``) whenever no peer sample was supplied, since a
    Magic axis is independently meaningful even with zero peers (T74.5
    Section 13: one axis failure/absence never blocks the other)."""
    if not peer_values:
        return None, None
    raw_str = to_canonical_decimal(raw_value)
    percentile_fraction = raw_percentile(raw_str, peer_values)
    percentile = to_canonical_decimal(attractiveness_percentile(percentile_fraction, direction=direction) or percentile_fraction)
    rank = to_canonical_decimal(ordinal_midrank(raw_str, peer_values, direction=direction))
    return percentile, rank


def evaluate_earnings_yield(facts: MagicFormulaFacts, *, policy: MagicFormulaDiagnosticPolicy, peer_values: Sequence[str] = ()) -> dict[str, Any]:
    """``EY = core_EBIT / compatible_EV`` -- the inverse family of EV/EBIT
    (never double-counted alongside it). Requires ``EBIT>0`` and ``EV>0``;
    negative/not-meaningful EV never yields an ordinary rank (T74.5
    Section 9)."""
    if not _available(facts.ebit) or not _available(facts.enterprise_value):
        return _unavailable_axis(policy.earnings_yield_formula_ref, "comparison.rank_ineligible_value")
    ebit = to_exact_rational(facts.ebit["value"])
    ev = to_exact_rational(facts.enterprise_value["value"])
    if ebit <= 0:
        return _unavailable_axis(policy.earnings_yield_formula_ref, "strategy.magic_ebit_nonpositive")
    if ev <= 0:
        return _unavailable_axis(policy.earnings_yield_formula_ref, "strategy.magic_enterprise_value_nonpositive")
    ey = divide_exact(ebit, ev)
    percentile, rank = _rank_fields(ey, peer_values=peer_values, direction="higher_is_more_attractive")
    return {
        "formula_ref": policy.earnings_yield_formula_ref, "raw_value": {"status": "available", "value": to_canonical_decimal(ey)},
        "eligibility": "eligible", "percentile": percentile, "rank": rank, "reason_codes": [],
    }


def evaluate_return_on_capital(facts: MagicFormulaFacts, *, policy: MagicFormulaDiagnosticPolicy, peer_values: Sequence[str] = ()) -> dict[str, Any]:
    """``ROC = core_EBIT / (net_working_capital + net_operating_fixed_assets)``,
    suppressed under the near-zero/negative capital floor ``0.01 x
    max(revenue, total_assets)`` (T74.5 Sections 10-11) -- a suppressed
    value can never surface as the best/infinite ROC."""
    if not facts.lease_basis_compatible:
        return _unavailable_axis(policy.return_on_capital_formula_ref, "strategy.magic_lease_basis_mismatch")
    if not all(_available(e) for e in (facts.ebit, facts.net_working_capital, facts.net_operating_fixed_assets, facts.revenue, facts.total_assets)):
        return _unavailable_axis(policy.return_on_capital_formula_ref, "comparison.rank_ineligible_value")
    ebit = to_exact_rational(facts.ebit["value"])
    capital = add_exact(to_exact_rational(facts.net_working_capital["value"]), to_exact_rational(facts.net_operating_fixed_assets["value"]))
    revenue = to_exact_rational(facts.revenue["value"])
    total_assets = to_exact_rational(facts.total_assets["value"])
    floor = multiply_exact(Fraction(policy.denominator_floor_ratio), max(abs(revenue), abs(total_assets)))
    if capital <= 0:
        return _unavailable_axis(policy.return_on_capital_formula_ref, "strategy.magic_operating_capital_nonpositive")
    if capital < floor:
        return _unavailable_axis(policy.return_on_capital_formula_ref, "strategy.magic_operating_capital_near_zero")
    roc = divide_exact(ebit, capital)
    percentile, rank = _rank_fields(roc, peer_values=peer_values, direction="higher_is_more_attractive")
    return {
        "formula_ref": policy.return_on_capital_formula_ref, "raw_value": {"status": "available", "value": to_canonical_decimal(roc)},
        "eligibility": "eligible", "percentile": percentile, "rank": rank, "reason_codes": [],
    }


def evaluate_combined(
    ey_result: Mapping[str, Any], roc_result: Mapping[str, Any], *, policy: MagicFormulaDiagnosticPolicy,
    same_universe_intersection_count: int, same_universe_intersection_coverage: Fraction | None,
    universe_ref: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Combined ordinal position only when both axes are ``eligible`` in
    the same approved universe/version AND the same-universe intersection
    sample clears the policy's own ``combined_min_intersection_n``/
    ``combined_min_intersection_coverage`` gates (T74.5 Section 14;
    T68-07 Section 18). Missing one axis excludes the company from
    ``combined`` entirely -- it never becomes a bottom rank."""
    if ey_result["eligibility"] != "eligible" or roc_result["eligibility"] != "eligible":
        return {
            "eligibility": "excluded_insufficient_data", "rank_sum": None, "universe_ref": None,
            "reason_codes": [{"code": "strategy.magic_combined_component_missing", "severity": "info"}],
        }
    gate_passes = (
        same_universe_intersection_count >= policy.combined_min_intersection_n
        and same_universe_intersection_coverage is not None
        and same_universe_intersection_coverage >= Fraction(policy.combined_min_intersection_coverage)
    )
    if not gate_passes:
        return {
            "eligibility": "provisional", "rank_sum": None, "universe_ref": None,
            "reason_codes": [{"code": "strategy.magic_universe_gate_failed", "severity": "info"}],
        }
    if ey_result["rank"] is None or roc_result["rank"] is None:
        return {
            "eligibility": "provisional", "rank_sum": None, "universe_ref": dict(universe_ref) if universe_ref else None,
            "reason_codes": [{"code": "strategy.magic_combined_component_missing", "severity": "info"}],
        }
    rank_sum = to_exact_rational(ey_result["rank"]) + to_exact_rational(roc_result["rank"])
    return {
        "eligibility": "eligible", "rank_sum": to_canonical_decimal(rank_sum),
        "universe_ref": dict(universe_ref) if universe_ref else None, "reason_codes": [],
    }


def evaluate_magic_formula(
    facts: MagicFormulaFacts, *, policy: MagicFormulaDiagnosticPolicy, ey_peer_values: Sequence[str] = (),
    roc_peer_values: Sequence[str] = (), same_universe_intersection_count: int = 0,
    same_universe_intersection_coverage: Fraction | None = None, universe_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure: assemble the full ``magicAxes`` variant shape from
    already-resolved exact facts and (optional) peer samples."""
    ey_result = evaluate_earnings_yield(facts, policy=policy, peer_values=ey_peer_values)
    roc_result = evaluate_return_on_capital(facts, policy=policy, peer_values=roc_peer_values)
    combined = evaluate_combined(
        ey_result, roc_result, policy=policy, same_universe_intersection_count=same_universe_intersection_count,
        same_universe_intersection_coverage=same_universe_intersection_coverage, universe_ref=universe_ref,
    )
    return {"variant_kind": "magic_formula_diagnostic", "earnings_yield": ey_result, "return_on_capital": roc_result, "combined": combined}
