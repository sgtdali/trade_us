"""Research jobs: deduplication, retry, and the queue the operator actually sees.

A job is stored as a sequence of immutable revisions rather than a row that
gets updated. Every write still goes through the one commit gate, the attempt
history cannot be quietly rewritten, and "what did this job look like before it
failed the third time" stays answerable.

The queue is **not** a fourth ledger. Q0/Q1/Q2 are computed from the jobs and
the open assessments every time they are asked for. A stored queue is a second
copy of the truth that drifts the first time something is written to one and
not the other.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

from . import ids
from .errors import FundError

PENDING = "pending"
RUNNING = "running"
AWAITING_ADJUDICATION = "awaiting_adjudication"
ADJUDICATED = "adjudicated"
FAILED = "failed"
CONTRACT_FAILED = "contract_failed"
SUPERSEDED = "superseded"
ABANDONED = "abandoned"

OPEN_STATUSES = frozenset({PENDING, RUNNING, AWAITING_ADJUDICATION})

#: The design's error table. Each class differs in how many times it is worth
#: trying again, because they fail for different reasons: a data source is
#: usually late rather than broken, a transport error is usually transient, and
#: a contract error will not fix itself by being run again.
RETRY_BUDGET: dict[str, int] = {
    "data_source_error": 3,
    "skill_transport_error": 3,
    "contract_error": 2,
    "late_result": 1,
}

#: After this many failed attempts the system stops trying by itself. It does
#: not go quiet -- the job surfaces in Q0 -- it just stops burning cycles on
#: something that is not going to start working on its own.
MAX_ATTEMPTS = 3


class JobError(FundError):
    """A job transition was refused."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Deduplication
# --------------------------------------------------------------------------

def dedup_key(
    *,
    observation: str,
    security_id: str,
    thesis_id: str | None = None,
    evidence_accession: str | None = None,
    monitoring_contract_version: int | None = None,
    review_due: str | None = None,
    price_window: str | None = None,
    discovery_date: str | None = None,
) -> str:
    """What makes two pieces of work the same piece of work.

    Deliberately built from the *evidence*, not from the moment of noticing.
    Running the cycle twice on one night, or three nights in a row over the
    same unread filing, has to produce one job.
    """
    parts = [observation, security_id, thesis_id or "-"]
    if evidence_accession:
        parts.append(f"acc={evidence_accession}")
    if monitoring_contract_version is not None:
        parts.append(f"cv={monitoring_contract_version}")
    if review_due:
        parts.append(f"due={review_due}")
    if price_window:
        parts.append(f"pw={price_window}")
    if discovery_date:
        parts.append(f"disc={discovery_date}")
    raw = "|".join(parts)
    return f"{observation}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def merge_triggers(triggers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fold several observations about one thesis into a single trigger snapshot.

    Three signals about the same company on the same evidence is one piece of
    reading, not three. Merging them here is what stops a busy filing night
    from producing an inbox nobody opens.
    """
    if not triggers:
        raise JobError("no triggers to merge")
    if len(triggers) == 1:
        return dict(triggers[0])

    ordered = sorted(triggers, key=lambda t: t["observed_at"])
    merged = dict(ordered[0])
    breached: list[str] = []
    for trigger in ordered:
        breached.extend(trigger.get("breached_rule_ids", []))
        for key in ("evidence_accession", "evidence_date", "monitoring_contract_version",
                    "review_due", "price_move_fraction"):
            if key not in merged and key in trigger:
                merged[key] = trigger[key]
    if breached:
        merged["breached_rule_ids"] = sorted(dict.fromkeys(breached))
    merged["detail"] = (
        f"merged {len(triggers)} observations: "
        + ", ".join(sorted({t["observation"] for t in triggers}))
    )
    return merged


# --------------------------------------------------------------------------
# Building and advancing jobs
# --------------------------------------------------------------------------

def new_job(
    *,
    trigger_snapshot: Mapping[str, Any],
    rule_id: str,
    rule_version: int,
    recipe: str,
    assessment_mode: str,
    security_id: str | None,
    dedup_key_value: str,
    thesis_id: str | None = None,
    decision_deadline: str | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "job_id": ids.new_id(ids.RESEARCH_JOB),
        "created_at": _now(),
        "status": PENDING,
        "trigger_snapshot": dict(trigger_snapshot),
        "rule_id": rule_id,
        "rule_version": rule_version,
        "recipe": recipe,
        "assessment_mode": assessment_mode,
        "dedup_key": dedup_key_value,
        "attempts": [],
    }
    # A screening job is about a universe, not a security.
    if security_id and security_id != "-":
        document["security_id"] = security_id
    if thesis_id:
        document["thesis_id"] = thesis_id
    if decision_deadline:
        document["decision_deadline"] = decision_deadline
    return document


def _next(document: Mapping[str, Any]) -> dict[str, Any]:
    import copy

    return copy.deepcopy(dict(document))


#: Statuses a job can be attempted from. contract_failed is included because
#: the design allows one repair attempt: a malformed result is sometimes a
#: transient formatting failure rather than a permanently broken recipe.
ATTEMPTABLE = frozenset({PENDING, RUNNING, FAILED, CONTRACT_FAILED})


def start_attempt(document: Mapping[str, Any]) -> dict[str, Any]:
    if document["status"] not in ATTEMPTABLE:
        raise JobError(f"a job in {document['status']} cannot be attempted")
    if stopped(document):
        raise JobError(
            f"automatic retry stopped after {len(document['attempts'])} attempts; "
            "this job needs a human before it runs again"
        )
    updated = _next(document)
    updated["status"] = RUNNING
    updated["attempts"].append({
        "attempt": len(updated["attempts"]) + 1,
        "started_at": _now(),
        "outcome": "failed",  # replaced on success; a crash leaves it honest
        "error_class": "skill_transport_error",
        "detail": "attempt started",
    })
    return updated


def fail_attempt(document: Mapping[str, Any], *, error_class: str, detail: str) -> dict[str, Any]:
    if error_class not in RETRY_BUDGET:
        raise JobError(f"unknown error class: {error_class!r}")
    updated = _next(document)
    # A failure is itself an attempt. Callers that never opened one -- a result
    # rejected by its contract, for instance -- should not have to fake one.
    if not updated["attempts"] or updated["attempts"][-1].get("finished_at"):
        updated["attempts"].append({
            "attempt": len(updated["attempts"]) + 1,
            "started_at": _now(),
            "outcome": "failed",
            "error_class": error_class,
            "detail": detail,
        })
    attempt = updated["attempts"][-1]
    attempt.update({"finished_at": _now(), "outcome": "failed",
                    "error_class": error_class, "detail": detail})

    budget = min(RETRY_BUDGET[error_class], MAX_ATTEMPTS)
    exhausted = len(updated["attempts"]) >= budget
    updated["status"] = CONTRACT_FAILED if error_class == "contract_error" else FAILED
    updated["error"] = {
        "error_class": error_class,
        "detail": detail,
        "automatic_retry_stopped": exhausted,
    }
    return updated


def attach_result(
    document: Mapping[str, Any],
    *,
    artifact: Mapping[str, Any],
    proposed_assessment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    updated = _next(document)
    if updated["attempts"]:
        attempt = updated["attempts"][-1]
        attempt.update({"finished_at": _now(), "outcome": "succeeded"})
        attempt.pop("error_class", None)
        attempt["detail"] = "result attached"
    updated["result"] = {"artifact": dict(artifact)}
    if proposed_assessment is not None:
        updated["result"]["proposed_assessment"] = dict(proposed_assessment)
    updated["status"] = AWAITING_ADJUDICATION
    updated.pop("error", None)
    return updated


def mark_contract_failed(document: Mapping[str, Any], detail: str) -> dict[str, Any]:
    """A result that does not satisfy its contract is never put in front of a human.

    'The analyst had nothing to say' and 'the output could not be read' look
    the same on a screen and are not the same fact.
    """
    updated = fail_attempt(document, error_class="contract_error", detail=detail)
    updated.pop("result", None)
    return updated


def supersede(document: Mapping[str, Any], *, by_job_id: str) -> dict[str, Any]:
    updated = _next(document)
    updated["status"] = SUPERSEDED
    updated["superseded_by"] = by_job_id
    return updated


def adjudicate(
    document: Mapping[str, Any],
    *,
    outcome: str,
    assessment_id: str | None = None,
    reason: str | None = None,
    minutes_spent: int | None = None,
) -> dict[str, Any]:
    if document["status"] != AWAITING_ADJUDICATION:
        raise JobError(f"a job in {document['status']} is not awaiting adjudication")
    updated = _next(document)
    adjudication: dict[str, Any] = {"outcome": outcome, "adjudicated_at": _now()}
    if assessment_id:
        adjudication["assessment_id"] = assessment_id
    if reason:
        adjudication["reason"] = reason
    if minutes_spent is not None:
        adjudication["minutes_spent"] = minutes_spent
    updated["adjudication"] = adjudication
    updated["status"] = AWAITING_ADJUDICATION if outcome == "deferred" else ADJUDICATED
    return updated


def stopped(document: Mapping[str, Any]) -> bool:
    return bool(document.get("error", {}).get("automatic_retry_stopped"))


def attempts_used(document: Mapping[str, Any]) -> int:
    return len(document.get("attempts", []))


# --------------------------------------------------------------------------
# The queue
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class QueueItem:
    job: Mapping[str, Any]
    reason: str
    detail: str = ""
    estimate_minutes: int | None = None

    @property
    def job_id(self) -> str:
        return self.job["job_id"]


@dataclass
class Queue:
    """Q0 stops things, Q1 needs judgement, Q2 is information."""

    q0: list[QueueItem] = field(default_factory=list)
    q1: list[QueueItem] = field(default_factory=list)
    q2: list[QueueItem] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.q0 or self.q1)

    @property
    def blocks_new_risk(self) -> bool:
        return bool(self.q0)


#: Rough minutes, from the design's expectations. Shown so the owner can decide
#: whether they have time for this now -- and so anything routinely running
#: over is visible as a signal rather than absorbed as normal.
ESTIMATES = {
    "tracker": 10,
    "deep_dive_then_tracker": 25,
    "blind_review": 30,
    "onboarding_underwrite": 30,
    "idea_generation": 20,
}

_MATERIAL_OBSERVATIONS = frozenset({"mechanical_breach", "new_periodic_filing",
                                    "earnings_evidence", "price_shock"})


def _q1_rank(item: QueueItem, *, funded: set[str], as_of: str) -> tuple:
    job = item.job
    deadline = job.get("decision_deadline")
    overdue = 0 if (deadline and deadline < as_of) else 1
    # A screening job has no security, so it can never be "funded" -- which is
    # also the right priority: an existing position outranks a new idea.
    is_funded = 0 if job.get("security_id") in funded else 1
    observation = job["trigger_snapshot"]["observation"]
    material = 0 if observation in _MATERIAL_OBSERVATIONS else 1
    routine = 0 if observation == "review_due" else 1
    return (overdue, is_funded, material, routine, job["created_at"])


def build_queue(
    jobs: Iterable[Mapping[str, Any]],
    *,
    funded_security_ids: set[str] | None = None,
    blind_theses: Mapping[str, str] | None = None,
    as_of: str,
) -> Queue:
    """Derive the three classes. Nothing here is stored."""
    funded = funded_security_ids or set()
    queue = Queue()

    for job in jobs:
        status = job["status"]
        estimate = ESTIMATES.get(job["recipe"])

        if status == AWAITING_ADJUDICATION:
            observation = job["trigger_snapshot"]["observation"]
            queue.q1.append(QueueItem(
                job=job,
                reason=observation.replace("_", " "),
                detail=job["trigger_snapshot"].get("detail", ""),
                estimate_minutes=estimate,
            ))
        elif status in {FAILED, CONTRACT_FAILED}:
            error = job.get("error", {})
            if stopped(job):
                queue.q0.append(QueueItem(
                    job=job,
                    reason=f"{error.get('error_class', 'failed')} -- automatic retry stopped",
                    detail=error.get("detail", ""),
                ))
            else:
                queue.q2.append(QueueItem(
                    job=job,
                    reason=f"{error.get('error_class', 'failed')} -- will retry",
                    detail=error.get("detail", ""),
                ))
        elif status in {PENDING, RUNNING}:
            queue.q2.append(QueueItem(job=job, reason=f"{status}", estimate_minutes=estimate))

    for thesis_id, detail in (blind_theses or {}).items():
        queue.q0.append(QueueItem(
            job={"job_id": thesis_id, "security_id": "-", "recipe": "tracker",
                 "created_at": as_of, "trigger_snapshot": {"observation": "review_due"},
                 "status": PENDING},
            reason="monitoring is blind",
            detail=detail,
        ))

    queue.q1.sort(key=lambda item: _q1_rank(item, funded=funded, as_of=as_of))
    return queue


def total_estimate(queue: Queue) -> int:
    return sum(item.estimate_minutes or 0 for item in queue.q1)


def material_change(
    proposed: Mapping[str, Any], prior: Mapping[str, Any] | None
) -> tuple[bool, str]:
    """Whether accepting this proposal is a material change to the prior view.

    Material means a readiness move or a downside difference over 500 bp -- the
    two things that change what the position may be, and therefore the two that
    have to come with a written reason.
    """
    if prior is None:
        return False, ""
    if proposed["readiness"] != prior["readiness"]:
        return True, f"readiness {prior['readiness']} -> {proposed['readiness']}"
    if proposed["downside"]["status"] != prior["downside"]["status"]:
        return True, (f"downside {prior['downside']['status']} -> "
                      f"{proposed['downside']['status']}")
    if proposed["downside"]["status"] == "known":
        difference = abs(Decimal(proposed["downside"]["return_fraction"])
                         - Decimal(prior["downside"]["return_fraction"]))
        if difference > Decimal("0.05"):
            return True, f"downside moved {difference * 100:.1f} points"
    return False, ""
