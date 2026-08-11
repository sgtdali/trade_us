"""T74-B comparison/diagnostic generation service adapters: load exact
governed inputs, compile the comparison policy plan, run the matching
pure engine, assemble and validate the final artifact, and perform
check/transactional-write behavior, reusing (never duplicating) T70's
canonical/transaction/schema infrastructure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..canonical import canonical_bytes
from ..catalogs import CatalogRegistry
from ..errors import ValuationError
from ..paths import comparison_relative_path
from ..safe_json import read_safe_json
from ..schemas import iter_schema_errors
from ..transaction import TransactionResult, WriteTarget, check_transaction, execute_transaction
from ..validation.findings import Finding, sort_findings
from .compiler import CompiledComparisonPlan, compile_comparison_policies
from .historical import evaluate_historical
from .magic_formula import MagicFormulaFacts, evaluate_magic_formula
from .observations import parse_comparison_observation_set
from .peers import evaluate_peer
from .piotroski import PiotroskiFacts, evaluate_piotroski
from .results import assemble_valuation_comparison
from .universe import parse_peer_universe, verify_universe_canonical_eligible
from .validation import validate_valuation_comparison

RESULT_SCHEMA_KEY = "valuation-comparison"


class ComparisonGenerationResult:
    def __init__(self, *, findings: tuple[Finding, ...], artifact: dict[str, Any] | None, transaction: TransactionResult | None):
        self.findings = findings
        self.artifact = artifact
        self.transaction = transaction

    @property
    def ok(self) -> bool:
        return not any(f.severity in ("blocker", "error") for f in self.findings)


def _load_json(path: Path, *, label: str) -> tuple[dict[str, Any] | None, list[Finding]]:
    if not path.exists():
        return None, [Finding(rule_id="VAL-COMP-002", severity="blocker", scope="bundle", reason_code="comparison.exact_reference_integrity_failure", message=f"missing {label}: {path}")]
    document = read_safe_json(path, label=path.name)
    if not isinstance(document, dict):
        return None, [Finding(rule_id="VAL-COMP-002", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message=f"{label} root must be a JSON object")]
    return document, []


def _compile_plan(registry: CatalogRegistry) -> tuple[CompiledComparisonPlan | None, list[Finding]]:
    try:
        return compile_comparison_policies(registry), []
    except ValuationError as exc:
        return None, [Finding(rule_id="CAT-APP-001", severity="blocker", scope="catalog", reason_code="comparison.policy_or_catalog_lock_mismatch", message=str(exc))]


def _finalize(
    artifact: dict[str, Any], findings: list[Finding], *, registry: CatalogRegistry, output_dir: Path, check_only: bool,
) -> ComparisonGenerationResult:
    schema_errors = list(iter_schema_errors(RESULT_SCHEMA_KEY, artifact))
    for error in schema_errors:
        findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", json_pointer="/" + "/".join(str(p) for p in error.path), message=error.message))
    if schema_errors:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    structural_findings = validate_valuation_comparison(artifact, registry=registry)
    findings.extend(structural_findings)
    if any(f.severity == "blocker" for f in structural_findings):
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    context_id = artifact["artifact_id"].rsplit(":", 1)[-1]
    relative_path = comparison_relative_path(artifact["comparison_type"], context_id)
    target = WriteTarget(relative_path=relative_path, content=canonical_bytes(artifact))
    transaction_result = check_transaction(output_dir, [target]) if check_only else execute_transaction(output_dir, [target])
    return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=artifact, transaction=transaction_result)


def _empty_confidence(level: str = "insufficient") -> dict[str, Any]:
    return {
        "sample_size_confidence": level, "method_coverage_confidence": level, "comparability_confidence": level,
        "source_confidence": level, "overall_ranking_confidence": level, "limiting_refs": [],
    }


# --- historical ----------------------------------------------------------

def generate_historical_comparison(
    *, subject_result_path: Path, history_path: Path, current_observation_ref: str, current_value: str,
    as_of_date: str, generated_at: str, engine_version: str, comparison_registry: CatalogRegistry,
    output_dir: Path, check_only: bool = False,
) -> ComparisonGenerationResult:
    findings: list[Finding] = []
    subject_result, err1 = _load_json(subject_result_path, label="--subject-result")
    history_doc, err2 = _load_json(history_path, label="--history")
    findings.extend(err1 + err2)
    if subject_result is None or history_doc is None:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    for error in iter_schema_errors("valuation-comparison-observations", history_doc):
        findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="bundle", json_pointer="/history", message=error.message))
    if findings:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    observation_set = parse_comparison_observation_set(history_doc)
    plan, plan_findings = _compile_plan(comparison_registry)
    findings.extend(plan_findings)
    if plan is None:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)
    ranking_policy = plan.ranking_policies["historical_self"]

    engine_result = evaluate_historical(
        current_observation_ref=current_observation_ref, current_value=current_value,
        comparator_observations=observation_set.observations, ranking_policy=ranking_policy, as_of_date=as_of_date,
    )

    ticker = observation_set.observations[0].ticker if observation_set.observations else "UNKNOWN"
    subject_refs = [{"subject_ref_id": "subj-a", "subject_kind": "valuation_result", "ticker": ticker, "as_of_date": as_of_date, "artifact_ref": {
        "artifact_id": subject_result["artifact_id"], "artifact_type": subject_result.get("artifact_type", "valuation_results"),
        "relative_path": "valuation-results.json",
    }}]

    eligible_count = engine_result.statistics_or_matrix["eligible_count"]
    excluded_count = len(engine_result.excluded)
    artifact = assemble_valuation_comparison(
        comparison_type="historical_self", purpose="historical_valuation", as_of_date=as_of_date, generated_at=generated_at,
        engine_version=engine_version, comparison_policy_ref=f"val.policy.comparison.historical_self@{ranking_policy.policy_version}",
        methodology_bundle_ref="val.bundle.comparison@1.0.0",
        subject_refs=subject_refs, universe_ref=None,
        method_or_dimension_scope={"scope_id": observation_set.method_family_id, "direction": ranking_policy.direction},
        eligibility_records=[], observations=[], statistics_or_matrix=engine_result.statistics_or_matrix, ranking_records=[],
        confidence=_empty_confidence("high" if engine_result.eligibility_state == "eligible" else "insufficient"),
        coverage={
            "candidate_count": engine_result.candidate_count, "eligible_count": eligible_count, "provisional_count": 0,
            "excluded_count": excluded_count, "coverage_numerator": eligible_count, "coverage_denominator": engine_result.candidate_count or 1,
            "coverage_ratio": None,
            "calendar_span_months": engine_result.statistics_or_matrix["calendar_span_months"],
            "distinct_financial_anchor_count": engine_result.statistics_or_matrix["distinct_financial_anchor_count"],
        },
        eligibility_state=engine_result.eligibility_state,
    )
    return _finalize(artifact, findings, registry=comparison_registry, output_dir=output_dir, check_only=check_only)


# --- peer ----------------------------------------------------------

def generate_peer_comparison(
    *, subject_result_path: Path, universe_path: Path, observations_path: Path, subject_ticker: str, subject_value: str,
    method_family_id: str, as_of_date: str, generated_at: str, engine_version: str, comparison_registry: CatalogRegistry,
    output_dir: Path, check_only: bool = False,
) -> ComparisonGenerationResult:
    findings: list[Finding] = []
    subject_result, err1 = _load_json(subject_result_path, label="--subject-result")
    universe_doc, err2 = _load_json(universe_path, label="--universe")
    observations_doc, err3 = _load_json(observations_path, label="--observations")
    findings.extend(err1 + err2 + err3)
    if subject_result is None or universe_doc is None or observations_doc is None:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    for schema_key, doc, label in (("valuation-peer-universe", universe_doc, "universe"), ("valuation-comparison-observations", observations_doc, "observations")):
        for error in iter_schema_errors(schema_key, doc):
            findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="bundle", json_pointer=f"/{label}", message=error.message))
    if findings:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    universe = parse_peer_universe(universe_doc)
    try:
        verify_universe_canonical_eligible(universe, as_of_date=as_of_date)
    except ValuationError as exc:
        findings.append(Finding(rule_id="VAL-COMP-008", severity="blocker", scope="bundle", reason_code="comparison.peer_universe_not_canonical_eligible", message=str(exc)))
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    observation_set = parse_comparison_observation_set(observations_doc)
    plan, plan_findings = _compile_plan(comparison_registry)
    findings.extend(plan_findings)
    if plan is None:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)
    ranking_policy = plan.ranking_policies["sector_peer"]

    engine_result = evaluate_peer(
        subject_ticker=subject_ticker, subject_value=subject_value, universe=universe, method_family_id=method_family_id,
        member_observations=observation_set.observations, ranking_policy=ranking_policy, as_of_date=as_of_date,
    )

    universe_ref = {"artifact_id": universe_doc["artifact_id"], "artifact_type": "valuation_peer_universe", "relative_path": "peer-universe.json"}
    subject_refs = [{"subject_ref_id": "subj-a", "subject_kind": "valuation_result", "ticker": subject_ticker, "as_of_date": as_of_date, "artifact_ref": {
        "artifact_id": subject_result["artifact_id"], "artifact_type": subject_result.get("artifact_type", "valuation_results"),
        "relative_path": "valuation-results.json",
    }}]

    approved = engine_result.approved_primary_cohort_count
    eligible = len(engine_result.eligible_member_ids)
    artifact = assemble_valuation_comparison(
        comparison_type="sector_peer", purpose="comparison", as_of_date=as_of_date, generated_at=generated_at,
        engine_version=engine_version, comparison_policy_ref=f"val.policy.comparison.sector_peer@{ranking_policy.policy_version}",
        methodology_bundle_ref="val.bundle.comparison@1.0.0",
        subject_refs=subject_refs, universe_ref=universe_ref,
        method_or_dimension_scope={"scope_id": method_family_id, "direction": ranking_policy.direction},
        eligibility_records=[], observations=[], statistics_or_matrix=engine_result.statistics_or_matrix, ranking_records=[],
        confidence=_empty_confidence("high" if engine_result.eligibility_state == "eligible" else "insufficient"),
        coverage={
            "candidate_count": approved, "eligible_count": eligible, "provisional_count": 0,
            "excluded_count": approved - eligible, "coverage_numerator": eligible, "coverage_denominator": approved or 1,
            "coverage_ratio": engine_result.statistics_or_matrix["coverage_ratio"],
        },
        eligibility_state=engine_result.eligibility_state,
    )
    return _finalize(artifact, findings, registry=comparison_registry, output_dir=output_dir, check_only=check_only)


# --- diagnostics: piotroski ----------------------------------------------------------

_PIOTROSKI_FACT_FIELDS = (
    "roa_t", "roa_t1", "cfo_t", "cfoa_t", "leverage_t", "leverage_t1", "current_ratio_t", "current_ratio_t1",
    "equity_issuance_amount_t", "gross_margin_t", "gross_margin_t1", "asset_turnover_t", "asset_turnover_t1",
)


def _parse_piotroski_facts(document: Mapping[str, Any]) -> PiotroskiFacts:
    kwargs = {field: document[field] for field in _PIOTROSKI_FACT_FIELDS}
    return PiotroskiFacts(
        current_refs=tuple(document.get("current_refs", ())), prior_refs=tuple(document.get("prior_refs", ())),
        opening_balance_refs=tuple(document.get("opening_balance_refs", ())), **kwargs,
    )


def generate_piotroski_diagnostic(
    *, ticker: str, company_type: str, facts_path: Path, as_of_date: str, generated_at: str, engine_version: str,
    comparison_registry: CatalogRegistry, output_dir: Path, check_only: bool = False,
) -> ComparisonGenerationResult:
    findings: list[Finding] = []
    facts_doc, err = _load_json(facts_path, label="--facts")
    findings.extend(err)
    if facts_doc is None:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    missing = [f for f in _PIOTROSKI_FACT_FIELDS if f not in facts_doc]
    if missing:
        findings.append(Finding(rule_id="VAL-COMP-002", severity="blocker", scope="bundle", reason_code="comparison.exact_reference_integrity_failure", message=f"--facts is missing required field(s): {missing}"))
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    plan, plan_findings = _compile_plan(comparison_registry)
    findings.extend(plan_findings)
    if plan is None:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    facts = _parse_piotroski_facts(facts_doc)
    statistics_or_matrix = evaluate_piotroski(facts, company_type=company_type, policy=plan.piotroski_policy)

    subject_refs = [{"subject_ref_id": "subj-a", "subject_kind": "fundamental_source", "ticker": ticker, "as_of_date": as_of_date}]
    available = statistics_or_matrix["available_component_count"]
    artifact = assemble_valuation_comparison(
        comparison_type="piotroski_diagnostic", purpose="diagnostic", as_of_date=as_of_date, generated_at=generated_at,
        engine_version=engine_version, comparison_policy_ref=f"val.policy.diagnostic.piotroski@{plan.piotroski_policy.policy_version}",
        methodology_bundle_ref="val.bundle.comparison@1.0.0",
        subject_refs=subject_refs, universe_ref=None,
        method_or_dimension_scope={"scope_id": plan.piotroski_policy.diagnostic_id, "direction": "not_rankable"},
        eligibility_records=[], observations=[], statistics_or_matrix=statistics_or_matrix, ranking_records=[],
        confidence=_empty_confidence("high" if available == 9 else "medium"),
        coverage={"candidate_count": 9, "eligible_count": available, "provisional_count": 0, "excluded_count": 9 - available, "coverage_numerator": available, "coverage_denominator": 9, "coverage_ratio": None},
    )
    return _finalize(artifact, findings, registry=comparison_registry, output_dir=output_dir, check_only=check_only)


# --- diagnostics: magic formula ----------------------------------------------------------

_MAGIC_FACT_FIELDS = ("ebit", "enterprise_value", "net_working_capital", "net_operating_fixed_assets", "revenue", "total_assets")


def _parse_magic_facts(document: Mapping[str, Any]) -> MagicFormulaFacts:
    kwargs = {field: document[field] for field in _MAGIC_FACT_FIELDS}
    return MagicFormulaFacts(lease_basis_compatible=bool(document.get("lease_basis_compatible", True)), **kwargs)


def generate_magic_formula_diagnostic(
    *, ticker: str, facts_path: Path, as_of_date: str, generated_at: str, engine_version: str,
    comparison_registry: CatalogRegistry, output_dir: Path, check_only: bool = False,
) -> ComparisonGenerationResult:
    findings: list[Finding] = []
    facts_doc, err = _load_json(facts_path, label="--facts")
    findings.extend(err)
    if facts_doc is None:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    missing = [f for f in _MAGIC_FACT_FIELDS if f not in facts_doc]
    if missing:
        findings.append(Finding(rule_id="VAL-COMP-002", severity="blocker", scope="bundle", reason_code="comparison.exact_reference_integrity_failure", message=f"--facts is missing required field(s): {missing}"))
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    plan, plan_findings = _compile_plan(comparison_registry)
    findings.extend(plan_findings)
    if plan is None:
        return ComparisonGenerationResult(findings=tuple(sort_findings(findings)), artifact=None, transaction=None)

    facts = _parse_magic_facts(facts_doc)
    statistics_or_matrix = evaluate_magic_formula(facts, policy=plan.magic_formula_policy)

    subject_refs = [{"subject_ref_id": "subj-a", "subject_kind": "fundamental_source", "ticker": ticker, "as_of_date": as_of_date}]
    both_eligible = statistics_or_matrix["earnings_yield"]["eligibility"] == "eligible" and statistics_or_matrix["return_on_capital"]["eligibility"] == "eligible"
    artifact = assemble_valuation_comparison(
        comparison_type="magic_formula_diagnostic", purpose="diagnostic", as_of_date=as_of_date, generated_at=generated_at,
        engine_version=engine_version, comparison_policy_ref=f"val.policy.diagnostic.magic_formula@{plan.magic_formula_policy.policy_version}",
        methodology_bundle_ref="val.bundle.comparison@1.0.0",
        subject_refs=subject_refs, universe_ref=None,
        method_or_dimension_scope={"scope_id": plan.magic_formula_policy.diagnostic_id, "direction": "not_rankable"},
        eligibility_records=[], observations=[], statistics_or_matrix=statistics_or_matrix, ranking_records=[],
        confidence=_empty_confidence("high" if both_eligible else "medium"),
        coverage={"candidate_count": 2, "eligible_count": sum(1 for axis in ("earnings_yield", "return_on_capital") if statistics_or_matrix[axis]["eligibility"] == "eligible"), "provisional_count": 0, "excluded_count": sum(1 for axis in ("earnings_yield", "return_on_capital") if statistics_or_matrix[axis]["eligibility"] != "eligible"), "coverage_numerator": 1, "coverage_denominator": 2, "coverage_ratio": None},
    )
    return _finalize(artifact, findings, registry=comparison_registry, output_dir=output_dir, check_only=check_only)
