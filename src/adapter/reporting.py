from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from engine.paths import repo_path
from engine.io import read_json
from engine.valuation.paths import (
    resolve_governed_report_path,
    valuation_report_relative_path,
)
from engine.valuation.reporting.context import build_report_context
from engine.valuation.reporting.loader import load_report_dependencies
from engine.valuation.reporting.validator import validate_report_content


_METHOD_LABELS = {
    "val.method.price_to_book.parent_equity": "Price / Book Value",
    "val.method.pe.reported_parent": "Price / Earnings",
    "val.method.ev_to_ebit.core": "Lease-Exclusive Enterprise Value / Reported Operating Income",
    "val.method.ev_to_ebitda.canonical": "Enterprise Value / Issuer-Reported EBITDA",
    "val.method.fcf_yield.standard_equity": "Parent-Attributed Free Cash Flow Yield (Proxy)",
    "val.method.earnings_yield.reported_parent": "Earnings Yield",
    "val.method.ebit_yield.core": "EBIT Yield",
    "val.method.dividend_yield.cash_declared_paid": "Dividend Yield",
}

_METRIC_LABELS = {
    "revenue_total": "Revenue",
    "gross_profit": "Gross Profit",
    "operating_profit_before_investment_activities": "Reported Operating Income (EBIT)",
    "operating_profit": "Operating Profit",
    "net_profit_attributable_parent": "Net Income Attributable to Parent",
    "net_profit_for_period": "Consolidated Net Income",
    "net_financial_debt": "Net Financial Debt (Excluding Leases)",
    "cf_net_operating_activities": "Cash Flow from Operating Activities",
    "cf_capex_ppe_intangible": "Capital Expenditures",
    "cf_share_repurchases": "Cash Paid for Share Repurchases",
    "free_cash_flow": "Free Cash Flow",
    "gross_margin": "Gross Margin",
    "net_margin": "Consolidated Net Margin",
    "free_cash_flow_margin": "Free Cash Flow Margin",
    "current_ratio": "Current Ratio",
}

_SIGNAL_LABELS = {
    "operating_profit_before_investment_trend": "Reported Operating Income Trend",
    "operating_profit_including_investments_trend": "Reported Operating Income Trend",
    "net_profit_trend": "Consolidated Net Income Trend",
}

_TECHNICAL_LABELS = {
    "sma_50": "50-Day Simple Moving Average",
    "sma_200": "200-Day Simple Moving Average",
    "rsi_14": "14-Day Relative Strength Index",
    "avg_volume_20d": "20-Day Average Volume",
    "avg_volume_60d": "60-Day Average Volume",
    "support_63d": "63-Day Price Low",
    "resistance_63d": "63-Day Price High",
}

_COMPARISON_ORDER = {
    "gross_margin": 10,
    "net_margin": 20,
    "free_cash_flow_margin": 30,
    "current_ratio": 40,
    "val.method.earnings_yield.reported_parent": 50,
}

_RISK_TEXT = {
    "competition_and_demand": ("Competition and Consumer Demand Risk", "The filing discusses competition or changes in consumer demand and preferences."),
    "supply_chain_and_inputs": ("Supply Chain and Input Cost Risk", "The filing discusses supply-chain disruption, suppliers, transportation, commodities, or raw-material costs."),
    "cybersecurity_and_systems": ("Cybersecurity and Information Systems Risk", "The filing discusses cybersecurity, data, or information-system disruption risk."),
    "regulation_and_litigation": ("Regulatory and Legal Risk", "The filing discusses regulation, taxation, litigation, or other legal proceedings."),
    "foreign_currency_and_macro": ("Foreign Currency and Macroeconomic Risk", "The filing discusses foreign exchange, inflation, interest rates, or broader economic conditions."),
    "climate_and_environment": ("Climate and Environmental Regulation Risk", "The filing discusses climate, water, emissions, or environmental regulation."),
}

_PERCENT_POINT_PEER_METRICS = {
    "gross_margin",
    "net_margin",
    "free_cash_flow_margin",
}

_REASON_TEXT = {
    "method.canonical_ebitda_unavailable": (
        "Issuer-reported EBITDA was not available from an accession-specific filing "
        "or earnings exhibit, so this method was not calculated."
    ),
    "issuer_reported_ebitda_not_found": (
        "No accession-specific issuer-reported EBITDA fact was found."
    ),
    "issuer_reported_net_debt_apm_not_found": (
        "No accession-specific issuer-reported net-debt APM fact was found."
    ),
}


def generate_us_valuation_report(
    ticker: str,
    as_of_date: str,
    context_id: str,
    latest_period: str,
    fy_period: str,
    *,
    workspace: Path,
    config_root: Path | None = None,
) -> tuple[str, list[str]]:
    config_root = config_root if config_root is not None else workspace
    deps = load_report_dependencies(
        ticker=ticker,
        as_of_date=as_of_date,
        context_id=context_id,
        latest_period=latest_period,
        fy_period=fy_period,
        root=workspace,
    )
    context = build_report_context(deps, as_of_date)
    operational_path = workspace / "data" / "financial-operational" / ticker / f"{fy_period}.json"
    issuer_operational = read_json(operational_path) if operational_path.exists() else {"metrics": []}
    peer_universe = read_json(
        config_root / "config" / "valuation" / "comparison" / "peer-universes" /
        "consumer-staples.json"
    )
    signal_details = {
        signal["signal_id"]: {
            "label": _SIGNAL_LABELS.get(
                signal["signal_id"], _humanize_id(signal["signal_id"])
            ),
            "explanation": _signal_explanation(signal),
        }
        for signal in deps.latest_signals.get("signals", [])
    }
    signal_summary = (
        deps.latest_summaries.get("summaries", {}).get("company_fundamentals_summary", {})
    )
    peer_group = _peer_group(peer_universe, ticker)
    context["comparisons"] = _matched_peer_comparisons(
        _ordered_comparisons(_latest_comparisons(context["comparisons"])),
        peer_group,
        ticker,
    )
    review_signal_ids = _review_required_signal_ids(deps.latest_signals)
    positive_signal_ids = _deduplicate_signal_ids(
        signal_summary.get("positive_signals", []), signal_details
    )
    context.update({
        "latest_financials": deps.latest_financials,
        "fy_financials": deps.fy_financials,
        "issuer_operational": issuer_operational,
        "peer_universe": peer_universe,
        "peer_group_label": peer_group["label"],
        "peer_tickers": [member["ticker"] for member in peer_group["members"]],
        "signal_details": signal_details,
        "positive_signal_ids": [
            signal_id for signal_id in positive_signal_ids
            if signal_id not in review_signal_ids
        ],
        "review_signal_ids": review_signal_ids,
        "negative_signal_ids": _deduplicate_signal_ids(
            signal_summary.get("negative_signals", []), signal_details
        ),
        "has_financial_signals": bool(
            positive_signal_ids
            or review_signal_ids
            or signal_summary.get("negative_signals", [])
        ),
        "latest_source": _financial_source_summary(deps.latest_financials),
        "fy_source": _financial_source_summary(deps.fy_financials),
        "ev_bridge": _build_ev_bridge(context["ledger"], context["ev_bases"]),
        "ttm_fcf_bridge": _build_ttm_fcf_bridge(
            context["latest_lookup"], context["fy_lookup"], context["methods"]
        ),
        "ttm_earnings_bridges": _build_ttm_earnings_bridges(
            context["latest_lookup"], context["fy_lookup"], context["methods"]
        ),
        "latest_available_annual_leases": _latest_available_annual_leases(
            context["latest_lookup"], context["fy_lookup"], deps.fy_financials,
        ),
        "maturity_coverage_notes": _maturity_coverage_notes(deps.latest_debt_profile),
        "maturity_schedule_source": _maturity_schedule_source(deps.latest_debt_profile),
        "share_count_summary": _share_count_summary(deps.market_snapshot),
        "market_financial_gap_days": _date_gap_days(
            deps.latest_financials.get("period_end"), context["price_session_date"]
        ),
        "fiscal_year_naming_note": _fiscal_year_naming_note(
            deps.latest_financials, deps.fy_financials,
        ),
        "metric_lineage_rows": _metric_lineage_rows(
            context["latest_lookup"], context["fy_lookup"]
        ),
        "accounting_basis_en": _accounting_basis_label(context["accounting_basis"]),
        "share_count_basis_en": _share_basis_label(context["share_count_basis"]),
        "method_label_en": lambda method_id: _METHOD_LABELS.get(method_id, method_id),
        "metric_label_en": lambda metric_id: _METRIC_LABELS.get(metric_id, metric_id.replace("_", " ").title()),
        "peer_label_en": _peer_label,
        "risk_text_en": lambda risk_id: _RISK_TEXT.get(risk_id, (risk_id.replace("_", " ").title(), "Risk disclosed in the source filing.")),
        "risk_evidence_en": _risk_evidence,
        "reason_text_en": lambda code: _REASON_TEXT.get(code, _humanize_id(code)),
        "technical_label_en": lambda metric_id: _TECHNICAL_LABELS.get(metric_id, _humanize_id(metric_id)),
        "extraction_method_en": _extraction_method_label,
        "metric_provenance_en": _metric_provenance,
        "fmt_number_en": _fmt_number,
        "fmt_amount_en": _fmt_amount,
        "fmt_amount_millions_en": _fmt_amount_millions,
        "fmt_scaled_amount_en": _fmt_scaled_amount,
        "fmt_metric_en": _fmt_metric,
        "fmt_record_en": _fmt_record,
        "fmt_peer_value_en": _fmt_peer_value,
        "fmt_ratio_percent_en": _fmt_ratio_percent,
        "operand_basis_en": lambda operand: _operand_basis_label(
            operand, deps.latest_financials, deps.fy_financials, context["price_session_date"]
        ),
        "fmt_date_en": _fmt_date,
        "fiscal_period_label": _fiscal_period_label,
    })
    env = Environment(
        loader=FileSystemLoader(str(repo_path("templates", "valuation"))),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    rendered = env.get_template("valuation-analysis-v1.en.md.j2").render(**context)
    report_text = _collapse_blank_lines(rendered)
    errors = _validate_us_report_content(report_text, deps.current_results)
    if errors:
        return report_text, errors
    report_path = resolve_governed_report_path(
        workspace, valuation_report_relative_path(ticker, as_of_date)
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    return report_text, []


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)) if value is not None else None
    except (InvalidOperation, ValueError):
        return None


def _fmt_number(value: Any, decimals: int = 1) -> str:
    number = _decimal(value)
    if number is None:
        return "not available"
    return f"{number:,.{decimals}f}"


def _fmt_amount(amount: dict[str, Any] | None, decimals: int = 1) -> str:
    if not amount or amount.get("status", "available") != "available" or amount.get("value") is None:
        return "not available"
    return f"{_fmt_number(amount['value'], decimals)} {amount.get('currency', '')}".rstrip()


def _fmt_amount_millions(amount: dict[str, Any] | None, decimals: int = 1) -> str:
    if not amount or amount.get("status", "available") != "available" or amount.get("value") is None:
        return "not available"
    value = _decimal(amount["value"])
    if value is None:
        return "not available"
    return f"{_fmt_number(value / Decimal('1000000'), decimals)} million {amount.get('currency', '')}".rstrip()


def _fmt_scaled_amount(value: Any, currency: str | None, scale: str | None) -> str:
    if value is None:
        return "not available"
    scale_label = {"million": "million", "thousand": "thousand", "unit": ""}.get(
        scale or "", scale or ""
    )
    suffix = " ".join(part for part in (scale_label, currency or "") if part)
    return f"{_fmt_number(value, 1)} {suffix}".rstrip()


def _fmt_metric(metric: dict[str, Any] | None, decimals: int = 2) -> str:
    if not metric or metric.get("status", "available") != "available" or metric.get("value") is None:
        return "not available"
    value = _decimal(metric["value"])
    unit = metric.get("unit")
    if value is None:
        return "not available"
    if unit == "percent":
        return f"{_fmt_number(value * 100, decimals)}%"
    if unit == "multiple":
        return f"{_fmt_number(value, decimals)}x"
    return _fmt_number(value, decimals)


def _fmt_record(record: dict[str, Any] | None, decimals: int = 1) -> str:
    if not record or record.get("status", "available") != "available" or record.get("value") is None:
        return "not available"
    unit = record.get("unit", "")
    suffix = ""
    if unit == "million_usd":
        suffix = " million USD"
    elif unit == "usd_per_share":
        suffix = " USD per share"
    elif unit in ("percent", "ratio"):
        value = _decimal(record["value"])
        if value is None:
            return "not available"
        return f"{_fmt_number(value * (100 if unit == 'percent' else 1), decimals)}{'%' if unit == 'percent' else ''}"
    return f"{_fmt_number(record['value'], decimals)}{suffix}"


def _fmt_ratio_percent(value: Any, decimals: int = 2) -> str:
    number = _decimal(value)
    if number is None:
        return "not available"
    return f"{_fmt_number(number * 100, decimals)}%"


def _peer_label(scope_id: str) -> str:
    return _METHOD_LABELS.get(
        scope_id,
        _METRIC_LABELS.get(scope_id, scope_id.replace("_", " ").title()),
    )


def _comparison_scope(comparison: dict[str, Any]) -> str:
    return (comparison.get("method_or_dimension_scope") or {}).get("scope_id", "")


def _ordered_comparisons(comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            item for item in comparisons
            if _comparison_scope(item) not in {
                "gross_margin", "net_margin", "free_cash_flow_margin",
            }
        ],
        key=lambda item: (
            _COMPARISON_ORDER.get(
                _comparison_scope(item),
                90,
            ),
            _comparison_scope(item),
        ),
    )


def _latest_comparisons(comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the newest artifact for each comparison type and metric scope."""
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for comparison in comparisons:
        key = (comparison.get("comparison_type", ""), _comparison_scope(comparison))
        current = selected.get(key)
        rank = (
            comparison.get("temporal_context", {}).get("generated_at") or "",
            comparison.get("artifact_id") or "",
        )
        current_rank = (
            current.get("temporal_context", {}).get("generated_at") or "",
            current.get("artifact_id") or "",
        ) if current else ("", "")
        if current is None or rank > current_rank:
            selected[key] = comparison
    return list(selected.values())


def _peer_group(peer_universe: dict[str, Any], ticker: str) -> dict[str, Any]:
    members = peer_universe.get("members", [])
    subject = next((member for member in members if member.get("ticker") == ticker), None)
    subject_refs = tuple((subject or {}).get("classification_refs") or ())
    if not subject_refs:
        return {"label": "Broad authored cohort", "members": members}
    matched = [
        member for member in members
        if tuple(member.get("classification_refs") or ()) == subject_refs
    ]
    label = ", ".join(ref.split(":", 1)[-1] for ref in subject_refs)
    return {"label": f"Authored operating-model cohort: {label}", "members": matched}


def _matched_peer_comparisons(
    comparisons: list[dict[str, Any]], peer_group: dict[str, Any], ticker: str,
) -> list[dict[str, Any]]:
    member_ids = {member["member_id"] for member in peer_group["members"]}
    subject_ids = {
        member["member_id"] for member in peer_group["members"]
        if member.get("ticker") == ticker
    }
    matched = []
    for comparison in comparisons:
        if comparison.get("comparison_type") != "sector_peer":
            matched.append(comparison)
            continue
        peer_stats = dict(comparison.get("statistics_or_matrix") or {})
        members = [
            member for member in peer_stats.get("members", [])
            if member.get("member_ref") in member_ids
        ]
        values = sorted(
            value for member in members
            if member.get("member_ref") not in subject_ids
            and member.get("eligibility_state") == "eligible"
            and (value := _decimal(member.get("value"))) is not None
        )
        peer_stats.update({
            "members": members,
            "approved_primary_cohort_count": len(member_ids),
            "eligible_peer_count": len(values),
            "median": _median(values),
        })
        restricted = dict(comparison)
        restricted["statistics_or_matrix"] = peer_stats
        matched.append(restricted)
    return matched


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    midpoint = len(values) // 2
    if len(values) % 2:
        return values[midpoint]
    return (values[midpoint - 1] + values[midpoint]) / Decimal("2")


def _deduplicate_signal_ids(
    signal_ids: list[str], signal_details: dict[str, dict[str, str]],
) -> list[str]:
    seen_explanations: set[str] = set()
    result = []
    for signal_id in signal_ids:
        explanation = signal_details.get(signal_id, {}).get("explanation", signal_id)
        if explanation in seen_explanations:
            continue
        seen_explanations.add(explanation)
        result.append(signal_id)
    return result


def _review_required_signal_ids(signals: dict[str, Any]) -> list[str]:
    review_ids = []
    for signal in signals.get("signals", []):
        evidence = signal.get("evidence") or {}
        if (
            signal.get("signal_id") in {
                "free_cash_flow_trend",
                "operating_cash_flow_trend",
            }
            and signal.get("value") == "positive"
            and _decimal(evidence.get("current_comparison_value")) is not None
            and _decimal(evidence.get("current_comparison_value")) < 0
        ):
            review_ids.append(signal["signal_id"])
    return review_ids


def _validate_us_report_content(
    report_text: str, current_results: dict[str, Any],
) -> list[str]:
    """Run shared safety checks without exposing machine IDs in the LLM report."""
    method_results = current_results.get("method_results", [])
    audit_ids = "\n".join(
        f"{method.get('method_id', '')} {method.get('economic_family_id', '')}"
        for method in method_results
    )
    errors = validate_report_content(f"{report_text}\n{audit_ids}", current_results)
    for method in method_results:
        method_id = method.get("method_id", "")
        label = _METHOD_LABELS.get(method_id, method_id)
        if label not in report_text:
            errors.append(
                f"US valuation method was not presented by its report label: {label}"
            )
    return errors


def _fmt_peer_value(scope_id: str, value: Any) -> str:
    number = _decimal(value)
    if number is None:
        return "not available"
    if scope_id == "val.method.earnings_yield.reported_parent":
        return f"{_fmt_number(number * 100, 2)}%"
    if scope_id in _PERCENT_POINT_PEER_METRICS:
        return f"{_fmt_number(number, 2)}%"
    if scope_id == "current_ratio":
        return f"{_fmt_number(number, 2)}x"
    return _fmt_number(number, 2)


def _humanize_id(value: str) -> str:
    tail = value.split(".")[-1]
    return tail.replace("_", " ").strip().title()


def _accounting_basis_label(value: str) -> str:
    return {"US_GAAP": "US GAAP", "IFRS": "IFRS"}.get(value, _humanize_id(value))


def _share_basis_label(value: str) -> str:
    return {
        "spot_basic_shares_outstanding": "Spot basic shares outstanding (directly reported)",
    }.get(value, _humanize_id(value))


def _extraction_method_label(value: str) -> str:
    return {
        "sec_xbrl": "SEC Inline XBRL",
        "sec_inline_xbrl": "SEC Inline XBRL",
    }.get(value, _humanize_id(value))


def _metric_provenance(metric: dict[str, Any] | None) -> str:
    provenance = (metric or {}).get("provenance") or {}
    concept = provenance.get("cell_or_range")
    if not concept:
        formula = provenance.get("formula") or (metric or {}).get("formula_description")
        return formula or "No metric-level concept was recorded."
    concept = str(concept).split("}")[-1].split("#")[0]
    return f"SEC Inline XBRL concept: {concept}"


def _metric_lineage_rows(latest_lookup: Any, fy_lookup: Any) -> list[dict[str, str]]:
    rows = []
    specifications = (
        (
            "Fiscal year", fy_lookup,
            (
                "revenue_total", "operating_profit_before_investment_activities",
                "net_profit_attributable_parent", "cf_net_operating_activities",
                "cf_capex_ppe_intangible", "cf_dividends_paid",
                "cf_share_repurchases", "free_cash_flow",
            ),
        ),
        (
            "Latest YTD", latest_lookup,
            (
                "revenue_total", "operating_profit_before_investment_activities",
                "net_profit_attributable_parent", "free_cash_flow",
            ),
        ),
    )
    for period_set, lookup, metric_ids in specifications:
        for metric_id in metric_ids:
            metric = lookup.get(metric_id)
            if not metric or metric.get("value") is None:
                continue
            rows.append({
                "period_set": period_set,
                "metric": _METRIC_LABELS.get(metric_id, _humanize_id(metric_id)),
                "lineage": _metric_provenance(metric),
            })
    return rows


def _share_count_summary(market_snapshot: dict[str, Any]) -> dict[str, Any] | None:
    basis = market_snapshot.get("share_basis") or {}
    shares = _decimal(basis.get("spot_basic_shares_outstanding"))
    if shares is None:
        return None
    return {
        "shares_millions": shares / Decimal("1000000"),
        "effective_date": basis.get("effective_date"),
        "derivation_method": _humanize_id(basis.get("derivation_method", "")),
    }


def _date_gap_days(financial_period_end: str | None, price_session_date: str | None) -> int | None:
    try:
        return (
            date.fromisoformat(str(price_session_date)) -
            date.fromisoformat(str(financial_period_end))
        ).days
    except ValueError:
        return None


def _fiscal_year_naming_note(
    latest_financials: dict[str, Any], fy_financials: dict[str, Any],
) -> str | None:
    try:
        latest_label_year = int(str(latest_financials["period"]).split("-", 1)[0])
        latest_end_year = date.fromisoformat(latest_financials["period_end"]).year
        fy_end = date.fromisoformat(fy_financials["period_end"])
    except (KeyError, TypeError, ValueError):
        return None
    if latest_label_year == latest_end_year and (fy_end.month, fy_end.day) == (12, 31):
        return None
    return (
        "Fiscal period labels follow the issuer's fiscal-year convention, not the "
        "calendar year in which every quarter occurs. A period can therefore be "
        f"labelled FY{latest_label_year} even when it ends in {latest_end_year}."
    )


def _latest_available_annual_leases(
    latest_lookup: Any, fy_lookup: Any, fy_financials: dict[str, Any],
) -> dict[str, Any] | None:
    latest_current = latest_lookup.get("lease_liabilities_short_term")
    latest_noncurrent = latest_lookup.get("lease_liabilities_long_term")
    if latest_current and latest_noncurrent:
        return None
    annual_current = fy_lookup.get("lease_liabilities_short_term")
    annual_noncurrent = fy_lookup.get("lease_liabilities_long_term")
    current_value = _decimal((annual_current or {}).get("value"))
    noncurrent_value = _decimal((annual_noncurrent or {}).get("value"))
    if current_value is None or noncurrent_value is None:
        return None
    return {
        "current": current_value,
        "noncurrent": noncurrent_value,
        "total": current_value + noncurrent_value,
        "period": fy_financials.get("period"),
        "period_end": fy_financials.get("period_end"),
        "source_id": ((annual_current.get("provenance") or {}).get("source_id")),
    }


def _build_ttm_fcf_bridge(
    latest_lookup: Any, fy_lookup: Any, methods: dict[str, Any],
) -> dict[str, Any] | None:
    fy_fcf = fy_lookup.get("free_cash_flow")
    current_ytd_fcf = latest_lookup.get("free_cash_flow")
    if not fy_fcf or not current_ytd_fcf:
        return None
    fy_value = _decimal(fy_fcf.get("value"))
    latest_is_annual = _latest_is_the_fiscal_year(fy_fcf, current_ytd_fcf)
    current_value = _decimal(current_ytd_fcf.get("value"))
    prior_value = _decimal(current_ytd_fcf.get("comparison_value"))
    if latest_is_annual:
        if fy_value is None:
            return None
        raw_ttm = fy_value
    else:
        if None in (fy_value, current_value, prior_value):
            return None
        raw_ttm = fy_value + current_value - prior_value
    current_cfo = latest_lookup.get("cf_net_operating_activities")
    current_capex = latest_lookup.get("cf_capex_ppe_intangible")
    current_parent_income = latest_lookup.get("net_profit_attributable_parent")
    fy_parent_income = fy_lookup.get("net_profit_attributable_parent")
    current_total_income = latest_lookup.get("net_profit_for_period")
    fy_total_income = fy_lookup.get("net_profit_for_period")
    ttm_parent_income = _ttm_metric_value(fy_parent_income, current_parent_income)
    ttm_total_income = _ttm_metric_value(fy_total_income, current_total_income)
    attribution_ratio = (
        ttm_parent_income / ttm_total_income
        if ttm_parent_income is not None and ttm_total_income not in (None, Decimal("0"))
        else None
    )
    method = methods.get("val.method.fcf_yield.standard_equity") or {}
    numerator = _decimal(((method.get("numerator") or {}).get("amount") or {}).get("value"))
    valuation_fcf = numerator / Decimal("1000000") if numerator is not None else None
    return {
        "latest_is_annual": latest_is_annual,
        "fy_fcf": fy_value,
        "fy_period": fy_fcf.get("period"),
        "current_ytd_fcf": current_value,
        "current_period": current_ytd_fcf.get("period"),
        "prior_ytd_fcf": prior_value,
        "prior_period": current_ytd_fcf.get("comparison_period"),
        "raw_ttm_fcf": raw_ttm,
        "valuation_fcf": valuation_fcf,
        "attribution_adjustment": valuation_fcf - raw_ttm if valuation_fcf is not None else None,
        "current_ytd_cfo": _decimal((current_cfo or {}).get("value")),
        "prior_ytd_cfo": _decimal((current_cfo or {}).get("comparison_value")),
        "current_ytd_capex": _decimal((current_capex or {}).get("value")),
        "prior_ytd_capex": _decimal((current_capex or {}).get("comparison_value")),
        # Only meaningful for a real interim bridge: with no YTD legs there
        # is no prior-year comparable to inflate the mechanical TTM.
        "prior_ytd_was_negative": (
            not latest_is_annual and prior_value is not None and prior_value < 0
        ),
        "ttm_parent_income": ttm_parent_income,
        "ttm_total_income": ttm_total_income,
        "attribution_ratio": attribution_ratio,
    }


def _latest_is_the_fiscal_year(
    annual_metric: dict[str, Any] | None, current_metric: dict[str, Any] | None,
) -> bool:
    """True when the most recent financial basis IS the annual period
    itself rather than an interim YTD period. Documented as possible in
    docs/us-market-pipeline.md (a newly filed 10-K is more recent than the
    last 10-Q), but the TTM bridges below originally assumed an interim
    latest period unconditionally and so added the fiscal year to itself."""
    annual_period = (annual_metric or {}).get("period")
    current_period = (current_metric or {}).get("period")
    return bool(annual_period) and annual_period == current_period


def _ttm_metric_value(
    annual_metric: dict[str, Any] | None, current_metric: dict[str, Any] | None,
) -> Decimal | None:
    annual = _decimal((annual_metric or {}).get("value"))
    if _latest_is_the_fiscal_year(annual_metric, current_metric):
        # The trailing twelve months ARE the fiscal year; adding the same
        # period to itself and subtracting the prior year would produce
        # 2xFY - priorFY, which is not a period at all.
        return annual
    current = _decimal((current_metric or {}).get("value"))
    prior = _decimal((current_metric or {}).get("comparison_value"))
    if None in (annual, current, prior):
        return None
    return annual + current - prior


def _build_ttm_earnings_bridges(
    latest_lookup: Any, fy_lookup: Any, methods: dict[str, Any],
) -> list[dict[str, Any]]:
    specifications = (
        (
            "net_profit_attributable_parent", "Net Income Attributable to Parent",
            "val.method.pe.reported_parent", "denominator",
        ),
        (
            "operating_profit_before_investment_activities", "Core Operating Profit (EBIT)",
            "val.method.ev_to_ebit.core", "denominator",
        ),
    )
    bridges = []
    for metric_id, label, method_id, operand_name in specifications:
        annual = fy_lookup.get(metric_id)
        current = latest_lookup.get(metric_id)
        if not annual or not current:
            continue
        annual_value = _decimal(annual.get("value"))
        latest_is_annual = _latest_is_the_fiscal_year(annual, current)
        current_value = _decimal(current.get("value"))
        prior_value = _decimal(current.get("comparison_value"))
        if latest_is_annual:
            if annual_value is None:
                continue
            calculated = annual_value
        else:
            if None in (annual_value, current_value, prior_value):
                continue
            calculated = annual_value + current_value - prior_value
        method = methods.get(method_id) or {}
        amount = _decimal(
            (((method.get(operand_name) or {}).get("amount") or {}).get("value"))
        )
        valuation_value = amount / Decimal("1000000") if amount is not None else None
        bridges.append({
            "label": label,
            "latest_is_annual": latest_is_annual,
            "fy_period": annual.get("period"),
            "current_period": current.get("period"),
            "prior_period": current.get("comparison_period"),
            "fy_value": annual_value,
            "current_ytd_value": current_value,
            "prior_ytd_value": prior_value,
            "calculated_ttm": calculated,
            "valuation_value": valuation_value,
            "reconciled": valuation_value is not None and abs(calculated - valuation_value) < Decimal("0.1"),
        })
    return bridges


def _maturity_coverage_notes(debt_profile: dict[str, Any] | None) -> list[str]:
    if not debt_profile:
        return []
    expected = (
        "next 12 months", "year 2", "year 3", "year 4", "year 5", "after year 5",
    )
    reported = {
        (row.get("liability_scope"), row.get("maturity_bucket"))
        for row in debt_profile.get("maturity_profile", [])
        if row.get("status") == "reported"
    }
    notes = []
    for scope in ("Long-term debt", "Operating leases", "Finance leases"):
        present = {bucket for row_scope, bucket in reported if row_scope == scope}
        if not present:
            notes.append(f"{scope}: no structured maturity schedule was disclosed or extracted.")
            continue
        missing = [bucket for bucket in expected if bucket not in present]
        if missing:
            notes.append(
                f"{scope}: " + ", ".join(missing) + " not disclosed or extracted."
            )
    return notes


def _maturity_schedule_source(debt_profile: dict[str, Any] | None) -> dict[str, str] | None:
    if not debt_profile:
        return None
    for row in debt_profile.get("maturity_profile", []):
        evidence = row.get("evidence") or {}
        if evidence.get("source_id"):
            return {
                "source_id": evidence["source_id"],
                "source_file": evidence.get("source_file", ""),
            }
    return None


def _financial_source_summary(financials: dict[str, Any]) -> dict[str, Any]:
    source = None
    for statement in ("income_statement", "balance_sheet", "cash_flow_statement"):
        for metric in financials.get(statement, []):
            provenance = metric.get("provenance") or {}
            if provenance.get("source_id"):
                source = provenance
                break
        if source:
            break
    return {
        "source_id": (source or {}).get("source_id", "not available"),
        "source_file": (source or {}).get("source_file", "not available"),
        "publication_date": financials.get("publication_date"),
        "period_end": financials.get("period_end"),
    }


def _available_amount(ledger: dict[str, Any], component_id: str) -> Decimal | None:
    amount = ledger.get(component_id, {}).get("amount") or {}
    if amount.get("status", "available") != "available":
        return None
    return _decimal(amount.get("value"))


def _build_ev_bridge(
    ledger: dict[str, Any], ev_bases: dict[str, Any],
) -> dict[str, Any] | None:
    component_specs = (
        ("Market capitalization", "comp-market-cap", 1),
        ("Short-term financial debt", "comp-debt-current", 1),
        ("Current portion of long-term debt", "comp-debt-current-portion", 1),
        ("Noncurrent financial debt", "comp-debt-noncurrent", 1),
        ("Noncontrolling interests", "comp-nci", 1),
        ("Cash and cash equivalents", "comp-cash-0", -1),
    )
    rows = []
    total = Decimal("0")
    for label, component_id, sign in component_specs:
        value = _available_amount(ledger, component_id)
        if value is None:
            return None
        signed = value * sign
        rows.append({"label": label, "amount": signed})
        total += signed
    disclosed = _decimal(
        ev_bases.get("ev-ex-lease", {}).get("enterprise_value", {}).get("value")
    )
    calculated_net_debt = sum(
        value
        for value in (
            _available_amount(ledger, "comp-debt-current"),
            _available_amount(ledger, "comp-debt-current-portion"),
            _available_amount(ledger, "comp-debt-noncurrent"),
        )
        if value is not None
    ) - (_available_amount(ledger, "comp-cash-0") or Decimal("0"))
    lease_current = _available_amount(ledger, "comp-lease-current")
    lease_noncurrent = _available_amount(ledger, "comp-lease-noncurrent")
    lease_total = None
    lease_inclusive = None
    if lease_current is not None and lease_noncurrent is not None:
        lease_total = lease_current + lease_noncurrent
        lease_inclusive = total + lease_total
    return {
        "rows": rows,
        "lease_exclusive_ev": total,
        "reported_lease_exclusive_ev": disclosed,
        "lease_exclusive_reconciled": disclosed is not None and abs(total - disclosed) < Decimal("0.1"),
        "calculated_net_debt": calculated_net_debt,
        "lease_liabilities": lease_total,
        "lease_inclusive_ev": lease_inclusive,
    }


def _operand_basis_label(
    operand: dict[str, Any], latest_financials: dict[str, Any],
    fy_financials: dict[str, Any], price_session_date: str,
) -> str:
    economic_type = operand.get("economic_type", "")
    if economic_type == "standard_fcf_parent_share":
        return f"TTM basis ending {_fmt_date(latest_financials.get('period_end', ''))}"
    flow_types = {"parent_net_income", "core_ebit"}
    if economic_type in flow_types:
        return f"TTM basis ending {_fmt_date(latest_financials.get('period_end', ''))}"
    if economic_type in {"market_cap", "enterprise_value_ex_lease", "enterprise_value_incl_lease"}:
        return f"spot market basis using the {_fmt_date(price_session_date)} close"
    return f"balance-sheet basis at {_fmt_date(latest_financials.get('period_end', ''))}"


def _signal_explanation(signal: dict[str, Any]) -> str:
    code = signal.get("reason_code", "")
    params = signal.get("reason_params") or {}
    evidence = signal.get("evidence") or {}
    if code == "growth_positive":
        return (
            f"Up {_fmt_number(params.get('growth_pct'), 1)}% year over year "
            f"({_fmt_number(evidence.get('current_value'), 1)} versus "
            f"{_fmt_number(evidence.get('current_comparison_value'), 1)} million USD); "
            "positive threshold is +5%."
        )
    if code == "growth_negative":
        return (
            f"Down {_fmt_number(abs(params.get('growth_pct', 0)), 1)}% year over year "
            f"({_fmt_number(evidence.get('current_value'), 1)} versus "
            f"{_fmt_number(evidence.get('current_comparison_value'), 1)} million USD); "
            "negative threshold is -5%."
        )
    if code == "profit_to_loss":
        return f"Changed from {_fmt_number(params.get('previous'), 1)} to {_fmt_number(params.get('current'), 1)} million USD."
    if code == "loss_to_profit":
        return f"Changed from {_fmt_number(params.get('previous'), 1)} to {_fmt_number(params.get('current'), 1)} million USD."
    if code == "margin_positive":
        return f"Improved by {_fmt_number(params.get('change_pp'), 1)} percentage points; positive threshold is +0.5 points."
    if code == "margin_negative":
        return f"Declined by {_fmt_number(abs(params.get('change_pp', 0)), 1)} percentage points; negative threshold is -0.5 points."
    if code == "cash_conversion_improved":
        return f"Operating-cash-flow / net-income ratio improved by {_fmt_number(params.get('change'), 2)}x."
    if code == "cash_conversion_deteriorated":
        return f"Operating-cash-flow / net-income ratio declined by {_fmt_number(abs(params.get('change', 0)), 2)}x."
    if code == "lease_burden_directional":
        return f"Lease liabilities increased {_fmt_number(params.get('lease_liability_growth_pct'), 1)}% year over year."
    return _humanize_id(code or signal.get("signal_id", "signal"))


def _risk_evidence(risk: dict[str, Any]) -> str:
    evidence = risk.get("evidence") or []
    if not evidence or not evidence[0].get("summary"):
        return "No short excerpt was available in the authored risk artifact."
    words = str(evidence[0]["summary"]).split()
    excerpt = " ".join(words[:22])
    return f'“{excerpt}{"…" if len(words) > 22 else ""}”'


def _fmt_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value[:10])
        return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
    except (ValueError, TypeError):
        return value


def _fiscal_period_label(financials: dict[str, Any]) -> str:
    period = financials.get("period", "period")
    end = _fmt_date(financials.get("period_end", ""))
    start_raw = financials.get("period_start")
    if financials.get("period_type") == "annual":
        return f"{period.replace('-FY', ' fiscal year')} ended {end}"
    if start_raw:
        try:
            days = (date.fromisoformat(financials["period_end"]) - date.fromisoformat(start_raw)).days + 1
            weeks = round(days / 7)
            return f"fiscal {period.split('-')[-1]} {period.split('-')[0]} YTD ({weeks} weeks) ended {end}"
        except ValueError:
            pass
    return f"fiscal {period} ended {end}"


def _collapse_blank_lines(text: str) -> str:
    collapsed: list[str] = []
    for line in (line.rstrip() for line in text.splitlines()):
        if line or not collapsed or collapsed[-1]:
            collapsed.append(line)
    while collapsed and not collapsed[-1]:
        collapsed.pop()
    return "\n".join(collapsed) + "\n"
