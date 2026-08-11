"""Safely loads and validates all canonical JSON dependencies for valuation report rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..paths import (
    resolve_governed_path,
    valuation_inputs_relative_path,
    valuation_results_relative_path,
    market_snapshot_relative_path,
)
from ..safe_json import read_safe_json
from ..references import verify_artifact_reference
from .models import ReportDependencies
from ...paths import repo_path


def _load_fundamental_json(root: Path, *parts: str) -> dict[str, Any]:
    path = root.joinpath(*parts)
    if not path.exists():
        raise FileNotFoundError(f"Required fundamental analysis file not found: {path}")
    return read_safe_json(path)


#: Karsilastirma artifactlarinin filtre anahtarlari: yol -> (mtime, boyut,
#: as_of_date, subject ticker'lari). Ayni surecte ayni dosyayi tekrar tekrar
#: ayristirmamak icin vardir; secilen dosya kumesini degistirmez.
_COMPARISON_KEYS: dict[Path, tuple[float, int, str | None, frozenset[str]]] = {}

#: comparison_type klasoru -> (klasor mtime, dosya sayisi, as_of_date -> yollar).
#: Anahtarlari dosya basina onbelleklemek okumayi bitirdi ama taramayi
#: bitirmedi: her rapor yine 16.500 dosyayi glob'layip stat'liyordu (olculdu
#: 2026-08-05: sirket basina 0,9 sn). Bu ters indeks onu da kaldirir.
#:
#: Gecersizlestirme klasorun kendi mtime'ina dayanir. Bu, artifactlarin
#: `write_json_atomic` ile (gecici dosya + replace) yazildigi icin guvenlidir:
#: replace bir dizin girdisi islemidir, dolayisiyla hem yeni hem de yerinde
#: yeniden yazilan bir artifact klasor mtime'ini gunceller. Klasor
#: degismediginde tarama tamamen atlanir; degistiginde tum klasor yeniden
#: indekslenir ve dosya basina (mtime, boyut) kontrolu orada devreye girer.
_COMPARISON_DIR_INDEX: dict[Path, tuple[float, dict[str, list[Path]]]] = {}


def _comparison_paths_for(comp_type_dir: Path, as_of_date: str) -> list[Path]:
    """Bir comparison_type klasorunde verilen as_of_date'e ait yollar."""
    mtime = comp_type_dir.stat().st_mtime
    cached = _COMPARISON_DIR_INDEX.get(comp_type_dir)
    if cached is None or cached[0] != mtime:
        by_date: dict[str, list[Path]] = {}
        for path in sorted(comp_type_dir.glob("*.json")):
            candidate_as_of, _ = _comparison_keys(path)
            if candidate_as_of is not None:
                by_date.setdefault(candidate_as_of, []).append(path)
        _COMPARISON_DIR_INDEX[comp_type_dir] = (mtime, by_date)
    return _COMPARISON_DIR_INDEX[comp_type_dir][1].get(as_of_date, [])


def _comparison_keys(path: Path) -> tuple[str | None, frozenset[str]]:
    """(as_of_date, subject ticker'lari) -- dosya basina bir kez ayristirilir.

    Karsilastirma dosyalari icerik hash'iyle adlandirildigi icin hangi
    sirkete/tarihe ait olduklari ancak icerikleri okunarak anlasilabiliyor ve
    her rapor tum klasoru tariyordu. Bu klasor her olay gunu buyudugu icin
    maliyet gun sayisinin karesiyle artiyordu: olculdu (2026-08-05), 90 gunluk
    bir kosuda sirket basina 14.978 dosya okunuyor, bunun 14.949'u karsilastirma
    klasorlerinden geliyor ve rapor suresinin ~%62'sini yiyordu.

    Onbellek (mtime, boyut) ile gecersizlenir: uretici bir artifact'i yeniden
    yazarsa anahtarlar yeniden okunur. Esleme kurali degismedi -- eslesen
    dosyalar yine `read_safe_json` ile tam olarak ayristirilir.
    """
    stat = path.stat()
    cached = _COMPARISON_KEYS.get(path)
    if cached is not None and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return cached[2], cached[3]
    body = read_safe_json(path)
    as_of = body.get("temporal_context", {}).get("as_of_date")
    tickers = frozenset(
        ref.get("ticker") for ref in body.get("subject_refs", []) if ref.get("ticker")
    )
    _COMPARISON_KEYS[path] = (stat.st_mtime, stat.st_size, as_of, tickers)
    return as_of, tickers


def load_report_dependencies(
    ticker: str,
    as_of_date: str,
    context_id: str,
    latest_period: str,
    fy_period: str,
    *,
    root: Path | None = None,
) -> ReportDependencies:
    """Load and validate all JSON files needed to generate a report.
    Enforces exact cross-reference and content hash validation across all
    loaded valuation artifacts.
    """
    if root is None:
        root = repo_path()

    # 1. Company Config
    company_config = _load_fundamental_json(root, "config", "companies", f"{ticker}.json")

    # 2. Market Snapshot
    market_snapshot_rel = market_snapshot_relative_path(ticker, as_of_date)
    market_snapshot_path = resolve_governed_path(root, market_snapshot_rel)
    if not market_snapshot_path.exists():
        raise FileNotFoundError(f"Market snapshot not found: {market_snapshot_path}")
    market_snapshot = read_safe_json(market_snapshot_path)

    # 3. Valuation Inputs
    valuation_inputs_rel = valuation_inputs_relative_path(ticker, as_of_date, context_id)
    valuation_inputs_path = resolve_governed_path(root, valuation_inputs_rel)
    if not valuation_inputs_path.exists():
        raise FileNotFoundError(f"Valuation inputs not found: {valuation_inputs_path}")
    valuation_inputs = read_safe_json(valuation_inputs_path)

    # 4. Current Valuation Results
    current_results_rel = valuation_results_relative_path(ticker, as_of_date, context_id)
    current_results_path = resolve_governed_path(root, current_results_rel)
    if not current_results_path.exists():
        raise FileNotFoundError(f"Current results not found: {current_results_path}")
    current_results = read_safe_json(current_results_path)

    # Verify cross-references:
    verify_artifact_reference(
        valuation_inputs.get("market_snapshot_ref", {}),
        market_snapshot,
        market_snapshot_rel,
        root=root,
    )
    verify_artifact_reference(
        current_results.get("valuation_input_ref", {}),
        valuation_inputs,
        valuation_inputs_rel,
        root=root,
    )

    # Load fundamental data for latest_period
    latest_financials = _load_fundamental_json(root, "data", "financial", ticker, f"{latest_period}.json")
    latest_derived = _load_fundamental_json(root, "data", "financial", ticker, f"{latest_period}-derived-ratios.json")
    latest_signals = _load_fundamental_json(root, "data", "signals", ticker, f"{latest_period}.json")
    latest_summaries = _load_fundamental_json(root, "data", "summaries", ticker, f"{latest_period}.json")
    latest_risks = _load_fundamental_json(root, "data", "risks", ticker, f"{latest_period}.json")

    # Load fundamental data for fy_period
    fy_financials = _load_fundamental_json(root, "data", "financial", ticker, f"{fy_period}.json")
    fy_derived = _load_fundamental_json(root, "data", "financial", ticker, f"{fy_period}-derived-ratios.json")
    fy_signals = _load_fundamental_json(root, "data", "signals", ticker, f"{fy_period}.json")
    fy_summaries = _load_fundamental_json(root, "data", "summaries", ticker, f"{fy_period}.json")
    fy_risks = _load_fundamental_json(root, "data", "risks", ticker, f"{fy_period}.json")

    # Optional Downstream Assets:
    # Comparison (try standard comparison types). Comparison/diagnostic
    # artifacts key their filename on comparison_type + their own
    # independently-derived context_id (T74-B: dimensions are ticker(s) +
    # as_of_date + purpose + diagnostic/comparison-specific facts, never the
    # valuation-inputs context_id) -- so lookup cannot reuse `context_id`
    # the way market_snapshot/valuation_inputs do. Instead scan each
    # comparison_type directory and match on subject ticker + as_of_date.
    comparisons: list[dict[str, Any]] = []
    comparison_root = root / "data" / "valuation-comparison"
    for comp_type in ("historical_self", "sector_peer", "piotroski_diagnostic", "magic_formula_diagnostic", "peer_groups"):
        comp_type_dir = comparison_root / comp_type
        if not comp_type_dir.is_dir():
            continue
        for comp_path in _comparison_paths_for(comp_type_dir, as_of_date):
            _, subject_tickers = _comparison_keys(comp_path)
            if ticker not in subject_tickers:
                continue
            comparisons.append(read_safe_json(comp_path))

    # 8. Human Decision
    human_decision = None
    decision_candidates = [
        root / "config" / "decisions" / f"{ticker}-{as_of_date}.json",
        root / "data" / "decisions" / f"{ticker}-{as_of_date}.json",
    ]
    for cand in decision_candidates:
        if cand.exists():
            human_decision = read_safe_json(cand)
            break

    # 9. All-period cash flow trend (best-effort, 2026-07-22 SNA trend
    # disclosure). Scans every committed data/financial/{ticker}/{PERIOD}.json
    # (never the -derived-ratios sibling), never fails the report if a
    # sibling period is missing/unreadable -- this is a supplementary
    # trend table, not a required dependency.
    all_period_cash_flows: list[dict[str, Any]] = []
    financial_dir = root / "data" / "financial" / ticker
    if financial_dir.is_dir():
        for period_path in sorted(financial_dir.glob("*.json")):
            if period_path.stem.endswith("-derived-ratios"):
                continue
            period_doc = read_safe_json(period_path)
            cf_by_id = {m["metric_id"]: m for m in period_doc.get("cash_flow_statement", [])}
            income_by_id = {m["metric_id"]: m for m in period_doc.get("income_statement", [])}
            all_period_cash_flows.append({
                "period": period_doc.get("period"),
                "period_end": period_doc.get("period_end"),
                "cfo": cf_by_id.get("cf_net_operating_activities"),
                "capex": cf_by_id.get("cf_capex_ppe_intangible"),
                "revenue": income_by_id.get("revenue_total"),
            })
    all_period_cash_flows.sort(key=lambda p: p.get("period_end") or "")

    # 10. Technical Analysis Snapshot (optional entry-timing indicators)
    technical = None
    technical_path = root / "data" / "technical" / ticker / f"{as_of_date}.json"
    if technical_path.exists():
        technical = read_safe_json(technical_path)

    # 11. Structured debt profiles. Optional for backward compatibility with
    # historical report artifacts; the production run.py chain treats both
    # latest and FY profiles as mandatory before generating a new report.
    latest_debt_profile = None
    latest_debt_path = root / "data" / "debt-profile" / ticker / f"{latest_period}.json"
    if latest_debt_path.exists():
        latest_debt_profile = read_safe_json(latest_debt_path)
    fy_debt_profile = None
    fy_debt_path = root / "data" / "debt-profile" / ticker / f"{fy_period}.json"
    if fy_debt_path.exists():
        fy_debt_profile = read_safe_json(fy_debt_path)

    return ReportDependencies(
        company_config=company_config,
        market_snapshot=market_snapshot,
        valuation_inputs=valuation_inputs,
        current_results=current_results,
        latest_financials=latest_financials,
        latest_derived=latest_derived,
        latest_signals=latest_signals,
        latest_summaries=latest_summaries,
        latest_risks=latest_risks,
        fy_financials=fy_financials,
        fy_derived=fy_derived,
        fy_signals=fy_signals,
        fy_summaries=fy_summaries,
        fy_risks=fy_risks,
        comparisons=tuple(comparisons),
        human_decision=human_decision,
        all_period_cash_flows=tuple(all_period_cash_flows),
        technical=technical,
        latest_debt_profile=latest_debt_profile,
        fy_debt_profile=fy_debt_profile,
    )
