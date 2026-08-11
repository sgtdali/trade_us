"""Generalized financial-statement reconciliation checks, ported from the
pre-generalization ticker-specific validator that used to live in
scripts/. Operate on any company's loaded
``data/financial/{TICKER}/{period}.json`` structure; nothing here
references a ticker, a file path, or a hard-coded expected period.
"""

from __future__ import annotations

from .result import ValidationFinding, ValidationResult

TOLERANCE = 1  # million-currency-unit rounding tolerance, matching the pre-generalization validator


def _value(metrics: list[dict], metric_id: str) -> float | None:
    for m in metrics:
        if m["metric_id"] == metric_id:
            return m["value"]
    return None


def validate_statements(direct_financials: dict, file_label: str) -> ValidationResult:
    result = ValidationResult()
    bs = direct_financials.get("balance_sheet", [])
    inc = direct_financials.get("income_statement", [])
    cf = direct_financials.get("cash_flow_statement", [])

    _check_balance_sheet(result, bs, file_label)
    _check_income_statement(result, inc, file_label)
    _check_cash_flow(result, cf, file_label)
    _check_cash_flow_opening_profit(result, inc, cf, file_label)
    _check_numeric_types(result, direct_financials, file_label)
    return result


def _check_balance_sheet(result: ValidationResult, bs: list[dict], file_label: str) -> None:
    if not bs:
        return
    assets = _value(bs, "total_assets")
    liabilities = _value(bs, "total_liabilities")
    equity = _value(bs, "total_equity")
    if None in (assets, liabilities, equity):
        result.add(ValidationFinding("balance_sheet_incomplete", "warning", "Required balance-sheet totals for the equality check are missing.", file_label))
    else:
        diff = abs(assets - (liabilities + equity))
        if diff > TOLERANCE:
            result.add(ValidationFinding(
                "balance_sheet_inequality", "error",
                f"total_assets ({assets}) != total_liabilities + total_equity ({liabilities}+{equity}={liabilities + equity}), diff={diff}",
                file_label,
            ))

    cur_assets, noncur_assets = _value(bs, "total_current_assets"), _value(bs, "total_noncurrent_assets")
    if cur_assets is not None and noncur_assets is not None and assets is not None:
        if abs((cur_assets + noncur_assets) - assets) > TOLERANCE:
            result.add(ValidationFinding("current_noncurrent_assets_mismatch", "error", f"current + noncurrent assets ({cur_assets}+{noncur_assets}) != total_assets ({assets})", file_label))

    cur_liab, noncur_liab = _value(bs, "total_current_liabilities"), _value(bs, "total_noncurrent_liabilities")
    if cur_liab is not None and noncur_liab is not None and liabilities is not None:
        if abs((cur_liab + noncur_liab) - liabilities) > TOLERANCE:
            result.add(ValidationFinding("current_noncurrent_liabilities_mismatch", "error", f"current + noncurrent liabilities ({cur_liab}+{noncur_liab}) != total_liabilities ({liabilities})", file_label))


def _check_income_statement(result: ValidationResult, inc: list[dict], file_label: str) -> None:
    if not inc:
        return
    revenue, cos, gross_profit = _value(inc, "revenue_total"), _value(inc, "cost_of_sales"), _value(inc, "gross_profit")
    # Some issuers (e.g. an OEM consolidating a captive finance subsidiary)
    # report gross profit as commercial-operations gross profit plus a
    # separate finance-sector-operations gross profit/loss line. Missing
    # this optional term is zero only in the sense that the two-term
    # identity must still pass; it is never invented to close a residual.
    finance_sector_gp = _value(inc, "gross_profit_finance_sector_operations")
    # Gross profit pairs the revenue that actually carries a cost of sales.
    # A membership warehouse, franchisor or licensor reports total revenue
    # that also contains streams with no matched cost, and its reported gross
    # profit is struck against merchandise sales alone: COST's fiscal 2019 Q1
    # shows total revenue 35,069, merchandise costs 30,623 and gross profit
    # 3,688, the 758 residual being membership fees. Forcing the two-term
    # identity on total revenue fails such an issuer in every period.
    #
    # The term is only ever an amount extracted from a disclosed revenue
    # component, never the residual itself -- deriving it from the identity
    # would make the check tautological, the same trap that let a broken
    # revenue selection through a derived gross profit unnoticed.
    uncosted_revenue = _value(inc, "revenue_without_matched_cost_of_sales")
    if None not in (revenue, cos, gross_profit):
        finance_sector_gp_or_zero = finance_sector_gp if finance_sector_gp is not None else 0
        uncosted_or_zero = uncosted_revenue if uncosted_revenue is not None else 0
        if abs((revenue + cos + finance_sector_gp_or_zero - uncosted_or_zero) - gross_profit) > TOLERANCE:
            result.add(ValidationFinding("gross_profit_mismatch", "error", f"revenue ({revenue}) + cost_of_sales ({cos}) + gross_profit_finance_sector_operations ({finance_sector_gp}) - revenue_without_matched_cost_of_sales ({uncosted_revenue}) != gross_profit ({gross_profit})", file_label))

    if cos is not None:
        cost_breakdown_sum = sum(m["value"] for m in inc if m["metric_id"].startswith("cost_") and m["metric_id"] != "cost_of_sales")
        if abs(cost_breakdown_sum - cos) > TOLERANCE and cost_breakdown_sum != 0:
            result.add(ValidationFinding("cost_breakdown_mismatch", "warning", f"sum of cost_* line items ({cost_breakdown_sum}) != cost_of_sales ({cos})", file_label))

    net_profit = _value(inc, "net_profit_for_period")
    parent = _value(inc, "net_profit_attributable_parent")
    nci = _value(inc, "net_profit_attributable_noncontrolling")
    # A consolidated total the issuer never tagged is summed from these same
    # two components, so comparing it back to them is true by construction and
    # checks nothing. Only a reported total is a real cross-check.
    total_is_reported = any(
        metric.get("metric_id") == "net_profit_for_period"
        and metric.get("data_type") != "derived"
        for metric in inc
    )
    if total_is_reported and None not in (net_profit, parent, nci):
        if abs((parent + nci) - net_profit) > TOLERANCE:
            result.add(ValidationFinding("net_profit_attribution_mismatch", "error", f"parent ({parent}) + noncontrolling ({nci}) != net_profit_for_period ({net_profit})", file_label))


def _check_cash_flow(result: ValidationResult, cf: list[dict], file_label: str) -> None:
    if not cf:
        return
    begin, change, end = _value(cf, "cf_cash_beginning_period"), _value(cf, "cf_net_change_in_cash"), _value(cf, "cf_cash_end_period")
    if None not in (begin, change, end):
        if abs((begin + change) - end) > TOLERANCE:
            result.add(ValidationFinding("cash_reconciliation_mismatch", "error", f"beginning cash ({begin}) + net change ({change}) != ending cash ({end})", file_label))

    before_fx, fx = _value(cf, "cf_net_change_before_fx"), _value(cf, "cf_fx_effect_on_cash")
    inflation = _value(cf, "cf_inflation_effect_on_cash")  # IAS 29 purchasing-power effect on cash; only present for hyperinflationary-economy filers (e.g. TMS 29 reporters)
    if None not in (before_fx, fx, change):
        reconciled = before_fx + fx + (inflation or 0)
        if abs(reconciled - change) > TOLERANCE:
            detail = f"pre-FX change ({before_fx}) + FX effect ({fx})"
            if inflation is not None:
                detail += f" + inflation effect ({inflation})"
            result.add(ValidationFinding("cash_fx_reconciliation_mismatch", "error", f"{detail} != total net change ({change})", file_label))

    capex = _value(cf, "cf_capex_ppe_intangible")
    if capex is not None and capex > 0:
        result.add(ValidationFinding("capex_sign_positive", "error", f"cf_capex_ppe_intangible is positive ({capex}); capex is a cash outflow and must be signed negative", file_label))

    lease_payments = _value(cf, "cf_lease_payments")
    if lease_payments is not None and lease_payments > 0:
        result.add(ValidationFinding("lease_payments_sign_positive", "error", f"cf_lease_payments is positive ({lease_payments}); lease payments are a cash outflow and must be signed negative", file_label))


def _check_cash_flow_opening_profit(result: ValidationResult, inc: list[dict], cf: list[dict], file_label: str) -> None:
    """The cash flow statement's opening profit line must be the same figure
    the income statement reports for the same period.

    This is the only check that ties the income statement and the cash flow
    statement together, and it is the one that catches a *period-scope* error
    -- a file whose income statement was captured from KAP's single-quarter
    column while its cash flow statement (published YTD-only) stayed
    cumulative. Every other rule here is intra-statement, and KAP's
    single-quarter column is itself a complete, internally consistent
    statement, so nothing else can see that class of mistake.

    Two openings are both legitimate under IAS 7's indirect method: profit
    for the period, or profit before tax (SASA files the latter). Only a
    figure matching neither is reported, and only as a warning -- a genuine
    third convention exists in the wild (some issuers open from profit from
    continuing operations), so this flags a period-scope suspicion for
    review rather than blocking a filing that may be faithfully extracted.
    """
    opening = _value(cf, "cf_net_profit_for_period")
    if opening is None:
        return
    net_profit = _value(inc, "net_profit_for_period")
    profit_before_tax = _value(inc, "profit_before_tax")
    candidates = [candidate for candidate in (net_profit, profit_before_tax) if candidate is not None]
    if not candidates:
        return
    # Relative tolerance: these are raw statement figures whose scale varies by
    # orders of magnitude across issuers, so a flat unit tolerance would be
    # meaningless on the large ones and spuriously strict on the small ones.
    if any(abs(opening - candidate) <= max(TOLERANCE, abs(candidate) * 0.001) for candidate in candidates):
        return
    result.add(ValidationFinding(
        "cash_flow_opening_profit_mismatch", "warning",
        f"cash flow statement opens from {opening}, which matches neither net_profit_for_period "
        f"({net_profit}) nor profit_before_tax ({profit_before_tax}); the two statements may cover "
        "different period scopes (e.g. a single-quarter income statement against a year-to-date cash flow statement)",
        file_label,
    ))


_NUMERIC_KEYS = {"value", "comparison_value", "change", "score"}
_ALLOWED_STRING_SIGNAL_VALUES = {"positive", "negative", "neutral", "mixed", "unavailable"}


def _check_numeric_types(result: ValidationResult, data: dict, file_label: str, path: str = "") -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            child_path = f"{path}.{key}" if path else key
            if key in _NUMERIC_KEYS and isinstance(value, str) and value not in _ALLOWED_STRING_SIGNAL_VALUES:
                result.add(ValidationFinding("numeric_field_is_string", "error", f"field {key!r} holds a string value where a number was expected: {value!r}", file_label, child_path))
            else:
                _check_numeric_types(result, value, file_label, child_path)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _check_numeric_types(result, item, file_label, f"{path}[{i}]")
