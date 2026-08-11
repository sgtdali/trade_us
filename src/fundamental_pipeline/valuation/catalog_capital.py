"""Authored valuation catalog definitions.

Kept by domain so catalog content remains reviewable without changing its
canonical structure.
"""

from __future__ import annotations

from typing import Any

_CAPITAL_BASIS_ENTRIES: list[dict[str, Any]] = [
    {
        "entry_id": "val.formula.capital.spot_basic_shares",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Spot basic shares outstanding",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#1"],
        "body": {
            "evaluator_type": "arithmetic",
            "expression": "S_basic = issued_shares - treasury_shares",
            "ast": {"op": "subtract", "args": [{"ref": "issued_shares"}, {"ref": "treasury_shares"}]},
            "inputs": [
                {"input_id": "issued_shares", "requiredness": "required", "unit_family": "shares"},
                {"input_id": "treasury_shares", "requiredness": "required", "unit_family": "shares"},
            ],
            "output": {"output_id": "spot_basic_shares_outstanding", "unit_family": "shares"},
            "applicability": "Same effective date and instrument class basis for both operands; corporate-action coverage must be complete.",
            "missing_data_behavior": "Missing treasury disclosure is unavailable, never assumed zero. Result <= 0 is calculation_blocked.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.market_cap_spot_basic",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Spot basic market capitalization",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#2"],
        "body": {
            "evaluator_type": "arithmetic",
            "expression": "MC_native = P_native_per_share * S_basic * unit_multiplier",
            "ast": {"op": "multiply", "args": [{"ref": "price_native_per_share"}, {"ref": "spot_basic_shares_outstanding"}, {"ref": "unit_multiplier"}]},
            "inputs": [
                {"input_id": "price_native_per_share", "requiredness": "required", "unit_family": "price_per_share"},
                {"input_id": "spot_basic_shares_outstanding", "requiredness": "required", "unit_family": "shares"},
                {"input_id": "unit_multiplier", "requiredness": "required", "unit_family": "ratio"},
            ],
            "output": {"output_id": "market_cap_native", "unit_family": "amount"},
            "applicability": "Price and share basis must be on a compatible effective date; free-float shares are never the denominator; diluted shares never produce this primary spot market cap.",
            "missing_data_behavior": "Any missing required operand leaves market_cap_native unavailable; never coerced to zero.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.currency_convert",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Currency conversion",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#5"],
        "body": {
            "evaluator_type": "arithmetic",
            "expression": "amount_target = amount_source * fx_target_per_source",
            "ast": {"op": "multiply", "args": [{"ref": "amount_source"}, {"ref": "fx_target_per_source"}]},
            "inputs": [
                {"input_id": "amount_source", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "fx_target_per_source", "requiredness": "required", "unit_family": "rate"},
            ],
            "output": {"output_id": "amount_target", "unit_family": "amount"},
            "applicability": "fx_target_per_source must be strictly positive and as-of compatible; inverse quote uses fx_target_per_source = 1 / fx_source_per_target.",
            "missing_data_behavior": "Missing or non-positive FX rate leaves amount_target unavailable.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.financial_debt_ex_lease",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Interest-bearing financial debt excluding lease liabilities",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#4"],
        "body": {
            "evaluator_type": "ledger_aggregate",
            "expression": "D_fin = short_term_borrowings + current_portion_long_term_borrowings + long_term_borrowings + eligible_interest_bearing_other_debt",
            "ast": {"op": "add", "args": [
                {"ref": "short_term_borrowings"}, {"ref": "current_portion_long_term_borrowings"},
                {"ref": "long_term_borrowings"}, {"ref": "eligible_interest_bearing_other_debt"},
            ]},
            "inputs": [
                {"input_id": "short_term_borrowings", "requiredness": "conditional", "unit_family": "amount"},
                {"input_id": "current_portion_long_term_borrowings", "requiredness": "conditional", "unit_family": "amount"},
                {"input_id": "long_term_borrowings", "requiredness": "conditional", "unit_family": "amount"},
                {"input_id": "eligible_interest_bearing_other_debt", "requiredness": "optional_diagnostic", "unit_family": "amount"},
            ],
            "output": {"output_id": "financial_debt_ex_lease", "unit_family": "amount"},
            "applicability": "Lease liabilities are always excluded here; each ledger component is tagged included/excluded/conditional/unresolved by the source balance sheet.",
            "missing_data_behavior": "An unresolved required component leaves financial_debt_ex_lease unavailable, never assumed zero.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.lease_liability_total",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Total recognized lease liabilities",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#5"],
        "body": {
            "evaluator_type": "arithmetic",
            "expression": "L = current_lease_liability + noncurrent_lease_liability",
            "ast": {"op": "add", "args": [{"ref": "current_lease_liability"}, {"ref": "noncurrent_lease_liability"}]},
            "inputs": [
                {"input_id": "current_lease_liability", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "noncurrent_lease_liability", "requiredness": "required", "unit_family": "amount"},
            ],
            "output": {"output_id": "lease_liability_total", "unit_family": "amount"},
            "applicability": "Only used by lease-inclusive net-debt/EV variants.",
            "missing_data_behavior": "Missing lease disclosure is unavailable, never assumed zero; a company with no separate lease disclosure (e.g. EREGL-like) simply cannot produce a lease-inclusive result, while lease-exclusive results remain unaffected.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.eligible_cash_total",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Eligible cash and cash-like total",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#6"],
        "body": {
            "evaluator_type": "ledger_aggregate",
            "expression": "C_elig = sum(included eligible cash/investment components)",
            "ast": {"op": "sum", "args": [{"ref": "eligible_cash_component"}]},
            "inputs": [
                {"input_id": "eligible_cash_component", "requiredness": "conditional", "unit_family": "amount"},
            ],
            "output": {"output_id": "eligible_cash_total", "unit_family": "amount"},
            "applicability": "Default included: unrestricted cash/equivalents, policy-confirmed highly-liquid current financial investments. Default excluded: restricted cash, strategic/equity-method investments, non-distributable pension/insurance assets, collateral balances, noncurrent financial investments. Noncurrent financial investments are only conditional_included when reliable current value, liquidity, non-strategic character, and reviewed rationale jointly hold.",
            "missing_data_behavior": "An unresolved component is excluded from the sum and flagged, never silently treated as zero-eligible or fully-eligible.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.net_debt_ex_lease",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Net debt, lease-exclusive",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#7"],
        "body": {
            "evaluator_type": "arithmetic",
            "expression": "ND_ex = D_fin - C_elig",
            "ast": {"op": "subtract", "args": [{"ref": "financial_debt_ex_lease"}, {"ref": "eligible_cash_total"}]},
            "inputs": [
                {"input_id": "financial_debt_ex_lease", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "eligible_cash_total", "requiredness": "required", "unit_family": "amount"},
            ],
            "output": {"output_id": "net_debt_ex_lease", "unit_family": "amount"},
            "applicability": "A negative result is canonical net cash; clamping to zero is forbidden.",
            "missing_data_behavior": "Missing either operand leaves net_debt_ex_lease unavailable.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.net_debt_incl_lease",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Net debt, lease-inclusive",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#8"],
        "body": {
            "evaluator_type": "arithmetic",
            "expression": "ND_incl = D_fin + L - C_elig",
            "ast": {"op": "subtract", "args": [
                {"op": "add", "args": [{"ref": "financial_debt_ex_lease"}, {"ref": "lease_liability_total"}]},
                {"ref": "eligible_cash_total"},
            ]},
            "inputs": [
                {"input_id": "financial_debt_ex_lease", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "lease_liability_total", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "eligible_cash_total", "requiredness": "required", "unit_family": "amount"},
            ],
            "output": {"output_id": "net_debt_incl_lease", "unit_family": "amount"},
            "applicability": "Postcondition: net_debt_incl_lease - net_debt_ex_lease must equal lease_liability_total exactly; a lease double-counted in another debt line is a blocker.",
            "missing_data_behavior": "Missing lease_liability_total leaves net_debt_incl_lease unavailable even when net_debt_ex_lease is available.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.enterprise_value_ex_lease",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Enterprise value, lease-exclusive",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#9"],
        "body": {
            "evaluator_type": "ledger_aggregate",
            "expression": "EV_ex = MC + D_fin + NCI + Pref + JV_adj - C_elig, equivalently MC + ND_ex + NCI + Pref + JV_adj",
            "ast": {"op": "add", "args": [
                {"ref": "market_cap_native"}, {"ref": "net_debt_ex_lease"},
                {"ref": "noncontrolling_interests"}, {"ref": "preferred_equity"}, {"ref": "equity_method_adjustment"},
            ]},
            "inputs": [
                {"input_id": "market_cap_native", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "net_debt_ex_lease", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "noncontrolling_interests", "requiredness": "conditional", "unit_family": "amount"},
                {"input_id": "preferred_equity", "requiredness": "conditional", "unit_family": "amount"},
                {"input_id": "equity_method_adjustment", "requiredness": "optional_diagnostic", "unit_family": "amount"},
            ],
            "output": {"output_id": "enterprise_value_ex_lease", "unit_family": "amount"},
            "applicability": "equity_method_adjustment is only applied via the paired T12 policy; the two ledger forms (direct-component sum and MC + ND_ex sum) must reconcile exactly.",
            "missing_data_behavior": "Missing market_cap_native or net_debt_ex_lease leaves enterprise_value_ex_lease unavailable.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.enterprise_value_incl_lease",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Enterprise value, lease-inclusive",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#10"],
        "body": {
            "evaluator_type": "ledger_aggregate",
            "expression": "EV_incl = MC + D_fin + L + NCI + Pref + JV_adj - C_elig = EV_ex + L",
            "ast": {"op": "add", "args": [{"ref": "enterprise_value_ex_lease"}, {"ref": "lease_liability_total"}]},
            "inputs": [
                {"input_id": "enterprise_value_ex_lease", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "lease_liability_total", "requiredness": "required", "unit_family": "amount"},
            ],
            "output": {"output_id": "enterprise_value_incl_lease", "unit_family": "amount"},
            "applicability": "Only pairable with a lease-compatible operating-earnings/FCF/DCF claim (e.g. EBITDAR); an IFRS16 EBITDA numerator is not automatically lease-inclusive-compatible.",
            "missing_data_behavior": "Missing lease_liability_total leaves enterprise_value_incl_lease unavailable even when enterprise_value_ex_lease is available.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.enterprise_to_parent_equity",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Enterprise value to parent equity value bridge",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#11"],
        "body": {
            "evaluator_type": "ledger_aggregate",
            "expression": "Equity_parent = Enterprise_value - D_fin[- L for lease-inclusive basis] - NCI - Pref - JV_adj + C_elig",
            "ast": {"op": "add", "args": [
                {"op": "subtract", "args": [{"ref": "enterprise_value"}, {"ref": "debt_bridge_component"}]},
                {"ref": "eligible_cash_total"},
            ]},
            "inputs": [
                {"input_id": "enterprise_value", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "debt_bridge_component", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "eligible_cash_total", "requiredness": "required", "unit_family": "amount"},
            ],
            "output": {"output_id": "equity_parent", "unit_family": "amount"},
            "applicability": "debt_bridge_component is the exact reverse of whichever EV-ledger basis (lease-exclusive or lease-inclusive) produced enterprise_value; equity_method_adjustment sign is the exact reverse of its EV-ledger entry.",
            "missing_data_behavior": "Missing enterprise_value leaves equity_parent unavailable.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.equity_value_per_spot_basic_share",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Equity value per spot basic share",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#12"],
        "body": {
            "evaluator_type": "ratio",
            "expression": "value_per_share = Equity_parent / S_basic",
            "ast": {"op": "divide", "args": [{"ref": "equity_parent"}, {"ref": "spot_basic_shares_outstanding"}]},
            "inputs": [
                {"input_id": "equity_parent", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "spot_basic_shares_outstanding", "requiredness": "required", "unit_family": "shares"},
            ],
            "output": {"output_id": "value_per_share", "unit_family": "price_per_share"},
            "applicability": "spot_basic_shares_outstanding must be strictly positive and on the same claim/class basis as equity_parent.",
            "missing_data_behavior": "spot_basic_shares_outstanding <= 0 is calculation_blocked, not unavailable.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        # T71-B addition: standard/after-lease FCF construction. This is a
        # ledger-arithmetic (subtract) formula structurally identical to
        # net_debt_ex_lease/net_debt_incl_lease above -- not a T71 method
        # AST (fundamental_pipeline.valuation.methods.ast) formula -- so it
        # is compiled and evaluated through the same generic
        # basis/capital.py evaluator as the rest of this catalog, not
        # through the T71-A method compiler (which is purpose-built for
        # closed-form ratio methods and has no "amount-only" output shape).
        "entry_id": "val.formula.capital.fcf_standard_equity",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Standard free cash flow (equity), CFO minus capex",
        "source_contract_refs": ["docs/valuation-t67-03-valuation-method-formula-catalog.md#7"],
        "body": {
            "evaluator_type": "arithmetic",
            "expression": "FCF_standard = CFO - capex_standard",
            "ast": {"op": "subtract", "args": [{"ref": "cfo"}, {"ref": "capex_standard"}]},
            "inputs": [
                {"input_id": "cfo", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "capex_standard", "requiredness": "required", "unit_family": "amount"},
            ],
            "output": {"output_id": "fcf_standard", "unit_family": "amount"},
            "applicability": "CFO and capex must share the same period/currency/scope; capex is a normalized positive outflow.",
            "missing_data_behavior": "Missing either operand leaves fcf_standard unavailable; a negative result is preserved signed, never clamped to zero.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.fcf_after_lease_equity",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "After-lease free cash flow (equity), CFO minus capex minus lease principal paid",
        "source_contract_refs": ["docs/valuation-t67-03-valuation-method-formula-catalog.md#8"],
        "body": {
            "evaluator_type": "arithmetic",
            "expression": "FCF_after_lease = CFO - capex_standard - lease_principal_paid",
            "ast": {"op": "subtract", "args": [
                {"op": "subtract", "args": [{"ref": "cfo"}, {"ref": "capex_standard"}]},
                {"ref": "lease_principal_paid"},
            ]},
            "inputs": [
                {"input_id": "cfo", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "capex_standard", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "lease_principal_paid", "requiredness": "required", "unit_family": "amount"},
            ],
            "output": {"output_id": "fcf_after_lease", "unit_family": "amount"},
            "applicability": "lease_principal_paid must be checked against the CFO reconciliation it came from to prevent double subtraction; missing lease payment is unavailable, never assumed zero.",
            "missing_data_behavior": "Missing any operand leaves fcf_after_lease unavailable; a negative result is preserved signed, never clamped to zero.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.fcf_standard_equity_parent_share",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Standard free cash flow (equity), parent-attributed via net-income ownership share",
        "source_contract_refs": ["wiki/systems/valuation-pipeline.md#serbest-nakit-akışı-yönteminin-nci-atfı-2026-07-22"],
        "body": {
            "evaluator_type": "arithmetic",
            "expression": "FCF_standard_parent = (CFO - capex_standard) * (parent_net_income / total_net_income)",
            "ast": {"op": "multiply", "args": [
                {"op": "subtract", "args": [{"ref": "cfo"}, {"ref": "capex_standard"}]},
                {"op": "divide", "args": [{"ref": "parent_net_income"}, {"ref": "total_net_income"}]},
            ]},
            "inputs": [
                {"input_id": "cfo", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "capex_standard", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "parent_net_income", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "total_net_income", "requiredness": "required", "unit_family": "amount"},
            ],
            "output": {"output_id": "fcf_standard_parent_share", "unit_family": "amount"},
            "applicability": "All four operands must share the same period/currency/scope. This is a proxy attribution, not a directly disclosed figure: IFRS cash flow statements do not split CFO by ownership the way the P&L splits net income into parent/NCI, so the parent's share of total net income is used as the allocation key. For a company with no noncontrolling interests the ratio is 1 and this is numerically identical to fcf_standard_equity.",
            "missing_data_behavior": "Missing any operand leaves fcf_standard_parent_share unavailable. total_net_income == 0 (or non-positive) is calculation_blocked, not unavailable, matching this catalog's existing zero/negative-denominator convention (see equity_value_per_spot_basic_share). A negative result is preserved signed, never clamped to zero.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.fcf_after_lease_equity_parent_share",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "After-lease free cash flow (equity), parent-attributed via net-income ownership share",
        "source_contract_refs": ["wiki/systems/valuation-pipeline.md#serbest-nakit-akışı-yönteminin-nci-atfı-2026-07-22"],
        "body": {
            "evaluator_type": "arithmetic",
            "expression": "FCF_after_lease_parent = (CFO - capex_standard - lease_principal_paid) * (parent_net_income / total_net_income)",
            "ast": {"op": "multiply", "args": [
                {"op": "subtract", "args": [
                    {"op": "subtract", "args": [{"ref": "cfo"}, {"ref": "capex_standard"}]},
                    {"ref": "lease_principal_paid"},
                ]},
                {"op": "divide", "args": [{"ref": "parent_net_income"}, {"ref": "total_net_income"}]},
            ]},
            "inputs": [
                {"input_id": "cfo", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "capex_standard", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "lease_principal_paid", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "parent_net_income", "requiredness": "required", "unit_family": "amount"},
                {"input_id": "total_net_income", "requiredness": "required", "unit_family": "amount"},
            ],
            "output": {"output_id": "fcf_after_lease_parent_share", "unit_family": "amount"},
            "applicability": "All five operands must share the same period/currency/scope; lease_principal_paid must be checked against the CFO reconciliation it came from to prevent double subtraction. Same net-income-share proxy attribution as fcf_standard_equity_parent_share -- see that entry's applicability note.",
            "missing_data_behavior": "Missing any operand leaves fcf_after_lease_parent_share unavailable. total_net_income == 0 (or non-positive) is calculation_blocked, not unavailable. A negative result is preserved signed, never clamped to zero.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
    {
        "entry_id": "val.formula.capital.implied_return_vs_spot",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Implied return versus spot price",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#13"],
        "body": {
            "evaluator_type": "ratio",
            "expression": "implied_return = implied_value_per_share / spot_price_per_share - 1",
            "ast": {"op": "subtract", "args": [
                {"op": "divide", "args": [{"ref": "implied_value_per_share"}, {"ref": "spot_price_per_share"}]},
                {"ref": "one"},
            ]},
            "inputs": [
                {"input_id": "implied_value_per_share", "requiredness": "required", "unit_family": "price_per_share"},
                {"input_id": "spot_price_per_share", "requiredness": "required", "unit_family": "price_per_share"},
            ],
            "output": {"output_id": "implied_return", "unit_family": "ratio"},
            "applicability": "spot_price_per_share must be strictly positive and in the same currency/basis as implied_value_per_share. This is a diagnostic comparison, never a recommendation.",
            "missing_data_behavior": "spot_price_per_share <= 0 is calculation_blocked.",
            "rounding_policy_ref": "shared.policy.rounding_default",
        },
    },
]
