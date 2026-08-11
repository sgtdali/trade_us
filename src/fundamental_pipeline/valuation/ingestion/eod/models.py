"""Immutable, provider-neutral EOD ingestion models.

Nothing in this module (or in any module importing only from it) ever
holds a pandas/numpy object -- those are converted to these closed,
frozen dataclasses at the YFinance adapter boundary
(``providers/yfinance_provider.py``) and nowhere else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from .errors import ProviderConfigError, RequestConstructionError

INTERVAL = "1d"

_REQUEST_FIXED_OPTIONS: Mapping[str, object] = {
    "interval": INTERVAL,
    "auto_adjust": False,
    "actions": True,
    "keepna": True,
    "rounding": False,
    "prepost": False,
}


@dataclass(frozen=True)
class FieldValue:
    """One provider-reported field paired with an explicit availability
    status. Never represents "missing" as 0, NaN, Infinity, or an empty
    string -- see docs/yfinance-eod-pilot.md."""

    status: str  # "available" | "unavailable"
    value: str | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ("available", "unavailable"):
            raise ValueError(f"FieldValue.status must be 'available' or 'unavailable', got {self.status!r}")
        if self.status == "available":
            if self.value is None:
                raise ValueError("FieldValue(status='available') requires a non-None value")
            if self.reason_code is not None:
                raise ValueError("FieldValue(status='available') must not carry a reason_code")
        else:
            if self.value is not None:
                raise ValueError("FieldValue(status='unavailable') must not carry a value")
            if not self.reason_code:
                raise ValueError("FieldValue(status='unavailable') requires a reason_code")

    @classmethod
    def available(cls, value: str) -> "FieldValue":
        return cls(status="available", value=value)

    @classmethod
    def unavailable(cls, reason_code: str) -> "FieldValue":
        return cls(status="unavailable", reason_code=reason_code)

    @classmethod
    def from_dict(cls, raw: Mapping) -> "FieldValue":
        return cls(status=raw["status"], value=raw.get("value"), reason_code=raw.get("reason_code"))

    @property
    def decimal_value(self) -> Decimal | None:
        if self.status != "available":
            return None
        return Decimal(self.value)

    def to_dict(self) -> dict:
        d: dict = {"status": self.status}
        if self.value is not None:
            d["value"] = self.value
        if self.reason_code is not None:
            d["reason_code"] = self.reason_code
        return d


@dataclass(frozen=True)
class ProviderRow:
    trade_date: str
    open: FieldValue
    high: FieldValue
    low: FieldValue
    close: FieldValue
    adjusted_close: FieldValue
    volume: FieldValue
    dividend: FieldValue
    stock_split: FieldValue

    def to_dict(self) -> dict:
        return {
            "trade_date": self.trade_date,
            "open": self.open.to_dict(),
            "high": self.high.to_dict(),
            "low": self.low.to_dict(),
            "close": self.close.to_dict(),
            "adjusted_close": self.adjusted_close.to_dict(),
            "volume": self.volume.to_dict(),
            "dividend": self.dividend.to_dict(),
            "stock_split": self.stock_split.to_dict(),
        }

    @classmethod
    def from_dict(cls, raw: Mapping) -> "ProviderRow":
        return cls(
            trade_date=raw["trade_date"],
            open=FieldValue.from_dict(raw["open"]),
            high=FieldValue.from_dict(raw["high"]),
            low=FieldValue.from_dict(raw["low"]),
            close=FieldValue.from_dict(raw["close"]),
            adjusted_close=FieldValue.from_dict(raw["adjusted_close"]),
            volume=FieldValue.from_dict(raw["volume"]),
            dividend=FieldValue.from_dict(raw["dividend"]),
            stock_split=FieldValue.from_dict(raw["stock_split"]),
        )


@dataclass(frozen=True)
class ProviderSeries:
    """One requested ticker's isolated fetch outcome. ``status='failed'``
    isolates this symbol's failure -- it never causes another, genuinely
    successful ticker in the same run to be silently dropped, and it never
    lets the overall run be reported as fully successful either."""

    internal_ticker: str
    provider_symbol: str
    status: str  # "ok" | "failed"
    error_reason: str | None = None
    rows: tuple[ProviderRow, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in ("ok", "failed"):
            raise ValueError(f"ProviderSeries.status must be 'ok' or 'failed', got {self.status!r}")
        if self.status == "failed" and not self.error_reason:
            raise ValueError("ProviderSeries(status='failed') requires error_reason")
        if self.status == "ok" and self.error_reason is not None:
            raise ValueError("ProviderSeries(status='ok') must not carry error_reason")

    def to_dict(self) -> dict:
        d: dict = {
            "internal_ticker": self.internal_ticker,
            "provider_symbol": self.provider_symbol,
            "status": self.status,
            "rows": [r.to_dict() for r in self.rows],
            "warnings": list(self.warnings),
        }
        if self.error_reason is not None:
            d["error_reason"] = self.error_reason
        return d

    @classmethod
    def from_dict(cls, raw: Mapping) -> "ProviderSeries":
        return cls(
            internal_ticker=raw["internal_ticker"],
            provider_symbol=raw["provider_symbol"],
            status=raw["status"],
            error_reason=raw.get("error_reason"),
            rows=tuple(ProviderRow.from_dict(r) for r in raw.get("rows", ())),
            warnings=tuple(raw.get("warnings", ())),
        )


@dataclass(frozen=True)
class EndOfDayFetchRequest:
    """One ticker's fetch request. Every economically relevant YFinance
    option is explicit. Equity EOD ingestion enables YFinance repair while
    FX ingestion leaves it disabled; neither service exposes a CLI override.
    Auto-adjustment and intraday intervals remain forbidden."""

    internal_ticker: str
    provider_symbol: str
    start_date_inclusive: str
    end_date_exclusive: str
    timeout: int = 20
    interval: str = INTERVAL
    auto_adjust: bool = False
    actions: bool = True
    repair: bool = False
    keepna: bool = True
    rounding: bool = False
    prepost: bool = False

    def __post_init__(self) -> None:
        for key, fixed in _REQUEST_FIXED_OPTIONS.items():
            if getattr(self, key) != fixed:
                raise RequestConstructionError(
                    f"EndOfDayFetchRequest.{key} must be {fixed!r} (forbidden to override), got {getattr(self, key)!r}"
                )
        if not isinstance(self.repair, bool):
            raise RequestConstructionError(f"EndOfDayFetchRequest.repair must be a boolean, got {self.repair!r}")
        if not self.internal_ticker:
            raise RequestConstructionError("internal_ticker must be non-empty")
        if not self.provider_symbol:
            raise RequestConstructionError("provider_symbol must be non-empty")
        if self.start_date_inclusive >= self.end_date_exclusive:
            raise RequestConstructionError(
                f"start_date_inclusive ({self.start_date_inclusive!r}) must be strictly before "
                f"end_date_exclusive ({self.end_date_exclusive!r})"
            )
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, int):
            raise RequestConstructionError(f"timeout must be an int (whole seconds), got {self.timeout!r}")
        if self.timeout <= 0:
            raise RequestConstructionError(f"timeout must be strictly positive, got {self.timeout!r}")


@dataclass(frozen=True)
class TickerMapping:
    internal_ticker: str
    provider_symbol: str
    exchange: str
    trading_currency: str
    instrument_type: str
    active: bool


@dataclass(frozen=True)
class FxPairMapping:
    """An FX pair's provider-symbol mapping (additive sibling of
    :class:`TickerMapping`). ``pair_id`` is always canonical ``BASE/QUOTE``
    (docs/valuation-t07-currency-fx-contract.md Section 3.1); ``rate_convention``
    is always explicit -- pair direction is never inferred from the
    provider symbol's own order or numeric magnitude."""

    pair_id: str
    provider_symbol: str
    base_currency: str
    quote_currency: str
    rate_convention: str
    active: bool


_PROVIDER_REQUIRED_FIELDS = (
    "provider_id", "provider_library", "pinned_library_version", "adjustment_policy",
    "revision_policy",
)
_MAPPING_REQUIRED_FIELDS = ("internal_ticker", "provider_symbol", "exchange", "trading_currency", "instrument_type", "active")
_MAPPING_ALL_FIELDS = frozenset(_MAPPING_REQUIRED_FIELDS)
_FX_MAPPING_REQUIRED_FIELDS = ("pair_id", "provider_symbol", "base_currency", "quote_currency", "rate_convention", "active")
_FX_MAPPING_ALL_FIELDS = frozenset(_FX_MAPPING_REQUIRED_FIELDS)
_FX_PAIR_PATTERN = re.compile(r"^[A-Z]{3}/[A-Z]{3}$")
_ALLOWED_RATE_CONVENTIONS = frozenset({"quote_currency_per_base_currency"})

@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    provider_library: str
    pinned_library_version: str
    adjustment_policy: str
    revision_policy: str
    ticker_mappings: tuple[TickerMapping, ...] = field(default_factory=tuple)
    fx_pair_mappings: tuple[FxPairMapping, ...] = field(default_factory=tuple)

    def active_mapping(self, internal_ticker: str) -> TickerMapping | None:
        for mapping in self.ticker_mappings:
            if mapping.internal_ticker == internal_ticker:
                return mapping if mapping.active else None
        return None

    def mapping(self, internal_ticker: str) -> TickerMapping | None:
        for mapping in self.ticker_mappings:
            if mapping.internal_ticker == internal_ticker:
                return mapping
        return None

    def active_fx_mapping(self, pair_id: str) -> FxPairMapping | None:
        for mapping in self.fx_pair_mappings:
            if mapping.pair_id == pair_id:
                return mapping if mapping.active else None
        return None

    def fx_mapping(self, pair_id: str) -> FxPairMapping | None:
        for mapping in self.fx_pair_mappings:
            if mapping.pair_id == pair_id:
                return mapping
        return None

    @classmethod
    def from_dict(cls, raw: Mapping) -> "ProviderConfig":
        if not isinstance(raw, Mapping):
            raise ProviderConfigError("provider config root must be a JSON object")
        missing = [f for f in _PROVIDER_REQUIRED_FIELDS if f not in raw]
        if missing:
            raise ProviderConfigError(f"provider config missing required field(s): {sorted(missing)}")
        if raw["provider_id"] != "yfinance":
            raise ProviderConfigError(f"provider_id must be 'yfinance', got {raw['provider_id']!r}")
        raw_mappings = raw.get("ticker_mappings", [])
        if not isinstance(raw_mappings, Sequence) or isinstance(raw_mappings, (str, bytes)):
            raise ProviderConfigError("ticker_mappings must be an array")

        seen_tickers: set[str] = set()
        mappings: list[TickerMapping] = []
        for index, entry in enumerate(raw_mappings):
            if not isinstance(entry, Mapping):
                raise ProviderConfigError(f"ticker_mappings[{index}]: must be an object")
            unknown = set(entry.keys()) - _MAPPING_ALL_FIELDS
            if unknown:
                raise ProviderConfigError(f"ticker_mappings[{index}]: unknown field(s): {sorted(unknown)}")
            entry_missing = [f for f in _MAPPING_REQUIRED_FIELDS if f not in entry]
            if entry_missing:
                raise ProviderConfigError(f"ticker_mappings[{index}]: missing required field(s): {sorted(entry_missing)}")
            internal_ticker = entry["internal_ticker"]
            if internal_ticker in seen_tickers:
                raise ProviderConfigError(f"ticker_mappings: duplicate internal_ticker {internal_ticker!r}")
            seen_tickers.add(internal_ticker)
            if not isinstance(entry["active"], bool):
                raise ProviderConfigError(f"ticker_mappings[{index}].active must be a boolean")
            mappings.append(TickerMapping(
                internal_ticker=internal_ticker,
                provider_symbol=entry["provider_symbol"],
                exchange=entry["exchange"],
                trading_currency=entry["trading_currency"],
                instrument_type=entry["instrument_type"],
                active=entry["active"],
            ))

        raw_fx_mappings = raw.get("fx_pair_mappings", [])
        if not isinstance(raw_fx_mappings, Sequence) or isinstance(raw_fx_mappings, (str, bytes)):
            raise ProviderConfigError("fx_pair_mappings must be an array")

        seen_pairs: set[str] = set()
        fx_mappings: list[FxPairMapping] = []
        for index, entry in enumerate(raw_fx_mappings):
            if not isinstance(entry, Mapping):
                raise ProviderConfigError(f"fx_pair_mappings[{index}]: must be an object")
            unknown = set(entry.keys()) - _FX_MAPPING_ALL_FIELDS
            if unknown:
                raise ProviderConfigError(f"fx_pair_mappings[{index}]: unknown field(s): {sorted(unknown)}")
            entry_missing = [f for f in _FX_MAPPING_REQUIRED_FIELDS if f not in entry]
            if entry_missing:
                raise ProviderConfigError(f"fx_pair_mappings[{index}]: missing required field(s): {sorted(entry_missing)}")
            pair_id = entry["pair_id"]
            if not isinstance(pair_id, str) or not _FX_PAIR_PATTERN.match(pair_id):
                raise ProviderConfigError(f"fx_pair_mappings[{index}].pair_id must match 'BASE/QUOTE' (e.g. 'USD/TRY'), got {pair_id!r}")
            base_currency, quote_currency = pair_id.split("/")
            if entry["base_currency"] != base_currency or entry["quote_currency"] != quote_currency:
                raise ProviderConfigError(
                    f"fx_pair_mappings[{index}]: base_currency/quote_currency ({entry['base_currency']!r}/"
                    f"{entry['quote_currency']!r}) must exactly match pair_id {pair_id!r}"
                )
            if entry["rate_convention"] not in _ALLOWED_RATE_CONVENTIONS:
                raise ProviderConfigError(f"fx_pair_mappings[{index}].rate_convention must be one of {sorted(_ALLOWED_RATE_CONVENTIONS)}, got {entry['rate_convention']!r}")
            if pair_id in seen_pairs:
                raise ProviderConfigError(f"fx_pair_mappings: duplicate pair_id {pair_id!r}")
            seen_pairs.add(pair_id)
            if not isinstance(entry["active"], bool):
                raise ProviderConfigError(f"fx_pair_mappings[{index}].active must be a boolean")
            fx_mappings.append(FxPairMapping(
                pair_id=pair_id,
                provider_symbol=entry["provider_symbol"],
                base_currency=entry["base_currency"],
                quote_currency=entry["quote_currency"],
                rate_convention=entry["rate_convention"],
                active=entry["active"],
            ))

        return cls(
            provider_id=raw["provider_id"],
            provider_library=raw["provider_library"],
            pinned_library_version=raw["pinned_library_version"],
            adjustment_policy=raw["adjustment_policy"],
            revision_policy=raw["revision_policy"],
            ticker_mappings=tuple(mappings),
            fx_pair_mappings=tuple(fx_mappings),
        )


def decimal_from_provider_number(raw: object) -> Decimal:
    """Convert a provider-supplied numeric value (a Python ``int``/``float``
    or a numpy scalar duck-typed the same way) to an exact :class:`Decimal`
    *without ever calling* ``Decimal(float_value)`` directly -- that would
    capture the float's binary imprecision as spurious extra digits.
    Instead this always round-trips through ``str()``, which for both
    Python ``float`` and ``numpy.float64`` yields the shortest decimal
    string that reads back to the identical binary value. Rejects
    non-finite input; never silently substitutes 0."""
    if isinstance(raw, bool):
        raise ValueError(f"boolean is not a valid provider numeric value: {raw!r}")
    if isinstance(raw, int):
        return Decimal(raw)
    as_float = float(raw)  # duck-types numpy.float64/float32 without importing numpy
    if as_float != as_float or as_float in (float("inf"), float("-inf")):
        raise ValueError(f"non-finite provider numeric value: {raw!r}")
    try:
        return Decimal(str(as_float))
    except InvalidOperation as exc:
        raise ValueError(f"provider numeric value could not be converted to Decimal: {raw!r}") from exc
