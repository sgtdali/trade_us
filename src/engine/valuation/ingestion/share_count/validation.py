"""Pure eligibility checks and deterministic record selection for the
share-count promotion bridge.

Every function here is pure: no file I/O, no process clock, no ticker
literal, and no network. Findings reuse the shared, unchanged
:class:`~engine.valuation.validation.findings.Finding`
contract -- the same type the sibling price-promotion package and T70
market resolver already use.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence

from ...market.registry import check_manifest_authorization
from ...validation.findings import Finding
from .models import CorporateActionLedgerEntry, CoverageRecord, ShareCountRecord


def select_eligible_records(
    records: Sequence[ShareCountRecord],
    *,
    concept: str,
    as_of_date: str,
    cutoff_instant: str,
) -> list[ShareCountRecord]:
    """Filter ledger records down to the ones structurally eligible for
    promotion: matching concept, not withdrawn, effective date not in the
    future relative to ``as_of_date``, and both publication and
    availability known no later than ``cutoff_instant``."""
    eligible: list[ShareCountRecord] = []
    for record in records:
        if record.concept != concept:
            continue
        if record.revision_status == "withdrawn":
            continue
        if record.effective_at[:10] > as_of_date:
            continue
        if record.published_at > cutoff_instant:
            continue
        if record.available_at > cutoff_instant:
            continue
        eligible.append(record)
    return eligible


def select_record(
    eligible: Sequence[ShareCountRecord],
    *,
    concept: str,
    derivation_priority: Sequence[str],
) -> tuple[ShareCountRecord | None, list[Finding]]:
    """Deterministically select the latest-effective eligible record.
    Among records tied at the latest effective instant, prefer the
    highest-priority ``derivation_type`` (direct disclosure over a
    percentage-derived value); a same-priority-tier disagreement in value
    is an unresolved conflict, never averaged."""
    if not eligible:
        return None, [Finding(
            rule_id="SHARE-ROW-001", severity="blocker", scope="bundle",
            reason_code="selection.no_eligible_record",
            message=f"no eligible {concept} record was found for the requested as-of date/cutoff",
        )]

    latest_effective = max(r.effective_at for r in eligible)
    top = [r for r in eligible if r.effective_at == latest_effective]

    def _priority(record: ShareCountRecord) -> int:
        try:
            return derivation_priority.index(record.derivation_type)
        except ValueError:
            return len(derivation_priority)

    best_priority = min(_priority(r) for r in top)
    top = [r for r in top if _priority(r) == best_priority]

    distinct_values = {r.value for r in top}
    if len(distinct_values) > 1:
        return None, [Finding(
            rule_id="SHARE-ROW-002", severity="blocker", scope="bundle",
            reason_code="identity.unresolved_same_tier_conflict",
            message=f"{concept}: {len(top)} same-priority-tier record(s) disagree on value at effective_at {latest_effective!r}",
            related_reference_ids=tuple(sorted(r.record_id for r in top)),
        )]

    selected = sorted(top, key=lambda r: r.record_id)[0]
    return selected, []


def check_reconciliation(*, issued_value: str, treasury_value: str) -> list[Finding]:
    """Positivity/ordering checks per the promotion policy's reconciliation
    block. Never averages, never treats missing as zero (the caller is
    responsible for not invoking this when either value is unavailable)."""
    findings: list[Finding] = []
    issued_decimal = Decimal(issued_value)
    treasury_decimal = Decimal(treasury_value)

    if issued_decimal <= 0:
        findings.append(Finding(
            rule_id="SHARE-RECON-001", severity="blocker", scope="bundle",
            reason_code="capital.nonpositive_issued_shares",
            message=f"issued_shares must be strictly positive, got {issued_value!r}",
        ))
    if treasury_decimal < 0:
        findings.append(Finding(
            rule_id="SHARE-RECON-002", severity="blocker", scope="bundle",
            reason_code="capital.negative_treasury_shares",
            message=f"treasury_shares must not be negative, got {treasury_value!r}",
        ))
    if treasury_decimal > issued_decimal:
        findings.append(Finding(
            rule_id="SHARE-RECON-003", severity="blocker", scope="bundle",
            reason_code="capital.treasury_exceeds_issued",
            message=f"treasury_shares ({treasury_value!r}) must not exceed issued_shares ({issued_value!r})",
        ))
    if not findings and (issued_decimal - treasury_decimal) <= 0:
        findings.append(Finding(
            rule_id="SHARE-RECON-004", severity="blocker", scope="bundle",
            reason_code="capital.nonpositive_basic_shares",
            message="issued_shares - treasury_shares did not reconcile to a positive spot basic share count",
        ))
    return findings


# Which record concept(s) each corporate-action event_type can actually
# change. A treasury_purchase/treasury_sale never changes issued_shares
# (a buyback moves shares into treasury, it does not retire or issue
# them), so an unresolved treasury event must never block the
# issued_shares selection -- and symmetrically for a capital event and
# treasury_shares. Confirmed a real, generalizable bug via BIMAS: a
# "Pay Geri Alım Programının Başlatılması" (buyback *program launch*)
# notice reports no post-transaction cumulative total (status stays
# "unknown" -- see build_treasury_record_from_corporate_action), and
# without this scoping it spuriously blocked the unrelated issued_shares
# record even though every later daily buyback notice already resolved
# the treasury side with a clean ascending cumulative total. split/
# reverse_split/cancellation/class_conversion/other are conservatively
# left affecting both concepts, since their real-world effect is less
# uniform than a plain capital or treasury event.
_EVENT_TYPE_AFFECTED_CONCEPTS: dict[str, frozenset[str]] = {
    "capital_increase": frozenset({"issued_shares"}),
    "capital_reduction": frozenset({"issued_shares"}),
    "treasury_purchase": frozenset({"treasury_shares"}),
    "treasury_sale": frozenset({"treasury_shares"}),
}
_BOTH_CONCEPTS = frozenset({"issued_shares", "treasury_shares"})


def check_unresolved_corporate_actions(
    *, record: ShareCountRecord, corporate_actions: Sequence[CorporateActionLedgerEntry], as_of_date: str,
) -> list[Finding]:
    """Apply lifecycle-aware temporal compatibility to spot share counts.

    ``announced`` and ``approved`` describe a known but not-yet-effective
    future action. They therefore produce a visible warning but do not make
    the last confirmed *spot* share count stale. ``unknown`` means the
    disclosure could already have affected the relevant concept and remains
    a blocker. Confirmed ``effective`` events are represented by their own
    share-count records; ``cancelled`` events never affect spot state.

    Concept scoping remains strict: a treasury event cannot change issued
    shares, and a capital event cannot change treasury holdings.
    """
    findings: list[Finding] = []
    record_effective_date = record.effective_at[:10]
    for entry in corporate_actions:
        if entry.status in ("effective", "cancelled"):
            continue
        if record.concept not in _EVENT_TYPE_AFFECTED_CONCEPTS.get(entry.event_type, _BOTH_CONCEPTS):
            continue
        if record_effective_date < entry.effective_date <= as_of_date:
            if entry.status in ("announced", "approved"):
                findings.append(Finding(
                    rule_id="SHARE-CA-002", severity="warning", scope="bundle",
                    reason_code="capital.pending_future_dilution",
                    message=(
                        f"{record.concept}: corporate-action event {entry.event_id!r} is "
                        f"{entry.status!r} but not effective as of {as_of_date!r}; the last "
                        f"confirmed spot record {record.record_id!r} remains eligible, while "
                        "forward/diluted share count is not asserted"
                    ),
                    related_reference_ids=(entry.event_id,),
                ))
            else:
                findings.append(Finding(
                    rule_id="SHARE-CA-001", severity="blocker", scope="bundle",
                    reason_code="capital.unresolved_later_capital_event",
                    message=(
                        f"{record.concept}: selected record {record.record_id!r} (effective_at {record.effective_at!r}) "
                        f"predates corporate-action event {entry.event_id!r} (status {entry.status!r}, "
                        f"reference date {entry.effective_date!r}), whose effect is unknown as of {as_of_date!r} -- "
                        "the record is not production-eligible until that ambiguity resolves"
                    ),
                    related_reference_ids=(entry.event_id,),
                ))
    return findings


def check_coverage_freshness(
    coverage: CoverageRecord, *, as_of_date: str, required_status: str,
) -> list[Finding]:
    """Enforce the promotion policy's declared
    ``corporate_action_coverage_policy.current_valuation_requires_status``
    (validated at policy-load time to be ``"complete"``) against the
    ledger's own authored coverage review -- previously declared by the
    policy schema and by this package's own error-hierarchy docstring, but
    never actually checked here.

    Both checks are **warnings**, not blockers. A ``coverage_status``
    mismatch flags a known, analyst-recorded gap (e.g. an undetermined
    treasury basis for a historical period) -- real production ledgers
    (e.g. AKSEN, as of this writing) already carry ``"gap"`` status while
    still promoting a fully eligible *current* share count, because the
    gap sits in a historical record the current as-of date never selects.
    Turning this into a hard blocker would silently break those already-
    working current valuations, so it stays advisory: visible in every
    promotion's findings, but never zeroes out ``observations_doc``.

    A ``coverage_end_date`` older than ``as_of_date`` is likewise a
    warning only: the ledger is normally reviewed/refreshed per financial
    period, not per calendar day, so this is the ordinary steady state
    between quarterly reviews, not a defect -- it flags that no one has
    *specifically* re-checked for a capital/treasury ÖDA published in that
    gap, so a human should periodically look, but it must not halt every
    subsequent current-valuation run."""
    findings: list[Finding] = []
    if coverage.coverage_status != required_status:
        findings.append(Finding(
            rule_id="SHARE-COV-001", severity="warning", scope="bundle",
            reason_code="coverage.status_not_required",
            message=(
                f"share-count ledger coverage_status is {coverage.coverage_status!r}, but the "
                f"promotion policy declares {required_status!r} as the target for current "
                "valuation -- review the ledger's unresolved_gap_refs; this does not block "
                "promotion by itself, since the gap may sit outside the currently-selected record"
            ),
        ))
        return findings
    if coverage.coverage_end_date < as_of_date:
        findings.append(Finding(
            rule_id="SHARE-COV-002", severity="warning", scope="bundle",
            reason_code="coverage.stale_review_window",
            message=(
                f"share-count ledger coverage_end_date ({coverage.coverage_end_date!r}) is before "
                f"the requested as_of_date ({as_of_date!r}) -- no one has specifically re-checked "
                "for a capital/treasury ÖDA published between the two dates; this does not block "
                "promotion, but the ledger's coverage review should be periodically extended"
            ),
        ))
    return findings


def check_manifest_authorization_findings(manifest: Mapping[str, Any], *, ticker: str, as_of_date: str) -> list[Finding]:
    """Wrap :func:`engine.valuation.market.registry.check_manifest_authorization`
    as findings -- reused identically for both the share-count manifest and
    the corporate-action manifest."""
    problems = check_manifest_authorization(dict(manifest), ticker=ticker, as_of_date=as_of_date)
    return [
        Finding(
            rule_id="SHARE-AUTH-001", severity="blocker", scope="bundle",
            reason_code="authorization.manifest_rejected",
            message=problem,
        )
        for problem in problems
    ]

