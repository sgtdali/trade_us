"""The nightly cycle, its catch-up behaviour, and the heartbeat.

This is the phase where the system starts driving itself, so the tests are
mostly about the two ways that goes wrong: going quiet, and thrashing.
"""

from __future__ import annotations

import json

import pytest

from adapter.fund import cli, cycle, jobs, store, thesis as thesis_module


@pytest.fixture()
def fund(tmp_path):
    prefix = ["--ledger", str(tmp_path / "ledger.sqlite3"),
              "--instruments", str(tmp_path / "instruments.json")]

    def run(*argv: str) -> int:
        return cli.main(prefix + list(argv))

    run.tmp_path = tmp_path  # type: ignore[attr-defined]
    run("init")
    run("instrument", "add", "--ticker", "NVDA", "--name", "NVIDIA Corporation",
        "--cik", "0001045810")
    run("open", "cash", "--amount", "100000", "--date", "2026-08-01")
    run("assess", "NVDA", "--summary", "Pricing power holds",
        "--readiness", "starter", "--downside", "-0.30",
        "--downside-scenario", "Competition compresses the margin",
        "--evidence-date", "2026-08-16", "--review-due", "2026-11-15",
        "--as-of", "2026-08-16")
    run("thesis", "open", "NVDA", "--as-of", "2026-08-16")

    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({
        "version": 1, "effective_from": "2026-08-16",
        "mechanical_rules": [],
        "qualitative_checks": [{
            "check_id": "customer_concentration",
            "question": "Has the top-two customer share moved materially?",
            "review_on": ["review_due"], "review_due": "2027-01-01",
        }],
    }), encoding="utf-8")
    ledger = store.open_ledger(path=tmp_path / "ledger.sqlite3")
    thesis_id = next(iter(thesis_module.project(ledger.thesis_events())))
    run("thesis", "contract", thesis_id, "--from", str(contract))
    run.thesis_id = thesis_id  # type: ignore[attr-defined]
    return run


def ledger_of(fund):
    return store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")


def filings_file(tmp_path, entries, name="filings.json"):
    path = tmp_path / name
    path.write_text(json.dumps({"NVDA": entries}), encoding="utf-8")
    return str(path)


def one_filing(tmp_path, accession="0001045810-26-000123", filing_date="2026-11-01"):
    return filings_file(tmp_path, [{
        "accession": accession, "form": "10-Q",
        "filing_date": filing_date, "report_date": "2026-09-30"}])


def sidecars(tmp_path):
    path = tmp_path / "sidecars.json"
    path.write_text(json.dumps({
        "earnings-deep-dive": {
            "sidecar_version": 1, "skill": "earnings-deep-dive",
            "findings": [{"statement": "Margin held", "direction": "supports",
                          "source": "10-Q p.14"}],
        },
        "thesis-tracker": {
            "sidecar_version": 1, "skill": "thesis-tracker",
            "findings": [{"statement": "Pillar intact", "direction": "supports",
                          "source": "10-Q p.14"}],
            "proposed_assessment": {
                "thesis_summary": "Pricing power held", "readiness": "starter",
                "downside": {"status": "known", "return_fraction": "-0.28",
                             "scenario": "Mix shift persists"},
                "evidence_date": "2026-11-01", "review_due": "2027-02-15"},
        },
    }), encoding="utf-8")
    return str(path)


# ------------------------------------------------------------- the cycle

def test_a_cycle_observes_opens_and_runs(fund, tmp_path, capsys):
    capsys.readouterr()
    assert fund("research-cycle", "--filings", one_filing(tmp_path),
                "--stub", sidecars(tmp_path), "--as-of", "2026-11-05") == 0
    output = capsys.readouterr().out

    assert "CYCLE" in output
    assert "opened" in output
    assert "1 opened, 1 run" in output

    job = ledger_of(fund).jobs()[-1]
    assert job["status"] == jobs.AWAITING_ADJUDICATION
    assert job["rule_id"] == "new_filing_open_thesis"


def test_a_second_cycle_over_the_same_evidence_opens_nothing(fund, tmp_path, capsys):
    fund("research-cycle", "--filings", one_filing(tmp_path), "--stub", sidecars(tmp_path),
         "--as-of", "2026-11-05")
    capsys.readouterr()
    fund("research-cycle", "--filings", one_filing(tmp_path), "--stub", sidecars(tmp_path),
         "--as-of", "2026-11-06")
    output = capsys.readouterr().out
    assert "0 opened" in output
    assert len(ledger_of(fund).jobs()) == 1


def test_the_cycle_can_observe_without_running(fund, tmp_path, capsys):
    capsys.readouterr()
    fund("research-cycle", "--filings", one_filing(tmp_path), "--observe-only",
         "--as-of", "2026-11-05")
    assert "1 opened, 0 run" in capsys.readouterr().out
    assert ledger_of(fund).jobs()[-1]["status"] == jobs.PENDING


def test_a_due_review_is_observed_even_with_no_new_evidence(fund, tmp_path, capsys):
    """The observation is made. Dispatching it is F8.1's rule, not F6's."""
    capsys.readouterr()
    fund("research-cycle", "--filings", filings_file(tmp_path, []), "--observe-only",
         "--as-of", "2027-02-01")
    output = capsys.readouterr().out
    assert "1 observation(s)" in output
    assert "0 opened" in output


def test_one_job_failing_does_not_fail_the_cycle(fund, tmp_path, capsys):
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"earnings-deep-dive": {"sidecar_version": 1}}),
                      encoding="utf-8")
    capsys.readouterr()
    assert fund("research-cycle", "--filings", one_filing(tmp_path),
                "--stub", str(broken), "--as-of", "2026-11-05") == 0
    output = capsys.readouterr().out
    assert "1 failed" in output
    assert ledger_of(fund).cycle_runs()[-1]["status"] == "succeeded"


def test_a_job_whose_retry_budget_is_spent_is_not_attempted_again(fund, tmp_path):
    fund("research-cycle", "--filings", one_filing(tmp_path), "--observe-only",
         "--as-of", "2026-11-05")
    job_id = ledger_of(fund).jobs()[-1]["job_id"]
    for _ in range(3):
        fund("job", "fail", job_id, "--error-class", "data_source_error", "--detail", "503")

    assert not cycle.runnable(ledger_of(fund).job(job_id))
    fund("research-cycle", "--filings", one_filing(tmp_path), "--stub", sidecars(tmp_path),
         "--as-of", "2026-11-06")
    assert ledger_of(fund).job(job_id)["status"] == jobs.FAILED


# ----------------------------------------------------------- catch-up

def test_a_week_switched_off_loses_nothing(fund, tmp_path, capsys):
    """The watermark is what was seen, not when we last looked."""
    entries = [
        {"accession": "0001045810-26-000101", "form": "10-Q",
         "filing_date": "2026-11-01", "report_date": "2026-09-30"},
        {"accession": "0001045810-26-000102", "form": "8-K",
         "filing_date": "2026-11-03", "report_date": "2026-11-03"},
        {"accession": "0001045810-26-000103", "form": "10-K",
         "filing_date": "2026-11-06", "report_date": "2026-09-30"},
    ]
    # Nothing ran on the 1st through the 7th. The cycle runs on the 8th.
    capsys.readouterr()
    fund("research-cycle", "--filings", filings_file(tmp_path, entries),
         "--limit", "3", "--observe-only", "--as-of", "2026-11-08")

    ledger = ledger_of(fund)
    assert len(ledger.observed_filings("sec:nvda")) == 3
    accessions = {job["trigger_snapshot"]["evidence_accession"] for job in ledger.jobs()}
    assert accessions == {e["accession"] for e in entries}


def test_the_first_run_on_a_long_history_produces_one_piece_of_work(fund, tmp_path):
    entries = [
        {"accession": f"0001045810-{year}-000001", "form": "10-K",
         "filing_date": f"20{year}-02-01", "report_date": f"20{year - 1}-12-31"}
        for year in range(10, 26)
    ]
    fund("research-cycle", "--filings", filings_file(tmp_path, entries), "--observe-only",
         "--as-of", "2026-11-05")

    ledger = ledger_of(fund)
    assert len(ledger.jobs()) == 1
    assert len(ledger.observed_filings("sec:nvda")) == 16


# ---------------------------------------------------------- heartbeat

def test_every_run_is_recorded(fund, tmp_path):
    fund("research-cycle", "--filings", one_filing(tmp_path), "--observe-only",
         "--as-of", "2026-11-05")
    runs = ledger_of(fund).cycle_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "succeeded"
    assert runs[0]["jobs_opened"] == 1


def test_a_failed_cycle_is_recorded_not_swallowed(fund, capsys):
    capsys.readouterr()
    assert fund("research-cycle", "--filings", "no-such-file.json",
                "--as-of", "2026-11-05") == 1
    assert "CYCLE FAILED" in capsys.readouterr().out
    assert ledger_of(fund).cycle_runs()[-1]["status"] == "failed"


def test_status_reports_a_healthy_cycle(fund, tmp_path, capsys):
    fund("research-cycle", "--filings", one_filing(tmp_path), "--stub", sidecars(tmp_path),
         "--as-of", "2026-11-05")
    capsys.readouterr()
    assert fund("status", "--as-of", "2026-11-05") == 0
    output = capsys.readouterr().out
    assert "succeeded" in output
    assert "Q1" in output
    assert "not healthy" not in output


def test_status_says_when_the_automation_is_not_healthy(fund, capsys):
    for _ in range(2):
        fund("research-cycle", "--filings", "missing.json", "--as-of", "2026-11-05")
    capsys.readouterr()
    fund("status", "--as-of", "2026-11-05")
    output = capsys.readouterr().out
    assert "2 consecutive failed cycles" in output
    assert "do not read a quiet inbox as good news" in output


def test_status_notices_a_cycle_that_stopped_running(fund, tmp_path, capsys):
    fund("research-cycle", "--filings", one_filing(tmp_path), "--observe-only",
         "--as-of", "2026-11-05")
    capsys.readouterr()
    fund("status", "--as-of", "2026-11-20")
    assert "no cycle for 15 days" in capsys.readouterr().out


def test_status_before_the_first_run(fund, capsys):
    capsys.readouterr()
    fund("status", "--as-of", "2026-11-05")
    assert "never run" in capsys.readouterr().out


@pytest.mark.parametrize("runs,expected_healthy", [
    ([], False),
    ([{"started_at": "2026-11-05T03:30:00Z", "status": "succeeded"}], True),
    ([{"started_at": "2026-11-05T03:30:00Z", "status": "failed"}], False),
    ([{"started_at": "2026-11-04T03:30:00Z", "status": "failed"},
      {"started_at": "2026-11-05T03:30:00Z", "status": "succeeded"}], True),
])
def test_heartbeat_health(runs, expected_healthy):
    beat = cycle.heartbeat_from(runs, as_of="2026-11-05")
    assert beat.healthy is expected_healthy


# ------------------------------------------------------------ scheduling

def test_the_schedule_command_prints_the_registration(fund, capsys):
    capsys.readouterr()
    assert fund("schedule", "--at", "03:30") == 0
    output = capsys.readouterr().out
    assert "schtasks /Create" in output
    assert "research-cycle" in output
    assert "StartWhenAvailable" in output
    assert "quiet market" in output


# ----------------------------------------------------------- planning

def test_several_observations_about_one_thesis_become_one_job():
    class _History:
        status = thesis_module.ACTIVE
        document = {"thesis_id": "THS-a", "security_id": "sec:nvda", "status": "active"}

    planned, duplicates = cycle.plan_work(
        [
            {"observation": "new_periodic_filing", "observed_at": "2026-11-01T00:00:00Z",
             "evidence_accession": "acc-1", "_security_id": "sec:nvda", "_thesis_id": "THS-a"},
            {"observation": "new_periodic_filing", "observed_at": "2026-11-01T01:00:00Z",
             "evidence_accession": "acc-1", "_security_id": "sec:nvda", "_thesis_id": "THS-a"},
        ],
        theses={"THS-a": _History()},
        already_open=lambda key: False,
    )
    assert len(planned) == 1
    assert duplicates == 0


def test_work_already_open_is_counted_not_reopened():
    class _History:
        status = thesis_module.ACTIVE
        document = {"thesis_id": "THS-a", "security_id": "sec:nvda", "status": "active"}

    planned, duplicates = cycle.plan_work(
        [{"observation": "new_periodic_filing", "observed_at": "2026-11-01T00:00:00Z",
          "evidence_accession": "acc-1", "_security_id": "sec:nvda", "_thesis_id": "THS-a"}],
        theses={"THS-a": _History()},
        already_open=lambda key: True,
    )
    assert planned == []
    assert duplicates == 1


def test_an_observation_with_no_matching_rule_is_dropped_quietly():
    planned, duplicates = cycle.plan_work(
        [{"observation": "price_shock", "observed_at": "2026-11-01T00:00:00Z",
          "_security_id": "sec:nvda", "_thesis_id": None}],
        theses={}, already_open=lambda key: False)
    assert planned == [] and duplicates == 0
