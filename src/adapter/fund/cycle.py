"""The nightly cycle.

Refresh, observe, match, deduplicate, run serially, validate, queue. One pass,
one process, no daemon, no workers, no queue server. For a book of five to ten
names that is not a simplification -- it is the correct size, and every piece of
machinery not built here is machinery that cannot fail at three in the morning.

Two properties this has to have, and they pull in opposite directions:

**It must not go quiet.** A cycle that fails silently is worse than no cycle,
because the owner stops checking. Every run records a heartbeat whether it
succeeded or not, and a failed run surfaces in Q0 the next morning.

**It must not thrash.** A cycle that reopens the same work every night trains
the owner to ignore it. Deduplication is on the evidence, and a job whose retry
budget is spent stops being retried automatically -- while still being visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from . import dispatch, ids, jobs, thesis as thesis_module
from .errors import FundError


class CycleError(FundError):
    """The cycle could not run at all."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class CycleReport:
    cycle_id: str
    started_at: str
    as_of: str
    finished_at: str | None = None
    status: str = "running"
    observed: int = 0
    jobs_opened: list[str] = field(default_factory=list)
    jobs_run: list[str] = field(default_factory=list)
    jobs_failed: list[tuple[str, str]] = field(default_factory=list)
    skipped_duplicates: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return self.status == "succeeded" and not self.jobs_failed

    def summary(self) -> str:
        parts = [
            f"{self.observed} observation(s)",
            f"{len(self.jobs_opened)} opened",
            f"{len(self.jobs_run)} run",
        ]
        if self.jobs_failed:
            parts.append(f"{len(self.jobs_failed)} failed")
        if self.skipped_duplicates:
            parts.append(f"{self.skipped_duplicates} already known")
        return ", ".join(parts)


def new_report(as_of: str) -> CycleReport:
    return CycleReport(cycle_id=ids.uuid7(), started_at=_now(), as_of=as_of)


# --------------------------------------------------------------------------
# Matching observations to work
# --------------------------------------------------------------------------

#: When several observations share one piece of evidence, the job is opened
#: under the most serious of them. A mechanical breach outranks the filing that
#: revealed it, because the breach is what the reading has to address.
OBSERVATION_PRIORITY: tuple[str, ...] = (
    "mechanical_breach",
    "price_shock",
    "earnings_evidence",
    "new_periodic_filing",
    "review_due",
    "preview_without_assessment",
    "periodic_discovery",
)


@dataclass(frozen=True)
class PendingWork:
    """An observation that matched a rule and has not been seen before."""

    trigger: Mapping[str, Any]
    rule: dispatch.DispatchRule
    security_id: str
    thesis_id: str | None
    dedup_key: str


def plan_work(
    observations: Sequence[Mapping[str, Any]],
    *,
    theses: Mapping[str, Any],
    already_open: Callable[[str], bool],
) -> tuple[list[PendingWork], int]:
    """Match observations to rules, merge and deduplicate.

    Several observations about one thesis on one piece of evidence become one
    job. Three signals about one company on one filing is one piece of reading,
    and an inbox that says otherwise is an inbox nobody opens.
    """
    # Grouped by EVIDENCE, not by observation type. Two signals about one
    # filing are one piece of reading; two different filings are two, however
    # similar they look. Getting this backwards either floods the inbox or
    # silently swallows a quarter.
    grouped: dict[tuple[str, str | None, str], list[Mapping[str, Any]]] = {}
    for observation in observations:
        evidence = (observation.get("evidence_accession")
                    or observation.get("review_due")
                    or observation.get("price_window")
                    or observation["observed_at"][:10])
        key = (observation["_security_id"], observation.get("_thesis_id"), evidence)
        grouped.setdefault(key, []).append(observation)

    planned: list[PendingWork] = []
    duplicates = 0

    for (security_id, thesis_id, _evidence), group in sorted(grouped.items()):
        history = theses.get(thesis_id) if thesis_id else None
        has_thesis = history is not None and history.status != thesis_module.CLOSED

        # One rule per piece of evidence: the most serious observation that has
        # one. A breach and the filing that revealed it produce a single job.
        chosen: tuple[str, dispatch.DispatchRule] | None = None
        for observation_type in OBSERVATION_PRIORITY:
            if not any(entry["observation"] == observation_type for entry in group):
                continue
            rule = dispatch.match(observation_type, has_open_thesis=has_thesis)
            if rule is not None:
                chosen = (observation_type, rule)
                break
        if chosen is None:
            continue
        observation_type, rule = chosen

        merged = jobs.merge_triggers([
            {k: v for k, v in entry.items() if not k.startswith("_")} for entry in group
        ])
        merged["observation"] = observation_type

        contract = history.document.get("monitoring_contract") if history is not None else None
        key = jobs.dedup_key(
            observation=observation_type,
            security_id=security_id,
            thesis_id=thesis_id,
            evidence_accession=merged.get("evidence_accession"),
            monitoring_contract_version=contract["version"] if contract else None,
            review_due=merged.get("review_due"),
        )
        if already_open(key):
            duplicates += 1
            continue
        if contract is not None:
            merged["monitoring_contract_version"] = contract["version"]
        planned.append(PendingWork(trigger=merged, rule=rule, security_id=security_id,
                                   thesis_id=thesis_id, dedup_key=key))

    return planned, duplicates


def to_job(work: PendingWork, *, decision_deadline: str | None = None) -> dict[str, Any]:
    return jobs.new_job(
        trigger_snapshot=work.trigger,
        rule_id=work.rule.rule_id,
        rule_version=work.rule.version,
        recipe=work.rule.recipe,
        assessment_mode=work.rule.assessment_mode,
        security_id=work.security_id,
        dedup_key_value=work.dedup_key,
        thesis_id=work.thesis_id,
        decision_deadline=decision_deadline,
    )


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------

def runnable(job: Mapping[str, Any]) -> bool:
    """Whether the cycle should attempt this job tonight."""
    if job["status"] not in jobs.ATTEMPTABLE:
        return False
    return not jobs.stopped(job)


def run_serially(
    pending: Sequence[Mapping[str, Any]],
    *,
    run_one: Callable[[Mapping[str, Any]], None],
    report: CycleReport,
    limit: int | None = None,
) -> None:
    """Run jobs one at a time, and let one failure be one failure.

    Serial on purpose. Parallelism would buy minutes on a workload that runs
    while the owner is asleep, and cost a class of bug that only appears under
    concurrency.
    """
    for job in list(pending)[:limit] if limit else pending:
        try:
            run_one(job)
            report.jobs_run.append(job["job_id"])
        except Exception as exc:  # noqa: BLE001 -- one job failing is not the cycle failing
            report.jobs_failed.append((job["job_id"], str(exc)[:300]))


def finish(report: CycleReport, *, failed: str | None = None) -> CycleReport:
    report.finished_at = _now()
    report.status = "failed" if failed else "succeeded"
    if failed:
        report.notes.append(failed)
    return report


# --------------------------------------------------------------------------
# Heartbeat
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Heartbeat:
    last_run_at: str | None
    last_status: str | None
    consecutive_failures: int
    silent_days: int | None

    @property
    def healthy(self) -> bool:
        return (self.last_status == "succeeded"
                and self.consecutive_failures == 0
                and (self.silent_days or 0) <= 2)

    def describe(self, as_of: str) -> str:
        if self.last_run_at is None:
            return "the cycle has never run"
        if self.consecutive_failures >= 2:
            return (f"{self.consecutive_failures} consecutive failed cycles "
                    f"since {self.last_run_at[:10]}")
        if (self.silent_days or 0) > 2:
            return f"no cycle for {self.silent_days} days (last {self.last_run_at[:10]})"
        return f"last cycle {self.last_run_at[:16].replace('T', ' ')} UTC: {self.last_status}"


def heartbeat_from(runs: Sequence[Mapping[str, Any]], *, as_of: str) -> Heartbeat:
    if not runs:
        return Heartbeat(None, None, 0, None)
    ordered = sorted(runs, key=lambda r: r["started_at"])
    last = ordered[-1]

    consecutive = 0
    for run in reversed(ordered):
        if run["status"] == "failed":
            consecutive += 1
        else:
            break

    from datetime import date

    # Measured against the operator date the cycle ran FOR, not the wall clock
    # it happened to run ON. "Today" is not a canonical field anywhere in this
    # system: the scheduler supplies an evaluation date and everything derives
    # from it, so a backfilled run is not misread as a two-month silence.
    last_as_of = last.get("as_of") or last["started_at"][:10]
    silent = (date.fromisoformat(as_of) - date.fromisoformat(last_as_of)).days
    return Heartbeat(last_run_at=last["started_at"], last_status=last["status"],
                     consecutive_failures=consecutive, silent_days=max(silent, 0))
