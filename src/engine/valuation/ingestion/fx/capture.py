"""Build the canonical, replayable ``fx-provider-extract`` document from a
fetched (or replayed) set of :class:`~..eod.models.ProviderSeries`.

Structurally parallel to ``ingestion.eod.capture`` -- reuses the exact same
``ProviderSeries``/``EndOfDayFetchRequest`` models (per this package's
reuse boundary; see ``ingestion/fx/__init__.py``). ``ProviderSeries.
internal_ticker`` holds the canonical ``BASE/QUOTE`` pair identity for
every FX request (see ``ingestion.eod.models.EndOfDayFetchRequest``, whose
``internal_ticker`` field has no ticker-shaped regex constraint of its
own -- only ``fx-provider-extract.schema.json`` enforces the ``BASE/QUOTE``
pattern at the artifact boundary).

This is a deterministic *capture* of the tabular values already returned
by the YFinance library -- never a claim about the original Yahoo HTTP
payload (docs/yfinance-eod-pilot.md, "Provider extract versus original
HTTP payload").
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..eod.models import EndOfDayFetchRequest, ProviderSeries

__all__ = ["build_fx_provider_extract", "parse_fx_provider_extract"]


def build_fx_provider_extract(
    *,
    provider_config,
    requests: Sequence[EndOfDayFetchRequest],
    series_list: Sequence[ProviderSeries],
    retrieved_at: str,
    provider_library_version: str,
    pair_currencies: Mapping[str, tuple[str, str]],
    provider_timezone: str | None = None,
) -> dict:
    """``requests``/``series_list`` must be the same length and in the same
    requested-pair order (the caller -- ``service.py`` -- guarantees this).
    ``pair_currencies`` maps ``pair_id`` -> ``(base_currency,
    quote_currency)``. The returned dict is plain JSON-native data written
    as-is."""
    if len(requests) != len(series_list):
        raise ValueError("requests and series_list must have the same length")

    request_order = [r.internal_ticker for r in requests]
    if [s.internal_ticker for s in series_list] != request_order:
        raise ValueError("series_list must be in the same order as requests")

    first = requests[0]
    for other in requests[1:]:
        if (other.start_date_inclusive, other.end_date_exclusive, other.interval, other.timeout) != (
            first.start_date_inclusive, first.end_date_exclusive, first.interval, first.timeout
        ):
            raise ValueError("all requests within one fetch run must share the same date range/interval/timeout")

    resolved_symbols = {r.internal_ticker: r.provider_symbol for r in requests}
    resolved_pair_currencies = {
        pair_id: {"base_currency": base, "quote_currency": quote}
        for pair_id, (base, quote) in pair_currencies.items()
    }

    return {
        "schema_version": "1.0.0",
        "artifact_type": "fx_provider_extract",
        "provider": {
            "provider_id": provider_config.provider_id,
            "provider_library": provider_config.provider_library,
            "provider_library_version": provider_library_version,
        },
        "request": {
            "requested_pairs": request_order,
            "resolved_provider_symbols": resolved_symbols,
            "resolved_pair_currencies": resolved_pair_currencies,
            "start_date_inclusive": first.start_date_inclusive,
            "end_date_exclusive": first.end_date_exclusive,
            "interval": first.interval,
            "auto_adjust": first.auto_adjust,
            "actions": first.actions,
            "repair": first.repair,
            "keepna": first.keepna,
            "rounding": first.rounding,
            "prepost": first.prepost,
            "timeout": first.timeout,
            "request_order": request_order,
        },
        "retrieved_at": retrieved_at,
        "provider_timezone": provider_timezone,
        "series": [s.to_dict() for s in series_list],
    }


def parse_fx_provider_extract(document: Mapping[str, Any]) -> tuple[ProviderSeries, ...]:
    """Deserialize a committed ``fx-provider-extract.json`` document's
    ``series`` array back into immutable :class:`ProviderSeries` models,
    for ``fx-bundle replay``. Never re-fetches network data -- the extract
    itself is the sole, immutable source of truth for a replay."""
    return tuple(ProviderSeries.from_dict(raw) for raw in document["series"])
