"""The two-stage decision flow, end to end.

The assertions that matter most here are about what is absent: the assess
screen must not mention capital, and an assessment the owner would not stand
behind must not be able to buy anything.
"""

from __future__ import annotations

import pytest

from adapter.fund import cli, store


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
    return run


def assess(fund, *extra: str, readiness="starter", downside="-0.30"):
    return fund(
        "assess", "NVDA",
        "--summary", "Data centre demand outruns supply into 2027",
        "--readiness", readiness,
        "--downside", downside,
        "--downside-scenario", "Hyperscaler capex pauses and the multiple compresses",
        "--evidence-date", "2026-08-16",
        "--review-due", "2026-11-15",
        "--as-of", "2026-08-16",
        *extra,
    )


def latest_assessment(fund):
    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    return ledger.assessments()[-1]


def decisions_of(fund):
    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    return ledger.decisions()


# ------------------------------------------------------- stage one: assess

def test_assess_records_the_judgement(fund, capsys):
    capsys.readouterr()
    assert assess(fund) == 0
    output = capsys.readouterr().out
    assert "RESEARCH JUDGEMENT" in output
    assert "-30.00%" in output

    record = latest_assessment(fund)
    assert record["readiness"] == "starter"
    assert record["downside"]["return_fraction"] == "-0.3"
    assert record["assessment_mode"] == "de_novo"
    assert record["acceptance"]["mode"] == "human_adjudicated"


def test_the_assess_screen_shows_no_capital_figures(fund, capsys):
    """The whole point of stage one: judge the research, not the position."""
    fund("open", "position", "--security", "NVDA", "--quantity", "100",
         "--unit-cost", "90", "--date", "2026-08-01")
    capsys.readouterr()
    assess(fund)
    output = capsys.readouterr().out

    for forbidden in ("NAV", "Cash", "Weight", "P&L", "100000", "90.00", "9,000"):
        assert forbidden not in output, f"{forbidden!r} leaked into the assess screen"
    assert "Nothing above depends on what you own" in output


def test_a_downside_must_be_stated_or_explicitly_unknown(fund, capsys):
    capsys.readouterr()
    assert fund("assess", "NVDA", "--summary", "x", "--readiness", "starter",
                "--evidence-date", "2026-08-16", "--review-due", "2026-11-15") == 2
    assert "An unstated downside is not a smaller one" in capsys.readouterr().err


def test_a_downside_number_needs_a_scenario(fund, capsys):
    capsys.readouterr()
    assert fund("assess", "NVDA", "--summary", "x", "--readiness", "starter",
                "--downside", "-0.3", "--evidence-date", "2026-08-16",
                "--review-due", "2026-11-15") == 2
    assert "a number with no story" in capsys.readouterr().err


def test_an_unknown_downside_is_recorded_with_its_consequence(fund, capsys):
    capsys.readouterr()
    assert fund("assess", "NVDA", "--summary", "Too early to underwrite",
                "--readiness", "watchlist", "--downside-unknown",
                "--downside-reason", "segment disclosure changes next quarter",
                "--evidence-date", "2026-08-16", "--review-due", "2026-11-15") == 0
    assert "ineligible for new risk" in capsys.readouterr().out
    assert latest_assessment(fund)["downside"]["status"] == "unknown"


def test_a_second_assessment_must_say_what_changed(fund, capsys):
    assess(fund)
    capsys.readouterr()
    assert assess(fund, "--mode", "update_against_prior") == 2
    assert "--change-driver is required" in capsys.readouterr().err


def test_a_second_assessment_links_back_to_the_first(fund):
    assess(fund)
    first = latest_assessment(fund)["assessment_id"]
    assess(fund, "--change-driver", "Q2 gross margin came in 300 bp light")
    second = latest_assessment(fund)
    assert second["derived_from"] == first
    assert second["assessment_mode"] == "update_against_prior"


def test_a_material_change_requires_a_rationale(fund, capsys):
    assess(fund)
    capsys.readouterr()
    assert assess(fund, "--change-driver", "margins", readiness="core") == 2
    assert "material change" in capsys.readouterr().err

    assert assess(fund, "--change-driver", "margins", "--rationale",
                  "Two clean quarters of the pillar holding", readiness="core") == 0


def test_a_large_downside_move_is_material_too(fund, capsys):
    assess(fund, downside="-0.30")
    capsys.readouterr()
    assert assess(fund, "--change-driver", "guide cut", downside="-0.45") == 2
    assert "500 bp" in capsys.readouterr().err


def test_a_small_downside_move_is_not_material(fund):
    assess(fund, downside="-0.30")
    assert assess(fund, "--change-driver", "minor revision", downside="-0.33") == 0


def test_skipping_the_sources_check_cannot_pass_as_adjudicated(fund, capsys):
    capsys.readouterr()
    assert assess(fund, "--sources-not-checked") == 2
    assert "not a full adjudication" in capsys.readouterr().err


def test_acknowledging_without_adjudicating_is_marked(fund, capsys):
    capsys.readouterr()
    assert assess(fund, "--acknowledge", "--sources-not-checked") == 0
    assert "cannot raise readiness" in capsys.readouterr().out
    assert latest_assessment(fund)["acceptance"]["mode"] == \
        "acknowledged_without_full_adjudication"


# ------------------------------------------------ stage two: trade-preview

def test_preview_reproduces_the_designs_worked_example(fund, capsys):
    assess(fund)
    capsys.readouterr()
    assert fund("trade-preview", "NVDA", "buy", "--quantity", "50", "--price", "180",
                "--as-of", "2026-08-16") == 0
    output = capsys.readouterr().out

    assert "9,000.00" in output
    assert "0.00% -> 9.00%" in output
    assert "downside capacity     3.33%   <-- binding" in output
    assert "OUTSIDE POLICY" in output
    assert "~18 shares / 3,240.00" in output
    assert "270 bp of NAV" in output


def test_a_preview_alone_records_nothing(fund, capsys):
    assess(fund)
    fund("trade-preview", "NVDA", "buy", "--quantity", "50", "--price", "180")
    assert decisions_of(fund) == []


def test_previewing_without_an_assessment_is_refused(fund, capsys):
    capsys.readouterr()
    assert fund("trade-preview", "NVDA", "buy", "--quantity", "10", "--price", "180") == 2
    error = capsys.readouterr().err
    assert "has no assessment" in error
    assert "before its capital consequence is visible" in error


def test_accepting_an_out_of_policy_trade_is_refused(fund, capsys):
    assess(fund)
    capsys.readouterr()
    assert fund("trade-preview", "NVDA", "buy", "--quantity", "50", "--price", "180",
                "--decide", "accept", "--rationale", "I want it") == 2
    assert "outside policy" in capsys.readouterr().err


def test_reducing_to_the_policy_limit(fund, capsys):
    assess(fund)
    capsys.readouterr()
    assert fund("trade-preview", "NVDA", "buy", "--quantity", "50", "--price", "180",
                "--as-of", "2026-08-16",
                "--decide", "reduce", "--rationale", "Loss budget binds") == 0
    assert "reduced_to_policy_limit" in capsys.readouterr().out

    record = decisions_of(fund)[-1]
    assert record["outcome"]["final_quantity"] == "18"
    assert record["contemplated"]["quantity"] == "50"
    assert record["policy_evaluation"]["binding_constraint"] == "downside_capacity"
    assert record["mode"] == "shadow"


def test_overruling_the_policy_needs_a_reason_code(fund, capsys):
    assess(fund)
    capsys.readouterr()
    assert fund("trade-preview", "NVDA", "buy", "--quantity", "50", "--price", "180",
                "--decide", "outside-policy", "--rationale", "conviction") == 2
    assert "--reason-code" in capsys.readouterr().err


def test_overruling_the_policy_is_recorded_as_such(fund):
    assess(fund)
    fund("trade-preview", "NVDA", "buy", "--quantity", "50", "--price", "180",
         "--decide", "outside-policy", "--reason-code", "owner.override",
         "--rationale", "Deliberately larger than policy; revisit at review")
    record = decisions_of(fund)[-1]
    assert record["outcome"]["decision"] == "recorded_outside_policy"
    assert record["outcome"]["reason_code"] == "owner.override"
    assert record["policy_evaluation"]["within_policy"] is False


def test_cancelling_is_a_decision_worth_keeping(fund):
    assess(fund)
    fund("trade-preview", "NVDA", "buy", "--quantity", "50", "--price", "180",
         "--decide", "cancel", "--rationale", "Not at this price")
    record = decisions_of(fund)[-1]
    assert record["outcome"]["decision"] == "cancelled"
    assert record["outcome"]["final_quantity"] == "0"


def test_an_assessment_the_owner_disowns_cannot_buy(fund, capsys):
    assess(fund, "--would-not-accept")
    capsys.readouterr()
    assert fund("trade-preview", "NVDA", "buy", "--quantity", "10", "--price", "180",
                "--decide", "reduce", "--rationale", "anyway") == 2
    assert "would not accept its downside from scratch" in capsys.readouterr().err


def test_a_disowned_assessment_still_previews_with_a_warning(fund, capsys):
    assess(fund, "--would-not-accept")
    capsys.readouterr()
    assert fund("trade-preview", "NVDA", "buy", "--quantity", "10", "--price", "180") == 0
    assert "answered NO to accepting this downside" in capsys.readouterr().out


def test_a_watchlist_assessment_sizes_to_nothing(fund, capsys):
    assess(fund, readiness="watchlist")
    capsys.readouterr()
    fund("trade-preview", "NVDA", "buy", "--quantity", "10", "--price", "180")
    output = capsys.readouterr().out
    assert "readiness weight      0.00%" in output
    assert "OUTSIDE POLICY" in output


def test_selling_more_than_is_held_is_refused_in_the_preview(fund, capsys):
    assess(fund)
    capsys.readouterr()
    assert fund("trade-preview", "NVDA", "sell", "--quantity", "10", "--price", "180") == 2
    assert "only 0 are held" in capsys.readouterr().err


def test_live_mode_is_opt_in(fund):
    assess(fund)
    fund("trade-preview", "NVDA", "buy", "--quantity", "10", "--price", "180",
         "--decide", "reduce", "--rationale", "x", "--live")
    assert decisions_of(fund)[-1]["mode"] == "live"


# ------------------------------------------------------------- trade-add

def test_a_fill_is_bound_to_its_decision(fund, capsys):
    assess(fund)
    fund("trade-preview", "NVDA", "buy", "--quantity", "50", "--price", "180",
         "--as-of", "2026-08-16", "--decide", "reduce", "--rationale", "budget binds")
    decision_id = decisions_of(fund)[-1]["decision_id"]

    capsys.readouterr()
    assert fund("trade-add", "--decision", decision_id, "--quantity", "18",
                "--price", "181.2", "--date", "2026-08-17") == 0
    assert "fills decision" in capsys.readouterr().out

    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    fill = ledger.account_events()[-1]
    assert fill["decision_id"] == decision_id
    assert fill["quantity"] == "18"


def test_a_fill_that_differs_from_the_decision_says_so(fund, capsys):
    assess(fund)
    fund("trade-preview", "NVDA", "buy", "--quantity", "50", "--price", "180",
         "--as-of", "2026-08-16", "--decide", "reduce", "--rationale", "budget binds")
    decision_id = decisions_of(fund)[-1]["decision_id"]

    capsys.readouterr()
    fund("trade-add", "--decision", decision_id, "--quantity", "15", "--price", "181.2")
    assert "the decision was for 18 shares, this fill is 15" in capsys.readouterr().out


def test_a_fill_needs_a_real_decision(fund, capsys):
    capsys.readouterr()
    assert fund("trade-add", "--decision", "DEC-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f",
                "--quantity", "1", "--price", "1") == 2
    assert "no such decision" in capsys.readouterr().err


# ---------------------------------------------------------------- review

def test_review_shows_the_book_against_its_ceilings(fund, capsys):
    assess(fund)
    fund("trade-preview", "NVDA", "buy", "--quantity", "50", "--price", "180",
         "--as-of", "2026-08-16", "--decide", "reduce", "--rationale", "budget binds")
    decision_id = decisions_of(fund)[-1]["decision_id"]
    fund("trade-add", "--decision", decision_id, "--quantity", "18", "--price", "181.2",
         "--date", "2026-08-17")

    capsys.readouterr()
    assert fund("review", "--price", "NVDA=185", "--as-of", "2026-08-31") == 0
    output = capsys.readouterr().out
    assert "MONTHLY REVIEW" in output
    assert "NVDA" in output
    assert "starter" in output
    assert "Holding is a decision" in output


def test_the_first_review_admits_it_has_no_peak_yet(fund, capsys):
    fund("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    capsys.readouterr()
    fund("review", "--price", "NVDA=100", "--as-of", "2026-08-31")
    assert "a peak needs a second review" in capsys.readouterr().out


def test_drawdown_appears_once_there_is_a_history(fund, capsys):
    fund("open", "position", "--security", "NVDA", "--quantity", "100", "--date", "2026-08-01")
    # NAV 120,000 (100,000 cash + 100 x 200) then 102,000 (100 x 20): exactly -15%.
    fund("review", "--price", "NVDA=200", "--as-of", "2026-08-31")
    capsys.readouterr()
    fund("review", "--price", "NVDA=20", "--as-of", "2026-09-30")
    output = capsys.readouterr().out
    assert "-15.00% from a peak of 120,000.00" in output
    assert "freeze_additions" in output


def test_holding_is_recorded_as_a_decision(fund, capsys):
    assess(fund)
    fund("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    capsys.readouterr()
    assert fund("review", "--price", "NVDA=185", "--as-of", "2026-08-31",
                "--no-change", "NVDA", "--rationale", "Thesis intact, drift inside the band") == 0
    assert "no_change" in capsys.readouterr().out
    assert decisions_of(fund)[-1]["outcome"]["decision"] == "no_change"


def test_holding_with_an_open_adjudication_is_marked(fund):
    assess(fund)
    fund("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    fund("review", "--price", "NVDA=185", "--as-of", "2026-08-31", "--no-change", "NVDA",
         "--rationale", "Holding while the filing is still being read", "--pending-review")
    assert decisions_of(fund)[-1]["outcome"]["decision"] == "no_change_with_pending_review"


def test_no_change_needs_a_rationale(fund, capsys):
    assess(fund)
    fund("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    capsys.readouterr()
    assert fund("review", "--price", "NVDA=185", "--no-change", "NVDA") == 2
    assert "holding is a decision too" in capsys.readouterr().err


def test_review_flags_a_position_with_no_assessment(fund, capsys):
    fund("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    capsys.readouterr()
    fund("review", "--price", "NVDA=185", "--as-of", "2026-08-31")
    assert "NO ASSESSMENT" in capsys.readouterr().out


def test_review_flags_an_overdue_assessment(fund, capsys):
    assess(fund)
    fund("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    capsys.readouterr()
    fund("review", "--price", "NVDA=185", "--as-of", "2027-01-31")
    assert "REVIEW DUE" in capsys.readouterr().out


def test_review_without_prices_stops_rather_than_guessing(fund, capsys):
    fund("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    capsys.readouterr()
    assert fund("review") == 1
    assert "NAV unavailable" in capsys.readouterr().out


# ---------------------------------------------------------------- report

def test_the_report_is_a_self_contained_file(fund, tmp_path, capsys):
    assess(fund)
    fund("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    destination = tmp_path / "out" / "report.html"

    capsys.readouterr()
    assert fund("report", "--price", "NVDA=185", "--as-of", "2026-08-31",
                "--out", str(destination)) == 0
    page = destination.read_text(encoding="utf-8")

    assert "<!doctype html>" in page
    assert "http://" not in page and "https://" not in page
    assert "<script" not in page
    assert "NVDA" in page
    assert "Positions" in page and "Recent decisions" in page


def test_the_report_is_regenerable_and_identical(fund, tmp_path):
    assess(fund)
    fund("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    first, second = tmp_path / "a.html", tmp_path / "b.html"
    fund("report", "--price", "NVDA=185", "--as-of", "2026-08-31", "--out", str(first))
    fund("report", "--price", "NVDA=185", "--as-of", "2026-08-31", "--out", str(second))

    def without_timestamp(text: str) -> list[str]:
        return [line for line in text.splitlines() if "Generated" not in line]

    assert without_timestamp(first.read_text(encoding="utf-8")) == \
           without_timestamp(second.read_text(encoding="utf-8"))


def test_the_report_refuses_to_render_a_partial_nav(fund, capsys):
    fund("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    capsys.readouterr()
    assert fund("report") == 2
    assert "NAV is unavailable" in capsys.readouterr().err
