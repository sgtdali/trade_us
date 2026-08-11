"""Minimal contextual presentation layer for generated signals.

The evaluator's raw ``value`` and ``score`` are never changed here. This
module only decides how that raw direction may be presented when an
absolute level is still negative or a composite signal used incomplete
data. Policies remain declarative in ``signal-rules.json``.
"""

from __future__ import annotations

from collections.abc import Callable

from .evaluators import SignalEvaluation
from .reason_renderer import render


_DIRECTION_BY_VALUE = {
    "positive": "improving",
    "negative": "deteriorating",
    "neutral": "stable",
    "mixed": "mixed",
    "unavailable": "unavailable",
}


def _absolute_state(policy: dict, metric_value: Callable[[str], float | None]) -> str:
    ref = policy.get("absolute_ref")
    if not ref:
        return "unknown"
    value = metric_value(ref)
    if value is None:
        return "unknown"
    if value < policy.get("negative_below", 0.0):
        return "negative"
    if value > policy.get("positive_above", 0.0):
        return "positive"
    return "neutral"


def contextualize(
    definition: dict,
    result: SignalEvaluation,
    metric_value: Callable[[str], float | None],
    locale: str,
) -> dict:
    """Return presentation metadata without mutating the raw evaluation."""
    policy = definition.get("context_policy", {})
    required_params = policy.get("required_reason_params", [])
    required_data_complete = all(result.reason_params.get(name) is not None for name in required_params)
    absolute_state = _absolute_state(policy, metric_value)
    direction = _DIRECTION_BY_VALUE[result.value]
    presentation_status = result.value
    reason_code = "signal_context_raw_preserved"

    if result.value == "unavailable":
        reason_code = "signal_context_unavailable"
    elif result.value == "positive" and not required_data_complete:
        presentation_status = "mixed"
        reason_code = "signal_context_positive_limited_by_missing_data"
    elif result.value == "positive" and absolute_state == "negative":
        presentation_status = "mixed"
        reason_code = "signal_context_improving_but_negative"
    elif result.value == "negative" and not required_data_complete:
        reason_code = "signal_context_negative_preserved_with_missing_data"

    return {
        "direction": direction,
        "absolute_state": absolute_state,
        "presentation_status": presentation_status,
        "required_data_complete": required_data_complete,
        "reason_code": reason_code,
        "reason": render(locale, reason_code, {}),
    }
