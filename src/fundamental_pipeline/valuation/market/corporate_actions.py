"""Closed, immutable corporate-action bundle parser (T70 corporate-action
integration).

Mirrors ``observations.py``'s parse-time immutability and closed-field
discipline for the governed corporate-action bundle
(``schemas/corporate-action-bundle.schema.json``) produced by
``fundamental_pipeline.valuation.ingestion.share_count``'s promotion
engine and optionally supplied to :func:`~.resolver.resolve_market_snapshot`
via ``MarketResolutionRequest.corporate_action_bundle``.

This module lives in ``market/`` (not ``ingestion/``): the T70 resolver
package never imports the ingestion package (see the import-boundary
test), so consuming a corporate-action bundle here is a plain, ticker-free
parse of an already-generated, already-schema-validated document -- never
a re-import of the promotion engine that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..errors import MarketResolutionError

EVENT_TYPES = (
    "split", "reverse_split", "capital_increase", "capital_reduction",
    "treasury_purchase", "treasury_sale", "cancellation", "class_conversion",
    "depositary_ratio_change", "other",
)
EVENT_STATUSES = ("announced", "approved", "effective", "cancelled", "unknown")
COVERAGE_STATUSES = ("complete", "gap", "unknown")
REVISION_STATUSES = ("original", "corrected", "restated", "withdrawn", "unknown")

_REQUIRED_EVENT_FIELDS = (
    "event_id", "event_type", "instrument_id", "available_at", "effective_date",
    "status", "source_manifest_id", "revision_status",
)
_OPTIONAL_EVENT_FIELDS = (
    "announcement_at", "source_record_ref", "revision_id",
    "pre_issued_quote_units", "post_issued_quote_units",
    "pre_treasury_quote_units", "post_treasury_quote_units", "adjustment_ratio",
)
_ALL_EVENT_FIELDS = frozenset(_REQUIRED_EVENT_FIELDS) | frozenset(_OPTIONAL_EVENT_FIELDS)

_REQUIRED_COVERAGE_FIELDS = (
    "coverage_start_date", "coverage_end_date", "coverage_status", "reviewed_at",
    "review_method", "reviewed_source_refs", "unresolved_gap_refs",
)

_REQUIRED_BUNDLE_FIELDS = (
    "ticker", "instrument_id", "as_of_date", "cutoff_instant", "coverage", "events", "source_manifest_refs",
)


@dataclass(frozen=True)
class CorporateActionEvent:
    event_id: str
    event_type: str
    instrument_id: str
    available_at: str
    effective_date: str
    status: str
    source_manifest_id: str
    revision_status: str
    announcement_at: str | None = None
    source_record_ref: str | None = None
    revision_id: str | None = None
    pre_issued_quote_units: str | None = None
    post_issued_quote_units: str | None = None
    pre_treasury_quote_units: str | None = None
    post_treasury_quote_units: str | None = None
    adjustment_ratio: str | None = None

    def to_snapshot_event(self) -> dict[str, Any]:
        """Project down to the closed 5-field
        ``market-snapshot.schema.json#/$defs/corporateActionEvent`` shape.
        The richer promotion-provenance fields (source refs, quote-unit
        deltas, revision identity, ...) belong to the corporate-action
        bundle artifact itself, never to the snapshot -- the snapshot only
        needs to say *that* an event exists and its effective status."""
        event: dict[str, Any] = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "effective_date": self.effective_date,
            "status": self.status,
        }
        if self.announcement_at is not None:
            event["announcement_at"] = self.announcement_at
        return event


@dataclass(frozen=True)
class CorporateActionCoverage:
    coverage_start_date: str
    coverage_end_date: str
    coverage_status: str
    reviewed_at: str
    review_method: str
    reviewed_source_refs: tuple[str, ...]
    unresolved_gap_refs: tuple[str, ...]


@dataclass(frozen=True)
class CorporateActionBundle:
    ticker: str
    instrument_id: str
    as_of_date: str
    cutoff_instant: str
    coverage: CorporateActionCoverage
    events: tuple[CorporateActionEvent, ...]
    source_manifest_ids: tuple[str, ...]


def _require_nonempty_str(value: Any, *, field_name: str, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise MarketResolutionError(f"{context}: {field_name} must be a non-empty string")
    return value


def _parse_event(raw: Mapping[str, Any], *, index: int) -> CorporateActionEvent:
    if not isinstance(raw, Mapping):
        raise MarketResolutionError(f"corporate-action bundle events[{index}]: must be an object")

    unknown = set(raw.keys()) - _ALL_EVENT_FIELDS
    if unknown:
        raise MarketResolutionError(f"corporate-action bundle events[{index}]: unknown field(s): {sorted(unknown)}")

    missing = [f for f in _REQUIRED_EVENT_FIELDS if f not in raw]
    if missing:
        raise MarketResolutionError(f"corporate-action bundle events[{index}]: missing required field(s): {sorted(missing)}")

    event_id = _require_nonempty_str(raw["event_id"], field_name="event_id", context=f"corporate-action bundle events[{index}]")

    event_type = raw["event_type"]
    if event_type not in EVENT_TYPES:
        raise MarketResolutionError(f"corporate-action event {event_id!r}: event_type must be one of {EVENT_TYPES}, got {event_type!r}")

    status = raw["status"]
    if status not in EVENT_STATUSES:
        raise MarketResolutionError(f"corporate-action event {event_id!r}: status must be one of {EVENT_STATUSES}, got {status!r}")

    revision_status = raw["revision_status"]
    if revision_status not in REVISION_STATUSES:
        raise MarketResolutionError(f"corporate-action event {event_id!r}: revision_status must be one of {REVISION_STATUSES}, got {revision_status!r}")

    instrument_id = _require_nonempty_str(raw["instrument_id"], field_name="instrument_id", context=f"corporate-action event {event_id!r}")
    available_at = _require_nonempty_str(raw["available_at"], field_name="available_at", context=f"corporate-action event {event_id!r}")
    effective_date = _require_nonempty_str(raw["effective_date"], field_name="effective_date", context=f"corporate-action event {event_id!r}")
    source_manifest_id = _require_nonempty_str(raw["source_manifest_id"], field_name="source_manifest_id", context=f"corporate-action event {event_id!r}")

    for optional_str in (
        "announcement_at", "source_record_ref", "revision_id",
        "pre_issued_quote_units", "post_issued_quote_units",
        "pre_treasury_quote_units", "post_treasury_quote_units", "adjustment_ratio",
    ):
        value = raw.get(optional_str)
        if value is not None and not isinstance(value, str):
            raise MarketResolutionError(f"corporate-action event {event_id!r}: {optional_str} must be a string or absent")

    return CorporateActionEvent(
        event_id=event_id,
        event_type=event_type,
        instrument_id=instrument_id,
        available_at=available_at,
        effective_date=effective_date,
        status=status,
        source_manifest_id=source_manifest_id,
        revision_status=revision_status,
        announcement_at=raw.get("announcement_at"),
        source_record_ref=raw.get("source_record_ref"),
        revision_id=raw.get("revision_id"),
        pre_issued_quote_units=raw.get("pre_issued_quote_units"),
        post_issued_quote_units=raw.get("post_issued_quote_units"),
        pre_treasury_quote_units=raw.get("pre_treasury_quote_units"),
        post_treasury_quote_units=raw.get("post_treasury_quote_units"),
        adjustment_ratio=raw.get("adjustment_ratio"),
    )


def _parse_coverage(raw: Any) -> CorporateActionCoverage:
    if not isinstance(raw, Mapping):
        raise MarketResolutionError("corporate-action bundle: 'coverage' must be an object")
    missing = [f for f in _REQUIRED_COVERAGE_FIELDS if f not in raw]
    if missing:
        raise MarketResolutionError(f"corporate-action bundle coverage: missing required field(s): {sorted(missing)}")

    coverage_status = raw["coverage_status"]
    if coverage_status not in COVERAGE_STATUSES:
        raise MarketResolutionError(f"corporate-action bundle coverage: coverage_status must be one of {COVERAGE_STATUSES}, got {coverage_status!r}")

    for list_field in ("reviewed_source_refs", "unresolved_gap_refs"):
        value = raw[list_field]
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise MarketResolutionError(f"corporate-action bundle coverage: {list_field} must be an array")
        for i, item in enumerate(value):
            if not isinstance(item, str) or not item:
                raise MarketResolutionError(f"corporate-action bundle coverage {list_field}[{i}]: must be a non-empty string")

    return CorporateActionCoverage(
        coverage_start_date=_require_nonempty_str(raw["coverage_start_date"], field_name="coverage_start_date", context="corporate-action bundle coverage"),
        coverage_end_date=_require_nonempty_str(raw["coverage_end_date"], field_name="coverage_end_date", context="corporate-action bundle coverage"),
        coverage_status=coverage_status,
        reviewed_at=_require_nonempty_str(raw["reviewed_at"], field_name="reviewed_at", context="corporate-action bundle coverage"),
        review_method=_require_nonempty_str(raw["review_method"], field_name="review_method", context="corporate-action bundle coverage"),
        reviewed_source_refs=tuple(raw["reviewed_source_refs"]),
        unresolved_gap_refs=tuple(raw["unresolved_gap_refs"]),
    )


def parse_corporate_action_bundle(document: Mapping[str, Any]) -> CorporateActionBundle:
    """Parse a governed ``corporate-action-bundle.schema.json`` document
    (already schema-validated and hash-verified by the caller) into an
    immutable in-memory bundle. Never returns a partially-parsed result --
    any structural violation raises :class:`MarketResolutionError` for the
    whole bundle, exactly like :func:`observations.parse_observation_bundle`."""
    if not isinstance(document, Mapping):
        raise MarketResolutionError("corporate-action bundle must be a JSON object")

    missing = [f for f in _REQUIRED_BUNDLE_FIELDS if f not in document]
    if missing:
        raise MarketResolutionError(f"corporate-action bundle: missing required field(s): {sorted(missing)}")

    ticker = _require_nonempty_str(document["ticker"], field_name="ticker", context="corporate-action bundle")
    instrument_id = _require_nonempty_str(document["instrument_id"], field_name="instrument_id", context="corporate-action bundle")
    as_of_date = _require_nonempty_str(document["as_of_date"], field_name="as_of_date", context="corporate-action bundle")
    cutoff_instant = _require_nonempty_str(document["cutoff_instant"], field_name="cutoff_instant", context="corporate-action bundle")

    raw_events = document["events"]
    if not isinstance(raw_events, Sequence) or isinstance(raw_events, (str, bytes)):
        raise MarketResolutionError("corporate-action bundle: 'events' must be an array")
    events = [_parse_event(item, index=i) for i, item in enumerate(raw_events)]

    seen: dict[str, int] = {}
    for event in events:
        if event.event_id in seen:
            raise MarketResolutionError(f"duplicate corporate-action event_id: {event.event_id!r}")
        seen[event.event_id] = 1

    coverage = _parse_coverage(document["coverage"])

    raw_refs = document["source_manifest_refs"]
    if not isinstance(raw_refs, Sequence) or isinstance(raw_refs, (str, bytes)) or not raw_refs:
        raise MarketResolutionError("corporate-action bundle: 'source_manifest_refs' must be a non-empty array")
    manifest_ids: list[str] = []
    for i, ref in enumerate(raw_refs):
        if not isinstance(ref, Mapping):
            raise MarketResolutionError(f"corporate-action bundle source_manifest_refs[{i}]: must be an object")
        manifest_ids.append(_require_nonempty_str(ref.get("manifest_id"), field_name="manifest_id", context=f"corporate-action bundle source_manifest_refs[{i}]"))

    return CorporateActionBundle(
        ticker=ticker,
        instrument_id=instrument_id,
        as_of_date=as_of_date,
        cutoff_instant=cutoff_instant,
        coverage=coverage,
        events=tuple(events),
        source_manifest_ids=tuple(manifest_ids),
    )
