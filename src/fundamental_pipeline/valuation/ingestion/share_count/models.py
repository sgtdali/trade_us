"""Immutable models for the share-count/corporate-action promotion bridge.

Nothing in this module performs file I/O, reads the process clock, or
imports the price ingestion/promotion packages. See ``ledger.py`` for the
only module allowed to touch the filesystem when loading a ledger, and
``service.py`` for the promotion service's own I/O layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from ...transaction import TransactionResult
from ...validation.findings import Finding
from .errors import LedgerError, PromotionPolicyError

_CONTROLLED_CONCEPTS = ("issued_shares", "treasury_shares")
_DERIVATION_TYPES = (
    "direct_disclosure",
    "derived_from_nominal_capital",
    "derived_from_direct_nominal_amount",
    "derived_from_percentage",
    "reconciled_from_components",
)
_REVISION_STATUSES = ("original", "corrected", "restated", "withdrawn", "unknown")
_CORPORATE_ACTION_EVENT_TYPES = (
    "split", "reverse_split", "capital_increase", "capital_reduction",
    "treasury_purchase", "treasury_sale", "cancellation", "class_conversion", "other",
)
_CORPORATE_ACTION_STATUSES = ("announced", "approved", "effective", "cancelled", "unknown")
_COVERAGE_STATUSES = ("complete", "gap", "unknown")


@dataclass(frozen=True)
class QuoteUnitBasis:
    """Distinguishes statutory legal shares from BIST market-quote-
    compatible units. ``legal_shares_per_market_quote_unit`` must equal
    ``market_quote_unit_nominal_value / statutory_nominal_value_per_legal_share``
    exactly (an integer) -- this is validated at construction, never
    trusted from the raw document alone."""

    statutory_nominal_value_per_legal_share: str
    statutory_nominal_currency: str
    market_quote_unit_nominal_value: str
    market_quote_unit_currency: str
    legal_shares_per_market_quote_unit: int
    t70_output_unit: str
    price_compatibility_basis: str

    @classmethod
    def from_dict(cls, raw: Mapping) -> "QuoteUnitBasis":
        from decimal import Decimal, InvalidOperation

        try:
            statutory = Decimal(raw["statutory_nominal_value_per_legal_share"])
            quote_unit = Decimal(raw["market_quote_unit_nominal_value"])
        except (KeyError, InvalidOperation) as exc:
            raise LedgerError(f"quote_unit_basis: invalid or missing nominal value: {exc}") from exc
        if statutory <= 0 or quote_unit <= 0:
            raise LedgerError("quote_unit_basis: nominal values must be strictly positive")

        declared = raw["legal_shares_per_market_quote_unit"]
        if isinstance(declared, bool) or not isinstance(declared, int) or declared <= 0:
            raise LedgerError("quote_unit_basis: legal_shares_per_market_quote_unit must be a positive integer")

        ratio = quote_unit / statutory
        if ratio != ratio.to_integral_value() or int(ratio) != declared:
            raise LedgerError(
                f"quote_unit_basis: legal_shares_per_market_quote_unit ({declared}) does not equal "
                f"market_quote_unit_nominal_value / statutory_nominal_value_per_legal_share "
                f"({quote_unit} / {statutory} = {ratio}); reject non-integral or internally inconsistent conversions"
            )

        if raw.get("t70_output_unit") != "shares":
            raise LedgerError("quote_unit_basis: t70_output_unit must be 'shares'")

        return cls(
            statutory_nominal_value_per_legal_share=raw["statutory_nominal_value_per_legal_share"],
            statutory_nominal_currency=raw["statutory_nominal_currency"],
            market_quote_unit_nominal_value=raw["market_quote_unit_nominal_value"],
            market_quote_unit_currency=raw["market_quote_unit_currency"],
            legal_shares_per_market_quote_unit=declared,
            t70_output_unit=raw["t70_output_unit"],
            price_compatibility_basis=raw["price_compatibility_basis"],
        )


@dataclass(frozen=True)
class ShareCountRecord:
    record_id: str
    concept: str  # "issued_shares" | "treasury_shares"
    value: str  # decimal string, market-quote units
    effective_at: str
    published_at: str
    available_at: str
    derivation_type: str
    source_refs: tuple[str, ...]
    revision_status: str = "original"
    revision_id: str | None = None
    supersedes_revision_id: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping) -> "ShareCountRecord":
        concept = raw.get("concept")
        if concept not in _CONTROLLED_CONCEPTS:
            raise LedgerError(f"share-count record {raw.get('record_id')!r}: concept must be one of {_CONTROLLED_CONCEPTS}, got {concept!r}")
        derivation_type = raw.get("derivation_type")
        if derivation_type not in _DERIVATION_TYPES:
            raise LedgerError(f"share-count record {raw.get('record_id')!r}: derivation_type must be one of {_DERIVATION_TYPES}")
        if derivation_type != "direct_disclosure" and not raw.get("derivation_operands"):
            raise LedgerError(f"share-count record {raw.get('record_id')!r}: derivation_operands required when derivation_type is not direct_disclosure")
        revision_status = raw.get("revision_status", "original")
        if revision_status not in _REVISION_STATUSES:
            raise LedgerError(f"share-count record {raw.get('record_id')!r}: revision_status must be one of {_REVISION_STATUSES}")
        source_refs = raw.get("source_refs") or []
        if not source_refs:
            raise LedgerError(f"share-count record {raw.get('record_id')!r}: source_refs must be non-empty")
        return cls(
            record_id=raw["record_id"],
            concept=concept,
            value=raw["value"],
            effective_at=raw["effective_at"],
            published_at=raw["published_at"],
            available_at=raw["available_at"],
            derivation_type=derivation_type,
            source_refs=tuple(source_refs),
            revision_status=revision_status,
            revision_id=raw.get("revision_id"),
            supersedes_revision_id=raw.get("supersedes_revision_id"),
        )


@dataclass(frozen=True)
class CorporateActionLedgerEntry:
    event_id: str
    event_type: str
    instrument_id: str
    available_at: str
    effective_date: str
    status: str
    source_refs: tuple[str, ...]
    revision_status: str = "original"
    announcement_at: str | None = None
    pre_issued_quote_units: str | None = None
    post_issued_quote_units: str | None = None
    pre_treasury_quote_units: str | None = None
    post_treasury_quote_units: str | None = None
    adjustment_ratio: str | None = None
    revision_id: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping) -> "CorporateActionLedgerEntry":
        event_type = raw.get("event_type")
        if event_type not in _CORPORATE_ACTION_EVENT_TYPES:
            raise LedgerError(f"corporate-action entry {raw.get('event_id')!r}: event_type must be one of {_CORPORATE_ACTION_EVENT_TYPES}")
        status = raw.get("status")
        if status not in _CORPORATE_ACTION_STATUSES:
            raise LedgerError(f"corporate-action entry {raw.get('event_id')!r}: status must be one of {_CORPORATE_ACTION_STATUSES}")
        revision_status = raw.get("revision_status", "original")
        if revision_status not in _REVISION_STATUSES:
            raise LedgerError(f"corporate-action entry {raw.get('event_id')!r}: revision_status must be one of {_REVISION_STATUSES}")
        source_refs = raw.get("source_refs") or []
        if not source_refs:
            raise LedgerError(f"corporate-action entry {raw.get('event_id')!r}: source_refs must be non-empty")
        return cls(
            event_id=raw["event_id"],
            event_type=event_type,
            instrument_id=raw["instrument_id"],
            available_at=raw["available_at"],
            effective_date=raw["effective_date"],
            status=status,
            source_refs=tuple(source_refs),
            revision_status=revision_status,
            announcement_at=raw.get("announcement_at"),
            pre_issued_quote_units=raw.get("pre_issued_quote_units"),
            post_issued_quote_units=raw.get("post_issued_quote_units"),
            pre_treasury_quote_units=raw.get("pre_treasury_quote_units"),
            post_treasury_quote_units=raw.get("post_treasury_quote_units"),
            adjustment_ratio=raw.get("adjustment_ratio"),
            revision_id=raw.get("revision_id"),
        )


@dataclass(frozen=True)
class CoverageRecord:
    coverage_start_date: str
    coverage_end_date: str
    coverage_status: str
    reviewed_at: str
    review_method: str
    reviewed_source_refs: tuple[str, ...]
    unresolved_gap_refs: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: Mapping) -> "CoverageRecord":
        status = raw.get("coverage_status")
        if status not in _COVERAGE_STATUSES:
            raise LedgerError(f"coverage: coverage_status must be one of {_COVERAGE_STATUSES}, got {status!r}")
        if raw["coverage_start_date"] > raw["coverage_end_date"]:
            raise LedgerError("coverage: coverage_start_date must not be after coverage_end_date")
        return cls(
            coverage_start_date=raw["coverage_start_date"],
            coverage_end_date=raw["coverage_end_date"],
            coverage_status=status,
            reviewed_at=raw["reviewed_at"],
            review_method=raw["review_method"],
            reviewed_source_refs=tuple(raw.get("reviewed_source_refs") or ()),
            unresolved_gap_refs=tuple(raw.get("unresolved_gap_refs") or ()),
        )


@dataclass(frozen=True)
class ShareCountLedger:
    ledger_id: str
    ledger_version: str
    ticker: str
    instrument_id: str
    trading_currency: str
    quote_unit_basis: QuoteUnitBasis
    records: tuple[ShareCountRecord, ...]
    corporate_actions: tuple[CorporateActionLedgerEntry, ...]
    coverage: CoverageRecord
    share_class_id: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping) -> "ShareCountLedger":
        if raw.get("artifact_type") != "share_count_ledger":
            raise LedgerError(f"ledger artifact_type must be 'share_count_ledger', got {raw.get('artifact_type')!r}")
        if raw.get("owner_type") != "authored":
            raise LedgerError("ledger owner_type must be 'authored'")

        source_ids = {loc["source_id"] for loc in raw.get("source_catalog", [])}
        records = tuple(ShareCountRecord.from_dict(r) for r in raw.get("records", []))
        corporate_actions = tuple(CorporateActionLedgerEntry.from_dict(e) for e in raw.get("corporate_actions", []))

        for record in records:
            unresolved = [s for s in record.source_refs if s not in source_ids]
            if unresolved:
                raise LedgerError(f"share-count record {record.record_id!r}: source_ref(s) not found in source_catalog: {unresolved}")
        for entry in corporate_actions:
            unresolved = [s for s in entry.source_refs if s not in source_ids]
            if unresolved:
                raise LedgerError(f"corporate-action entry {entry.event_id!r}: source_ref(s) not found in source_catalog: {unresolved}")

        return cls(
            ledger_id=raw["ledger_id"],
            ledger_version=raw["ledger_version"],
            ticker=raw["ticker"],
            instrument_id=raw["instrument_id"],
            trading_currency=raw["trading_currency"],
            quote_unit_basis=QuoteUnitBasis.from_dict(raw["quote_unit_basis"]),
            records=records,
            corporate_actions=corporate_actions,
            coverage=CoverageRecord.from_dict(raw["coverage"]),
            share_class_id=raw.get("share_class_id"),
        )


_DERIVATION_PRIORITY = (
    "direct_disclosure", "derived_from_direct_nominal_amount", "derived_from_nominal_capital",
    "reconciled_from_components", "derived_from_percentage",
)


@dataclass(frozen=True)
class PromotionPolicy:
    policy_id: str
    policy_version: str
    derivation_priority: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: Mapping) -> "PromotionPolicy":
        if raw.get("artifact_type") != "share_count_promotion_policy":
            raise PromotionPolicyError(f"policy artifact_type must be 'share_count_promotion_policy', got {raw.get('artifact_type')!r}")
        concepts = raw.get("controlled_concepts") or []
        if set(concepts) != set(_CONTROLLED_CONCEPTS):
            raise PromotionPolicyError(f"policy controlled_concepts must be exactly {sorted(_CONTROLLED_CONCEPTS)}")
        reconciliation = raw.get("reconciliation") or {}
        for key in ("require_issued_positive", "require_treasury_nonnegative", "require_treasury_lte_issued", "require_outstanding_positive"):
            if reconciliation.get(key) is not True:
                raise PromotionPolicyError(f"policy reconciliation.{key} must be true")
        if (raw.get("zero_handling") or {}).get("treasury_zero_requires_explicit_evidence") is not True:
            raise PromotionPolicyError("policy zero_handling.treasury_zero_requires_explicit_evidence must be true")
        derivation_priority = tuple(raw.get("derivation_priority") or ())
        if set(derivation_priority) != set(_DERIVATION_TYPES) or derivation_priority[-1] != "derived_from_percentage":
            raise PromotionPolicyError(
                "policy derivation_priority must list all derivation types exactly once, with "
                "'derived_from_percentage' last (lowest priority)"
            )
        if (raw.get("corporate_action_coverage_policy") or {}).get("current_valuation_requires_status") != "complete":
            raise PromotionPolicyError("policy corporate_action_coverage_policy.current_valuation_requires_status must be 'complete'")
        return cls(
            policy_id=raw["policy_id"],
            policy_version=raw["policy_version"],
            derivation_priority=derivation_priority,
        )


@dataclass(frozen=True)
class PromotionOutcome:
    """The fully-built, in-memory result of a pure promotion run -- every
    field is already hashed/canonicalizable; no filesystem access is
    required to produce this. ``observations_doc``/``corporate_actions_doc``/
    ``validation_doc``/``promotion_manifest_doc`` are exactly the four
    files a promotion writes."""

    overall_status: str  # "valid" | "invalid"
    observations_doc: dict
    corporate_actions_doc: dict
    validation_doc: dict
    promotion_manifest_doc: dict
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    finding_counts: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.overall_status == "valid"


@dataclass(frozen=True)
class PromotionRunResult:
    """The filesystem-level result of one ``promote(...)`` service call:
    the pure :class:`PromotionOutcome` plus the transactional write result."""

    outcome: PromotionOutcome
    transaction: TransactionResult

    @property
    def ok(self) -> bool:
        if self.transaction.status == "drift":
            return False
        return self.outcome.ok
