"""Research jobs, the queue, and adjudication.

The adjudication tests are mostly about refusals: no bulk approve, no default
Accept, no silent correction of a number, and no capital figure anywhere on the
screen.
"""

from __future__ import annotations

import json

import pytest

from adapter.fund import cli, jobs, store, thesis as thesis_module


@pytest.fixture()
def fund(tmp_path):
    prefix = ["--ledger", str(tmp_path / "ledger.sqlite3"),
              "--instruments", str(tmp_path / "instruments.json")]

    def run(*argv: str) -> int:
        return cli.main(prefix + list(argv))

    run.tmp_path = tmp_path  # type: ignore[attr-defined]
    run("init")
    run("instrument", "add", "--ticker", "NVDA", "--name", "NVIDIA Corporation")
    run("open", "cash", "--amount", "100000", "--date", "2026-08-01")
    run("assess", "NVDA", "--summary", "Pricing power holds through the cycle",
        "--readiness", "starter", "--downside", "-0.30",
        "--downside-scenario", "Competition compresses the margin",
        "--evidence-date", "2026-08-16", "--review-due", "2026-11-15",
        "--as-of", "2026-08-16")
    run("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    return run


def ledger_of(fund):
    return store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")


def proposal_file(tmp_path, **overrides):
    document = {
        "thesis_summary": "Pricing power held through Q3; mix is the swing factor",
        "readiness": "starter",
        "downside": {"status": "known", "return_fraction": "-0.28",
                     "scenario": "Mix shift persists and the multiple compresses"},
        "evidence_date": "2026-11-01",
        "review_due": "2027-02-15",
        "sources": ["10-Q 2026-11-01 p.14", "earnings call transcript"],
    }
    document.update(overrides)
    path = tmp_path / "proposal.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


def open_job(fund, **overrides):
    args = {
        "--security": "NVDA",
        "--observation": "new_periodic_filing",
        "--recipe": "deep_dive_then_tracker",
        "--mode": "update_against_prior",
        "--accession": "0001045810-26-000123",
    }
    args.update(overrides)
    flat = []
    for key, value in args.items():
        flat.extend([key, value])
    return fund("job", "open", "--thesis", *flat)


def latest_job(fund):
    return ledger_of(fund).jobs()[-1]


# ---------------------------------------------------------------- dedup

def test_the_same_evidence_opens_one_job(fund, capsys):
    assert open_job(fund) == 0
    capsys.readouterr()
    assert open_job(fund) == 0
    output = capsys.readouterr().out
    assert "already open" in output
    assert "same piece of work" in output
    assert len(ledger_of(fund).jobs()) == 1


def test_a_different_filing_opens_a_new_job(fund):
    open_job(fund)
    open_job(fund, **{"--accession": "0001045810-27-000001"})
    assert len(ledger_of(fund).jobs()) == 2


def test_the_dedup_key_is_built_from_the_evidence_not_the_moment():
    first = jobs.dedup_key(observation="new_periodic_filing", security_id="sec:nvda",
                           thesis_id="THS-a", evidence_accession="acc-1",
                           monitoring_contract_version=1)
    second = jobs.dedup_key(observation="new_periodic_filing", security_id="sec:nvda",
                            thesis_id="THS-a", evidence_accession="acc-1",
                            monitoring_contract_version=1)
    assert first == second


def test_a_new_contract_version_is_new_work():
    """A rethought contract judged against the same filing is a different question."""
    first = jobs.dedup_key(observation="mechanical_breach", security_id="sec:nvda",
                           thesis_id="THS-a", evidence_accession="acc-1",
                           monitoring_contract_version=1)
    second = jobs.dedup_key(observation="mechanical_breach", security_id="sec:nvda",
                            thesis_id="THS-a", evidence_accession="acc-1",
                            monitoring_contract_version=2)
    assert first != second


def test_several_observations_about_one_thesis_merge_into_one_trigger():
    merged = jobs.merge_triggers([
        {"observation": "new_periodic_filing", "observed_at": "2026-11-01T00:00:00Z",
         "evidence_accession": "acc-1"},
        {"observation": "mechanical_breach", "observed_at": "2026-11-01T01:00:00Z",
         "breached_rule_ids": ["gross_margin_floor"]},
        {"observation": "review_due", "observed_at": "2026-11-01T02:00:00Z",
         "review_due": "2026-11-01"},
    ])
    assert merged["evidence_accession"] == "acc-1"
    assert merged["breached_rule_ids"] == ["gross_margin_floor"]
    assert merged["review_due"] == "2026-11-01"
    assert "merged 3 observations" in merged["detail"]


# ---------------------------------------------------------------- retry

def test_a_failed_attempt_is_retried_within_budget(fund, capsys):
    open_job(fund)
    job_id = latest_job(fund)["job_id"]
    capsys.readouterr()
    assert fund("job", "fail", job_id, "--error-class", "data_source_error",
                "--detail", "SEC returned 503") == 0
    output = capsys.readouterr().out
    assert "attempt 1 of at most 3" in output
    assert "automatic retry stopped" not in output


def test_automatic_retry_stops_after_three_attempts(fund, capsys):
    open_job(fund)
    job_id = latest_job(fund)["job_id"]
    for _ in range(3):
        fund("job", "fail", job_id, "--error-class", "data_source_error", "--detail", "503")
    assert jobs.stopped(latest_job(fund))

    capsys.readouterr()
    fund("inbox", "--as-of", "2026-11-05")
    assert "Q0 -- BLOCKING" in capsys.readouterr().out


def test_a_stopped_job_refuses_to_start_again():
    document = jobs.new_job(trigger_snapshot={"observation": "review_due",
                                              "observed_at": "2026-11-01T00:00:00Z"},
                            rule_id="manual", rule_version=1, recipe="tracker",
                            assessment_mode="update_against_prior", security_id="sec:nvda",
                            dedup_key_value="k")
    for _ in range(3):
        document = jobs.fail_attempt(document, error_class="data_source_error", detail="503")
    with pytest.raises(jobs.JobError, match="needs a human"):
        jobs.start_attempt(document)


def test_a_contract_error_has_a_shorter_budget():
    document = jobs.new_job(trigger_snapshot={"observation": "review_due",
                                              "observed_at": "2026-11-01T00:00:00Z"},
                            rule_id="manual", rule_version=1, recipe="tracker",
                            assessment_mode="update_against_prior", security_id="sec:nvda",
                            dedup_key_value="k")
    document = jobs.fail_attempt(document, error_class="contract_error",
                                 detail="schema failed")
    assert not jobs.stopped(document)
    document = jobs.fail_attempt(document, error_class="contract_error",
                                 detail="schema failed again")
    assert jobs.stopped(document)
    assert document["status"] == jobs.CONTRACT_FAILED


def test_a_result_that_fails_its_contract_is_never_offered(fund, tmp_path, capsys):
    open_job(fund)
    job_id = latest_job(fund)["job_id"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"readiness": "wildly_confident"}), encoding="utf-8")

    capsys.readouterr()
    assert fund("job", "result", job_id, "--artifact", "runs/nvda/result.md",
                "--proposal", str(bad)) == 2
    assert "will not be put in front of you" in capsys.readouterr().err
    assert latest_job(fund)["status"] == jobs.CONTRACT_FAILED


def test_job_revisions_are_immutable(fund):
    import sqlite3

    open_job(fund)
    with ledger_of(fund).connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE research_job SET status = 'adjudicated'")
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute("DELETE FROM research_job")


def test_every_revision_is_kept(fund, tmp_path):
    open_job(fund)
    job_id = latest_job(fund)["job_id"]
    fund("job", "fail", job_id, "--error-class", "skill_transport_error", "--detail", "timeout")
    fund("job", "result", job_id, "--artifact", "runs/nvda/result.md",
         "--proposal", proposal_file(tmp_path))
    revisions = ledger_of(fund).job_revisions(job_id)
    assert [r["status"] for r in revisions] == [jobs.PENDING, jobs.FAILED,
                                                jobs.AWAITING_ADJUDICATION]


# ---------------------------------------------------------------- queue

def test_a_quiet_day_says_so(fund, capsys):
    capsys.readouterr()
    assert fund("inbox", "--as-of", "2026-11-05") == 0
    assert "Nothing needs you today." in capsys.readouterr().out


def test_work_waiting_shows_why_and_how_long(fund, tmp_path, capsys):
    open_job(fund)
    job_id = latest_job(fund)["job_id"]
    fund("job", "result", job_id, "--artifact", "runs/nvda/result.md",
         "--proposal", proposal_file(tmp_path))

    capsys.readouterr()
    fund("inbox", "--as-of", "2026-11-05")
    output = capsys.readouterr().out
    assert "Q1 -- NEEDS ADJUDICATION" in output
    assert "new periodic filing" in output
    assert "25 min" in output
    assert f"fund adjudicate {job_id}" in output


def test_the_queue_is_derived_not_stored(fund, tmp_path):
    open_job(fund)
    job_id = latest_job(fund)["job_id"]
    fund("job", "result", job_id, "--artifact", "r.md", "--proposal", proposal_file(tmp_path))

    ledger = ledger_of(fund)
    queue = jobs.build_queue(ledger.jobs(), as_of="2026-11-05")
    assert [item.job_id for item in queue.q1] == [job_id]

    with ledger.connection() as connection:
        tables = {row["name"] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert not any("queue" in name for name in tables)


def test_funded_positions_are_ranked_above_unfunded():
    def job(security_id, created):
        return {"job_id": f"JOB-{security_id}", "security_id": security_id,
                "status": jobs.AWAITING_ADJUDICATION, "recipe": "tracker",
                "created_at": created,
                "trigger_snapshot": {"observation": "review_due"}}

    queue = jobs.build_queue(
        [job("sec:unfunded", "2026-11-01T00:00:00Z"), job("sec:funded", "2026-11-02T00:00:00Z")],
        funded_security_ids={"sec:funded"}, as_of="2026-11-05")
    assert [item.job["security_id"] for item in queue.q1] == ["sec:funded", "sec:unfunded"]


def test_an_overdue_job_outranks_a_funded_one():
    def job(security_id, deadline=None):
        document = {"job_id": f"JOB-{security_id}", "security_id": security_id,
                    "status": jobs.AWAITING_ADJUDICATION, "recipe": "tracker",
                    "created_at": "2026-11-01T00:00:00Z",
                    "trigger_snapshot": {"observation": "review_due"}}
        if deadline:
            document["decision_deadline"] = deadline
        return document

    queue = jobs.build_queue([job("sec:funded"), job("sec:late", deadline="2026-10-01")],
                            funded_security_ids={"sec:funded"}, as_of="2026-11-05")
    assert queue.q1[0].job["security_id"] == "sec:late"


def test_q0_blocks_new_risk():
    queue = jobs.build_queue([], blind_theses={"THS-a": "two evidence periods unavailable"},
                             as_of="2026-11-05")
    assert queue.blocks_new_risk
    assert not queue.empty


# ---------------------------------------------------------- adjudication

@pytest.fixture()
def waiting(fund, tmp_path):
    open_job(fund)
    job_id = latest_job(fund)["job_id"]
    fund("job", "result", job_id, "--artifact", "runs/nvda/result.md",
         "--proposal", proposal_file(tmp_path))
    return fund, job_id


def test_the_screen_shows_the_proposal_and_records_nothing(waiting, capsys):
    fund, job_id = waiting
    capsys.readouterr()
    assert fund("adjudicate", job_id) == 0
    output = capsys.readouterr().out

    assert "ADJUDICATION" in output
    assert "-28.00%" in output
    assert "10-Q 2026-11-01 p.14" in output
    assert "AGAINST THE PREVIOUS ACCEPTED JUDGEMENT" in output
    assert "Nothing recorded" in output
    assert latest_job(fund)["status"] == jobs.AWAITING_ADJUDICATION


def test_accept_is_not_the_default(waiting, capsys):
    fund, job_id = waiting
    capsys.readouterr()
    fund("adjudicate", job_id)
    output = capsys.readouterr().out
    assert "--accept" in output and "--reject" in output
    assert len(ledger_of(fund).assessments()) == 1  # only the original


def test_no_capital_figures_reach_the_adjudication_screen(waiting, capsys):
    fund, job_id = waiting
    fund("open", "position", "--security", "NVDA", "--quantity", "100",
         "--unit-cost", "90", "--date", "2026-08-01")
    capsys.readouterr()
    fund("adjudicate", job_id)
    output = capsys.readouterr().out

    assert "Not shown: position weight, cash, P&L, average cost, capital at risk." in output
    # Scan everything except the disclaimer that names those very things.
    body = "\n".join(line for line in output.splitlines() if "Not shown" not in line)
    for forbidden in ("100000", "9,000", "weight", "NAV", "average cost", "Cash"):
        assert forbidden not in body, f"{forbidden!r} leaked into adjudication"


def test_two_outcomes_at_once_are_refused(waiting, capsys):
    fund, job_id = waiting
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--accept", "--reject", "--reason", "x") == 2
    assert "choose one outcome" in capsys.readouterr().err


def test_accepting_writes_an_assessment(waiting, capsys):
    fund, job_id = waiting
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--change-driver", "Q3 landed in line",
                "--minutes", "12", "--accept", "--as-of", "2026-11-05") == 0
    assert "accepted" in capsys.readouterr().out

    assessment = ledger_of(fund).assessments()[-1]
    assert assessment["readiness"] == "starter"
    assert assessment["downside"]["return_fraction"] == "-0.28"
    assert assessment["human_authored"] is False
    assert assessment["acceptance"]["minutes_spent"] == 12
    assert assessment["source_artifact"]["relative_path"] == "runs/nvda/result.md"
    assert latest_job(fund)["status"] == jobs.ADJUDICATED


def test_accepting_needs_to_say_what_changed(waiting, capsys):
    fund, job_id = waiting
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--accept") == 2
    assert "--change-driver is required" in capsys.readouterr().err


def test_a_material_change_needs_a_rationale(fund, tmp_path, capsys):
    open_job(fund)
    job_id = latest_job(fund)["job_id"]
    fund("job", "result", job_id, "--artifact", "r.md",
         "--proposal", proposal_file(tmp_path, readiness="core"))
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--accept", "--change-driver", "two clean quarters") == 2
    error = capsys.readouterr().err
    assert "material change" in error and "readiness starter -> core" in error


def test_rejecting_writes_no_assessment(waiting, capsys):
    fund, job_id = waiting
    before = len(ledger_of(fund).assessments())
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--reject",
                "--reason", "The margin figure is the segment, not the group") == 0
    output = capsys.readouterr().out
    assert "not silently corrected" in output
    assert len(ledger_of(fund).assessments()) == before
    assert latest_job(fund)["adjudication"]["outcome"] == "rejected"


def test_a_human_authored_replacement_links_back_to_the_proposal(waiting, capsys):
    fund, job_id = waiting
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--replace",
                "--summary", "The mix shift is structural, not cyclical",
                "--readiness", "watchlist", "--downside", "-0.45",
                "--downside-scenario", "Structural mix shift at a lower margin",
                "--change-driver", "I read the segment note differently",
                "--rationale", "Readiness down and downside wider than proposed",
                "--as-of", "2026-11-05") == 0
    assert "your judgement" in capsys.readouterr().out

    assessment = ledger_of(fund).assessments()[-1]
    assert assessment["human_authored"] is True
    assert assessment["readiness"] == "watchlist"
    assert assessment["downside"]["return_fraction"] == "-0.45"
    assert assessment["derived_from"] is not None
    assert latest_job(fund)["adjudication"]["outcome"] == "human_authored_replacement"


def test_deferring_keeps_the_job_in_the_queue(waiting, capsys):
    fund, job_id = waiting
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--defer", "--reason", "Need the transcript first") == 0
    assert "It stays in Q1." in capsys.readouterr().out
    assert latest_job(fund)["status"] == jobs.AWAITING_ADJUDICATION

    capsys.readouterr()
    fund("inbox", "--as-of", "2026-11-05")
    assert job_id in capsys.readouterr().out


def test_skipping_the_review_is_recorded_as_such(waiting, capsys):
    fund, job_id = waiting
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--acknowledge", "--change-driver", "no time today") == 0
    assert "cannot raise readiness" in capsys.readouterr().out

    assessment = ledger_of(fund).assessments()[-1]
    assert assessment["acceptance"]["mode"] == "acknowledged_without_full_adjudication"
    assert assessment["acceptance"]["critical_sources_checked"] is False


def test_accepting_without_checking_sources_is_refused(waiting, capsys):
    fund, job_id = waiting
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--accept", "--change-driver", "x",
                "--sources-not-checked") == 2
    assert "use --acknowledge instead" in capsys.readouterr().err


def test_the_would_accept_answer_is_carried_into_the_assessment(waiting):
    fund, job_id = waiting
    fund("adjudicate", job_id, "--accept", "--change-driver", "x", "--would-not-accept")
    assessment = ledger_of(fund).assessments()[-1]
    assert assessment["acceptance"]["would_accept_downside_without_position"] is False


def test_an_adjudicated_job_cannot_be_adjudicated_again(waiting, capsys):
    fund, job_id = waiting
    fund("adjudicate", job_id, "--accept", "--change-driver", "x")
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--accept", "--change-driver", "again") == 2
    assert "not awaiting adjudication" in capsys.readouterr().err


def test_accepting_links_the_assessment_to_the_thesis(waiting):
    fund, job_id = waiting
    fund("adjudicate", job_id, "--accept", "--change-driver", "Q3 in line", "--as-of", "2026-11-05")
    ledger = ledger_of(fund)
    history = next(iter(thesis_module.project(ledger.thesis_events()).values()))
    assert history.document["current_assessment_id"] == ledger.assessments()[-1]["assessment_id"]


def test_a_thesis_in_review_stays_the_owners_problem(fund, tmp_path, capsys):
    """Accepting the research does not resolve the thesis. That is a separate act."""
    ledger = ledger_of(fund)
    history = next(iter(thesis_module.project(ledger.thesis_events()).values()))
    fund("thesis", "status", history.thesis_id, "--to", "review_required",
         "--reason", "Q3 miss", "--as-of", "2026-11-01")

    open_job(fund)
    job_id = latest_job(fund)["job_id"]
    fund("job", "result", job_id, "--artifact", "r.md", "--proposal", proposal_file(tmp_path))

    capsys.readouterr()
    fund("adjudicate", job_id, "--accept", "--change-driver", "read the filing",
         "--as-of", "2026-11-05")
    assert "still review_required" in capsys.readouterr().out
