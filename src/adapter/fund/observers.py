"""Watching for evidence.

An observer answers one question: has something happened that the system has
not seen before? It does not decide what to do about it -- that is the dispatch
table's job -- and it does not run anything.

Everything an observer notices is recorded before it is acted on. That is what
makes the cycle safe to re-run: the second pass sees the filing already in the
observed table and produces nothing. It is also what makes a machine that was
switched off for a week catch up correctly, because the watermark is "the last
thing I actually saw", not "the last time I looked".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

from ..discovery import list_filings
from ..models import FilingRef
from ..sec_client import SecClient
from .errors import FundError

#: The forms that carry the periodic evidence a thesis is monitored against.
#: Amendments are included: a restatement is exactly the kind of thing a
#: monitoring contract exists to catch.
PERIODIC_FORMS = ("10-K", "10-Q", "10-K/A", "10-Q/A")


class ObserverError(FundError):
    """An observation could not be made."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class FilingObservation:
    security_id: str
    cik: str
    accession: str
    form: str
    filing_date: str
    report_date: str

    def to_trigger(self) -> dict[str, Any]:
        return {
            "observation": "new_periodic_filing",
            "observed_at": _now(),
            "evidence_accession": self.accession,
            "evidence_date": self.filing_date,
            "detail": f"{self.form} filed {self.filing_date} for period {self.report_date}",
        }


def new_filings(
    client: SecClient,
    *,
    security_id: str,
    cik: str,
    seen_accessions: set[str],
    as_of: date,
    forms: Sequence[str] = PERIODIC_FORMS,
    limit: int = 4,
) -> list[FilingObservation]:
    """Filings this security has that we have not recorded seeing.

    Bounded by ``limit`` because the first run on a company with twenty years
    of history should produce one piece of work, not eighty. The bound is on
    what is *reported as new*, not on what is recorded as seen -- so the
    remainder is marked observed and never resurfaces.
    """
    filings: Iterable[FilingRef] = list_filings(client, cik, as_of=as_of, forms=tuple(forms))
    unseen = [f for f in filings if f.accession not in seen_accessions]
    unseen.sort(key=lambda f: (f.filing_date, f.accession), reverse=True)
    return [
        FilingObservation(
            security_id=security_id,
            cik=cik,
            accession=filing.accession,
            form=filing.form,
            filing_date=filing.filing_date.isoformat(),
            report_date=filing.report_date.isoformat(),
        )
        for filing in unseen[:limit]
    ]


def all_unseen(
    client: SecClient,
    *,
    security_id: str,
    cik: str,
    seen_accessions: set[str],
    as_of: date,
    forms: Sequence[str] = PERIODIC_FORMS,
) -> list[FilingObservation]:
    """Every unseen filing, so the ones beyond the limit can still be marked seen."""
    return new_filings(client, security_id=security_id, cik=cik,
                       seen_accessions=seen_accessions, as_of=as_of, forms=forms,
                       limit=10_000)


def earnings_observations(
    filings: Sequence[Mapping[str, Any]],
    *,
    security_id: str,
    thesis_id: str | None,
) -> list[dict[str, Any]]:
    """Earnings evidence that has actually landed.

    A date is not evidence. An expected earnings date is an estimate -- issued
    by the company, revised without notice, and frequently wrong -- and firing
    research at an estimate produces work against numbers that do not exist yet.

    So the trigger is the Item 2.02 filing itself. ``release_observed`` and
    ``evidence_available`` are different facts, and only the second one starts
    anything.
    """
    observations = []
    for filing in filings:
        items = filing.get("items") or ()
        if isinstance(items, str):
            items = tuple(part.strip() for part in items.split(",") if part.strip())
        if "2.02" not in items:
            continue
        observations.append({
            "observation": "earnings_evidence",
            "observed_at": _now(),
            "evidence_accession": filing["accession"],
            "evidence_date": filing["filing_date"],
            "detail": f"Item 2.02 results filed {filing['filing_date']}",
            "_security_id": security_id,
            "_thesis_id": thesis_id,
        })
    return observations


def price_shock_observations(
    marks: Sequence[Mapping[str, str]],
    *,
    security_id: str,
    thesis_id: str | None,
    threshold_bps: int,
    window_days: int,
    as_of: str,
) -> list[dict[str, Any]]:
    """A move large enough to be worth re-reading the thesis for.

    A price fall triggers a review, never a sale. That distinction is the whole
    reason this observer exists: the market disagreeing with a thesis is
    information about the thesis, not an instruction about the position.

    The baseline is the most recent mark at least ``window_days`` old, so a
    steady drift does not register while a step does.
    """
    from decimal import Decimal

    from .money import to_string

    if len(marks) < 2:
        return []

    ordered = sorted(marks, key=lambda m: m["as_of"])
    latest = ordered[-1]
    if latest["as_of"] > as_of:
        return []

    cutoff = (date.fromisoformat(latest["as_of"]) - timedelta(days=window_days)).isoformat()
    older = [m for m in ordered[:-1] if m["as_of"] <= cutoff]
    baseline = older[-1] if older else ordered[0]
    if baseline["as_of"] == latest["as_of"]:
        return []

    base_price = Decimal(baseline["price"])
    if base_price <= 0:
        return []
    move = (Decimal(latest["price"]) - base_price) / base_price
    if abs(move) * 10000 < threshold_bps:
        return []

    return [{
        "observation": "price_shock",
        "observed_at": _now(),
        "price_move_fraction": to_string(move.quantize(Decimal("0.0001"))),
        "price_window": f"{baseline['as_of']}..{latest['as_of']}",
        "detail": (f"{move * 100:.1f}% between {baseline['as_of']} and {latest['as_of']} "
                   f"-- a review, not a sale"),
        "_security_id": security_id,
        "_thesis_id": thesis_id,
    }]


def review_due_observations(
    theses: Mapping[str, Any], *, as_of: str
) -> list[dict[str, Any]]:
    """Theses whose qualitative review has come due.

    Included here rather than left to the monthly session because a review that
    only happens when someone remembers it is not a review.
    """
    from . import thesis as thesis_module

    triggers = []
    for history in theses.values():
        document = history.document
        if document["status"] == thesis_module.CLOSED:
            continue
        due = thesis_module.due_qualitative_checks(document, as_of)
        if not due:
            continue
        triggers.append({
            "observation": "review_due",
            "observed_at": _now(),
            "review_due": min(check["review_due"] for check in due),
            "detail": f"{len(due)} qualitative check(s) due: "
                      + ", ".join(check["check_id"] for check in due),
            "_thesis_id": document["thesis_id"],
            "_security_id": document["security_id"],
        })
    return triggers
