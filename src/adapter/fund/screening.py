"""Discovery: looking for names we do not yet have a view on.

Deliberately the last thing built, and deliberately off by default. Monitoring
the book you already own has to be reliable before the system starts suggesting
additions to it -- otherwise discovery becomes a way of not looking at what is
already there.

Three limits shape it.

**It runs through the same dispatch table as everything else.** No separate
scheduler, no special path. A rule that grants the authority to call a model
should look like every other rule that does.

**Its output is a research candidate and nothing more.** Not a thesis, not a
readiness, not a capital judgement. A screen that ranks names has not
underwritten any of them, and the schema refuses to let it pretend otherwise.

**The screen does not know what we own.** No positions, no weights, no existing
theses. Duplicates are filtered afterwards, from the candidate list -- filtering
beforehand would tell the model which names we already believe in, and the
cheapest way to look insightful is to agree with the person asking.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

from .errors import FundError

#: How often discovery runs when it is switched on. Low by design: for a book
#: of five to ten names, a monthly screen already produces more candidates than
#: can be underwritten properly.
DEFAULT_INTERVAL_DAYS = 30

#: How many candidates may be open at once. The binding constraint on a book
#: this size is underwriting attention, not idea supply.
DEFAULT_MAX_OPEN_CANDIDATES = 3


class ScreeningError(FundError):
    """Discovery could not be planned."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class DiscoveryDecision:
    should_run: bool
    reason: str
    open_candidates: int = 0


def should_run(
    *,
    as_of: str,
    last_discovery: str | None,
    open_candidates: int,
    open_positions: int,
    max_active_positions: int,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
    max_open_candidates: int = DEFAULT_MAX_OPEN_CANDIDATES,
) -> DiscoveryDecision:
    """Whether to screen tonight.

    Two brakes, both about attention rather than cost. Candidates already open
    are candidates not yet underwritten, and a full book has nowhere to put a
    new name even if the name is good -- so the screen slows down instead of
    producing a backlog that quietly becomes a to-do list nobody works.
    """
    if open_candidates >= max_open_candidates:
        return DiscoveryDecision(
            False,
            f"{open_candidates} candidate(s) already waiting to be underwritten "
            f"(limit {max_open_candidates})",
            open_candidates)

    effective_interval = interval_days
    if open_positions >= max_active_positions:
        # Nowhere to put a new name. Still worth looking occasionally -- a
        # better idea can displace a weaker one -- but not at the usual rate.
        effective_interval = interval_days * 2

    if last_discovery is None:
        return DiscoveryDecision(True, "no screen has run yet", open_candidates)

    due = (date.fromisoformat(last_discovery) + timedelta(days=effective_interval)).isoformat()
    if as_of < due:
        return DiscoveryDecision(
            False, f"last screen {last_discovery}, next due {due}", open_candidates)

    note = f"last screen {last_discovery}"
    if effective_interval != interval_days:
        note += f" (book full: interval widened to {effective_interval} days)"
    return DiscoveryDecision(True, note, open_candidates)


def discovery_observation(*, as_of: str, universe_id: str) -> dict[str, Any]:
    return {
        "observation": "periodic_discovery",
        "observed_at": _now(),
        "detail": f"periodic screen of {universe_id}",
        "_security_id": None,
        "_thesis_id": None,
    }


def count_open_candidates(
    jobs: Iterable[Mapping[str, Any]],
    *,
    theses_by_security: Mapping[str, Any],
) -> int:
    """Candidates raised and not yet resolved into a thesis or a rejection."""
    open_statuses = {"pending", "running", "awaiting_adjudication"}
    total = 0
    for job in jobs:
        if job["recipe"] not in {"idea_generation", "onboarding_underwrite"}:
            continue
        if job["status"] in open_statuses:
            total += 1
        elif (job["recipe"] == "onboarding_underwrite"
              and job["status"] == "adjudicated"
              and job["security_id"] not in theses_by_security):
            # Underwritten, accepted, and no thesis opened from it: still an
            # open question rather than a closed one.
            total += 1
    return total


@dataclass(frozen=True)
class Candidate:
    ticker: str
    reason: str

    def to_document(self) -> dict[str, str]:
        return {"ticker": self.ticker, "reason": self.reason}


def filter_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    known_tickers: set[str],
    limit: int,
) -> tuple[list[Candidate], list[str]]:
    """Drop names we already have a view on -- afterwards, never beforehand.

    Telling the screen which names we already believe in would hand it the
    cheapest possible way to look insightful.
    """
    kept: list[Candidate] = []
    dropped: list[str] = []
    for entry in candidates:
        ticker = str(entry.get("ticker", "")).upper()
        if not ticker:
            continue
        if ticker in known_tickers:
            dropped.append(ticker)
            continue
        if len(kept) >= limit:
            dropped.append(ticker)
            continue
        kept.append(Candidate(ticker=ticker, reason=str(entry.get("reason", ""))))
    return kept, dropped


#: Keys that would mean the pipeline pack had been contaminated with our own
#: book. A company's own cash balance is exactly what a screen should see; our
#: cash is not. The two are different things and only the second is forbidden.
OUR_BOOK_KEYS = frozenset({
    "portfolio", "positions", "holdings", "thesis", "theses", "assessments",
    "decisions", "readiness", "current_weight", "policy_compliant_max_weight",
})


def build_universe_pack(
    *,
    job: Mapping[str, Any],
    universe: Sequence[str],
    universe_id: str,
    pipeline_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The screening pack: a universe and a question, and nothing about us.

    ``pipeline_pack`` is the output of ``us_pei_pack.py --for idea`` -- the SEC
    and valuation data for the whole universe, roughly a megabyte of it. Without
    it the screen has only ticker symbols to work with, which is not screening;
    it is asking a model what it remembers.

    That pack knows nothing about this book by construction: it is built from
    the universe config and SEC filings, and never reads the ledger. The check
    below is a guard against someone helpfully merging portfolio context into it
    later.

    No positions, no weights, no theses, no prior judgements. The exclusion of
    what we already own is not an oversight to be fixed later -- it is what
    makes the output worth reading.
    """
    pack: dict[str, Any] = {
        "pack_version": 1,
        "job_id": job["job_id"],
        "assessment_mode": "de_novo",
        "recipe": "idea_generation",
        "universe_id": universe_id,
        "universe": sorted(universe),
        "instructions": [
            "Screen this universe for names worth researching further.",
            "Produce research candidates with a reason each. Do not produce a readiness, "
            "a downside, a position size or any capital judgement -- none of those are "
            "yours to make here, and the output contract will reject them.",
            "Nothing about an existing portfolio is in this pack, deliberately. Do not "
            "speculate about what is held.",
            "Kill weak ideas aggressively. A short list of candidates that survive "
            "scrutiny is worth more than a long list that has not had any.",
        ],
    }

    if pipeline_pack is None:
        pack["data_warning"] = (
            "No financial data is attached. You are being asked to screen on ticker "
            "symbols alone, which you cannot do properly -- say so rather than "
            "recalling what you know about these companies."
        )
        return pack

    contaminated = sorted(OUR_BOOK_KEYS & set(pipeline_pack))
    if contaminated:
        raise ScreeningError(
            "the screening data carries this book's own state ("
            + ", ".join(contaminated)
            + "). A screen that knows what we hold is a screen that agrees with us."
        )

    pack["companies"] = pipeline_pack.get("companies", [])
    pack["data"] = {
        key: value for key, value in pipeline_pack.items()
        if key not in {"companies", "purpose", "pack_purpose", "intended_step"}
    }
    pack["universe"] = sorted(
        {str(company["ticker"]) for company in pack["companies"] if company.get("ticker")}
        or set(universe)
    )
    pack["instructions"].insert(
        1,
        f"`companies` holds the SEC-derived figures for all {len(pack['companies'])} names, "
        "prepared by this pipeline. Those numbers are the primary source of truth; "
        "prefer them over anything you recall.",
    )
    return pack
