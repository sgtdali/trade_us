"""Summary-section reference validation: every signal/risk a summary
references must actually exist, no summary may carry a weighted investment
score, and every status/completeness field must be exactly reproducible
from the registered section policy plus the generated signals/risks it
claims to summarize."""

from __future__ import annotations

from .result import ValidationFinding, ValidationResult

_PROHIBITED_KEYS = {"investment_score", "weighted_score", "total_score", "final_score"}
_REPRODUCIBLE_KEYS = (
    "status", "positive_signals", "negative_signals", "neutral_signals",
    "unavailable_signals", "missing_signals", "key_drivers", "key_risks",
    "completeness", "data_completeness", "investment_signal",
)


def validate_summaries(summaries_data: dict, known_signal_ids: set[str], known_risk_ids: set[str], file_label: str) -> ValidationResult:
    result = ValidationResult()
    for section_id, section in summaries_data.get("summaries", {}).items():
        for key in _PROHIBITED_KEYS:
            if key in section:
                result.add(ValidationFinding("prohibited_investment_score", "error", f"{section_id}: contains a prohibited weighted investment score field {key!r}.", file_label, section_id))
        if section.get("investment_signal") is not False:
            result.add(ValidationFinding("investment_signal_not_false", "error", f"{section_id}: investment_signal must be false.", file_label, section_id))

        referenced = (
            list(section.get("positive_signals", [])) + list(section.get("negative_signals", []))
            + list(section.get("neutral_signals", [])) + list(section.get("unavailable_signals", []))
        )
        if len(referenced) != len(set(referenced)):
            result.add(ValidationFinding("duplicate_signal_reference", "error", f"{section_id}: duplicate signal reference in its bucket lists.", file_label, section_id))
        for signal_id in referenced:
            if signal_id not in known_signal_ids and signal_id not in known_risk_ids:
                result.add(ValidationFinding("unknown_signal_or_risk_reference", "error", f"{section_id}: references unknown signal/risk id {signal_id!r}.", file_label, section_id))
    return result


def validate_reproducibility(committed: dict, expected: dict, file_label: str) -> ValidationResult:
    """Recompute the summaries contract from the same policy engine
    (:func:`fundamental_pipeline.summaries.engine.generate_summaries`) and
    diff every field against what is committed. A committed summary whose
    completeness, status, or bucket membership does not match what the
    registered policy would produce from the same signals/risks is a
    validation error, not a warning -- ``summaries.json`` is generated
    output and must never drift from its own generation logic."""
    result = ValidationResult()
    committed_sections = committed.get("summaries", {})
    expected_sections = expected.get("summaries", {})

    if committed.get("input_completeness") != expected.get("input_completeness"):
        result.add(ValidationFinding(
            "input_completeness_not_reproducible", "error",
            "Committed input_completeness does not match the value recomputed from normalized inputs.",
            file_label,
        ))

    missing_sections = set(expected_sections) - set(committed_sections)
    extra_sections = set(committed_sections) - set(expected_sections)
    if missing_sections:
        result.add(ValidationFinding("summary_section_missing", "error", f"Expected section(s) not present in committed summaries: {sorted(missing_sections)}.", file_label))
    if extra_sections:
        result.add(ValidationFinding("summary_section_unexpected", "error", f"Committed summaries contain section(s) the registered policy would not produce: {sorted(extra_sections)}.", file_label))

    for section_id, expected_section in expected_sections.items():
        committed_section = committed_sections.get(section_id)
        if committed_section is None:
            continue
        for key in _REPRODUCIBLE_KEYS:
            expected_value = expected_section.get(key)
            committed_value = committed_section.get(key)
            if committed_value != expected_value:
                result.add(ValidationFinding(
                    "summary_not_reproducible", "error",
                    f"{section_id}.{key}: committed value {committed_value!r} does not match the value "
                    f"recomputed from the registered policy and generated signals/risks: {expected_value!r}.",
                    file_label, f"{section_id}.{key}",
                ))
    return result
