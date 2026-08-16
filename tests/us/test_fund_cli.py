"""The operator surface, exercised the way it is actually used."""

from __future__ import annotations

import json

import pytest

from adapter.fund import cli


@pytest.fixture()
def book(tmp_path):
    """A run() helper bound to a private ledger and instrument master."""
    prefix = ["--ledger", str(tmp_path / "ledger.sqlite3"),
              "--instruments", str(tmp_path / "instruments.json")]

    def run(*argv: str) -> int:
        return cli.main(prefix + list(argv))

    run.tmp_path = tmp_path  # type: ignore[attr-defined]
    return run


@pytest.fixture()
def stocked(book):
    book("init")
    book("instrument", "add", "--ticker", "NVDA", "--name", "NVIDIA Corporation")
    book("instrument", "add", "--ticker", "GOOGL", "--name", "Alphabet Inc.",
         "--issuer", "iss:alphabet", "--share-class", "A")
    return book


# ----------------------------------------------------------------------- init

def test_init_creates_the_ledger_and_the_instrument_master(book, capsys):
    assert book("init") == 0
    output = capsys.readouterr().out
    assert "schema    version " in output
    assert "base currency USD" in output
    assert (book.tmp_path / "ledger.sqlite3").is_file()
    assert (book.tmp_path / "instruments.json").is_file()


def test_init_is_repeatable(book):
    assert book("init") == 0
    assert book("init") == 0


# ---------------------------------------------------------------- instruments

def test_registering_a_security(stocked, capsys):
    capsys.readouterr()
    assert stocked("instrument", "list") == 0
    output = capsys.readouterr().out
    assert "NVDA" in output and "sec:nvda" in output


def test_two_share_classes_share_an_issuer(stocked, book):
    stocked("instrument", "add", "--ticker", "GOOG", "--name", "Alphabet Inc.",
            "--issuer", "iss:alphabet", "--share-class", "C")
    master = json.loads((book.tmp_path / "instruments.json").read_text(encoding="utf-8"))
    alphabet = [s for s in master["securities"] if s["issuer_id"] == "iss:alphabet"]
    assert {s["security_id"] for s in alphabet} == {"sec:googl", "sec:goog"}
    assert len([i for i in master["issuers"] if i["issuer_id"] == "iss:alphabet"]) == 1


def test_registering_the_same_ticker_twice_is_refused(stocked, capsys):
    assert stocked("instrument", "add", "--ticker", "NVDA", "--name", "NVIDIA Corporation") == 2
    assert "already registered" in capsys.readouterr().err


def test_an_unknown_ticker_says_how_to_add_it(stocked, capsys):
    capsys.readouterr()
    assert stocked("trade", "record", "buy", "--security", "AMZN",
                   "--quantity", "10", "--price", "200") == 2
    error = capsys.readouterr().err
    assert "no active listing for ticker 'AMZN'" in error
    assert "fund instrument add" in error


# --------------------------------------------------------------- opening book

def test_opening_a_position_with_a_known_cost(stocked, capsys):
    capsys.readouterr()
    assert stocked("open", "position", "--security", "NVDA", "--quantity", "100",
                   "--unit-cost", "90", "--date", "2026-08-01") == 0
    assert "opened position" in capsys.readouterr().out


def test_opening_a_position_with_an_unknown_cost_says_so(stocked, capsys):
    capsys.readouterr()
    stocked("open", "position", "--security", "GOOGL", "--quantity", "50", "--date", "2026-08-01")
    assert "cost basis unknown" in capsys.readouterr().out


def test_the_opening_book_cannot_be_entered_twice(stocked, capsys):
    stocked("open", "cash", "--amount", "100000", "--date", "2026-08-01")
    capsys.readouterr()
    assert stocked("open", "cash", "--amount", "100000", "--date", "2026-08-01") == 2
    assert "already recorded" in capsys.readouterr().err


# ---------------------------------------------------------------------- trade

def test_recording_a_buy(stocked, capsys):
    capsys.readouterr()
    assert stocked("trade", "record", "buy", "--security", "NVDA", "--quantity", "18",
                   "--price", "181.2", "--fee", "1.25", "--date", "2026-08-14") == 0
    output = capsys.readouterr().out
    assert "recorded buy" in output
    assert "18 x 181.2 = 3261.6 USD" in output


def test_selling_more_than_is_held_is_refused(stocked, capsys):
    stocked("open", "position", "--security", "NVDA", "--quantity", "10", "--date", "2026-08-01")
    stocked("trade", "record", "sell", "--security", "NVDA", "--quantity", "5",
            "--price", "100", "--date", "2026-08-05")
    capsys.readouterr()
    stocked("trade", "record", "sell", "--security", "NVDA", "--quantity", "20",
            "--price", "100", "--date", "2026-08-06")
    assert stocked("positions", "--price", "NVDA=100") == 2
    assert "shorting is disabled" in capsys.readouterr().err


def test_the_same_trade_twice_is_refused_but_can_be_forced(stocked, capsys):
    args = ("trade", "record", "buy", "--security", "NVDA", "--quantity", "18",
            "--price", "181.2", "--date", "2026-08-14")
    assert stocked(*args) == 0
    capsys.readouterr()
    assert stocked(*args) == 2
    assert "--allow-duplicate" in capsys.readouterr().err

    capsys.readouterr()
    assert stocked(*args, "--allow-duplicate") == 0
    assert "recorded anyway" in capsys.readouterr().out


def test_a_dividend_needs_the_security_it_came_from(stocked, capsys):
    capsys.readouterr()
    assert stocked("cash", "record", "dividend", "--amount", "400") == 2
    assert "needs --security" in capsys.readouterr().err


def test_cash_movements_take_a_magnitude(stocked, capsys):
    assert stocked("cash", "record", "deposit", "--amount", "5000", "--date", "2026-08-03") == 0
    assert stocked("cash", "record", "withdrawal", "--amount", "1000", "--date", "2026-08-12") == 0


def test_a_split_is_recorded_as_an_adjustment(stocked, capsys):
    stocked("open", "position", "--security", "NVDA", "--quantity", "100",
            "--unit-cost", "400", "--date", "2026-08-01")
    capsys.readouterr()
    assert stocked("adjust", "--security", "NVDA", "--quantity", "300",
                   "--reason", "stock_split", "--note", "4-for-1") == 0
    assert "stock_split" in capsys.readouterr().out


# ------------------------------------------------------------------ corrections

def _last_event_id(book) -> str:
    from adapter.fund import store

    ledger = store.open_ledger(path=book.tmp_path / "ledger.sqlite3")
    return ledger.account_events()[-1]["event_id"]


def test_correcting_a_quantity_supersedes_the_original(stocked, capsys):
    stocked("open", "cash", "--amount", "100000", "--date", "2026-08-01")
    stocked("trade", "record", "buy", "--security", "NVDA", "--quantity", "100",
            "--price", "110", "--date", "2026-08-05")
    event_id = _last_event_id(stocked)

    capsys.readouterr()
    assert stocked("correct", event_id, "--quantity", "80",
                   "--note", "the statement says 80") == 0
    output = capsys.readouterr().out
    assert "quantity: 100 -> 80" in output
    assert "original row is untouched" in output

    capsys.readouterr()
    stocked("positions", "--price", "NVDA=120")
    assert "80" in capsys.readouterr().out


def test_voiding_an_event_that_never_happened(stocked, capsys):
    stocked("open", "cash", "--amount", "100000", "--date", "2026-08-01")
    stocked("trade", "record", "buy", "--security", "NVDA", "--quantity", "100",
            "--price", "110", "--date", "2026-08-05")
    event_id = _last_event_id(stocked)

    capsys.readouterr()
    assert stocked("correct", event_id, "--void", "--note", "entered twice") == 0
    assert "voided" in capsys.readouterr().out

    capsys.readouterr()
    stocked("positions")
    output = capsys.readouterr().out
    assert "NVDA" not in output
    assert "100,000.00" in output


def test_a_correction_needs_something_to_change(stocked, capsys):
    stocked("open", "cash", "--amount", "100000", "--date", "2026-08-01")
    event_id = _last_event_id(stocked)
    capsys.readouterr()
    assert stocked("correct", event_id, "--note", "hmm") == 2
    assert "nothing to correct" in capsys.readouterr().err


def test_correcting_an_unknown_event_is_refused(stocked, capsys):
    capsys.readouterr()
    assert stocked("correct", "EVT-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f",
                   "--void", "--note", "x") == 2
    assert "no such event" in capsys.readouterr().err


# -------------------------------------------------------------------- reading

def test_positions_reports_nav_and_weights(stocked, capsys):
    stocked("open", "cash", "--amount", "100000", "--date", "2026-08-01")
    stocked("open", "position", "--security", "NVDA", "--quantity", "100",
            "--unit-cost", "90", "--date", "2026-08-01")
    capsys.readouterr()
    assert stocked("positions", "--price", "NVDA=120", "--as-of", "2026-08-14") == 0
    output = capsys.readouterr().out
    assert "112,000.00" in output          # 100000 cash + 100 x 120
    assert "3,000.00" in output            # unrealized 12000 - 9000
    assert "10.71%" in output              # 12000 / 112000


def test_positions_withholds_nav_when_a_price_is_missing(stocked, capsys):
    stocked("open", "position", "--security", "NVDA", "--quantity", "100", "--date", "2026-08-01")
    capsys.readouterr()
    stocked("positions")
    output = capsys.readouterr().out
    assert "unavailable" in output
    assert "NAV unavailable: no price for sec:nvda" in output


def test_positions_on_an_empty_book(stocked, capsys):
    capsys.readouterr()
    assert stocked("positions") == 0
    assert "the book is empty" in capsys.readouterr().out


def test_events_marks_superseded_rows(stocked, capsys):
    stocked("open", "cash", "--amount", "100000", "--date", "2026-08-01")
    stocked("trade", "record", "buy", "--security", "NVDA", "--quantity", "100",
            "--price", "110", "--date", "2026-08-05")
    event_id = _last_event_id(stocked)
    stocked("correct", event_id, "--quantity", "80", "--note", "statement")

    capsys.readouterr()
    stocked("events")
    output = capsys.readouterr().out
    assert "(superseded)" in output


def test_prices_can_come_from_a_file(stocked, capsys, tmp_path):
    stocked("open", "position", "--security", "NVDA", "--quantity", "100", "--date", "2026-08-01")
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"NVDA": "120"}), encoding="utf-8")

    capsys.readouterr()
    assert stocked("positions", "--prices", str(prices)) == 0
    assert "12,000.00" in capsys.readouterr().out


def test_policy_show_marks_provisional_fields(stocked, capsys):
    capsys.readouterr()
    assert stocked("policy", "show") == 0
    output = capsys.readouterr().out
    assert "(provisional)" in output
    assert "position loss budget" in output
