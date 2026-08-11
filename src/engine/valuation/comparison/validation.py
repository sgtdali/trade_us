"""T74-B recomputing comparison validator, composing the existing closed
T68 rule IDs (``VAL-COMP-001..012``, ``CAT-APP-001``;
docs/valuation-t68-07-comparison-strategy-applicability-matrix.md;
docs/valuation-t74-06-validation-cli-transaction-specification.md
Sections 2-5). No new rule ID is invented here.

Every check recomputes from the candidate artifact's own bytes (and,
where a loaded ``universe``/``subject`` artifact is supplied, from the
real referenced file) -- it never trusts a stored count/total/ratio at
face value for the structural checks it owns."""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping

from ..catalogs import CatalogRegistry
from ..errors import ArtifactReferenceError
from ..references import verify_artifact_reference
from ..validation.findings import Finding, sort_findings
from .models import COMPARISON_TYPES, PIOTROSKI_COMPONENT_ORDER
from .statistics import to_canonical_decimal

_FORBIDDEN_KEY_SUBSTRINGS = (
    "total_score", "weighted_score", "overall_score", "recommendation", "buy_sell_hold",
    "target_price", "preferred_ticker", "portfolio_weight", "position_size", "order_instruction",
    "human_investment_decision", "winner", "global_rank", "portfolio_action",
)

_VARIANT_SUBJECT_COUNT = {
    "historical_self": 1, "sector_peer": 1,
    "piotroski_diagnostic": 1, "magic_formula_diagnostic": 1,
}


def _scan_forbidden_fields(node: Any, path: str, findings: list[Finding]) -> None:
    if isinstance(node, Mapping):
        for key, value in node.items():
            key_lower = str(key).lower()
            if any(bad in key_lower for bad in _FORBIDDEN_KEY_SUBSTRINGS):
                findings.append(Finding(
                    rule_id="VAL-COMP-005", severity="blocker", scope="artifact", json_pointer=f"{path}/{key}",
                    reason_code="comparison.forbidden_aggregation_or_decision_field",
                    message=f"forbidden aggregation/decision field present: {path}/{key}",
                ))
            _scan_forbidden_fields(value, f"{path}/{key}", findings)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _scan_forbidden_fields(item, f"{path}/{index}", findings)


def validate_forbidden_semantics(artifact: Mapping[str, Any]) -> list[Finding]:
    """VAL-COMP-005/T74 invariant: no winner/score/rank/decision field
    anywhere, and ``comparison_refs`` stays empty (schema already enforces
    both structurally; this is defense-in-depth against a schema-
    conformant-but-semantically-forbidden artifact)."""
    findings: list[Finding] = []
    _scan_forbidden_fields(artifact, "", findings)
    if artifact.get("comparison_refs"):
        findings.append(Finding(
            rule_id="VAL-COMP-005", severity="blocker", scope="artifact", json_pointer="/comparison_refs",
            reason_code="comparison.nonempty_comparison_refs_unsupported",
            message="comparison_refs must be empty -- a comparison result is never itself input to another comparison in the same run",
        ))
    return findings


def validate_variant_shape(artifact: Mapping[str, Any]) -> list[Finding]:
    """VAL-COMP-001: exactly one allowed ``comparison_type`` branch, with
    coherent subject_refs count and a matching ``statistics_or_matrix.variant_kind``."""
    findings: list[Finding] = []
    comparison_type = artifact.get("comparison_type")
    if comparison_type not in COMPARISON_TYPES:
        findings.append(Finding(
            rule_id="VAL-COMP-001", severity="blocker", scope="artifact", json_pointer="/comparison_type",
            reason_code="comparison.unknown_variant", message=f"unknown comparison_type: {comparison_type!r}",
        ))
        return findings

    variant_kind = (artifact.get("statistics_or_matrix") or {}).get("variant_kind")
    if variant_kind != comparison_type:
        findings.append(Finding(
            rule_id="VAL-COMP-001", severity="blocker", scope="artifact", json_pointer="/statistics_or_matrix/variant_kind",
            reason_code="comparison.variant_kind_mismatch",
            message=f"statistics_or_matrix.variant_kind {variant_kind!r} does not match comparison_type {comparison_type!r}",
        ))

    expected_subject_count = _VARIANT_SUBJECT_COUNT.get(comparison_type)
    actual_subject_count = len(artifact.get("subject_refs", ()))
    if expected_subject_count is not None and actual_subject_count != expected_subject_count:
        findings.append(Finding(
            rule_id="VAL-COMP-002", severity="blocker", scope="artifact", json_pointer="/subject_refs",
            reason_code="comparison.subject_ref_count_incoherent",
            message=f"{comparison_type!r} requires exactly {expected_subject_count} subject_refs, got {actual_subject_count}",
        ))

    if comparison_type == "sector_peer" and artifact.get("universe_ref") is None:
        findings.append(Finding(
            rule_id="VAL-COMP-008", severity="blocker", scope="artifact", json_pointer="/universe_ref",
            reason_code="comparison.peer_universe_ref_missing", message="sector_peer comparison requires a non-null universe_ref",
        ))

    return findings


def validate_piotroski_total_consistency(artifact: Mapping[str, Any]) -> list[Finding]:
    """Recompute the Piotroski total from ``components[]`` -- an integer
    sum only when all nine are ``complete``, else ``null``, never a
    partial "x/9" (T74.5 Section 6; VAL-COMP-004)."""
    findings: list[Finding] = []
    matrix = artifact.get("statistics_or_matrix") or {}
    if matrix.get("variant_kind") != "piotroski_diagnostic":
        return findings
    components = matrix.get("components", ())
    component_ids = tuple(c.get("component_id") for c in components)
    if component_ids != PIOTROSKI_COMPONENT_ORDER:
        findings.append(Finding(
            rule_id="VAL-COMP-001", severity="blocker", scope="artifact", json_pointer="/statistics_or_matrix/components",
            reason_code="comparison.piotroski_component_order_incoherent",
            message=f"components[] must be exactly the nine canonical component_id values in order, got {component_ids!r}",
        ))
        return findings
    complete = [c for c in components if c.get("status") == "complete"]
    expected_total = sum(c["binary_value"] for c in complete) if len(complete) == 9 else None
    if matrix.get("total") != expected_total:
        findings.append(Finding(
            rule_id="VAL-COMP-004", severity="blocker", scope="artifact", json_pointer="/statistics_or_matrix/total",
            reason_code="comparison.piotroski_total_forged",
            message=f"stored total {matrix.get('total')!r} does not match recomputed total {expected_total!r} from components[]",
        ))
    available_component_count = len(complete)
    if matrix.get("available_component_count") != available_component_count:
        findings.append(Finding(
            rule_id="VAL-COMP-004", severity="blocker", scope="artifact", json_pointer="/statistics_or_matrix/available_component_count",
            reason_code="comparison.piotroski_available_count_forged",
            message=f"stored available_component_count {matrix.get('available_component_count')!r} does not match recomputed {available_component_count}",
        ))
    return findings


def validate_peer_coverage_consistency(artifact: Mapping[str, Any]) -> list[Finding]:
    """Recompute ``coverage_ratio`` exactly (never lossy ``Decimal``
    division) from ``eligible_peer_count``/``approved_primary_cohort_count``
    and cross-check ``members[]``'s own eligible count -- VAL-COMP-004/009."""
    findings: list[Finding] = []
    matrix = artifact.get("statistics_or_matrix") or {}
    if matrix.get("variant_kind") != "sector_peer":
        return findings
    approved = matrix.get("approved_primary_cohort_count")
    eligible = matrix.get("eligible_peer_count")
    members = matrix.get("members", ())
    actual_eligible_from_members = sum(1 for m in members if m.get("eligibility_state") == "eligible")
    if eligible != actual_eligible_from_members:
        findings.append(Finding(
            rule_id="VAL-COMP-004", severity="blocker", scope="artifact", json_pointer="/statistics_or_matrix/eligible_peer_count",
            reason_code="comparison.peer_eligible_count_forged",
            message=f"eligible_peer_count {eligible!r} does not match recomputed count {actual_eligible_from_members} from members[]",
        ))
    if isinstance(approved, int) and isinstance(eligible, int) and approved > 0:
        # Compare like-for-like canonical decimal strings -- 5/7 has no
        # exact terminating decimal, so the stored value is itself a
        # precision-bounded canonical projection; recomputing a true
        # infinite-precision Fraction and comparing THAT against the
        # (necessarily truncated) stored string would spuriously fail on
        # every non-terminating ratio. Both sides must go through the
        # same projection (:func:`~.statistics.to_canonical_decimal`).
        expected_ratio_str = to_canonical_decimal(Fraction(eligible, approved))
        stored_ratio = matrix.get("coverage_ratio")
        if stored_ratio != expected_ratio_str:
            findings.append(Finding(
                rule_id="VAL-COMP-009", severity="blocker", scope="artifact", json_pointer="/statistics_or_matrix/coverage_ratio",
                reason_code="comparison.peer_coverage_ratio_forged",
                message=f"coverage_ratio {stored_ratio!r} does not match exact recomputed {eligible}/{approved} ({expected_ratio_str!r})",
            ))
    return findings


def validate_lineage_acyclic(artifact: Mapping[str, Any]) -> list[Finding]:
    """The lineage DAG must be acyclic and every edge must reference a
    real node (T74 non-circularity boundary)."""
    findings: list[Finding] = []
    dag = artifact.get("lineage", {}).get("dag", {})
    nodes = {n["node_id"] for n in dag.get("nodes", ())}
    edges = dag.get("edges", ())
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        src, dst = edge.get("from_node_id"), edge.get("to_node_id")
        if src not in nodes or dst not in nodes:
            findings.append(Finding(
                rule_id="VAL-COMP-001", severity="blocker", scope="artifact", json_pointer="/lineage/dag/edges",
                reason_code="comparison.lineage_dangling_edge", message=f"lineage edge references an unknown node: {src!r} -> {dst!r}",
            ))
            continue
        adjacency.setdefault(src, []).append(dst)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in nodes}

    def _visit(node: str) -> bool:
        color[node] = GRAY
        for neighbor in adjacency.get(node, ()):
            if color.get(neighbor) == GRAY:
                return True
            if color.get(neighbor) == WHITE and _visit(neighbor):
                return True
        color[node] = BLACK
        return False

    for node in sorted(nodes):
        if color[node] == WHITE and _visit(node):
            findings.append(Finding(
                rule_id="VAL-COMP-001", severity="blocker", scope="artifact", json_pointer="/lineage/dag",
                reason_code="comparison.lineage_cycle_detected", message="lineage DAG contains a cycle",
            ))
            break
    return findings


def validate_exact_subject_references(artifact: Mapping[str, Any], *, loaded_subjects: Mapping[str, Mapping[str, Any]]) -> list[Finding]:
    """Verify each ``subject_refs[].artifact_ref`` against an already-
    loaded real artifact the caller supplies keyed by ``artifact_id``
    (VAL-COMP-002; reuses the shared, already-established
    :func:`~..references.verify_artifact_reference`, never a second
    parallel reference-verification implementation)."""
    findings: list[Finding] = []
    for index, subject_ref in enumerate(artifact.get("subject_refs", ())):
        artifact_ref = subject_ref.get("artifact_ref")
        if artifact_ref is None:
            continue
        loaded = loaded_subjects.get(artifact_ref["artifact_id"])
        if loaded is None:
            continue
        try:
            verify_artifact_reference(artifact_ref, loaded, artifact_ref["relative_path"])
        except ArtifactReferenceError as exc:
            findings.append(Finding(
                rule_id="VAL-COMP-002", severity="blocker", scope="artifact", json_pointer=f"/subject_refs/{index}/artifact_ref",
                reason_code="comparison.exact_reference_integrity_failure", message=str(exc),
            ))
    return findings


def validate_valuation_comparison(
    artifact: Mapping[str, Any], *, registry: CatalogRegistry, loaded_subjects: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[Finding]:
    """Top-level structural/referential validator entry point (T74.6
    Sections 2-5). Assumes schema validation has already run
    (:func:`~..schemas.iter_schema_errors`) -- this adds the T68
    VAL-COMP/CAT-APP checks a schema cannot express."""
    findings: list[Finding] = []
    findings.extend(validate_variant_shape(artifact))
    findings.extend(validate_forbidden_semantics(artifact))
    findings.extend(validate_piotroski_total_consistency(artifact))
    findings.extend(validate_peer_coverage_consistency(artifact))
    findings.extend(validate_lineage_acyclic(artifact))
    if loaded_subjects is not None:
        findings.extend(validate_exact_subject_references(artifact, loaded_subjects=loaded_subjects))
    return sort_findings(findings)
