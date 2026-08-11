"""Immutable models for the EOD-close promotion bridge.

Nothing in this module performs file I/O, reads the process clock, or
imports the EOD ingestion provider adapter -- see ``service.py`` for the
only module in this package allowed to touch the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ...transaction import TransactionResult
from ...validation.findings import Finding
from .errors import PromotionPolicyError

#: The only governed value today -- effective_at is always supplied
#: explicitly by the caller (CLI ``--effective-at``), never derived from an
#: unverified local closing-auction time. See the repository's temporary-
#: use-exception decision document and the loaded policy's own
#: ``effective_at_verification_note`` for why this is the current state,
#: not a shortcut.
_EFFECTIVE_AT_SOURCE = "explicit_cli_argument"
_SELECTED_PRICE_FIELD = "close"
_PRICE_MODE = "official_close"
_AVAILABLE_AT_SOURCE = "provider_extract.retrieved_at"
_PUBLISHED_AT_SOURCE = "provider_extract.retrieved_at"

_POLICY_REQUIRED_FIELDS = (
    "schema_version", "artifact_type", "policy_id", "policy_version", "exchange", "timezone",
    "effective_at_source", "effective_at_verification_note", "max_fallback_lag_days",
    "selected_price_field", "price_mode", "timestamp_proxy_rules",
)
_TIMESTAMP_PROXY_REQUIRED_FIELDS = ("available_at_source", "published_at_source")


@dataclass(frozen=True)
class PromotionPolicy:
    """A governed EOD-close promotion policy
    (``config/market-data/promotion/bist-eod-close-v1.json``). Fixes the
    selected price field, price mode, timestamp-proxy rules, and maximum
    fallback lag; deliberately does *not* fix a local closing time --
    ``effective_at`` remains an explicit, policy-external CLI argument
    until a BIST regular-session close convention has been verified from
    an official source (recorded as a known limitation, never guessed)."""

    policy_id: str
    policy_version: str
    exchange: str
    timezone: str
    effective_at_source: str
    effective_at_verification_note: str
    max_fallback_lag_days: int
    selected_price_field: str
    price_mode: str
    available_at_source: str
    published_at_source: str

    @classmethod
    def from_dict(cls, raw: Mapping) -> "PromotionPolicy":
        if not isinstance(raw, Mapping):
            raise PromotionPolicyError("promotion policy root must be a JSON object")
        missing = [f for f in _POLICY_REQUIRED_FIELDS if f not in raw]
        if missing:
            raise PromotionPolicyError(f"promotion policy missing required field(s): {sorted(missing)}")
        if raw["artifact_type"] != "eod_close_promotion_policy":
            raise PromotionPolicyError(
                f"artifact_type must be 'eod_close_promotion_policy', got {raw['artifact_type']!r}"
            )
        if raw["effective_at_source"] != _EFFECTIVE_AT_SOURCE:
            raise PromotionPolicyError(
                f"effective_at_source must be {_EFFECTIVE_AT_SOURCE!r} (no verified BIST close-time "
                f"convention is governed yet), got {raw['effective_at_source']!r}"
            )
        if raw["selected_price_field"] != _SELECTED_PRICE_FIELD:
            raise PromotionPolicyError(
                f"selected_price_field must be {_SELECTED_PRICE_FIELD!r} (never adjusted_close/open/high/low), "
                f"got {raw['selected_price_field']!r}"
            )
        if raw["price_mode"] != _PRICE_MODE:
            raise PromotionPolicyError(f"price_mode must be {_PRICE_MODE!r}, got {raw['price_mode']!r}")

        max_lag = raw["max_fallback_lag_days"]
        if isinstance(max_lag, bool) or not isinstance(max_lag, int) or max_lag < 0:
            raise PromotionPolicyError(f"max_fallback_lag_days must be a non-negative integer, got {max_lag!r}")

        timestamp_proxy_rules = raw["timestamp_proxy_rules"]
        if not isinstance(timestamp_proxy_rules, Mapping):
            raise PromotionPolicyError("timestamp_proxy_rules must be an object")
        proxy_missing = [f for f in _TIMESTAMP_PROXY_REQUIRED_FIELDS if f not in timestamp_proxy_rules]
        if proxy_missing:
            raise PromotionPolicyError(f"timestamp_proxy_rules missing required field(s): {sorted(proxy_missing)}")
        if timestamp_proxy_rules["available_at_source"] != _AVAILABLE_AT_SOURCE:
            raise PromotionPolicyError(
                f"timestamp_proxy_rules.available_at_source must be {_AVAILABLE_AT_SOURCE!r}"
            )
        if timestamp_proxy_rules["published_at_source"] != _PUBLISHED_AT_SOURCE:
            raise PromotionPolicyError(
                f"timestamp_proxy_rules.published_at_source must be {_PUBLISHED_AT_SOURCE!r}"
            )

        return cls(
            policy_id=raw["policy_id"],
            policy_version=raw["policy_version"],
            exchange=raw["exchange"],
            timezone=raw["timezone"],
            effective_at_source=raw["effective_at_source"],
            effective_at_verification_note=raw["effective_at_verification_note"],
            max_fallback_lag_days=max_lag,
            selected_price_field=raw["selected_price_field"],
            price_mode=raw["price_mode"],
            available_at_source=timestamp_proxy_rules["available_at_source"],
            published_at_source=timestamp_proxy_rules["published_at_source"],
        )


@dataclass(frozen=True)
class SelectedRow:
    """The one normalized ``eod-price-series`` row chosen for promotion."""

    internal_ticker: str
    provider_id: str
    provider_symbol: str
    trade_date: str
    currency: str
    close_value: str
    interval: str = "1d"


@dataclass(frozen=True)
class PromotionOutcome:
    """The fully-built, in-memory result of a pure promotion run -- every
    field is already hashed/canonicalizable; no filesystem access is
    required to produce this. ``observations_doc``/``validation_doc``/
    ``promotion_manifest_doc`` are exactly the three files a promotion
    writes (``observations.json``, ``validation.json``,
    ``promotion-manifest.json``)."""

    overall_status: str  # "valid" | "invalid"
    selected_trade_date: str | None
    observations_doc: dict
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
