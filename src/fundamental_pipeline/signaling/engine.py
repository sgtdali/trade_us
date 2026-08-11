"""Signal generation: resolves ``config/pipeline/signal-rules.json`` against
an AnalysisContext and its already-derived ratios, dispatching to the
controlled evaluators in :mod:`fundamental_pipeline.signaling.evaluators`.
"""

from __future__ import annotations

from ..context import AnalysisContext
from ..errors import ConfigError
from ..io import read_json
from ..paths import repo_path
from . import evaluators as ev
from .contextualizer import contextualize
from .reason_renderer import render


def _load_signal_rules() -> dict:
    return read_json(repo_path("config/pipeline/signal-rules.json"))


class _SignalPools:
    def __init__(self, context: AnalysisContext, derived_data: dict):
        self.direct: dict[str, dict] = {}
        if context.direct_financials:
            for section in ("income_statement", "balance_sheet", "cash_flow_statement", "commitments"):
                for m in context.direct_financials.get(section, []):
                    self.direct[m["metric_id"]] = m
        self.finops: dict[str, dict] = {}
        if context.financial_operational_data:
            for m in context.financial_operational_data.get("metrics", []):
                self.finops[m["metric_id"]] = m
        self.derived: dict[str, dict] = {}
        for category in ("growth", "margins", "liquidity", "leverage", "returns", "cash_generation"):
            for m in derived_data.get(category, []):
                self.derived[m["metric_id"]] = m

    def metric(self, ref: str) -> dict | None:
        dataset, metric_id = ref.split(":", 1)
        return {"direct": self.direct, "finops": self.finops, "derived": self.derived}[dataset].get(metric_id)

    def value(self, ref: str) -> float | None:
        m = self.metric(ref)
        return m.get("value") if m else None

    def comparison_value(self, ref: str) -> float | None:
        m = self.metric(ref)
        return m.get("comparison_value") if m else None

    def growth(self, ref: str) -> float | None:
        m = self.metric(ref)
        if not m:
            return None
        if m.get("change_unit") == "percent" and m.get("change") is not None:
            return m["change"]
        current, previous = m.get("value"), m.get("comparison_value")
        if current is None or previous is None or previous == 0:
            return None
        result = ev.f.growth_pct(current, previous, rounding=1)
        return result.value if result.status == "available" else None


def _applicable(definition: dict, context: AnalysisContext) -> bool:
    return (
        context.company_type in definition.get("applicable_company_types", [])
        and context.sector_module_id in definition.get("applicable_sector_modules", [])
    )


def _dispatch(definition: dict, rule: dict, pools: _SignalPools, context: AnalysisContext) -> ev.SignalEvaluation:
    rule_id = definition["rule_id"]
    thresholds = rule.get("thresholds", {})

    if rule_id == "growth_or_transition_band":
        ref = definition["current_ref"]
        return ev.growth_or_transition_band(pools.value(ref), pools.comparison_value(ref), thresholds)

    if rule_id == "margin_change_band":
        m = pools.metric(definition["margin_ref"])
        change = m.get("change") if m and m.get("change_unit") == "percentage_point" else None
        return ev.margin_change_band(change, thresholds)

    if rule_id == "cost_direction":
        return ev.cost_direction(pools.growth(definition["current_ref"]))

    if rule_id == "dual_growth_confirmation":
        m = pools.metric(definition["current_ref"])
        reported = pools.growth(definition["current_ref"])
        constant_currency = None
        if m and m.get("constant_currency_value") is not None and m.get("constant_currency_change") is not None:
            constant_currency = m["constant_currency_change"]
        return ev.dual_growth_confirmation(reported, constant_currency)

    if rule_id == "cash_conversion_ratio_change":
        m = pools.metric(definition["ratio_ref"])
        current = m.get("value") if m else None
        comparison = m.get("comparison_value") if m else None
        return ev.cash_conversion_ratio_change(current, comparison, thresholds)

    if rule_id == "liquidity_composite":
        cr = pools.metric(definition["current_ratio_ref"])
        cash = pools.metric(definition["cash_ratio_ref"])
        return ev.liquidity_composite(
            cr.get("change") if cr else None,
            cash.get("change") if cash else None,
        )

    if rule_id == "leverage_composite":
        lm = pools.metric(definition["liability_ratio_ref"])
        nd = pools.metric(definition["net_debt_ratio_ref"])
        return ev.leverage_composite(
            lm.get("change") if lm else None,
            nd.get("change") if nd else None,
            thresholds,
        )

    if rule_id == "lease_burden_composite":
        return ev.lease_burden_composite(
            pools.growth(definition["lease_liability_ref"]),
            _abs_growth(pools, definition["lease_payments_ref"]),
            thresholds,
        )

    if rule_id == "deferred_revenue_composite":
        return ev.deferred_revenue_composite(
            pools.growth(definition["balance_ref"]),
            pools.growth(definition["cash_flow_ref"]),
        )

    raise ConfigError(f"Unknown signal rule_id: {rule_id!r}")


def _abs_growth(pools: _SignalPools, ref: str) -> float | None:
    m = pools.metric(ref)
    if not m:
        return None
    current, previous = m.get("value"), m.get("comparison_value")
    if current is None or previous is None:
        return None
    result = ev.f.growth_pct(abs(current), abs(previous), rounding=1)
    return result.value if result.status == "available" else None


def _evidence(definition: dict, pools: _SignalPools) -> dict:
    evidence = {}
    for key, value in definition.items():
        if not key.endswith("_ref"):
            continue
        m = pools.metric(value)
        if m is None:
            continue
        evidence[f"{key[:-4]}_value"] = m.get("value")
        evidence[f"{key[:-4]}_comparison_value"] = m.get("comparison_value")
        if m.get("constant_currency_value") is not None:
            evidence[f"{key[:-4]}_constant_currency_value"] = m["constant_currency_value"]
    return evidence


_SOURCE_DATASET_DIRS = {"direct": "financial", "finops": "financial-operational", "derived": "financial"}


def _source_data_path(definition: dict, context: AnalysisContext) -> str:
    dataset = definition["source_dataset"]
    directory = _SOURCE_DATASET_DIRS[dataset]
    suffix = "-derived-ratios" if dataset == "derived" else ""
    return f"data/{directory}/{context.ticker}/{context.period_id}{suffix}.json"


def generate_signals(context: AnalysisContext, derived_data: dict) -> dict:
    """Compute the full signal set for the given context from its direct,
    financial-operational, and derived data. Pure function: does not read
    or write any file."""
    pools = _SignalPools(context, derived_data)
    rules_config = _load_signal_rules()
    rule_by_id = {r["rule_id"]: r for r in rules_config["rule_definitions"]}

    signals = []
    for definition in rules_config["signals"]:
        if not _applicable(definition, context):
            continue
        rule = rule_by_id[definition["rule_id"]]
        result = _dispatch(definition, rule, pools, context)
        locale = context.company_config.get("reporting_locale", "tr-TR")
        reason_text = render(locale, result.reason_code, result.reason_params)
        signal = {
            "signal_id": definition["signal_id"],
            "rule_id": definition["rule_id"],
            "rule_version": definition["rule_version"],
            "sector_module": context.sector_module_id,
            "value": result.value,
            "score": result.score,
            "components": result.components,
            "evidence": _evidence(definition, pools),
            "reason_code": result.reason_code,
            "reason_params": result.reason_params,
            "reason": reason_text,
            "interpretation_scope": definition["interpretation_scope"],
            "investment_signal": False,
            "source_data": _source_data_path(definition, context),
        }
        if definition.get("context_policy"):
            signal["context"] = contextualize(definition, result, pools.value, locale)
        signals.append(signal)

    return {
        "schema_version": 2,
        "ticker": context.ticker,
        "period": context.period_id,
        "signals": signals,
    }
