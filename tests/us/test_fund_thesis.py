"""Thesis lifecycle and the monitoring contract.

The load-bearing test in this file is the one asserting that no code path lets
a machine break or close a thesis. Everything else is convenience; that one is
the design.
"""

from __future__ import annotations

import json

import pytest

from adapter.fund import cli, store, thesis as thesis_module
from adapter.fund.thesis import ACTIVE, BROKEN, CLOSED, REVIEW_REQUIRED, TransitionRefused


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
    run("assess", "NVDA",
        "--summary", "Data centre demand outruns supply into 2027",
        "--readiness", "starter", "--downside", "-0.30",
        "--downside-scenario", "Capex pauses and the multiple compresses",
        "--evidence-date", "2026-08-16", "--review-due", "2026-11-15",
        "--as-of", "2026-08-16")
    return run


def theses(fund):
    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    return thesis_module.project(ledger.thesis_events())


def only_thesis(fund):
    return next(iter(theses(fund).values()))


def contract_file(tmp_path, **overrides):
    document = {
        "version": 1,
        "effective_from": "2026-08-16",
        "mechanical_rules": [
            {"rule_id": "gross_margin_floor", "metric_id": "gross_margin",
             "period_basis": "ttm", "test_type": "absolute_value",
             "operator": "lt", "threshold": "0.55"}
        ],
        "qualitative_checks": [
            {"check_id": "customer_concentration",
             "question": "Has the top-two customer share moved materially?",
             "review_on": ["new_periodic_filing", "review_due"],
             "review_due": "2026-11-15"}
        ],
    }
    document.update(overrides)
    path = tmp_path / f"contract-v{document['version']}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


# ------------------------------------------------------- transition rules

@pytest.mark.parametrize("from_status,to_status", [
    (ACTIVE, REVIEW_REQUIRED),
    (REVIEW_REQUIRED, ACTIVE),
    (REVIEW_REQUIRED, BROKEN),
    (REVIEW_REQUIRED, CLOSED),
])
def test_the_designs_transitions_are_allowed_to_a_human(from_status, to_status):
    thesis_module.check_transition(from_status, to_status, "human")


@pytest.mark.parametrize("to_status", [ACTIVE, REVIEW_REQUIRED, BROKEN, CLOSED])
def test_nothing_moves_out_of_closed(to_status):
    with pytest.raises(TransitionRefused):
        thesis_module.check_transition(CLOSED, to_status, "human")


@pytest.mark.parametrize("to_status", [BROKEN, CLOSED])
def test_a_thesis_reaches_broken_or_closed_only_through_review(to_status):
    with pytest.raises(TransitionRefused, match="may only become"):
        thesis_module.check_transition(ACTIVE, to_status, "human")


@pytest.mark.parametrize("from_status,to_status", [
    (ACTIVE, REVIEW_REQUIRED),
    (REVIEW_REQUIRED, ACTIVE),
    (REVIEW_REQUIRED, BROKEN),
    (REVIEW_REQUIRED, CLOSED),
    (BROKEN, CLOSED),
])
def test_the_machine_may_only_ever_request_a_review(from_status, to_status):
    """A breached rule means a number crossed a line. It does not mean the
    reasoning was wrong, and only the owner decides which it is."""
    if (from_status, to_status) == (ACTIVE, REVIEW_REQUIRED):
        thesis_module.check_transition(from_status, to_status, "machine")
        return
    with pytest.raises(TransitionRefused, match="owner's judgement"):
        thesis_module.check_transition(from_status, to_status, "machine")


def test_no_code_path_lets_a_machine_break_or_close_a_thesis():
    """Exhaustive over the whole transition space, not a sample of it."""
    statuses = [ACTIVE, REVIEW_REQUIRED, BROKEN, CLOSED]
    reached_by_machine = set()
    for from_status in statuses:
        for to_status in statuses:
            try:
                thesis_module.check_transition(from_status, to_status, "machine")
            except TransitionRefused:
                continue
            reached_by_machine.add(to_status)
    assert reached_by_machine == {REVIEW_REQUIRED}


def test_building_a_machine_status_event_is_refused_at_the_source():
    with pytest.raises(TransitionRefused):
        thesis_module.status_event(
            thesis_id="THS-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f",
            from_status=REVIEW_REQUIRED, to_status=BROKEN,
            reason="the rule breached", effective_date="2026-09-01", actor="machine",
        )


# --------------------------------------------------------------- opening

def test_a_thesis_opens_from_an_accepted_assessment(fund, capsys):
    capsys.readouterr()
    assert fund("thesis", "open", "NVDA", "--as-of", "2026-08-16") == 0
    output = capsys.readouterr().out
    assert "opened" in output and "status active" in output

    document = only_thesis(fund).document
    assert document["status"] == ACTIVE
    assert document["security_id"] == "sec:nvda"
    assert document["current_assessment_id"].startswith("ASM-")


def test_a_security_cannot_have_two_open_theses(fund, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    capsys.readouterr()
    assert fund("thesis", "open", "NVDA", "--as-of", "2026-08-17") == 2
    assert "already has an open thesis" in capsys.readouterr().err


def test_a_new_thesis_can_open_once_the_old_one_is_closed(fund):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "status", thesis_id, "--to", "review_required",
         "--reason", "Q3 broke the pillar", "--as-of", "2026-11-01")
    fund("thesis", "close", thesis_id, "--close-reason", "thesis_broken",
         "--reason", "Pricing power was the whole claim", "--as-of", "2026-11-02")
    assert fund("thesis", "open", "NVDA", "--as-of", "2026-11-03") == 0
    assert len(theses(fund)) == 2


def test_opening_needs_an_assessment(fund, capsys):
    fund("instrument", "add", "--ticker", "AMD", "--name", "Advanced Micro Devices")
    capsys.readouterr()
    assert fund("thesis", "open", "AMD") == 2
    assert "run `fund assess AMD` first" in capsys.readouterr().err


def test_an_acknowledged_assessment_cannot_open_a_thesis(fund, capsys):
    fund("instrument", "add", "--ticker", "AMD", "--name", "Advanced Micro Devices")
    fund("assess", "AMD", "--summary", "worth a look", "--readiness", "watchlist",
         "--downside-unknown", "--downside-reason", "no segment detail",
         "--evidence-date", "2026-08-16", "--review-due", "2026-11-15",
         "--acknowledge", "--sources-not-checked")
    capsys.readouterr()
    assert fund("thesis", "open", "AMD") == 2
    assert "acknowledged without full adjudication" in capsys.readouterr().err


# ------------------------------------------------------ monitoring contract

def test_activating_a_contract(fund, tmp_path, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    capsys.readouterr()
    assert fund("thesis", "contract", thesis_id, "--from", contract_file(tmp_path)) == 0
    assert "1 mechanical rule(s), 1 qualitative check(s)" in capsys.readouterr().out

    contract = only_thesis(fund).document["monitoring_contract"]
    assert contract["version"] == 1
    assert contract["mechanical_rules"][0]["metric_id"] == "gross_margin"


def test_a_thesis_without_a_contract_says_nothing_is_watching(fund, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    capsys.readouterr()
    fund("thesis", "show", "NVDA")
    assert "NO MONITORING CONTRACT" in capsys.readouterr().out


def test_replacing_a_contract_needs_a_new_version_and_a_reason(fund, tmp_path, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", contract_file(tmp_path))

    capsys.readouterr()
    assert fund("thesis", "contract", thesis_id, "--from", contract_file(tmp_path)) == 2
    assert "not newer than the active v1" in capsys.readouterr().err

    same_version_bumped = contract_file(tmp_path, version=2)
    capsys.readouterr()
    assert fund("thesis", "contract", thesis_id, "--from", same_version_bumped) == 2
    assert "requires --reason" in capsys.readouterr().err

    assert fund("thesis", "contract", thesis_id, "--from", same_version_bumped,
                "--reason", "Margin floor was set before the mix shift") == 0
    assert only_thesis(fund).document["monitoring_contract"]["version"] == 2


def test_old_contract_versions_are_retained(fund, tmp_path):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", contract_file(tmp_path))
    fund("thesis", "contract", thesis_id, "--from", contract_file(tmp_path, version=2),
         "--reason", "recalibrated")
    assert [c["version"] for c in only_thesis(fund).contract_versions] == [1, 2]


def test_a_contract_may_not_carry_more_than_five_mechanical_rules():
    rules = [
        {"rule_id": f"rule_{n}", "metric_id": "gross_margin", "period_basis": "ttm",
         "test_type": "absolute_value", "operator": "lt", "threshold": "0.5"}
        for n in range(6)
    ]
    with pytest.raises(thesis_module.ThesisError, match="ceiling is 5"):
        thesis_module.build_contract(version=1, effective_from="2026-08-16",
                                     mechanical_rules=rules, qualitative_checks=[])


def test_two_rules_may_not_share_an_id():
    rule = {"rule_id": "same", "metric_id": "gross_margin", "period_basis": "ttm",
            "test_type": "absolute_value", "operator": "lt", "threshold": "0.5"}
    with pytest.raises(thesis_module.ThesisError, match="share a rule_id"):
        thesis_module.build_contract(version=1, effective_from="2026-08-16",
                                     mechanical_rules=[rule, dict(rule)],
                                     qualitative_checks=[])


def test_a_qualitative_check_can_be_marked_reviewed(fund, tmp_path, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", contract_file(tmp_path))

    capsys.readouterr()
    assert fund("thesis", "reviewed", thesis_id, "--check", "customer_concentration",
                "--next-due", "2027-02-15", "--as-of", "2026-11-15") == 0
    check = only_thesis(fund).document["monitoring_contract"]["qualitative_checks"][0]
    assert check["last_reviewed_at"] == "2026-11-15"
    assert check["review_due"] == "2027-02-15"


def test_reviewing_an_unknown_check_is_refused(fund, tmp_path, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", contract_file(tmp_path))
    capsys.readouterr()
    assert fund("thesis", "reviewed", thesis_id, "--check", "nope",
                "--next-due", "2027-02-15") == 2
    assert "no qualitative check called" in capsys.readouterr().err


def test_due_checks_are_reported(fund, tmp_path):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", contract_file(tmp_path))
    document = only_thesis(fund).document
    assert thesis_module.due_qualitative_checks(document, "2026-09-01") == []
    assert len(thesis_module.due_qualitative_checks(document, "2026-12-01")) == 1


# -------------------------------------------------------------- lifecycle

def test_the_full_lifecycle(fund, tmp_path, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", contract_file(tmp_path))

    fund("thesis", "status", thesis_id, "--to", "review_required",
         "--reason", "Gross margin came in below the floor", "--as-of", "2026-11-01")
    assert only_thesis(fund).status == REVIEW_REQUIRED

    fund("thesis", "status", thesis_id, "--to", "active",
         "--reason", "The miss was a one-off inventory charge",
         "--resolution", "decision_irrelevant_breach", "--as-of", "2026-11-05")
    assert only_thesis(fund).status == ACTIVE
    assert "status_reason" not in only_thesis(fund).document

    fund("thesis", "status", thesis_id, "--to", "review_required",
         "--reason", "Second consecutive miss", "--as-of", "2027-02-01")
    fund("thesis", "status", thesis_id, "--to", "broken",
         "--reason", "The pricing-power claim is not standing up",
         "--resolution", "thesis_broken", "--as-of", "2027-02-03")
    assert only_thesis(fund).status == BROKEN

    capsys.readouterr()
    fund("thesis", "show", thesis_id)
    output = capsys.readouterr().out
    assert "active -> review_required" in output
    assert "review_required -> broken" in output


def test_leaving_a_review_needs_its_cause(fund, capsys):
    """Without it the thresholds cannot be calibrated, and it is not recoverable later."""
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "status", thesis_id, "--to", "review_required", "--reason", "margin miss")
    capsys.readouterr()
    assert fund("thesis", "status", thesis_id, "--to", "active", "--reason", "fine now") == 2
    assert "needs --resolution" in capsys.readouterr().err


def test_an_illegal_transition_is_refused_with_the_legal_ones(fund, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    capsys.readouterr()
    assert fund("thesis", "status", thesis_id, "--to", "broken", "--reason", "x") == 2
    error = capsys.readouterr().err
    assert "cannot go from active to broken" in error
    assert "review_required" in error


def test_closing_records_its_reason(fund, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "status", thesis_id, "--to", "review_required",
         "--reason", "Target reached", "--as-of", "2027-01-01")
    capsys.readouterr()
    assert fund("thesis", "close", thesis_id, "--close-reason", "thesis_played_out",
                "--reason", "Multiple re-rated to fair", "--as-of", "2027-01-05") == 0
    document = only_thesis(fund).document
    assert document["status"] == CLOSED
    assert document["closed_at"] == "2027-01-05"
    assert document["close_reason"] == "thesis_played_out"


def test_a_closed_thesis_cannot_be_reopened(fund, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "status", thesis_id, "--to", "review_required", "--reason", "x")
    fund("thesis", "close", thesis_id, "--close-reason", "position_exited", "--reason", "sold")
    capsys.readouterr()
    assert fund("thesis", "status", thesis_id, "--to", "active", "--reason", "changed my mind",
                "--resolution", "thesis_confirmed") == 2
    assert "cannot go from closed" in capsys.readouterr().err


# ------------------------------------------------------------- projection

def test_the_thesis_is_a_projection_not_a_stored_row(fund, tmp_path):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", contract_file(tmp_path))
    fund("thesis", "status", thesis_id, "--to", "review_required", "--reason", "miss")

    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    events = ledger.thesis_events()
    assert [e["event_type"] for e in events] == ["opened", "contract_activated", "status_changed"]
    assert thesis_module.project(events)[thesis_id].status == REVIEW_REQUIRED


def test_thesis_events_are_immutable(fund):
    import sqlite3

    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    with ledger.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE thesis_event SET actor = 'machine'")
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute("DELETE FROM thesis_event")


def test_a_transition_from_the_wrong_starting_status_is_caught_on_replay():
    thesis_id = "THS-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f"
    events = [
        thesis_module.open_event(security_id="sec:nvda", thesis_statement="x",
                                 assessment_id="ASM-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f",
                                 effective_date="2026-08-16", thesis_id=thesis_id),
        {
            "thesis_event_id": "0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e71",
            "thesis_id": thesis_id, "event_type": "status_changed",
            "effective_date": "2026-09-01", "recorded_at": "2026-09-01T00:00:00Z",
            "actor": "human", "from_status": REVIEW_REQUIRED, "to_status": ACTIVE,
            "reason": "claims to start from review_required",
        },
    ]
    with pytest.raises(thesis_module.ThesisError, match="but the thesis is active"):
        thesis_module.project(events)


def test_an_event_for_an_unopened_thesis_is_caught():
    with pytest.raises(thesis_module.ThesisError, match="unopened thesis"):
        thesis_module.project([{
            "thesis_event_id": "0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e71",
            "thesis_id": "THS-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f",
            "event_type": "status_changed", "effective_date": "2026-09-01",
            "recorded_at": "2026-09-01T00:00:00Z", "actor": "human",
            "from_status": ACTIVE, "to_status": REVIEW_REQUIRED, "reason": "x",
        }])


def test_the_thesis_carries_no_exposure(fund):
    """Position size is a fact about the book, not about the belief."""
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    document = only_thesis(fund).document
    for forbidden in ("quantity", "weight", "market_value", "cost_basis", "exposure"):
        assert forbidden not in document


def test_the_contract_template_is_usable_as_is(fund, tmp_path, capsys):
    fund("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    thesis_id = only_thesis(fund).thesis_id

    capsys.readouterr()
    fund("thesis", "contract-template")
    template = capsys.readouterr().out
    path = tmp_path / "from-template.json"
    path.write_text(template, encoding="utf-8")

    assert fund("thesis", "contract", thesis_id, "--from", str(path)) == 0
