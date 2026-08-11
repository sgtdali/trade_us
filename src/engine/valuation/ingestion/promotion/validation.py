"""Pure eligibility checks and deterministic row selection for the
EOD-close promotion bridge.

Every function here is pure: no file I/O, no process clock, no ticker
literal, and no network. Findings reuse the shared, unchanged
:class:`~engine.valuation.validation.findings.Finding`
contract -- the same type the sibling EOD ingestion namespace and T70
market resolver already use.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from ...market.registry import check_manifest_authorization
from ...validation.findings import Finding
from .models import SelectedRow


def check_bundle_domain_eligibility(bundle_manifest: Mapping[str, Any], *, ticker: str) -> list[Finding]:
    """Domain-level (not structural -- structural integrity is proven by
    the caller via ``ingestion.eod.service.validate_bundle``/
    ``replay_bundle`` before this is ever called) checks on the source
    ingestion bundle's own recorded outcome."""
    findings: list[Finding] = []
    requested = bundle_manifest.get("requested_internal_tickers") or []
    if ticker not in requested:
        findings.append(Finding(
            rule_id="PROMO-BUNDLE-001", severity="blocker", scope="bundle",
            reason_code="identity.ticker_not_requested",
            message=f"ticker {ticker!r} was not among the bundle's requested_internal_tickers {requested!r}",
        ))
    if bundle_manifest.get("overall_status") != "valid":
        findings.append(Finding(
            rule_id="PROMO-BUNDLE-002", severity="blocker", scope="bundle",
            reason_code="identity.overall_status_invalid",
            message=f"source ingestion bundle overall_status is {bundle_manifest.get('overall_status')!r}, not 'valid'",
        ))
    return findings


def check_provider_manifest_compatibility(provider_extract: Mapping[str, Any], manifest: Mapping[str, Any]) -> list[Finding]:
    """Exact-compatibility checks between the source provider-extract and
    the target market-source-manifest. The manifest must name the same
    fixed provider the bundle was actually fetched from."""
    findings: list[Finding] = []
    provider = provider_extract.get("provider") or {}
    authority = manifest.get("source_authority") or {}

    if provider.get("provider_id") != authority.get("provider_id"):
        findings.append(Finding(
            rule_id="PROMO-PROV-001", severity="blocker", scope="bundle",
            reason_code="identity.provider_id_mismatch",
            message=(
                f"provider-extract provider_id {provider.get('provider_id')!r} does not match "
                f"manifest source_authority.provider_id {authority.get('provider_id')!r}"
            ),
        ))

    return findings


def check_manifest_authorization_findings(manifest: Mapping[str, Any], *, ticker: str, as_of_date: str) -> list[Finding]:
    """Wrap :func:`engine.valuation.market.registry.check_manifest_authorization`
    (lifecycle/scope/effective-window/temporary-use-exception) as findings."""
    problems = check_manifest_authorization(dict(manifest), ticker=ticker, as_of_date=as_of_date)
    return [
        Finding(
            rule_id="PROMO-AUTH-001", severity="blocker", scope="bundle",
            reason_code="authorization.manifest_rejected",
            message=problem,
        )
        for problem in problems
    ]


def check_temporal_bounds(*, retrieved_at: str, cutoff_instant: str, effective_at: str) -> list[Finding]:
    """``retrieved_at`` (the ``published_at``/``available_at`` proxy) and
    ``effective_at`` must both be known no later than the cutoff -- T70's
    own cutoff-eligibility rule, enforced here before an ineligible
    observation is even built."""
    findings: list[Finding] = []
    if retrieved_at > cutoff_instant:
        findings.append(Finding(
            rule_id="PROMO-TIME-001", severity="blocker", scope="bundle",
            reason_code="temporal.retrieval_after_cutoff",
            message=f"provider-extract retrieved_at {retrieved_at!r} is after cutoff_instant {cutoff_instant!r}",
        ))
    if effective_at > cutoff_instant:
        findings.append(Finding(
            rule_id="PROMO-TIME-002", severity="blocker", scope="bundle",
            reason_code="temporal.effective_at_after_cutoff",
            message=f"--effective-at {effective_at!r} is after cutoff_instant {cutoff_instant!r}",
        ))
    return findings


def check_effective_at_matches_trade_date(*, effective_at: str, trade_date: str) -> list[Finding]:
    if effective_at[:10] != trade_date:
        return [Finding(
            rule_id="PROMO-TIME-003", severity="blocker", scope="bundle",
            reason_code="temporal.effective_at_trade_date_mismatch",
            message=(
                f"--effective-at {effective_at!r} date does not match the selected trade_date {trade_date!r}"
            ),
        )]
    return []


def select_eligible_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    internal_ticker: str,
    provider_symbol: str,
    currency: str,
    as_of_date: str,
    start_date_inclusive: str,
    end_date_exclusive: str,
) -> list[Mapping[str, Any]]:
    """Filter normalized ``eod-price-series`` rows down to the ones that
    are structurally eligible for promotion (T70's own row-selection
    contract, Section 7.5). Never uses ``adjusted_close``/``open``/
    ``high``/``low``. Never treats missing as zero."""
    eligible: list[Mapping[str, Any]] = []
    for row in rows:
        if row.get("internal_ticker") != internal_ticker:
            continue
        if row.get("provider_symbol") != provider_symbol:
            continue
        if row.get("currency") != currency:
            continue
        if row.get("row_status") != "valid":
            continue
        if row.get("quarantine_reason_codes"):
            continue
        close = row.get("close") or {}
        if close.get("status") != "available":
            continue
        raw_value = close.get("value")
        try:
            value = Decimal(raw_value)
        except (InvalidOperation, TypeError):
            continue
        if value <= 0:
            continue
        trade_date = row.get("trade_date")
        if not trade_date or trade_date > as_of_date:
            continue
        if not (start_date_inclusive <= trade_date < end_date_exclusive):
            continue
        eligible.append(row)
    return eligible


def select_row(
    eligible_rows: Sequence[Mapping[str, Any]],
    *,
    as_of_date: str,
    max_fallback_lag_days: int,
) -> tuple[SelectedRow | None, list[Finding]]:
    """Deterministically select the latest eligible trade date on or
    before ``as_of_date``, subject to the policy's explicit maximum
    fallback lag. No averaging, no hidden unlimited fallback, no future
    row. Returns ``(None, findings)`` when nothing is selectable."""
    if not eligible_rows:
        return None, [Finding(
            rule_id="PROMO-ROW-001", severity="blocker", scope="bundle",
            reason_code="selection.no_eligible_row",
            message="no eligible valid, non-quarantined, positive-close row was found for this ticker/date range",
        )]

    latest_trade_date = max(row["trade_date"] for row in eligible_rows)
    candidates = [row for row in eligible_rows if row["trade_date"] == latest_trade_date]
    if len(candidates) > 1:
        return None, [Finding(
            rule_id="PROMO-ROW-003", severity="blocker", scope="bundle",
            reason_code="identity.duplicate_eligible_row",
            message=f"more than one eligible row shares trade_date {latest_trade_date!r}",
        )]

    from datetime import date
    lag_days = (date.fromisoformat(as_of_date) - date.fromisoformat(latest_trade_date)).days
    if lag_days > max_fallback_lag_days:
        return None, [Finding(
            rule_id="PROMO-ROW-002", severity="blocker", scope="bundle",
            reason_code="selection.lag_exceeded",
            message=(
                f"latest eligible trade_date {latest_trade_date!r} is {lag_days} day(s) before as_of_date "
                f"{as_of_date!r}, exceeding the policy's max_fallback_lag_days={max_fallback_lag_days}"
            ),
        )]

    row = candidates[0]
    selected = SelectedRow(
        internal_ticker=row["internal_ticker"],
        provider_id=row["source_row_reference"]["provider_id"],
        provider_symbol=row["provider_symbol"],
        trade_date=row["trade_date"],
        currency=row["currency"],
        close_value=row["close"]["value"],
        interval=row["source_row_reference"]["interval"],
    )
    return selected, []
