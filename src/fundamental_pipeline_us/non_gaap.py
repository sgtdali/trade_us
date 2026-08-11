from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fundamental_pipeline.io import read_json, write_json_atomic

from .models import FilingRef, SecFact
from .xbrl import load_facts


def build_financial_operational_artifact(
    *, workspace: Path, ticker: str, period_id: str,
    period_start: str | None, period_end: str,
    filing_caches: tuple[tuple[FilingRef, Path], ...],
    fallback_source_id: str | None = None,
) -> dict[str, Any]:
    target_end = date.fromisoformat(period_end)
    target_days = (
        (target_end - date.fromisoformat(period_start)).days + 1
        if period_start else None
    )
    all_facts: list[tuple[FilingRef, Path, SecFact]] = []
    for filing, cache_dir in filing_caches:
        for document in sorted(cache_dir.glob("*.htm*")):
            try:
                facts = load_facts(document)
            except Exception:  # an exhibit need not be Inline XBRL
                continue
            all_facts.extend((filing, document, fact) for fact in facts)

    ebitda = _select_metric(
        all_facts, target_end=target_end, target_days=target_days,
        predicate=lambda concept: "ebitda" in concept and "margin" not in concept,
        instant=False,
    )
    net_debt = _select_metric(
        all_facts, target_end=target_end, target_days=None,
        predicate=lambda concept: "netdebt" in concept.replace("_", ""),
        instant=True,
    )
    selected = [item for item in (ebitda, net_debt) if item is not None]
    source_id = (
        f"sec-non-gaap-{selected[0][0].accession.lower()}"
        if selected else fallback_source_id
    )
    source_path = None
    if selected:
        source_path = f"raw/sec-filings/{ticker}/{selected[0][0].accession}-non-gaap.json"
        write_json_atomic(workspace / source_path, {
            "schema_version": 1,
            "ticker": ticker,
            "period": period_id,
            "selected_facts": [_fact_record(item) for item in selected],
        })
        _upsert_manifest_source(
            workspace, ticker, source_id, source_path, selected[0][0]
        )
    metrics = [
        _operational_metric(
            "ebitda_amount", "Issuer-Reported EBITDA", ebitda,
            source_id=source_id, source_path=source_path,
            unavailable_reason="issuer_reported_ebitda_not_found",
        ),
        _operational_metric(
            "net_debt_apm_amount", "Issuer-Reported Net Debt APM", net_debt,
            source_id=source_id, source_path=source_path,
            unavailable_reason="issuer_reported_net_debt_apm_not_found",
        ),
    ]
    artifact = {
        "schema_version": 1,
        "ticker": ticker,
        "period": period_id,
        "period_start": period_start,
        "period_end": period_end,
        "period_type": "annual",
        "currency": "USD",
        "default_source_id": source_id,
        "metrics": metrics,
    }
    path = workspace / "data" / "financial-operational" / ticker / f"{period_id}.json"
    write_json_atomic(path, artifact)
    return artifact


def _select_metric(
    facts: list[tuple[FilingRef, Path, SecFact]], *, target_end: date,
    target_days: int | None, predicate, instant: bool,
) -> tuple[FilingRef, Path, SecFact] | None:
    candidates: list[tuple[FilingRef, Path, SecFact]] = []
    for filing, document, fact in facts:
        concept = fact.concept.lower()
        if not predicate(concept) or fact.unit != "usd" or fact.is_nil:
            continue
        if abs((fact.end_date - target_end).days) > 10 or fact.is_instant != instant:
            continue
        if target_days is not None and fact.duration_days is not None and abs(fact.duration_days - target_days) > 20:
            continue
        if fact.dimensions:
            continue
        candidates.append((filing, document, fact))
    values = {_numeric(item[2]) for item in candidates}
    values.discard(None)
    if len(values) != 1:
        return None
    return sorted(candidates, key=lambda item: (item[0].filing_date, item[1].name), reverse=True)[0]


def _numeric(fact: SecFact) -> float | None:
    try:
        return float(fact.value)
    except (TypeError, ValueError):
        return None


def _operational_metric(
    metric_id: str, name: str, selected: tuple[FilingRef, Path, SecFact] | None,
    *, source_id: str | None, source_path: str | None, unavailable_reason: str,
) -> dict[str, Any]:
    if selected is None:
        return {
            "metric_id": metric_id, "name": name, "value": None,
            "unit": "million_usd", "data_type": "direct",
            "status": "unavailable", "reason": unavailable_reason,
            "notes": "No unique issuer-reported fact was found in accession-specific SEC 8-K exhibits.",
        }
    filing, document, fact = selected
    return {
        "metric_id": metric_id,
        "name": name,
        "value": _numeric(fact) / 1_000_000,
        "unit": "million_usd",
        "data_type": "direct",
        "status": "available",
        "context": {
            "period_scope": "fy" if not fact.is_instant else "instant",
            "ebitda_basis": "company_adjusted_apm" if metric_id == "ebitda_amount" else "issuer_reported_apm",
            "reconciliation_status": "reported_unreconciled",
            "comparability": "issuer_specific_only",
        },
        "notes": f"Issuer-reported SEC Inline XBRL fact {fact.qualified_name} from {document.name}; accession {filing.accession}.",
        "provenance": {"source_id": source_id, "source_file": source_path, "page": None},
    }


def _fact_record(item: tuple[FilingRef, Path, SecFact]) -> dict[str, Any]:
    filing, document, fact = item
    return {
        "accession": filing.accession, "filing_date": filing.filing_date.isoformat(),
        "document": document.name, "concept": fact.qualified_name,
        "value": fact.value, "unit": fact.unit, "context_id": fact.context_id,
        "start_date": fact.start_date.isoformat() if fact.start_date else None,
        "end_date": fact.end_date.isoformat(),
    }


def _upsert_manifest_source(
    workspace: Path, ticker: str, source_id: str, source_path: str, filing: FilingRef,
) -> None:
    manifest_path = workspace / "data" / "source-manifests" / f"{ticker}.json"
    manifest = read_json(manifest_path)
    source = {
        "source_id": source_id,
        "path": source_path,
        "source_type": "sec_filing_text",
        "language": "en",
        "publication_date": filing.filing_date.isoformat(),
        "periods_covered": [], "currency": "USD", "scale": "million",
        "consolidation": "consolidated", "audit_status": "unaudited",
        "accounting_basis": "US_GAAP", "is_primary": True,
        "sha256": __import__("hashlib").sha256((workspace / source_path).read_bytes()).hexdigest(),
        "notes": f"Issuer-reported non-GAAP facts from SEC accession {filing.accession}.",
    }
    manifest["sources"] = [item for item in manifest["sources"] if item.get("source_id") != source_id] + [source]
    manifest["sources"].sort(key=lambda item: (item.get("publication_date") or "", item["source_id"]))
    write_json_atomic(manifest_path, manifest)
