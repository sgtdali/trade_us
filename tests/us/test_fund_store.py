"""The ledger's guarantees: one way in, nothing edited, nothing doubled."""

from __future__ import annotations

import sqlite3
import threading

import pytest

from adapter.fund import ids, store
from adapter.fund.errors import LedgerError, SchemaViolation

RECORDED_AT = "2026-08-16T13:05:00Z"


@pytest.fixture()
def ledger(tmp_path):
    return store.open_ledger(path=tmp_path / "ledger.sqlite3")


def buy(security="sec:nvda-common", quantity="18", price="181.2", date="2026-08-14", **extra):
    document = {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": "buy",
        "effective_date": date,
        "recorded_at": RECORDED_AT,
        "security_id": security,
        "quantity": quantity,
        "price": {"amount": price, "currency": "USD"},
    }
    document.update(extra)
    return document


def opening_position(security="sec:nvda-common", quantity="100"):
    return {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": "opening_position",
        "effective_date": "2026-08-01",
        "recorded_at": RECORDED_AT,
        "security_id": security,
        "quantity": quantity,
        "cost_basis_status": "unknown",
    }


def opening_cash(amount="20000", currency="USD"):
    return {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": "opening_cash",
        "effective_date": "2026-08-01",
        "recorded_at": RECORDED_AT,
        "cash_amount": {"amount": amount, "currency": currency},
    }


def write(document):
    return store.Write(kind=store.ACCOUNT_EVENT.name, document=document)


# ------------------------------------------------------------------ migration

def test_migration_creates_the_schema(ledger):
    assert ledger.schema_version() == max(m.version for m in store.MIGRATIONS)


def test_migration_is_idempotent(ledger):
    before = ledger.schema_version()
    ledger.migrate()
    ledger.migrate()
    assert ledger.schema_version() == before


def test_exact_decimals_are_stored_as_text(ledger):
    """NUMERIC affinity would coerce '181.2' to a float and lose the cent."""
    ledger.commit([write(buy())])
    with ledger.connection() as connection:
        row = connection.execute(
            "SELECT typeof(document) AS document_type FROM account_event"
        ).fetchone()
    assert row["document_type"] == "text"


# ---------------------------------------------------------------- write gate

def test_commit_writes_and_returns_ids(ledger):
    document = buy()
    result = ledger.commit([write(document)])
    assert result.written == (document["event_id"],)
    assert ledger.count() == 1


def test_commit_validates_before_writing(ledger):
    with pytest.raises(SchemaViolation):
        ledger.commit([write(buy(quantity="-5"))])
    assert ledger.count() == 0


def test_commit_rejects_an_unknown_record_kind(ledger):
    with pytest.raises(LedgerError, match="unknown record kind"):
        ledger.commit([store.Write(kind="thesis", document=buy())])


def test_a_batch_lands_whole_or_not_at_all(ledger):
    """A half-written opening book reconciles against nothing."""
    good, bad = buy(), buy(quantity="0")
    with pytest.raises(SchemaViolation):
        ledger.commit([write(good), write(bad)])
    assert ledger.count() == 0


def test_the_same_id_twice_in_one_batch_is_refused(ledger):
    document = buy()
    with pytest.raises(LedgerError, match="same identifier"):
        ledger.commit([write(document), write(dict(document))])
    assert ledger.count() == 0


def test_empty_batch_is_a_no_op(ledger):
    assert ledger.commit([]).written == ()


# ---------------------------------------------------------------- immutability

def test_rows_cannot_be_updated(ledger):
    ledger.commit([write(buy())])
    with ledger.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE account_event SET effective_date = '2020-01-01'")


def test_rows_cannot_be_deleted(ledger):
    ledger.commit([write(buy())])
    with ledger.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute("DELETE FROM account_event")
    assert ledger.count() == 1


# ------------------------------------------------------------------ duplicates

def test_entering_the_same_trade_twice_is_refused(ledger):
    document = buy()
    ledger.commit([write(document)])

    again = dict(document)
    again["event_id"] = ids.new_id(ids.ACCOUNT_EVENT)
    again["recorded_at"] = "2026-08-16T18:00:00Z"
    with pytest.raises(LedgerError, match="duplicates an existing record"):
        ledger.commit([write(again)])
    assert ledger.count() == 1


def test_a_genuine_repeat_can_be_recorded_deliberately(ledger):
    document = buy()
    ledger.commit([write(document)])

    again = dict(document)
    again["event_id"] = ids.new_id(ids.ACCOUNT_EVENT)
    result = ledger.commit([write(again)], allow_duplicate=True)

    assert ledger.count() == 2
    assert len(result.duplicates) == 1
    assert result.duplicates[0].existing_ids == (document["event_id"],)


def test_the_digest_ignores_bookkeeping_fields(ledger):
    document = buy()
    other = dict(document)
    other["event_id"] = ids.new_id(ids.ACCOUNT_EVENT)
    other["recorded_at"] = "2027-01-01T00:00:00Z"
    other["note"] = "typed in from the statement"
    assert store.content_digest(document) == store.content_digest(other)


def test_the_digest_notices_a_different_price(ledger):
    assert store.content_digest(buy(price="181.2")) != store.content_digest(buy(price="181.3"))


# -------------------------------------------------------------- opening book

def test_the_opening_book_cannot_be_imported_twice(ledger):
    """Re-running the import must not double every position and the cash."""
    book = [write(opening_position("sec:nvda-common")),
            write(opening_position("sec:googl", quantity="40")),
            write(opening_cash())]
    ledger.commit(book)
    assert ledger.count() == 3

    again = [write(opening_position("sec:nvda-common")),
             write(opening_position("sec:googl", quantity="40")),
             write(opening_cash())]
    with pytest.raises(LedgerError):
        ledger.commit(again)
    assert ledger.count() == 3


def test_a_second_opening_row_for_one_security_is_refused_even_when_different(ledger):
    ledger.commit([write(opening_position("sec:nvda-common", quantity="100"))])
    with pytest.raises(LedgerError, match="rejected by the ledger"):
        ledger.commit([write(opening_position("sec:nvda-common", quantity="120"))])


def test_one_opening_cash_row_per_currency(ledger):
    ledger.commit([write(opening_cash("20000", "USD"))])
    ledger.commit([write(opening_cash("5000", "EUR"))])
    with pytest.raises(LedgerError, match="rejected by the ledger"):
        ledger.commit([write(opening_cash("30000", "USD"))])


# -------------------------------------------------------------- corrections

def test_a_correction_must_point_at_a_real_event(ledger):
    ghost = ids.new_id(ids.ACCOUNT_EVENT)
    correction = {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": "correction",
        "effective_date": "2026-08-15",
        "recorded_at": RECORDED_AT,
        "corrects_event_id": ghost,
        "note": "never happened",
    }
    with pytest.raises(LedgerError, match="rejected by the ledger"):
        ledger.commit([write(correction)])


def test_an_event_can_only_be_superseded_once(ledger):
    original = buy()
    ledger.commit([write(original)])

    first = buy(quantity="20", corrects_event_id=original["event_id"])
    ledger.commit([write(first)])

    second = buy(quantity="22", corrects_event_id=original["event_id"])
    with pytest.raises(LedgerError, match="rejected by the ledger"):
        ledger.commit([write(second)])


def test_a_corrected_opening_position_is_exempt_from_the_single_opening_rule(ledger):
    original = opening_position("sec:nvda-common", quantity="100")
    ledger.commit([write(original)])

    fixed = opening_position("sec:nvda-common", quantity="120")
    fixed["corrects_event_id"] = original["event_id"]
    ledger.commit([write(fixed)])

    assert ledger.count() == 2


# ------------------------------------------------------------------- reading

def test_events_come_back_in_replay_order(ledger):
    late = buy(date="2026-08-20", price="190")
    early = buy(date="2026-08-01", price="170")
    middle = buy(date="2026-08-10", price="180")
    ledger.commit([write(late), write(early), write(middle)])

    dates = [event["effective_date"] for event in ledger.account_events()]
    assert dates == ["2026-08-01", "2026-08-10", "2026-08-20"]


def test_events_can_be_read_for_one_security(ledger):
    ledger.commit([write(buy("sec:nvda-common")), write(buy("sec:googl", price="200"))])
    assert len(ledger.account_events(security_id="sec:googl")) == 1


def test_stored_document_round_trips_exactly(ledger):
    document = buy(fee={"amount": "1.25", "currency": "USD"}, note="statement line 14")
    ledger.commit([write(document)])
    assert ledger.account_events()[0] == document


# --------------------------------------------------------------- concurrency

def test_concurrent_writers_do_not_lose_events(tmp_path):
    """BEGIN IMMEDIATE plus a busy timeout, not a file lock."""
    path = tmp_path / "ledger.sqlite3"
    store.open_ledger(path=path)

    writers, per_writer = 4, 10
    failures: list[BaseException] = []
    barrier = threading.Barrier(writers)

    def run(worker: int) -> None:
        try:
            own = store.Ledger(path=path)
            barrier.wait()
            for n in range(per_writer):
                own.commit([write(buy(security=f"sec:worker-{worker}", price=f"1{worker}{n}.5"))])
        except BaseException as exc:  # noqa: BLE001 -- reported after the join
            failures.append(exc)

    threads = [threading.Thread(target=run, args=(worker,)) for worker in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not failures, failures
    assert store.Ledger(path=path).count() == writers * per_writer
