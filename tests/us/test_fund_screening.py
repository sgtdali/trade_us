"""Discovery: rate limits, and what the screen is not allowed to know.

The screen must not be told which names we hold or believe in. The cheapest way
for a model to look insightful is to agree with the person asking, so the
duplicate filter runs afterwards, on the output, never on the input.
"""

from __future__ import annotations

import json

import pytest

from adapter.fund import cli, dispatch, schemas, screening, store, thesis as thesis_module


def decision(**overrides):
    kwargs = {
        "as_of": "2026-11-05",
        "last_discovery": None,
        "open_candidates": 0,
        "open_positions": 3,
        "max_active_positions": 10,
    }
    kwargs.update(overrides)
    return screening.should_run(**kwargs)


# ------------------------------------------------------------ rate limits

def test_the_first_screen_runs():
    assert decision().should_run


def test_a_screen_waits_for_its_interval():
    assert not decision(last_discovery="2026-11-01").should_run
    assert decision(last_discovery="2026-10-01").should_run


def test_candidates_waiting_stop_the_screen():
    """A candidate not yet underwritten is a reason not to raise another."""
    result = decision(open_candidates=3, max_open_candidates=3)
    assert not result.should_run
    assert "already waiting to be underwritten" in result.reason


def test_a_full_book_widens_the_interval_rather_than_stopping():
    """A better idea can still displace a weaker one -- just not weekly."""
    full = decision(last_discovery="2026-10-15", open_positions=10, max_active_positions=10)
    assert not full.should_run
    assert "interval widened" not in full.reason  # not due yet either way

    later = decision(as_of="2026-12-20", last_discovery="2026-10-15",
                     open_positions=10, max_active_positions=10)
    assert later.should_run
    assert "book full" in later.reason


def test_a_book_with_room_uses_the_normal_interval():
    result = decision(as_of="2026-11-05", last_discovery="2026-10-01", open_positions=3)
    assert result.should_run
    assert "book full" not in result.reason


def test_open_candidates_are_counted_from_jobs():
    jobs = [
        {"recipe": "idea_generation", "status": "awaiting_adjudication",
         "security_id": "sec:a"},
        {"recipe": "onboarding_underwrite", "status": "pending", "security_id": "sec:b"},
        {"recipe": "onboarding_underwrite", "status": "adjudicated", "security_id": "sec:c"},
        {"recipe": "onboarding_underwrite", "status": "adjudicated", "security_id": "sec:d"},
        {"recipe": "tracker", "status": "awaiting_adjudication", "security_id": "sec:e"},
    ]
    # sec:c became a thesis; sec:d did not, so it is still an open question.
    assert screening.count_open_candidates(jobs, theses_by_security={"sec:c": object()}) == 3


# ------------------------------------------------------- what it may see

def test_the_screening_pack_says_nothing_about_us():
    pack = screening.build_universe_pack(
        job={"job_id": "JOB-x"}, universe=["AAPL", "MSFT", "NVDA"], universe_id="us60")

    # The instructions name these things in order to forbid them, so scan the
    # data the screen is given rather than the words telling it what not to do.
    data = json.dumps({k: v for k, v in pack.items() if k != "instructions"}).lower()
    for forbidden in ("thesis", "position", "weight", "nav", "cash", "readiness",
                      "held", "portfolio"):
        assert forbidden not in data, forbidden
    assert pack["universe"] == ["AAPL", "MSFT", "NVDA"]
    assert pack["assessment_mode"] == "de_novo"


def test_the_pack_tells_the_screen_not_to_judge_capital():
    pack = screening.build_universe_pack(
        job={"job_id": "JOB-x"}, universe=["AAPL"], universe_id="us60")
    instructions = " ".join(pack["instructions"])
    assert "Do not produce a readiness" in instructions
    assert "Kill weak ideas aggressively" in instructions


def test_duplicates_are_filtered_after_the_screen_not_before():
    kept, dropped = screening.filter_candidates(
        [{"ticker": "NVDA", "reason": "a"}, {"ticker": "AMD", "reason": "b"}],
        known_tickers={"NVDA"}, limit=5)
    assert [c.ticker for c in kept] == ["AMD"]
    assert dropped == ["NVDA"]


def test_the_candidate_list_is_capped():
    kept, dropped = screening.filter_candidates(
        [{"ticker": t, "reason": "r"} for t in ("A", "B", "C", "D")],
        known_tickers=set(), limit=2)
    assert len(kept) == 2
    assert dropped == ["C", "D"]


# ---------------------------------------------------------- the contract

def test_a_screen_may_not_propose_a_judgement():
    sidecar = {
        "sidecar_version": 1, "skill": "idea-generation", "security_id": "sec:nvda",
        "produced_at": "2026-11-05T00:00:00Z",
        "findings": [{"statement": "cheap on normalised earnings", "direction": "neutral",
                      "source": "screen"}],
        "proposed_assessment": {
            "thesis_summary": "buy it", "readiness": "core",
            "downside": {"status": "known", "return_fraction": "-0.2", "scenario": "s"},
            "evidence_date": "2026-11-01", "review_due": "2027-02-01"},
    }
    assert schemas.schema_errors(sidecar, schemas.SKILL_OUTPUT)


def test_a_screen_output_with_only_findings_is_valid():
    sidecar = {
        "sidecar_version": 1, "skill": "idea-generation",
        "produced_at": "2026-11-05T00:00:00Z",
        "findings": [{"statement": "cheap on normalised earnings", "direction": "neutral",
                      "source": "screen"}],
    }
    assert schemas.schema_errors(sidecar, schemas.SKILL_OUTPUT) == []


def test_a_screen_may_not_name_one_security():
    """It looked at a universe. Naming a single security is a judgement in disguise."""
    sidecar = {
        "sidecar_version": 1, "skill": "idea-generation", "security_id": "sec:nvda",
        "produced_at": "2026-11-05T00:00:00Z",
        "findings": [{"statement": "cheap", "direction": "neutral", "source": "screen"}],
    }
    assert schemas.schema_errors(sidecar, schemas.SKILL_OUTPUT)


def test_every_other_skill_must_name_its_security():
    sidecar = {
        "sidecar_version": 1, "skill": "earnings-deep-dive",
        "produced_at": "2026-11-05T00:00:00Z",
        "findings": [{"statement": "x", "direction": "neutral", "source": "10-Q"}],
    }
    assert any("security_id" in message
               for message in schemas.schema_errors(sidecar, schemas.SKILL_OUTPUT))


def test_a_screening_job_carries_no_security():
    from adapter.fund import jobs

    document = jobs.new_job(
        trigger_snapshot={"observation": "periodic_discovery",
                          "observed_at": "2026-11-05T00:00:00Z"},
        rule_id="periodic_discovery", rule_version=1, recipe="idea_generation",
        assessment_mode="de_novo", security_id=None, dedup_key_value="k")
    assert "security_id" not in document
    assert schemas.schema_errors(document, schemas.RESEARCH_JOB_RECORD) == []


def test_a_non_screening_job_must_carry_a_security():
    from adapter.fund import jobs

    document = jobs.new_job(
        trigger_snapshot={"observation": "review_due", "observed_at": "2026-11-05T00:00:00Z"},
        rule_id="review_due_open_thesis", rule_version=1, recipe="tracker",
        assessment_mode="update_against_prior", security_id=None, dedup_key_value="k")
    assert any("security_id" in message
               for message in schemas.schema_errors(document, schemas.RESEARCH_JOB_RECORD))


# ------------------------------------------------------------------- CLI

@pytest.fixture()
def fund(tmp_path):
    prefix = ["--ledger", str(tmp_path / "ledger.sqlite3"),
              "--instruments", str(tmp_path / "instruments.json")]

    def run(*argv: str) -> int:
        return cli.main(prefix + list(argv))

    run.tmp_path = tmp_path  # type: ignore[attr-defined]
    run("init")
    return run


def test_discovery_reports_that_it_is_off(fund, capsys):
    capsys.readouterr()
    assert fund("discovery") == 0
    output = capsys.readouterr().out
    assert "enabled               no" in output
    assert "not looking at what is already there" in output


def test_a_switched_off_rule_dispatches_nothing():
    assert dispatch.match("periodic_discovery", has_open_thesis=False) is None


def test_switching_it_on_is_a_config_change_not_a_code_change():
    tuned = dispatch.apply_tuning(
        dispatch.RULES, {"rules": {"periodic_discovery": {"enabled": True}}})
    by_id = {rule.rule_id: rule for rule in tuned}
    assert by_id["periodic_discovery"].enabled is True
    assert by_id["periodic_discovery"].recipe == "idea_generation"


# ------------------------------------------------- the screening run path

def screen_sidecar(tmp_path):
    path = tmp_path / "sidecars.json"
    path.write_text(json.dumps({"idea-generation": {
        "sidecar_version": 1,
        "skill": "idea-generation",
        "findings": [
            {"statement": "ABBV: FCF yield 8% against a stable pipeline",
             "direction": "neutral", "source": "screen"},
            {"statement": "CAT: order book turned after two soft quarters",
             "direction": "neutral", "source": "screen"},
        ],
        "open_questions": ["Neither has been underwritten"],
    }}), encoding="utf-8")
    return str(path)


def test_a_screen_can_be_opened_without_a_security(fund, capsys):
    capsys.readouterr()
    assert fund("job", "open", "--observation", "periodic_discovery",
                "--recipe", "idea_generation", "--mode", "de_novo",
                "--universe", "us60", "--as-of", "2026-08-16") == 0
    assert "screen of us60" in capsys.readouterr().out

    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    job = ledger.jobs()[-1]
    assert "security_id" not in job
    assert job["recipe"] == "idea_generation"


def test_pointing_a_screen_at_one_name_is_refused(fund, capsys):
    fund("instrument", "add", "--ticker", "NVDA", "--name", "NVIDIA Corporation")
    capsys.readouterr()
    assert fund("job", "open", "--security", "NVDA", "--observation", "periodic_discovery",
                "--recipe", "idea_generation", "--mode", "de_novo") == 2
    assert "not screening" in capsys.readouterr().err


def test_a_screen_runs_end_to_end(fund, tmp_path, capsys):
    fund("job", "open", "--observation", "periodic_discovery", "--recipe", "idea_generation",
         "--mode", "de_novo", "--universe", "us60", "--as-of", "2026-08-16")
    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    job_id = ledger.jobs()[-1]["job_id"]

    capsys.readouterr()
    assert fund("run", job_id, "--stub", screen_sidecar(tmp_path),
                "--workdir", str(tmp_path / "run"), "--as-of", "2026-08-16") == 0
    output = capsys.readouterr().out
    assert "screened   us60" in output
    assert "2 candidate finding(s)" in output
    assert "research candidates, not judgements" in output
    assert ledger.job(job_id)["status"] == "awaiting_adjudication"


def test_the_run_pack_holds_the_universe_and_nothing_about_us(fund, tmp_path, capsys):
    fund("job", "open", "--observation", "periodic_discovery", "--recipe", "idea_generation",
         "--mode", "de_novo", "--universe", "us60", "--as-of", "2026-08-16")
    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    job_id = ledger.jobs()[-1]["job_id"]

    fund("run", job_id, "--dry-run", "--workdir", str(tmp_path / "run"))
    pack = json.loads((tmp_path / "run" / "pack.json").read_text(encoding="utf-8"))
    assert len(pack["universe"]) == 60
    assert not {"thesis", "positions", "nav", "cash", "previous_judgement"} & set(pack)


def test_a_screen_is_not_adjudicated(fund, tmp_path, capsys):
    """It produced candidates, not a judgement. Different verb."""
    fund("job", "open", "--observation", "periodic_discovery", "--recipe", "idea_generation",
         "--mode", "de_novo", "--universe", "us60", "--as-of", "2026-08-16")
    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    job_id = ledger.jobs()[-1]["job_id"]
    fund("run", job_id, "--stub", screen_sidecar(tmp_path), "--workdir", str(tmp_path / "run"))

    capsys.readouterr()
    assert fund("adjudicate", job_id) == 2
    error = capsys.readouterr().err
    assert "not a judgement to adjudicate" in error
    assert "onboarding_underwrite" in error


def test_an_unknown_universe_lists_the_real_ones(fund, tmp_path, capsys):
    fund("job", "open", "--observation", "periodic_discovery", "--recipe", "idea_generation",
         "--mode", "de_novo", "--universe", "atlantis", "--as-of", "2026-08-16")
    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    job_id = ledger.jobs()[-1]["job_id"]

    capsys.readouterr()
    assert fund("run", job_id, "--dry-run", "--workdir", str(tmp_path / "run")) == 2
    error = capsys.readouterr().err
    assert "no universe called 'atlantis'" in error
    assert "us60" in error


def test_the_screen_lists_without_a_ticker(fund, capsys):
    fund("job", "open", "--observation", "periodic_discovery", "--recipe", "idea_generation",
         "--mode", "de_novo", "--universe", "us60", "--as-of", "2026-08-16")
    capsys.readouterr()
    assert fund("jobs") == 0
    assert "periodic_discovery" in capsys.readouterr().out
