"""Normalize a fetched (or replayed) set of :class:`~..eod.models.ProviderSeries`
into the strict internal ``fx-rate-series`` row contract.

Structurally parallel to ``ingestion.eod.normalize`` -- this module never
quarantines a row itself, that is ``validation.py``'s job. rate_convention
is always ``quote_currency_per_base_currency`` (docs/valuation-t07-
currency-fx-contract.md Section 3.1): ``1 base_currency = close x
quote_currency``.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ..eod.models import ProviderSeries

INTERVAL = "1d"
RATE_CONVENTION = "quote_currency_per_base_currency"


def build_normalized_fx_rows(
    series_list: Sequence[ProviderSeries],
    *,
    pair_currencies: Mapping[str, tuple[str, str]],
) -> list[dict]:
    """Reshape every ``status="ok"`` series' rows into the flat
    ``fx-rate-series`` row dict shape (before quarantine classification).
    A ``status="failed"`` series contributes no rows here -- its failure is
    instead surfaced as a blocking finding by the caller (``service.py``),
    never silently treated as "zero valid rows, otherwise fine".

    Output is always sorted by ``(pair_id, trade_date)`` -- final row
    order never depends on the provider's own row order, the input pair
    order, or dict/set iteration order.
    """
    rows: list[dict] = []
    for series in series_list:
        if series.status != "ok":
            continue
        pair_id = series.internal_ticker
        base_currency, quote_currency = pair_currencies[pair_id]
        for row in series.rows:
            rows.append({
                "pair_id": pair_id,
                "provider_symbol": series.provider_symbol,
                "trade_date": row.trade_date,
                "base_currency": base_currency,
                "quote_currency": quote_currency,
                "rate_convention": RATE_CONVENTION,
                "open": row.open.to_dict(),
                "high": row.high.to_dict(),
                "low": row.low.to_dict(),
                "close": row.close.to_dict(),
                "adjusted_close": row.adjusted_close.to_dict(),
                "volume": row.volume.to_dict(),
                "dividend": row.dividend.to_dict(),
                "stock_split": row.stock_split.to_dict(),
                "row_status": "valid",
                "quarantine_reason_codes": [],
                "source_row_reference": {
                    "provider_id": "yfinance",
                    "provider_symbol": series.provider_symbol,
                    "trade_date": row.trade_date,
                    "interval": INTERVAL,
                },
            })
    rows.sort(key=lambda r: (r["pair_id"], r["trade_date"]))
    return rows
