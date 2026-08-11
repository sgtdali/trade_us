"""Declarative summary-section policies: which signals feed each section,
and whether one signal dominates the section's overall status regardless
of what else is present.

Sections list their full aviation-scope membership; at generation time each
section is filtered down to whichever of its listed signals actually exist
in the generated signal set, so the same policy table naturally produces a
smaller, generic-only summary for a non-aviation sector module without any
ticker- or sector-specific branching in code.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SectionPolicy:
    section_id: str
    signal_ids: tuple[str, ...]
    applicable_sector_modules: tuple[str, ...] = ("generic", "aviation")
    dominant_signal_id: str | None = None
    uses_all_signals: bool = False
    uses_risks: bool = False
    #: A section becomes ``insufficient_data`` when fewer than this many of
    #: its configured signals actually resolved to usable (non-unavailable,
    #: present) data. Default of 1 means: at least one usable signal is
    #: required to classify the section at all -- a section whose only
    #: signal, or *all* of whose signals, are unavailable/missing can never
    #: be positive/negative/neutral/mixed.
    min_available_signals: int = 1
    #: An additional, independent completeness floor. 0.0 means "not used"
    #: (only ``min_available_signals`` gates insufficient_data).
    min_completeness_pct: float = 0.0


SECTION_POLICIES: tuple[SectionPolicy, ...] = (
    SectionPolicy(
        "aviation_operational_summary",
        ("rask_trend", "passenger_rask_trend", "passenger_yield_trend", "fuel_unit_cost_trend", "ex_fuel_unit_cost_trend"),
        applicable_sector_modules=("aviation",),
    ),
    SectionPolicy(
        "unit_revenue_summary",
        ("rask_trend", "passenger_rask_trend", "passenger_yield_trend"),
        applicable_sector_modules=("aviation",),
    ),
    SectionPolicy(
        "unit_cost_summary",
        ("fuel_unit_cost_trend", "ex_fuel_unit_cost_trend"),
        applicable_sector_modules=("aviation",),
    ),
    SectionPolicy(
        "profitability_summary",
        (
            "revenue_growth_trend", "passenger_revenue_growth_trend", "cargo_revenue_growth_trend",
            "operating_profit_before_investment_trend", "operating_profit_including_investments_trend",
            "net_profit_trend", "gross_margin_trend", "operating_margin_trend", "net_margin_trend",
            "ebitdar_margin_trend",
        ),
    ),
    SectionPolicy(
        "cash_flow_summary",
        ("operating_cash_flow_trend", "free_cash_flow_trend", "cash_conversion_trend", "deferred_revenue_trend"),
        dominant_signal_id="free_cash_flow_trend",
    ),
    SectionPolicy(
        "balance_sheet_summary",
        ("deferred_revenue_trend", "lease_burden_trend", "leverage_trend"),
    ),
    SectionPolicy("liquidity_summary", ("liquidity_trend",)),
    SectionPolicy("leverage_summary", ("leverage_trend", "lease_burden_trend")),
    SectionPolicy("risk_summary", (), uses_risks=True),
    SectionPolicy("company_fundamentals_summary", (), uses_all_signals=True),
)


def bucket_status(positive_ids: list[str], negative_ids: list[str], neutral_ids: list[str], dominant_value: str | None = None) -> str:
    """The generic section-status policy: a configured dominant signal's own
    bucket wins outright; otherwise a single nonempty bucket determines the
    status, and two or more nonempty buckets together are 'mixed'."""
    if dominant_value in ("positive", "negative"):
        return dominant_value
    nonempty = [bool(positive_ids), bool(negative_ids), bool(neutral_ids)]
    if sum(nonempty) == 0:
        return "mixed"
    if sum(nonempty) == 1:
        return "positive" if positive_ids else ("negative" if negative_ids else "neutral")
    return "mixed"
