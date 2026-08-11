"""Builds the template rendering context from loaded valuation report dependencies.

Display units and metric labels exposed here come from
:mod:`fundamental_pipeline.valuation.reporting.semantic_catalog`, which reads
``config/valuation/reporting/*.json``. See AGENTS.md's "Değerleme Raporu
Sunum Semantiği" section before hardcoding a label or unit inline here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .formatting import fmt_decimal_tr, fmt_valuation_amount, fmt_valuation_metric, to_decimal
from .models import ReportDependencies
from .semantic_catalog import (
    debt_profile_reason_label,
    debt_profile_status_label,
    display_unit_for_method,
    label_for_metric,
    lease_standard_label,
    status_label_for_method,
    status_label_for_reason_codes,
    market_freshness_caveat,
    label_for_method,
    caveat_for_method,
    caveat_for_reconciliation,
    operand_label,
    risk_analysis_status_label,
)

_DEBT_SCALE_TO_MILLION = {
    "unit": Decimal("0.000001"),
    "thousand": Decimal("0.001"),
    "million": Decimal("1"),
    "billion": Decimal("1000"),
}


def fmt_debt_amount(observation: dict[str, Any] | None) -> str:
    """Format a debt-profile source amount in millions without losing scale."""
    if not observation or observation.get("status") != "reported" or observation.get("value") is None:
        return "veri açıklanmadı"
    value = to_decimal(observation.get("value"))
    multiplier = _DEBT_SCALE_TO_MILLION.get(observation.get("scale"))
    if value is None or multiplier is None:
        return "veri açıklanmadı"
    currency = observation.get("currency") or ""
    return f"{fmt_decimal_tr(value * multiplier, 1)} milyon {currency}".strip()


def _with_display_unit(method: dict[str, Any]) -> dict[str, Any]:
    """Return a method result whose canonical_value carries a display unit.

    Method results carry a bare numeric ratio with no unit, so the report
    previously rendered a 19.5% FCF yield as a truncated "0,2". This looks up
    the display unit from the reporting semantic catalog so fmt_metric
    renders it as a percentage or multiple instead. A method_id missing from
    the catalog is left untouched here (falls back to fmt_metric's default
    plain-ratio rendering) -- report validation is responsible for turning
    that gap into a loud, fail-closed error rather than a silent guess.
    """
    canonical = method.get("canonical_value")
    if not canonical or canonical.get("unit") or canonical.get("status") != "available":
        return method
    unit = display_unit_for_method(method.get("method_id", ""))
    if unit is None:
        return method
    patched = dict(method)
    patched["canonical_value"] = {**canonical, "unit": unit}
    return patched


class ValuationMetricLookup:
    """Template-friendly lookup for fundamental metrics using Decimal-based formatting."""

    def __init__(self, pool: dict[str, dict[str, Any]]):
        self.pool = pool

    def get(self, metric_id: str) -> dict[str, Any] | None:
        return self.pool.get(metric_id)

    def value(self, metric_id: str) -> Any:
        m = self.pool.get(metric_id)
        return m.get("value") if m else None

    def fmt(self, metric_id: str, decimals: int | None = None) -> str:
        return fmt_valuation_metric(self.pool.get(metric_id), decimals, pre_scaled_percent=True)

    def is_available(self, metric_id: str) -> bool:
        m = self.pool.get(metric_id)
        return bool(m) and m.get("value") is not None


def _index_fundamental(financials: dict[str, Any], derived: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for section in ("income_statement", "balance_sheet", "cash_flow_statement", "commitments"):
        for m in financials.get(section, []):
            by_id[m["metric_id"]] = m
    for category in ("growth", "margins", "liquidity", "leverage", "returns", "cash_generation"):
        for m in derived.get(category, []):
            by_id[m["metric_id"]] = m
    return by_id
_TR_MONTHS = {
    "01": "Ocak",
    "02": "Şubat",
    "03": "Mart",
    "04": "Nisan",
    "05": "Mayıs",
    "06": "Haziran",
    "07": "Temmuz",
    "08": "Ağustos",
    "09": "Eylül",
    "10": "Ekim",
    "11": "Kasım",
    "12": "Aralık"
}


def format_tr_date(date_str: str) -> str:
    if not date_str:
        return ""
    parts = date_str.split("T")[0].split("-")
    if len(parts) != 3:
        return date_str
    year, month, day = parts[0], parts[1], parts[2]
    day_str = str(int(day))
    month_name = _TR_MONTHS.get(month, month)
    return f"{day_str} {month_name} {year}"


def fmt_operand_period(basis_ref: str, valuation_inputs: dict[str, Any], as_of_date: str, market_snapshot: dict[str, Any] | None = None) -> str:
    if not basis_ref:
        return ""

    # 1. Spot/instant market data. The report's as_of_date is when the
    # pipeline RAN, not necessarily when the underlying price was actually
    # observed (found 2026-07-26, ARCLK: as_of_date was a Sunday, the
    # market snapshot's own price_observation.session_date was the prior
    # Friday's close) -- the real session date + a staleness caveat (when
    # not fresh) come from the market snapshot itself, never the run date.
    if basis_ref in ("comp-market-cap", "price-basis", "ev-ex-lease", "ev-incl-lease"):
        price_obs = (market_snapshot or {}).get("price_observation") or {}
        session_date = price_obs.get("session_date")
        if session_date:
            return f"{format_tr_date(session_date)}{market_freshness_caveat(price_obs.get('freshness', ''))}"
        return format_tr_date(as_of_date)

    # 2. Book equity basis
    if basis_ref == "book-equity-parent":
        beb = valuation_inputs.get("book_equity_basis") or {}
        anchor = beb.get("period_anchor_ref", "")
        date_str = ""
        for ref in valuation_inputs.get("financial_basis_refs", []):
            if ref.get("source_id") == anchor:
                date_str = ref.get("period_end", "")
                break
        if date_str:
            return f"{format_tr_date(date_str)} / {anchor}"
        return anchor

    # 3. Cash flow bases
    if basis_ref.startswith("cf-"):
        cf_bases = valuation_inputs.get("cash_flow_bases", [])
        for cf in cf_bases:
            if cf.get("cash_flow_basis_id") == basis_ref:
                anchor = cf.get("period_anchor_ref", "")
                variant = cf.get("period_variant", "")
                # A true_ttm-tagged entry must never be mislabeled with the
                # FY source_id just because an FY period also happens to be
                # among financial_basis_refs (it is, by construction, for
                # every TTM assembly -- FY(Y-1) is one of the three legs).
                if variant == "true_ttm":
                    # `anchor` (financial_period_refs[0].source_id) is
                    # whatever period happened to be listed first among the
                    # TTM triple's three legs (usually the FY leg) -- not
                    # reliably the TTM window's own end date. Look up the
                    # most recent quarterly ref instead, same defensive
                    # pattern the "fy" branch below uses for its own anchor.
                    ttm_end_ref = None
                    for ref in valuation_inputs.get("financial_basis_refs", []):
                        if ref.get("period_type") == "quarterly" and (
                            ttm_end_ref is None or ref.get("period_end", "") > ttm_end_ref.get("period_end", "")
                        ):
                            ttm_end_ref = ref
                    ttm_end_label = ttm_end_ref.get("source_id") if ttm_end_ref else anchor
                    return f"Son 12 Ay (TTM, {ttm_end_label} itibarıyla, yaklaşık — enflasyon düzeltmesi yapılmamıştır)"
                if variant == "fy":
                    fy_ref = None
                    for ref in valuation_inputs.get("financial_basis_refs", []):
                        if ref.get("period_type") == "annual":
                            fy_ref = ref
                            break
                    if fy_ref:
                        return f"{fy_ref.get('source_id')}"
                return f"{anchor}-{variant}" if variant else anchor
                
    # 4. Earnings bases
    if basis_ref.startswith("earn-"):
        eb_bases = valuation_inputs.get("earnings_bases", [])
        for eb in eb_bases:
            if eb.get("earnings_basis_id") == basis_ref:
                anchor = eb.get("period_anchor_ref", "")
                variant = eb.get("period_variant", "")
                if variant == "true_ttm":
                    # `anchor` (financial_period_refs[0].source_id) is
                    # whatever period happened to be listed first among the
                    # TTM triple's three legs (usually the FY leg) -- not
                    # reliably the TTM window's own end date. Look up the
                    # most recent quarterly ref instead, same defensive
                    # pattern the "fy" branch below uses for its own anchor.
                    ttm_end_ref = None
                    for ref in valuation_inputs.get("financial_basis_refs", []):
                        if ref.get("period_type") == "quarterly" and (
                            ttm_end_ref is None or ref.get("period_end", "") > ttm_end_ref.get("period_end", "")
                        ):
                            ttm_end_ref = ref
                    ttm_end_label = ttm_end_ref.get("source_id") if ttm_end_ref else anchor
                    return f"Son 12 Ay (TTM, {ttm_end_label} itibarıyla, yaklaşık — enflasyon düzeltmesi yapılmamıştır)"
                if variant == "fy":
                    fy_ref = None
                    for ref in valuation_inputs.get("financial_basis_refs", []):
                        if ref.get("period_type") == "annual":
                            fy_ref = ref
                            break
                    if fy_ref:
                        return f"{fy_ref.get('source_id')}"
                return f"{anchor}-{variant}" if variant else anchor

    # 5. Distribution basis. event_type tells us whether this is a rolling
    # trailing-12-month window or a fixed fiscal-year figure -- these are not
    # interchangeable, so the label must not say "Son 12 Ay" and cite a fixed
    # FY source_id in the same breath unless the basis actually is that FY.
    if basis_ref == "distribution-basis":
        distribution_basis = valuation_inputs.get("distribution_basis") or {}
        event_type = distribution_basis.get("event_type", "")
        if event_type == "trailing_paid_12m":
            return f"Son 12 Ay ({format_tr_date(as_of_date)} itibarıyla)"
        fy_ref = None
        for ref in valuation_inputs.get("financial_basis_refs", []):
            if ref.get("period_type") == "annual":
                fy_ref = ref
                break
        if fy_ref:
            return fy_ref.get("source_id")
        return event_type or "dönem bilgisi mevcut değil"

    return basis_ref


def build_net_debt_reconciliation(
    valuation_inputs: dict[str, Any],
    latest_lookup: ValuationMetricLookup,
    reporting_currency: str
) -> dict[str, Any] | None:
    ledger = {c["component_id"]: c for c in valuation_inputs.get("capital_structure_ledger", [])}
    
    debt_current = to_decimal(ledger.get("comp-debt-current", {}).get("amount", {}).get("value"))
    debt_portion = to_decimal(ledger.get("comp-debt-current-portion", {}).get("amount", {}).get("value"))
    debt_noncurrent = to_decimal(ledger.get("comp-debt-noncurrent", {}).get("amount", {}).get("value"))
    cash = to_decimal(ledger.get("comp-cash-0", {}).get("amount", {}).get("value"))
    
    if None in (debt_current, debt_portion, debt_noncurrent, cash):
        return None
        
    bridge_net_debt = (debt_current + debt_portion + debt_noncurrent - cash) / Decimal("1000000")
    
    def metric_in_millions(metric_id: str) -> Decimal | None:
        metric = latest_lookup.get(metric_id)
        value = to_decimal(metric.get("value")) if metric else None
        if value is None:
            return None
        unit = (metric.get("unit") or "").lower()
        multiplier = {
            "unit_try": Decimal("0.000001"),
            "thousand_try": Decimal("0.001"),
            "million_try": Decimal("1"),
        }.get(unit)
        return value * multiplier if multiplier is not None else value

    apm_net_debt = metric_in_millions("net_financial_debt")
    if apm_net_debt is None:
        return None
        
    fin_inv_current = metric_in_millions("financial_investments_current") or Decimal("0")
    fin_inv_noncurrent = metric_in_millions("financial_investments_noncurrent") or Decimal("0")
    
    total_fin_investments = fin_inv_current + fin_inv_noncurrent
    other_adjustments = bridge_net_debt - total_fin_investments - apm_net_debt
    
    reconciled = abs(other_adjustments) <= Decimal("0.1")
        
    return {
        "bridge_net_debt": bridge_net_debt,
        "fin_inv_current": fin_inv_current,
        "fin_inv_noncurrent": fin_inv_noncurrent,
        "total_fin_investments": total_fin_investments,
        "other_adjustments": other_adjustments,
        "apm_net_debt": apm_net_debt,
        "reconciled": reconciled,
        "currency": reporting_currency
    }


def build_fcf_trend(all_period_cash_flows: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    """Multi-year CFO/Capex/FCF/FCF-margin trend (2026-07-22 report
    enhancement -- shows whether a strong single-period FCF is a trend or
    a one-off, per the same review that surfaced the NCI-attribution gap).
    Never fabricates a period that failed to load; a period missing CFO or
    capex simply shows 'veri yok' for FCF, its revenue/margin still shown
    if available."""
    rows: list[dict[str, Any]] = []
    for entry in all_period_cash_flows:
        cfo = entry.get("cfo")
        capex = entry.get("capex")
        cfo_val = to_decimal(cfo.get("value")) if cfo and cfo.get("value") is not None else None
        capex_val = to_decimal(capex.get("value")) if capex and capex.get("value") is not None else None
        fcf_amount = None
        if cfo_val is not None and capex_val is not None:
            fcf_amount = {"value": str(cfo_val + capex_val), "unit": cfo.get("unit")}
        revenue = entry.get("revenue")
        revenue_val = to_decimal(revenue.get("value")) if revenue and revenue.get("value") is not None else None
        fcf_margin = None
        if fcf_amount is not None and revenue_val:
            fcf_margin = {"value": str((cfo_val + capex_val) / revenue_val), "unit": "percent"}
        rows.append({
            "period": entry.get("period"),
            "cfo": cfo,
            "capex": capex,
            "fcf": fcf_amount,
            "fcf_margin": fcf_margin,
        })
    return rows


def build_report_context(deps: ReportDependencies, as_of_date: str) -> dict[str, Any]:
    """Index and assemble dependencies into a template-friendly rendering context."""
    latest_indexed = _index_fundamental(deps.latest_financials, deps.latest_derived)
    fy_indexed = _index_fundamental(deps.fy_financials, deps.fy_derived)

    latest_lookup = ValuationMetricLookup(latest_indexed)
    fy_lookup = ValuationMetricLookup(fy_indexed)
    contextual_signals = [
        signal
        for signal in deps.latest_signals.get("signals", [])
        if signal.get("context", {}).get("presentation_status", signal.get("value")) != signal.get("value")
        and signal.get("value") != "unavailable"
    ]

    # Index valuation components
    method_results = [_with_display_unit(m) for m in deps.current_results.get("method_results", [])]
    methods = {m["method_id"]: m for m in method_results}
    methods_by_family = {m["economic_family_id"]: m for m in method_results}

    ledger = {c["component_id"]: c for c in deps.valuation_inputs.get("capital_structure_ledger", [])}
    ev_bases = {e["ev_basis_id"]: e for e in deps.valuation_inputs.get("ev_basis_family", [])}

    # The report's as_of_date is when the pipeline ran, not necessarily
    # when the price itself was observed (found 2026-07-26, ARCLK: as_of
    # 2026-07-26 vs. the market snapshot's own session_date 2026-07-24) --
    # the opening summary sentence must cite the real session date.
    price_observation = (deps.market_snapshot or {}).get("price_observation") or {}
    price_session_date = price_observation.get("session_date") or as_of_date
    price_freshness_caveat = market_freshness_caveat(price_observation.get("freshness", ""))
    ebitda_basis = next(
        (
            entry
            for entry in deps.valuation_inputs.get("earnings_bases", ())
            if entry.get("earnings_basis_id") == "earn-ebitda"
        ),
        {},
    )
    latest_risk_items = deps.latest_risks.get("risks", [])
    latest_risk_analysis_status = deps.latest_risks.get("analysis_status")
    latest_risk_unavailable_reason = deps.latest_risks.get(
        "unavailable_reason_code"
    )
    if latest_risk_analysis_status is None:
        latest_risk_analysis_status = (
            "available" if latest_risk_items else "unavailable"
        )
        if not latest_risk_items:
            latest_risk_unavailable_reason = "risk_not_authored"
    latest_risk_status_label = risk_analysis_status_label(
        latest_risk_analysis_status,
        latest_risk_unavailable_reason,
        has_risks=bool(latest_risk_items),
    )

    def _method_caveat(method_id: str) -> str:
        parts = [caveat_for_method(method_id)]
        if method_id == "val.method.ev_to_ebitda.canonical":
            parts.append(caveat_for_reconciliation(ebitda_basis.get("reconciliation_status", "")))
        return " ".join(part for part in parts if part)

    return {
        "ticker": deps.company_config.get("ticker"),
        "company_name": deps.company_config.get("company_name"),
        "exchange": deps.company_config.get("exchange"),
        "as_of_date": as_of_date,
        "price_session_date": price_session_date,
        "price_freshness_caveat": price_freshness_caveat,
        "context_id": deps.valuation_inputs.get("input_identity", {}).get("context_id"),
        "reporting_currency": deps.valuation_inputs.get("reporting_currency_basis", {}).get("valuation_reporting_currency"),
        "accounting_basis": deps.latest_financials.get("accounting_basis", "undetermined"),
        "lease_standard": lease_standard_label(
            deps.latest_financials.get("accounting_basis", "undetermined")
        ),
        "share_count_basis": deps.valuation_inputs.get("share_basis", {}).get("basis_type"),
        "primary_price_mode": deps.valuation_inputs.get("price_basis", {}).get("mode"),
        "market_snapshot": deps.market_snapshot,
        "valuation_inputs": deps.valuation_inputs,
        "current_results": deps.current_results,
        "comparisons": deps.comparisons,
        "human_decision": deps.human_decision,
        "technical": deps.technical,
        "latest_lookup": latest_lookup,
        "fy_lookup": fy_lookup,
        "methods": methods,
        "methods_by_family": methods_by_family,
        "ledger": ledger,
        "ev_bases": ev_bases,
        "sources": deps.valuation_inputs.get("lineage", []),
        # Canonical dependencies
        "latest_signals": deps.latest_signals,
        "latest_risks": deps.latest_risks,
        "latest_risk_analysis_available": (
            latest_risk_analysis_status == "available"
        ),
        "latest_risk_analysis_status_label": latest_risk_status_label,
        "latest_summaries": deps.latest_summaries,
        "contextual_signals": contextual_signals,
        "fy_signals": deps.fy_signals,
        "fy_risks": deps.fy_risks,
        "fy_summaries": deps.fy_summaries,
        "latest_debt_profile": deps.latest_debt_profile,
        "fy_debt_profile": deps.fy_debt_profile,
        # Formatting helpers
        "fmt_tr": fmt_decimal_tr,
        "fmt_amount": fmt_valuation_amount,
        "fmt_metric": fmt_valuation_metric,
        "fmt_method_status": lambda method: status_label_for_method(
            (method.get("applicability") or {}).get("outcome", ""), method.get("reason_records", [])
        ),
        "fmt_reason_records": lambda reason_records: status_label_for_reason_codes(reason_records),
        "metric_label": label_for_metric,
        "net_debt_reconciliation": build_net_debt_reconciliation(
            deps.valuation_inputs,
            latest_lookup,
            deps.valuation_inputs.get("reporting_currency_basis", {}).get("valuation_reporting_currency", "USD")
        ),
        "fmt_operand_period": lambda basis_ref: fmt_operand_period(basis_ref, deps.valuation_inputs, as_of_date, deps.market_snapshot),
        "fcf_trend": build_fcf_trend(deps.all_period_cash_flows),
        "method_label": label_for_method,
        "method_caveat": _method_caveat,
        "operand_label": operand_label,
        "fmt_date": format_tr_date,
        "fmt_debt_amount": fmt_debt_amount,
        "debt_pressure_label": debt_profile_status_label,
        "debt_reason_label": debt_profile_reason_label,
    }
