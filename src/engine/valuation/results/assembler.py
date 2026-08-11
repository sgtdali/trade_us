"""Current-run result assembly (docs/valuation-t71-05-results-schema-assembly-coverage-specification.md).

:func:`assemble_current_results` produces one complete, self-consistent
``valuation-results`` artifact dict (matching ``schemas/valuation-results.schema.json``)
from an already-evaluated method list -- every configured row becomes
exactly one ``method_results[]`` envelope, including failures. Coverage,
family sufficiency, confidence, and bundle/publication state are always
recomputed here, never accepted from a caller.

This module produces an *unvalidated* in-memory artifact
(docs/valuation-t71-05-*.md Section 18): ``results/service.py`` runs
``validation/methods.py`` against it and attaches the real
``validation_summary``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..canonical import canonical_bytes
from ..identity import derive_artifact_id
from ..methods.evaluator import MethodEvaluation
from ..methods.families import compute_family_coverage, minimum_valid_family_satisfied
from ..methods.operands import BoundOperand
from .confidence import bundle_confidence, propagated_confidence
from .coverage import compute_coverage

_ENTERPRISE_LEASE_INCLUSIVE_TYPES = frozenset({"enterprise_value_incl_lease", "canonical_ebitdar", "after_lease_fcf"})
_ENTERPRISE_LEASE_EXCLUSIVE_TYPES = frozenset({"enterprise_value_ex_lease"})
_PER_SHARE_TYPES = frozenset({"dividend_per_share", "spot_price_per_share"})
_ENTERPRISE_TYPES = frozenset({"core_ebit", "canonical_ebitda", "canonical_ebitdar", "enterprise_value_ex_lease", "enterprise_value_incl_lease"})
_FLOW_TYPES = frozenset({"parent_net_income", "core_ebit", "canonical_ebitda", "canonical_ebitdar", "standard_fcf", "after_lease_fcf", "fcfe", "dividend_per_share"})

_REASON_SEVERITY = {
    "calculation_blocked": "blocker",
    "not_meaningful": "warning",
    "unavailable": "error",
    "insufficient_data": "error",
    "not_comparable": "warning",
    "not_applicable": "info",
}


@dataclass(frozen=True)
class CurrentRunRequest:
    ticker: str
    company_ref: str
    valuation_context_id: str
    engine_version: str
    valuation_input_ref: Mapping[str, str]
    method_set_entry: Mapping[str, Any]
    as_of_date: str
    cutoff_instant: str
    valuation_timezone: str = "Europe/Istanbul"
    calendar_policy_ref: str = "val.policy.calendar.default"


def _derive_run_id(request: CurrentRunRequest, method_set_version: str) -> str:
    """Deterministic run identity: valuation-input exact ref, method-set
    exact ref, engine version, and run purpose -- excludes path, host,
    user, current time, and git SHA (docs/valuation-t71-05-*.md Section
    4)."""
    preimage = {
        "valuation_input_ref": dict(request.valuation_input_ref),
        "method_set_id": request.method_set_entry["entry_id"],
        "method_set_version": method_set_version,
        "engine_version": request.engine_version,
        "run_purpose": "current",
    }
    digest = hashlib.sha256(canonical_bytes(preimage)).hexdigest()
    return f"run-{digest[:24]}"


def operand_dict(bound: BoundOperand | None) -> dict[str, Any] | None:
    if bound is None:
        return None
    economic_type = bound.economic_type
    if economic_type in _FLOW_TYPES:
        period_kind, period_variant = "flow", "fy"
    else:
        period_kind, period_variant = "instant", "spot"
    if economic_type in _ENTERPRISE_LEASE_INCLUSIVE_TYPES:
        lease_scope = "lease_inclusive"
    elif economic_type in _ENTERPRISE_LEASE_EXCLUSIVE_TYPES:
        lease_scope = "lease_exclusive"
    else:
        lease_scope = "not_applicable"
    if economic_type in _ENTERPRISE_TYPES:
        ownership_scope = "enterprise_consolidated"
    elif economic_type in _PER_SHARE_TYPES:
        ownership_scope = "per_share"
    else:
        ownership_scope = "parent_common_equity"

    envelope: dict[str, Any] = {"status": bound.status}
    if bound.available:
        envelope["value"] = str(bound.value.numerator) if bound.value.denominator == 1 else _decimal_repr(bound.value)
        if bound.currency:
            envelope["currency"] = bound.currency
    else:
        envelope["reason_codes"] = [{"code": rc, "severity": _REASON_SEVERITY.get("unavailable", "error")} for rc in bound.reason_codes]

    return {
        "basis_ref": bound.basis_ref or f"unavailable:{economic_type}",
        "economic_type": economic_type,
        "amount": envelope,
        "period_ref": {"period_kind": period_kind, "period_variant": period_variant},
        "ownership_scope": ownership_scope,
        "lease_scope": lease_scope,
        "sign_state": bound.sign_state,
    }


def _decimal_repr(value) -> str:
    from decimal import Decimal
    from ..canonical import normalize_decimal

    return normalize_decimal(Decimal(value.numerator) / Decimal(value.denominator))


def method_result_dict(
    *, run_id: str, evaluation: MethodEvaluation, confidence_policy_ref: str,
) -> dict[str, Any]:
    method_result_id = f"{run_id}:{evaluation.formula_id}:{evaluation.variant_id}"
    available = evaluation.status == "available"

    reason_records = []
    if evaluation.reason_code is not None:
        reason_records.append({"code": evaluation.reason_code, "severity": _REASON_SEVERITY.get(evaluation.status, "warning")})

    lineage_node_refs = sorted({
        ref for ref in (
            (evaluation.numerator.basis_ref if evaluation.numerator else None),
            (evaluation.denominator.basis_ref if evaluation.denominator else None),
        ) if ref
    })

    confidence = propagated_confidence(available=available, policy_ref=confidence_policy_ref)

    result: dict[str, Any] = {
        "method_result_id": method_result_id,
        "method_id": evaluation.method_id,
        "method_version": evaluation.method_version,
        "economic_family_id": evaluation.economic_family_id,
        "role": evaluation.role,
        "variant_id": evaluation.variant_id,
        "applicability": {
            "outcome": evaluation.outcome,
            "company_type_applicable": evaluation.outcome not in ("not_applicable", "deferred_not_implemented"),
            "sector_policy_applicable": evaluation.outcome not in ("not_applicable", "deferred_not_implemented"),
            "applicability_policy_ref": evaluation.applicability_policy_ref or "val.policy.applicability.default_conditional",
            "applicability_reason_codes": [] if evaluation.outcome not in ("not_applicable", "deferred_not_implemented") else [
                {"code": "applicability.company_type_not_implemented", "severity": "info"}
            ],
        },
        "status": evaluation.status,
        "basis_refs": lineage_node_refs,
        "formula_ref": {
            "formula_id": evaluation.formula_id,
            "formula_version": evaluation.method_version,
        },
        "output_semantics": dict(evaluation.output_semantics),
        "data_confidence": confidence,
        "model_confidence": confidence,
        "output_confidence": confidence,
        "reason_records": reason_records,
        "lineage_node_refs": lineage_node_refs,
        "current_use_eligible": evaluation.current_use_eligible,
        "ranking_eligible": evaluation.ranking_eligible,
    }
    if evaluation.numerator is not None:
        result["numerator"] = operand_dict(evaluation.numerator)
    if evaluation.denominator is not None:
        result["denominator"] = operand_dict(evaluation.denominator)
    if available:
        result["canonical_value"] = {"status": "available", "value": evaluation.canonical_value}
    return result


def bundle_state(*, available_count: int, unavailable_count: int, blocked_count: int, primary_family_available: bool) -> str:
    if available_count == 0:
        return "calculation_blocked" if blocked_count > 0 and unavailable_count == 0 else "all_methods_unavailable"
    if primary_family_available and unavailable_count == 0 and blocked_count == 0:
        return "complete"
    if primary_family_available:
        return "partial"
    return "diagnostic_only"


def assemble_current_results(
    request: CurrentRunRequest, evaluations: Sequence[MethodEvaluation],
) -> dict[str, Any]:
    """Assemble one unvalidated ``valuation-results`` artifact dict. Pure
    function of its arguments -- performs no I/O, no clock/host/random
    access, and no network."""
    method_set_entry = request.method_set_entry
    method_set_version = method_set_entry["entry_version"]
    run_id = _derive_run_id(request, method_set_version)

    context_id = request.valuation_context_id
    artifact_id = derive_artifact_id("valuation_results", {"ticker": request.ticker, "as_of_date": request.as_of_date, "context_id": context_id})

    confidence_policy_ref = "val.policy.status.confidence_propagation"
    method_results = [
        method_result_dict(
            run_id=run_id, evaluation=evaluation,
            confidence_policy_ref=confidence_policy_ref,
        )
        for evaluation in evaluations
    ]

    family_coverage = compute_family_coverage(evaluations)
    coverage = compute_coverage(evaluations, family_coverage)
    primary_family_available = minimum_valid_family_satisfied(family_coverage)

    available_count = coverage["available_method_count"]
    unavailable_count = sum(1 for e in evaluations if e.status in ("unavailable", "not_meaningful", "insufficient_data", "not_comparable"))
    blocked_count = sum(1 for e in evaluations if e.status == "calculation_blocked")
    state = bundle_state(available_count=available_count, unavailable_count=unavailable_count, blocked_count=blocked_count, primary_family_available=primary_family_available)

    bundle_status = {
        "state": state,
        "whole_run_blockers": [],
        "method_level_failures": [e.formula_id for e in evaluations if e.status not in ("available", "not_applicable")],
        "warnings": [],
        "minimum_valid_family_satisfied": primary_family_available,
        "assessment_eligible": primary_family_available,
        "current_publication_eligible": primary_family_available,
    }

    lineage_nodes: dict[str, dict[str, Any]] = {
        request.valuation_input_ref["artifact_id"]: {
            "node_id": request.valuation_input_ref["artifact_id"], "node_type": "valuation_inputs",
            "artifact_ref": dict(request.valuation_input_ref), "owner_type": "generated",
        },
    }
    lineage_edges: list[dict[str, Any]] = []
    for evaluation, result in zip(evaluations, method_results):
        for basis_ref in result["lineage_node_refs"]:
            if basis_ref not in lineage_nodes:
                lineage_nodes[basis_ref] = {"node_id": basis_ref, "node_type": "operand_basis", "owner_type": "generated"}
            lineage_edges.append({
                "edge_id": f"{basis_ref}->{result['method_result_id']}",
                "from_node_id": basis_ref, "to_node_id": result["method_result_id"],
                "relation": "calculated_from" if evaluation.status == "available" else "blocked_by",
                "criticality": "critical",
            })
        if not result["lineage_node_refs"]:
            lineage_edges.append({
                "edge_id": f"{request.valuation_input_ref['artifact_id']}->{result['method_result_id']}",
                "from_node_id": request.valuation_input_ref["artifact_id"], "to_node_id": result["method_result_id"],
                "relation": "blocked_by", "criticality": "critical",
            })

    unhashed: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_type": "valuation_results",
        "artifact_id": artifact_id,
        "owner_type": "generated",
        "run_identity": {
            "run_id": run_id,
            "company_ref": request.company_ref,
            "ticker": request.ticker,
            "valuation_context_id": context_id,
            "run_purpose": "current",
            "engine_version": request.engine_version,
            "methodology_bundle_ref": {
                "method_set_id": method_set_entry["entry_id"],
                "method_set_version": method_set_entry["entry_version"],
            },
            "canonical_serialization_version": "1.0.0",
        },
        "temporal_context": {
            "as_of_date": request.as_of_date,
            "valuation_timezone": request.valuation_timezone,
            "valuation_cutoff_at": request.cutoff_instant,
            "temporal_mode": "current",
            "calendar_policy_ref": request.calendar_policy_ref,
        },
        "valuation_input_ref": dict(request.valuation_input_ref),
        "scenario_set_ref": None,
        "method_set_ref": {
            "method_set_id": method_set_entry["entry_id"],
            "method_set_version": method_set_entry["entry_version"],
        },
        "method_results": method_results,
        "weighted_scenario_result": None,
        "coverage": coverage,
        "bundle_status": bundle_status,
        "confidence_summary": bundle_confidence(any_current_use_available=primary_family_available, policy_ref=confidence_policy_ref),
        "validation_summary": {"structurally_valid": True, "finding_ids": [], "blocking_finding_count": 0, "warning_finding_count": 0},
        "publication_state": {
            "structured_artifact_valid": True,
            "report_render_eligible": False,
            "current_use_eligible": primary_family_available,
            "historical_use_eligible": False,
            "comparison_input_eligible": False,
            "portfolio_review_handoff_eligible": primary_family_available,
            "restriction_reason_refs": [] if primary_family_available else [{"code": "applicability.no_valid_primary_secondary_family", "severity": "warning"}],
        },
        "lineage": {
            "nodes": sorted(lineage_nodes.values(), key=lambda n: n["node_id"]),
            "edges": sorted(lineage_edges, key=lambda e: e["edge_id"]),
        },
    }
    return unhashed
