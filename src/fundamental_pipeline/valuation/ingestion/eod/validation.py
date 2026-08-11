"""Quarantine/quality validation for normalized EOD rows, and request/
mapping-level findings.

Every finding is a :class:`~fundamental_pipeline.valuation.validation.findings.Finding`
(reused unchanged from the T70 validation namespace -- same
rule_id/severity/scope/reason_code/message shape, same deterministic
:func:`sort_findings`). Reason codes are stable, dotted, machine-readable
identifiers; they are quarantine/diagnostic rules, never investment
signals.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from ...validation.findings import Finding
from .models import ProviderConfig, ProviderSeries

#: A same-ticker single trading-day unadjusted-close move at or beyond this
#: multiple is flagged as a diagnostic-only suspicious-change finding, never
#: auto-repaired and never blocking.
EXTREME_DAY_OVER_DAY_RATIO = Decimal("3")

#: |adjusted_close / close - 1| beyond this fraction is flagged as a
#: diagnostic-only suspicious adjusted/unadjusted divergence.
EXTREME_ADJUSTMENT_DIVERGENCE = Decimal("0.5")


def validate_request_and_mapping(
    provider_config: ProviderConfig, requested_tickers: Sequence[str],
) -> list[Finding]:
    """Validate the requested ticker list against the provider's ticker
    mapping table before any fetch is attempted. Duplicate requests and
    unknown/inactive mappings are all blocking -- a partial, silently
    reduced ticker set is never fetched in place of the caller's actual
    request."""
    findings: list[Finding] = []
    seen: set[str] = set()
    for ticker in requested_tickers:
        if ticker in seen:
            findings.append(Finding(
                rule_id="ING-MAP-002", severity="blocker", scope="bundle",
                reason_code="mapping.duplicate_requested_ticker",
                message=f"ticker {ticker!r} was requested more than once",
            ))
        seen.add(ticker)

        mapping = provider_config.mapping(ticker)
        if mapping is None:
            findings.append(Finding(
                rule_id="ING-MAP-001", severity="blocker", scope="bundle",
                reason_code="mapping.unknown_ticker",
                message=f"no provider mapping is configured for internal ticker {ticker!r}",
            ))
        elif not mapping.active:
            findings.append(Finding(
                rule_id="ING-MAP-003", severity="blocker", scope="bundle",
                reason_code="mapping.inactive_ticker",
                message=f"provider mapping for {ticker!r} is not active",
            ))
    return findings


def _decimal_or_none(field: Mapping) -> Decimal | None:
    if field.get("status") != "available":
        return None
    return Decimal(field["value"])


def _quarantine(row: dict, *, reason_code: str) -> None:
    row["row_status"] = "quarantined"
    if reason_code not in row["quarantine_reason_codes"]:
        row["quarantine_reason_codes"].append(reason_code)


def validate_and_quarantine(
    rows: list[dict],
    *,
    start_date_inclusive: str,
    end_date_exclusive: str,
) -> tuple[list[dict], list[Finding]]:
    """Classify every normalized row as ``valid``/``quarantined`` and
    return ``(rows, findings)``. ``rows`` must already be sorted by
    ``(internal_ticker, trade_date)`` (``normalize.build_normalized_rows``'s
    contract). Mutates and returns the same row dicts (already private,
    freshly built copies -- never the caller's own committed data)."""
    findings: list[Finding] = []

    seen_keys: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["internal_ticker"], row["trade_date"])
        seen_keys[key] = seen_keys.get(key, 0) + 1
    duplicate_keys = {k for k, count in seen_keys.items() if count > 1}

    for row in rows:
        key = (row["internal_ticker"], row["trade_date"])
        if key in duplicate_keys:
            _quarantine(row, reason_code="identity.duplicate_row")
            findings.append(Finding(
                rule_id="ING-ROW-001", severity="error", scope="field",
                reason_code="identity.duplicate_row",
                message=f"duplicate row for ticker {key[0]!r} trade_date {key[1]!r}",
                artifact_id=key[0],
            ))
        if not (start_date_inclusive <= row["trade_date"] < end_date_exclusive):
            _quarantine(row, reason_code="identity.row_outside_requested_range")
            findings.append(Finding(
                rule_id="ING-ROW-002", severity="error", scope="field",
                reason_code="identity.row_outside_requested_range",
                message=f"row trade_date {row['trade_date']!r} is outside the requested "
                        f"[{start_date_inclusive}, {end_date_exclusive}) range",
                artifact_id=row["internal_ticker"],
            ))

        close = _decimal_or_none(row["close"])
        if close is None:
            _quarantine(row, reason_code="quality.close_missing")
            findings.append(Finding(
                rule_id="ING-QUAL-001", severity="warning", scope="field",
                reason_code="quality.close_missing",
                message=f"row {row['internal_ticker']}/{row['trade_date']} has no close value and cannot be used as an EOD close",
            ))
            continue  # remaining OHLC-integrity checks all depend on close

        if close <= 0:
            _quarantine(row, reason_code="quality.non_positive_close")
            findings.append(Finding(
                rule_id="ING-QUAL-002", severity="error", scope="field",
                reason_code="quality.non_positive_close",
                message=f"row {row['internal_ticker']}/{row['trade_date']}: close must be strictly positive",
            ))

        open_ = _decimal_or_none(row["open"])
        high = _decimal_or_none(row["high"])
        low = _decimal_or_none(row["low"])

        if high is not None and low is not None and high < low:
            _quarantine(row, reason_code="quality.invalid_ohlc_high_low")
            findings.append(Finding(rule_id="ING-QUAL-003", severity="error", scope="field", reason_code="quality.invalid_ohlc_high_low", message=f"row {row['internal_ticker']}/{row['trade_date']}: high < low"))
        if high is not None and open_ is not None and high < open_:
            _quarantine(row, reason_code="quality.invalid_ohlc_high_open")
            findings.append(Finding(rule_id="ING-QUAL-004", severity="error", scope="field", reason_code="quality.invalid_ohlc_high_open", message=f"row {row['internal_ticker']}/{row['trade_date']}: high < open"))
        if high is not None and high < close:
            _quarantine(row, reason_code="quality.invalid_ohlc_high_close")
            findings.append(Finding(rule_id="ING-QUAL-005", severity="error", scope="field", reason_code="quality.invalid_ohlc_high_close", message=f"row {row['internal_ticker']}/{row['trade_date']}: high < close"))
        if low is not None and open_ is not None and low > open_:
            _quarantine(row, reason_code="quality.invalid_ohlc_low_open")
            findings.append(Finding(rule_id="ING-QUAL-006", severity="error", scope="field", reason_code="quality.invalid_ohlc_low_open", message=f"row {row['internal_ticker']}/{row['trade_date']}: low > open"))
        if low is not None and low > close:
            _quarantine(row, reason_code="quality.invalid_ohlc_low_close")
            findings.append(Finding(rule_id="ING-QUAL-007", severity="error", scope="field", reason_code="quality.invalid_ohlc_low_close", message=f"row {row['internal_ticker']}/{row['trade_date']}: low > close"))

        adjusted_close = _decimal_or_none(row["adjusted_close"])
        if adjusted_close is not None and adjusted_close <= 0:
            _quarantine(row, reason_code="quality.non_positive_adjusted_close")
            findings.append(Finding(rule_id="ING-QUAL-008", severity="error", scope="field", reason_code="quality.non_positive_adjusted_close", message=f"row {row['internal_ticker']}/{row['trade_date']}: adjusted_close must be strictly positive"))

        volume = _decimal_or_none(row["volume"])
        if volume is not None and volume < 0:
            _quarantine(row, reason_code="quality.negative_volume")
            findings.append(Finding(rule_id="ING-QUAL-009", severity="error", scope="field", reason_code="quality.negative_volume", message=f"row {row['internal_ticker']}/{row['trade_date']}: volume must not be negative"))

        dividend = _decimal_or_none(row["dividend"])
        if dividend is not None and dividend < 0:
            _quarantine(row, reason_code="quality.negative_dividend")
            findings.append(Finding(rule_id="ING-QUAL-010", severity="error", scope="field", reason_code="quality.negative_dividend", message=f"row {row['internal_ticker']}/{row['trade_date']}: dividend must not be negative"))

        stock_split = _decimal_or_none(row["stock_split"])
        if stock_split is not None and stock_split < 0:
            _quarantine(row, reason_code="quality.negative_stock_split")
            findings.append(Finding(rule_id="ING-QUAL-011", severity="error", scope="field", reason_code="quality.negative_stock_split", message=f"row {row['internal_ticker']}/{row['trade_date']}: stock_split must not be negative"))

    findings.extend(_suspicious_change_diagnostics(rows))
    return rows, findings


def _suspicious_change_diagnostics(rows: Sequence[dict]) -> list[Finding]:
    """Diagnostic-only (``warning`` severity), never auto-repaired, never
    blocking: extreme day-over-day unadjusted-close ratio and extreme
    adjusted/unadjusted divergence, per docs Section 13 "Suspicious
    changes". Rows must already be sorted by ``(internal_ticker,
    trade_date)``."""
    findings: list[Finding] = []
    previous_close: dict[str, Decimal] = {}
    for row in rows:
        ticker = row["internal_ticker"]
        close = _decimal_or_none(row["close"])
        adjusted_close = _decimal_or_none(row["adjusted_close"])

        if close is not None and close > 0:
            prior = previous_close.get(ticker)
            if prior is not None and prior > 0:
                ratio = close / prior if close >= prior else prior / close
                if ratio >= EXTREME_DAY_OVER_DAY_RATIO:
                    findings.append(Finding(
                        rule_id="ING-DIAG-001", severity="warning", scope="field",
                        reason_code="quality.extreme_day_over_day_close_ratio",
                        message=f"row {ticker}/{row['trade_date']}: unadjusted close moved by a factor of "
                                f"{ratio} vs. the prior available close -- diagnostic only, not auto-repaired",
                    ))
            previous_close[ticker] = close

        if close is not None and close > 0 and adjusted_close is not None:
            divergence = abs(adjusted_close / close - 1)
            if divergence >= EXTREME_ADJUSTMENT_DIVERGENCE:
                findings.append(Finding(
                    rule_id="ING-DIAG-002", severity="warning", scope="field",
                    reason_code="quality.extreme_adjustment_divergence",
                    message=f"row {ticker}/{row['trade_date']}: adjusted_close diverges from close by "
                            f"{divergence:%} -- diagnostic only",
                ))
    return findings


def classify_row_revisions(old_series: Sequence[ProviderSeries], new_series: Sequence[ProviderSeries]) -> dict[str, list[dict]]:
    """Compare two captures' rows keyed on the stable source-row identity
    (``provider_id``, ``provider_symbol``, ``trade_date``, ``interval`` --
    deliberately excluding retrieval time, per docs Section 14) and
    classify each key as ``new``, ``unchanged``, ``changed``, or
    ``missing_from_new_capture``. This is a pure comparison utility for a
    later revision ledger; it performs no I/O and is not itself wired into
    the ``market-ingestion`` CLI in this task."""
    def _index(series_list: Sequence[ProviderSeries]) -> dict[tuple[str, str], dict]:
        index: dict[tuple[str, str], dict] = {}
        for series in series_list:
            if series.status != "ok":
                continue
            for row in series.rows:
                index[(series.provider_symbol, row.trade_date)] = row.to_dict()
        return index

    old_index = _index(old_series)
    new_index = _index(new_series)

    result: dict[str, list[dict]] = {"new": [], "unchanged": [], "changed": [], "missing_from_new_capture": []}
    for key, new_row in sorted(new_index.items()):
        provider_symbol, trade_date = key
        identity = {"provider_id": "yfinance", "provider_symbol": provider_symbol, "trade_date": trade_date, "interval": "1d"}
        if key not in old_index:
            result["new"].append(identity)
        elif old_index[key] == new_row:
            result["unchanged"].append(identity)
        else:
            result["changed"].append(identity)
    for key in sorted(set(old_index) - set(new_index)):
        provider_symbol, trade_date = key
        result["missing_from_new_capture"].append({"provider_id": "yfinance", "provider_symbol": provider_symbol, "trade_date": trade_date, "interval": "1d"})
    return result
