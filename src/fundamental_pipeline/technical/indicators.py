"""Pure technical indicator computation module.

All indicator functions are pure, deterministic functions taking a sequence of DailyBar
records and optional parameter windows/dates. No disk or network I/O is performed here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from .models import (
    DailyBar,
    decimal_envelope_available,
    decimal_envelope_unavailable,
    string_envelope_available,
    string_envelope_unavailable,
)


def _check_discontinuity(
    start_date: str,
    end_date: str,
    corporate_action_dates: set[str] | None,
) -> bool:
    """Return True if any corporate action effective_date falls within [start_date, end_date]."""
    if not corporate_action_dates:
        return False
    return any(start_date <= ca_date <= end_date for ca_date in corporate_action_dates)


def compute_sma(
    bars: Sequence[DailyBar],
    period: int,
    as_of_date: str,
    corporate_action_dates: set[str] | None = None,
) -> dict:
    """Compute Simple Moving Average of adjusted_close over trailing `period` trading days."""
    valid_bars = [b for b in bars if b.trade_date <= as_of_date and b.adjusted_close is not None]
    if len(valid_bars) < period:
        return decimal_envelope_unavailable("technical.insufficient_price_history")

    trailing = valid_bars[-period:]
    start_date = trailing[0].trade_date
    end_date = trailing[-1].trade_date

    if _check_discontinuity(start_date, end_date, corporate_action_dates):
        return decimal_envelope_unavailable("technical.corporate_action_discontinuity_in_window")

    total = sum(b.adjusted_close for b in trailing if b.adjusted_close is not None)
    sma = total / Decimal(period)
    return decimal_envelope_available(sma)


def compute_price_vs_sma(
    latest_adj_close: Decimal | None,
    sma_envelope: dict,
) -> dict:
    """Compare latest adjusted_close to an SMA indicator envelope ("above" / "below" / "at")."""
    if latest_adj_close is None or sma_envelope.get("status") != "available":
        code = (
            sma_envelope.get("reason_codes", [{}])[0].get("code")
            if sma_envelope.get("reason_codes")
            else "technical.indicator_dependency_unavailable"
        )
        return string_envelope_unavailable(code)

    sma_val = Decimal(sma_envelope["value"])
    if latest_adj_close > sma_val:
        res = "above"
    elif latest_adj_close < sma_val:
        res = "below"
    else:
        res = "at"
    return string_envelope_available(res)


def compute_sma_50_vs_sma_200(
    sma_50_envelope: dict,
    sma_200_envelope: dict,
) -> dict:
    """Compare SMA_50 to SMA_200 ("above" / "below" / "at") for cross-over detection."""
    if sma_50_envelope.get("status") != "available" or sma_200_envelope.get("status") != "available":
        return string_envelope_unavailable("technical.indicator_dependency_unavailable")

    v50 = Decimal(sma_50_envelope["value"])
    v200 = Decimal(sma_200_envelope["value"])
    if v50 > v200:
        res = "above"
    elif v50 < v200:
        res = "below"
    else:
        res = "at"
    return string_envelope_available(res)


def compute_rsi_14(
    bars: Sequence[DailyBar],
    as_of_date: str,
    corporate_action_dates: set[str] | None = None,
) -> dict:
    """Compute 14-period RSI using Wilder's original exponential smoothing method.

    First average gain/loss is calculated over the first 14 daily changes (15 price points).
    Subsequent days use Wilder's recursive formula:
        avg_gain = (prev_avg_gain * 13 + current_gain) / 14
        avg_loss = (prev_avg_loss * 13 + current_loss) / 14
    If avg_loss is zero, RSI is 100.
    """
    valid_bars = [b for b in bars if b.trade_date <= as_of_date and b.adjusted_close is not None]
    if len(valid_bars) < 15:
        return decimal_envelope_unavailable("technical.insufficient_price_history")

    # Restrict RSI calculation to trailing max 250 bars to stay within recent continuous series
    valid_bars = valid_bars[-250:]

    start_date = valid_bars[0].trade_date
    end_date = valid_bars[-1].trade_date
    if _check_discontinuity(start_date, end_date, corporate_action_dates):
        return decimal_envelope_unavailable("technical.corporate_action_discontinuity_in_window")

    diffs: list[Decimal] = []
    for i in range(1, len(valid_bars)):
        prev_p = valid_bars[i - 1].adjusted_close
        curr_p = valid_bars[i].adjusted_close
        if prev_p is not None and curr_p is not None:
            diffs.append(curr_p - prev_p)

    if len(diffs) < 14:
        return decimal_envelope_unavailable("technical.insufficient_price_history")

    initial_gains = [max(d, Decimal("0")) for d in diffs[:14]]
    initial_losses = [max(-d, Decimal("0")) for d in diffs[:14]]

    avg_gain = sum(initial_gains) / Decimal("14")
    avg_loss = sum(initial_losses) / Decimal("14")

    for i in range(14, len(diffs)):
        change = diffs[i]
        gain = max(change, Decimal("0"))
        loss = max(-change, Decimal("0"))
        avg_gain = (avg_gain * Decimal("13") + gain) / Decimal("14")
        avg_loss = (avg_loss * Decimal("13") + loss) / Decimal("14")

    if avg_loss == Decimal("0"):
        rsi = Decimal("100")
    else:
        rs = avg_gain / avg_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

    return decimal_envelope_available(rsi)


def compute_avg_volume(
    bars: Sequence[DailyBar],
    period: int,
    as_of_date: str,
) -> dict:
    """Compute simple mean daily trading volume over trailing `period` trading days."""
    valid_bars = [b for b in bars if b.trade_date <= as_of_date and b.volume is not None]
    if len(valid_bars) < period:
        return decimal_envelope_unavailable("technical.insufficient_price_history")

    trailing = valid_bars[-period:]
    total = sum(b.volume for b in trailing if b.volume is not None)
    avg_vol = total / Decimal(period)
    return decimal_envelope_available(avg_vol)


def compute_volume_trend(
    avg_vol_20d_envelope: dict,
    avg_vol_60d_envelope: dict,
    threshold: Decimal = Decimal("0.10"),
) -> dict:
    """Derive volume trend ("artıyor" / "azalıyor" / "yatay") by comparing 20d vs 60d average volume.

    Threshold concept:
    A relative difference of > 10% (threshold = 0.10) between short-term (20-day) and
    medium-term (60-day) average volume is required to classify the volume trend as
    increasing ("artıyor") or decreasing ("azalıyor"). Within the [-10%, +10%] band,
    the trend is classified as flat ("yatay").
    """
    if avg_vol_20d_envelope.get("status") != "available" or avg_vol_60d_envelope.get("status") != "available":
        return string_envelope_unavailable("technical.indicator_dependency_unavailable")

    vol20 = Decimal(avg_vol_20d_envelope["value"])
    vol60 = Decimal(avg_vol_60d_envelope["value"])

    if vol60 == Decimal("0"):
        return string_envelope_unavailable("technical.calculation_blocked")

    diff_pct = (vol20 - vol60) / vol60

    if diff_pct > threshold:
        res = "artıyor"
    elif diff_pct < -threshold:
        res = "azalıyor"
    else:
        res = "yatay"

    return string_envelope_available(res)


def compute_support_resistance(
    bars: Sequence[DailyBar],
    period: int,
    as_of_date: str,
    corporate_action_dates: set[str] | None = None,
) -> tuple[dict, dict]:
    """Compute mechanical support (min low) and resistance (max high) over trailing `period` trading days."""
    valid_bars = [
        b for b in bars
        if b.trade_date <= as_of_date and b.high is not None and b.low is not None
    ]
    if len(valid_bars) < period:
        insuf = decimal_envelope_unavailable("technical.insufficient_price_history")
        return insuf, insuf

    trailing = valid_bars[-period:]
    start_date = trailing[0].trade_date
    end_date = trailing[-1].trade_date

    if _check_discontinuity(start_date, end_date, corporate_action_dates):
        discont = decimal_envelope_unavailable("technical.corporate_action_discontinuity_in_window")
        return discont, discont

    max_high = max(b.high for b in trailing if b.high is not None)
    min_low = min(b.low for b in trailing if b.low is not None)

    return decimal_envelope_available(min_low), decimal_envelope_available(max_high)


def compute_all_indicators(
    bars: Sequence[DailyBar],
    ticker: str,
    as_of_date: str,
    corporate_action_dates: set[str] | None = None,
) -> dict:
    """Compute all 11 technical indicators for the ticker as of `as_of_date`."""
    sorted_bars = sorted(bars, key=lambda b: b.trade_date)
    valid_as_of_bars = [b for b in sorted_bars if b.trade_date <= as_of_date]

    latest_bar = valid_as_of_bars[-1] if valid_as_of_bars else None
    latest_adj_close = latest_bar.adjusted_close if latest_bar else None

    sma_50 = compute_sma(sorted_bars, 50, as_of_date, corporate_action_dates)
    sma_200 = compute_sma(sorted_bars, 200, as_of_date, corporate_action_dates)

    price_vs_sma_50 = compute_price_vs_sma(latest_adj_close, sma_50)
    price_vs_sma_200 = compute_price_vs_sma(latest_adj_close, sma_200)
    sma_50_vs_sma_200 = compute_sma_50_vs_sma_200(sma_50, sma_200)

    rsi_14 = compute_rsi_14(sorted_bars, as_of_date, corporate_action_dates)

    avg_vol_20d = compute_avg_volume(sorted_bars, 20, as_of_date)
    avg_vol_60d = compute_avg_volume(sorted_bars, 60, as_of_date)
    volume_trend = compute_volume_trend(avg_vol_20d, avg_vol_60d)

    support_63d, resistance_63d = compute_support_resistance(sorted_bars, 63, as_of_date, corporate_action_dates)

    return {
        "sma_50": sma_50,
        "sma_200": sma_200,
        "price_vs_sma_50": price_vs_sma_50,
        "price_vs_sma_200": price_vs_sma_200,
        "sma_50_vs_sma_200": sma_50_vs_sma_200,
        "rsi_14": rsi_14,
        "avg_volume_20d": avg_vol_20d,
        "avg_volume_60d": avg_vol_60d,
        "volume_trend": volume_trend,
        "support_63d": support_63d,
        "resistance_63d": resistance_63d,
    }
