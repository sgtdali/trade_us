"""Pure ``valuation_comparison`` artifact assembly (T74-B;
docs/valuation-t66-08-comparison-specification.md: given already-evaluated
engine output and resolved exact references, derive identity, status,
and lineage, after which nothing in the returned mapping is ever
mutated).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..identity import derive_artifact_id, derive_context_id

COMPARISON_SCHEMA_VERSION = "1.0.0"

def derive_comparison_status(comparison_type: str, eligibility_state: str | None) -> tuple[str, bool, bool]:
    """Map an engine's eligibility outcome to the schema's closed
    ``status.state`` vocabulary plus ``canonical_statistic_available``/
    ``ranking_available`` -- never a stored claim the engine itself
    *correctly computed* ``insufficient_data`` status, not a failure)."""
    mapping = {"eligible": "available", "provisional": "provisional", "excluded_insufficient_data": "insufficient_data"}
    state = mapping[eligibility_state]  # type: ignore[index]
    canonical_statistic_available = eligibility_state == "eligible"
    ranking_available = eligibility_state == "eligible" and comparison_type == "sector_peer"
    return state, canonical_statistic_available, ranking_available


def _lineage_dag(*, comparison_node_id: str, subject_refs: Sequence[Mapping[str, Any]], universe_ref: Mapping[str, Any] | None) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [{"node_id": comparison_node_id, "node_type": "valuation_comparison", "owner_type": "generated"}]
    edges: list[dict[str, Any]] = []

    for subject_ref in subject_refs:
        artifact_ref = subject_ref.get("artifact_ref")
        if artifact_ref is None:
            continue
        node_id = f"node:subject:{artifact_ref['artifact_id']}"
        if any(n["node_id"] == node_id for n in nodes):
            continue
        nodes.append({"node_id": node_id, "node_type": artifact_ref["artifact_type"], "owner_type": "generated"})
        edges.append({"edge_id": f"edge:{comparison_node_id}:{node_id}", "from_node_id": comparison_node_id, "to_node_id": node_id, "relation": "calculated_from", "criticality": "critical"})

    if universe_ref is not None:
        node_id = f"node:universe:{universe_ref['artifact_id']}"
        nodes.append({"node_id": node_id, "node_type": "valuation_peer_universe", "owner_type": "authored"})
        edges.append({"edge_id": f"edge:{comparison_node_id}:{node_id}", "from_node_id": comparison_node_id, "to_node_id": node_id, "relation": "calculated_from", "criticality": "critical"})

    return {"nodes": nodes, "edges": edges}


def assemble_valuation_comparison(
    *,
    comparison_type: str, purpose: str, as_of_date: str, generated_at: str, engine_version: str,
    comparison_policy_ref: str, methodology_bundle_ref: str,
    subject_refs: Sequence[Mapping[str, Any]], universe_ref: Mapping[str, Any] | None,
    method_or_dimension_scope: Mapping[str, Any], eligibility_records: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]], statistics_or_matrix: Mapping[str, Any],
    ranking_records: Sequence[Mapping[str, Any]], confidence: Mapping[str, Any], coverage: Mapping[str, Any],
    eligibility_state: str | None = None, comparison_currency: str | None = None,
    universe_version_ref: Mapping[str, Any] | None = None, as_of_gap_record: Mapping[str, Any] | None = None,
    supersedes: Mapping[str, Any] | None = None, status_reason_records: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Pure: assemble the final schema-shaped ``valuation_comparison``
    artifact from already-evaluated engine output and resolved exact
    references. Never computes a statistic, percentile, or eligibility
    decision itself -- those are already baked into ``statistics_or_matrix``/
    ``eligibility_records``/``eligibility_state`` by the caller's engine
    call."""
    context_projection = {
        "comparison_type": comparison_type, "purpose": purpose, "as_of_date": as_of_date,
        "subject_refs": [dict(s) for s in subject_refs], "universe_ref": dict(universe_ref) if universe_ref else None,
        "method_or_dimension_scope": dict(method_or_dimension_scope), "comparison_policy_ref": comparison_policy_ref,
    }
    context_id = derive_context_id(context_projection)
    artifact_id = derive_artifact_id("valuation_comparison", {"comparison_type": comparison_type, "context_id": context_id})

    state, canonical_statistic_available, ranking_available = derive_comparison_status(comparison_type, eligibility_state)
    publication_eligible = state in ("available",)
    current_use_eligible = state in ("available", "provisional")

    status = {
        "state": state, "reason_records": [dict(r) for r in status_reason_records],
        "canonical_statistic_available": canonical_statistic_available, "ranking_available": ranking_available,
        "publication_eligible": publication_eligible, "current_use_eligible": current_use_eligible,
    }

    comparison_node_id = f"node:comparison:{artifact_id}"
    lineage = {
        "engine_version": engine_version, "comparison_schema_version": COMPARISON_SCHEMA_VERSION,
        "supersedes": dict(supersedes) if supersedes else None,
        "dag": _lineage_dag(comparison_node_id=comparison_node_id, subject_refs=subject_refs, universe_ref=universe_ref),
    }

    temporal_context: dict[str, Any] = {"as_of_date": as_of_date, "generated_at": generated_at}
    if as_of_gap_record is not None:
        temporal_context["as_of_gap_record"] = dict(as_of_gap_record)

    comparison_identity: dict[str, Any] = {
        "comparison_id": artifact_id, "purpose": purpose, "as_of_date": as_of_date,
        "comparison_policy_ref": comparison_policy_ref, "methodology_bundle_ref": methodology_bundle_ref,
    }
    if comparison_currency is not None:
        comparison_identity["comparison_currency"] = comparison_currency
    if universe_version_ref is not None:
        comparison_identity["universe_version_ref"] = dict(universe_version_ref)

    unhashed: dict[str, Any] = {
        "schema_version": COMPARISON_SCHEMA_VERSION, "artifact_type": "valuation_comparison", "artifact_id": artifact_id,
        "owner_type": "generated",
        "comparison_identity": comparison_identity, "comparison_type": comparison_type,
        "temporal_context": temporal_context, "subject_refs": [dict(s) for s in subject_refs],
        "method_or_dimension_scope": dict(method_or_dimension_scope),
        "eligibility_records": [dict(r) for r in eligibility_records], "observations": [dict(o) for o in observations],
        "statistics_or_matrix": dict(statistics_or_matrix), "ranking_records": [dict(r) for r in ranking_records],
        "confidence": dict(confidence), "coverage": dict(coverage), "status": status,
        "comparison_refs": [], "lineage": lineage,
    }
    if universe_ref is not None:
        unhashed["universe_ref"] = dict(universe_ref)
    return unhashed
