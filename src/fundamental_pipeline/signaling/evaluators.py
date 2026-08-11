"""Controlled signal evaluators.

Each evaluator is a plain Python function selected by ``rule_id`` from
``config/pipeline/signal-rules.json``; there is no expression evaluation or
arbitrary code execution here. Every evaluator returns a
:class:`SignalEvaluation` with a machine-readable ``reason_code`` and
``reason_params`` — the actual localized sentence is built separately by
:mod:`fundamental_pipeline.signaling.reason_renderer`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..derivation import formulas as f


@dataclass
class SignalEvaluation:
    value: str  # "positive" | "negative" | "neutral" | "mixed" | "unavailable"
    score: int | None
    reason_code: str
    reason_params: dict = field(default_factory=dict)
    components: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)


def growth_or_transition_band(current: float | None, previous: float | None, thresholds: dict) -> SignalEvaluation:
    if current is None or previous is None:
        return SignalEvaluation("unavailable", None, "growth_unavailable", {})

    transition = f.transition_kind(current, previous)
    if transition == "loss_to_profit":
        return SignalEvaluation("positive", 2, "loss_to_profit", {"current": current, "previous": previous})
    if transition == "profit_to_loss":
        return SignalEvaluation("negative", -2, "profit_to_loss", {"current": current, "previous": previous})
    if transition in ("loss_narrowing", "loss_narrowing_minor"):
        pct = float((abs(f._d(previous)) - abs(f._d(current))) / abs(f._d(previous)) * 100)
        if transition == "loss_narrowing":
            return SignalEvaluation("mixed", 1, "loss_narrowing", {"narrowed_pct": round(pct, 1), "current": current, "previous": previous})
        return SignalEvaluation("negative", -1, "loss_narrowing_minor", {"narrowed_pct": round(pct, 1), "current": current, "previous": previous})
    if transition == "loss_widening":
        return SignalEvaluation("negative", -2, "loss_widening", {"current": current, "previous": previous})

    result = f.growth_pct(current, previous, rounding=1)
    if result.status != "available":
        return SignalEvaluation("unavailable", None, "growth_unavailable", {"reason": result.reason})
    pct = result.value
    if pct >= thresholds["positive_pct"]:
        return SignalEvaluation("positive", 2, "growth_positive", {"growth_pct": pct})
    if pct <= thresholds["negative_pct"]:
        return SignalEvaluation("negative", -2, "growth_negative", {"growth_pct": pct})
    return SignalEvaluation("neutral", 0, "growth_neutral", {"growth_pct": pct})


def margin_change_band(margin_change_pp: float | None, thresholds: dict) -> SignalEvaluation:
    if margin_change_pp is None:
        return SignalEvaluation("unavailable", None, "margin_unavailable", {})
    if margin_change_pp >= thresholds["positive_pp"]:
        return SignalEvaluation("positive", 1, "margin_positive", {"change_pp": margin_change_pp})
    if margin_change_pp <= thresholds["negative_pp"]:
        return SignalEvaluation("negative", -1, "margin_negative", {"change_pp": margin_change_pp})
    return SignalEvaluation("neutral", 0, "margin_neutral", {"change_pp": margin_change_pp})


def cost_direction(growth_pct: float | None) -> SignalEvaluation:
    if growth_pct is None:
        return SignalEvaluation("unavailable", None, "cost_unavailable", {})
    if growth_pct > 0:
        return SignalEvaluation("negative", -1, "cost_rising", {"growth_pct": growth_pct})
    if growth_pct < 0:
        return SignalEvaluation("positive", 1, "cost_declining", {"growth_pct": growth_pct})
    return SignalEvaluation("neutral", 0, "cost_flat", {"growth_pct": growth_pct})


def dual_growth_confirmation(reported_growth: float | None, constant_currency_growth: float | None) -> SignalEvaluation:
    if reported_growth is None:
        return SignalEvaluation("unavailable", None, "dual_growth_unavailable", {})
    if constant_currency_growth is None:
        if reported_growth > 0:
            return SignalEvaluation("mixed", 1, "dual_growth_reported_only_positive", {"reported_growth_pct": reported_growth})
        if reported_growth < 0:
            return SignalEvaluation("mixed", -1, "dual_growth_reported_only_negative", {"reported_growth_pct": reported_growth})
        return SignalEvaluation("neutral", 0, "dual_growth_reported_only_flat", {"reported_growth_pct": reported_growth})
    if reported_growth > 0 and constant_currency_growth > 0:
        return SignalEvaluation("positive", 2, "dual_growth_confirmed_positive", {"reported_growth_pct": reported_growth, "constant_currency_growth_pct": constant_currency_growth})
    if reported_growth < 0 and constant_currency_growth < 0:
        return SignalEvaluation("negative", -2, "dual_growth_confirmed_negative", {"reported_growth_pct": reported_growth, "constant_currency_growth_pct": constant_currency_growth})
    return SignalEvaluation("mixed", 0, "dual_growth_disagreement", {"reported_growth_pct": reported_growth, "constant_currency_growth_pct": constant_currency_growth})


def cash_conversion_ratio_change(current_ratio: float | None, comparison_ratio: float | None, thresholds: dict) -> SignalEvaluation:
    if current_ratio is None:
        return SignalEvaluation("unavailable", None, "cash_conversion_unavailable", {})
    if comparison_ratio is None:
        return SignalEvaluation("unavailable", None, "cash_conversion_no_comparison", {"current_ratio": current_ratio})
    change = float(f._d(current_ratio) - f._d(comparison_ratio))
    if change >= thresholds["positive"]:
        return SignalEvaluation("positive", 1, "cash_conversion_improved", {"change": round(change, 2)})
    if change <= thresholds["negative"]:
        return SignalEvaluation("negative", -1, "cash_conversion_deteriorated", {"change": round(change, 2)})
    return SignalEvaluation("neutral", 0, "cash_conversion_flat", {"change": round(change, 2)})


def liquidity_composite(current_ratio_change: float | None, cash_ratio_change: float | None) -> SignalEvaluation:
    if current_ratio_change is None or cash_ratio_change is None:
        return SignalEvaluation("unavailable", None, "liquidity_unavailable", {})
    same_direction = (current_ratio_change > 0 and cash_ratio_change > 0) or (current_ratio_change < 0 and cash_ratio_change < 0)
    if not same_direction:
        return SignalEvaluation("mixed", 0, "liquidity_mixed", {"current_ratio_change": current_ratio_change, "cash_ratio_change": cash_ratio_change})
    score = 1 if current_ratio_change > 0 else -1
    return SignalEvaluation("positive" if score > 0 else "negative", score, "liquidity_directional", {"current_ratio_change": current_ratio_change, "cash_ratio_change": cash_ratio_change})


def leverage_composite(liability_ratio_change: float | None, net_debt_ratio_change: float | None, thresholds: dict) -> SignalEvaluation:
    available = [c for c in (liability_ratio_change, net_debt_ratio_change) if c is not None]
    if not available:
        return SignalEvaluation("unavailable", None, "leverage_unavailable", {})
    if liability_ratio_change is not None and net_debt_ratio_change is not None:
        same_direction = (liability_ratio_change > 0 and net_debt_ratio_change > 0) or (liability_ratio_change < 0 and net_debt_ratio_change < 0)
        if not same_direction:
            return SignalEvaluation("mixed", 0, "leverage_mixed", {"liability_ratio_change": liability_ratio_change, "net_debt_ratio_change": net_debt_ratio_change})
        magnitude = (abs(liability_ratio_change) + abs(net_debt_ratio_change)) / 2
        direction = liability_ratio_change
    else:
        magnitude = abs(available[0])
        direction = available[0]
    if magnitude < thresholds["small"]:
        return SignalEvaluation("neutral", 0, "leverage_flat", {"magnitude": round(magnitude, 3)})
    grade = 1 if magnitude < thresholds["large"] else 2
    score = -grade if direction > 0 else grade
    return SignalEvaluation(
        "negative" if score < 0 else "positive",
        score,
        "leverage_directional",
        {
            "magnitude": round(magnitude, 3),
            "increasing": direction > 0,
            "liability_ratio_change": liability_ratio_change,
            "net_debt_ratio_change": net_debt_ratio_change,
        },
    )


def lease_burden_composite(lease_liability_growth_pct: float | None, lease_payments_growth_pct: float | None, thresholds: dict) -> SignalEvaluation:
    if lease_liability_growth_pct is None and lease_payments_growth_pct is None:
        return SignalEvaluation("unavailable", None, "lease_burden_unavailable", {})
    values = [v for v in (lease_liability_growth_pct, lease_payments_growth_pct) if v is not None]
    average = sum(values) / len(values)
    grade = 1 if abs(average) < thresholds["large_pct"] else 2
    score = -grade if average > 0 else (grade if average < 0 else 0)
    value = "negative" if score < 0 else ("positive" if score > 0 else "neutral")
    return SignalEvaluation(value, score, "lease_burden_directional", {
        "lease_liability_growth_pct": lease_liability_growth_pct,
        "lease_payments_growth_pct": lease_payments_growth_pct,
    })


def deferred_revenue_composite(balance_growth_pct: float | None, cash_flow_growth_pct: float | None) -> SignalEvaluation:
    if balance_growth_pct is None or cash_flow_growth_pct is None:
        return SignalEvaluation("unavailable", None, "deferred_revenue_unavailable", {})
    if balance_growth_pct > 0 and cash_flow_growth_pct > 0:
        return SignalEvaluation("positive", 1, "deferred_revenue_growing", {"balance_growth_pct": balance_growth_pct, "cash_flow_growth_pct": cash_flow_growth_pct})
    if balance_growth_pct < 0 and cash_flow_growth_pct < 0:
        return SignalEvaluation("negative", -1, "deferred_revenue_shrinking", {"balance_growth_pct": balance_growth_pct, "cash_flow_growth_pct": cash_flow_growth_pct})
    return SignalEvaluation("neutral", 0, "deferred_revenue_mixed", {"balance_growth_pct": balance_growth_pct, "cash_flow_growth_pct": cash_flow_growth_pct})
