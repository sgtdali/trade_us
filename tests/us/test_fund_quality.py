"""Monitoring liveness and adjudication quality.

Both of the things measured here fail silently by construction. A contract
whose rules stopped being evaluable produces silence, and silence looks exactly
like a healthy thesis; an owner clicking Accept produces an audit trail that
looks exactly like careful judgement.
"""

from __future__ import annotations

import json

import pytest

from adapter.fund import cli, quality, store, thesis as thesis_module
from adapter.fund.quality import BLIND, DEGRADED, HEALTHY


def rule(rule_id="gross_margin_floor"):
    return {"rule_id": rule_id, "metric_id": "gross_margin", "period_basis": "ttm",
            "test_type": "absolute_value", "operator": "lt", "threshold": "0.55"}


def check(rule_id="gross_margin_floor", result="not_breached", at="2026-11-05T00:00:00Z"):
    return {"rule_id": rule_id, "result": result, "evaluated_at": at}


# -------------------------------------------------------------- coverage

def test_a_thesis_with_no_contract_is_blind():
    coverage = quality.coverage_for("THS-a", contract=None, check_records=[], evidence_seen=0)
    assert coverage.state == BLIND
    assert "nothing is watching" in coverage.detail
    assert coverage.blocks_new_risk


def test_a_qualitatively_monitored_thesis_is_not_blind():
    """A condition no catalog metric captures honestly stays qualitative."""
    coverage = quality.coverage_for(
        "THS-a", contract={"mechanical_rules": [], "qualitative_checks": [{"check_id": "x"}]},
        check_records=[], evidence_seen=3)
    assert coverage.state == HEALTHY


def test_no_evidence_yet_is_not_a_failure():
    coverage = quality.coverage_for("THS-a", contract={"mechanical_rules": [rule()]},
                                    check_records=[], evidence_seen=0)
    assert coverage.state == HEALTHY


def test_evidence_arrived_and_nothing_ran_is_degraded():
    coverage = quality.coverage_for("THS-a", contract={"mechanical_rules": [rule()]},
                                    check_records=[], evidence_seen=2)
    assert coverage.state == DEGRADED
    assert "no rule was evaluated" in coverage.detail


def test_one_unavailable_check_is_degraded_not_blind():
    """A single late quarter is not a rule that has stopped working."""
    coverage = quality.coverage_for(
        "THS-a", contract={"mechanical_rules": [rule()]},
        check_records=[check(result="not_breached", at="2026-08-05T00:00:00Z"),
                       check(result="unavailable", at="2026-11-05T00:00:00Z")],
        evidence_seen=2)
    assert coverage.state == DEGRADED


def test_two_consecutive_unavailable_checks_are_blind():
    coverage = quality.coverage_for(
        "THS-a", contract={"mechanical_rules": [rule()]},
        check_records=[check(result="unavailable", at="2026-08-05T00:00:00Z"),
                       check(result="unavailable", at="2026-11-05T00:00:00Z")],
        evidence_seen=2)
    assert coverage.state == BLIND
    assert coverage.blocks_new_risk
    assert coverage.unavailable_rules == ("gross_margin_floor",)


def test_a_recovered_rule_is_healthy_again():
    coverage = quality.coverage_for(
        "THS-a", contract={"mechanical_rules": [rule()]},
        check_records=[check(result="unavailable", at="2026-05-05T00:00:00Z"),
                       check(result="unavailable", at="2026-08-05T00:00:00Z"),
                       check(result="breached", at="2026-11-05T00:00:00Z")],
        evidence_seen=3)
    assert coverage.state == HEALTHY


def test_a_breached_rule_still_counts_as_watched():
    """breached means the monitoring worked, not that it failed."""
    coverage = quality.coverage_for(
        "THS-a", contract={"mechanical_rules": [rule()]},
        check_records=[check(result="breached")], evidence_seen=1)
    assert coverage.state == HEALTHY


def test_one_blind_rule_makes_the_thesis_blind():
    coverage = quality.coverage_for(
        "THS-a", contract={"mechanical_rules": [rule("a"), rule("b")]},
        check_records=[check("a", "not_breached", "2026-11-05T00:00:00Z"),
                       check("b", "unavailable", "2026-08-05T00:00:00Z"),
                       check("b", "unavailable", "2026-11-05T00:00:00Z")],
        evidence_seen=2)
    assert coverage.state == BLIND
    assert coverage.unavailable_rules == ("b",)


# ---------------------------------------------------- adjudication quality

def job(outcome="accepted", assessment_id="ASM-1", minutes=None, proposal=None):
    document = {
        "job_id": f"JOB-{outcome}-{assessment_id}",
        "adjudication": {"outcome": outcome, "adjudicated_at": "2026-11-05T00:00:00Z",
                         "assessment_id": assessment_id},
        "result": {"proposed_assessment": proposal or {
            "readiness": "starter",
            "downside": {"status": "known", "return_fraction": "-0.3", "scenario": "s"}}},
    }
    if minutes is not None:
        document["adjudication"]["minutes_spent"] = minutes
    return document


def assessment(assessment_id="ASM-1", readiness="starter", downside_fraction="-0.3",
               sources_checked=True):
    return {
        "assessment_id": assessment_id,
        "readiness": readiness,
        "downside": {"status": "known", "return_fraction": downside_fraction, "scenario": "s"},
        "acceptance": {"critical_sources_checked": sources_checked},
    }


def test_accepting_everything_unchanged_is_flagged():
    jobs_list = [job(assessment_id=f"ASM-{n}") for n in range(6)]
    assessments = {f"ASM-{n}": assessment(f"ASM-{n}") for n in range(6)}
    report = quality.adjudication_quality(jobs_list, assessments)

    assert report.accepted_unchanged == 6
    assert report.unchanged_share == 1.0
    assert any("stopped carrying information" in w for w in report.warnings)


def test_a_mixed_record_is_not_flagged():
    jobs_list = [job(assessment_id=f"ASM-{n}") for n in range(4)]
    jobs_list.append(job(outcome="rejected", assessment_id="ASM-4"))
    jobs_list.append(job(outcome="human_authored_replacement", assessment_id="ASM-5"))
    assessments = {f"ASM-{n}": assessment(f"ASM-{n}") for n in range(4)}
    assessments["ASM-5"] = assessment("ASM-5", readiness="watchlist")

    report = quality.adjudication_quality(jobs_list, assessments)
    assert report.rejected == 1
    assert report.replaced == 1
    assert not any("stopped carrying" in w for w in report.warnings)


def test_a_very_short_adjudication_is_flagged():
    report = quality.adjudication_quality([job(minutes=1)], {"ASM-1": assessment()})
    assert report.short == 1
    assert any("under 3 minutes" in w for w in report.warnings)


def test_accepting_without_opening_the_sources_is_flagged():
    report = quality.adjudication_quality(
        [job()], {"ASM-1": assessment(sources_checked=False)})
    assert report.sources_unchecked == 1
    assert any("without the critical sources" in w for w in report.warnings)


def test_a_deferral_is_not_an_adjudication():
    report = quality.adjudication_quality([job(outcome="deferred")], {})
    assert report.total == 0


def test_changing_the_readiness_is_not_accepting_unchanged():
    report = quality.adjudication_quality(
        [job()], {"ASM-1": assessment(readiness="core")})
    assert report.accepted_unchanged == 0


# ------------------------------------------------------------ false alarms

def transition(to_status="review_required", from_status="active", resolution=None,
               effective_date="2026-11-05"):
    document = {"from_status": from_status, "to_status": to_status,
                "effective_date": effective_date}
    if resolution:
        document["resolution"] = resolution
    return document


def test_reviews_are_counted_against_the_target_band():
    report = quality.false_alarms([transition() for _ in range(6)], as_of="2026-12-31")
    assert report.reviews_triggered == 6
    assert not any("measuring noise" in w for w in report.warnings)


def test_too_many_reviews_is_a_calibration_warning():
    report = quality.false_alarms([transition() for _ in range(15)], as_of="2026-12-31")
    assert any("measuring noise" in w for w in report.warnings)


def test_too_few_reviews_is_also_a_calibration_warning():
    report = quality.false_alarms([transition()], as_of="2026-12-31")
    assert any("measuring nothing" in w for w in report.warnings)


def test_causes_are_split_by_kind():
    report = quality.false_alarms([
        transition(),
        transition(to_status="active", from_status="review_required",
                   resolution="measurement_error"),
        transition(to_status="active", from_status="review_required",
                   resolution="decision_irrelevant_breach"),
        transition(to_status="broken", from_status="review_required",
                   resolution="thesis_broken"),
    ], as_of="2026-12-31")
    assert report.measurement_error == 1
    assert report.decision_irrelevant == 1
    assert report.thesis_changed == 1


def test_a_review_resolved_with_no_cause_is_flagged():
    report = quality.false_alarms(
        [transition(to_status="active", from_status="review_required")], as_of="2026-12-31")
    assert report.unresolved == 1
    assert any("carry no cause" in w for w in report.warnings)


def test_old_transitions_fall_outside_the_window():
    report = quality.false_alarms(
        [transition(effective_date="2024-01-01") for _ in range(20)],
        as_of="2026-12-31", window_days=365)
    assert report.reviews_triggered == 0


# ------------------------------------------------------------------- CLI

@pytest.fixture()
def fund(tmp_path):
    prefix = ["--ledger", str(tmp_path / "ledger.sqlite3"),
              "--instruments", str(tmp_path / "instruments.json")]

    def run(*argv: str) -> int:
        return cli.main(prefix + list(argv))

    run.tmp_path = tmp_path  # type: ignore[attr-defined]
    run("init")
    run("instrument", "add", "--ticker", "NVDA", "--name", "NVIDIA Corporation")
    run("assess", "NVDA", "--summary", "Pricing power holds", "--readiness", "starter",
        "--downside", "-0.30", "--downside-scenario", "Margin compresses",
        "--evidence-date", "2026-08-16", "--review-due", "2026-11-15", "--as-of", "2026-08-16")
    run("thesis", "open", "NVDA", "--as-of", "2026-08-16")

    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({
        "version": 1, "effective_from": "2026-08-16",
        "mechanical_rules": [rule()], "qualitative_checks": [],
    }), encoding="utf-8")
    ledger = store.open_ledger(path=tmp_path / "ledger.sqlite3")
    thesis_id = next(iter(thesis_module.project(ledger.thesis_events())))
    run("thesis", "contract", thesis_id, "--from", str(contract))
    run.thesis_id = thesis_id  # type: ignore[attr-defined]
    return run


def unavailable_observations(tmp_path, name):
    path = tmp_path / name
    path.write_text(json.dumps({"observations": []}), encoding="utf-8")
    return str(path)


def test_quality_reports_a_healthy_thesis(fund, tmp_path, capsys):
    capsys.readouterr()
    assert fund("quality", "--as-of", "2026-11-05") == 0
    output = capsys.readouterr().out
    assert "MONITORING COVERAGE" in output
    assert "DISPATCH" in output
    assert "ADJUDICATION" in output
    assert "FALSE ALARMS" in output


def test_two_unavailable_checks_show_up_as_blind(fund, tmp_path, capsys):
    for n, accession in enumerate(("acc-1", "acc-2")):
        fund("check", fund.thesis_id, "--observations",
             unavailable_observations(tmp_path, f"obs-{n}.json"),
             "--accession", accession, "--as-of", f"2026-1{n}-05")

    capsys.readouterr()
    fund("quality", "--as-of", "2026-11-05")
    output = capsys.readouterr().out
    assert "BLIND" in output
    assert "new risk should not be increased" in output


def test_a_rule_that_never_fired_is_named(fund, capsys):
    capsys.readouterr()
    fund("quality", "--as-of", "2026-11-05")
    assert "never fired" in capsys.readouterr().out


def test_the_resolution_reaches_the_false_alarm_report(fund, capsys):
    fund("thesis", "status", fund.thesis_id, "--to", "review_required",
         "--reason", "margin miss", "--as-of", "2026-11-01")
    fund("thesis", "status", fund.thesis_id, "--to", "active",
         "--reason", "one-off inventory charge",
         "--resolution", "decision_irrelevant_breach", "--as-of", "2026-11-05")

    capsys.readouterr()
    fund("quality", "--as-of", "2026-12-31")
    output = capsys.readouterr().out
    assert "real but irrelevant       1" in output.replace("  ", "  ")
