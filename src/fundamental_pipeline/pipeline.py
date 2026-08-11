"""Orchestration layer: the reusable Python API behind every CLI command.

Each stage function takes an :class:`~fundamental_pipeline.context.AnalysisContext`
plus whatever upstream generated data it needs, and returns structured
output. No stage reads its own previously committed output as a source of
truth, no stage holds hidden global state, and nothing here is specific to
any one ticker or sector.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .context import AnalysisContext
from .derivation.engine import derive_financials
from .reports.context import build_report_context
from .reports.renderer import render_report as _render_report_markdown
from .signaling.engine import generate_signals
from .summaries.engine import generate_summaries as _generate_summaries
from .validation.engine import validate_full_analysis
from .validation.result import ValidationResult

__all__ = [
    "derive_financials", "generate_signals", "generate_summaries", "render_report",
    "validate_full_analysis", "GeneratedAnalysis", "run_pipeline",
]


def generate_summaries(context: AnalysisContext, derived_data: dict, signals_data: dict) -> dict:
    """Generate the summaries contract. ``derived_data`` is accepted for
    interface symmetry with the other stages (a company-type module could
    in principle want it for a future summary policy) but the current
    standard-corporate summary policies are driven entirely by signals and
    authored risks."""
    del derived_data
    return _generate_summaries(context, signals_data, context.authored_risks)


def render_report(context: AnalysisContext, derived_data: dict, signals_data: dict, summaries_data: dict) -> str:
    report_context = build_report_context(context, derived_data, signals_data, summaries_data)
    return _render_report_markdown(report_context)


@dataclass
class GeneratedAnalysis:
    derived: dict
    signals: dict
    summaries: dict
    report: str
    validation: ValidationResult = field(default_factory=ValidationResult)


def run_pipeline(context: AnalysisContext) -> GeneratedAnalysis:
    """Run the full stage chain: derive -> signals -> summaries -> report,
    then validate every generated artifact together with the inputs. Pure
    function over the given context; does not touch the filesystem."""
    derived = derive_financials(context)
    signals = generate_signals(context, derived)
    summaries = generate_summaries(context, derived, signals)
    report = render_report(context, derived, signals, summaries)
    validation = validate_full_analysis(context, {
        "derived": derived, "signals": signals, "summaries": summaries, "report": report,
    })
    return GeneratedAnalysis(derived=derived, signals=signals, summaries=summaries, report=report, validation=validation)
