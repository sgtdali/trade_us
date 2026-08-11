"""The standard-corporate derivation engine: resolves the formula catalog
against an :class:`~fundamental_pipeline.context.AnalysisContext` and
produces the full derived-ratios contract, with no dependency on any
previously generated output file.
"""

from __future__ import annotations

from typing import Any

from ..accounting_context import (
    comparison_context_from_direct_financials,
    context_from_direct_financials,
    context_from_series,
)
from ..context import AnalysisContext
from ..errors import FormulaError, PeriodError
from ..periods import PeriodValue, assemble_ttm, parse_period
from ..registry.formulas import formulas as formula_catalog
from ..registry.metrics import metric_catalog
from . import formulas as ev

CATEGORY_ORDER = ["growth", "margins", "liquidity", "leverage", "returns", "cash_generation"]


class _Pools:
    """Lookup pools for a single AnalysisContext: direct financial metrics,
    financial-operational metrics, and a growing pool of derived values
    (kept separately per current/comparison pass)."""

    def __init__(self, context: AnalysisContext):
        self.direct: dict[str, dict] = {}
        if context.direct_financials:
            for section in ("income_statement", "balance_sheet", "cash_flow_statement", "commitments"):
                for m in context.direct_financials.get(section, []):
                    self.direct[m["metric_id"]] = m
        self.finops: dict[str, dict] = {}
        if context.financial_operational_data:
            for m in context.financial_operational_data.get("metrics", []):
                self.finops[m["metric_id"]] = m
        self.derived_current: dict[str, float | None] = {}
        self.derived_comparison: dict[str, float | None] = {}

        # Whether this file's current-period accounting context is
        # compatible with its comparison-period accounting context (same
        # currency/scale/consolidation/accounting_basis/inflation-adjustment,
        # and non-asymmetric restatement status). Growth/point-change
        # formulas below refuse to compare across an incompatible context
        # rather than silently producing a misleading percentage or delta.
        direct_financials = context.direct_financials or {}
        current_ctx = context_from_direct_financials(direct_financials)
        comparison_ctx = comparison_context_from_direct_financials(direct_financials)
        self.comparison_problems = current_ctx.compatible_with(comparison_ctx)
        self.comparison_compatible = not self.comparison_problems

    def _base_metric(self, dataset: str, metric_id: str) -> dict | None:
        return {"direct": self.direct, "finops": self.finops}[dataset].get(metric_id)

    def resolve(self, ref: str, pass_name: str) -> float | None:
        dataset, metric_id = ref.split(":", 1)
        if dataset == "derived":
            pool = self.derived_current if pass_name == "current" else self.derived_comparison
            return pool.get(metric_id)
        metric = self._base_metric(dataset, metric_id)
        if metric is None:
            return None
        return metric.get("value") if pass_name == "current" else metric.get("comparison_value")

    def primary_metadata(self, ref: str) -> dict | None:
        """The unit/comparison_period/name of the first direct-or-finops ref
        used by a formula, for output metadata purposes."""
        dataset, metric_id = ref.split(":", 1)
        if dataset == "derived":
            return None
        return self._base_metric(dataset, metric_id)


def _first_base_metadata(pools: _Pools, refs: list[str]) -> dict | None:
    for ref in refs:
        meta = pools.primary_metadata(ref)
        if meta is not None:
            return meta
    return None


_SINGLE_REF_KEYS = (
    "ref", "numerator_ref", "denominator_ref", "ocf_ref", "capex_ref", "base_ref",
    "operating_profit_pre_investment_ref", "tax_expense_ref", "profit_before_tax_ref",
    "equity_ref", "net_financial_liability_incl_lease_ref", "net_debt_ref", "ebitdar_annual_ref",
)


def _refs_from_inputs(inputs: Any) -> list[str]:
    if isinstance(inputs, dict):
        refs: list[str] = []
        for key in ("numerator", "denominator"):
            refs.extend(t["ref"] for t in inputs.get(key, []))
        for key in _SINGLE_REF_KEYS:
            if key in inputs and inputs[key] not in refs:
                refs.append(inputs[key])
        return refs
    return [t["ref"] for t in inputs]


def _terms(pools: _Pools, spec: list[dict], pass_name: str) -> list[tuple[float | None, int]]:
    return [(pools.resolve(t["ref"], pass_name), t.get("sign", 1)) for t in spec]


def _evaluate_pass(formula: dict, pools: _Pools, pass_name: str, context: AnalysisContext) -> ev.FormulaResult:
    evaluator = formula["evaluator"]
    inputs = formula["inputs"]
    rounding = formula.get("rounding", 1)

    if evaluator == "growth_pct":
        ref = inputs["ref"]
        current = pools.resolve(ref, "current")
        previous = pools.resolve(ref, "comparison")
        if pass_name != "current":
            return ev.FormulaResult("unavailable", None, "growth is only computed for the current period")
        if not pools.comparison_compatible:
            return ev.FormulaResult(
                "not_comparable", None,
                f"current and comparison accounting contexts are incompatible: {'; '.join(pools.comparison_problems)}",
            )
        return ev.growth_pct(current, previous, rounding=rounding)

    if evaluator == "linear_combination":
        return ev.linear_combination(_terms(pools, inputs, pass_name), rounding=rounding)

    if evaluator in ("ratio", "margin_pct"):
        fn = ev.ratio if evaluator == "ratio" else ev.margin_pct
        kwargs = {}
        if evaluator == "ratio" and formula.get("require_positive_denominator"):
            kwargs["require_positive_denominator"] = True
        return fn(
            _terms(pools, inputs["numerator"], pass_name),
            _terms(pools, inputs["denominator"], pass_name),
            rounding=rounding,
            **kwargs,
        )

    if evaluator == "abs_ratio_pct":
        return ev.abs_ratio_pct(
            pools.resolve(inputs["numerator_ref"], pass_name),
            pools.resolve(inputs["denominator_ref"], pass_name),
            rounding=rounding,
        )

    if evaluator == "standard_fcf":
        return ev.standard_fcf(
            pools.resolve(inputs["ocf_ref"], pass_name),
            pools.resolve(inputs["capex_ref"], pass_name),
            rounding=rounding,
        )

    if evaluator == "add_signed":
        return ev.add_signed([pools.resolve(t["ref"], pass_name) for t in inputs], rounding=rounding)

    if evaluator == "passthrough_with_percent_change":
        ref = inputs["ref"]
        if pass_name != "current":
            return ev.FormulaResult("unavailable", None)
        previous = pools.resolve(ref, "comparison") if pools.comparison_compatible else None
        return ev.passthrough_with_percent_change(pools.resolve(ref, "current"), previous, rounding=rounding)

    if evaluator == "net_debt_to_ebitdar_ratio":
        return _eval_net_debt_to_ebitdar(formula, pools, pass_name, context, rounding)

    if evaluator == "return_on_average_base":
        return _eval_return_on_average_base(formula, pools, pass_name, context, rounding)

    if evaluator == "roic_ratio":
        return _eval_roic(formula, pools, pass_name, context, rounding)

    raise FormulaError(f"Unknown evaluator: {evaluator!r}")


def _trailing_four_quarters_from_series(context: AnalysisContext, metric_id: str) -> list[PeriodValue] | None:
    if not context.historical_series:
        return None
    target = parse_period(context.period_id)
    if target.kind != "quarterly":
        return None
    end_key = target.fiscal_year * 4 + (target.quarter or 0)
    wanted_keys = {end_key - i for i in range(4)}
    by_key: dict[int, PeriodValue] = {}
    for p in context.historical_series.get("periods", []):
        pid = p.get("period")
        try:
            parsed = parse_period(pid)
        except PeriodError:
            continue
        if parsed.kind != "quarterly":
            continue
        key = parsed.fiscal_year * 4 + (parsed.quarter or 0)
        if key not in wanted_keys:
            continue
        entry = p.get("metrics", {}).get(metric_id)
        if entry is None:
            continue
        by_key[key] = PeriodValue(
            metric_id=metric_id,
            period_id=pid,
            value=entry["value"],
            unit=entry.get("unit", ""),
            is_point_in_time=False,
            accounting=context_from_series(context.historical_series, p),
        )
    if len(by_key) != 4:
        return None
    return [by_key[k] for k in sorted(by_key)]


def _eval_net_debt_to_ebitdar(formula: dict, pools: _Pools, pass_name: str, context: AnalysisContext, rounding: int) -> ev.FormulaResult:
    if pass_name != "current":
        return ev.FormulaResult("unavailable", None, "comparison-period net-debt-to-EBITDAR is not assembled generically")
    inputs = formula["inputs"]
    net_debt = pools.resolve(inputs["net_debt_ref"], "current")
    if net_debt is None:
        return ev.FormulaResult("unavailable", None, "net financial liability including leases is unavailable")
    if context.period.kind == "annual":
        ebitdar = pools.resolve(inputs["ebitdar_annual_ref"], "current")
        if ebitdar is None:
            return ev.FormulaResult("unavailable", None, "annual EBITDAR is unavailable")
    else:
        quarters = _trailing_four_quarters_from_series(context, inputs["ebitdar_series_metric_id"])
        if quarters is None:
            return ev.FormulaResult("unavailable", None, "trailing-twelve-month EBITDAR requires four consecutive discrete quarters in the historical series")
        try:
            ttm = assemble_ttm(quarters)
        except PeriodError as e:
            return ev.FormulaResult("unavailable", None, f"TTM assembly failed: {e}")
        ebitdar = ttm.value
    return ev.ratio([(net_debt, 1)], [(ebitdar, 1)], rounding=rounding)


def _eval_return_on_average_base(formula: dict, pools: _Pools, pass_name: str, context: AnalysisContext, rounding: int) -> ev.FormulaResult:
    if pass_name != "current" or context.period.kind != "annual":
        return ev.FormulaResult("unavailable", None, "return ratios are only computed for annual periods without a TTM engine for the numerator")
    inputs = formula["inputs"]
    numerator = pools.resolve(inputs["numerator_ref"], "current")
    base_current = pools.resolve(inputs["base_ref"], "current")
    base_prior = pools.resolve(inputs["base_ref"], "comparison")
    if numerator is None or base_current is None or base_prior is None:
        return ev.FormulaResult("unavailable", None, "numerator or average-base inputs are unavailable")
    average_base = (ev._d(base_current) + ev._d(base_prior)) / 2
    return ev.margin_pct([(numerator, 1)], [(float(average_base), 1)], rounding=rounding)


def _eval_roic(formula: dict, pools: _Pools, pass_name: str, context: AnalysisContext, rounding: int) -> ev.FormulaResult:
    if pass_name != "current" or context.period.kind != "annual":
        return ev.FormulaResult("unavailable", None, "ROIC is only computed for annual periods")
    inputs = formula["inputs"]
    op_profit = pools.resolve(inputs["operating_profit_pre_investment_ref"], "current")
    tax_expense = pools.resolve(inputs["tax_expense_ref"], "current")
    pbt = pools.resolve(inputs["profit_before_tax_ref"], "current")
    equity_current = pools.resolve(inputs["equity_ref"], "current")
    equity_prior = pools.resolve(inputs["equity_ref"], "comparison")
    net_debt_current = pools.resolve(inputs["net_financial_liability_incl_lease_ref"], "current")
    net_debt_prior = pools.resolve(inputs["net_financial_liability_incl_lease_ref"], "comparison")
    if None in (op_profit, tax_expense, pbt, equity_current, equity_prior, net_debt_current):
        return ev.FormulaResult("unavailable", None, "one or more ROIC inputs are unavailable")
    if pbt == 0:
        return ev.FormulaResult("calculation_blocked", None, "zero pre-tax profit")
    # tax_expense follows the signed_statement_value convention (negative =
    # an expense), so negate it to get a positive effective tax rate.
    effective_tax_rate = -ev._d(tax_expense) / ev._d(pbt)
    effective_tax_rate = max(ev._d("0"), min(ev._d("1"), effective_tax_rate))
    nopat = ev._d(op_profit) * (1 - effective_tax_rate)
    invested_current = ev._d(equity_current) + ev._d(net_debt_current)
    if net_debt_prior is None:
        invested_capital = invested_current
    else:
        invested_prior = ev._d(equity_prior) + ev._d(net_debt_prior)
        invested_capital = (invested_current + invested_prior) / 2
    if invested_capital == 0:
        return ev.FormulaResult("calculation_blocked", None, "zero invested capital")
    return ev.FormulaResult("available", ev._round(nopat / invested_capital * 100, rounding), components={
        "effective_tax_rate": float(effective_tax_rate),
        "nopat": float(nopat),
        "average_invested_capital": float(invested_capital),
    })


_CHANGE_POLICY_ROUNDING = {"percentage_point": 2, "ratio_points": 3, "money_points": 1}


def _apply_change_policy(
    policy: str, value: float | None, comparison_value: float | None, growth_component: float | None,
    comparison_compatible: bool = True,
) -> tuple[float | None, str]:
    if policy == "none":
        return None, "not_applicable"
    if not comparison_compatible:
        return None, "not_applicable"
    if policy == "percent_of_prior":
        return growth_component, "percent" if growth_component is not None else "not_applicable"
    if value is None or comparison_value is None:
        return None, "not_applicable"
    places = _CHANGE_POLICY_ROUNDING[policy]
    change = ev._round(ev._d(value) - ev._d(comparison_value), places)
    unit = {"percentage_point": "percentage_point", "ratio_points": "ratio_points", "money_points": "currency_points"}[policy]
    return change, unit


def _applicable(formula: dict, context: AnalysisContext) -> bool:
    if context.company_type not in formula.get("applicable_company_types", []):
        return False
    if context.sector_module_id not in formula.get("applicable_sector_modules", []):
        return False
    if "output_metric_id_by_period_kind" in formula:
        return context.period.kind in formula["output_metric_id_by_period_kind"]
    return True


def _output_metric_id(formula: dict, context: AnalysisContext) -> str:
    if "output_metric_id_by_period_kind" in formula:
        return formula["output_metric_id_by_period_kind"][context.period.kind]
    return formula["output_metric_id"]


def _output_unit(formula: dict, context: AnalysisContext) -> str:
    """Currency-denominated formulas (net_working_capital, financial_debt,
    free_cash_flow, etc.) carry ``"million_usd"`` in the formula catalog as a
    scale-shape placeholder, not a literal currency claim -- every real
    company onboarded before AEFES happened to report in USD/million, so this
    was never wrong in practice until a TRY-reporting company exposed it. The
    actual unit is always the source financial file's own ``currency``/``scale``
    (already used for every direct metric); a non-currency output_unit
    (percent/ratio/etc.) is returned unchanged."""
    unit = formula["output_unit"]
    if unit != "million_usd":
        return unit
    direct_financials = context.direct_financials or {}
    currency = direct_financials.get("currency")
    scale = direct_financials.get("scale")
    if currency and scale:
        return f"{scale}_{currency.lower()}"
    return unit


def derive_financials(context: AnalysisContext) -> dict:
    """Compute the full derived-ratios contract for a standard-corporate
    company from its :class:`AnalysisContext`. Pure function: does not read
    or write any file."""
    pools = _Pools(context)
    catalog = formula_catalog()
    catalog_metadata = metric_catalog()

    by_category: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}

    for formula_id in context.company_type_module.derived_formula_ids:
        formula = catalog.get(formula_id)
        if formula is None:
            raise FormulaError(f"formula_id {formula_id!r} is not registered in the formula catalog")
        if not _applicable(formula, context):
            continue

        current = _evaluate_pass(formula, pools, "current", context)
        comparison = _evaluate_pass(formula, pools, "comparison", context)
        if formula["evaluator"] == "passthrough_with_percent_change":
            # The comparison pass intentionally returns "unavailable" for this
            # evaluator (see _evaluate_pass); the comparison_value shown to
            # the reader is the raw comparison figure of the source metric,
            # not a second pass of the same passthrough logic.
            comparison = ev.FormulaResult("available", pools.resolve(formula["inputs"]["ref"], "comparison"))

        output_id = _output_metric_id(formula, context)
        # Formulas that vary their output id by period kind (e.g.
        # net_debt_to_ebitdar_ttm vs net_debt_to_ebitdar) are also indexed
        # under their bare formula_id so later formulas can reference them
        # generically via "derived:financial_debt" regardless of period kind.
        pools.derived_current[formula_id] = current.value
        pools.derived_current[output_id] = current.value
        pools.derived_comparison[formula_id] = comparison.value
        pools.derived_comparison[output_id] = comparison.value

        refs = _refs_from_inputs(formula["inputs"])
        primary_meta = _first_base_metadata(pools, refs)
        comparison_period = primary_meta.get("comparison_period") if primary_meta else None

        change, change_unit = _apply_change_policy(
            formula["change_policy"], current.value, comparison.value,
            current.components.get("percent_change_vs_prior") if current.components else None,
            comparison_compatible=pools.comparison_compatible,
        )

        catalog_entry = catalog_metadata.get(output_id, {})
        display_name = catalog_entry.get("display_name", {}).get("tr", output_id)

        metric: dict[str, Any] = {
            "metric_id": output_id,
            "name": display_name,
            "value": current.value,
            "unit": _output_unit(formula, context),
            "period": context.period_id,
            "comparison_value": comparison.value,
            "comparison_period": comparison_period,
            "change": change,
            "change_unit": change_unit,
            "data_type": "derived",
            "formula_id": formula_id,
            "formula_version": formula["version"],
            "formula_inputs": refs,
            "formula_description": formula["description"],
        }
        if current.status != "available":
            metric["status"] = current.status
            metric["reason"] = current.reason
        if current.components:
            metric["components"] = current.components

        by_category[formula["category"]].append(metric)

    result = {
        "schema_version": 1,
        "ticker": context.ticker,
        "period": context.period_id,
    }
    result.update({c: by_category[c] for c in CATEGORY_ORDER})
    return result
