"""The ``market-ingestion`` command-line entry point.

Command surface (docs/yfinance-eod-pilot.md):

    market-ingestion yfinance fetch --ticker T [--ticker T...] --start DATE --end DATE
        --mapping PATH --output-dir DIR [--timeout N] [--json]
    market-ingestion yfinance refresh-price --ticker T --as-of DATE --cutoff-instant INSTANT
        --mapping PATH --manifest PATH --policy PATH --effective-at INSTANT
        --output-dir DIR [--timeout N] [--json]
    market-ingestion bundle validate --root DIR [--json]
    market-ingestion bundle replay --root DIR [--check] [--json]
    market-ingestion price manifest-validate --manifest PATH --ticker T --as-of DATE [--json]
    market-ingestion price promote --bundle-root DIR --manifest PATH --policy PATH
        --ticker T --as-of DATE --cutoff-instant INSTANT --effective-at INSTANT
        --output-dir DIR [--check] [--json]
    market-ingestion share-count ledger-validate --ledger PATH [--json]
    market-ingestion share-count manifest-validate --manifest PATH --ticker T --as-of DATE [--json]
    market-ingestion share-count promote --ledger PATH --share-manifest PATH
        --corporate-action-manifest PATH --policy PATH --ticker T --as-of DATE
        --cutoff-instant INSTANT --output-dir DIR [--check] [--json]
    market-ingestion fx fetch --pair BASE/QUOTE [--pair BASE/QUOTE...] --start DATE --end DATE
        --mapping PATH --output-dir DIR [--timeout N] [--json]
    market-ingestion fx bundle-validate --root DIR [--json]
    market-ingestion fx bundle-replay --root DIR [--check] [--json]
    market-ingestion fx manifest-validate --manifest PATH --pair BASE/QUOTE --as-of DATE [--json]
    market-ingestion fx promote --bundle-root DIR --manifest PATH --policy PATH
        --pair BASE/QUOTE --as-of DATE --cutoff-instant INSTANT --effective-at INSTANT
        --output-dir DIR [--check] [--json]
    market-ingestion observations merge --bundle PATH [--bundle PATH...] --output-dir DIR [--check] [--json]

``share-count`` is an authored-official-evidence path, not a network fetch
path -- unlike ``yfinance``, it deliberately has no live-provider
convenience command (docs/eregl-point-in-time-share-count-governance.md).
``fx`` is the provider-neutral FX ingestion/promotion bridge -- a
sibling of ``yfinance``/``price``, kept as its own top-level group (not
merged into ``bundle``/``price``) because its bundle schemas and subject
identity (``BASE/QUOTE`` pairs, not tickers) genuinely differ.
``observations merge`` combines two or more already-promoted
market-observation-bundle.schema.json files (e.g. a price+share-count
bundle and a separate FX bundle) into one combined bundle for T70
snapshot generation.

Exit codes:

    0 = success / no drift
    1 = validation failure, quarantined blocking data, or replay drift
    2 = invocation/bootstrap/dependency/provider-availability/path failure

``fetch``/``refresh-price``/``price promote`` never have a default
``--output-dir``; there is no implicit production write path. If the
optional ``market`` dependency group is not installed, this CLI fails with
an actionable message and exit code 2, never a raw ``ImportError``
traceback. ``refresh-price`` is a live-provider convenience command and
therefore never exposes ``--check`` -- ``price promote`` is the
deterministic offline drift-check surface.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ....paths import repo_path
from ...errors import MarketResolutionError
from ...market.observation_merge import merge_observation_bundles
from ...validation.findings import Finding, has_blocking
from ..fx.errors import FxBundleIntegrityError, FxIngestionError
from ..fx.service import load_fx_provider_config, replay_fx_bundle, run_fetch_fx, validate_fx_bundle
from ..fx.validation import validate_fx_request_and_mapping
from ..fx_promotion.errors import FxPromotionError
from ..fx_promotion.service import load_fx_promotion_policy, promote as promote_fx_service, validate_manifest as validate_fx_manifest
from ..promotion.errors import PromotionError
from ..promotion.service import load_promotion_policy, promote as promote_service, validate_manifest
from ..share_count.errors import ShareCountError
from ..share_count.service import (
    promote as promote_share_count_service,
    validate_ledger as validate_share_count_ledger,
    validate_manifest as validate_share_count_manifest,
)
from .errors import BundleIntegrityError, IngestionError, ProviderBootstrapError, ProviderConfigError, RequestConstructionError
from .service import load_provider_config, replay_bundle, run_fetch, validate_bundle
from .validation import validate_request_and_mapping

EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILED = 1
EXIT_BOOTSTRAP_FAILURE = 2


def _finding_to_json(finding: Finding) -> dict:
    return {
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "scope": finding.scope,
        "reason_code": finding.reason_code,
        "message": finding.message,
        "artifact_id": finding.artifact_id,
        "relative_path": finding.relative_path,
        "json_pointer": finding.json_pointer,
    }


def _emit(command: str, *, ok: bool, findings, as_json: bool, extra: dict | None = None) -> int:
    exit_code = EXIT_SUCCESS if ok else EXIT_VALIDATION_FAILED
    if as_json:
        import json
        payload = {"command": command, "status": "ok" if ok else "failed", "exit_code": exit_code, "findings": [_finding_to_json(f) for f in findings]}
        if extra:
            payload.update(extra)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        if ok:
            print(f"{command}: ok (0 blocking finding(s))")
        else:
            print(f"{command}: FAILED", file=sys.stderr)
        for f in findings:
            stream = sys.stderr if f.severity in ("error", "blocker") else sys.stdout
            print(f"  [{f.severity.upper()}] {f.rule_id} {f.reason_code}: {f.message}", file=stream)
    return exit_code


def _reject_output_dir_inside_raw(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    raw_root = repo_path("raw").resolve()
    if resolved == raw_root or raw_root in resolved.parents:
        raise ArgumentPathError(f"--output-dir must not be inside raw/: {output_dir}")


class ArgumentPathError(Exception):
    pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="market-ingestion", description="Provider-neutral end-of-day market-data ingestion CLI.")
    subparsers = parser.add_subparsers(dest="group", required=True)

    yfinance_group = subparsers.add_parser("yfinance", help="YFinance pilot provider commands")
    yfinance_sub = yfinance_group.add_subparsers(dest="command", required=True)
    fetch = yfinance_sub.add_parser("fetch", help="Fetch daily EOD bars for one or more mapped internal tickers")
    fetch.add_argument("--ticker", action="append", required=True, dest="tickers", help="Internal ticker to fetch (repeatable)")
    fetch.add_argument("--start", required=True, dest="start_date_inclusive", help="Start date, inclusive (YYYY-MM-DD)")
    fetch.add_argument("--end", required=True, dest="end_date_exclusive", help="End date, EXCLUSIVE (YYYY-MM-DD) -- the last bar produced is the trading day before this date")
    fetch.add_argument("--mapping", required=True, type=Path, help="Path to the provider mapping config (config/market-data/providers/yfinance.json)")
    fetch.add_argument("--output-dir", required=True, type=Path, help="Directory to write the run bundle into. Mandatory -- there is no default or inferred production write root.")
    fetch.add_argument("--timeout", type=int, default=20, help="Bounded per-symbol fetch timeout in whole seconds (default: 20)")
    fetch.add_argument("--json", action="store_true", help="Emit a stable machine-readable JSON envelope on stdout")

    refresh_price = yfinance_sub.add_parser(
        "refresh-price",
        help="Convenience: fetch + validate + promote one ticker's EOD close in a single command",
    )
    refresh_price.add_argument("--ticker", required=True, help="Internal ticker (e.g. EREGL)")
    refresh_price.add_argument("--as-of", required=True, dest="as_of_date", help="As-of date (YYYY-MM-DD)")
    refresh_price.add_argument("--cutoff-instant", required=True, help="UTC cutoff instant (...Z)")
    refresh_price.add_argument("--mapping", required=True, type=Path, help="Provider mapping config (e.g. config/market-data/providers/yfinance-eregl-temporary-valuation.json)")
    refresh_price.add_argument("--manifest", required=True, type=Path, help="Market-source manifest path")
    refresh_price.add_argument("--policy", required=True, type=Path, help="Promotion policy path")
    refresh_price.add_argument("--effective-at", required=True, dest="effective_at", help="Explicit UTC instant for the promoted observation's effective_at")
    refresh_price.add_argument("--output-dir", required=True, type=Path, help="Directory to write ingestion/ and promotion/ subdirectories into")
    refresh_price.add_argument("--timeout", type=int, default=20, help="Bounded per-symbol fetch timeout in whole seconds (default: 20)")
    refresh_price.add_argument("--json", action="store_true")

    bundle_group = subparsers.add_parser("bundle", help="Ingestion bundle commands")
    bundle_sub = bundle_group.add_subparsers(dest="command", required=True)
    validate_cmd = bundle_sub.add_parser("validate", help="Structurally validate a committed ingestion bundle")
    validate_cmd.add_argument("--root", required=True, type=Path, help="Bundle root directory")
    validate_cmd.add_argument("--json", action="store_true")

    replay_cmd = bundle_sub.add_parser("replay", help="Recompute eod-price-series/validation/bundle-manifest from the committed provider-extract")
    replay_cmd.add_argument("--root", required=True, type=Path, help="Bundle root directory")
    replay_cmd.add_argument("--check", action="store_true", help="Compare only; perform zero filesystem writes; exit 1 on drift")
    replay_cmd.add_argument("--json", action="store_true")

    price_group = subparsers.add_parser("price", help="EOD-close promotion bridge commands")
    price_sub = price_group.add_subparsers(dest="command", required=True)

    manifest_validate_cmd = price_sub.add_parser(
        "manifest-validate", help="Validate a market-source manifest's structure, hash, and authorization"
    )
    manifest_validate_cmd.add_argument("--manifest", required=True, type=Path)
    manifest_validate_cmd.add_argument("--ticker", required=True)
    manifest_validate_cmd.add_argument("--as-of", required=True, dest="as_of_date")
    manifest_validate_cmd.add_argument("--json", action="store_true")

    promote_cmd = price_sub.add_parser(
        "promote",
        help="Deterministic offline promotion of a validated EOD ingestion bundle into a T70-compatible observation bundle",
    )
    promote_cmd.add_argument("--bundle-root", required=True, type=Path, help="Root of a validated market-ingestion yfinance fetch bundle")
    promote_cmd.add_argument("--manifest", required=True, type=Path, help="Market-source manifest path")
    promote_cmd.add_argument("--policy", required=True, type=Path, help="Promotion policy path")
    promote_cmd.add_argument("--ticker", required=True)
    promote_cmd.add_argument("--as-of", required=True, dest="as_of_date")
    promote_cmd.add_argument("--cutoff-instant", required=True)
    promote_cmd.add_argument(
        "--effective-at", required=True, dest="effective_at",
        help="Explicit UTC instant for the promoted observation's effective_at -- mandatory because no "
             "verified BIST closing-auction convention is governed yet (see the loaded policy's "
             "effective_at_verification_note)",
    )
    promote_cmd.add_argument("--output-dir", required=True, type=Path)
    promote_cmd.add_argument("--check", action="store_true", help="Compare only; perform zero filesystem writes; exit 1 on drift")
    promote_cmd.add_argument("--json", action="store_true")

    share_count_group = subparsers.add_parser("share-count", help="Share-count/corporate-action ledger promotion bridge commands")
    share_count_sub = share_count_group.add_subparsers(dest="command", required=True)

    ledger_validate_cmd = share_count_sub.add_parser(
        "ledger-validate", help="Structurally validate an authored share-count ledger's schema, cross-references, and content hash"
    )
    ledger_validate_cmd.add_argument("--ledger", required=True, type=Path)
    ledger_validate_cmd.add_argument("--json", action="store_true")

    sc_manifest_validate_cmd = share_count_sub.add_parser(
        "manifest-validate", help="Validate a share-count or corporate-action market-source manifest's structure, hash, and authorization"
    )
    sc_manifest_validate_cmd.add_argument("--manifest", required=True, type=Path)
    sc_manifest_validate_cmd.add_argument("--ticker", required=True)
    sc_manifest_validate_cmd.add_argument("--as-of", required=True, dest="as_of_date")
    sc_manifest_validate_cmd.add_argument("--json", action="store_true")

    sc_promote_cmd = share_count_sub.add_parser(
        "promote",
        help="Deterministic offline promotion of an authored share-count ledger into T70-compatible "
             "issued_shares/treasury_shares observations and a governed corporate-action bundle",
    )
    sc_promote_cmd.add_argument("--ledger", required=True, type=Path, help="Authored share-count ledger path")
    sc_promote_cmd.add_argument("--share-manifest", required=True, type=Path, dest="share_manifest", help="Official share-count market-source manifest path")
    sc_promote_cmd.add_argument("--corporate-action-manifest", required=True, type=Path, dest="corporate_action_manifest", help="Official corporate-action market-source manifest path")
    sc_promote_cmd.add_argument("--policy", required=True, type=Path, help="Share-count promotion policy path")
    sc_promote_cmd.add_argument("--ticker", required=True)
    sc_promote_cmd.add_argument("--as-of", required=True, dest="as_of_date")
    sc_promote_cmd.add_argument("--cutoff-instant", required=True)
    sc_promote_cmd.add_argument("--output-dir", required=True, type=Path)
    sc_promote_cmd.add_argument("--check", action="store_true", help="Compare only; perform zero filesystem writes; exit 1 on drift")
    sc_promote_cmd.add_argument("--json", action="store_true")

    fx_group = subparsers.add_parser("fx", help="Temporary provider-neutral FX ingestion/promotion bridge commands")
    fx_sub = fx_group.add_subparsers(dest="command", required=True)

    fx_fetch = fx_sub.add_parser("fetch", help="Fetch daily FX bars for one or more mapped BASE/QUOTE pairs")
    fx_fetch.add_argument("--pair", action="append", required=True, dest="pairs", help="FX pair to fetch, canonical BASE/QUOTE (repeatable)")
    fx_fetch.add_argument("--start", required=True, dest="start_date_inclusive", help="Start date, inclusive (YYYY-MM-DD)")
    fx_fetch.add_argument("--end", required=True, dest="end_date_exclusive", help="End date, EXCLUSIVE (YYYY-MM-DD)")
    fx_fetch.add_argument("--mapping", required=True, type=Path, help="Path to the FX provider mapping config")
    fx_fetch.add_argument("--output-dir", required=True, type=Path, help="Directory to write the run bundle into. Mandatory -- there is no default or inferred production write root.")
    fx_fetch.add_argument("--timeout", type=int, default=20, help="Bounded per-pair fetch timeout in whole seconds (default: 20)")
    fx_fetch.add_argument("--json", action="store_true")

    fx_bundle_validate = fx_sub.add_parser("bundle-validate", help="Structurally validate a committed FX ingestion bundle")
    fx_bundle_validate.add_argument("--root", required=True, type=Path)
    fx_bundle_validate.add_argument("--json", action="store_true")

    fx_bundle_replay = fx_sub.add_parser("bundle-replay", help="Recompute fx-rate-series/validation/bundle-manifest from the committed fx-provider-extract")
    fx_bundle_replay.add_argument("--root", required=True, type=Path)
    fx_bundle_replay.add_argument("--check", action="store_true", help="Compare only; perform zero filesystem writes; exit 1 on drift")
    fx_bundle_replay.add_argument("--json", action="store_true")

    fx_manifest_validate = fx_sub.add_parser("manifest-validate", help="Validate an FX market-source manifest's structure, hash, and authorization")
    fx_manifest_validate.add_argument("--manifest", required=True, type=Path)
    fx_manifest_validate.add_argument("--pair", required=True, help="Canonical BASE/QUOTE pair (e.g. USD/TRY)")
    fx_manifest_validate.add_argument("--as-of", required=True, dest="as_of_date")
    fx_manifest_validate.add_argument("--json", action="store_true")

    fx_promote_cmd = fx_sub.add_parser("promote", help="Deterministic offline promotion of a validated FX ingestion bundle into a T70-compatible fx observation")
    fx_promote_cmd.add_argument("--bundle-root", required=True, type=Path, help="Root of a validated market-ingestion fx fetch bundle")
    fx_promote_cmd.add_argument("--manifest", required=True, type=Path)
    fx_promote_cmd.add_argument("--policy", required=True, type=Path)
    fx_promote_cmd.add_argument("--pair", required=True, help="Canonical BASE/QUOTE pair (e.g. USD/TRY)")
    fx_promote_cmd.add_argument("--as-of", required=True, dest="as_of_date")
    fx_promote_cmd.add_argument("--cutoff-instant", required=True)
    fx_promote_cmd.add_argument(
        "--effective-at", required=True, dest="effective_at",
        help="Explicit UTC instant for the promoted observation's effective_at -- mandatory because no "
             "verified FX market-close convention is governed yet (see the loaded policy's "
             "effective_at_verification_note)",
    )
    fx_promote_cmd.add_argument("--output-dir", required=True, type=Path)
    fx_promote_cmd.add_argument("--check", action="store_true", help="Compare only; perform zero filesystem writes; exit 1 on drift")
    fx_promote_cmd.add_argument("--json", action="store_true")

    observations_group = subparsers.add_parser("observations", help="Market-observation-bundle utility commands")
    observations_sub = observations_group.add_subparsers(dest="command", required=True)
    merge_cmd = observations_sub.add_parser("merge", help="Merge two or more already-promoted observation bundles into one combined bundle")
    merge_cmd.add_argument("--bundle", action="append", required=True, dest="bundles", type=Path, help="Path to an observations.json to merge (repeatable, at least two required)")
    merge_cmd.add_argument("--output-dir", required=True, type=Path)
    merge_cmd.add_argument("--check", action="store_true", help="Compare only; perform zero filesystem writes; exit 1 on drift")
    merge_cmd.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.group == "yfinance" and args.command == "fetch":
            return _cmd_fetch(args)
        if args.group == "yfinance" and args.command == "refresh-price":
            return _cmd_refresh_price(args)
        if args.group == "bundle" and args.command == "validate":
            return _cmd_bundle_validate(args)
        if args.group == "bundle" and args.command == "replay":
            return _cmd_bundle_replay(args)
        if args.group == "price" and args.command == "manifest-validate":
            return _cmd_price_manifest_validate(args)
        if args.group == "price" and args.command == "promote":
            return _cmd_price_promote(args)
        if args.group == "share-count" and args.command == "ledger-validate":
            return _cmd_share_count_ledger_validate(args)
        if args.group == "share-count" and args.command == "manifest-validate":
            return _cmd_share_count_manifest_validate(args)
        if args.group == "share-count" and args.command == "promote":
            return _cmd_share_count_promote(args)
        if args.group == "fx" and args.command == "fetch":
            return _cmd_fx_fetch(args)
        if args.group == "fx" and args.command == "bundle-validate":
            return _cmd_fx_bundle_validate(args)
        if args.group == "fx" and args.command == "bundle-replay":
            return _cmd_fx_bundle_replay(args)
        if args.group == "fx" and args.command == "manifest-validate":
            return _cmd_fx_manifest_validate(args)
        if args.group == "fx" and args.command == "promote":
            return _cmd_fx_promote(args)
        if args.group == "observations" and args.command == "merge":
            return _cmd_observations_merge(args)
    except (ProviderBootstrapError, ProviderConfigError, RequestConstructionError, ArgumentPathError) as exc:
        print(f"market-ingestion: {exc}", file=sys.stderr)
        return EXIT_BOOTSTRAP_FAILURE
    except (BundleIntegrityError, FxBundleIntegrityError) as exc:
        print(f"market-ingestion: {exc}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    except (MarketResolutionError, PromotionError, ShareCountError, FxPromotionError) as exc:
        print(f"market-ingestion: {exc}", file=sys.stderr)
        return EXIT_BOOTSTRAP_FAILURE
    except (IngestionError, FxIngestionError) as exc:
        print(f"market-ingestion: internal error: {exc}", file=sys.stderr)
        return EXIT_BOOTSTRAP_FAILURE

    parser.print_help(sys.stderr)
    return EXIT_BOOTSTRAP_FAILURE


def _cmd_fetch(args: argparse.Namespace) -> int:
    if args.start_date_inclusive >= args.end_date_exclusive:
        print("market-ingestion: --start must be strictly before --end (--end is exclusive)", file=sys.stderr)
        return EXIT_BOOTSTRAP_FAILURE
    if args.timeout <= 0:
        print("market-ingestion: --timeout must be strictly positive", file=sys.stderr)
        return EXIT_BOOTSTRAP_FAILURE

    _reject_output_dir_inside_raw(args.output_dir)

    provider_config = load_provider_config(args.mapping)

    # Validate the request against the mapping table *before* touching the
    # optional yfinance dependency at all -- an invocation naming only
    # unknown/inactive/duplicate tickers must fail as an ordinary domain
    # validation (exit 1) without ever importing yfinance, both so the
    # bootstrap-error/exit-2 path is reserved for genuine dependency
    # problems and so this command never has an unnecessary side effect
    # (importing a third-party network library) when it is going to reject
    # the request anyway.
    mapping_findings = validate_request_and_mapping(provider_config, args.tickers)
    if has_blocking(mapping_findings):
        extra = {"overall_status": "invalid", "output_dir": str(args.output_dir)}
        return _emit("yfinance fetch", ok=False, findings=mapping_findings, as_json=args.json, extra=extra)

    from .providers.yfinance_provider import YFinanceProvider, yfinance_library_version
    provider_library_version = yfinance_library_version()  # raises ProviderBootstrapError if yfinance is not installed
    provider = YFinanceProvider()

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = run_fetch(
        provider=provider,
        provider_config=provider_config,
        requested_tickers=args.tickers,
        start_date_inclusive=args.start_date_inclusive,
        end_date_exclusive=args.end_date_exclusive,
        timeout=args.timeout,
        retrieved_at=retrieved_at,
        provider_library_version=provider_library_version,
        output_dir=args.output_dir,
    )
    extra = {"overall_status": result.overall_status, "output_dir": str(args.output_dir)}
    return _emit("yfinance fetch", ok=result.ok, findings=result.findings, as_json=args.json, extra=extra)


def _cmd_bundle_validate(args: argparse.Namespace) -> int:
    findings = validate_bundle(args.root)
    ok = not has_blocking(findings)
    return _emit("bundle validate", ok=ok, findings=findings, as_json=args.json)


def _cmd_bundle_replay(args: argparse.Namespace) -> int:
    transaction_result, findings = replay_bundle(args.root, check_only=args.check)
    ok = not has_blocking(findings)
    drifted = args.check and transaction_result.status == "drift"
    extra = {"transaction_status": transaction_result.status}
    if drifted:
        extra["diffs"] = [{"relative_path": d.relative_path, "state": d.state} for d in transaction_result.diffs]
    return _emit("bundle replay", ok=ok and not drifted, findings=findings, as_json=args.json, extra=extra)


def _cmd_price_manifest_validate(args: argparse.Namespace) -> int:
    findings = validate_manifest(args.manifest, ticker=args.ticker, as_of_date=args.as_of_date)
    ok = not has_blocking(findings)
    return _emit("price manifest-validate", ok=ok, findings=findings, as_json=args.json)


def _cmd_price_promote(args: argparse.Namespace) -> int:
    _reject_output_dir_inside_raw(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run = promote_service(
        bundle_root=args.bundle_root,
        manifest_path=args.manifest,
        policy_path=args.policy,
        ticker=args.ticker,
        as_of_date=args.as_of_date,
        cutoff_instant=args.cutoff_instant,
        effective_at=args.effective_at,
        output_dir=args.output_dir,
        check_only=args.check,
    )
    drifted = args.check and run.transaction.status == "drift"
    extra = {
        "overall_status": run.outcome.overall_status,
        "selected_trade_date": run.outcome.selected_trade_date,
        "output_dir": str(args.output_dir),
        "transaction_status": run.transaction.status,
    }
    if drifted:
        extra["diffs"] = [{"relative_path": d.relative_path, "state": d.state} for d in run.transaction.diffs]
    return _emit("price promote", ok=run.ok, findings=list(run.outcome.findings), as_json=args.json, extra=extra)


def _cmd_share_count_ledger_validate(args: argparse.Namespace) -> int:
    findings = validate_share_count_ledger(args.ledger)
    ok = not has_blocking(findings)
    return _emit("share-count ledger-validate", ok=ok, findings=findings, as_json=args.json)


def _cmd_share_count_manifest_validate(args: argparse.Namespace) -> int:
    findings = validate_share_count_manifest(args.manifest, ticker=args.ticker, as_of_date=args.as_of_date)
    ok = not has_blocking(findings)
    return _emit("share-count manifest-validate", ok=ok, findings=findings, as_json=args.json)


def _cmd_share_count_promote(args: argparse.Namespace) -> int:
    _reject_output_dir_inside_raw(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run = promote_share_count_service(
        ledger_path=args.ledger,
        share_manifest_path=args.share_manifest,
        corporate_action_manifest_path=args.corporate_action_manifest,
        policy_path=args.policy,
        ticker=args.ticker,
        as_of_date=args.as_of_date,
        cutoff_instant=args.cutoff_instant,
        output_dir=args.output_dir,
        check_only=args.check,
    )
    drifted = args.check and run.transaction.status == "drift"
    extra = {
        "overall_status": run.outcome.overall_status,
        "output_dir": str(args.output_dir),
        "transaction_status": run.transaction.status,
    }
    if drifted:
        extra["diffs"] = [{"relative_path": d.relative_path, "state": d.state} for d in run.transaction.diffs]
    return _emit("share-count promote", ok=run.ok, findings=list(run.outcome.findings), as_json=args.json, extra=extra)


def _cmd_refresh_price(args: argparse.Namespace) -> int:
    if args.timeout <= 0:
        print("market-ingestion: --timeout must be strictly positive", file=sys.stderr)
        return EXIT_BOOTSTRAP_FAILURE
    _reject_output_dir_inside_raw(args.output_dir)

    provider_config = load_provider_config(args.mapping)
    mapping_findings = validate_request_and_mapping(provider_config, [args.ticker])
    if has_blocking(mapping_findings):
        return _emit(
            "yfinance refresh-price", ok=False, findings=mapping_findings, as_json=args.json,
            extra={"overall_status": "invalid", "output_dir": str(args.output_dir)},
        )

    # Load the promotion policy before touching the network -- its
    # max_fallback_lag_days governs the bounded fetch window below, and a
    # broken/unhashable policy must fail before any provider call is made.
    _policy_doc, policy = load_promotion_policy(args.policy)

    as_of = date.fromisoformat(args.as_of_date)
    start_date_inclusive = (as_of - timedelta(days=policy.max_fallback_lag_days + 1)).isoformat()
    end_date_exclusive = (as_of + timedelta(days=1)).isoformat()

    from .providers.yfinance_provider import YFinanceProvider, yfinance_library_version
    provider_library_version = yfinance_library_version()
    provider = YFinanceProvider()
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ingestion_dir = args.output_dir / "ingestion"
    ingestion_dir.mkdir(parents=True, exist_ok=True)
    ingestion_result = run_fetch(
        provider=provider,
        provider_config=provider_config,
        requested_tickers=[args.ticker],
        start_date_inclusive=start_date_inclusive,
        end_date_exclusive=end_date_exclusive,
        timeout=args.timeout,
        retrieved_at=retrieved_at,
        provider_library_version=provider_library_version,
        output_dir=ingestion_dir,
    )
    if not ingestion_result.ok:
        return _emit(
            "yfinance refresh-price", ok=False, findings=ingestion_result.findings, as_json=args.json,
            extra={
                "stage": "ingestion",
                "overall_status": ingestion_result.overall_status,
                "output_dir": str(ingestion_dir),
            },
        )

    promotion_dir = args.output_dir / "promotion"
    promotion_dir.mkdir(parents=True, exist_ok=True)
    run = promote_service(
        bundle_root=ingestion_dir,
        manifest_path=args.manifest,
        policy_path=args.policy,
        ticker=args.ticker,
        as_of_date=args.as_of_date,
        cutoff_instant=args.cutoff_instant,
        effective_at=args.effective_at,
        output_dir=promotion_dir,
    )
    extra = {
        "stage": "promotion",
        "overall_status": run.outcome.overall_status,
        "selected_trade_date": run.outcome.selected_trade_date,
        "ingestion_dir": "ingestion",
        "promotion_dir": "promotion",
    }
    return _emit("yfinance refresh-price", ok=run.ok, findings=list(run.outcome.findings), as_json=args.json, extra=extra)


def _cmd_fx_fetch(args: argparse.Namespace) -> int:
    if args.start_date_inclusive >= args.end_date_exclusive:
        print("market-ingestion: --start must be strictly before --end (--end is exclusive)", file=sys.stderr)
        return EXIT_BOOTSTRAP_FAILURE
    if args.timeout <= 0:
        print("market-ingestion: --timeout must be strictly positive", file=sys.stderr)
        return EXIT_BOOTSTRAP_FAILURE

    _reject_output_dir_inside_raw(args.output_dir)

    provider_config = load_fx_provider_config(args.mapping)

    mapping_findings = validate_fx_request_and_mapping(provider_config, args.pairs)
    if has_blocking(mapping_findings):
        extra = {"overall_status": "invalid", "output_dir": str(args.output_dir)}
        return _emit("fx fetch", ok=False, findings=mapping_findings, as_json=args.json, extra=extra)

    from ..eod.providers.yfinance_provider import YFinanceProvider, yfinance_library_version
    provider_library_version = yfinance_library_version()  # raises ProviderBootstrapError if yfinance is not installed
    provider = YFinanceProvider()

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = run_fetch_fx(
        provider=provider,
        provider_config=provider_config,
        requested_pairs=args.pairs,
        start_date_inclusive=args.start_date_inclusive,
        end_date_exclusive=args.end_date_exclusive,
        timeout=args.timeout,
        retrieved_at=retrieved_at,
        provider_library_version=provider_library_version,
        output_dir=args.output_dir,
    )
    extra = {"overall_status": result.overall_status, "output_dir": str(args.output_dir)}
    return _emit("fx fetch", ok=result.ok, findings=result.findings, as_json=args.json, extra=extra)


def _cmd_fx_bundle_validate(args: argparse.Namespace) -> int:
    findings = validate_fx_bundle(args.root)
    ok = not has_blocking(findings)
    return _emit("fx bundle-validate", ok=ok, findings=findings, as_json=args.json)


def _cmd_fx_bundle_replay(args: argparse.Namespace) -> int:
    transaction_result, findings = replay_fx_bundle(args.root, check_only=args.check)
    ok = not has_blocking(findings)
    drifted = args.check and transaction_result.status == "drift"
    extra = {"transaction_status": transaction_result.status}
    if drifted:
        extra["diffs"] = [{"relative_path": d.relative_path, "state": d.state} for d in transaction_result.diffs]
    return _emit("fx bundle-replay", ok=ok and not drifted, findings=findings, as_json=args.json, extra=extra)


def _cmd_fx_manifest_validate(args: argparse.Namespace) -> int:
    findings = validate_fx_manifest(args.manifest, pair_id=args.pair, as_of_date=args.as_of_date)
    ok = not has_blocking(findings)
    return _emit("fx manifest-validate", ok=ok, findings=findings, as_json=args.json)


def _cmd_fx_promote(args: argparse.Namespace) -> int:
    _reject_output_dir_inside_raw(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run = promote_fx_service(
        bundle_root=args.bundle_root,
        manifest_path=args.manifest,
        policy_path=args.policy,
        pair_id=args.pair,
        as_of_date=args.as_of_date,
        cutoff_instant=args.cutoff_instant,
        effective_at=args.effective_at,
        output_dir=args.output_dir,
        check_only=args.check,
    )
    drifted = args.check and run.transaction.status == "drift"
    extra = {
        "overall_status": run.outcome.overall_status,
        "selected_trade_date": run.outcome.selected_trade_date,
        "output_dir": str(args.output_dir),
        "transaction_status": run.transaction.status,
    }
    if drifted:
        extra["diffs"] = [{"relative_path": d.relative_path, "state": d.state} for d in run.transaction.diffs]
    return _emit("fx promote", ok=run.ok, findings=list(run.outcome.findings), as_json=args.json, extra=extra)


def _cmd_observations_merge(args: argparse.Namespace) -> int:
    _reject_output_dir_inside_raw(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if len(args.bundles) < 2:
        print("market-ingestion: observations merge requires at least two --bundle paths", file=sys.stderr)
        return EXIT_BOOTSTRAP_FAILURE
    _output_doc, validation_doc, merge_manifest_doc, transaction_result = merge_observation_bundles(
        bundle_paths=args.bundles, output_dir=args.output_dir, check_only=args.check,
    )
    findings = [
        Finding(
            rule_id=f["rule_id"], severity=f["severity"], scope=f["scope"], reason_code=f["reason_code"],
            message=f["message"], json_pointer=f.get("json_pointer", ""), relative_path=f.get("relative_path"),
        )
        for f in validation_doc["findings"]
    ]
    ok = merge_manifest_doc["overall_status"] == "valid"
    drifted = args.check and transaction_result.status == "drift"
    extra = {
        "overall_status": merge_manifest_doc["overall_status"],
        "total_observation_count": merge_manifest_doc["total_observation_count"],
        "output_dir": str(args.output_dir),
        "transaction_status": transaction_result.status,
    }
    if drifted:
        extra["diffs"] = [{"relative_path": d.relative_path, "state": d.state} for d in transaction_result.diffs]
    return _emit("observations merge", ok=ok and not drifted, findings=findings, as_json=args.json, extra=extra)


if __name__ == "__main__":
    sys.exit(main())
