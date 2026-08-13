from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from engine.public.financial_basis import FinancialPeriodRef
from engine.valuation.basis.service import generate_valuation_inputs
from engine.valuation.catalogs import load_catalog_registry
from engine.valuation.identity import derive_context_id
from engine.valuation.paths import valuation_inputs_relative_path, valuation_results_relative_path
from engine.valuation.results.service import CompanyContext, generate_current_results
from engine.technical.service import generate_technical_snapshot

from .errors import UsPipelineError
from .market import generate_us_market_snapshot, valuation_context_projection
from .models import SecFact
from .reporting import generate_us_valuation_report


def run_us_valuation(
    *, workspace: Path, ticker: str, exchange: str, as_of_date: str, cutoff_instant: str,
    accession: str, facts: tuple[SecFact, ...], latest_period: str, fy_period: str,
    latest_period_end: date, fy_period_end: date, company_type: str, sector_module: str,
    prior_interim_period: dict[str, Any] | None = None,
    historical_market_observation: dict[str, str] | None = None,
    filing_available_at: str | None = None,
    historical_technical_input: dict[str, Any] | None = None,
    generate_report: bool = True,
    config_root: Path | None = None,
) -> dict[str, Any]:
    registry = load_catalog_registry()
    context_periods = tuple(dict.fromkeys((latest_period, fy_period)))
    context_projection = valuation_context_projection(
        ticker, as_of_date, cutoff_instant, context_periods
    )
    market_path = generate_us_market_snapshot(
        workspace=workspace, ticker=ticker, exchange=exchange, as_of_date=as_of_date,
        cutoff_instant=cutoff_instant, accession=accession, facts=facts, catalog_registry=registry,
        context_projection=context_projection,
        historical_observation=historical_market_observation,
        filing_available_at=filing_available_at,
    )
    period_refs = [
        FinancialPeriodRef(
            latest_period, latest_period_end, "annual" if latest_period == fy_period else "quarterly"
        )
    ]
    if fy_period != latest_period:
        period_refs.append(FinancialPeriodRef(fy_period, fy_period_end, "annual"))
    if prior_interim_period is not None:
        period_refs.append(
            FinancialPeriodRef(
                prior_interim_period["period"],
                date.fromisoformat(prior_interim_period["period_end"]),
                "quarterly",
            )
        )
    inputs_result = generate_valuation_inputs(
        data_root=workspace, ticker=ticker, as_of_date=as_of_date, cutoff_instant=cutoff_instant,
        financial_period_refs=tuple(period_refs), market_snapshot_path=market_path,
        context_projection=context_projection, catalog_registry=registry, output_dir=workspace,
        config_root=config_root,
    )
    if not inputs_result.ok or inputs_result.valuation_inputs is None:
        raise UsPipelineError(_finding_message("valuation inputs", inputs_result.findings))
    context_id = derive_context_id(context_projection)
    inputs_path = workspace / valuation_inputs_relative_path(ticker, as_of_date, context_id)
    results_result = generate_current_results(
        valuation_inputs_path=inputs_path,
        company_context=CompanyContext(ticker=ticker, company_type=company_type, sector_module=sector_module),
        method_set_id=None, engine_version="1.0.0", catalog_registry=registry, output_dir=workspace,
    )
    if not results_result.ok or results_result.artifact is None:
        raise UsPipelineError(_finding_message("valuation results", results_result.findings))
    _, technical_findings = generate_technical_snapshot(
        ticker=ticker,
        as_of_date=as_of_date,
        generated_at=cutoff_instant,
        engine_version="1.0.0",
        output_dir=workspace / "data" / "technical",
        root=workspace,
        daily_bars_override=(
            historical_technical_input["daily_bars"]
            if historical_technical_input is not None else None
        ),
        provider_symbol_override=ticker if historical_technical_input is not None else None,
        corporate_action_dates_override=(
            historical_technical_input["corporate_action_dates"]
            if historical_technical_input is not None else None
        ),
    )
    if any(finding.severity in ("blocker", "error") for finding in technical_findings):
        raise UsPipelineError(_finding_message("technical snapshot", technical_findings))
    # Rapor bir SUNUM katmani. Canli akista kimse okumuyor -- paket artik
    # dogrudan artifact'lerden kuruluyor (live_pack.py) -- ve uretimi hem
    # sureyi hem kirilganligi getiriyor. Varsayilan ACIK birakildi ki
    # backtest'ler ve mevcut cagrilar aynen calissin.
    report_text = ""
    if generate_report:
        report_text, errors = generate_us_valuation_report(
            ticker, as_of_date, context_id, latest_period, fy_period,
            workspace=workspace, config_root=config_root,
        )
        if errors:
            raise UsPipelineError(f"valuation report validation failed: {'; '.join(errors)}")
    return {
        "context_id": context_id,
        "market_snapshot": str(market_path),
        "valuation_inputs": str(inputs_path),
        "valuation_results": str(workspace / valuation_results_relative_path(ticker, as_of_date, context_id)),
        "valuation_report": (
            str(workspace / "reports" / "valuation" / ticker / f"{as_of_date}-valuation-analysis.md")
            if generate_report else None),
        "report_bytes": len(report_text.encode("utf-8")) if generate_report else 0,
    }


def _finding_message(stage: str, findings) -> str:
    detail = "; ".join(f"{finding.rule_id}: {finding.message}" for finding in findings)
    return f"{stage} generation failed: {detail}"
