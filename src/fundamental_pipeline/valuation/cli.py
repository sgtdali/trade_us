"""The ``valuation-pipeline`` command-line entry point.

Command surface (T70-B, docs/valuation-t70-06-validation-cli-transaction-specification.md
Section 6):

    valuation-pipeline market validate
    valuation-pipeline market resolve
    valuation-pipeline inputs validate
    valuation-pipeline inputs generate

Catalogs are loaded directly from their JSON files under
``config/valuation/**`` (no manifest/lock indirection, no
``--catalog-lock``-style argument on any subcommand); the ``catalog
validate``/``bundle validate`` subcommands existed only to verify that
manifest/lock machinery and have been removed along with it.

Exit codes:

    0 = success; warnings may exist; no drift
    1 = validation error/blocker, or drift in --check mode
    2 = invocation/bootstrap/configuration failure, unsafe path, or
        unsupported network/provider option

Generation commands (``market resolve``, ``inputs generate``) always
require an explicit ``--output-dir``; there is no default or inferred
production write root. ``--check`` compares against that explicit root and
performs zero writes. ``--json`` output is a stable machine-readable
envelope on stdout; human diagnostics go to stderr on failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..errors import PipelineError
from ..paths import repo_path
from ..public.financial_basis import FinancialPeriodRef
from .basis.service import generate_valuation_inputs, validate_valuation_inputs
from .catalogs import (
    load_catalog_registry,
    load_comparison_catalog_registry,
)
from .errors import BootstrapError, ValuationError
from .identity import MARKET_SNAPSHOT_PURPOSES, PRICE_MODE_PURPOSES
from .market.observations import PRICE_MODES
from .market.service import generate_market_snapshot, validate_market_snapshot
from .safe_json import read_safe_json
from .validation.findings import Finding, has_blocking
from ..technical.service import generate_technical_snapshot
from ..technical.validation import validate_technical_snapshot

EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILED = 1
EXIT_BOOTSTRAP_FAILURE = 2


def _finding_to_dict(finding: Finding) -> dict:
    return {
        "finding_id": finding.finding_id,
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "scope": finding.scope,
        "reason_code": finding.reason_code,
        "artifact_type": finding.artifact_type,
        "artifact_id": finding.artifact_id,
        "relative_path": finding.relative_path,
        "json_pointer": finding.json_pointer,
        "message": finding.message,
        "recoverability": finding.recoverability,
    }


def _emit_findings(command: str, findings: list[Finding], *, as_json: bool, warnings_as_errors: bool = False, extra: dict | None = None) -> int:
    blocking = has_blocking(findings, warnings_as_errors=warnings_as_errors)
    exit_code = EXIT_VALIDATION_FAILED if blocking else EXIT_SUCCESS

    if as_json:
        payload = {
            "command": command,
            "status": "invalid" if blocking else "valid",
            "exit_code": exit_code,
            "finding_counts": {
                "blocker": sum(1 for f in findings if f.severity == "blocker"),
                "error": sum(1 for f in findings if f.severity == "error"),
                "warning": sum(1 for f in findings if f.severity == "warning"),
                "info": sum(1 for f in findings if f.severity == "info"),
            },
            "findings": [_finding_to_dict(f) for f in findings],
        }
        if extra:
            payload.update(extra)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        if not findings:
            print(f"{command}: valid, no findings.")
        for finding in findings:
            print(f"{finding.severity.upper()} [{finding.rule_id}] {finding.message}")
        if blocking:
            print(f"Validation failed: {len(findings)} finding(s).", file=sys.stderr)
        else:
            print(f"Validation passed: {len(findings)} finding(s) (none blocking).")

    return exit_code


def _load_context_projection(context_file_arg: str, registry=None) -> dict:
    context_path = Path(context_file_arg).resolve()
    if not context_path.exists():
        raise BootstrapError(f"--context-file does not exist: {context_file_arg}")
    projection = read_safe_json(context_path, label=context_path.name)
    if not isinstance(projection, dict):
        raise BootstrapError("--context-file root must be a JSON object")
    required = ("ticker", "as_of_date", "cutoff_instant", "reporting_currency", "share_count_basis", "primary_price_mode", "purpose", "financial_period_refs")
    missing = [f for f in required if f not in projection]
    if missing:
        raise BootstrapError(f"--context-file is missing required field(s): {missing}")
    if projection["primary_price_mode"] not in PRICE_MODES:
        raise BootstrapError(f"--context-file primary_price_mode must be one of {sorted(PRICE_MODES)}")
    purpose = projection["purpose"]
    if purpose not in MARKET_SNAPSHOT_PURPOSES:
        raise BootstrapError(f"--context-file purpose must be one of {sorted(MARKET_SNAPSHOT_PURPOSES)}")
    if purpose not in PRICE_MODE_PURPOSES[projection["primary_price_mode"]]:
        raise BootstrapError(
            "--context-file primary_price_mode is not compatible with purpose: "
            f"{projection['primary_price_mode']!r} cannot be used for {purpose!r}"
        )
    return projection


def market_validate(args: argparse.Namespace) -> int:
    try:
        registry = load_catalog_registry(repo_root=repo_path())
        findings = validate_market_snapshot(
            manifest_path=Path(args.manifest).resolve(),
            snapshot_path=Path(args.snapshot).resolve(),
            catalog_registry=registry,
        )
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE
    return _emit_findings("market validate", findings, as_json=args.json)


def market_resolve(args: argparse.Namespace) -> int:
    try:
        registry = load_catalog_registry(repo_root=repo_path())
        context_projection = _load_context_projection(args.context_file, registry)
        if context_projection["ticker"] != args.ticker:
            raise BootstrapError("--context-file ticker does not match --ticker")
        if context_projection["as_of_date"] != args.as_of:
            raise BootstrapError("--context-file as_of_date does not match --as-of")
        if context_projection["cutoff_instant"] != args.cutoff_instant:
            raise BootstrapError("--context-file cutoff_instant does not match --cutoff-instant")

        result = generate_market_snapshot(
            manifest_path=Path(args.manifest).resolve(),
            observations_path=Path(args.observations).resolve(),
            ticker=args.ticker,
            as_of_date=args.as_of,
            cutoff_instant=args.cutoff_instant,
            context_projection=context_projection,
            catalog_registry=registry,
            output_dir=Path(args.output_dir).resolve(),
            check_only=args.check,
            additional_manifest_paths=tuple(Path(p).resolve() for p in (args.additional_manifest or [])),
            overrides_path=Path(args.overrides).resolve() if args.overrides else None,
            corporate_actions_path=Path(args.corporate_actions).resolve() if args.corporate_actions else None,
        )
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE

    extra = {"transaction": _transaction_to_dict(result.transaction)} if result.transaction else None
    exit_code = _emit_findings("market resolve", list(result.findings), as_json=args.json, extra=extra)
    if exit_code != EXIT_SUCCESS:
        return exit_code
    if result.transaction is not None and result.transaction.status == "drift":
        if not args.json:
            print(f"Drift detected: {result.transaction.diffs}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    return EXIT_SUCCESS


def inputs_validate(args: argparse.Namespace) -> int:
    try:
        registry = load_catalog_registry(repo_root=repo_path())
        root = Path(args.root).resolve() if args.root else None
        findings = validate_valuation_inputs(
            artifact_path=Path(args.artifact).resolve(), catalog_registry=registry,
            resolve_dependencies=args.resolve_dependencies, root=root,
        )
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE
    return _emit_findings("inputs validate", findings, as_json=args.json)


def _parse_period_ref(raw: str) -> FinancialPeriodRef:
    from datetime import date as date_type

    parts = raw.split(":")
    if len(parts) != 3:
        raise BootstrapError(f"--financial-period-ref must be 'SOURCE_ID:PERIOD_END:PERIOD_TYPE', got {raw!r}")
    source_id, period_end, period_type = parts
    try:
        parsed_end = date_type.fromisoformat(period_end)
    except ValueError as exc:
        raise BootstrapError(f"--financial-period-ref period_end is not an ISO date: {period_end!r}") from exc
    return FinancialPeriodRef(source_id, parsed_end, period_type)


def inputs_generate(args: argparse.Namespace) -> int:
    try:
        registry = load_catalog_registry(repo_root=repo_path())
        context_projection = _load_context_projection(args.context_file, registry)
        if context_projection["ticker"] != args.ticker:
            raise BootstrapError("--context-file ticker does not match --ticker")
        if context_projection["as_of_date"] != args.as_of:
            raise BootstrapError("--context-file as_of_date does not match --as-of")
        if context_projection["cutoff_instant"] != args.cutoff_instant:
            raise BootstrapError("--context-file cutoff_instant does not match --cutoff-instant")

        period_refs = tuple(_parse_period_ref(raw) for raw in args.financial_period_ref)

        result = generate_valuation_inputs(
            data_root=Path(args.data_root).resolve(),
            ticker=args.ticker,
            as_of_date=args.as_of,
            cutoff_instant=args.cutoff_instant,
            financial_period_refs=period_refs,
            market_snapshot_path=Path(args.market_snapshot).resolve(),
            context_projection=context_projection,
            catalog_registry=registry,
            output_dir=Path(args.output_dir).resolve(),
            check_only=args.check,
        )
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE

    extra = {"transaction": _transaction_to_dict(result.transaction)} if result.transaction else None
    exit_code = _emit_findings("inputs generate", list(result.findings), as_json=args.json, extra=extra)
    if exit_code != EXIT_SUCCESS:
        return exit_code
    if result.transaction is not None and result.transaction.status == "drift":
        if not args.json:
            print(f"Drift detected: {result.transaction.diffs}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    return EXIT_SUCCESS


def _transaction_to_dict(transaction) -> dict:
    # transaction.root is deliberately never included: it is always the
    # CLI's own .resolve()'d absolute output-dir path regardless of what
    # form --output-dir was given in, so including it would leak an
    # absolute host path into machine output even for a caller who only
    # ever typed a relative --output-dir (docs/valuation-t70-08-*.md
    # Section 18: the CLI execution envelope "must not record ...
    # absolute paths"). written_paths/unchanged_paths/diffs are already
    # governed-root-relative and carry no such risk.
    return {
        "status": transaction.status,
        "written_paths": list(transaction.written_paths),
        "unchanged_paths": list(transaction.unchanged_paths),
        "diffs": [{"relative_path": d.relative_path, "state": d.state} for d in transaction.diffs],
    }


def methods_catalog_validate(args: argparse.Namespace) -> int:
    """Compile the ``valuation.formulas.methods`` catalog and report
    success/failure -- distinct from generic ``catalog validate`` (which
    only checks manifest/lock/schema membership, not that every formula
    entry actually compiles to a safe AST plan)."""
    from .errors import FormulaCompileError, MethodCatalogError, UnitCompatibilityError
    from .methods.compiler import compile_method_catalog

    try:
        registry = load_catalog_registry(repo_root=repo_path())
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE

    try:
        compiled = compile_method_catalog(registry)
    except (MethodCatalogError, FormulaCompileError, UnitCompatibilityError, ValuationError) as exc:
        finding = Finding(rule_id="VAL-METHOD-002", severity="blocker", scope="catalog", reason_code="identity.schema_violation", message=str(exc))
        return _emit_findings("methods catalog-validate", [finding], as_json=args.json)

    extra = {"compiled_formula_count": len(compiled.formula_ids)} if args.json else None
    return _emit_findings("methods catalog-validate", [], as_json=args.json, extra=extra)


def methods_plan(args: argparse.Namespace) -> int:
    """Deterministic, non-numeric execution plan: resolved method set,
    ordered configured rows, formula/version/family/role, and
    applicability outcome. Calculates no value and writes nothing."""
    from .methods.applicability import CompanySelector, resolve_method_set_entry
    from .methods.method_sets import resolve_configured_rows

    try:
        registry = load_catalog_registry(repo_root=repo_path())
        selector = CompanySelector(ticker=args.ticker, company_type=args.company_type, sector_module=args.sector_module)
        method_set_entry = resolve_method_set_entry(selector, registry)
        rows = resolve_configured_rows(method_set_entry, registry)
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE

    plan = {
        "method_set_id": method_set_entry["entry_id"],
        "method_set_version": method_set_entry["entry_version"],
        "rows": [
            {"method_id": r.method_id, "formula_id": r.formula_id, "role": r.role, "outcome": r.outcome, "requires": list(r.requires)}
            for r in rows
        ],
    }
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"method_set: {plan['method_set_id']}@{plan['method_set_version']}")
        for row in plan["rows"]:
            print(f"  {row['method_id']:<55} role={row['role']:<11} outcome={row['outcome']}")
    return EXIT_SUCCESS


def results_generate_current(args: argparse.Namespace) -> int:
    from .results import CompanyContext, generate_current_results

    try:
        registry = load_catalog_registry(repo_root=repo_path())
        result = generate_current_results(
            valuation_inputs_path=Path(args.inputs).resolve(),
            company_context=CompanyContext(ticker=args.ticker, company_type=args.company_type, sector_module=args.sector_module),
            method_set_id=args.method_set,
            engine_version=args.engine_version,
            catalog_registry=registry,
            output_dir=Path(args.output_dir).resolve(),
            check_only=args.check,
        )
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE

    extra = {"transaction": _transaction_to_dict(result.transaction)} if result.transaction else None
    exit_code = _emit_findings("results generate-current", list(result.findings), as_json=args.json, extra=extra)
    if exit_code != EXIT_SUCCESS:
        return exit_code
    if result.transaction is not None and result.transaction.status == "drift":
        if not args.json:
            print(f"Drift detected: {result.transaction.diffs}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    return EXIT_SUCCESS


def results_check_current(args: argparse.Namespace) -> int:
    args.check = True
    return results_generate_current(args)


def results_validate(args: argparse.Namespace) -> int:
    from .results import validate_current_results

    try:
        registry = load_catalog_registry(repo_root=repo_path())
        findings = validate_current_results(artifact_path=Path(args.artifact).resolve(), catalog_registry=registry)
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE
    return _emit_findings("results validate", findings, as_json=args.json)


def _parse_financial_period_refs(raw_list: list[str]):
    return tuple(_parse_period_ref(raw) for raw in raw_list)


def _print_comparison_plan(args: argparse.Namespace, *, variant: str, extra: dict) -> int:
    """Shared T74-B ``... plan`` print/JSON envelope: the caller has
    already resolved the compiled comparison plan for one variant
    (calculating nothing, writing nothing -- docs/valuation-t74-06-*.md
    Section 11); this only formats it."""
    payload = {"variant": variant}
    payload.update(extra)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"variant: {variant}")
        for key, value in extra.items():
            print(f"  {key}: {value}")
    return EXIT_SUCCESS


def comparison_historical_plan(args: argparse.Namespace) -> int:
    from .comparison.compiler import compile_comparison_policies

    try:
        registry = load_comparison_catalog_registry(repo_root=repo_path())
        plan = compile_comparison_policies(registry)
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE
    rp = plan.ranking_policies["historical_self"]
    return _print_comparison_plan(
        args, variant="historical_self", extra={"direction": rp.direction, "policy_id": rp.policy_id},
    )


def comparison_historical_generate(args: argparse.Namespace) -> int:
    from .comparison.service import generate_historical_comparison

    try:
        registry = load_comparison_catalog_registry(repo_root=repo_path())
        result = generate_historical_comparison(
            subject_result_path=Path(args.subject_result).resolve(), history_path=Path(args.history).resolve(),
            current_observation_ref=args.current_observation_ref, current_value=args.current_value,
            as_of_date=args.as_of, generated_at=args.generated_at, engine_version=args.engine_version,
            comparison_registry=registry, output_dir=Path(args.output_dir).resolve(), check_only=args.check,
        )
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE

    extra = {"transaction": _transaction_to_dict(result.transaction)} if result.transaction else None
    exit_code = _emit_findings("comparison historical generate", list(result.findings), as_json=args.json, extra=extra)
    if exit_code != EXIT_SUCCESS:
        return exit_code
    if result.transaction is not None and result.transaction.status == "drift":
        if not args.json:
            print(f"Drift detected: {result.transaction.diffs}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    return EXIT_SUCCESS


def comparison_historical_check(args: argparse.Namespace) -> int:
    args.check = True
    return comparison_historical_generate(args)


def comparison_peer_plan(args: argparse.Namespace) -> int:
    from .comparison.compiler import compile_comparison_policies

    try:
        registry = load_comparison_catalog_registry(repo_root=repo_path())
        plan = compile_comparison_policies(registry)
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE
    rp = plan.ranking_policies["sector_peer"]
    return _print_comparison_plan(
        args, variant="sector_peer", extra={"direction": rp.direction, "policy_id": rp.policy_id},
    )


def comparison_peer_generate(args: argparse.Namespace) -> int:
    from .comparison.service import generate_peer_comparison

    try:
        registry = load_comparison_catalog_registry(repo_root=repo_path())
        result = generate_peer_comparison(
            subject_result_path=Path(args.subject_result).resolve(), universe_path=Path(args.universe).resolve(),
            observations_path=Path(args.observations).resolve(), subject_ticker=args.ticker, subject_value=args.subject_value,
            method_family_id=args.method, as_of_date=args.as_of, generated_at=args.generated_at, engine_version=args.engine_version,
            comparison_registry=registry, output_dir=Path(args.output_dir).resolve(), check_only=args.check,
        )
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE

    extra = {"transaction": _transaction_to_dict(result.transaction)} if result.transaction else None
    exit_code = _emit_findings("comparison peer generate", list(result.findings), as_json=args.json, extra=extra)
    if exit_code != EXIT_SUCCESS:
        return exit_code
    if result.transaction is not None and result.transaction.status == "drift":
        if not args.json:
            print(f"Drift detected: {result.transaction.diffs}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    return EXIT_SUCCESS


def comparison_peer_check(args: argparse.Namespace) -> int:
    args.check = True
    return comparison_peer_generate(args)


def diagnostics_piotroski_plan(args: argparse.Namespace) -> int:
    from .comparison.compiler import compile_comparison_policies

    try:
        registry = load_comparison_catalog_registry(repo_root=repo_path())
        plan = compile_comparison_policies(registry)
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE
    pp = plan.piotroski_policy
    return _print_comparison_plan(
        args, variant="piotroski_diagnostic",
        extra={"diagnostic_id": pp.diagnostic_id, "company_type_applicability": list(pp.company_type_applicability)},
    )


def diagnostics_piotroski_generate(args: argparse.Namespace) -> int:
    from .comparison.service import generate_piotroski_diagnostic

    try:
        registry = load_comparison_catalog_registry(repo_root=repo_path())
        result = generate_piotroski_diagnostic(
            ticker=args.ticker, company_type=args.company_type, facts_path=Path(args.facts).resolve(),
            as_of_date=args.as_of, generated_at=args.generated_at, engine_version=args.engine_version,
            comparison_registry=registry, output_dir=Path(args.output_dir).resolve(), check_only=args.check,
        )
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE

    extra = {"transaction": _transaction_to_dict(result.transaction)} if result.transaction else None
    exit_code = _emit_findings("diagnostics piotroski generate", list(result.findings), as_json=args.json, extra=extra)
    if exit_code != EXIT_SUCCESS:
        return exit_code
    if result.transaction is not None and result.transaction.status == "drift":
        if not args.json:
            print(f"Drift detected: {result.transaction.diffs}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    return EXIT_SUCCESS


def diagnostics_piotroski_check(args: argparse.Namespace) -> int:
    args.check = True
    return diagnostics_piotroski_generate(args)


def diagnostics_magic_formula_plan(args: argparse.Namespace) -> int:
    from .comparison.compiler import compile_comparison_policies

    try:
        registry = load_comparison_catalog_registry(repo_root=repo_path())
        plan = compile_comparison_policies(registry)
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE
    mp = plan.magic_formula_policy
    return _print_comparison_plan(
        args, variant="magic_formula_diagnostic",
        extra={"diagnostic_id": mp.diagnostic_id, "denominator_floor_ratio": mp.denominator_floor_ratio},
    )


def diagnostics_magic_formula_generate(args: argparse.Namespace) -> int:
    from .comparison.service import generate_magic_formula_diagnostic

    try:
        registry = load_comparison_catalog_registry(repo_root=repo_path())
        result = generate_magic_formula_diagnostic(
            ticker=args.ticker, facts_path=Path(args.facts).resolve(),
            as_of_date=args.as_of, generated_at=args.generated_at, engine_version=args.engine_version,
            comparison_registry=registry, output_dir=Path(args.output_dir).resolve(), check_only=args.check,
        )
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE

    extra = {"transaction": _transaction_to_dict(result.transaction)} if result.transaction else None
    exit_code = _emit_findings("diagnostics magic-formula generate", list(result.findings), as_json=args.json, extra=extra)
    if exit_code != EXIT_SUCCESS:
        return exit_code
    if result.transaction is not None and result.transaction.status == "drift":
        if not args.json:
            print(f"Drift detected: {result.transaction.diffs}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    return EXIT_SUCCESS


def diagnostics_magic_formula_check(args: argparse.Namespace) -> int:
    args.check = True
    return diagnostics_magic_formula_generate(args)


def comparison_validate(args: argparse.Namespace) -> int:
    """Shared T74-B ``... validate`` implementation across all five
    variants: schema + VAL-COMP/CAT-APP structural/referential validate a
    candidate ``valuation_comparison`` artifact; computes and writes
    nothing (docs/valuation-t74-06-*.md Section 11)."""
    from .comparison.validation import validate_valuation_comparison
    from .schemas import iter_schema_errors

    try:
        registry = load_comparison_catalog_registry(repo_root=repo_path())
        input_path = Path(args.input).resolve()
        if not input_path.exists():
            raise BootstrapError(f"--input file does not exist: {args.input}")
        artifact = read_safe_json(input_path, label=input_path.name)
        if not isinstance(artifact, dict):
            raise BootstrapError("--input root must be a JSON object")

        findings = [Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", json_pointer="/" + "/".join(str(p) for p in e.path), message=e.message) for e in iter_schema_errors("valuation-comparison", artifact)]
        findings.extend(validate_valuation_comparison(artifact, registry=registry))
    except (ValuationError, PipelineError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE

    return _emit_findings("comparison validate", findings, as_json=args.json)


def _print_bootstrap_error(exc: Exception, *, as_json: bool) -> None:
    message = f"{type(exc).__name__}: {exc}"
    if as_json:
        print(json.dumps({"status": "bootstrap_error", "exit_code": EXIT_BOOTSTRAP_FAILURE, "message": message}, ensure_ascii=False, indent=2))
    else:
        print(f"ERROR: {message}", file=sys.stderr)


def report_generate(args: argparse.Namespace) -> int:
    from .reporting.service import generate_valuation_report

    output_dir = Path(args.output_dir).resolve() if args.output_dir else None

    try:
        report_text, errors = generate_valuation_report(
            ticker=args.ticker,
            as_of_date=args.as_of,
            context_id=args.context_id,
            latest_period=args.latest_period,
            fy_period=args.fy_period,
            output_dir=output_dir,
        )
        if not args.json:
            if output_dir is None:
                print(report_text)
            else:
                print(f"Valuation report generated successfully under: {output_dir}")
        else:
            print(json.dumps({"status": "success", "report": report_text}, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS
    except Exception as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE


def report_validate(args: argparse.Namespace) -> int:
    from .reporting.service import validate_valuation_report

    report_path = Path(args.report).resolve()
    if not report_path.exists():
        raise BootstrapError(f"--report file does not exist: {args.report}")

    try:
        report_text = report_path.read_text(encoding="utf-8")
        errors = validate_valuation_report(
            ticker=args.ticker,
            as_of_date=args.as_of,
            context_id=args.context_id,
            latest_period=args.latest_period,
            fy_period=args.fy_period,
            report_text=report_text,
        )

        if errors:
            findings = [Finding(rule_id="VAL-REP-001", severity="error", scope="report", message=err) for err in errors]
            return _emit_findings("report validate", findings, as_json=args.json)

        if not args.json:
            print("Validation passed: 0 finding(s) (none blocking).")
        else:
            print(json.dumps({"status": "success", "findings": []}, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS
    except Exception as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE


def report_check(args: argparse.Namespace) -> int:
    from .reporting.service import check_valuation_report

    output_dir = Path(args.output_dir).resolve()

    try:
        errors = check_valuation_report(
            ticker=args.ticker,
            as_of_date=args.as_of,
            context_id=args.context_id,
            latest_period=args.latest_period,
            fy_period=args.fy_period,
            output_dir=output_dir,
        )

        if errors:
            findings = [Finding(rule_id="VAL-REP-002", severity="error", scope="report", message=err) for err in errors]
            return _emit_findings("report check", findings, as_json=args.json)

        if not args.json:
            print("Report check passed: report is present and matches the recompiled results byte-for-byte.")
        else:
            print(json.dumps({"status": "success", "findings": []}, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS
    except Exception as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE


def technical_generate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    check_mode = getattr(args, "check", False)
    artifact, findings = generate_technical_snapshot(
        ticker=args.ticker,
        as_of_date=args.as_of,
        generated_at=args.generated_at,
        engine_version=args.engine_version,
        output_dir=output_dir,
        check=check_mode,
        lookback_days=getattr(args, "lookback_days", 400),
    )
    if check_mode:
        target_path = output_dir / args.ticker / f"{args.as_of}.json"
        if not target_path.exists():
            findings.append(
                Finding(
                    rule_id="TECH-CHECK-001",
                    severity="error",
                    scope="artifact",
                    message=f"target technical snapshot artifact missing in --check mode: {target_path}",
                    reason_code="artifact.missing",
                )
            )
        else:
            existing = read_safe_json(target_path)
            if existing != artifact:
                findings.append(
                    Finding(
                        rule_id="TECH-CHECK-002",
                        severity="error",
                        scope="artifact",
                        message=f"drift detected in technical snapshot artifact: {target_path}",
                        reason_code="artifact.drift_detected",
                    )
                )
    return _emit_findings("technical generate" if not check_mode else "technical check", findings, as_json=args.json)


def technical_check(args: argparse.Namespace) -> int:
    args.check = True
    return technical_generate(args)


def technical_validate(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        findings = [
            Finding(
                rule_id="TECH-VAL-001",
                severity="blocker",
                scope="artifact",
                message=f"technical snapshot input file not found: {input_path}",
                reason_code="file.not_found",
            )
        ]
        return _emit_findings("technical validate", findings, as_json=args.json)
    data = read_safe_json(input_path)
    findings = validate_technical_snapshot(data, relative_path=str(input_path))
    return _emit_findings("technical validate", findings, as_json=args.json)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="valuation-pipeline")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON output")
    sub = parser.add_subparsers(dest="cmd", required=True)

    market_parser = sub.add_parser("market", help="offline market snapshot operations")
    market_sub = market_parser.add_subparsers(dest="market_cmd", required=True)

    market_validate_parser = market_sub.add_parser("validate", help="validate a committed market-snapshot artifact")
    market_validate_parser.add_argument("--manifest", required=True)
    market_validate_parser.add_argument("--snapshot", required=True)
    market_validate_parser.set_defaults(func=market_validate)

    market_resolve_parser = market_sub.add_parser("resolve", help="resolve a market snapshot from a local manifest and injected observations")
    market_resolve_parser.add_argument("--manifest", required=True)
    market_resolve_parser.add_argument(
        "--additional-manifest", action="append", dest="additional_manifest",
        help="an independent additional market-source manifest for authority-first cross-source comparison (repeatable)",
    )
    market_resolve_parser.add_argument("--observations", required=True)
    market_resolve_parser.add_argument(
        "--overrides", help="a local {\"overrides\": [...]} file of governed manual override records (repeatable is not needed -- one file may list several)",
    )
    market_resolve_parser.add_argument(
        "--corporate-actions",
        help="a governed corporate-action bundle (schemas/corporate-action-bundle.schema.json); "
             "when absent, corporate_action_state stays events: [] / coverage_status: 'unknown'",
    )
    market_resolve_parser.add_argument("--ticker", required=True)
    market_resolve_parser.add_argument("--as-of", required=True)
    market_resolve_parser.add_argument("--cutoff-instant", required=True)
    market_resolve_parser.add_argument("--context-file", required=True)
    market_resolve_parser.add_argument("--output-dir", required=True)
    market_resolve_parser.add_argument("--check", action="store_true")
    market_resolve_parser.set_defaults(func=market_resolve)

    inputs_parser = sub.add_parser("inputs", help="valuation-inputs operations")
    inputs_sub = inputs_parser.add_subparsers(dest="inputs_cmd", required=True)

    inputs_validate_parser = inputs_sub.add_parser("validate", help="validate a committed valuation-inputs artifact")
    inputs_validate_parser.add_argument("--artifact", required=True)
    inputs_validate_parser.add_argument("--resolve-dependencies", action="store_true")
    inputs_validate_parser.add_argument("--root")
    inputs_validate_parser.set_defaults(func=inputs_validate)

    inputs_generate_parser = inputs_sub.add_parser("generate", help="generate valuation inputs from an accepted market snapshot and authored fundamental periods")
    inputs_generate_parser.add_argument("--data-root", required=True)
    inputs_generate_parser.add_argument("--ticker", required=True)
    inputs_generate_parser.add_argument("--as-of", required=True)
    inputs_generate_parser.add_argument("--cutoff-instant", required=True)
    inputs_generate_parser.add_argument("--financial-period-ref", action="append", required=True, dest="financial_period_ref")
    inputs_generate_parser.add_argument("--market-snapshot", required=True)
    inputs_generate_parser.add_argument("--context-file", required=True)
    inputs_generate_parser.add_argument("--output-dir", required=True)
    inputs_generate_parser.add_argument("--check", action="store_true")
    inputs_generate_parser.set_defaults(func=inputs_generate)

    methods_parser = sub.add_parser("methods", help="T71 method catalog/plan operations")
    methods_sub = methods_parser.add_subparsers(dest="methods_cmd", required=True)

    methods_catalog_validate_parser = methods_sub.add_parser("catalog-validate", help="compile the method-formula catalog and report success/failure")
    methods_catalog_validate_parser.add_argument("--manifest", required=False, help="unused; accepted for CLI symmetry with 'catalog validate'")
    methods_catalog_validate_parser.set_defaults(func=methods_catalog_validate)

    methods_plan_parser = methods_sub.add_parser("plan", help="resolve and print the ordered configured method-set plan; calculates nothing, writes nothing")
    methods_plan_parser.add_argument("--ticker", required=True)
    methods_plan_parser.add_argument("--company-type", required=True)
    methods_plan_parser.add_argument("--sector-module", required=True)
    methods_plan_parser.set_defaults(func=methods_plan)

    results_parser = sub.add_parser("results", help="T71 current-method valuation-results operations")
    results_sub = results_parser.add_subparsers(dest="results_cmd", required=True)

    results_generate_parser = results_sub.add_parser("generate-current", help="generate a current valuation-results artifact from a valuation-inputs artifact")
    results_generate_parser.add_argument("--inputs", required=True, help="path to a committed valuation-inputs.json")
    results_generate_parser.add_argument("--ticker", required=True)
    results_generate_parser.add_argument("--company-type", required=True)
    results_generate_parser.add_argument("--sector-module", required=True)
    results_generate_parser.add_argument("--method-set", help="exact method_set_id the resolved router result must match (optional cross-check)")
    results_generate_parser.add_argument("--engine-version", required=True)
    results_generate_parser.add_argument("--output-dir", required=True)
    results_generate_parser.add_argument("--check", action="store_true")
    results_generate_parser.set_defaults(func=results_generate_current)

    results_check_parser = results_sub.add_parser("check-current", help="alias for 'results generate-current --check': zero-write drift check")
    results_check_parser.add_argument("--inputs", required=True)
    results_check_parser.add_argument("--ticker", required=True)
    results_check_parser.add_argument("--company-type", required=True)
    results_check_parser.add_argument("--sector-module", required=True)
    results_check_parser.add_argument("--method-set")
    results_check_parser.add_argument("--engine-version", required=True)
    results_check_parser.add_argument("--output-dir", required=True)
    results_check_parser.set_defaults(func=results_check_current, check=True)

    results_validate_parser = results_sub.add_parser("validate", help="validate a committed valuation-results artifact")
    results_validate_parser.add_argument("--artifact", required=True)
    results_validate_parser.set_defaults(func=results_validate)

    comparison_parser = sub.add_parser("comparison", help="T74-B historical/peer comparison operations")
    comparison_sub = comparison_parser.add_subparsers(dest="comparison_cmd", required=True)

    historical_parser = comparison_sub.add_parser("historical", help="a company's position within its own governed monthly history for one method")
    historical_sub = historical_parser.add_subparsers(dest="historical_cmd", required=True)

    historical_plan_parser = historical_sub.add_parser("plan", help="resolve the compiled historical_self policy; computes and writes nothing")
    historical_plan_parser.set_defaults(func=comparison_historical_plan)

    def _add_historical_generate_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--subject-result", required=True, help="path to a committed valuation-results(-scenario).json")
        p.add_argument("--history", required=True, help="path to a governed local valuation_comparison_observations.json (observation_kind=historical_monthly)")
        p.add_argument("--current-observation-ref", required=True, help="the subject's own current observation_id -- never itself a comparator sample member")
        p.add_argument("--current-value", required=True, help="the subject's own current canonical decimal value")
        p.add_argument("--as-of", required=True)
        p.add_argument("--generated-at", required=True)
        p.add_argument("--engine-version", required=True)
        p.add_argument("--output-dir", required=True)

    historical_generate_parser = historical_sub.add_parser("generate", help="generate a historical_self valuation_comparison artifact")
    _add_historical_generate_args(historical_generate_parser)
    historical_generate_parser.add_argument("--check", action="store_true")
    historical_generate_parser.set_defaults(func=comparison_historical_generate)

    historical_check_parser = historical_sub.add_parser("check", help="alias for 'historical generate --check': zero-write drift check")
    _add_historical_generate_args(historical_check_parser)
    historical_check_parser.set_defaults(func=comparison_historical_check, check=True)

    historical_validate_parser = historical_sub.add_parser("validate", help="schema + VAL-COMP structural/referential validate a candidate historical artifact; computes and writes nothing")
    historical_validate_parser.add_argument("--input", required=True)
    historical_validate_parser.set_defaults(func=comparison_validate)

    peer_parser = comparison_sub.add_parser("peer", help="a company's position within an authored, approved peer universe for one method")
    peer_sub = peer_parser.add_subparsers(dest="peer_cmd", required=True)

    peer_plan_parser = peer_sub.add_parser("plan", help="resolve the compiled sector_peer policy; computes and writes nothing")
    peer_plan_parser.set_defaults(func=comparison_peer_plan)

    def _add_peer_generate_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--subject-result", required=True, help="path to a committed valuation-results(-scenario).json")
        p.add_argument("--universe", required=True, help="path to an approved valuation_peer_universe.json")
        p.add_argument("--observations", required=True, help="path to a governed local valuation_comparison_observations.json (observation_kind=peer_member)")
        p.add_argument("--ticker", required=True, help="the subject's own ticker -- excluded from the peer sample exactly once")
        p.add_argument("--subject-value", required=True, help="the subject's own canonical decimal value for this method")
        p.add_argument("--method", required=True, help="the exact registered method_family_id shared by subject and universe")
        p.add_argument("--as-of", required=True)
        p.add_argument("--generated-at", required=True)
        p.add_argument("--engine-version", required=True)
        p.add_argument("--output-dir", required=True)

    peer_generate_parser = peer_sub.add_parser("generate", help="generate a sector_peer valuation_comparison artifact")
    _add_peer_generate_args(peer_generate_parser)
    peer_generate_parser.add_argument("--check", action="store_true")
    peer_generate_parser.set_defaults(func=comparison_peer_generate)

    peer_check_parser = peer_sub.add_parser("check", help="alias for 'peer generate --check': zero-write drift check")
    _add_peer_generate_args(peer_check_parser)
    peer_check_parser.set_defaults(func=comparison_peer_check, check=True)

    peer_validate_parser = peer_sub.add_parser("validate", help="schema + VAL-COMP structural/referential validate a candidate peer artifact; computes and writes nothing")
    peer_validate_parser.add_argument("--input", required=True)
    peer_validate_parser.set_defaults(func=comparison_validate)

    diagnostics_parser = sub.add_parser("diagnostics", help="T74-B Piotroski/Magic Formula strategy diagnostics")
    diagnostics_sub = diagnostics_parser.add_subparsers(dest="diagnostics_cmd", required=True)

    piotroski_parser = diagnostics_sub.add_parser("piotroski", help="nine-component Piotroski F-Score diagnostic")
    piotroski_sub = piotroski_parser.add_subparsers(dest="piotroski_cmd", required=True)

    piotroski_plan_parser = piotroski_sub.add_parser("plan", help="resolve the compiled Piotroski policy; computes and writes nothing")
    piotroski_plan_parser.set_defaults(func=diagnostics_piotroski_plan)

    def _add_piotroski_generate_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ticker", required=True)
        p.add_argument("--company-type", required=True, help="must be a registered company_type_applicability value or every component is not_applicable")
        p.add_argument("--facts", required=True, help="path to a governed local JSON facts file (roa_t, roa_t1, cfo_t, cfoa_t, leverage_t, leverage_t1, current_ratio_t, current_ratio_t1, equity_issuance_amount_t, gross_margin_t, gross_margin_t1, asset_turnover_t, asset_turnover_t1 -- each a decimalEnvelope)")
        p.add_argument("--as-of", required=True)
        p.add_argument("--generated-at", required=True)
        p.add_argument("--engine-version", required=True)
        p.add_argument("--output-dir", required=True)

    piotroski_generate_parser = piotroski_sub.add_parser("generate", help="generate a piotroski_diagnostic valuation_comparison artifact")
    _add_piotroski_generate_args(piotroski_generate_parser)
    piotroski_generate_parser.add_argument("--check", action="store_true")
    piotroski_generate_parser.set_defaults(func=diagnostics_piotroski_generate)

    piotroski_check_parser = piotroski_sub.add_parser("check", help="alias for 'piotroski generate --check': zero-write drift check")
    _add_piotroski_generate_args(piotroski_check_parser)
    piotroski_check_parser.set_defaults(func=diagnostics_piotroski_check, check=True)

    piotroski_validate_parser = piotroski_sub.add_parser("validate", help="schema + VAL-COMP structural/referential validate a candidate Piotroski artifact; computes and writes nothing")
    piotroski_validate_parser.add_argument("--input", required=True)
    piotroski_validate_parser.set_defaults(func=comparison_validate)

    magic_formula_parser = diagnostics_sub.add_parser("magic-formula", help="Greenblatt-compatible Magic Formula (earnings yield / return on capital) diagnostic")
    magic_formula_sub = magic_formula_parser.add_subparsers(dest="magic_formula_cmd", required=True)

    magic_formula_plan_parser = magic_formula_sub.add_parser("plan", help="resolve the compiled Magic Formula policy; computes and writes nothing")
    magic_formula_plan_parser.set_defaults(func=diagnostics_magic_formula_plan)

    def _add_magic_formula_generate_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ticker", required=True)
        p.add_argument("--facts", required=True, help="path to a governed local JSON facts file (ebit, enterprise_value, net_working_capital, net_operating_fixed_assets, revenue, total_assets -- each a decimalEnvelope; optional lease_basis_compatible boolean)")
        p.add_argument("--as-of", required=True)
        p.add_argument("--generated-at", required=True)
        p.add_argument("--engine-version", required=True)
        p.add_argument("--output-dir", required=True)

    magic_formula_generate_parser = magic_formula_sub.add_parser("generate", help="generate a magic_formula_diagnostic valuation_comparison artifact")
    _add_magic_formula_generate_args(magic_formula_generate_parser)
    magic_formula_generate_parser.add_argument("--check", action="store_true")
    magic_formula_generate_parser.set_defaults(func=diagnostics_magic_formula_generate)

    magic_formula_check_parser = magic_formula_sub.add_parser("check", help="alias for 'magic-formula generate --check': zero-write drift check")
    _add_magic_formula_generate_args(magic_formula_check_parser)
    magic_formula_check_parser.set_defaults(func=diagnostics_magic_formula_check, check=True)

    magic_formula_validate_parser = magic_formula_sub.add_parser("validate", help="schema + VAL-COMP structural/referential validate a candidate Magic Formula artifact; computes and writes nothing")
    magic_formula_validate_parser.add_argument("--input", required=True)
    magic_formula_validate_parser.set_defaults(func=comparison_validate)

    report_parser = sub.add_parser("report", help="valuation Markdown report operations")
    report_sub = report_parser.add_subparsers(dest="report_cmd", required=True)

    def _add_report_common_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ticker", required=True)
        p.add_argument("--as-of", required=True)
        p.add_argument("--context-id", required=True)
        p.add_argument("--latest-period", required=True)
        p.add_argument("--fy-period", required=True)

    report_generate_parser = report_sub.add_parser("generate", help="generate a valuation Markdown report")
    _add_report_common_args(report_generate_parser)
    report_generate_parser.add_argument("--output-dir", required=False, help="optional output directory to write report to")
    report_generate_parser.set_defaults(func=report_generate)

    report_validate_parser = report_sub.add_parser("validate", help="validate a valuation Markdown report against forbidden patterns and method reporting rules")
    _add_report_common_args(report_validate_parser)
    report_validate_parser.add_argument("--report", required=True, help="path to the Markdown report file")
    report_validate_parser.set_defaults(func=report_validate)

    report_check_parser = report_sub.add_parser("check", help="check that the valuation report is present and matches the recompiled output byte-for-byte")
    _add_report_common_args(report_check_parser)
    report_check_parser.add_argument("--output-dir", required=True, help="output directory containing the report")
    report_check_parser.set_defaults(func=report_check)

    technical_parser = sub.add_parser("technical", help="technical analysis snapshot operations")
    technical_sub = technical_parser.add_subparsers(dest="technical_cmd", required=True)

    def _add_technical_generate_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ticker", required=True)
        p.add_argument("--as-of", required=True)
        p.add_argument("--generated-at", required=True)
        p.add_argument("--engine-version", required=True)
        p.add_argument("--output-dir", required=True)
        p.add_argument("--lookback-days", type=int, default=400, help="calendar days lookback for trailing price history (default: 400)")

    technical_generate_parser = technical_sub.add_parser("generate", help="generate a technical_snapshot artifact")
    _add_technical_generate_args(technical_generate_parser)
    technical_generate_parser.add_argument("--check", action="store_true")
    technical_generate_parser.set_defaults(func=technical_generate)

    technical_check_parser = technical_sub.add_parser("check", help="alias for 'technical generate --check': zero-write drift check")
    _add_technical_generate_args(technical_check_parser)
    technical_check_parser.set_defaults(func=technical_check, check=True)

    technical_validate_parser = technical_sub.add_parser("validate", help="validate a technical_snapshot artifact against its schema")
    technical_validate_parser.add_argument("--input", required=True)
    technical_validate_parser.set_defaults(func=technical_validate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (PipelineError, ValuationError) as exc:
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE
    except Exception as exc:  # noqa: BLE001 - CLI boundary: surface any failure as a clean, non-leaking error exit
        _print_bootstrap_error(exc, as_json=args.json)
        return EXIT_BOOTSTRAP_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
