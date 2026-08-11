"""Immutable report dependency models for the valuation reporting layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReportDependencies:
    """The complete set of validated canonical dependencies needed to render a report.
    Required dependencies are non-optional; optional ones default to None.
    """
    company_config: dict[str, Any]
    market_snapshot: dict[str, Any]
    valuation_inputs: dict[str, Any]
    current_results: dict[str, Any]
    latest_financials: dict[str, Any]
    latest_derived: dict[str, Any]
    latest_signals: dict[str, Any]
    latest_summaries: dict[str, Any]
    latest_risks: dict[str, Any]
    fy_financials: dict[str, Any]
    fy_derived: dict[str, Any]
    fy_signals: dict[str, Any]
    fy_summaries: dict[str, Any]
    fy_risks: dict[str, Any]

    # Optional downstream assets:
    comparisons: tuple[dict[str, Any], ...] = ()
    human_decision: dict[str, Any] | None = None
    all_period_cash_flows: tuple[dict[str, Any], ...] = ()
    technical: dict[str, Any] | None = None
    latest_debt_profile: dict[str, Any] | None = None
    fy_debt_profile: dict[str, Any] | None = None
