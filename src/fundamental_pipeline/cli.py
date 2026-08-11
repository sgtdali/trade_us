"""The ``fundamental-pipeline`` command-line entry point.

Every generation command (``derive``, ``signals``, ``summarize``, ``report``,
``run``) validates its inputs and every upstream stage it depends on
*before* generating its own output, and validates that output itself before
writing anything -- an invalid intermediate result is never committed to
disk. Each command either writes its output transactionally or, under
``--check``, compares the freshly generated output against whatever is
currently committed and exits non-zero on any drift (``--check`` always
compares against the real committed production files, never an
``--output-dir``; the two are mutually exclusive). Nothing here reads a
previously generated file as the source of truth for what to output.

``validate`` defaults to full-mode: it checks authored/normalized inputs
*and* every committed generated output (derived ratios, signals, summaries,
report), and it is an error for an expected generated output to be missing.
``--inputs-only`` restricts it to just the authored/normalized inputs, for
onboarding a company before any output has been generated yet.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .context import build_context
from .errors import PipelineError
from .generation import canonical_json, diff_against_committed, load_committed_outputs, output_paths, write_bundle_transactional
from .io import write_json_atomic
from .paths import repo_path, safe_ticker
from .pipeline import derive_financials, generate_signals, generate_summaries, render_report
from .registry.companies import load_company
from .registry.company_types import assert_implemented, get_company_type
from .registry.sector_modules import get_sector_module
from .validation.engine import (
    validate_derived,
    validate_full_analysis,
    validate_inputs,
    validate_report,
    validate_signals,
    validate_summaries,
)
from .validation.result import ValidationResult


def _print(data, as_json: bool) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2) if as_json else data)


def _print_validation(result, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Validation: {len(result.errors)} errors, {len(result.warnings)} warnings, {len(result.info)} info")
        for e in result.errors:
            print("ERROR:", e)
        for w in result.warnings:
            print("WARNING:", w)
    return 1 if result.errors else 0


def _fail_fast(result, args: argparse.Namespace) -> int | None:
    """Print and return an exit code if ``result`` has errors; otherwise
    return None so the caller knows to continue to the next stage. Used so
    every generation command rejects an invalid stage immediately instead of
    deferring all validation to the very end."""
    if not result.ok:
        _print_validation(result, args.json)
        return 1
    return None


def company_show(args: argparse.Namespace) -> int:
    _print(load_company(args.ticker, allow_inactive=args.allow_inactive), args.json)
    return 0


def route(args: argparse.Namespace) -> int:
    company = load_company(args.ticker, allow_inactive=args.allow_inactive)
    company_type = company["pipeline"]["company_type"]
    sector_module = company["pipeline"]["sector_module"]
    get_company_type(company_type)
    get_sector_module(sector_module)
    assert_implemented(company_type)
    _print({"ticker": args.ticker, "company_type": company_type, "sector_module": sector_module}, args.json)
    return 0


def validate(args: argparse.Namespace) -> int:
    context = build_context(args.ticker, args.period, allow_inactive=args.allow_inactive)
    if args.inputs_only:
        result = validate_inputs(context)
    else:
        committed = load_committed_outputs(args.ticker, args.period)
        result = validate_full_analysis(context, committed, require_outputs=True)
    return _print_validation(result, args.json)


def _output_root(args: argparse.Namespace) -> Path | None:
    return Path(args.output_dir).resolve() if args.output_dir else None


def _resolve_output_paths(args: argparse.Namespace) -> dict[str, Path]:
    """``--check`` always compares freshly generated output against the
    committed production files; combining it with ``--output-dir`` would
    silently compare against an (almost certainly empty) scratch directory
    and misreport that as production drift, so the combination is rejected
    outright rather than given ambiguous behavior."""
    if args.check and args.output_dir:
        raise PipelineError(
            "--check cannot be combined with --output-dir: --check always compares freshly generated "
            "output against the committed production files, never against an arbitrary output directory."
        )
    output_root = None if args.check else _output_root(args)
    return output_paths(args.ticker, args.period, output_root)


def _handle_bundle(args: argparse.Namespace, files: dict[Path, str]) -> int:
    if args.check:
        findings = diff_against_committed(files)
        if findings:
            if args.json:
                print(json.dumps({"drift": True, "files": [str(f.path) for f in findings]}, ensure_ascii=False, indent=2))
            else:
                print(f"ERROR: Drift detected in {len(findings)} file(s):", file=sys.stderr)
                for f in findings:
                    print(f"  - {f.path}", file=sys.stderr)
            return 1
        print(json.dumps({"drift": False}) if args.json else "No drift detected.")
        return 0
    write_bundle_transactional(files)
    for path in files:
        print(f"Wrote {path.relative_to(repo_path()) if _is_relative(path) else path}")
    return 0


def _is_relative(path: Path) -> bool:
    try:
        path.relative_to(repo_path())
        return True
    except ValueError:
        return False


def derive(args: argparse.Namespace) -> int:
    context = build_context(args.ticker, args.period, allow_inactive=args.allow_inactive)
    if (rc := _fail_fast(validate_inputs(context), args)) is not None:
        return rc
    derived = derive_financials(context)
    if (rc := _fail_fast(validate_derived(context, derived), args)) is not None:
        return rc
    paths = _resolve_output_paths(args)
    return _handle_bundle(args, {paths["derived"]: canonical_json(derived)})


def signals(args: argparse.Namespace) -> int:
    context = build_context(args.ticker, args.period, allow_inactive=args.allow_inactive)
    if (rc := _fail_fast(validate_inputs(context), args)) is not None:
        return rc
    derived = derive_financials(context)
    if (rc := _fail_fast(validate_derived(context, derived), args)) is not None:
        return rc
    signal_data = generate_signals(context, derived)
    if (rc := _fail_fast(validate_signals(context, signal_data), args)) is not None:
        return rc
    paths = _resolve_output_paths(args)
    return _handle_bundle(args, {paths["signals"]: canonical_json(signal_data)})


def summarize(args: argparse.Namespace) -> int:
    context = build_context(args.ticker, args.period, allow_inactive=args.allow_inactive)
    if (rc := _fail_fast(validate_inputs(context), args)) is not None:
        return rc
    derived = derive_financials(context)
    if (rc := _fail_fast(validate_derived(context, derived), args)) is not None:
        return rc
    signal_data = generate_signals(context, derived)
    if (rc := _fail_fast(validate_signals(context, signal_data), args)) is not None:
        return rc
    summary_data = generate_summaries(context, derived, signal_data)
    if (rc := _fail_fast(validate_summaries(context, summary_data, signal_data), args)) is not None:
        return rc
    paths = _resolve_output_paths(args)
    return _handle_bundle(args, {paths["summaries"]: canonical_json(summary_data)})


def report(args: argparse.Namespace) -> int:
    context = build_context(args.ticker, args.period, allow_inactive=args.allow_inactive)
    if (rc := _fail_fast(validate_inputs(context), args)) is not None:
        return rc
    derived = derive_financials(context)
    if (rc := _fail_fast(validate_derived(context, derived), args)) is not None:
        return rc
    signal_data = generate_signals(context, derived)
    if (rc := _fail_fast(validate_signals(context, signal_data), args)) is not None:
        return rc
    summary_data = generate_summaries(context, derived, signal_data)
    if (rc := _fail_fast(validate_summaries(context, summary_data, signal_data), args)) is not None:
        return rc
    report_text = render_report(context, derived, signal_data, summary_data)
    if (rc := _fail_fast(validate_report(context, report_text), args)) is not None:
        return rc
    paths = _resolve_output_paths(args)
    return _handle_bundle(args, {paths["report"]: report_text})


def run(args: argparse.Namespace) -> int:
    context = build_context(args.ticker, args.period, allow_inactive=args.allow_inactive)

    inputs_result = validate_inputs(context)
    if (rc := _fail_fast(inputs_result, args)) is not None:
        return rc
    derived = derive_financials(context)
    derived_result = validate_derived(context, derived)
    if (rc := _fail_fast(derived_result, args)) is not None:
        return rc
    signal_data = generate_signals(context, derived)
    signals_result = validate_signals(context, signal_data)
    if (rc := _fail_fast(signals_result, args)) is not None:
        return rc
    summary_data = generate_summaries(context, derived, signal_data)
    summaries_result = validate_summaries(context, summary_data, signal_data)
    if (rc := _fail_fast(summaries_result, args)) is not None:
        return rc
    report_text = render_report(context, derived, signal_data, summary_data)
    report_result = validate_report(context, report_text)
    if (rc := _fail_fast(report_result, args)) is not None:
        return rc

    combined = ValidationResult()
    for stage_result in (inputs_result, derived_result, signals_result, summaries_result, report_result):
        combined.merge(stage_result)

    paths = _resolve_output_paths(args)
    files = {
        paths["derived"]: canonical_json(derived),
        paths["signals"]: canonical_json(signal_data),
        paths["summaries"]: canonical_json(summary_data),
        paths["report"]: report_text,
    }
    rc = _handle_bundle(args, files)
    if rc == 0:
        _print_validation(combined, args.json)
    return rc


def scaffold(args: argparse.Namespace) -> int:
    ticker = safe_ticker(args.ticker)
    get_company_type(args.company_type)
    get_sector_module(args.sector_module)
    company_type_entry = get_company_type(args.company_type)
    if company_type_entry["status"] != "implemented" and not args.allow_inactive:
        raise PipelineError(f"company_type {args.company_type!r} is not implemented; pass --allow-inactive to scaffold it anyway")

    out = Path(args.output_dir).resolve() if args.output_dir else repo_path()
    out.mkdir(parents=True, exist_ok=True)

    def w(rel: Path, data: dict) -> None:
        p = out / rel
        if p.exists() and not args.force:
            raise PipelineError(f"File exists (use --force): {p}")
        write_json_atomic(p, data)

    w(Path("config/companies") / f"{ticker}.json", {
        "schema_version": 1, "ticker": ticker, "exchange": args.exchange, "company_name": None,
        "reporting_locale": "tr-TR",
        "classification": {"source": None, "official_sector": None, "official_industry": None, "official_subindustry": None, "actual_activity": None, "classification_date": None},
        "pipeline": {"company_type": args.company_type, "sector_module": args.sector_module},
        "sources": {"identity_source": None, "classification_source": None},
        "version": 1, "is_active": False,
    })
    w(Path("data/source-manifests") / f"{ticker}.json", {"schema_version": 1, "ticker": ticker, "sources": []})
    w(Path("data/financial") / ticker / f"{args.period}.json", {
        "schema_version": 1, "ticker": ticker, "period": args.period, "period_type": "quarterly",
        "currency": "USD", "scale": "million", "consolidation": "consolidated", "audit_status": "unaudited",
        "accounting_basis": "undetermined",
        "inflation_adjustment": {"status": "undetermined", "standard": None},
        "restatement": {"status": "undetermined", "restated_from_publication_date": None},
        "publication_date": None, "source_revision": None,
        "income_statement": [], "balance_sheet": [], "cash_flow_statement": [],
    })
    w(
        Path("data/risks") / ticker / f"{args.period}.json",
        {
            "schema_version": 1,
            "ticker": ticker,
            "period": args.period,
            "analysis_status": "unavailable",
            "unavailable_reason_code": "risk_not_authored",
            "validation_findings": [],
            "risks": [],
        },
    )
    print(f"Scaffold created under {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fundamental-pipeline")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    company = sub.add_parser("company")
    company_sub = company.add_subparsers(dest="sub", required=True)
    show = company_sub.add_parser("show")
    show.add_argument("--ticker", required=True)
    show.add_argument("--allow-inactive", action="store_true")
    show.set_defaults(func=company_show)

    route_parser = sub.add_parser("route")
    route_parser.add_argument("--ticker", required=True)
    route_parser.add_argument("--allow-inactive", action="store_true")
    route_parser.set_defaults(func=route)

    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--ticker", required=True)
    validate_parser.add_argument("--period", required=True)
    validate_parser.add_argument("--allow-inactive", action="store_true")
    validate_parser.add_argument(
        "--inputs-only", action="store_true",
        help="Validate only authored/normalized inputs (company config, source manifest, direct "
             "financials, historical series, financial-operational data, risks). Use this before "
             "generated outputs exist (onboarding a new company). Without this flag, validate also "
             "requires and checks the committed derived/signals/summaries/report outputs.",
    )
    validate_parser.set_defaults(func=validate)

    for name, func in [("derive", derive), ("signals", signals), ("summarize", summarize), ("report", report), ("run", run)]:
        p = sub.add_parser(name)
        p.add_argument("--ticker", required=True)
        p.add_argument("--period", required=True)
        p.add_argument("--allow-inactive", action="store_true")
        p.add_argument("--output-dir")
        p.add_argument("--check", action="store_true")
        p.set_defaults(func=func)

    scaffold_parser = sub.add_parser("scaffold")
    scaffold_parser.add_argument("--ticker", required=True)
    scaffold_parser.add_argument("--exchange", required=True)
    scaffold_parser.add_argument("--company-type", required=True)
    scaffold_parser.add_argument("--sector-module", required=True)
    scaffold_parser.add_argument("--period", required=True)
    scaffold_parser.add_argument("--output-dir")
    scaffold_parser.add_argument("--force", action="store_true")
    scaffold_parser.add_argument("--allow-inactive", action="store_true")
    scaffold_parser.set_defaults(func=scaffold)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PipelineError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 - CLI boundary: surface any failure as a clean error exit
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
