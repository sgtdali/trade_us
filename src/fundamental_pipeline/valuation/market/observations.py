"""Closed, immutable market observation model and bundle parser (T70-B).

This module owns the injected-observation transport contract described in
docs/valuation-t70-09-final-coding-task-prompt-acceptance-handoff.md's
governing prompt, Section 6.1: the exact observation record fields are
normatively fixed there (``observation_id``, ``observation_type``,
``instrument_or_pair``, ``value``, ``unit``, ``currency``, ``effective_at``,
``published_at``, ``available_at``, ``source_manifest_id``,
``source_record_ref``, ``revision_id``, ``revision_status``,
``supersedes_revision_id``, ``ingested_at``). No T70 schema defines a sixth
top-level valuation artifact for this wrapper, so the outer bundle shape
(``{"observations": [...]}}``) is kept as an internal closed parser
contract, not a JSON-Schema-governed artifact -- see the module tests for
its exact accepted/rejected shapes.

``observation_type`` is one of ``price`` | ``share_count`` | ``fx``
(docs/valuation-t70-04-market-registry-snapshot-specification.md Section 3).
Share-count observations carry the specific concept
(``issued_shares``/``treasury_shares``/``spot_basic_shares_outstanding``)
as a controlled suffix on ``instrument_or_pair`` rather than inventing a fourth
top-level ``observation_type`` value, since the governing prompt lists
exactly those three.

Observations are immutable after parsing. ``ingested_at`` is evidence
metadata only -- it is carried through unchanged but never participates in
cutoff/selection logic anywhere in this package.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from ..errors import MarketResolutionError

_UTC_INSTANT_RE = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T"
    r"([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{1,6})?Z$"
)
_FX_PAIR_RE = re.compile(r"^[A-Z]{3}/[A-Z]{3}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")

OBSERVATION_TYPES = ("price", "share_count", "fx")
REVISION_STATUSES = ("original", "corrected", "restated", "withdrawn", "unknown")
#: docs/valuation-t05-price-basis-contract.md Section 2 and
#: schemas/market-snapshot.schema.json price_observation.mode -- the exact
#: economic kind of a price tick. Required for every price observation so
#: the resolver never has to guess (or worse, silently hard-code) what
#: kind of price it is dealing with.
PRICE_MODES = ("official_close", "intraday", "historical_close", "diagnostic_reference")
#: docs/valuation-t07-currency-fx-contract.md Section 4 -- the exact
#: economic kind of an FX observation. Required for every fx observation
#: (parallel to price_mode for price observations) so the resolver never
#: has to guess what kind of rate it is dealing with.
FX_MODES = ("daily_benchmark", "market_close", "intraday_spot", "historical_benchmark", "diagnostic_reference", "accounting_translation")

_REQUIRED_FIELDS = (
    "observation_id",
    "observation_type",
    "instrument_or_pair",
    "value",
    "unit",
    "effective_at",
    "published_at",
    "available_at",
    "source_manifest_id",
)
_OPTIONAL_FIELDS = (
    "currency",
    "price_mode",
    "fx_mode",
    "source_record_ref",
    "revision_id",
    "revision_status",
    "supersedes_revision_id",
    "ingested_at",
)
_ALL_FIELDS = frozenset(_REQUIRED_FIELDS) | frozenset(_OPTIONAL_FIELDS)


@dataclass(frozen=True)
class MarketObservation:
    observation_id: str
    observation_type: str
    instrument_or_pair: str
    value: str
    unit: str
    effective_at: str
    published_at: str
    available_at: str
    source_manifest_id: str
    currency: str | None = None
    price_mode: str | None = None
    fx_mode: str | None = None
    source_record_ref: str | None = None
    revision_id: str | None = None
    revision_status: str = "original"
    supersedes_revision_id: str | None = None
    ingested_at: str | None = None

    @property
    def decimal_value(self) -> Decimal:
        return Decimal(self.value)

    @property
    def is_issued_shares(self) -> bool:
        return self.observation_type == "share_count" and self.instrument_or_pair.endswith(":issued_shares")

    @property
    def is_treasury_shares(self) -> bool:
        return self.observation_type == "share_count" and self.instrument_or_pair.endswith(":treasury_shares")

    @property
    def is_spot_basic_shares_outstanding(self) -> bool:
        return self.observation_type == "share_count" and self.instrument_or_pair.endswith(":spot_basic_shares_outstanding")

    @property
    def instrument_id(self) -> str:
        if self.observation_type == "share_count":
            return self.instrument_or_pair.rsplit(":", 1)[0]
        return self.instrument_or_pair


def _require_utc_instant(field_name: str, value: Any, *, observation_id: str) -> str:
    if not isinstance(value, str) or not _UTC_INSTANT_RE.fullmatch(value):
        raise MarketResolutionError(
            f"observation {observation_id!r}: {field_name} must be a UTC instant ending in 'Z' "
            f"(no other timezone offset is accepted), got {value!r}"
        )
    return value


def _parse_one(raw: Mapping[str, Any], *, index: int) -> MarketObservation:
    if not isinstance(raw, Mapping):
        raise MarketResolutionError(f"observations[{index}]: must be an object")

    unknown = set(raw.keys()) - _ALL_FIELDS
    if unknown:
        raise MarketResolutionError(f"observations[{index}]: unknown field(s): {sorted(unknown)}")

    missing = [f for f in _REQUIRED_FIELDS if f not in raw]
    if missing:
        raise MarketResolutionError(f"observations[{index}]: missing required field(s): {sorted(missing)}")

    observation_id = raw["observation_id"]
    if not isinstance(observation_id, str) or not observation_id:
        raise MarketResolutionError(f"observations[{index}]: observation_id must be a non-empty string")

    observation_type = raw["observation_type"]
    if observation_type not in OBSERVATION_TYPES:
        raise MarketResolutionError(
            f"observation {observation_id!r}: observation_type must be one of {OBSERVATION_TYPES}, got {observation_type!r}"
        )

    instrument_or_pair = raw["instrument_or_pair"]
    if not isinstance(instrument_or_pair, str) or not instrument_or_pair:
        raise MarketResolutionError(f"observation {observation_id!r}: instrument_or_pair must be a non-empty string")

    if observation_type == "fx":
        if not _FX_PAIR_RE.fullmatch(instrument_or_pair):
            raise MarketResolutionError(
                f"observation {observation_id!r}: fx instrument_or_pair must match 'BASE/QUOTE' (e.g. 'USD/TRY'), got {instrument_or_pair!r}"
            )
    if observation_type == "share_count":
        if not (
            instrument_or_pair.endswith(":issued_shares")
            or instrument_or_pair.endswith(":treasury_shares")
            or instrument_or_pair.endswith(":spot_basic_shares_outstanding")
        ):
            raise MarketResolutionError(
                f"observation {observation_id!r}: share_count instrument_or_pair must end with "
                f"':issued_shares', ':treasury_shares', or ':spot_basic_shares_outstanding', got {instrument_or_pair!r}"
            )

    raw_value = raw["value"]
    if not isinstance(raw_value, str):
        raise MarketResolutionError(f"observation {observation_id!r}: value must be a decimal string")
    try:
        decimal_value = Decimal(raw_value)
    except InvalidOperation as exc:
        raise MarketResolutionError(f"observation {observation_id!r}: invalid decimal value {raw_value!r}") from exc
    if not decimal_value.is_finite():
        raise MarketResolutionError(f"observation {observation_id!r}: value must be finite")

    if observation_type in ("price", "fx"):
        if decimal_value <= 0:
            raise MarketResolutionError(f"observation {observation_id!r}: {observation_type} value must be strictly positive")
    elif instrument_or_pair.endswith((":issued_shares", ":spot_basic_shares_outstanding")):
        if decimal_value <= 0:
            concept = instrument_or_pair.rsplit(":", 1)[1]
            raise MarketResolutionError(f"observation {observation_id!r}: {concept} value must be strictly positive")
    else:  # treasury_shares
        if decimal_value < 0:
            raise MarketResolutionError(f"observation {observation_id!r}: treasury_shares value must not be negative")

    unit = raw["unit"]
    if not isinstance(unit, str) or not unit:
        raise MarketResolutionError(f"observation {observation_id!r}: unit must be a non-empty string")

    currency = raw.get("currency")
    if currency is not None:
        if not isinstance(currency, str) or not _CURRENCY_RE.fullmatch(currency):
            raise MarketResolutionError(f"observation {observation_id!r}: currency must be a 3-letter ISO 4217 code, got {currency!r}")
    elif observation_type in ("price",):
        raise MarketResolutionError(f"observation {observation_id!r}: price observations require currency")

    price_mode = raw.get("price_mode")
    if observation_type == "price":
        if price_mode not in PRICE_MODES:
            raise MarketResolutionError(
                f"observation {observation_id!r}: price observations require price_mode to be one of {PRICE_MODES}, got {price_mode!r}"
            )
    elif price_mode is not None:
        raise MarketResolutionError(f"observation {observation_id!r}: price_mode is only meaningful for price observations")

    fx_mode = raw.get("fx_mode")
    if observation_type == "fx":
        if fx_mode not in FX_MODES:
            raise MarketResolutionError(
                f"observation {observation_id!r}: fx observations require fx_mode to be one of {FX_MODES}, got {fx_mode!r}"
            )
    elif fx_mode is not None:
        raise MarketResolutionError(f"observation {observation_id!r}: fx_mode is only meaningful for fx observations")

    effective_at = _require_utc_instant("effective_at", raw["effective_at"], observation_id=observation_id)
    published_at = _require_utc_instant("published_at", raw["published_at"], observation_id=observation_id)
    available_at = _require_utc_instant("available_at", raw["available_at"], observation_id=observation_id)

    source_manifest_id = raw["source_manifest_id"]
    if not isinstance(source_manifest_id, str) or not source_manifest_id:
        raise MarketResolutionError(f"observation {observation_id!r}: source_manifest_id must be a non-empty string")

    revision_status = raw.get("revision_status", "original")
    if revision_status not in REVISION_STATUSES:
        raise MarketResolutionError(
            f"observation {observation_id!r}: revision_status must be one of {REVISION_STATUSES}, got {revision_status!r}"
        )

    for optional_str_field in ("source_record_ref", "revision_id", "supersedes_revision_id", "ingested_at"):
        value = raw.get(optional_str_field)
        if value is not None and not isinstance(value, str):
            raise MarketResolutionError(f"observation {observation_id!r}: {optional_str_field} must be a string or absent")

    if raw.get("supersedes_revision_id") and not raw.get("revision_id"):
        raise MarketResolutionError(
            f"observation {observation_id!r}: supersedes_revision_id requires revision_id to also be present"
        )

    return MarketObservation(
        observation_id=observation_id,
        observation_type=observation_type,
        instrument_or_pair=instrument_or_pair,
        value=raw_value,
        unit=unit,
        currency=currency,
        price_mode=price_mode,
        fx_mode=fx_mode,
        effective_at=effective_at,
        published_at=published_at,
        available_at=available_at,
        source_manifest_id=source_manifest_id,
        source_record_ref=raw.get("source_record_ref"),
        revision_id=raw.get("revision_id"),
        revision_status=revision_status,
        supersedes_revision_id=raw.get("supersedes_revision_id"),
        ingested_at=raw.get("ingested_at"),
    )


def parse_observation_bundle(document: Mapping[str, Any]) -> tuple[MarketObservation, ...]:
    """Parse the closed ``{"observations": [...]}`` bundle wrapper into an
    immutable, ordered tuple of :class:`MarketObservation`. Rejects
    duplicate ``observation_id`` values and NFC-normalization-colliding
    IDs. Never returns a partially-parsed result -- any structural or
    semantic violation raises :class:`MarketResolutionError` for the whole
    bundle."""
    if not isinstance(document, Mapping):
        raise MarketResolutionError("observation bundle must be a JSON object")
    unknown = set(document.keys()) - {"observations"}
    if unknown:
        raise MarketResolutionError(f"observation bundle: unknown top-level field(s): {sorted(unknown)}")
    raw_observations = document.get("observations")
    if not isinstance(raw_observations, Sequence) or isinstance(raw_observations, (str, bytes)):
        raise MarketResolutionError("observation bundle: 'observations' must be an array")

    observations = [_parse_one(item, index=i) for i, item in enumerate(raw_observations)]

    seen_raw: dict[str, int] = {}
    seen_normalized: dict[str, str] = {}
    for observation in observations:
        oid = observation.observation_id
        if oid in seen_raw:
            raise MarketResolutionError(f"duplicate observation_id: {oid!r}")
        seen_raw[oid] = 1
        normalized = unicodedata.normalize("NFC", oid)
        if normalized in seen_normalized and seen_normalized[normalized] != oid:
            raise MarketResolutionError(
                f"observation_id {oid!r} collides with {seen_normalized[normalized]!r} after NFC normalization"
            )
        seen_normalized[normalized] = oid

    return tuple(observations)
