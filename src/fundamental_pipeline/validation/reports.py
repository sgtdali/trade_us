"""Report validation, wrapping :mod:`fundamental_pipeline.reports.validation`
as structured findings."""

from __future__ import annotations

from ..reports.validation import validate_report
from .result import ValidationFinding, ValidationResult


def validate_report_markdown(markdown_text: str, ticker: str, period: str, is_aviation: bool, file_label: str) -> ValidationResult:
    result = ValidationResult()
    for message in validate_report(markdown_text, ticker, period, is_aviation):
        result.add(ValidationFinding("report_validation_failed", "error", message, file_label))
    return result
