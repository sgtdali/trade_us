"""Pure share-count/corporate-action promotion engine: given an
already-loaded ledger, share-count manifest, corporate-action manifest,
and promotion policy, deterministically select eligible issued/treasury
records and build the four promotion documents in memory.

No file I/O, no process clock, no network, no random ID, and no
ticker/company literal anywhere in this module -- every economically
relevant decision comes from the caller-supplied ledger/manifest/policy
data. Byte-identical inputs always produce byte-identical output.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any, Mapping

from ...canonical import canonical_bytes, normalize_decimal
from ...validation.findings import Finding, has_blocking, sort_findings
from .models import CorporateActionLedgerEntry, PromotionOutcome, PromotionPolicy, ShareCountLedger, ShareCountRecord
from .validation import (
    check_coverage_freshness,
    check_manifest_authorization_findings,
    check_reconciliation,
    check_unresolved_corporate_actions,
    select_eligible_records,
    select_record,
)

_UNIT = "shares"


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


def _record_revision_id(record: ShareCountRecord) -> str:
    if record.revision_id:
        return record.revision_id
    return _hash_id("share-count-revision", {"record_id": record.record_id, "value": record.value})


def _build_observation(record: ShareCountRecord, *, ledger: ShareCountLedger, manifest_id: str) -> dict:
    identity_payload = {"manifest_id": manifest_id, "ledger_id": ledger.ledger_id, "instrument_id": ledger.instrument_id, "concept": record.concept}
    observation_id = _hash_id("share-count-observation", identity_payload)
    return {
        "observation_id": observation_id,
        "observation_type": "share_count",
        "instrument_or_pair": f"{ledger.instrument_id}:{record.concept}",
        "value": record.value,
        "unit": _UNIT,
        "effective_at": record.effective_at,
        "published_at": record.published_at,
        "available_at": record.available_at,
        "source_manifest_id": manifest_id,
        "source_record_ref": record.record_id,
        "revision_id": _record_revision_id(record),
        "revision_status": record.revision_status,
        **({"supersedes_revision_id": record.supersedes_revision_id} if record.supersedes_revision_id else {}),
    }


def _entry_revision_id(entry: CorporateActionLedgerEntry) -> str:
    if entry.revision_id:
        return entry.revision_id
    payload = {
        "event_id": entry.event_id, "event_type": entry.event_type, "effective_date": entry.effective_date,
        "status": entry.status, "pre_issued_quote_units": entry.pre_issued_quote_units,
        "post_issued_quote_units": entry.post_issued_quote_units,
        "pre_treasury_quote_units": entry.pre_treasury_quote_units,
        "post_treasury_quote_units": entry.post_treasury_quote_units, "adjustment_ratio": entry.adjustment_ratio,
    }
    return _hash_id("corporate-action-revision", payload)


def _build_promoted_event(entry: CorporateActionLedgerEntry, *, manifest_id: str) -> dict:
    event: dict[str, Any] = {
        "event_id": entry.event_id,
        "event_type": entry.event_type,
        "instrument_id": entry.instrument_id,
        "available_at": entry.available_at,
        "effective_date": entry.effective_date,
        "status": entry.status,
        "source_manifest_id": manifest_id,
        "source_record_ref": entry.event_id,
        "revision_id": _entry_revision_id(entry),
        "revision_status": entry.revision_status,
    }
    if entry.announcement_at is not None:
        event["announcement_at"] = entry.announcement_at
    for field_name in (
        "pre_issued_quote_units", "post_issued_quote_units",
        "pre_treasury_quote_units", "post_treasury_quote_units", "adjustment_ratio",
    ):
        value = getattr(entry, field_name)
        if value is not None:
            event[field_name] = value
    return event


def build_promotion(
    *,
    ledger: ShareCountLedger,
    share_manifest: Mapping[str, Any],
    corporate_action_manifest: Mapping[str, Any],
    policy: PromotionPolicy,
    policy_doc: Mapping[str, Any],
    ticker: str,
    as_of_date: str,
    cutoff_instant: str,
) -> PromotionOutcome:
    """Pure top-level promotion algorithm. Deterministic: identical
    arguments always produce byte-identical documents."""
    findings: list[Finding] = []
    findings += check_manifest_authorization_findings(share_manifest, ticker=ticker, as_of_date=as_of_date)
    findings += check_manifest_authorization_findings(corporate_action_manifest, ticker=ticker, as_of_date=as_of_date)
    required_coverage_status = (policy_doc.get("corporate_action_coverage_policy") or {}).get("current_valuation_requires_status")
    findings += check_coverage_freshness(ledger.coverage, as_of_date=as_of_date, required_status=required_coverage_status)

    eligible_issued = select_eligible_records(ledger.records, concept="issued_shares", as_of_date=as_of_date, cutoff_instant=cutoff_instant)
    eligible_treasury = select_eligible_records(ledger.records, concept="treasury_shares", as_of_date=as_of_date, cutoff_instant=cutoff_instant)

    selected_issued, issued_findings = select_record(eligible_issued, concept="issued_shares", derivation_priority=policy.derivation_priority)
    selected_treasury, treasury_findings = select_record(eligible_treasury, concept="treasury_shares", derivation_priority=policy.derivation_priority)
    findings += issued_findings
    findings += treasury_findings

    for selected in (selected_issued, selected_treasury):
        if selected is not None:
            findings += check_unresolved_corporate_actions(record=selected, corporate_actions=ledger.corporate_actions, as_of_date=as_of_date)

    if selected_issued is not None and selected_treasury is not None:
        findings += check_reconciliation(issued_value=selected_issued.value, treasury_value=selected_treasury.value)

    overall_invalid = has_blocking(findings)
    share_manifest_id = share_manifest.get("manifest_id")
    ca_manifest_id = corporate_action_manifest.get("manifest_id")

    if selected_issued is not None and selected_treasury is not None and not overall_invalid:
        observations = [
            _build_observation(selected_issued, ledger=ledger, manifest_id=share_manifest_id),
            _build_observation(selected_treasury, ledger=ledger, manifest_id=share_manifest_id),
        ]
        observations_doc: dict = {"observations": observations}
        issued_quote_units = selected_issued.value
        treasury_quote_units = selected_treasury.value
        outstanding_quote_units = normalize_decimal(Decimal(issued_quote_units) - Decimal(treasury_quote_units))
    else:
        observations_doc = {"observations": []}
        issued_quote_units = None
        treasury_quote_units = None
        outstanding_quote_units = None

    sorted_findings = sort_findings(findings)

    promoted_events = [_build_promoted_event(entry, manifest_id=ca_manifest_id) for entry in ledger.corporate_actions]
    promoted_events.sort(key=lambda e: e["event_id"])
    corporate_actions_doc = {
        "schema_version": "1.0.0",
        "artifact_type": "corporate_action_bundle",
        "ticker": ticker,
        "instrument_id": ledger.instrument_id,
        "as_of_date": as_of_date,
        "cutoff_instant": cutoff_instant,
        "coverage": {
            "coverage_start_date": ledger.coverage.coverage_start_date,
            "coverage_end_date": ledger.coverage.coverage_end_date,
            "coverage_status": ledger.coverage.coverage_status,
            "reviewed_at": ledger.coverage.reviewed_at,
            "review_method": ledger.coverage.review_method,
            "reviewed_source_refs": list(ledger.coverage.reviewed_source_refs),
            "unresolved_gap_refs": list(ledger.coverage.unresolved_gap_refs),
        },
        "events": promoted_events,
        "source_manifest_refs": [
            {"manifest_id": ca_manifest_id, "manifest_version": corporate_action_manifest.get("manifest_version")},
        ],
    }

    validation_doc = {
        "schema_version": "1.0.0",
        "artifact_type": "share_count_promotion_validation",
        "findings": [_finding_to_dict(f) for f in sorted_findings],
    }

    overall_status = "invalid" if overall_invalid else "valid"

    promotion_id_payload = {
        "ticker": ticker, "as_of_date": as_of_date, "cutoff_instant": cutoff_instant,
        "ledger_id": ledger.ledger_id,
        "ledger_version": ledger.ledger_version,
        "share_manifest_id": share_manifest_id,
        "corporate_action_manifest_id": ca_manifest_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
    }
    promotion_id = _hash_id("share-count-promotion", promotion_id_payload)

    promotion_manifest_doc = {
        "schema_version": "1.0.0",
        "artifact_type": "share_count_promotion_manifest",
        "promotion_id": promotion_id,
        "ticker": ticker,
        "as_of_date": as_of_date,
        "cutoff_instant": cutoff_instant,
        "selected_issued_record_id": selected_issued.record_id if selected_issued else None,
        "selected_treasury_record_id": selected_treasury.record_id if selected_treasury else None,
        "issued_quote_units": issued_quote_units,
        "treasury_quote_units": treasury_quote_units,
        "spot_basic_shares_outstanding_quote_units": outstanding_quote_units,
        "source_ledger_ref": {"ledger_id": ledger.ledger_id, "ledger_version": ledger.ledger_version},
        "share_manifest_ref": {"manifest_id": share_manifest_id, "manifest_version": share_manifest.get("manifest_version")},
        "corporate_action_manifest_ref": {"manifest_id": ca_manifest_id, "manifest_version": corporate_action_manifest.get("manifest_version")},
        "promotion_policy_ref": {"policy_id": policy.policy_id, "policy_version": policy.policy_version},
        "output_files": [
            {"relative_path": "observations.json"},
            {"relative_path": "corporate-actions.json"},
            {"relative_path": "validation.json"},
        ],
        "overall_status": overall_status,
        "finding_counts": _finding_counts(sorted_findings),
    }

    return PromotionOutcome(
        overall_status=overall_status,
        observations_doc=observations_doc,
        corporate_actions_doc=corporate_actions_doc,
        validation_doc=validation_doc,
        promotion_manifest_doc=promotion_manifest_doc,
        findings=tuple(sorted_findings),
        finding_counts=_finding_counts(sorted_findings),
    )
