"""Orchestrates technical snapshot generation, fetching daily price history,
checking corporate action ledgers, computing indicators, and validating/saving artifacts.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from ..io import write_json_atomic
from ..paths import repo_path
from ..valuation.ingestion.eod.models import EndOfDayFetchRequest
from ..valuation.ingestion.eod.providers.yfinance_provider import YFinanceProvider
from ..valuation.safe_json import read_safe_json
from ..valuation.validation.findings import Finding, has_blocking
from .indicators import compute_all_indicators
from .models import DailyBar
from .validation import validate_technical_snapshot


def _get_provider_symbol(ticker: str, root: Path) -> str:
    """Look up provider symbol from config/market-data/providers/yfinance.json, defaulting to {ticker}.IS."""
    mapping_path = root / "config" / "market-data" / "providers" / "yfinance.json"
    if mapping_path.exists():
        try:
            doc = read_safe_json(mapping_path)
            for m in doc.get("ticker_mappings", []):
                if m.get("internal_ticker") == ticker:
                    return m.get("provider_symbol", f"{ticker}.IS")
        except Exception:  # noqa: BLE001
            pass
    return f"{ticker}.IS"


def get_corporate_action_dates(ticker: str, root: Path) -> set[str]:
    """Extract corporate action effective dates from ticker's share-count-ledger.json if present."""
    ledger_path = root / "data" / "market-input-ledgers" / ticker / "share-count-ledger.json"
    if not ledger_path.exists():
        return set()

    dates: set[str] = set()
    try:
        ledger = read_safe_json(ledger_path)
        for ca in ledger.get("corporate_actions", []):
            eff_date = ca.get("effective_date")
            if eff_date:
                dates.add(eff_date)
    except Exception:  # noqa: BLE001
        pass
    return dates


def fetch_daily_bars(
    ticker: str,
    as_of_date: str,
    root: Path,
    lookback_days: int = 400,
    timeout: int = 30,
) -> tuple[list[DailyBar], str, str]:
    """Fetch trailing daily price history using the existing YFinanceProvider."""
    as_of_dt = datetime.date.fromisoformat(as_of_date)
    start_dt = as_of_dt - datetime.timedelta(days=lookback_days)
    end_dt = as_of_dt + datetime.timedelta(days=1)

    start_str = start_dt.isoformat()
    end_str = end_dt.isoformat()
    provider_symbol = _get_provider_symbol(ticker, root)

    req = EndOfDayFetchRequest(
        internal_ticker=ticker,
        provider_symbol=provider_symbol,
        start_date_inclusive=start_str,
        end_date_exclusive=end_str,
        timeout=timeout,
    )

    provider = YFinanceProvider()
    series_list = provider.fetch([req])
    if not series_list or series_list[0].status != "ok":
        reason = series_list[0].error_reason if series_list else "no data returned"
        raise RuntimeError(f"YFinanceProvider fetch failed for {ticker}: {reason}")

    daily_bars: list[DailyBar] = []
    for row in series_list[0].rows:
        daily_bars.append(
            DailyBar(
                trade_date=row.trade_date,
                open=row.open.decimal_value,
                high=row.high.decimal_value,
                low=row.low.decimal_value,
                close=row.close.decimal_value,
                adjusted_close=row.adjusted_close.decimal_value,
                volume=row.volume.decimal_value,
            )
        )

    return daily_bars, start_str, provider_symbol


def generate_technical_snapshot(
    ticker: str,
    as_of_date: str,
    generated_at: str,
    engine_version: str,
    output_dir: Path,
    *,
    check: bool = False,
    root: Path | None = None,
    lookback_days: int = 400,
    daily_bars_override: list[DailyBar] | None = None,
    provider_symbol_override: str | None = None,
    corporate_action_dates_override: set[str] | None = None,
) -> tuple[dict[str, Any], list[Finding]]:
    """Generate and validate a technical_snapshot artifact."""
    if root is None:
        root = repo_path()

    if daily_bars_override is None:
        daily_bars, start_date_str, provider_symbol = fetch_daily_bars(
            ticker=ticker,
            as_of_date=as_of_date,
            root=root,
            lookback_days=lookback_days,
        )
    else:
        daily_bars = daily_bars_override
        if not daily_bars:
            raise RuntimeError(f"point-in-time technical bars are empty for {ticker}")
        start_date_str = min(bar.trade_date for bar in daily_bars)
        provider_symbol = provider_symbol_override or ticker

    ca_dates = (
        corporate_action_dates_override
        if corporate_action_dates_override is not None
        else get_corporate_action_dates(ticker, root)
    )
    indicators = compute_all_indicators(daily_bars, ticker, as_of_date, ca_dates)

    valid_as_of_bars = [b for b in daily_bars if b.trade_date <= as_of_date]

    artifact = {
        "schema_version": "1.0.0",
        "artifact_type": "technical_snapshot",
        "artifact_id": f"technical-snapshot:{ticker}:{as_of_date}",
        "owner_type": "generated",
        "ticker": ticker,
        "as_of_date": as_of_date,
        "generated_at": generated_at,
        "engine_version": engine_version,
        "indicators": indicators,
        "provenance": {
            "price_series_length": len(valid_as_of_bars),
            "lookback_start_date": start_date_str,
            "lookback_end_date": as_of_date,
            "price_field_used": "adjusted_close",
            "yfinance_ticker": provider_symbol,
        },
    }

    rel_path = f"data/technical/{ticker}/{as_of_date}.json"
    findings = validate_technical_snapshot(artifact, relative_path=rel_path)

    if not check and not has_blocking(findings):
        target_file = output_dir / ticker / f"{as_of_date}.json"
        write_json_atomic(target_file, artifact)

    return artifact, findings
