"""Quarantine/quality validation for normalized FX rows, and request/
mapping-level findings.

Structurally parallel to ``ingestion.eod.validation`` -- same
:class:`~engine.valuation.validation.findings.Finding`
contract, same deterministic :func:`sort_findings`. FX rows have no
dividend/stock_split/volume economic meaning, so this module omits the
EOD sibling's corresponding quality checks; OHLC-integrity and close-
positivity checks still apply (an FX daily bar is still an OHLC bar).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from ...validation.findings import Finding
from ..eod.models import ProviderConfig

#: A same-pair single trading-day unadjusted-close move at or beyond this
#: multiple is flagged as a diagnostic-only suspicious-change finding, never
#: auto-repaired and never blocking.
EXTREME_DAY_OVER_DAY_RATIO = Decimal("3")


def validate_fx_request_and_mapping(
    provider_config: ProviderConfig, requested_pairs: Sequence[str],
) -> list[Finding]:
    """Validate the requested FX pair list against the provider's FX pair
    mapping table before any fetch is attempted. Duplicate requests and
    unknown/inactive mappings are all blocking -- a partial, silently
    reduced pair set is never fetched in place of the caller's actual
    request."""
    findings: list[Finding] = []
    seen: set[str] = set()
    for pair_id in requested_pairs:
        if pair_id in seen:
            findings.append(Finding(
                rule_id="FXING-MAP-002", severity="blocker", scope="bundle",
                reason_code="mapping.duplicate_requested_pair",
                message=f"pair {pair_id!r} was requested more than once",
            ))
        seen.add(pair_id)

        mapping = provider_config.fx_mapping(pair_id)
        if mapping is None:
            findings.append(Finding(
                rule_id="FXING-MAP-001", severity="blocker", scope="bundle",
                reason_code="mapping.unknown_pair",
                message=f"no FX provider mapping is configured for pair {pair_id!r}",
            ))
        elif not mapping.active:
            findings.append(Finding(
                rule_id="FXING-MAP-003", severity="blocker", scope="bundle",
                reason_code="mapping.inactive_pair",
                message=f"FX provider mapping for {pair_id!r} is not active",
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


def validate_and_quarantine_fx_rows(
    rows: list[dict],
    *,
    start_date_inclusive: str,
    end_date_exclusive: str,
) -> tuple[list[dict], list[Finding]]:
    """Classify every normalized FX row as ``valid``/``quarantined`` and
    return ``(rows, findings)``. ``rows`` must already be sorted by
    ``(pair_id, trade_date)`` (``normalize.build_normalized_fx_rows``'s
    contract). Mutates and returns the same row dicts (already private,
    freshly built copies -- never the caller's own committed data)."""
    findings: list[Finding] = []

    seen_keys: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["pair_id"], row["trade_date"])
        seen_keys[key] = seen_keys.get(key, 0) + 1
    duplicate_keys = {k for k, count in seen_keys.items() if count > 1}

    for row in rows:
        key = (row["pair_id"], row["trade_date"])
        if key in duplicate_keys:
            _quarantine(row, reason_code="identity.duplicate_row")
            findings.append(Finding(
                rule_id="FXING-ROW-001", severity="error", scope="field",
                reason_code="identity.duplicate_row",
                message=f"duplicate row for pair {key[0]!r} trade_date {key[1]!r}",
                artifact_id=key[0],
            ))
        if not (start_date_inclusive <= row["trade_date"] < end_date_exclusive):
            _quarantine(row, reason_code="identity.row_outside_requested_range")
            findings.append(Finding(
                rule_id="FXING-ROW-002", severity="error", scope="field",
                reason_code="identity.row_outside_requested_range",
                message=f"row trade_date {row['trade_date']!r} is outside the requested "
                        f"[{start_date_inclusive}, {end_date_exclusive}) range",
                artifact_id=row["pair_id"],
            ))

        close = _decimal_or_none(row["close"])
        if close is None:
            _quarantine(row, reason_code="quality.close_missing")
            findings.append(Finding(
                rule_id="FXING-QUAL-001", severity="warning", scope="field",
                reason_code="quality.close_missing",
                message=f"row {row['pair_id']}/{row['trade_date']} has no close value and cannot be used as an FX close",
            ))
            continue  # remaining OHLC-integrity checks all depend on close

        if close <= 0:
            _quarantine(row, reason_code="quality.non_positive_close")
            findings.append(Finding(
                rule_id="FXING-QUAL-002", severity="error", scope="field",
                reason_code="quality.non_positive_close",
                message=f"row {row['pair_id']}/{row['trade_date']}: close must be strictly positive",
            ))

        open_ = _decimal_or_none(row["open"])
        high = _decimal_or_none(row["high"])
        low = _decimal_or_none(row["low"])

        if high is not None and low is not None and high < low:
            _quarantine(row, reason_code="quality.invalid_ohlc_high_low")
            findings.append(Finding(rule_id="FXING-QUAL-003", severity="error", scope="field", reason_code="quality.invalid_ohlc_high_low", message=f"row {row['pair_id']}/{row['trade_date']}: high < low"))
        if high is not None and open_ is not None and high < open_:
            _quarantine(row, reason_code="quality.invalid_ohlc_high_open")
            findings.append(Finding(rule_id="FXING-QUAL-004", severity="error", scope="field", reason_code="quality.invalid_ohlc_high_open", message=f"row {row['pair_id']}/{row['trade_date']}: high < open"))
        if high is not None and high < close:
            _quarantine(row, reason_code="quality.invalid_ohlc_high_close")
            findings.append(Finding(rule_id="FXING-QUAL-005", severity="error", scope="field", reason_code="quality.invalid_ohlc_high_close", message=f"row {row['pair_id']}/{row['trade_date']}: high < close"))
        if low is not None and open_ is not None and low > open_:
            _quarantine(row, reason_code="quality.invalid_ohlc_low_open")
            findings.append(Finding(rule_id="FXING-QUAL-006", severity="error", scope="field", reason_code="quality.invalid_ohlc_low_open", message=f"row {row['pair_id']}/{row['trade_date']}: low > open"))
        if low is not None and low > close:
            _quarantine(row, reason_code="quality.invalid_ohlc_low_close")
            findings.append(Finding(rule_id="FXING-QUAL-007", severity="error", scope="field", reason_code="quality.invalid_ohlc_low_close", message=f"row {row['pair_id']}/{row['trade_date']}: low > close"))

        adjusted_close = _decimal_or_none(row["adjusted_close"])
        if adjusted_close is not None and adjusted_close <= 0:
            _quarantine(row, reason_code="quality.non_positive_adjusted_close")
            findings.append(Finding(rule_id="FXING-QUAL-008", severity="error", scope="field", reason_code="quality.non_positive_adjusted_close", message=f"row {row['pair_id']}/{row['trade_date']}: adjusted_close must be strictly positive"))

    findings.extend(_suspicious_change_diagnostics(rows))
    return rows, findings


def _suspicious_change_diagnostics(rows: Sequence[dict]) -> list[Finding]:
    """Diagnostic-only (``warning`` severity), never auto-repaired, never
    blocking: extreme day-over-day unadjusted-close ratio. Rows must
    already be sorted by ``(pair_id, trade_date)``."""
    findings: list[Finding] = []
    previous_close: dict[str, Decimal] = {}
    for row in rows:
        pair_id = row["pair_id"]
        close = _decimal_or_none(row["close"])

        if close is not None and close > 0:
            prior = previous_close.get(pair_id)
            if prior is not None and prior > 0:
                ratio = close / prior if close >= prior else prior / close
                if ratio >= EXTREME_DAY_OVER_DAY_RATIO:
                    findings.append(Finding(
                        rule_id="FXING-DIAG-001", severity="warning", scope="field",
                        reason_code="quality.extreme_day_over_day_close_ratio",
                        message=f"row {pair_id}/{row['trade_date']}: unadjusted close moved by a factor of "
                                f"{ratio} vs. the prior available close -- diagnostic only, not auto-repaired",
                    ))
            previous_close[pair_id] = close

    return findings
