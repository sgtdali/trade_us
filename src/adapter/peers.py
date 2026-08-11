from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.io import read_json, write_json_atomic
from engine.valuation.catalog_runtime import load_comparison_catalog_registry
from engine.valuation.comparison.build_peer_observations import build_observations
from engine.valuation.comparison.service import generate_peer_comparison

from .errors import UsPipelineError
from .reporting import generate_us_valuation_report


_REPO_ROOT = Path(__file__).resolve().parents[2]


def generate_us_peer_comparisons(
    *, workspace: Path, tickers: list[str], as_of_date: str, generated_at: str,
    generate_report: bool = True,
) -> dict[str, int]:
    universe_root = workspace / "config" / "valuation" / "comparison" / "peer-universes"
    universe_paths = sorted(universe_root.glob("*.json"))
    if not universe_paths:
        raise UsPipelineError(f"no peer universe is defined under {universe_root}")
    registry = load_comparison_catalog_registry(repo_root=_REPO_ROOT)
    generated_count = 0

    # Emsal karsilastirmasi sektor-goreldir: bir sirket kendi sektorunun
    # medyaniyla kiyaslanir, evrenin tamamiyla degil. Cok sektorlu bir evrende
    # tek dosyaya sabitlemek NVDA'yi KO ile ayni dagilima sokardi ve carpan
    # seviyeleri sektorler arasinda yapisal olarak farkli oldugu icin yuzdelik
    # anlamsiz cikardi. Bu yuzden her evren kendi uyeleri icinde islenir.
    for universe_path in universe_paths:
        universe = read_json(universe_path)
        universe_id = universe["universe_id"]
        members = {str(member["ticker"]).upper() for member in universe.get("members", [])}
        subjects = [ticker for ticker in tickers if ticker in members]
        if not subjects:
            continue

        for method_id in universe["method_family_ids"]:
            observations = build_observations(
                universe_path, method_id, as_of_date,
                root=workspace, currency="USD", accounting_basis="US_GAAP",
            )
            safe_method = method_id.replace("val.method.", "").replace(".", "_")
            observations_path = (
                workspace / "data" / "peer-observations" / universe_id / f"{safe_method}.json"
            )
            write_json_atomic(observations_path, observations)
            by_ticker = {item["ticker"]: item for item in observations["observations"]}

            for ticker in subjects:
                subject = by_ticker.get(ticker)
                if not subject or subject.get("status") != "available":
                    continue
                result = generate_peer_comparison(
                    subject_result_path=_single_result_path(workspace, ticker, as_of_date),
                    universe_path=universe_path,
                    observations_path=observations_path,
                    subject_ticker=ticker,
                    subject_value=str(subject["value"]["value"]),
                    method_family_id=method_id,
                    as_of_date=as_of_date,
                    generated_at=generated_at,
                    engine_version="1.0.0",
                    comparison_registry=registry,
                    output_dir=workspace,
                )
                if not result.ok:
                    details = "; ".join(
                        f"{finding.rule_id}: {finding.message}" for finding in result.findings
                    )
                    raise UsPipelineError(
                        f"{ticker} {method_id} peer comparison failed: {details}"
                    )
                generated_count += 1

    # Ikinci tur: emsal tablolari ancak butun evren hesaplandiktan sonra
    # bilindigi icin rapor bir kez daha render edilir. Karsilastirmalarin
    # KENDISI yukarida artifact olarak yazildi; bu tur yalniz sunum icin.
    if generate_report:
        for ticker in tickers:
            _rerender_report(workspace, ticker, as_of_date)
    return {"comparison_count": generated_count, "ticker_count": len(tickers)}


def _single_result_path(workspace: Path, ticker: str, as_of_date: str) -> Path:
    candidates = sorted(
        (workspace / "data" / "valuation-results" / ticker / as_of_date).glob("ctx-*/current.json")
    )
    if not candidates:
        raise UsPipelineError(
            f"expected at least one valuation result for {ticker} {as_of_date}, found none"
        )
    return max(candidates, key=lambda path: (
        read_json(path).get("temporal_context", {}).get("valuation_cutoff_at") or "",
        path.as_posix(),
    ))


def _rerender_report(workspace: Path, ticker: str, as_of_date: str) -> None:
    result_path = _single_result_path(workspace, ticker, as_of_date)
    context_id = result_path.parent.name
    financials = [
        read_json(path)
        for path in (workspace / "data" / "financial" / ticker).glob("*.json")
        if not path.stem.endswith("-derived-ratios")
    ]
    latest = max(financials, key=lambda item: item.get("period_end") or "")
    annuals = [item for item in financials if item.get("period_type") == "annual"]
    latest_fy = max(annuals, key=lambda item: item.get("period_end") or "")
    _, errors = generate_us_valuation_report(
        ticker,
        as_of_date,
        context_id,
        latest["period"],
        latest_fy["period"],
        workspace=workspace,
    )
    if errors:
        raise UsPipelineError(
            f"{ticker} peer-enriched report validation failed: {'; '.join(errors)}"
        )
