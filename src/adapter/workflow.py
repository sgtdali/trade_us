from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from engine.context import build_context
from engine.generation import canonical_json, output_paths, write_bundle_transactional
from engine.io import read_json
from engine.pipeline import run_pipeline
from engine.validation.engine import validate_inputs

from .cache import cache_filing, cache_filing_html_documents, facts_document_paths
from .fact_cache import load_facts_for_documents
from .discovery import list_filings, resolve_cik
from .errors import UsPipelineError
from .normalize import (
    build_comparison_period_artifact,
    normalize_filing,
    write_normalized_filing,
)
from .qualitative import (
    build_and_write_debt_profile,
    build_and_write_risk_artifact,
    inherit_annual_risks,
)
from .sec_client import SecClient
from .market import direct_share_count_as_int, select_direct_outstanding_shares
from .non_gaap import build_financial_operational_artifact
from .valuation import run_us_valuation
from .xbrl import load_facts


def _bundle(paths: dict[str, Path], generated: Any,
            generate_report: bool) -> dict[Path, str]:
    """Bir donemin dort ciktisi -- rapor istege bagli.

    Rapor bir SUNUM katmani; canli akista onu okuyan yok, paket
    derived/signals/summaries'ten kuruluyor. Yine de run_pipeline icinde
    render edilip DOGRULANMAYA devam ediyor: rapor seviyesindeki kurallar
    gercek veri kusuru yakalayabiliyor, kaybetmeye degmez. Atlanan yalniz
    diske yazma.
    """
    bundle = {
        paths["derived"]: canonical_json(generated.derived),
        paths["signals"]: canonical_json(generated.signals),
        paths["summaries"]: canonical_json(generated.summaries),
    }
    if generate_report:
        bundle[paths["report"]] = generated.report
    return bundle


def run_company_workflow(
    *, client: SecClient, workspace: Path, ticker: str, as_of: date, cutoff_instant: str,
    historical_market_observation: dict[str, str] | None = None,
    historical_technical_input: dict[str, Any] | None = None,
    generate_report: bool = True,
    config_root: Path | None = None,
) -> dict[str, Any]:
    """`config_root` is a repo-root-like directory containing a `config/`
    subdirectory (matching `data_root`'s existing convention) that
    overrides where config is read from; defaults to `workspace` (the
    original, single-root behaviour) so plain CLI usage (workspace == repo
    root already) is unaffected. A run root that holds its own generated
    data but shares the real, always-current company registry passes
    `config_root=repo_root` explicitly."""
    config_root = config_root if config_root is not None else workspace
    company = read_json(config_root / "config" / "companies" / f"{ticker}.json")
    cik = resolve_cik(client, ticker)
    filings = list_filings(client, cik, as_of=as_of, forms=("10-K", "10-Q"))
    event_filings = list_filings(client, cik, as_of=as_of, forms=("8-K",))
    quarterly = next((filing for filing in filings if filing.form == "10-Q"), None)
    annual_filings = [filing for filing in filings if filing.form == "10-K"][:2]
    annual = annual_filings[0] if annual_filings else None
    if quarterly is None or annual is None:
        raise UsPipelineError(f"{ticker}: eligible 10-Q and 10-K are both required as of {as_of}")

    processed: list[dict[str, Any]] = []
    facts_by_accession = {}
    annual_risks: dict[str, Any] | None = None
    annual_note_details: dict[str, Any] | None = None
    filing_sequence = tuple(reversed(annual_filings)) + (quarterly,)
    for filing in filing_sequence:
        cache_dir = cache_filing(client, workspace, filing)
        facts = load_facts_for_documents(
            facts_document_paths(cache_dir, read_json(cache_dir / "cache-metadata.json")),
            workspace / "cache" / "facts",
        )
        facts_by_accession[filing.accession] = facts
        period_id, direct, evidence = normalize_filing(
            workspace=workspace, ticker=ticker, filing=filing, facts=facts,
            mapping_path=config_root / "config" / "sec" / "metric-map.json",
        )
        comparison_direct = build_comparison_period_artifact(direct, evidence)
        write_normalized_filing(
            workspace=workspace, ticker=ticker, period_id=period_id, filing=filing,
            direct=direct, evidence=evidence,
            cache_metadata=read_json(cache_dir / "cache-metadata.json"),
            comparison_direct=comparison_direct,
        )
        if comparison_direct is not None:
            comparison_period = comparison_direct["period"]
            comparison_validation = validate_inputs(
                build_context(ticker, comparison_period, data_root=workspace, config_root=config_root)
            )
            if not comparison_validation.ok:
                raise UsPipelineError(
                    f"{ticker} {comparison_period}: comparison-period validation failed: "
                    f"{comparison_validation.as_dict()}"
                )
            comparison_generated = run_pipeline(
                build_context(ticker, comparison_period, data_root=workspace, config_root=config_root)
            )
            if not comparison_generated.validation.ok:
                raise UsPipelineError(
                    f"{ticker} {comparison_period}: comparison-period analysis failed: "
                    f"{comparison_generated.validation.as_dict()}"
                )
            comparison_paths = output_paths(ticker, comparison_period, workspace)
            write_bundle_transactional(_bundle(
                comparison_paths, comparison_generated, generate_report))
        risks = build_and_write_risk_artifact(
            workspace=workspace, ticker=ticker, period_id=period_id, filing=filing,
            primary_document=cache_dir / filing.primary_document,
        )
        if filing.accession == annual.accession:
            annual_risks = risks
        elif risks.get("analysis_status") != "available" and annual_risks is not None:
            risks = inherit_annual_risks(
                workspace=workspace, ticker=ticker, latest_period=period_id,
                latest_filing=filing, annual_artifact=annual_risks,
            )
        debt_profile = build_and_write_debt_profile(
            workspace=workspace, ticker=ticker, period_id=period_id,
            direct=direct, filing=filing, facts=facts,
            inherited_note_details=annual_note_details,
        )
        if filing.accession == annual.accession:
            annual_note_details = {
                "source_documents": debt_profile["source_documents"],
                "maturity_profile": debt_profile["maturity_profile"],
                "currency_profile": debt_profile["currency_profile"],
                "weighted_average_rates": debt_profile["interest_profile"]["weighted_average_rates"],
            }
        validation = validate_inputs(build_context(ticker, period_id, data_root=workspace, config_root=config_root))
        if not validation.ok:
            raise UsPipelineError(f"{ticker} {period_id}: normalized financial validation failed: {validation.as_dict()}")
        generated = run_pipeline(build_context(ticker, period_id, data_root=workspace, config_root=config_root))
        if not generated.validation.ok:
            raise UsPipelineError(f"{ticker} {period_id}: analysis failed: {generated.validation.as_dict()}")
        paths = output_paths(ticker, period_id, workspace)
        write_bundle_transactional(_bundle(paths, generated, generate_report))
        processed.append({
            "period": period_id, "accession": filing.accession,
            "metric_count": sum(len(direct[name]) for name in ("income_statement", "balance_sheet", "cash_flow_statement")),
            "warnings": validation.as_dict()["warnings"],
        })

    fy_period = next(item["period"] for item in processed if item["accession"] == annual.accession)
    annual_direct = read_json(workspace / "data" / "financial" / ticker / f"{fy_period}.json")
    nearby_events = tuple(
        filing for filing in event_filings
        if abs((filing.filing_date - annual.filing_date).days) <= 14
    )[:3]
    event_caches: list[tuple[Any, Path]] = []
    for event_filing in nearby_events:
        try:
            event_caches.append((
                event_filing,
                cache_filing_html_documents(client, workspace, event_filing),
            ))
        except Exception:  # one unrelated/malformed 8-K must not block financial statements
            continue
    build_financial_operational_artifact(
        workspace=workspace,
        ticker=ticker,
        period_id=fy_period,
        period_start=annual_direct.get("period_start"),
        period_end=annual_direct["period_end"],
        filing_caches=tuple(event_caches),
        fallback_source_id=f"sec-{annual.accession.lower()}",
    )
    latest_filing = max((annual, quarterly), key=lambda filing: (filing.report_date, filing.filing_date))
    latest_period = next(item["period"] for item in processed if item["accession"] == latest_filing.accession)
    prior_interim_period = None
    if latest_period != fy_period:
        candidate = workspace / "data" / "financial" / ticker / f"{int(latest_period[:4]) - 1}{latest_period[4:]}.json"
        if candidate.exists():
            prior_interim_period = read_json(candidate)
    valuation = run_us_valuation(
        workspace=workspace, config_root=config_root, ticker=ticker, exchange=company["exchange"],
        as_of_date=as_of.isoformat(), cutoff_instant=cutoff_instant,
        accession=latest_filing.accession, facts=facts_by_accession[latest_filing.accession],
        latest_period=latest_period, fy_period=fy_period,
        latest_period_end=latest_filing.report_date, fy_period_end=annual.report_date,
        prior_interim_period=prior_interim_period,
        annual_share_counts=_annual_share_counts(annual_filings, facts_by_accession),
        company_type=company["pipeline"]["company_type"],
        sector_module=company["pipeline"]["sector_module"],
        historical_market_observation=historical_market_observation,
        filing_available_at=f"{latest_filing.filing_date.isoformat()}T23:59:59Z",
        historical_technical_input=historical_technical_input,
        generate_report=generate_report,
    )
    return {"ticker": ticker, "cik": cik, "periods": processed, "valuation": valuation}


def _annual_share_counts(
    annual_filings, facts_by_accession: dict[str, tuple]
) -> tuple[int | None, int | None]:
    counts: list[int | None] = []
    for filing in annual_filings[:2]:
        facts = facts_by_accession.get(filing.accession)
        if not facts:
            counts.append(None)
            continue
        try:
            selected = select_direct_outstanding_shares(facts, as_of=filing.filing_date)
            counts.append(direct_share_count_as_int(selected))
        except Exception:  # noqa: BLE001 -- missing cover fact makes one Piotroski component unavailable
            counts.append(None)
    while len(counts) < 2:
        counts.append(None)
    return counts[0], counts[1]
