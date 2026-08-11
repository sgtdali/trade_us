"""Builds the structured context a report template renders from. No prose
is authored here — only structured lookups and pre-formatted display
strings; all narrative sentences live in the Jinja templates or are the
signals' own machine-rendered ``reason`` text.
"""

from __future__ import annotations

from ..context import AnalysisContext
from .formatting import fmt_change, fmt_metric, fmt_metric_comparison


def _index(data: dict | None, sections: tuple[str, ...] = ()) -> dict:
    by_id: dict[str, dict] = {}
    if not data:
        return by_id
    for section in sections:
        for m in data.get(section, []):
            by_id[m["metric_id"]] = m
    if "metrics" in data:
        for m in data["metrics"]:
            by_id[m["metric_id"]] = m
    return by_id


def _index_derived(derived_data: dict) -> dict:
    by_id: dict[str, dict] = {}
    for category in ("growth", "margins", "liquidity", "leverage", "returns", "cash_generation"):
        for m in derived_data.get(category, []):
            by_id[m["metric_id"]] = m
    return by_id


class MetricLookup:
    """Template-friendly accessor: ``lookup.value('revenue_total')``,
    ``lookup.fmt('revenue_total')``, ``lookup.change('gross_margin')``."""

    def __init__(self, *pools: dict):
        self.merged: dict[str, dict] = {}
        for pool in pools:
            self.merged.update(pool)

    def get(self, metric_id: str) -> dict | None:
        return self.merged.get(metric_id)

    def value(self, metric_id: str):
        m = self.merged.get(metric_id)
        return m.get("value") if m else None

    def fmt(self, metric_id: str, decimals: int | None = None) -> str:
        return fmt_metric(self.merged.get(metric_id), decimals)

    def fmt_comparison(self, metric_id: str, decimals: int | None = None) -> str:
        return fmt_metric_comparison(self.merged.get(metric_id), decimals)

    def change(self, metric_id: str) -> str:
        return fmt_change(self.merged.get(metric_id))

    def is_available(self, metric_id: str) -> bool:
        m = self.merged.get(metric_id)
        return bool(m) and m.get("value") is not None


def build_report_context(
    context: AnalysisContext,
    derived_data: dict,
    signals_data: dict,
    summaries_data: dict,
) -> dict:
    direct = _index(context.direct_financials, ("income_statement", "balance_sheet", "cash_flow_statement", "commitments"))
    finops = _index(context.financial_operational_data)
    derived = _index_derived(derived_data)
    lookup = MetricLookup(direct, finops, derived)

    signals_by_id = {s["signal_id"]: s for s in signals_data.get("signals", [])}
    risks = (context.authored_risks or {}).get("risks", [])
    sources = (context.source_manifest or {}).get("sources", [])

    def presentation_status(signal: dict) -> str:
        return signal.get("context", {}).get("presentation_status", signal["value"])

    positive_signals = sorted(
        (s for s in signals_by_id.values() if presentation_status(s) == "positive"),
        key=lambda s: -(s["score"] or 0),
    )
    negative_signals = sorted(
        (s for s in signals_by_id.values() if presentation_status(s) == "negative"),
        key=lambda s: (s["score"] or 0),
    )
    contextual_signals = [
        s for s in signals_by_id.values()
        if presentation_status(s) != s["value"] and s["value"] != "unavailable"
    ]
    unavailable_signals = [s for s in signals_by_id.values() if s["value"] == "unavailable"]
    unavailable_derived = [m for m in derived.values() if m.get("status") and m["status"] != "available"]

    return {
        "ticker": context.ticker,
        "period": context.period_id,
        "company_name": context.company_config.get("company_name"),
        "classification": context.company_config.get("classification", {}),
        "reporting_locale": context.company_config.get("reporting_locale", "tr-TR"),
        "company_type": context.company_type,
        "sector_module": context.sector_module_id,
        "is_aviation": context.sector_module_id == "aviation",
        "sources": sources,
        "lookup": lookup,
        "signals": signals_by_id,
        "summaries": summaries_data.get("summaries", {}),
        "risks": risks,
        "high_severity_risks": [r for r in risks if r.get("severity") == "high"],
        "positive_signals": positive_signals,
        "negative_signals": negative_signals,
        "contextual_signals": contextual_signals,
        "unavailable_signals": unavailable_signals,
        "unavailable_derived": unavailable_derived,
    }
