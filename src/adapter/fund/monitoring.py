"""The mechanical check engine.

A pure function from (rule, observation, catalog) to one of three answers:

``not_breached``
    The rule was evaluated and the line was not crossed. This does **not** mean
    the thesis is healthy -- it means one rule, out of the few that could be
    made mechanical, held. The distinction matters because a green screen is
    the easiest thing in the world to stop reading.

``breached``
    The line was crossed. The only consequence permitted anywhere in this
    system is that the thesis moves to ``review_required``.

``unavailable``
    The rule could not be evaluated: no data, stale data, a unit that no longer
    matches, a metric that has been restated. Never silently folded into
    "nothing changed" -- a check that did not happen is not a check that passed.

The engine reads no files, no clock and no network. Everything it needs is
handed to it, which is what makes the frozen-fixture tests meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

from . import ids, metrics
from .errors import FundError
from .money import to_decimal, to_string

NOT_BREACHED = "not_breached"
BREACHED = "breached"
UNAVAILABLE = "unavailable"

OPERATORS = {
    "lt": lambda observed, threshold: observed < threshold,
    "lte": lambda observed, threshold: observed <= threshold,
    "gt": lambda observed, threshold: observed > threshold,
    "gte": lambda observed, threshold: observed >= threshold,
}

#: Reasons a check could not be made. Closed, so "unavailable" is always
#: accompanied by something actionable rather than a shrug.
UNAVAILABLE_REASONS = frozenset({
    "no_observation",
    "observation_unavailable",
    "catalog_drift",
    "unit_mismatch",
    "stale_evidence",
    "binding_failed",
})


class MonitoringError(FundError):
    """A check could not be formed."""


@dataclass(frozen=True)
class Observation:
    """One measured value, as the data layer reports it.

    The narrow port between this system and the SEC/XBRL pipeline. Everything
    the engine needs travels through here, so the pipeline can change shape
    without the monitoring rules noticing.
    """

    metric_id: str
    period_basis: str
    status: str  # "available" | "unavailable"
    value: Decimal | None = None
    unit: str | None = None
    as_of: str | None = None
    source_accession: str | None = None
    reason: str | None = None

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "Observation":
        raw_value = document.get("value")
        return cls(
            metric_id=document["metric_id"],
            period_basis=document["period_basis"],
            status=document.get("status", "available"),
            value=to_decimal(raw_value) if raw_value is not None else None,
            unit=document.get("unit"),
            as_of=document.get("as_of"),
            source_accession=document.get("source_accession"),
            reason=document.get("reason"),
        )

    @property
    def key(self) -> tuple[str, str]:
        return (self.metric_id, self.period_basis)


@dataclass(frozen=True)
class CheckOutcome:
    rule_id: str
    result: str
    observed_value: Decimal | None = None
    threshold: Decimal | None = None
    reason: str | None = None
    detail: str | None = None
    source_accession: str | None = None
    binding_signature: str | None = None

    @property
    def is_breach(self) -> bool:
        return self.result == BREACHED

    @property
    def counted_as_checked(self) -> bool:
        """Whether this outcome represents a rule that was actually evaluated."""
        return self.result in {NOT_BREACHED, BREACHED}


def _unavailable(rule_id: str, reason: str, detail: str, **extra: Any) -> CheckOutcome:
    if reason not in UNAVAILABLE_REASONS:  # pragma: no cover -- guarded at call sites
        raise MonitoringError(f"unknown unavailable reason: {reason!r}")
    return CheckOutcome(rule_id=rule_id, result=UNAVAILABLE, reason=reason, detail=detail, **extra)


def evaluate_rule(
    rule: Mapping[str, Any],
    observation: Observation | None,
    catalog: Mapping[str, Any],
    *,
    max_evidence_age_days: int | None = None,
    as_of: str | None = None,
) -> CheckOutcome:
    """Evaluate one mechanical rule. Three answers, never two."""
    rule_id = rule["rule_id"]

    # Re-check the binding at evaluation time, not just at activation. The
    # catalog is a living file; a rule that bound six months ago may not now.
    try:
        metrics.check_binding(rule, catalog)
    except metrics.MetricBindingError as exc:
        return _unavailable(rule_id, "catalog_drift", str(exc))

    signature = metrics.binding_signature(rule, catalog)

    if observation is None:
        return _unavailable(rule_id, "no_observation",
                            f"no observation for {rule['metric_id']} on {rule['period_basis']}",
                            binding_signature=signature)
    if observation.status != "available":
        return _unavailable(rule_id, "observation_unavailable",
                            observation.reason or "the data layer reported no value",
                            source_accession=observation.source_accession,
                            binding_signature=signature)
    if observation.value is None:
        return _unavailable(rule_id, "observation_unavailable",
                            "observation marked available but carries no value",
                            source_accession=observation.source_accession,
                            binding_signature=signature)

    allowed_units = set(catalog.get(rule["metric_id"], {}).get("allowed_units", []))
    if observation.unit and allowed_units and observation.unit not in allowed_units:
        return _unavailable(
            rule_id, "unit_mismatch",
            f"observation is in {observation.unit!r}, the catalog allows "
            f"{', '.join(sorted(allowed_units))}",
            source_accession=observation.source_accession, binding_signature=signature,
        )

    if max_evidence_age_days is not None and as_of and observation.as_of:
        age = (datetime.fromisoformat(as_of) - datetime.fromisoformat(observation.as_of)).days
        if age > max_evidence_age_days:
            return _unavailable(
                rule_id, "stale_evidence",
                f"the newest observation is {age} days old, the limit is {max_evidence_age_days}",
                source_accession=observation.source_accession, binding_signature=signature,
            )

    threshold = to_decimal(rule["threshold"])
    comparison = OPERATORS.get(rule["operator"])
    if comparison is None:  # pragma: no cover -- the schema's enum is closed
        raise MonitoringError(f"unknown operator: {rule['operator']!r}")

    # The rule states the condition that would falsify the thesis, so a true
    # comparison is a breach.
    breached = comparison(observation.value, threshold)
    return CheckOutcome(
        rule_id=rule_id,
        result=BREACHED if breached else NOT_BREACHED,
        observed_value=observation.value,
        threshold=threshold,
        source_accession=observation.source_accession,
        binding_signature=signature,
        detail=(f"{observation.value} {rule['operator']} {threshold}"
                if breached else f"{observation.value} is not {rule['operator']} {threshold}"),
    )


def evaluate_contract(
    contract: Mapping[str, Any],
    observations: Iterable[Observation],
    catalog: Mapping[str, Any],
    **kwargs: Any,
) -> list[CheckOutcome]:
    by_key = {observation.key: observation for observation in observations}
    return [
        evaluate_rule(rule, by_key.get((rule["metric_id"], rule["period_basis"])), catalog, **kwargs)
        for rule in contract.get("mechanical_rules", [])
    ]


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(
    outcome: CheckOutcome,
    rule: Mapping[str, Any],
    *,
    thesis_id: str,
    contract_version: int,
    evaluated_for: str,
    evidence_accession: str | None = None,
) -> dict[str, Any]:
    """A durable record of one check: which rule, against which data, with what result."""
    document: dict[str, Any] = {
        "check_record_id": ids.new_id(ids.MONITORING_CHECK),
        "thesis_id": thesis_id,
        "rule_id": outcome.rule_id,
        "contract_version": contract_version,
        "metric_id": rule["metric_id"],
        "period_basis": rule["period_basis"],
        "test_type": rule["test_type"],
        "operator": rule["operator"],
        "threshold": rule["threshold"],
        "result": outcome.result,
        "evaluated_for": evaluated_for,
        "evaluated_at": _now(),
    }
    if outcome.observed_value is not None:
        document["observed_value"] = to_string(outcome.observed_value)
    if outcome.reason:
        document["unavailable_reason"] = outcome.reason
    if outcome.detail:
        document["detail"] = outcome.detail
    if outcome.binding_signature:
        document["binding_signature"] = outcome.binding_signature
    accession = evidence_accession or outcome.source_accession
    if accession:
        document["evidence_accession"] = accession
    return document


def breached_rules(outcomes: Sequence[CheckOutcome]) -> list[CheckOutcome]:
    return [outcome for outcome in outcomes if outcome.is_breach]


def unavailable_rules(outcomes: Sequence[CheckOutcome]) -> list[CheckOutcome]:
    return [outcome for outcome in outcomes if outcome.result == UNAVAILABLE]


def summarise(outcomes: Sequence[CheckOutcome]) -> str:
    if not outcomes:
        return "no mechanical rules"
    counts = {
        NOT_BREACHED: sum(1 for o in outcomes if o.result == NOT_BREACHED),
        BREACHED: sum(1 for o in outcomes if o.result == BREACHED),
        UNAVAILABLE: sum(1 for o in outcomes if o.result == UNAVAILABLE),
    }
    parts = [f"{count} {name.replace('_', ' ')}" for name, count in counts.items() if count]
    return ", ".join(parts)
