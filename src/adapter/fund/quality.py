"""Is the monitoring alive, and is the judgement real?

Both questions exist because this system fails quietly by construction.

A monitoring contract whose rules stop being evaluable does not raise an alarm
-- it produces silence, and silence is indistinguishable from a healthy thesis.
``monitoring_coverage`` is the mechanism that tells those apart.

An owner who accepts every proposal without changing anything, in ninety
seconds, without opening a source, is producing an audit trail that looks
exactly like careful adjudication. The quality signals do not stop that -- they
cannot -- but they make it countable, which is the most that can honestly be
done about it.

Nothing here blocks a decision except a blind thesis. These are measurements,
and measurements the owner is meant to read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

HEALTHY = "healthy"
DEGRADED = "degraded"
BLIND = "blind"

#: Two consecutive evidence periods with a rule unevaluable is the point at
#: which "the data was late" stops being a credible explanation.
BLIND_AFTER_CONSECUTIVE_UNAVAILABLE = 2

#: The design's expectation for a small book. Outside this band the thresholds
#: are miscalibrated, in one direction or the other: too many and the contract
#: is measuring noise, too few and it is measuring nothing.
FALSE_ALARM_TARGET = (4, 8)

#: Below this, the adjudication was not a judgement. Kept low deliberately --
#: it is meant to catch reflex, not thoroughness.
SHORT_ADJUDICATION_MINUTES = 3

#: Above this share of accepted-unchanged, acceptance has stopped carrying
#: information about the proposal.
UNCHANGED_ACCEPTANCE_WARNING = 0.8


@dataclass(frozen=True)
class Coverage:
    thesis_id: str
    state: str
    detail: str
    unavailable_rules: tuple[str, ...] = ()

    @property
    def blocks_new_risk(self) -> bool:
        return self.state == BLIND


def coverage_for(
    thesis_id: str,
    *,
    contract: Mapping[str, Any] | None,
    check_records: Sequence[Mapping[str, Any]],
    evidence_seen: int,
) -> Coverage:
    """How well this thesis is actually being watched.

    healthy  -- every mechanical rule was evaluated against the latest evidence.
    degraded -- evidence arrived and at least one rule could not be evaluated.
    blind    -- a rule has been unevaluable across two consecutive evidence
                periods, which is no longer explicable as late data.

    A thesis with no mechanical rules is not blind: it is monitored
    qualitatively, which is a legitimate choice for a condition no catalog
    metric captures honestly.
    """
    if contract is None:
        return Coverage(thesis_id, BLIND,
                        "no monitoring contract: nothing is watching this thesis")

    rules = contract.get("mechanical_rules", [])
    if not rules:
        return Coverage(thesis_id, HEALTHY,
                        "monitored qualitatively; no mechanical rules to evaluate")

    if not check_records:
        if evidence_seen == 0:
            return Coverage(thesis_id, HEALTHY, "no evidence has arrived yet")
        return Coverage(thesis_id, DEGRADED,
                        f"{evidence_seen} filing(s) arrived and no rule was evaluated",
                        tuple(rule["rule_id"] for rule in rules))

    # Per rule, walk its checks newest-first and count the unbroken run of
    # unavailable results. Only consecutive ones matter: one late quarter is
    # not the same as a rule that has stopped working.
    blind_rules: list[str] = []
    degraded_rules: list[str] = []
    for rule in rules:
        history = [record for record in check_records if record["rule_id"] == rule["rule_id"]]
        if not history:
            degraded_rules.append(rule["rule_id"])
            continue
        history.sort(key=lambda record: record["evaluated_at"])
        run = 0
        for record in reversed(history):
            if record["result"] == "unavailable":
                run += 1
            else:
                break
        if run >= BLIND_AFTER_CONSECUTIVE_UNAVAILABLE:
            blind_rules.append(rule["rule_id"])
        elif run == 1:
            degraded_rules.append(rule["rule_id"])

    if blind_rules:
        return Coverage(
            thesis_id, BLIND,
            f"{', '.join(blind_rules)} unevaluable across "
            f"{BLIND_AFTER_CONSECUTIVE_UNAVAILABLE} consecutive evidence periods",
            tuple(blind_rules))
    if degraded_rules:
        return Coverage(thesis_id, DEGRADED,
                        f"{', '.join(degraded_rules)} could not be evaluated on the "
                        "latest evidence",
                        tuple(degraded_rules))
    return Coverage(thesis_id, HEALTHY, f"{len(rules)} rule(s) evaluated on the latest evidence")


# --------------------------------------------------------------------------
# Adjudication quality
# --------------------------------------------------------------------------

@dataclass
class AdjudicationQuality:
    total: int = 0
    accepted_unchanged: int = 0
    short: int = 0
    acknowledged: int = 0
    sources_unchecked: int = 0
    rejected: int = 0
    replaced: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def unchanged_share(self) -> float:
        return self.accepted_unchanged / self.total if self.total else 0.0

    @property
    def warned(self) -> bool:
        return bool(self.warnings)


def adjudication_quality(
    jobs: Iterable[Mapping[str, Any]],
    assessments: Mapping[str, Mapping[str, Any]],
) -> AdjudicationQuality:
    """Signals that acceptance may have become ceremonial.

    None of these prove anything about a single decision. Across a year they
    are the difference between a person exercising judgement and a person
    clicking through.
    """
    quality = AdjudicationQuality()

    for job in jobs:
        adjudication = job.get("adjudication")
        if not adjudication or adjudication["outcome"] == "deferred":
            continue
        quality.total += 1
        outcome = adjudication["outcome"]

        if outcome == "rejected":
            quality.rejected += 1
            continue
        if outcome == "human_authored_replacement":
            quality.replaced += 1
        if outcome == "acknowledged_without_full_adjudication":
            quality.acknowledged += 1

        minutes = adjudication.get("minutes_spent")
        if minutes is not None and minutes < SHORT_ADJUDICATION_MINUTES:
            quality.short += 1

        assessment = assessments.get(adjudication.get("assessment_id", ""))
        if assessment is not None:
            if not assessment["acceptance"].get("critical_sources_checked"):
                quality.sources_unchecked += 1
            proposal = job.get("result", {}).get("proposed_assessment", {})
            if (outcome == "accepted"
                    and proposal.get("readiness") == assessment["readiness"]
                    and proposal.get("downside") == assessment["downside"]):
                quality.accepted_unchanged += 1

    if quality.total >= 5 and quality.unchanged_share > UNCHANGED_ACCEPTANCE_WARNING:
        quality.warnings.append(
            f"adjudication_quality_warning: {quality.accepted_unchanged} of {quality.total} "
            f"proposals accepted with nothing changed. Acceptance may have stopped "
            f"carrying information about the proposal."
        )
    if quality.short:
        quality.warnings.append(
            f"adjudication_quality_warning: {quality.short} adjudication(s) took under "
            f"{SHORT_ADJUDICATION_MINUTES} minutes"
        )
    if quality.sources_unchecked:
        quality.warnings.append(
            f"adjudication_quality_warning: {quality.sources_unchecked} acceptance(s) "
            "recorded without the critical sources being checked"
        )
    return quality


# --------------------------------------------------------------------------
# False alarms
# --------------------------------------------------------------------------

@dataclass
class FalseAlarms:
    window_days: int
    reviews_triggered: int = 0
    measurement_error: int = 0
    decision_irrelevant: int = 0
    thesis_changed: int = 0
    unresolved: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def false_alarm_rate(self) -> float:
        useful = self.measurement_error + self.decision_irrelevant
        return useful / self.reviews_triggered if self.reviews_triggered else 0.0


def false_alarms(
    transitions: Sequence[Mapping[str, Any]], *, as_of: str, window_days: int = 365
) -> FalseAlarms:
    """How often the monitoring cried wolf, and what kind of wolf it was.

    A breach that turned out to be a restated metric is a measurement error: the
    rule needs fixing. A breach that was real but changed no decision is a
    threshold set too tight. Both are calibration information, and neither is
    visible without asking the owner to say which it was.
    """
    report = FalseAlarms(window_days=window_days)
    cutoff = (date.fromisoformat(as_of) -
              __import__("datetime").timedelta(days=window_days)).isoformat()

    entered = [t for t in transitions
               if t.get("to_status") == "review_required" and t["effective_date"] >= cutoff]
    report.reviews_triggered = len(entered)

    for transition in transitions:
        if transition.get("from_status") != "review_required":
            continue
        if transition["effective_date"] < cutoff:
            continue
        resolution = transition.get("resolution")
        if resolution == "measurement_error":
            report.measurement_error += 1
        elif resolution == "decision_irrelevant_breach":
            report.decision_irrelevant += 1
        elif resolution:
            report.thesis_changed += 1
        else:
            report.unresolved += 1

    low, high = FALSE_ALARM_TARGET
    if report.reviews_triggered > high:
        report.warnings.append(
            f"calibration: {report.reviews_triggered} reviews triggered in {window_days} days "
            f"against a target band of {low}-{high}. The contract may be measuring noise."
        )
    elif report.reviews_triggered < low and window_days >= 365:
        report.warnings.append(
            f"calibration: only {report.reviews_triggered} reviews triggered in "
            f"{window_days} days against a target band of {low}-{high}. "
            "Thresholds this loose may be measuring nothing."
        )
    if report.unresolved:
        report.warnings.append(
            f"{report.unresolved} resolved review(s) carry no cause. Without it the "
            "thresholds cannot be calibrated."
        )
    return report
