"""Normalize a fetched (or replayed) set of :class:`~.models.ProviderSeries`
into the strict internal ``eod-price-series`` row contract.

This module never quarantines a row itself -- that is ``validation.py``'s
job, run immediately afterward on the rows this module produces. Splitting
the two keeps "what the provider said, reshaped" (this module) separate
from "is it usable" (validation.py), matching this repository's existing
normalize/validate separation elsewhere in the valuation namespace.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .models import ProviderSeries

INTERVAL = "1d"


def build_normalized_rows(
    series_list: Sequence[ProviderSeries],
    *,
    ticker_currencies: Mapping[str, str],
) -> list[dict]:
    """Reshape every ``status="ok"`` series' rows into the flat
    ``eod-price-series`` row dict shape (before quarantine
    classification). A ``status="failed"`` series contributes no rows here
    -- its failure is instead surfaced as a blocking finding by the caller
    (``service.py``), never silently treated as "zero valid rows,
    otherwise fine".

    Output is always sorted by ``(internal_ticker, trade_date)`` -- final
    row order never depends on the provider's own row order, the input
    ticker order, or dict/set iteration order.
    """
    rows: list[dict] = []
    for series in series_list:
        if series.status != "ok":
            continue
        currency = ticker_currencies[series.internal_ticker]
        for row in series.rows:
            rows.append({
                "internal_ticker": series.internal_ticker,
                "provider_symbol": series.provider_symbol,
                "trade_date": row.trade_date,
                "currency": currency,
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
    rows.sort(key=lambda r: (r["internal_ticker"], r["trade_date"]))
    return rows
