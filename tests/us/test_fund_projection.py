"""Positions, cash and NAV folded from events.

The core fixture is arithmetic a person can check on paper -- that is the
point of it. Every number below is reachable with a pencil.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from adapter.fund import ids, projection, store
from adapter.fund.errors import ProjectionError
from adapter.fund.money import Money, to_string

RECORDED_AT = "2026-08-16T13:05:00Z"
USD = "USD"


def usd(amount):
    return {"amount": str(amount), "currency": USD}


def event(event_type, date, **fields):
    document = {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": event_type,
        "effective_date": date,
        "recorded_at": RECORDED_AT,
    }
    document.update(fields)
    return document


def hand_checked_book():
    """A book whose every figure can be verified by hand.

        opening cash                                   100000
        opening NVDA  100 sh @ 90 known    cost  9000
        opening GOOGL  50 sh, cost unknown
        deposit                             +5000     105000
        buy NVDA      100 sh @ 110         -11000      94000   cost 20000, avg 100
        dividend NVDA                        +400      94400
        sell NVDA      50 sh @ 130, fee 10  +6490     100890   realized +1490
        fee                                   -25     100865
        withdrawal                          -1000      99865

        NVDA  150 sh, cost 15000, avg 100
        GOOGL  50 sh, cost unknown
    """
    return [
        event("opening_cash", "2026-08-01", cash_amount=usd(100000)),
        event("opening_position", "2026-08-01", security_id="sec:nvda", quantity="100",
              cost_basis_status="known", unit_cost=usd(90)),
        event("opening_position", "2026-08-01", security_id="sec:googl", quantity="50",
              cost_basis_status="unknown"),
        event("deposit", "2026-08-03", cash_amount=usd(5000)),
        event("buy", "2026-08-05", security_id="sec:nvda", quantity="100", price=usd(110)),
        event("dividend", "2026-08-07", security_id="sec:nvda", cash_amount=usd(400)),
        event("sell", "2026-08-10", security_id="sec:nvda", quantity="50", price=usd(130),
              fee=usd(10)),
        event("fee", "2026-08-11", cash_amount=usd(25)),
        event("withdrawal", "2026-08-12", cash_amount=usd(1000)),
    ]


# ------------------------------------------------------------------- folding

def test_hand_checked_book_matches_the_pencil():
    state = projection.project(hand_checked_book())

    assert to_string(state.cash_in(USD).amount) == "99865"

    nvda = state.positions["sec:nvda"]
    assert to_string(nvda.quantity) == "150"
    assert nvda.cost_basis.known
    assert to_string(nvda.cost_basis.total.amount) == "15000"
    assert to_string(nvda.cost_basis.per_share.amount) == "100"

    googl = state.positions["sec:googl"]
    assert to_string(googl.quantity) == "50"
    assert not googl.cost_basis.known

    assert to_string(state.realized_pnl[USD].amount) == "1490"
    assert projection.total_realized(state, USD).amount == Decimal(1490)


def test_a_buy_fee_lands_in_the_cost_basis():
    state = projection.project([
        event("opening_cash", "2026-08-01", cash_amount=usd(10000)),
        event("buy", "2026-08-02", security_id="sec:nvda", quantity="10", price=usd(100),
              fee=usd(5)),
    ])
    assert to_string(state.cash_in(USD).amount) == "8995"
    assert to_string(state.positions["sec:nvda"].cost_basis.total.amount) == "1005"


def test_an_unknown_cost_basis_is_announced_not_guessed():
    state = projection.project([
        event("opening_position", "2026-08-01", security_id="sec:googl", quantity="50",
              cost_basis_status="unknown"),
    ])
    assert not state.positions["sec:googl"].cost_basis.known
    assert state.positions["sec:googl"].cost_basis.total is None
    assert any("cost basis unknown" in w for w in state.warnings)


def test_selling_an_unknown_basis_position_makes_realized_pnl_incomplete():
    state = projection.project([
        event("opening_cash", "2026-08-01", cash_amount=usd(1000)),
        event("opening_position", "2026-08-01", security_id="sec:googl", quantity="50",
              cost_basis_status="unknown"),
        event("sell", "2026-08-05", security_id="sec:googl", quantity="10", price=usd(200)),
    ])
    assert to_string(state.cash_in(USD).amount) == "3000"
    assert not state.realized_pnl_complete
    assert projection.total_realized(state, USD) is None


def test_holding_an_unknown_basis_position_does_not_spoil_realized_pnl():
    """The gap belongs to that position until its shares are actually sold."""
    state = projection.project(hand_checked_book())
    assert state.realized_pnl_complete


def test_selling_more_than_is_held_is_a_data_error():
    with pytest.raises(ProjectionError, match="shorting is disabled"):
        projection.project([
            event("opening_position", "2026-08-01", security_id="sec:nvda", quantity="10",
                  cost_basis_status="unknown"),
            event("sell", "2026-08-05", security_id="sec:nvda", quantity="11", price=usd(100)),
        ])


def test_a_split_changes_the_count_not_what_was_paid():
    state = projection.project([
        event("opening_position", "2026-08-01", security_id="sec:nvda", quantity="100",
              cost_basis_status="known", unit_cost=usd(400)),
        event("quantity_adjustment", "2026-08-05", security_id="sec:nvda", quantity="300",
              adjustment_reason="stock_split", note="4-for-1"),
    ])
    position = state.positions["sec:nvda"]
    assert to_string(position.quantity) == "400"
    assert to_string(position.cost_basis.total.amount) == "40000"
    assert to_string(position.cost_basis.per_share.amount) == "100"


def test_a_reverse_split_may_not_drive_the_count_negative():
    with pytest.raises(ProjectionError, match="negative"):
        projection.project([
            event("opening_position", "2026-08-01", security_id="sec:nvda", quantity="10",
                  cost_basis_status="unknown"),
            event("quantity_adjustment", "2026-08-05", security_id="sec:nvda", quantity="-11",
                  adjustment_reason="reverse_split", note="wrong"),
        ])


def test_negative_cash_is_flagged_because_leverage_is_disabled():
    state = projection.project([
        event("opening_cash", "2026-08-01", cash_amount=usd(100)),
        event("buy", "2026-08-02", security_id="sec:nvda", quantity="10", price=usd(50)),
    ])
    assert any("leverage is disabled" in w for w in state.warnings)


# --------------------------------------------------------------- corrections

def test_a_replacement_supersedes_the_original():
    original = event("buy", "2026-08-05", security_id="sec:nvda", quantity="100", price=usd(110))
    fixed = event("buy", "2026-08-05", security_id="sec:nvda", quantity="10", price=usd(110),
                  corrects_event_id=original["event_id"])
    state = projection.project([
        event("opening_cash", "2026-08-01", cash_amount=usd(100000)),
        original,
        fixed,
    ])
    assert to_string(state.positions["sec:nvda"].quantity) == "10"
    assert to_string(state.cash_in(USD).amount) == "98900"
    assert state.events_superseded == 1


def test_a_void_removes_its_target_and_adds_nothing():
    original = event("buy", "2026-08-05", security_id="sec:nvda", quantity="100", price=usd(110))
    void = event("correction", "2026-08-06", corrects_event_id=original["event_id"],
                 note="entered twice from the statement")
    state = projection.project([
        event("opening_cash", "2026-08-01", cash_amount=usd(100000)),
        original,
        void,
    ])
    assert "sec:nvda" not in state.open_positions()
    assert to_string(state.cash_in(USD).amount) == "100000"


# ------------------------------------------------------------------ valuation

def prices(**overrides):
    base = {"sec:nvda": Money.parse("120", USD), "sec:googl": Money.parse("200", USD)}
    base.update(overrides)
    return base


def test_nav_and_weights():
    state = projection.project(hand_checked_book())
    valuation = projection.value(state, prices(), as_of="2026-08-14", base_currency=USD)

    # 99865 cash + 150x120 + 50x200 = 99865 + 18000 + 10000
    assert to_string(valuation.nav.amount) == "127865"
    assert to_string(valuation.invested.amount) == "28000"
    assert to_string(valuation.cash.amount) == "99865"

    nvda = next(p for p in valuation.positions if p.security_id == "sec:nvda")
    assert round(nvda.weight, 6) == round(Decimal(18000) / Decimal(127865), 6)


def test_weights_and_cash_add_to_one():
    state = projection.project(hand_checked_book())
    valuation = projection.value(state, prices(), as_of="2026-08-14", base_currency=USD)
    total = sum((p.weight for p in valuation.positions), Decimal(0)) + valuation.cash_weight
    assert abs(total - Decimal(1)) < Decimal("0.0000000001")


def test_unrealized_pnl_is_withheld_when_the_cost_basis_is_unknown():
    state = projection.project(hand_checked_book())
    valuation = projection.value(state, prices(), as_of="2026-08-14", base_currency=USD)

    nvda = next(p for p in valuation.positions if p.security_id == "sec:nvda")
    assert to_string(nvda.unrealized_pnl.amount) == "3000"  # 18000 - 15000

    googl = next(p for p in valuation.positions if p.security_id == "sec:googl")
    assert googl.unrealized_pnl is None
    assert googl.unrealized_unavailable_reason == "cost_basis_unknown"
    assert googl.market_value is not None  # the position is still valued


def test_a_missing_price_makes_nav_unavailable_not_partial():
    state = projection.project(hand_checked_book())
    valuation = projection.value(
        state, {"sec:nvda": Money.parse("120", USD)}, as_of="2026-08-14", base_currency=USD
    )
    assert valuation.nav is None
    assert not valuation.nav_available
    assert valuation.missing_prices == ("sec:googl",)
    assert any("NAV unavailable" in w for w in valuation.warnings)


def test_a_closed_position_leaves_the_valuation():
    state = projection.project([
        event("opening_cash", "2026-08-01", cash_amount=usd(10000)),
        event("buy", "2026-08-02", security_id="sec:nvda", quantity="10", price=usd(100)),
        event("sell", "2026-08-03", security_id="sec:nvda", quantity="10", price=usd(120)),
    ])
    valuation = projection.value(state, prices(), as_of="2026-08-14", base_currency=USD)
    assert valuation.positions == ()
    assert to_string(valuation.nav.amount) == "10200"


def test_foreign_cash_is_refused_rather_than_silently_converted():
    state = projection.project([
        event("opening_cash", "2026-08-01", cash_amount={"amount": "5000", "currency": "EUR"}),
    ])
    with pytest.raises(ProjectionError, match="dated rate"):
        projection.value(state, {}, as_of="2026-08-14", base_currency=USD)


def test_deployable_capital_leaves_the_operational_floor_alone():
    state = projection.project(hand_checked_book())
    valuation = projection.value(state, prices(), as_of="2026-08-14", base_currency=USD)
    assert projection.deployable_capital_fraction(valuation, 200) == Decimal("0.98")


# ------------------------------------------------------- replay & idempotency

def test_the_state_replays_from_a_rebuilt_database(tmp_path):
    book = hand_checked_book()

    first = store.open_ledger(path=tmp_path / "first.sqlite3")
    first.commit(store.events_from(book))
    original = projection.project(first.account_events())

    rebuilt_path = tmp_path / "rebuilt.sqlite3"
    second = store.open_ledger(path=rebuilt_path)
    second.commit(store.events_from(first.account_events()))
    replayed = projection.project(second.account_events())

    assert to_string(replayed.cash_in(USD).amount) == to_string(original.cash_in(USD).amount)
    assert {sid: to_string(p.quantity) for sid, p in replayed.positions.items()} == \
           {sid: to_string(p.quantity) for sid, p in original.positions.items()}
    assert to_string(replayed.realized_pnl[USD].amount) == to_string(original.realized_pnl[USD].amount)


def test_importing_the_opening_book_twice_does_not_double_anything(tmp_path):
    ledger = store.open_ledger(path=tmp_path / "ledger.sqlite3")
    opening = [e for e in hand_checked_book() if e["event_type"].startswith("opening_")]
    ledger.commit(store.events_from(opening))

    from adapter.fund.errors import LedgerError

    again = [dict(e, event_id=ids.new_id(ids.ACCOUNT_EVENT)) for e in opening]
    with pytest.raises(LedgerError):
        ledger.commit(store.events_from(again))

    state = projection.project(ledger.account_events())
    assert to_string(state.cash_in(USD).amount) == "100000"
    assert to_string(state.positions["sec:nvda"].quantity) == "100"


def test_projection_is_pure_no_matter_how_often_it_runs():
    book = hand_checked_book()
    first = projection.project(book)
    second = projection.project(book)
    assert to_string(first.cash_in(USD).amount) == to_string(second.cash_in(USD).amount)
    assert first.events_applied == second.events_applied
