"""Signal validation: definitions resolve, scores are consistent with
availability, and no signal ever claims to be an investment signal."""

from __future__ import annotations

from ..io import read_json
from ..paths import repo_path
from .result import ValidationFinding, ValidationResult

_VALID_VALUES = {"positive", "negative", "neutral", "mixed", "unavailable"}
_VALID_DIRECTIONS = {"improving", "deteriorating", "stable", "mixed", "unavailable"}
_VALID_ABSOLUTE_STATES = {"positive", "negative", "neutral", "unknown"}


def validate_signals(signals_data: dict, file_label: str) -> ValidationResult:
    result = ValidationResult()
    rules_config = read_json(repo_path("config/pipeline/signal-rules.json"))
    known_rule_ids = {r["rule_id"] for r in rules_config["rule_definitions"]}
    signal_definitions = {s["signal_id"]: s for s in rules_config["signals"]}
    known_signal_ids = set(signal_definitions)

    seen_ids: set[str] = set()
    for s in signals_data.get("signals", []):
        signal_id = s.get("signal_id")
        if signal_id in seen_ids:
            result.add(ValidationFinding("duplicate_signal_id", "error", f"Duplicate signal_id: {signal_id}", file_label))
        seen_ids.add(signal_id)

        if signal_id not in known_signal_ids:
            result.add(ValidationFinding("unregistered_signal_id", "error", f"{signal_id}: not a registered signal definition.", file_label, signal_id))
        if s.get("rule_id") not in known_rule_ids:
            result.add(ValidationFinding("unregistered_rule_id", "error", f"{signal_id}: rule_id {s.get('rule_id')!r} is not registered.", file_label, signal_id))
        if s.get("value") not in _VALID_VALUES:
            result.add(ValidationFinding("invalid_signal_value", "error", f"{signal_id}: value {s.get('value')!r} is not a supported vocabulary term.", file_label, signal_id))
        if s.get("investment_signal") is not False:
            result.add(ValidationFinding("investment_signal_not_false", "error", f"{signal_id}: investment_signal must be false.", file_label, signal_id))
        if s.get("value") == "unavailable" and s.get("score") is not None:
            result.add(ValidationFinding("unavailable_score_not_null", "error", f"{signal_id}: value is 'unavailable' but score is not null.", file_label, signal_id))
        if s.get("value") != "unavailable" and s.get("score") is None:
            result.add(ValidationFinding("available_score_is_null", "error", f"{signal_id}: value is {s.get('value')!r} but score is null.", file_label, signal_id))
        if not s.get("reason_code"):
            result.add(ValidationFinding("missing_reason_code", "warning", f"{signal_id}: no reason_code.", file_label, signal_id))
        context = s.get("context")
        requires_context = bool(signal_definitions.get(signal_id, {}).get("context_policy"))
        if signals_data.get("schema_version", 1) >= 2 and requires_context and not isinstance(context, dict):
            result.add(ValidationFinding("missing_signal_context", "error", f"{signal_id}: registered context policy produced no context block.", file_label, signal_id))
            continue
        if not isinstance(context, dict):
            continue
        if context.get("direction") not in _VALID_DIRECTIONS:
            result.add(ValidationFinding("invalid_signal_direction", "error", f"{signal_id}: invalid contextual direction.", file_label, signal_id))
        if context.get("absolute_state") not in _VALID_ABSOLUTE_STATES:
            result.add(ValidationFinding("invalid_absolute_state", "error", f"{signal_id}: invalid contextual absolute_state.", file_label, signal_id))
        if context.get("presentation_status") not in _VALID_VALUES:
            result.add(ValidationFinding("invalid_presentation_status", "error", f"{signal_id}: invalid contextual presentation_status.", file_label, signal_id))
        if s.get("value") == "unavailable" and context.get("presentation_status") != "unavailable":
            result.add(ValidationFinding("unavailable_context_mismatch", "error", f"{signal_id}: unavailable raw signal must remain unavailable in presentation.", file_label, signal_id))
    return result
