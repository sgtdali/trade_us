"""The second wave of triggers: earnings evidence, review due, price shock.

The load-bearing assertion here is that a date alone starts nothing. An
expected earnings date is an estimate; research fired at an estimate is
research against numbers that do not exist yet.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from adapter.fund import cli, dispatch, observers, store, thesis as thesis_module
from adapter.models import FilingRef


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
    run("assess", "NVDA", "--summary", "Pricing power holds",
        "--readiness", "starter", "--downside", "-0.30",
        "--downside-scenario", "Competition compresses the margin",
        "--evidence-date", "2026-08-16", "--review-due", "2026-11-15",
        "--as-of", "2026-08-16")
    run("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    ledger = store.open_ledger(path=tmp_path / "ledger.sqlite3")
    thesis_id = next(iter(thesis_module.project(ledger.thesis_events())))
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
    run("thesis", "contract", thesis_id, "--from", str(contract))
    run.thesis_id = thesis_id  # type: ignore[attr-defined]
    return run


def ledger_of(fund):
    return store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")


# ------------------------------------------------------- F8.3 SEC items

def test_filing_ref_carries_sec_items():
    filing = FilingRef(cik="0001045810", accession="acc-1", form="8-K",
                       filing_date=date(2026, 11, 19), report_date=date(2026, 11, 19),
                       primary_document="d.htm", items=("2.02", "9.01"))
    assert filing.is_earnings_release


def test_an_ordinary_8k_is_not_an_earnings_release():
    filing = FilingRef(cik="0001045810", accession="acc-1", form="8-K",
                       filing_date=date(2026, 11, 19), report_date=date(2026, 11, 19),
                       primary_document="d.htm", items=("5.02",))
    assert not filing.is_earnings_release


def test_items_are_parsed_from_the_submissions_payload():
    from adapter.discovery import list_filings

    class _Client:
        def get_json(self, url):
            return {"filings": {"recent": {
                "accessionNumber": ["0001045810-26-000200"],
                "form": ["8-K"],
                "filingDate": ["2026-11-19"],
                "reportDate": [""],
                "primaryDocument": ["d8k.htm"],
                "items": ["2.02,9.01"],
            }, "files": []}}

    filings = list_filings(_Client(), "0001045810", as_of=date(2026, 11, 30),
                           forms=("8-K",))
    assert filings[0].items == ("2.02", "9.01")
    assert filings[0].is_earnings_release
    # No period of report on an 8-K: the filing date stands in rather than the
    # filing being dropped.
    assert filings[0].report_date == date(2026, 11, 19)


def test_a_periodic_filing_with_no_period_is_still_skipped():
    """The fallback must not reach 10-Q, where a wrong period misaligns everything."""
    from adapter.discovery import list_filings

    class _Client:
        def get_json(self, url):
            return {"filings": {"recent": {
                "accessionNumber": ["0001045810-26-000201"],
                "form": ["10-Q"],
                "filingDate": ["2026-11-19"],
                "reportDate": [""],
                "primaryDocument": ["d10q.htm"],
                "items": [""],
            }, "files": []}}

    assert list_filings(_Client(), "0001045810", as_of=date(2026, 11, 30)) == ()


# --------------------------------------------- F8.4 evidence, not a date

def test_only_an_item_202_filing_is_earnings_evidence():
    observations = observers.earnings_observations(
        [
            {"accession": "acc-1", "form": "8-K", "filing_date": "2026-11-19",
             "items": ("5.02",)},
            {"accession": "acc-2", "form": "8-K", "filing_date": "2026-11-20",
             "items": ("2.02", "9.01")},
        ],
        security_id="sec:nvda", thesis_id="THS-a")
    assert [o["evidence_accession"] for o in observations] == ["acc-2"]


def test_an_expected_earnings_date_produces_nothing():
    """There is no code path from a calendar entry to a job. On purpose."""
    assert observers.earnings_observations([], security_id="sec:nvda",
                                           thesis_id="THS-a") == []
    assert observers.earnings_observations(
        [{"accession": "acc-1", "form": "8-K", "filing_date": "2026-11-19", "items": ()}],
        security_id="sec:nvda", thesis_id="THS-a") == []


def test_items_may_arrive_as_a_comma_string():
    observations = observers.earnings_observations(
        [{"accession": "acc-1", "form": "8-K", "filing_date": "2026-11-19",
          "items": "2.02,9.01"}],
        security_id="sec:nvda", thesis_id="THS-a")
    assert len(observations) == 1


def test_earnings_evidence_dispatches_to_a_deep_dive():
    rule = dispatch.match("earnings_evidence", has_open_thesis=True)
    assert rule.recipe == "deep_dive_then_tracker"
    assert rule.assessment_mode == "update_against_prior"


# ------------------------------------------------------ F8.2 price shock

def marks(*pairs):
    return [{"security_id": "sec:nvda", "as_of": as_of, "price": price, "currency": "USD"}
            for as_of, price in pairs]


def shock(series, *, threshold_bps=2000, window_days=30, as_of="2026-11-30"):
    return observers.price_shock_observations(
        series, security_id="sec:nvda", thesis_id="THS-a",
        threshold_bps=threshold_bps, window_days=window_days, as_of=as_of)


def test_a_large_fall_is_a_review_not_a_sale():
    observations = shock(marks(("2026-10-01", "200"), ("2026-11-30", "150")))
    assert len(observations) == 1
    assert observations[0]["price_move_fraction"] == "-0.25"
    assert "a review, not a sale" in observations[0]["detail"]


def test_a_large_rise_also_asks_for_a_re_read():
    assert shock(marks(("2026-10-01", "100"), ("2026-11-30", "140")))


def test_a_move_inside_the_threshold_is_not_a_shock():
    assert shock(marks(("2026-10-01", "200"), ("2026-11-30", "185"))) == []


def test_a_slow_drift_does_not_register():
    """The baseline is a step back in time, so gradual repricing stays quiet."""
    series = marks(("2026-09-01", "200"), ("2026-10-01", "190"),
                   ("2026-11-01", "180"), ("2026-11-30", "172"))
    assert shock(series, window_days=30) == []


def test_one_mark_is_not_a_series():
    assert shock(marks(("2026-11-30", "150"))) == []


def test_a_future_mark_is_ignored():
    assert shock(marks(("2026-10-01", "200"), ("2027-01-01", "100")),
                 as_of="2026-11-30") == []


def test_the_threshold_is_tunable():
    series = marks(("2026-10-01", "200"), ("2026-11-30", "180"))
    assert shock(series, threshold_bps=2000) == []
    assert shock(series, threshold_bps=1000)


# -------------------------------------------------------- owner tuning

def test_only_the_named_knobs_are_tunable(tmp_path, monkeypatch):
    config = tmp_path / "config" / "fund"
    config.mkdir(parents=True)
    (config / "dispatch-tuning.json").write_text(
        json.dumps({"recipe": "something_else"}), encoding="utf-8")

    with pytest.raises(dispatch.DispatchError, match="not tunable"):
        dispatch.load_tuning(root=tmp_path)


def test_a_rule_can_be_switched_off_without_a_code_change():
    tuned = dispatch.apply_tuning(
        dispatch.RULES, {"rules": {"price_shock_open_thesis": {"enabled": False}}})
    by_id = {rule.rule_id: rule for rule in tuned}
    assert by_id["price_shock_open_thesis"].enabled is False
    assert by_id["new_filing_open_thesis"].enabled is True


def test_a_rules_recipe_cannot_be_retuned():
    with pytest.raises(dispatch.DispatchError, match="not tunable"):
        dispatch.apply_tuning(
            dispatch.RULES, {"rules": {"new_filing_open_thesis": {"recipe": "tracker"}}})


def test_missing_tuning_means_defaults_not_an_error(tmp_path):
    settings = dispatch.load_tuning(root=tmp_path)
    assert settings["price_shock_bps"] == dispatch.DEFAULT_TUNING["price_shock_bps"]


# -------------------------------------------------- F8.5 what is scanned

def test_the_cycle_scans_open_theses_not_a_waiting_queue(fund, tmp_path, capsys):
    """The old orchestrator only looked at candidates in state 'waiting', so a
    thesis nobody had queued was invisible. Here the open theses are the scan."""
    empty = tmp_path / "none.json"
    empty.write_text(json.dumps({"NVDA": []}), encoding="utf-8")

    capsys.readouterr()
    fund("research-cycle", "--filings", str(empty), "--observe-only", "--as-of", "2027-02-01")
    output = capsys.readouterr().out
    assert "review_due" in output

    fund("thesis", "status", fund.thesis_id, "--to", "review_required", "--reason", "x")
    fund("thesis", "close", fund.thesis_id, "--close-reason", "position_exited",
         "--reason", "sold out")
    capsys.readouterr()
    fund("research-cycle", "--filings", str(empty), "--observe-only", "--as-of", "2027-03-01")
    assert "0 opened" in capsys.readouterr().out


def test_a_price_shock_becomes_a_blind_review_end_to_end(fund, tmp_path, capsys):
    ledger = ledger_of(fund)
    ledger.record_price_marks(marks(("2026-10-01", "200")))

    empty = tmp_path / "none.json"
    empty.write_text(json.dumps({"NVDA": []}), encoding="utf-8")

    capsys.readouterr()
    fund("research-cycle", "--filings", str(empty), "--mark", "NVDA=150",
         "--observe-only", "--as-of", "2026-11-30")
    output = capsys.readouterr().out
    assert "price_shock" in output

    job = ledger.jobs()[-1]
    assert job["rule_id"] == "price_shock_open_thesis"
    assert job["assessment_mode"] == "independent_then_reconcile"

    # And the blind pack withholds the previous judgement.
    fund("run", job["job_id"], "--dry-run", "--workdir", str(tmp_path / "run"),
         "--as-of", "2026-11-30")
    pack = json.loads((tmp_path / "run" / "pack.json").read_text(encoding="utf-8"))
    assert "previous_judgement" not in pack
    assert "deliberately not" in pack["previous_judgement_withheld"]


def test_marks_taken_at_review_feed_the_shock_observer(fund, tmp_path):
    fund("review", "--price", "NVDA=200", "--as-of", "2026-10-01")
    fund("review", "--price", "NVDA=150", "--as-of", "2026-11-30")
    series = ledger_of(fund).price_marks("sec:nvda")
    assert [m["price"] for m in series] == ["200", "150"]
    assert shock(series, as_of="2026-11-30")


def test_one_evidence_one_job_even_with_two_signals(fund, tmp_path, capsys):
    """A breach and the filing that revealed it are one piece of reading."""
    filings = tmp_path / "filings.json"
    filings.write_text(json.dumps({"NVDA": [
        {"accession": "0001045810-26-000300", "form": "8-K",
         "filing_date": "2026-11-19", "report_date": "2026-11-19",
         "items": ["2.02", "9.01"]},
    ]}), encoding="utf-8")

    capsys.readouterr()
    fund("research-cycle", "--filings", str(filings), "--observe-only", "--as-of", "2026-11-20")
    jobs_opened = ledger_of(fund).jobs()
    assert len(jobs_opened) == 1
    # Earnings evidence outranks the plain filing observation on the same accession.
    assert jobs_opened[0]["rule_id"] == "earnings_evidence_open_thesis"
