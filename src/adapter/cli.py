from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

from .cache import cache_filing, facts_document_paths
from .discovery import list_filings, resolve_cik
from .errors import UsPipelineError
from .normalize import normalize_filing, write_normalized_filing
from .sec_client import SecClient
from .fact_cache import load_facts_for_documents


def _client(args: argparse.Namespace) -> SecClient:
    user_agent = args.sec_user_agent or os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        raise UsPipelineError("set SEC_USER_AGENT or pass --sec-user-agent with a descriptive contact string")
    return SecClient(user_agent=user_agent)


def cmd_discover(args: argparse.Namespace) -> int:
    client = _client(args)
    cik = args.cik or resolve_cik(client, args.ticker)
    filings = list_filings(client, cik, as_of=date.fromisoformat(args.as_of))
    payload = [
        {
            "cik": item.cik,
            "accession": item.accession,
            "form": item.form,
            "filing_date": item.filing_date.isoformat(),
            "report_date": item.report_date.isoformat(),
            "primary_document": item.primary_document,
        }
        for item in filings[: args.limit]
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    client = _client(args)
    cik = args.cik or resolve_cik(client, args.ticker)
    filings = list_filings(client, cik, as_of=date.fromisoformat(args.as_of))
    selected = next((item for item in filings if item.accession == args.accession), None)
    if selected is None:
        raise UsPipelineError(f"accession {args.accession} is not an eligible filing as of {args.as_of}")
    workspace = Path(args.workspace).resolve()
    cache_dir = cache_filing(client, workspace, selected)
    facts = load_facts_for_documents(
        facts_document_paths(
            cache_dir, json.loads((cache_dir / "cache-metadata.json").read_text(encoding="utf-8"))),
        workspace / "cache" / "facts")
    print(json.dumps({
        "accession": selected.accession,
        "cache_dir": str(cache_dir),
        "fact_count": len(facts),
        "dimensionless_fact_count": sum(not fact.dimensions for fact in facts),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from engine.context import build_context
    from engine.io import read_json
    from engine.validation.engine import validate_inputs

    client = _client(args)
    cik = args.cik or resolve_cik(client, args.ticker)
    filings = list_filings(client, cik, as_of=date.fromisoformat(args.as_of))
    selected = next((item for item in filings if item.accession == args.accession), None)
    if selected is None:
        raise UsPipelineError(f"accession {args.accession} is not an eligible filing as of {args.as_of}")
    workspace = Path(args.workspace).resolve()
    cache_dir = cache_filing(client, workspace, selected)
    facts = load_facts_for_documents(
        facts_document_paths(
            cache_dir, json.loads((cache_dir / "cache-metadata.json").read_text(encoding="utf-8"))),
        workspace / "cache" / "facts")
    period_id, direct, evidence = normalize_filing(
        workspace=workspace,
        ticker=args.ticker,
        filing=selected,
        facts=facts,
        mapping_path=workspace / "config" / "sec" / "metric-map.json",
    )
    write_normalized_filing(
        workspace=workspace,
        ticker=args.ticker,
        period_id=period_id,
        filing=selected,
        direct=direct,
        evidence=evidence,
        cache_metadata=read_json(cache_dir / "cache-metadata.json"),
    )
    validation = validate_inputs(build_context(args.ticker, period_id, data_root=workspace))
    print(json.dumps({
        "ticker": args.ticker,
        "period": period_id,
        "metric_count": sum(len(direct[name]) for name in ("income_statement", "balance_sheet", "cash_flow_statement")),
        "validation": validation.as_dict(),
    }, ensure_ascii=False, indent=2))
    return 0 if validation.ok else 1


def cmd_analyze(args: argparse.Namespace) -> int:
    from engine.context import build_context
    from engine.generation import canonical_json, output_paths, write_bundle_transactional
    from engine.pipeline import run_pipeline

    workspace = Path(args.workspace).resolve()
    generated = run_pipeline(build_context(args.ticker, args.period, data_root=workspace))
    if not generated.validation.ok:
        print(json.dumps(generated.validation.as_dict(), ensure_ascii=False, indent=2))
        return 1
    paths = output_paths(args.ticker, args.period, workspace)
    write_bundle_transactional({
        paths["derived"]: canonical_json(generated.derived),
        paths["signals"]: canonical_json(generated.signals),
        paths["summaries"]: canonical_json(generated.summaries),
        paths["report"]: generated.report,
    })
    print(json.dumps({
        "ticker": args.ticker,
        "period": args.period,
        "validation": generated.validation.as_dict(),
        "outputs": {key: str(path) for key, path in paths.items()},
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_value(args: argparse.Namespace) -> int:
    from engine.io import read_json

    from .valuation import run_us_valuation

    workspace = Path(args.workspace).resolve()
    company = read_json(workspace / "config" / "companies" / f"{args.ticker}.json")
    cache_dir = workspace / "raw-cache" / "sec" / args.cik.zfill(10) / args.accession
    cache_metadata = read_json(cache_dir / "cache-metadata.json")
    facts = load_facts_for_documents(
        facts_document_paths(cache_dir, cache_metadata), workspace / "cache" / "facts")
    outputs = run_us_valuation(
        workspace=workspace, ticker=args.ticker, exchange=company["exchange"],
        as_of_date=args.as_of, cutoff_instant=args.cutoff_instant,
        accession=args.accession, facts=facts, latest_period=args.latest_period,
        fy_period=args.fy_period, latest_period_end=date.fromisoformat(args.latest_period_end),
        fy_period_end=date.fromisoformat(args.fy_period_end),
        company_type=company["pipeline"]["company_type"],
        sector_module=company["pipeline"]["sector_module"],
    )
    print(json.dumps({"ticker": args.ticker, "as_of": args.as_of, "outputs": outputs}, ensure_ascii=False, indent=2))
    return 0


def cmd_run_company(args: argparse.Namespace) -> int:
    from .workflow import run_company_workflow

    workspace = Path(args.workspace).resolve()
    result = run_company_workflow(
        client=_client(args), workspace=workspace, ticker=args.ticker,
        as_of=date.fromisoformat(args.as_of), cutoff_instant=args.cutoff_instant,
    )
    if args.enrich_peers:
        from .peers import generate_us_peer_comparisons

        peer_tickers = _peer_ready_tickers(
            workspace=workspace,
            as_of_date=args.as_of,
            required_ticker=args.ticker,
        )
        result["peers"] = generate_us_peer_comparisons(
            workspace=workspace,
            tickers=peer_tickers,
            as_of_date=args.as_of,
            generated_at=args.cutoff_instant,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _peer_ready_tickers(
    *, workspace: Path, as_of_date: str, required_ticker: str,
) -> list[str]:
    universe_path = (
        workspace / "config" / "valuation" / "comparison" / "peer-universes" /
        "consumer-staples.json"
    )
    universe = json.loads(universe_path.read_text(encoding="utf-8"))
    members = sorted({item["ticker"] for item in universe.get("members", [])})
    if required_ticker not in members:
        raise UsPipelineError(
            f"{required_ticker}: add the company to {universe_path} before peer enrichment"
        )

    ready = []
    for ticker in members:
        results = list(
            (workspace / "data" / "valuation-results" / ticker / as_of_date).glob(
                "ctx-*/current.json"
            )
        )
        if results:
            ready.append(ticker)
    return ready


def cmd_run_pilot(args: argparse.Namespace) -> int:
    from .peers import generate_us_peer_comparisons
    from .workflow import run_company_workflow

    workspace = Path(args.workspace).resolve()
    tickers = sorted(path.stem for path in (workspace / "config" / "companies").glob("*.json"))
    client = _client(args)
    results = []
    for ticker in tickers:
        results.append(run_company_workflow(
            client=client,
            workspace=workspace,
            ticker=ticker,
            as_of=date.fromisoformat(args.as_of),
            cutoff_instant=args.cutoff_instant,
        ))
    peers = generate_us_peer_comparisons(
        workspace=workspace,
        tickers=tickers,
        as_of_date=args.as_of,
        generated_at=args.cutoff_instant,
    )
    print(json.dumps({"tickers": tickers, "companies": results, "peers": peers}, ensure_ascii=False, indent=2))
    return 0


def cmd_enrich_peers(args: argparse.Namespace) -> int:
    from .peers import generate_us_peer_comparisons

    workspace = Path(args.workspace).resolve()
    tickers = sorted(path.stem for path in (workspace / "config" / "companies").glob("*.json"))
    result = generate_us_peer_comparisons(
        workspace=workspace,
        tickers=tickers,
        as_of_date=args.as_of,
        generated_at=args.generated_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="us-pipeline")
    parser.add_argument("--sec-user-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover")
    discover.add_argument("--ticker", required=True)
    discover.add_argument("--cik")
    discover.add_argument("--as-of", required=True)
    discover.add_argument("--limit", type=int, default=12)
    discover.set_defaults(func=cmd_discover)

    fetch = sub.add_parser("fetch")
    fetch.add_argument("--ticker", required=True)
    fetch.add_argument("--cik")
    fetch.add_argument("--as-of", required=True)
    fetch.add_argument("--accession", required=True)
    fetch.add_argument("--workspace", default=".")
    fetch.set_defaults(func=cmd_fetch)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--ticker", required=True)
    ingest.add_argument("--cik")
    ingest.add_argument("--as-of", required=True)
    ingest.add_argument("--accession", required=True)
    ingest.add_argument("--workspace", default=".")
    ingest.set_defaults(func=cmd_ingest)

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--ticker", required=True)
    analyze.add_argument("--period", required=True)
    analyze.add_argument("--workspace", default=".")
    analyze.set_defaults(func=cmd_analyze)

    value = sub.add_parser("value")
    value.add_argument("--ticker", required=True)
    value.add_argument("--cik", required=True)
    value.add_argument("--accession", required=True, help="SEC filing used for directly reported outstanding shares")
    value.add_argument("--as-of", required=True)
    value.add_argument("--cutoff-instant", required=True)
    value.add_argument("--latest-period", required=True)
    value.add_argument("--latest-period-end", required=True)
    value.add_argument("--fy-period", required=True)
    value.add_argument("--fy-period-end", required=True)
    value.add_argument("--workspace", default=".")
    value.set_defaults(func=cmd_value)

    run_company = sub.add_parser("run-company")
    run_company.add_argument("--ticker", required=True)
    run_company.add_argument("--as-of", required=True)
    run_company.add_argument("--cutoff-instant", required=True)
    run_company.add_argument("--workspace", default=".")
    run_company.add_argument(
        "--enrich-peers",
        action="store_true",
        help="refresh peer comparisons and rerender reports after the company run",
    )
    run_company.set_defaults(func=cmd_run_company)

    run_pilot = sub.add_parser("run-pilot")
    run_pilot.add_argument("--as-of", required=True)
    run_pilot.add_argument("--cutoff-instant", required=True)
    run_pilot.add_argument("--workspace", default=".")
    run_pilot.set_defaults(func=cmd_run_pilot)

    enrich_peers = sub.add_parser("enrich-peers")
    enrich_peers.add_argument("--as-of", required=True)
    enrich_peers.add_argument("--generated-at", required=True)
    enrich_peers.add_argument("--workspace", default=".")
    enrich_peers.set_defaults(func=cmd_enrich_peers)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (UsPipelineError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
