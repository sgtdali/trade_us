"""The YFinance pilot adapter -- the only module in this subsystem that may
import ``yfinance`` or ``pandas``, and it does so lazily so that importing
this module (or anything importing only from ``engine.valuation``
without touching the ``market-ingestion`` CLI) never requires the optional
``market`` dependency group.

Exact request contract (docs/yfinance-eod-pilot.md, per-ticker isolated
calls, never ``yf.download()``'s multi-ticker batch path, so one symbol's
provider error can never corrupt or silently drop another symbol's
result)::

    yf.Ticker(provider_symbol).history(
        start=..., end=..., interval="1d",
        auto_adjust=False, actions=True, repair=<explicit>, keepna=True,
        rounding=False, prepost=False, back_adjust=False, timeout=...,
    )
"""

from __future__ import annotations

from typing import Any, Sequence

from ....canonical import normalize_decimal
from ..errors import ProviderBootstrapError
from ..models import EndOfDayFetchRequest, FieldValue, ProviderRow, ProviderSeries, decimal_from_provider_number

_PRICE_COLUMNS = ("Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits")
_FIELD_TO_COLUMN = {
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "adjusted_close": "Adj Close",
    "volume": "Volume",
    "dividend": "Dividends",
    "stock_split": "Stock Splits",
}


def import_yfinance() -> Any:
    """Import and return the ``yfinance`` module, or raise
    :class:`ProviderBootstrapError` with an actionable message -- never a
    raw ``ImportError`` reaching a caller (the CLI maps this to exit code
    2, per docs Section 10)."""
    try:
        import yfinance  # noqa: F401  (imported lazily, deliberately not at module scope)
    except ImportError as exc:
        raise ProviderBootstrapError(
            "the optional 'yfinance' dependency is not installed. "
            "Install it with: python -m pip install -e '.[market]'"
        ) from exc
    return yfinance


def yfinance_library_version() -> str:
    yfinance = import_yfinance()
    return str(getattr(yfinance, "__version__", "unknown"))


def _field_value(row: Any, columns: frozenset, field_name: str) -> FieldValue:
    column = _FIELD_TO_COLUMN[field_name]
    if column not in columns:
        return FieldValue.unavailable("provider.field_missing")
    raw = row[column]
    if raw is None:
        return FieldValue.unavailable("provider.value_missing_row")
    try:
        if raw != raw:  # NaN != NaN is True for both python float and numpy.float64
            return FieldValue.unavailable("provider.value_missing_row")
    except TypeError:
        pass
    try:
        decimal_value = decimal_from_provider_number(raw)
    except ValueError:
        return FieldValue.unavailable("provider.value_non_finite")
    return FieldValue.available(normalize_decimal(decimal_value))


def _trade_date_of(index_value: Any) -> str:
    strftime = getattr(index_value, "strftime", None)
    if callable(strftime):
        return strftime("%Y-%m-%d")
    return str(index_value)[:10]


def dataframe_to_provider_series(df: Any, *, internal_ticker: str, provider_symbol: str) -> ProviderSeries:
    """Pure DataFrame -> :class:`ProviderSeries` conversion. Takes an
    already-fetched pandas ``DataFrame`` (or, for tests, anything exposing
    the same ``.columns``/``.iterrows()`` duck-typed surface) and returns
    an immutable, provider-neutral model -- never a pandas object. Row and
    column order in the input never affects the *set* of rows produced;
    the caller (``normalize.py``) is responsible for final deterministic
    ordering."""
    if df is None or len(df) == 0:
        return ProviderSeries(
            internal_ticker=internal_ticker, provider_symbol=provider_symbol,
            status="ok", rows=(), warnings=("provider.empty_response",),
        )

    columns = frozenset(df.columns)
    rows: list[ProviderRow] = []
    warnings: list[str] = []
    for index_value, row in df.iterrows():
        trade_date = _trade_date_of(index_value)
        rows.append(ProviderRow(
            trade_date=trade_date,
            open=_field_value(row, columns, "open"),
            high=_field_value(row, columns, "high"),
            low=_field_value(row, columns, "low"),
            close=_field_value(row, columns, "close"),
            adjusted_close=_field_value(row, columns, "adjusted_close"),
            volume=_field_value(row, columns, "volume"),
            dividend=_field_value(row, columns, "dividend"),
            stock_split=_field_value(row, columns, "stock_split"),
        ))
        if "Repaired?" in columns:
            try:
                repaired = row["Repaired?"]
                if repaired == repaired and bool(repaired):
                    warnings.append(f"provider.yfinance_repaired_row:{trade_date}")
            except (TypeError, ValueError):
                pass
    return ProviderSeries(
        internal_ticker=internal_ticker,
        provider_symbol=provider_symbol,
        status="ok",
        rows=tuple(rows),
        warnings=tuple(warnings),
    )


class YFinanceProvider:
    """Concrete :class:`~engine.valuation.ingestion.eod.providers.base.EndOfDayMarketProvider`.
    Every requested ticker is fetched with its own independent
    ``yf.Ticker(...).history(...)`` call -- one symbol's provider
    exception (network, rate limit, unknown symbol) becomes that symbol's
    own ``ProviderSeries(status="failed")`` and never aborts or corrupts
    the fetch of any other requested symbol."""

    def fetch(self, requests: Sequence[EndOfDayFetchRequest]) -> Sequence[ProviderSeries]:
        yfinance = import_yfinance()
        results: list[ProviderSeries] = []
        for request in requests:
            try:
                ticker = yfinance.Ticker(request.provider_symbol)
                dataframe = ticker.history(
                    start=request.start_date_inclusive,
                    end=request.end_date_exclusive,
                    interval=request.interval,
                    auto_adjust=request.auto_adjust,
                    back_adjust=False,
                    actions=request.actions,
                    repair=request.repair,
                    keepna=request.keepna,
                    rounding=request.rounding,
                    prepost=request.prepost,
                    timeout=request.timeout,
                )
            except Exception as exc:  # noqa: BLE001 - isolated per-symbol, never propagated
                results.append(ProviderSeries(
                    internal_ticker=request.internal_ticker, provider_symbol=request.provider_symbol,
                    status="failed", error_reason=f"{type(exc).__name__}: {exc}",
                ))
                continue
            try:
                results.append(dataframe_to_provider_series(
                    dataframe, internal_ticker=request.internal_ticker, provider_symbol=request.provider_symbol,
                ))
            except Exception as exc:  # noqa: BLE001 - conversion failure isolated the same way
                results.append(ProviderSeries(
                    internal_ticker=request.internal_ticker, provider_symbol=request.provider_symbol,
                    status="failed", error_reason=f"provider response conversion failed: {type(exc).__name__}: {exc}",
                ))
        return results
