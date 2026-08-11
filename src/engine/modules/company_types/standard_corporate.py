from .base import CompanyTypeModule

MODULE = CompanyTypeModule(
    module_id="standard_corporate",
    implementation_status="implemented",
    supported_period_types=("annual", "quarterly", "half_year", "nine_month"),
    derived_formula_ids=(
        # Base cash-generation and leverage figures are computed first so
        # that later formulas (margins, ratios) can reference them via
        # "derived:<id>" refs within the same pass.
        "financial_debt", "lease_liability_total", "total_financial_liability_incl_lease",
        "net_financial_debt", "net_financial_liability_incl_lease",
        "free_cash_flow",
        "revenue_growth", "passenger_revenue_growth", "cargo_revenue_growth", "technical_revenue_growth",
        "gross_profit_growth", "operating_profit_growth", "net_profit_growth", "operating_cash_flow_growth",
        "ask_growth", "passenger_growth", "cargo_tonnage_growth",
        "gross_margin", "operating_margin_pre_investment", "operating_margin", "ebitdar_margin",
        "net_margin", "operating_cash_flow_margin", "free_cash_flow_margin",
        "current_ratio", "cash_and_st_investments_to_current_liabilities", "net_working_capital",
        "debt_to_equity", "liability_incl_lease_to_equity", "net_debt_to_ebitdar",
        "roa", "roe", "roic",
        "ocf_to_net_profit", "capex_to_revenue",
        "free_cash_flow_after_lease_payments", "deferred_revenue_change_contribution",
    ),
)
