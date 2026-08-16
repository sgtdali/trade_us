"""Thesis lifecycle: the transition rules and the projection.

One rule outranks everything else in this module, and it is enforced in a
single place so it cannot be forgotten at a call site:

    A machine may move a thesis to ``review_required``. Nothing else.

A mechanical breach means a number crossed a line that was written down in
advance. It does not mean the reasoning was wrong -- the metric may have been
restated, the line may have been drawn badly, or the miss may be real and
irrelevant. Deciding which of those it is, is the judgement the owner is here
to make, and a system that made it for them would be quietly replacing the
person it was built to serve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from . import ids, schemas
from .errors import FundError

ACTIVE = "active"
REVIEW_REQUIRED = "review_required"
BROKEN = "broken"
CLOSED = "closed"

#: The transitions the design allows, and only those. Notably absent:
#: active -> closed. Winding a thesis up is a lifecycle judgement, so it goes
#: through review_required like any other. See "Tasarim sorulari" in
#: docs/uygulama-plani.md -- this is a question for the owner, not a decision
#: taken here.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    ACTIVE: frozenset({REVIEW_REQUIRED}),
    REVIEW_REQUIRED: frozenset({ACTIVE, BROKEN, CLOSED}),
    BROKEN: frozenset({CLOSED}),
    CLOSED: frozenset(),
}

#: The one transition a machine is trusted with.
MACHINE_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({(ACTIVE, REVIEW_REQUIRED)})

MAX_MECHANICAL_RULES = 5


class ThesisError(FundError):
    """A thesis operation was refused."""


class TransitionRefused(ThesisError):
    """The requested status change is not allowed, or not allowed to this actor."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_transition(from_status: str, to_status: str, actor: str) -> None:
    """Raise unless this actor may make this move."""
    if from_status not in ALLOWED_TRANSITIONS:
        raise TransitionRefused(f"unknown status: {from_status!r}")
    if to_status not in ALLOWED_TRANSITIONS[from_status]:
        allowed = ", ".join(sorted(ALLOWED_TRANSITIONS[from_status])) or "nothing"
        raise TransitionRefused(
            f"a thesis cannot go from {from_status} to {to_status}; from {from_status} it may "
            f"only become {allowed}"
        )
    if actor == "machine" and (from_status, to_status) not in MACHINE_TRANSITIONS:
        raise TransitionRefused(
            f"the machine may only request a review ({ACTIVE} -> {REVIEW_REQUIRED}); "
            f"moving a thesis to {to_status} is the owner's judgement"
        )


# --------------------------------------------------------------------------
# Building events
# --------------------------------------------------------------------------

def open_event(
    *,
    security_id: str,
    thesis_statement: str,
    assessment_id: str,
    effective_date: str,
    thesis_id: str | None = None,
) -> dict[str, Any]:
    return {
        "thesis_event_id": ids.uuid7(),
        "thesis_id": thesis_id or ids.new_id(ids.THESIS),
        "event_type": "opened",
        "effective_date": effective_date,
        "recorded_at": _now(),
        "actor": "human",
        "security_id": security_id,
        "thesis_statement": thesis_statement,
        "assessment_id": assessment_id,
    }


def status_event(
    *,
    thesis_id: str,
    from_status: str,
    to_status: str,
    reason: str,
    effective_date: str,
    actor: str = "human",
    resolution: str | None = None,
) -> dict[str, Any]:
    check_transition(from_status, to_status, actor)
    if resolution and from_status != REVIEW_REQUIRED:
        raise ThesisError("a resolution only describes the end of a review")
    document = {
        "thesis_event_id": ids.uuid7(),
        "thesis_id": thesis_id,
        "event_type": "status_changed",
        "effective_date": effective_date,
        "recorded_at": _now(),
        "actor": actor,
        "from_status": from_status,
        "to_status": to_status,
        "reason": reason,
    }
    if resolution:
        document["resolution"] = resolution
    return document


def contract_event(
    *, thesis_id: str, contract: Mapping[str, Any], effective_date: str
) -> dict[str, Any]:
    return {
        "thesis_event_id": ids.uuid7(),
        "thesis_id": thesis_id,
        "event_type": "contract_activated",
        "effective_date": effective_date,
        "recorded_at": _now(),
        "actor": "human",
        "monitoring_contract": dict(contract),
    }


def assessment_event(*, thesis_id: str, assessment_id: str, effective_date: str) -> dict[str, Any]:
    return {
        "thesis_event_id": ids.uuid7(),
        "thesis_id": thesis_id,
        "event_type": "assessment_linked",
        "effective_date": effective_date,
        "recorded_at": _now(),
        "actor": "human",
        "assessment_id": assessment_id,
    }


def check_reviewed_event(
    *, thesis_id: str, check_id: str, next_review_due: str, effective_date: str
) -> dict[str, Any]:
    return {
        "thesis_event_id": ids.uuid7(),
        "thesis_id": thesis_id,
        "event_type": "qualitative_check_reviewed",
        "effective_date": effective_date,
        "recorded_at": _now(),
        "actor": "human",
        "check_id": check_id,
        "next_review_due": next_review_due,
    }


def close_event(
    *, thesis_id: str, close_reason: str, reason: str, effective_date: str,
    superseded_by: str | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "thesis_event_id": ids.uuid7(),
        "thesis_id": thesis_id,
        "event_type": "closed",
        "effective_date": effective_date,
        "recorded_at": _now(),
        "actor": "human",
        "close_reason": close_reason,
        "reason": reason,
    }
    if superseded_by:
        document["superseded_by"] = superseded_by
    return document


# --------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------

@dataclass
class ThesisHistory:
    """A thesis plus the trail that produced it."""

    document: dict[str, Any]
    transitions: list[dict[str, Any]] = field(default_factory=list)
    contract_versions: list[dict[str, Any]] = field(default_factory=list)
    assessments: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return self.document["status"]

    @property
    def thesis_id(self) -> str:
        return self.document["thesis_id"]


def project(events: Iterable[Mapping[str, Any]]) -> dict[str, ThesisHistory]:
    """Fold the thesis event stream into current documents, keyed by thesis id."""
    theses: dict[str, ThesisHistory] = {}

    for event in sorted(events, key=lambda e: (e["effective_date"], e["recorded_at"])):
        thesis_id = event["thesis_id"]
        event_type = event["event_type"]

        if event_type == "opened":
            theses[thesis_id] = ThesisHistory(document={
                "thesis_id": thesis_id,
                "security_id": event["security_id"],
                "opened_at": event["effective_date"],
                "thesis_statement": event["thesis_statement"],
                "status": ACTIVE,
                "current_assessment_id": event["assessment_id"],
            })
            theses[thesis_id].assessments.append(event["assessment_id"])
            continue

        history = theses.get(thesis_id)
        if history is None:
            raise ThesisError(f"{event_type} arrived for an unopened thesis: {thesis_id}")
        document = history.document

        if event_type == "status_changed":
            check_transition(event["from_status"], event["to_status"], event["actor"])
            if document["status"] != event["from_status"]:
                raise ThesisError(
                    f"{thesis_id}: transition claims to start from {event['from_status']} "
                    f"but the thesis is {document['status']}"
                )
            document["status"] = event["to_status"]
            document["status_reason"] = event["reason"]
            if event["to_status"] == ACTIVE:
                document.pop("status_reason", None)
            history.transitions.append(dict(event))

        elif event_type == "contract_activated":
            document["monitoring_contract"] = dict(event["monitoring_contract"])
            history.contract_versions.append(dict(event["monitoring_contract"]))

        elif event_type == "assessment_linked":
            document["current_assessment_id"] = event["assessment_id"]
            history.assessments.append(event["assessment_id"])

        elif event_type == "qualitative_check_reviewed":
            contract = document.get("monitoring_contract")
            if contract:
                for check in contract["qualitative_checks"]:
                    if check["check_id"] == event["check_id"]:
                        check["last_reviewed_at"] = event["effective_date"]
                        check["review_due"] = event["next_review_due"]

        elif event_type == "closed":
            document["status"] = CLOSED
            document["closed_at"] = event["effective_date"]
            document["close_reason"] = event["close_reason"]
            document["status_reason"] = event["reason"]
            if event.get("superseded_by"):
                document["superseded_by"] = event["superseded_by"]
            history.transitions.append(dict(event))

        else:  # pragma: no cover -- the schema's enum is closed
            raise ThesisError(f"unhandled thesis event: {event_type!r}")

    for history in theses.values():
        schemas.validate(history.document, schemas.THESIS)
    return theses


def open_for_security(theses: Mapping[str, ThesisHistory], security_id: str) -> ThesisHistory | None:
    """The one live thesis for a security, if there is one."""
    for history in theses.values():
        if history.document["security_id"] == security_id and history.status != CLOSED:
            return history
    return None


# --------------------------------------------------------------------------
# Contracts
# --------------------------------------------------------------------------

def build_contract(
    *,
    version: int,
    effective_from: str,
    mechanical_rules: Sequence[Mapping[str, Any]],
    qualitative_checks: Sequence[Mapping[str, Any]],
    change_reason: str | None = None,
) -> dict[str, Any]:
    if len(mechanical_rules) > MAX_MECHANICAL_RULES:
        raise ThesisError(
            f"{len(mechanical_rules)} mechanical rules: the ceiling is {MAX_MECHANICAL_RULES}. "
            "A contract nobody reads is not monitoring."
        )
    rule_ids = [rule["rule_id"] for rule in mechanical_rules]
    if len(set(rule_ids)) != len(rule_ids):
        raise ThesisError("two mechanical rules share a rule_id")
    check_ids = [check["check_id"] for check in qualitative_checks]
    if len(set(check_ids)) != len(check_ids):
        raise ThesisError("two qualitative checks share a check_id")

    contract: dict[str, Any] = {
        "version": version,
        "effective_from": effective_from,
        "mechanical_rules": [dict(rule) for rule in mechanical_rules],
        "qualitative_checks": [dict(check) for check in qualitative_checks],
    }
    if change_reason:
        contract["change_reason"] = change_reason
    return contract


def due_qualitative_checks(document: Mapping[str, Any], as_of: str) -> list[dict[str, Any]]:
    contract = document.get("monitoring_contract")
    if not contract:
        return []
    return [check for check in contract["qualitative_checks"] if check["review_due"] <= as_of]
