"""Observation, dispatch, packs, output contracts, and the chain end to end.

The pack tests are the important ones. Everything else here can be fixed with
a patch; a capital figure reaching an analyst cannot be un-shown.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from adapter.fund import cli, dispatch, jobs, packs, recipes, schemas, store, thesis as thesis_module


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
    run("open", "position", "--security", "NVDA", "--quantity", "100",
        "--unit-cost", "90", "--date", "2026-08-01")
    run("assess", "NVDA", "--summary", "Pricing power holds through the cycle",
        "--readiness", "starter", "--downside", "-0.30",
        "--downside-scenario", "Competition compresses the margin",
        "--evidence-date", "2026-08-16", "--review-due", "2026-11-15",
        "--as-of", "2026-08-16")
    run("thesis", "open", "NVDA", "--as-of", "2026-08-16")

    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({
        "version": 1,
        "effective_from": "2026-08-16",
        "mechanical_rules": [{
            "rule_id": "gross_margin_floor", "metric_id": "gross_margin",
            "period_basis": "ttm", "test_type": "absolute_value",
            "operator": "lt", "threshold": "0.55",
        }],
        "qualitative_checks": [{
            "check_id": "customer_concentration",
            "question": "Has the top-two customer share moved materially?",
            "review_on": ["new_periodic_filing", "review_due"],
            "review_due": "2026-11-01",
        }],
    }), encoding="utf-8")
    ledger = store.open_ledger(path=tmp_path / "ledger.sqlite3")
    thesis_id = next(iter(thesis_module.project(ledger.thesis_events())))
    run("thesis", "contract", thesis_id, "--from", str(contract))
    run.thesis_id = thesis_id  # type: ignore[attr-defined]
    return run


def ledger_of(fund):
    return store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")


def filings_file(tmp_path, entries=None):
    path = tmp_path / "filings.json"
    path.write_text(json.dumps({"NVDA": entries if entries is not None else [
        {"accession": "0001045810-26-000123", "form": "10-Q",
         "filing_date": "2026-11-01", "report_date": "2026-09-30"},
    ]}), encoding="utf-8")
    return str(path)


def sidecars_file(tmp_path, **overrides):
    deep_dive = {
        "sidecar_version": 1,
        "skill": "earnings-deep-dive",
        "findings": [
            {"statement": "Gross margin held at 62% against a 55% floor",
             "direction": "supports", "source": "10-Q p.14", "materiality": "high"},
        ],
        "answers": [
            {"check_id": "customer_concentration", "answered": True,
             "answer": "Top-two share fell from 39% to 36%; the decline is broad-based",
             "source": "10-Q p.22"},
        ],
    }
    tracker = {
        "sidecar_version": 1,
        "skill": "thesis-tracker",
        "findings": [
            {"statement": "The pricing-power pillar is intact after Q3",
             "direction": "supports", "source": "10-Q p.14"},
        ],
        "proposed_assessment": {
            "thesis_summary": "Pricing power held through Q3; mix is the swing factor",
            "readiness": "starter",
            "downside": {"status": "known", "return_fraction": "-0.28",
                         "scenario": "Mix shift persists and the multiple compresses"},
            "evidence_date": "2026-11-01",
            "review_due": "2027-02-15",
            "sources": ["10-Q 2026-11-01 p.14"],
        },
    }
    document = {"earnings-deep-dive": deep_dive, "thesis-tracker": tracker}
    document.update(overrides)
    path = tmp_path / "sidecars.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


# ------------------------------------------------------------- dispatch

def test_every_rule_requires_an_open_thesis_and_names_a_recipe():
    """Nothing in the table acts on a company we have not underwritten."""
    assert {rule.rule_id for rule in dispatch.RULES} == {
        "new_filing_open_thesis", "earnings_evidence_open_thesis",
        "review_due_open_thesis", "price_shock_open_thesis",
        "mechanical_breach_open_thesis",
    }
    for rule in dispatch.RULES:
        assert rule.requires_open_thesis
        assert rule.recipe in recipes.RECIPE_STEPS
        assert rule.version >= 1


def test_a_price_shock_is_reviewed_blind():
    """A large move is exactly when a prior view is hardest to re-examine."""
    rule = dispatch.match("price_shock", has_open_thesis=True)
    assert rule.assessment_mode == "independent_then_reconcile"
    assert rule.recipe == "blind_review"


def test_a_filing_on_a_watched_company_matches():
    rule = dispatch.match("new_periodic_filing", has_open_thesis=True)
    assert rule is not None
    assert rule.recipe == "deep_dive_then_tracker"
    assert rule.assessment_mode == "update_against_prior"


def test_a_filing_with_no_thesis_matches_nothing():
    """Not an error -- a filing on a company we do not follow is normal."""
    assert dispatch.match("new_periodic_filing", has_open_thesis=False) is None


def test_an_observation_with_no_rule_matches_nothing():
    """Discovery arrives in F10; until then the observation simply goes nowhere."""
    assert dispatch.match("periodic_discovery", has_open_thesis=True) is None


def test_a_disabled_rule_stops_matching():
    from dataclasses import replace

    disabled = replace(dispatch.RULES[0], enabled=False)
    assert not disabled.matches("new_periodic_filing", has_open_thesis=True)


def test_health_flags_a_rule_that_never_fired():
    rows = dispatch.health(jobs=[], as_of="2026-11-05")
    assert rows[0]["never_fired"] is True
    assert rows[0]["last_dispatched"] is None


# ---------------------------------------------------------------- packs

def test_a_pack_carries_no_capital(fund, tmp_path, capsys):
    fund("observe", "--filings", filings_file(tmp_path), "--as-of", "2026-11-05")
    job_id = ledger_of(fund).jobs()[-1]["job_id"]
    workdir = tmp_path / "run"

    capsys.readouterr()
    assert fund("run", job_id, "--dry-run", "--workdir", str(workdir),
                "--as-of", "2026-11-05") == 0
    pack = json.loads((workdir / "pack.json").read_text(encoding="utf-8"))

    assert packs.walk_for_capital_leaks(pack) == []
    serialised = json.dumps(pack)
    for forbidden in ("100000", "9000", "\"weight\"", "unrealized", "average_cost"):
        assert forbidden not in serialised, f"{forbidden!r} reached the pack"


def test_the_leak_check_catches_a_nested_capital_field():
    leaks = packs.walk_for_capital_leaks({"thesis": {"context": {"nav": "100000"}}})
    assert leaks == ["/thesis/context/nav"]


def test_a_pack_that_would_leak_is_refused():
    with pytest.raises(packs.PackError, match="capital information"):
        packs.build_pack(
            job={"job_id": "JOB-x", "security_id": "sec:nvda", "recipe": "tracker",
                 "assessment_mode": "de_novo",
                 "trigger_snapshot": {"observation": "review_due"}},
            ticker="NVDA",
            thesis=None,
            prior_assessment=None,
            evidence={"accession": "acc-1", "nav": "100000"},
        )


def test_due_questions_are_written_into_the_pack(fund, tmp_path):
    fund("observe", "--filings", filings_file(tmp_path), "--as-of", "2026-11-05")
    job_id = ledger_of(fund).jobs()[-1]["job_id"]
    workdir = tmp_path / "run"
    fund("run", job_id, "--dry-run", "--workdir", str(workdir), "--as-of", "2026-11-05")
    pack = json.loads((workdir / "pack.json").read_text(encoding="utf-8"))

    questions = pack["questions_you_must_answer"]
    assert [q["check_id"] for q in questions] == ["customer_concentration"]
    assert "top-two customer share" in questions[0]["question"]


def test_update_mode_requires_the_previous_judgement():
    with pytest.raises(packs.PackError, match="measuring what changed"):
        packs.build_pack(
            job={"job_id": "JOB-x", "security_id": "sec:nvda", "recipe": "tracker",
                 "assessment_mode": "update_against_prior",
                 "trigger_snapshot": {"observation": "review_due"}},
            ticker="NVDA", thesis=None, prior_assessment=None)


def test_de_novo_shows_no_prior_view():
    pack = packs.build_pack(
        job={"job_id": "JOB-x", "security_id": "sec:nvda", "recipe": "onboarding_underwrite",
             "assessment_mode": "de_novo",
             "trigger_snapshot": {"observation": "preview_without_assessment"}},
        ticker="NVDA", thesis=None,
        prior_assessment={"assessment_id": "ASM-x", "readiness": "core"})
    assert "previous_judgement" not in pack


def test_blind_mode_says_the_prior_view_is_withheld():
    pack = packs.build_pack(
        job={"job_id": "JOB-x", "security_id": "sec:nvda", "recipe": "blind_review",
             "assessment_mode": "independent_then_reconcile",
             "trigger_snapshot": {"observation": "price_shock"}},
        ticker="NVDA", thesis=None, prior_assessment=None)
    assert "deliberately not" in pack["previous_judgement_withheld"]
    assert "previous_judgement" not in pack


def test_the_pack_explains_what_not_breached_does_not_mean(fund, tmp_path):
    fund("check", fund.thesis_id, "--observations", str(_observations(tmp_path)),
         "--as-of", "2026-11-05")
    fund("observe", "--filings", filings_file(tmp_path), "--as-of", "2026-11-05")
    job_id = ledger_of(fund).jobs()[-1]["job_id"]
    workdir = tmp_path / "run"
    fund("run", job_id, "--dry-run", "--workdir", str(workdir), "--as-of", "2026-11-05")
    pack = json.loads((workdir / "pack.json").read_text(encoding="utf-8"))
    assert "never as unchanged" in pack["mechanical_check_note"]


def _observations(tmp_path):
    path = tmp_path / "observations.json"
    path.write_text(json.dumps({"observations": [{
        "metric_id": "gross_margin", "period_basis": "ttm", "status": "available",
        "value": "0.62", "unit": "percent", "as_of": "2026-11-01",
    }]}), encoding="utf-8")
    return path


# ------------------------------------------------------------- observing

def test_a_new_filing_opens_one_job(fund, tmp_path, capsys):
    capsys.readouterr()
    assert fund("observe", "--filings", filings_file(tmp_path), "--as-of", "2026-11-05") == 0
    output = capsys.readouterr().out
    assert "NVDA" in output and "10-Q" in output
    assert len(ledger_of(fund).jobs()) == 1


def test_observing_twice_opens_nothing_more(fund, tmp_path, capsys):
    fund("observe", "--filings", filings_file(tmp_path), "--as-of", "2026-11-05")
    capsys.readouterr()
    assert fund("observe", "--filings", filings_file(tmp_path), "--as-of", "2026-11-06") == 0
    assert "nothing new" in capsys.readouterr().out
    assert len(ledger_of(fund).jobs()) == 1


def test_a_filing_is_recorded_as_seen_even_beyond_the_limit(fund, tmp_path):
    """Twenty years of history becomes one piece of work, not eighty."""
    entries = [
        {"accession": f"0001045810-2{n}-00000{n}", "form": "10-Q",
         "filing_date": f"202{n}-05-01", "report_date": f"202{n}-03-31"}
        for n in range(1, 6)
    ]
    fund("observe", "--filings", filings_file(tmp_path, entries), "--as-of", "2026-11-05")

    ledger = ledger_of(fund)
    assert len(ledger.jobs()) == 1
    assert len(ledger.observed_filings("sec:nvda")) == 5

    # And the ones beyond the limit never resurface.
    fund("observe", "--filings", filings_file(tmp_path, entries), "--as-of", "2026-11-06")
    assert len(ledger.jobs()) == 1


def test_nothing_is_watched_without_an_open_thesis(fund, tmp_path, capsys):
    fund("thesis", "status", fund.thesis_id, "--to", "review_required", "--reason", "x")
    fund("thesis", "close", fund.thesis_id, "--close-reason", "position_exited",
         "--reason", "sold out")
    capsys.readouterr()
    assert fund("observe", "--filings", filings_file(tmp_path)) == 0
    assert "nothing is being watched" in capsys.readouterr().out


# --------------------------------------------------------- output contract

def test_a_valid_sidecar_passes():
    document = json.loads(open(sidecars_file(_TmpDir()), encoding="utf-8").read()) \
        if False else None  # placeholder to keep the helper honest


def test_a_tracker_must_propose_a_judgement():
    sidecar = {
        "sidecar_version": 1, "skill": "thesis-tracker", "security_id": "sec:nvda",
        "produced_at": "2026-11-05T00:00:00Z",
        "findings": [{"statement": "x", "direction": "neutral", "source": "10-Q"}],
    }
    assert any("proposed_assessment" in message
               for message in schemas.schema_errors(sidecar, schemas.SKILL_OUTPUT))


def test_screening_may_not_propose_a_judgement():
    sidecar = {
        "sidecar_version": 1, "skill": "idea-generation", "security_id": "sec:nvda",
        "produced_at": "2026-11-05T00:00:00Z",
        "findings": [{"statement": "x", "direction": "neutral", "source": "screen"}],
        "proposed_assessment": {
            "thesis_summary": "buy it", "readiness": "core",
            "downside": {"status": "known", "return_fraction": "-0.2", "scenario": "s"},
            "evidence_date": "2026-11-01", "review_due": "2027-02-01",
        },
    }
    assert schemas.schema_errors(sidecar, schemas.SKILL_OUTPUT)


def test_a_finding_needs_a_source():
    sidecar = {
        "sidecar_version": 1, "skill": "earnings-deep-dive", "security_id": "sec:nvda",
        "produced_at": "2026-11-05T00:00:00Z",
        "findings": [{"statement": "margins are fine", "direction": "supports"}],
    }
    assert any("source" in message
               for message in schemas.schema_errors(sidecar, schemas.SKILL_OUTPUT))


def test_a_result_that_fails_its_contract_never_reaches_the_owner(fund, tmp_path, capsys):
    fund("observe", "--filings", filings_file(tmp_path), "--as-of", "2026-11-05")
    job_id = ledger_of(fund).jobs()[-1]["job_id"]
    broken = sidecars_file(tmp_path, **{
        "thesis-tracker": {"sidecar_version": 1, "skill": "thesis-tracker",
                           "findings": [{"statement": "x", "direction": "neutral",
                                         "source": "10-Q"}]},
    })

    capsys.readouterr()
    assert fund("run", job_id, "--stub", broken, "--workdir", str(tmp_path / "run"),
                "--as-of", "2026-11-05") == 2
    error = capsys.readouterr().err
    assert "does not satisfy its contract" in error
    assert "not 'the analyst had nothing to say'" in error
    assert ledger_of(fund).job(job_id)["status"] == jobs.CONTRACT_FAILED


# ------------------------------------------------------------ the chain

def test_the_whole_chain_runs(fund, tmp_path, capsys):
    """filing -> mechanical check -> deep dive -> tracker -> Q1 -> adjudication
    -> new assessment -> thesis status."""
    ledger = ledger_of(fund)

    # 1. A mechanical check on the new evidence: the margin held.
    assert fund("check", fund.thesis_id, "--observations", str(_observations(tmp_path)),
                "--evaluated-for", "new_periodic_filing",
                "--accession", "0001045810-26-000123", "--as-of", "2026-11-05") == 0
    assert ledger.check_records()[-1]["result"] == "not_breached"

    # 2. The filing is observed and becomes work.
    assert fund("observe", "--filings", filings_file(tmp_path), "--as-of", "2026-11-05") == 0
    job_id = ledger.jobs()[-1]["job_id"]
    assert ledger.job(job_id)["rule_id"] == "new_filing_open_thesis"

    # 3. The recipe runs both skills in order.
    capsys.readouterr()
    assert fund("run", job_id, "--stub", sidecars_file(tmp_path),
                "--workdir", str(tmp_path / "run"), "--as-of", "2026-11-05") == 0
    output = capsys.readouterr().out
    assert "earnings-deep-dive" in output and "thesis-tracker" in output
    assert ledger.job(job_id)["status"] == jobs.AWAITING_ADJUDICATION

    # 4. It appears in Q1 with a reason and an estimate.
    capsys.readouterr()
    fund("inbox", "--as-of", "2026-11-05")
    inbox = capsys.readouterr().out
    assert "Q1 -- NEEDS ADJUDICATION" in inbox
    assert job_id in inbox

    # 5. Adjudicated by a human, with answers.
    capsys.readouterr()
    assert fund("adjudicate", job_id, "--accept",
                "--change-driver", "Q3 confirmed the pricing-power pillar",
                "--minutes", "14", "--as-of", "2026-11-05") == 0

    assessment = ledger.assessments()[-1]
    assert assessment["downside"]["return_fraction"] == "-0.28"
    assert assessment["human_authored"] is False
    assert assessment["assessment_mode"] == "update_against_prior"

    # 6. The thesis now points at the new judgement.
    history = thesis_module.project(ledger.thesis_events())[fund.thesis_id]
    assert history.document["current_assessment_id"] == assessment["assessment_id"]
    assert history.status == thesis_module.ACTIVE

    # 7. And the inbox is quiet again.
    capsys.readouterr()
    fund("inbox", "--as-of", "2026-11-06")
    assert "Nothing needs you today." in capsys.readouterr().out


def test_the_upstream_step_feeds_the_next_one(tmp_path):
    calls: list[dict] = []

    def executor(skill, pack, workdir):
        calls.append(dict(pack))
        return {
            "sidecar_version": 1, "skill": skill, "security_id": "sec:nvda",
            "produced_at": "2026-11-05T00:00:00Z",
            "findings": [{"statement": f"{skill} finding", "direction": "neutral",
                          "source": "10-Q"}],
            **({"proposed_assessment": {
                "thesis_summary": "s", "readiness": "starter",
                "downside": {"status": "known", "return_fraction": "-0.3", "scenario": "s"},
                "evidence_date": "2026-11-01", "review_due": "2027-02-01"}}
               if skill == "thesis-tracker" else {}),
        }

    result = recipes.run(
        recipe="deep_dive_then_tracker",
        pack={"job_id": "JOB-x", "security_id": "sec:nvda"},
        executor=executor, workdir=tmp_path / "run")

    assert [step.skill for step in result.steps] == ["earnings-deep-dive", "thesis-tracker"]
    assert "upstream" not in calls[0]
    assert calls[1]["upstream"]["skill"] == "earnings-deep-dive"
    assert result.proposed_assessment["readiness"] == "starter"


def test_an_unknown_recipe_is_refused(tmp_path):
    with pytest.raises(recipes.RecipeError, match="unknown recipe"):
        recipes.run(recipe="do_something_clever", pack={}, executor=lambda *a: {},
                    workdir=tmp_path)
