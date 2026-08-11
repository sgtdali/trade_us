"""Orchestrates loading, rendering, validating, and checking valuation reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import ValuationError
from ..paths import resolve_governed_report_path, valuation_report_relative_path
from .context import build_report_context
from .loader import load_report_dependencies
from .renderer import render_valuation_report
from .validator import validate_report_content


class ValuationReportValidationError(ValuationError):
    """Raised when report generation or validation detects forbidden language or incomplete methods."""


def generate_valuation_report(
    ticker: str,
    as_of_date: str,
    context_id: str,
    latest_period: str,
    fy_period: str,
    *,
    output_dir: Path | None = None,
    root: Path | None = None,
) -> tuple[str, list[str]]:
    """Load dependencies, build context, render, and validate a report.
    If output_dir is specified and validation passes, writes the report to the governed path.
    If forbidden language or validation errors occur, raises ValuationReportValidationError (fails closed).
    """
    deps = load_report_dependencies(
        ticker=ticker,
        as_of_date=as_of_date,
        context_id=context_id,
        latest_period=latest_period,
        fy_period=fy_period,
        root=root,
    )

    context = build_report_context(deps, as_of_date)
    report_text = render_valuation_report(context)

    # Validate report content
    errors = validate_report_content(report_text, deps.current_results)
    if errors:
        raise ValuationReportValidationError(
            f"Raporda doğrulama hataları tespit edildi, yazım iptal edildi (Fail-Closed):\n" + "\n".join(errors)
        )

    # Write report if output_dir is provided and validation is successful
    if output_dir is not None:
        report_rel = valuation_report_relative_path(ticker, as_of_date)
        report_path = resolve_governed_report_path(output_dir, report_rel)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")

    return report_text, errors


def validate_valuation_report(
    ticker: str,
    as_of_date: str,
    context_id: str,
    latest_period: str,
    fy_period: str,
    report_text: str,
    *,
    root: Path | None = None,
) -> list[str]:
    """Validate a valuation report string against its corresponding results model."""
    deps = load_report_dependencies(
        ticker=ticker,
        as_of_date=as_of_date,
        context_id=context_id,
        latest_period=latest_period,
        fy_period=fy_period,
        root=root,
    )
    return validate_report_content(report_text, deps.current_results)


def check_valuation_report(
    ticker: str,
    as_of_date: str,
    context_id: str,
    latest_period: str,
    fy_period: str,
    output_dir: Path,
    *,
    root: Path | None = None,
) -> list[str]:
    """Check that a report exists under output_dir and matches the recompiled results byte-for-byte."""
    errors: list[str] = []

    report_rel = valuation_report_relative_path(ticker, as_of_date)
    report_path = output_dir / report_rel

    if not report_path.exists():
        errors.append(f"Valuation report is missing: {report_path}")
        return errors

    # Load and render fresh expected report text
    deps = load_report_dependencies(
        ticker=ticker,
        as_of_date=as_of_date,
        context_id=context_id,
        latest_period=latest_period,
        fy_period=fy_period,
        root=root,
    )
    context = build_report_context(deps, as_of_date)
    expected_text = render_valuation_report(context)

    # Read existing report bytes
    try:
        existing_text = report_path.read_text(encoding="utf-8")
    except Exception as exc:
        errors.append(f"Failed to read report file: {exc}")
        return errors

    # Check byte-for-byte match
    if existing_text != expected_text:
        errors.append(f"Report drift detected: {report_rel} has been modified or differs from expected recompiled output.")

    return errors
