"""Current-results service adapter: loads the exact valuation-inputs
artifact, resolves the method set, compiles/binds/evaluates every
configured row, assembles the provisional artifact, validates it, and
performs check/transactional-write behavior
(docs/valuation-t71-06-validation-cli-transaction-specification.md Section 11).

Generation sequence exactly as specified: safe-load dependencies -> verify
exact refs -> compile methods and resolve set -> bind/evaluate complete
bundle in memory -> assemble provisional result -> validate ->
attach/recompute validation summary -> final-validate -> stage canonical
bytes -> verify staged bytes -> promote in sorted order (all via the
existing T70 transaction writer -- never a second implementation).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes
from ..catalogs import CatalogRegistry
from ..errors import ApplicabilityError, ValuationError
from ..paths import valuation_results_relative_path
from ..safe_json import read_safe_json
from ..schemas import iter_schema_errors
from ..transaction import TransactionResult, WriteTarget, check_transaction, execute_transaction
from ..validation.findings import Finding, sort_findings
from ..validation.methods import validate_method_results
from .assembler import CurrentRunRequest, assemble_current_results


class CurrentResultsGenerationResult:
    def __init__(self, *, findings: tuple[Finding, ...], artifact: dict[str, Any] | None, transaction: TransactionResult | None):
        self.findings = findings
        self.artifact = artifact
        self.transaction = transaction

    @property
    def ok(self) -> bool:
        return not any(f.severity in ("blocker", "error") for f in self.findings)


@dataclass(frozen=True)
class CompanyContext:
    ticker: str
    company_type: str
    sector_module: str


def _apply_comparability_restrictions(evaluations, valuation_inputs: dict[str, Any]):
    """Keep issuer-specific APM methods visible but out of current-use/ranking."""
    issuer_specific_basis_refs = {
        entry.get("earnings_basis_id")
        for entry in valuation_inputs.get("earnings_bases", ())
        if entry.get("comparability") == "issuer_specific_only"
    }
    restricted = []
    for evaluation in evaluations:
        denominator_ref = evaluation.denominator.basis_ref if evaluation.denominator else None
        if denominator_ref in issuer_specific_basis_refs:
            evaluation = replace(evaluation, current_use_eligible=False, ranking_eligible=False)
        restricted.append(evaluation)
    return restricted


def load_valuation_inputs(path: Path, *, catalog_registry: CatalogRegistry) -> tuple[dict[str, Any] | None, list[Finding]]:
    if not path.exists():
        return None, [Finding(rule_id="VAL-ID-101", severity="blocker", scope="bundle", reason_code="identity.resource_missing", message=f"missing valuation-inputs artifact: {path.name}")]
    artifact = read_safe_json(path, label=path.name)
    if not isinstance(artifact, dict):
        return None, [Finding(rule_id="VAL-ID-103", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message="valuation-inputs root must be a JSON object")]
    schema_errors = list(iter_schema_errors("valuation-inputs", artifact))
    if schema_errors:
        findings = [
            Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", json_pointer="/" + "/".join(str(p) for p in e.path), message=e.message)
            for e in schema_errors
        ]
        return None, findings
    return artifact, []


def generate_current_results(
    *,
    valuation_inputs_path: Path,
    company_context: CompanyContext,
    method_set_id: str | None,
    engine_version: str,
    catalog_registry: CatalogRegistry,
    output_dir: Path,
    check_only: bool = False,
) -> CurrentResultsGenerationResult:
    from ..methods.applicability import CompanySelector, resolve_method_set_entry
    from ..methods.compiler import compile_method_catalog
    from ..methods.evaluator import evaluate_method
    from ..methods.method_sets import resolve_configured_rows
    from ..methods.operands import bind_operands

    findings: list[Finding] = []

    valuation_inputs, load_findings = load_valuation_inputs(valuation_inputs_path, catalog_registry=catalog_registry)
    findings.extend(load_findings)
    if valuation_inputs is None:
        return CurrentResultsGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    selector = CompanySelector(ticker=company_context.ticker, company_type=company_context.company_type, sector_module=company_context.sector_module)
    try:
        method_set_entry = resolve_method_set_entry(selector, catalog_registry)
        if method_set_id is not None and method_set_entry["entry_id"] != method_set_id:
            findings.append(Finding(
                rule_id="VAL-METHOD-001", severity="blocker", scope="bundle", reason_code="applicability.ticker_policy_missing",
                message=f"resolved method set {method_set_entry['entry_id']!r} does not match the requested --method-set {method_set_id!r}",
            ))
            return CurrentResultsGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)
        rows = resolve_configured_rows(method_set_entry, catalog_registry)
        compiled = compile_method_catalog(catalog_registry)
    except (ApplicabilityError, ValuationError) as exc:
        findings.append(Finding(rule_id="VAL-METHOD-001", severity="blocker", scope="bundle", reason_code="applicability.ticker_policy_missing", message=str(exc)))
        return CurrentResultsGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    evaluations = []
    for row in rows:
        plan = compiled.plan(row.formula_id)
        binding = bind_operands(plan.operand_declarations, valuation_inputs)
        evaluations.append(evaluate_method(plan, row, binding))
    evaluations = _apply_comparability_restrictions(evaluations, valuation_inputs)

    valuation_input_ref = {
        "artifact_id": valuation_inputs["artifact_id"],
        "artifact_type": "valuation_inputs",
        "relative_path": _valuation_inputs_relative_path_of(valuation_inputs_path),
    }
    request = CurrentRunRequest(
        ticker=company_context.ticker,
        company_ref=company_context.ticker,
        valuation_context_id=valuation_inputs["input_identity"]["context_id"],
        engine_version=engine_version,
        valuation_input_ref=valuation_input_ref,
        method_set_entry=method_set_entry,
        as_of_date=valuation_inputs["temporal_context"]["as_of_date"],
        cutoff_instant=valuation_inputs["temporal_context"]["cutoff_instant"],
    )
    provisional = assemble_current_results(request, evaluations)

    method_findings = validate_method_results(provisional, catalog_registry=catalog_registry)
    findings.extend(method_findings)
    schema_errors = list(iter_schema_errors("valuation-results", provisional))
    for error in schema_errors:
        findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", json_pointer="/" + "/".join(str(p) for p in error.path), message=error.message))

    blocking_count = sum(1 for f in method_findings if f.severity == "blocker")
    warning_count = sum(1 for f in method_findings if f.severity == "warning")
    final_artifact = dict(provisional)
    final_artifact["validation_summary"] = {
        "structurally_valid": blocking_count == 0 and not schema_errors,
        "finding_ids": [f.finding_id for f in method_findings],
        "blocking_finding_count": blocking_count,
        "warning_finding_count": warning_count,
    }

    final_errors = list(iter_schema_errors("valuation-results", final_artifact))
    if final_errors:
        for error in final_errors:
            findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", json_pointer="/" + "/".join(str(p) for p in error.path), message=error.message))
        return CurrentResultsGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    relative_path = valuation_results_relative_path(
        company_context.ticker, request.as_of_date, request.valuation_context_id,
    )
    target = WriteTarget(relative_path=relative_path, content=canonical_bytes(final_artifact))

    if check_only:
        transaction_result = check_transaction(output_dir, [target])
    else:
        transaction_result = execute_transaction(output_dir, [target])

    return CurrentResultsGenerationResult(findings=tuple(sort_findings(findings)), artifact=final_artifact, transaction=transaction_result)


def _valuation_inputs_relative_path_of(path: Path) -> str:
    """Best-effort root-relative form of ``path`` for the exact reference
    this run's ``valuation_input_ref`` carries -- callers that need an
    exact governed-root-relative path should prefer passing one directly;
    this fallback covers CLI invocations where only an absolute/relative
    filesystem path was given."""
    parts = path.parts
    if "data" in parts:
        idx = parts.index("data")
        return "/".join(parts[idx:])
    return path.name


def validate_current_results(*, artifact_path: Path, catalog_registry: CatalogRegistry) -> list[Finding]:
    """Independently recompute and verify a committed ``valuation-results``
    artifact's schema and method-result/coverage/bundle claims. Never
    trusts a stored value merely because it is schema-valid."""
    if not artifact_path.exists():
        return [Finding(rule_id="VAL-ID-101", severity="blocker", scope="bundle", reason_code="identity.resource_missing", message=f"missing artifact: {artifact_path.name}")]

    artifact = read_safe_json(artifact_path, label=artifact_path.name)
    if not isinstance(artifact, dict):
        return [Finding(rule_id="VAL-ID-103", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message="artifact root must be a JSON object")]

    findings: list[Finding] = []
    for error in iter_schema_errors("valuation-results", artifact):
        findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", json_pointer="/" + "/".join(str(p) for p in error.path), message=error.message))
    if findings:
        return sort_findings(findings)

    findings.extend(validate_method_results(artifact, catalog_registry=catalog_registry))
    return sort_findings(findings)
