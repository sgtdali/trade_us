"""Top-level validation orchestration: runs every layer and returns one
combined :class:`ValidationResult`."""

from __future__ import annotations

from pathlib import Path

from ..context import AnalysisContext
from ..registry.companies import load_company
from ..registry.company_types import assert_implemented, get_company_type
from ..registry.sector_modules import get_sector_module
from ..summaries.engine import generate_summaries as _regenerate_summaries
from . import accounting, formulas, paths, periods, provenance, risks, schema, signals, statements, summaries
from .reports import validate_report_markdown
from .result import ValidationFinding, ValidationResult


def validate_company_routing(ticker: str, allow_inactive: bool = False, data_root: Path | None = None) -> ValidationResult:
    result = ValidationResult()
    try:
        company = load_company(ticker, allow_inactive=allow_inactive, data_root=data_root)
    except Exception as e:
        result.add(ValidationFinding("company_config_error", "error", str(e)))
        return result
    company_type = company["pipeline"]["company_type"]
    sector_module = company["pipeline"]["sector_module"]
    try:
        get_company_type(company_type)
        get_sector_module(sector_module)
        assert_implemented(company_type)
    except Exception as e:
        result.add(ValidationFinding("routing_error", "error", str(e)))
    return result


def validate_inputs(context: AnalysisContext) -> ValidationResult:
    """Validate the authored/normalized inputs: company config, source
    manifest, direct financials, financial-operational data, risks."""
    result = ValidationResult()
    result.merge(validate_company_routing(context.ticker, data_root=context.data_root))
    result.merge(schema.validate_against_schema("company", context.company_config, f"config/companies/{context.ticker}.json"))

    if context.source_manifest is not None:
        result.merge(schema.validate_against_schema("source-manifest", context.source_manifest, f"data/source-manifests/{context.ticker}.json"))
    result.merge(provenance.validate_source_manifest(context.source_manifest, context.ticker, context.data_root))

    referenced_paths = [s["path"] for s in (context.source_manifest or {}).get("sources", [])]
    result.merge(paths.validate_ticker_and_paths(context.ticker, referenced_paths, context.data_root))

    direct_label = f"data/financial/{context.ticker}/{context.period_id}.json"
    if context.direct_financials is not None:
        result.merge(schema.validate_against_schema("financial-direct", context.direct_financials, direct_label))
        result.merge(periods.validate_period_fields(context.direct_financials, direct_label, context.ticker, context.period_id))
        result.merge(periods.validate_comparisons(context.direct_financials, direct_label))
        result.merge(accounting.validate_accounting_context(context.direct_financials, direct_label))
        result.merge(statements.validate_statements(context.direct_financials, direct_label))
        result.merge(provenance.validate_metric_provenance(context.direct_financials, context.source_manifest, direct_label))
    else:
        result.add(ValidationFinding("direct_financials_missing", "error", "No direct financial data for this period.", direct_label))

    finops_label = f"data/financial-operational/{context.ticker}/{context.period_id}.json"
    if context.financial_operational_data is not None:
        result.merge(schema.validate_against_schema("financial-operational", context.financial_operational_data, finops_label))
        result.merge(provenance.validate_financial_operational_provenance(context.financial_operational_data, context.source_manifest, finops_label))

    if context.historical_series is not None:
        series_label = f"data/financial-series/{context.ticker}/"
        result.merge(schema.validate_against_schema("financial-series", context.historical_series, series_label))
        result.merge(provenance.validate_series_provenance(context.historical_series, context.source_manifest, series_label))

    risks_label = f"data/risks/{context.ticker}/{context.period_id}.json"
    if context.authored_risks is not None:
        result.merge(schema.validate_against_schema("risks", context.authored_risks, risks_label))
        result.merge(risks.validate_risks(context.authored_risks, risks_label))
        result.merge(provenance.validate_risk_evidence_provenance(context.authored_risks, context.source_manifest, risks_label))

    return result


def validate_derived(context: AnalysisContext, derived_data: dict) -> ValidationResult:
    label = f"data/financial/{context.ticker}/{context.period_id}-derived-ratios.json"
    result = ValidationResult()
    result.merge(schema.validate_against_schema("financial-derived", derived_data, label))
    result.merge(formulas.validate_derived_output(derived_data, label))
    return result


def validate_signals(context: AnalysisContext, signals_data: dict) -> ValidationResult:
    label = f"data/signals/{context.ticker}/{context.period_id}.json"
    result = ValidationResult()
    result.merge(schema.validate_against_schema("signals", signals_data, label))
    result.merge(signals.validate_signals(signals_data, label))
    return result


def validate_summaries(context: AnalysisContext, summaries_data: dict, signals_data: dict) -> ValidationResult:
    label = f"data/summaries/{context.ticker}/{context.period_id}.json"
    result = ValidationResult()
    result.merge(schema.validate_against_schema("summaries", summaries_data, label))
    known_signal_ids = {s["signal_id"] for s in signals_data.get("signals", [])}
    known_risk_ids = {r["risk_id"] for r in (context.authored_risks or {}).get("risks", [])}
    result.merge(summaries.validate_summaries(summaries_data, known_signal_ids, known_risk_ids, label))
    expected = _regenerate_summaries(context, signals_data, context.authored_risks)
    result.merge(summaries.validate_reproducibility(summaries_data, expected, label))
    return result


def validate_report(context: AnalysisContext, markdown_text: str) -> ValidationResult:
    label = f"reports/{context.ticker}/{context.period_id}-fundamental-analysis.md"
    return validate_report_markdown(markdown_text, context.ticker, context.period_id, context.sector_module_id == "aviation", label)


def validate_full_analysis(context: AnalysisContext, generated_outputs: dict, require_outputs: bool = False) -> ValidationResult:
    """Validate every stage of a fully generated analysis.

    ``generated_outputs`` is expected to have keys 'derived', 'signals',
    'summaries', 'report' (markdown text); any of them may be absent
    (in-process generation, where a stage simply hasn't run yet) or
    explicitly ``None`` (loaded from disk via
    :func:`engine.generation.load_committed_outputs`, where
    the committed file does not exist).

    ``require_outputs=True`` additionally reports a missing/``None`` entry
    for any of the four keys as its own validation error -- this is what
    the CLI's full-mode ``validate`` command (the default, as opposed to
    ``--inputs-only``) uses, since a company past the onboarding stage is
    expected to have every generated output committed.
    """
    result = ValidationResult()
    result.merge(validate_inputs(context))

    derived = generated_outputs.get("derived")
    signals_data = generated_outputs.get("signals")
    summaries_data = generated_outputs.get("summaries")
    report_text = generated_outputs.get("report")

    if require_outputs:
        label = f"{context.ticker}/{context.period_id}"
        for key, value in (("derived", derived), ("signals", signals_data), ("summaries", summaries_data), ("report", report_text)):
            if value is None:
                result.add(ValidationFinding(
                    "committed_output_missing", "error",
                    f"Expected committed generated output {key!r} is missing for {label}. "
                    "This check only applies once outputs have been generated for this "
                    "period; pass require_outputs=False while onboarding a company before "
                    "any output has been generated.",
                    label,
                ))

    if derived is not None:
        result.merge(validate_derived(context, derived))
    if signals_data is not None:
        result.merge(validate_signals(context, signals_data))
    if summaries_data is not None and signals_data is not None:
        result.merge(validate_summaries(context, summaries_data, signals_data))
    if report_text is not None:
        result.merge(validate_report(context, report_text))
    return result
