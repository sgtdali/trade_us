"""Period-label and comparison-compatibility validation."""

from __future__ import annotations

from ..errors import PeriodError
from ..periods import compatible_comparison, parse_period
from .result import ValidationFinding, ValidationResult


def validate_period_fields(data: dict, file_label: str, expected_ticker: str, expected_period: str) -> ValidationResult:
    result = ValidationResult()
    if data.get("ticker") != expected_ticker:
        result.add(ValidationFinding("ticker_mismatch", "error", f"ticker field {data.get('ticker')!r} != expected {expected_ticker!r}", file_label))
    if data.get("period") != expected_period:
        result.add(ValidationFinding("period_mismatch", "error", f"period field {data.get('period')!r} != expected {expected_period!r}", file_label))
    try:
        parse_period(expected_period)
    except PeriodError as e:
        result.add(ValidationFinding("invalid_period_id", "error", str(e), file_label))
    return result


def validate_comparisons(direct_financials: dict, file_label: str) -> ValidationResult:
    """Warn when a metric's declared comparison_period is not a
    duration/cumulative-compatible period for a duration-type statement
    (income statement / cash flow), since those must not be compared across
    incompatible durations."""
    result = ValidationResult()
    current_period = direct_financials.get("period")
    if not current_period:
        return result
    for section in ("income_statement", "cash_flow_statement"):
        for m in direct_financials.get(section, []):
            comparison_period = m.get("comparison_period")
            if not comparison_period:
                continue
            try:
                if not compatible_comparison(current_period, comparison_period):
                    result.add(ValidationFinding(
                        "incompatible_comparison_period", "warning",
                        f"{m['metric_id']}: comparison_period {comparison_period!r} is not duration-compatible with {current_period!r} "
                        "(balance-sheet-style point-in-time comparisons are expected to differ; duration metrics should not)",
                        file_label, m["metric_id"],
                    ))
            except PeriodError:
                result.add(ValidationFinding("invalid_comparison_period", "warning", f"{m['metric_id']}: comparison_period {comparison_period!r} is not a valid period id", file_label, m["metric_id"]))
    return result
