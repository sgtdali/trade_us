"""Pure FX-close promotion engine: given already-loaded/parsed bundle
documents, a market-source manifest, and a promotion policy,
deterministically select one eligible row and build the three promotion
documents in memory.

Structurally parallel to ``ingestion.promotion.policy``. No file I/O, no
process clock, no network, no random ID, and no pair literal anywhere in
this module -- every economically relevant decision comes from the
caller-supplied bundle/manifest/policy data. Byte-identical inputs always
produce byte-identical output.

The promoted observation is ``observation_type="fx"`` with
``fx_mode="market_close"`` (fixed by the policy) and the **unadjusted**
``close`` field only -- never ``adjusted_close``.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from ...canonical import canonical_bytes
from ...validation.findings import Finding, has_blocking, sort_findings
from .models import FxPromotionOutcome, FxPromotionPolicy, SelectedFxRow
from .validation import (
    check_bundle_domain_eligibility,
    check_effective_at_matches_trade_date,
    check_manifest_authorization_findings,
    check_provider_manifest_compatibility,
    check_temporal_bounds,
    select_eligible_rows,
    select_row,
)

_UNIT = "rate"


def _finding_to_dict(finding: Finding) -> dict:
    d: dict[str, Any] = {
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "scope": finding.scope,
        "reason_code": finding.reason_code,
        "message": finding.message,
    }
    if finding.json_pointer:
        d["json_pointer"] = finding.json_pointer
    if finding.related_reference_ids:
        d["related_reference_ids"] = list(finding.related_reference_ids)
    if finding.message_params:
        d["message_params"] = finding.message_params
    return d


def _finding_counts(findings: list[Finding]) -> dict:
    counts = {"blocker": 0, "error": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[finding.severity] += 1
    return counts


def _hash_id(prefix: str, payload: Mapping) -> str:
    digest = hashlib.sha256(canonical_bytes(dict(payload))).hexdigest()
    return f"{prefix}:sha256:{digest}"


def _build_observation(
    selected: SelectedFxRow,
    *,
    policy: FxPromotionPolicy,
    manifest: Mapping[str, Any],
    effective_at: str,
    published_at: str,
    available_at: str,
) -> dict:
    manifest_id = manifest["manifest_id"]

    identity_payload = {
        "provider_id": selected.provider_id,
        "provider_symbol": selected.provider_symbol,
        "trade_date": selected.trade_date,
        "interval": selected.interval,
        "selected_price_field": policy.selected_price_field,
    }
    observation_id = _hash_id("fx-close-promotion-observation", {"manifest_id": manifest_id, **identity_payload})
    revision_id = _hash_id("fx-close-promotion-revision", {**identity_payload, "value": selected.close_value})
    source_record_ref = (
        f"{selected.provider_id}:{selected.provider_symbol}:{selected.trade_date}:"
        f"{selected.interval}:{policy.selected_price_field}"
    )

    return {
        "observation_id": observation_id,
        "observation_type": "fx",
        "instrument_or_pair": selected.pair_id,
        "value": selected.close_value,
        "unit": _UNIT,
        "fx_mode": policy.fx_mode,
        "effective_at": effective_at,
        "published_at": published_at,
        "available_at": available_at,
        "source_manifest_id": manifest_id,
        "source_record_ref": source_record_ref,
        "revision_id": revision_id,
        "revision_status": "original",
    }


def build_fx_promotion(
    *,
    bundle_request_doc: Mapping[str, Any],
    bundle_manifest_doc: Mapping[str, Any],
    provider_extract_doc: Mapping[str, Any],
    rate_series_doc: Mapping[str, Any],
    manifest: Mapping[str, Any],
    policy_doc: Mapping[str, Any],
    policy: FxPromotionPolicy,
    pair_id: str,
    as_of_date: str,
    cutoff_instant: str,
    effective_at: str,
) -> FxPromotionOutcome:
    """Pure top-level FX promotion algorithm. Deterministic: identical
    arguments always produce byte-identical documents."""
    findings: list[Finding] = []

    findings += check_bundle_domain_eligibility(bundle_manifest_doc, pair_id=pair_id)
    findings += check_provider_manifest_compatibility(provider_extract_doc, manifest)
    findings += check_manifest_authorization_findings(manifest, pair_id=pair_id, as_of_date=as_of_date)

    retrieved_at = provider_extract_doc.get("retrieved_at", "")
    findings += check_temporal_bounds(retrieved_at=retrieved_at, cutoff_instant=cutoff_instant, effective_at=effective_at)

    request = bundle_request_doc.get("request") or {}
    expected_provider_symbol = (request.get("resolved_provider_symbols") or {}).get(pair_id)
    pair_identity = manifest.get("pair_identity") or {}
    expected_base_currency = pair_identity.get("base_currency")
    expected_quote_currency = pair_identity.get("quote_currency")
    start_date_inclusive = request.get("start_date_inclusive", "")
    end_date_exclusive = request.get("end_date_exclusive", "")

    selected: SelectedFxRow | None = None
    if not has_blocking(findings):
        eligible_rows = select_eligible_rows(
            rate_series_doc.get("rows", ()),
            pair_id=pair_id,
            provider_symbol=expected_provider_symbol,
            base_currency=expected_base_currency,
            quote_currency=expected_quote_currency,
            as_of_date=as_of_date,
            start_date_inclusive=start_date_inclusive,
            end_date_exclusive=end_date_exclusive,
        )
        selected, row_findings = select_row(eligible_rows, as_of_date=as_of_date, max_fallback_lag_days=policy.max_fallback_lag_days)
        findings += row_findings
        if selected is not None:
            findings += check_effective_at_matches_trade_date(effective_at=effective_at, trade_date=selected.trade_date)

    overall_invalid = has_blocking(findings)
    sorted_findings = sort_findings(findings)

    if selected is not None and not overall_invalid:
        observation = _build_observation(
            selected,
            policy=policy,
            manifest=manifest,
            effective_at=effective_at,
            published_at=retrieved_at,
            available_at=retrieved_at,
        )
        observations_doc: dict = {"observations": [observation]}
        selected_trade_date = selected.trade_date
    else:
        observations_doc = {"observations": []}
        selected_trade_date = None

    validation_doc = {
        "schema_version": "1.0.0",
        "artifact_type": "fx_close_promotion_validation",
        "findings": [_finding_to_dict(f) for f in sorted_findings],
    }

    manifest_id = manifest.get("manifest_id")
    manifest_version = manifest.get("manifest_version")
    bundle_files = list(bundle_manifest_doc.get("bundle_files") or [])

    overall_status = "invalid" if overall_invalid else "valid"

    promotion_id_payload = {
        "pair_id": pair_id,
        "as_of_date": as_of_date,
        "cutoff_instant": cutoff_instant,
        "effective_at": effective_at,
        "manifest_id": manifest_id,
        "manifest_version": manifest_version,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
    }
    promotion_id = _hash_id("fx-close-promotion", promotion_id_payload)

    promotion_manifest_doc = {
        "schema_version": "1.0.0",
        "artifact_type": "fx_close_promotion_manifest",
        "promotion_id": promotion_id,
        "provider_id": (manifest.get("source_authority") or {}).get("provider_id"),
        "pair_id": pair_id,
        "as_of_date": as_of_date,
        "cutoff_instant": cutoff_instant,
        "selected_trade_date": selected_trade_date,
        "selected_price_field": policy.selected_price_field,
        "fx_mode": policy.fx_mode,
        "source_bundle": {"bundle_files": bundle_files},
        "market_source_manifest_ref": {
            "manifest_id": manifest_id,
            "manifest_version": manifest_version,
        },
        "promotion_policy_ref": {
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
        },
        "output_files": [
            {"relative_path": "observations.json"},
            {"relative_path": "validation.json"},
        ],
        "overall_status": overall_status,
        "finding_counts": _finding_counts(sorted_findings),
    }

    return FxPromotionOutcome(
        overall_status=overall_status,
        selected_trade_date=selected_trade_date,
        observations_doc=observations_doc,
        validation_doc=validation_doc,
        promotion_manifest_doc=promotion_manifest_doc,
        findings=tuple(sorted_findings),
        finding_counts=_finding_counts(sorted_findings),
    )
