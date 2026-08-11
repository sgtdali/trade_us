"""Immutable model for a governed ``valuation_comparison_observations``
input artifact (T74-A; docs/valuation-t74-02-comparison-schema-policy-universe-specification.md
Section 10). This is an offline, authored input the historical/peer
engines (T74-B) read from -- never generated, never mutated, never
resolved against a network or a mutable "latest" selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

OBSERVATION_KINDS = ("historical_monthly", "peer_member")


@dataclass(frozen=True)
class ComparisonObservation:
    observation_id: str
    company_or_member_id: str
    ticker: str
    as_of_date: str
    cutoff_instant: str
    value: Mapping[str, Any]
    status: str
    claim_basis: str
    corporate_action_basis: str
    formula_ref: str
    policy_version: str
    confidence: str
    provenance_refs: tuple[Mapping[str, Any], ...]
    financial_anchor_ref: str | None = None
    lease_basis: str | None = None

    @property
    def calendar_month(self) -> str:
        """``YYYY-MM`` derived from ``as_of_date`` -- the exact grouping
        key :func:`~.eligibility.one_observation_per_calendar_month` uses;
        computed here (not stored) so the raw artifact never needs a
        redundant derived field a caller could tamper with independently
        of ``as_of_date`` itself."""
        return self.as_of_date[:7]


@dataclass(frozen=True)
class ComparisonObservationSet:
    artifact_id: str
    observation_set_id: str
    observation_kind: str
    method_family_id: str
    method_variant_id: str
    currency: str
    accounting_basis: str
    consolidation: str
    observations: tuple[ComparisonObservation, ...]
    lineage: Mapping[str, Any]
    raw: Mapping[str, Any]


def parse_comparison_observation_set(artifact: Mapping[str, Any]) -> ComparisonObservationSet:
    """Structure an already schema-validated ``valuation_comparison_observations``
    JSON object. Assumes the caller has run it through
    ``schemas.iter_schema_errors("valuation-comparison-observations", ...)``
    first."""
    observations = tuple(
        ComparisonObservation(
            observation_id=o["observation_id"], company_or_member_id=o["company_or_member_id"], ticker=o["ticker"],
            as_of_date=o["as_of_date"], cutoff_instant=o["cutoff_instant"], value=MappingProxyType(dict(o["value"])),
            status=o["status"], claim_basis=o["claim_basis"], corporate_action_basis=o["corporate_action_basis"],
            formula_ref=o["formula_ref"], policy_version=o["policy_version"], confidence=o["confidence"],
            provenance_refs=tuple(MappingProxyType(dict(p)) for p in o["provenance_refs"]),
            financial_anchor_ref=o.get("financial_anchor_ref"), lease_basis=o.get("lease_basis"),
        )
        for o in artifact["observations"]
    )
    return ComparisonObservationSet(
        artifact_id=artifact["artifact_id"],
        observation_set_id=artifact["observation_set_id"], observation_kind=artifact["observation_kind"],
        method_family_id=artifact["method_family_id"], method_variant_id=artifact["method_variant_id"],
        currency=artifact["currency"], accounting_basis=artifact["accounting_basis"], consolidation=artifact["consolidation"],
        observations=observations, lineage=MappingProxyType(dict(artifact["lineage"])), raw=MappingProxyType(dict(artifact)),
    )
