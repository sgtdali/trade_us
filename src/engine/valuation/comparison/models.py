"""Immutable domain model for a generated ``valuation_comparison`` artifact
(T74-A; docs/valuation-t66-08-comparison-specification.md).

:func:`parse_valuation_comparison` assumes its input has already passed
``schemas.iter_schema_errors("valuation-comparison", ...)`` -- it performs
no re-validation of shapes the JSON Schema already enforces, only
structures access. It never computes an eligibility state, statistic, or
comparison statistic itself: those are the evaluation engines' job.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

#: The supported comparison variants.
COMPARISON_TYPES = (
    "historical_self",
    "sector_peer",
)

ELIGIBILITY_STATES = ("eligible", "provisional", "excluded_insufficient_data")
RESULT_STATUS_STATES = ("available", "provisional", "insufficient_data", "not_comparable", "calculation_blocked")
DIRECTIONS = ("higher_is_more_attractive", "lower_is_more_attractive", "neutral_contextual", "not_rankable")

def _tuple_of(value: Any) -> tuple:
    return tuple(value) if value is not None else ()


def _frozen_tuple_of_mappings(values: Any) -> tuple[Mapping[str, Any], ...]:
    return tuple(MappingProxyType(dict(v)) for v in (values or ()))


def _frozen(value: Any) -> Mapping[str, Any] | None:
    return MappingProxyType(dict(value)) if value is not None else None


@dataclass(frozen=True)
class ComparisonIdentity:
    comparison_id: str
    purpose: str
    as_of_date: str
    comparison_policy_ref: str
    methodology_bundle_ref: str
    comparison_currency: str | None = None
    universe_version_ref: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ComparisonSubjectRef:
    subject_ref_id: str
    subject_kind: str
    ticker: str
    as_of_date: str | None = None
    artifact_ref: Mapping[str, Any] | None = None
    embedded_record_ref: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class EligibilityRecord:
    subject_ref: str
    method_or_dimension_id: str
    eligibility_state: str
    reason_codes: tuple[Mapping[str, Any], ...]
    data_confidence: str
    model_confidence: str
    ranking_confidence: str
    current_use_eligible: bool
    included_in_statistic: bool


@dataclass(frozen=True)
class ComparisonObservationRecord:
    observation_id: str
    subject_ref: str
    method_or_dimension_id: str
    value_or_state: Mapping[str, Any]
    eligibility_ref: str
    lineage_node_refs: tuple[str, ...]
    direction_interpretation: str | None = None
    period_or_as_of: str | None = None
    financial_anchor_ref: str | None = None
    method_variant_ref: str | None = None
    currency_basis_ref: str | None = None
    corporate_action_basis_ref: str | None = None


@dataclass(frozen=True)
class RankingRecord:
    subject_ref: str
    scope_id: str
    sample_size: int
    coverage_ratio: str | None
    direction: str
    eligibility_ref: str
    ranking_confidence: str
    provisional: bool
    rank: str | None = None
    percentile: str | None = None
    tie_group_id: str | None = None


@dataclass(frozen=True)
class ComparisonConfidence:
    sample_size_confidence: str
    method_coverage_confidence: str
    comparability_confidence: str
    source_confidence: str
    overall_ranking_confidence: str
    limiting_refs: tuple[str, ...]


@dataclass(frozen=True)
class ComparisonCoverage:
    candidate_count: int
    eligible_count: int
    provisional_count: int
    excluded_count: int
    coverage_numerator: int
    coverage_denominator: int
    coverage_ratio: str | None
    calendar_span_months: int | None = None
    distinct_financial_anchor_count: int | None = None


@dataclass(frozen=True)
class ComparisonStatus:
    state: str
    reason_records: tuple[Mapping[str, Any], ...]
    canonical_statistic_available: bool
    ranking_available: bool
    publication_eligible: bool
    current_use_eligible: bool


@dataclass(frozen=True)
class ComparisonLineage:
    engine_version: str
    comparison_schema_version: str
    supersedes: Mapping[str, Any] | None
    dag: Mapping[str, Any]


@dataclass(frozen=True)
class ValuationComparison:
    """The full parsed, immutable generated comparison. ``raw`` retains
    the exact schema-validated source mapping, and ``statistics_or_matrix``
    is left as a plain frozen mapping (rather than four parallel typed
    variant dataclasses) since only one of the four shapes is ever present
    per artifact and callers already know which shape to expect from
    ``comparison_type`` -- a caller reads the sub-fields it needs directly
    rather than growing a dataclass for every nested shape."""

    artifact_id: str
    identity: ComparisonIdentity
    comparison_type: str
    temporal_context: Mapping[str, Any]
    subject_refs: tuple[ComparisonSubjectRef, ...]
    universe_ref: Mapping[str, Any] | None
    method_or_dimension_scope: Mapping[str, Any]
    eligibility_records: tuple[EligibilityRecord, ...]
    observations: tuple[ComparisonObservationRecord, ...]
    statistics_or_matrix: Mapping[str, Any]
    ranking_records: tuple[RankingRecord, ...]
    confidence: ComparisonConfidence
    coverage: ComparisonCoverage
    status: ComparisonStatus
    comparison_refs: tuple[Mapping[str, Any], ...]
    lineage: ComparisonLineage
    raw: Mapping[str, Any]

    def eligibility_by_ref(self, subject_ref: str, method_or_dimension_id: str) -> EligibilityRecord:
        for record in self.eligibility_records:
            if record.subject_ref == subject_ref and record.method_or_dimension_id == method_or_dimension_id:
                return record
        raise KeyError(f"valuation_comparison {self.artifact_id!r} has no eligibility record for ({subject_ref!r}, {method_or_dimension_id!r})")


def parse_valuation_comparison(artifact: Mapping[str, Any]) -> ValuationComparison:
    """Structure an already schema-validated ``valuation_comparison`` JSON
    object into the immutable :class:`ValuationComparison` model. Raises
    ``KeyError``/``TypeError`` only if called against a payload that was
    never actually schema-validated -- callers must run it through
    ``schemas.iter_schema_errors`` first."""
    identity_raw = artifact["comparison_identity"]
    identity = ComparisonIdentity(
        comparison_id=identity_raw["comparison_id"], purpose=identity_raw["purpose"], as_of_date=identity_raw["as_of_date"],
        comparison_policy_ref=identity_raw["comparison_policy_ref"], methodology_bundle_ref=identity_raw["methodology_bundle_ref"],
        comparison_currency=identity_raw.get("comparison_currency"),
        universe_version_ref=_frozen(identity_raw.get("universe_version_ref")),
    )

    subject_refs = tuple(
        ComparisonSubjectRef(
            subject_ref_id=s["subject_ref_id"], subject_kind=s["subject_kind"], ticker=s["ticker"],
            as_of_date=s.get("as_of_date"), artifact_ref=_frozen(s.get("artifact_ref")),
            embedded_record_ref=_frozen(s.get("embedded_record_ref")),
        )
        for s in artifact["subject_refs"]
    )

    eligibility_records = tuple(
        EligibilityRecord(
            subject_ref=e["subject_ref"], method_or_dimension_id=e["method_or_dimension_id"], eligibility_state=e["eligibility_state"],
            reason_codes=_frozen_tuple_of_mappings(e["reason_codes"]), data_confidence=e["data_confidence"],
            model_confidence=e["model_confidence"], ranking_confidence=e["ranking_confidence"],
            current_use_eligible=e["current_use_eligible"], included_in_statistic=e["included_in_statistic"],
        )
        for e in artifact.get("eligibility_records", ())
    )

    observations = tuple(
        ComparisonObservationRecord(
            observation_id=o["observation_id"], subject_ref=o["subject_ref"], method_or_dimension_id=o["method_or_dimension_id"],
            value_or_state=_frozen(o["value_or_state"]), eligibility_ref=o["eligibility_ref"],
            lineage_node_refs=_tuple_of(o["lineage_node_refs"]), direction_interpretation=o.get("direction_interpretation"),
            period_or_as_of=o.get("period_or_as_of"), financial_anchor_ref=o.get("financial_anchor_ref"),
            method_variant_ref=o.get("method_variant_ref"), currency_basis_ref=o.get("currency_basis_ref"),
            corporate_action_basis_ref=o.get("corporate_action_basis_ref"),
        )
        for o in artifact.get("observations", ())
    )

    ranking_records = tuple(
        RankingRecord(
            subject_ref=r["subject_ref"], scope_id=r["scope_id"], sample_size=r["sample_size"],
            coverage_ratio=r.get("coverage_ratio"), direction=r["direction"], eligibility_ref=r["eligibility_ref"],
            ranking_confidence=r["ranking_confidence"], provisional=r["provisional"], rank=r.get("rank"),
            percentile=r.get("percentile"), tie_group_id=r.get("tie_group_id"),
        )
        for r in artifact.get("ranking_records", ())
    )

    confidence_raw = artifact["confidence"]
    confidence = ComparisonConfidence(
        sample_size_confidence=confidence_raw["sample_size_confidence"], method_coverage_confidence=confidence_raw["method_coverage_confidence"],
        comparability_confidence=confidence_raw["comparability_confidence"], source_confidence=confidence_raw["source_confidence"],
        overall_ranking_confidence=confidence_raw["overall_ranking_confidence"], limiting_refs=_tuple_of(confidence_raw["limiting_refs"]),
    )

    coverage_raw = artifact["coverage"]
    coverage = ComparisonCoverage(**{k: coverage_raw.get(k) for k in (
        "candidate_count", "eligible_count", "provisional_count", "excluded_count",
        "coverage_numerator", "coverage_denominator", "coverage_ratio",
        "calendar_span_months", "distinct_financial_anchor_count",
    )})

    status_raw = artifact["status"]
    status = ComparisonStatus(
        state=status_raw["state"], reason_records=_frozen_tuple_of_mappings(status_raw["reason_records"]),
        canonical_statistic_available=status_raw["canonical_statistic_available"], ranking_available=status_raw["ranking_available"],
        publication_eligible=status_raw["publication_eligible"], current_use_eligible=status_raw["current_use_eligible"],
    )

    lineage_raw = artifact["lineage"]
    lineage = ComparisonLineage(
        engine_version=lineage_raw["engine_version"], comparison_schema_version=lineage_raw["comparison_schema_version"],
        supersedes=_frozen(lineage_raw.get("supersedes")), dag=MappingProxyType(dict(lineage_raw["dag"])),
    )

    return ValuationComparison(
        artifact_id=artifact["artifact_id"],
        identity=identity, comparison_type=artifact["comparison_type"], temporal_context=MappingProxyType(dict(artifact["temporal_context"])),
        subject_refs=subject_refs, universe_ref=_frozen(artifact.get("universe_ref")),
        method_or_dimension_scope=MappingProxyType(dict(artifact["method_or_dimension_scope"])),
        eligibility_records=eligibility_records, observations=observations,
        statistics_or_matrix=MappingProxyType(dict(artifact["statistics_or_matrix"])), ranking_records=ranking_records,
        confidence=confidence, coverage=coverage, status=status,
        comparison_refs=_frozen_tuple_of_mappings(artifact.get("comparison_refs")), lineage=lineage,
        raw=MappingProxyType(dict(artifact)),
    )
