"""``fund`` -- the operator's surface.

Manual entry is the design, not a stopgap: roughly a dozen transactions a year
do not justify a broker integration, and typing them is the moment the owner
looks at what they actually did.

Every command that writes prints back what it wrote, including the identifier,
because in an append-only ledger the identifier is how a mistake gets fixed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from . import ids, instruments, policy as policy_module, projection, schemas, store
from .errors import FundError, LedgerError
from .money import Money, format_display, to_string

PROGRAM = "fund"


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return date.today().isoformat()


def _money_document(amount: str, currency: str) -> dict[str, str]:
    return Money.parse(amount, currency).to_document()


def _ledger(args: argparse.Namespace) -> store.Ledger:
    return store.open_ledger(path=args.ledger)


def _master(args: argparse.Namespace) -> dict[str, Any]:
    return instruments.load(path=args.instruments)


def _resolve(args: argparse.Namespace, token: str) -> tuple[dict[str, Any], str]:
    master = _master(args)
    return master, instruments.resolve(master, token)


def _commit(ledger: store.Ledger, document: dict[str, Any], *, allow_duplicate: bool) -> str:
    try:
        result = ledger.commit([store.Write(kind=store.ACCOUNT_EVENT.name, document=document)],
                               allow_duplicate=allow_duplicate)
    except LedgerError as exc:
        if "duplicates an existing record" in str(exc):
            existing = str(exc).split("(", 1)[-1].split(")", 1)[0]
            raise LedgerError(
                f"this is identical to an event already recorded ({existing}).\n"
                "  If you really did the same thing twice, add --allow-duplicate."
            ) from exc
        raise
    for warning in result.duplicates:
        print(f"  ! recorded anyway; it repeats {', '.join(warning.existing_ids)}")
    return result.written[0]


def _report(document: dict[str, Any], event_id: str, label: str) -> None:
    print(f"{label}  {event_id}")
    print(f"  effective {document['effective_date']}")


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    print(f"ledger    {ledger.path}")
    print(f"schema    version {ledger.schema_version()}")

    master_path = args.instruments or schemas.repo_root() / instruments.DEFAULT_RELATIVE_PATH
    if not master_path.is_file():
        instruments.save(instruments.empty(_today()), path=master_path)
        print(f"instruments  created {master_path}")
    else:
        print(f"instruments  {master_path}")

    try:
        loaded = policy_module.load()
        print(f"policy    version {loaded['identity']['policy_version']}, "
              f"base currency {loaded['measurement']['base_currency']}")
    except FundError as exc:
        print(f"policy    NOT LOADED: {exc}")
        return 1
    return 0


# --------------------------------------------------------------------------
# instrument
# --------------------------------------------------------------------------

def cmd_instrument_add(args: argparse.Namespace) -> int:
    path = args.instruments or schemas.repo_root() / instruments.DEFAULT_RELATIVE_PATH
    master = instruments.load(path=path) if path.is_file() else instruments.empty(_today())
    master, security_id = instruments.add_security(
        master,
        ticker=args.ticker,
        legal_name=args.name,
        issuer_id=args.issuer,
        share_class=args.share_class,
        cik=args.cik,
        mic=args.mic,
        currency=args.currency,
    )
    master["as_of"] = _today()
    instruments.save(master, path=path)
    print(f"registered  {args.ticker.upper()} -> {security_id}")
    print(f"  issuer    {instruments.issuer_of(master, security_id)}")
    return 0


def cmd_instrument_list(args: argparse.Namespace) -> int:
    master = _master(args)
    if not master["securities"]:
        print("no securities registered yet")
        return 0
    print(f"{'TICKER':<8} {'SECURITY':<24} {'ISSUER':<24} CLASS")
    for entry in sorted(master["securities"], key=lambda s: s["security_id"]):
        ticker = instruments.ticker_for(master, entry["security_id"])
        print(f"{ticker:<8} {entry['security_id']:<24} {entry['issuer_id']:<24} "
              f"{entry.get('share_class', '-')}")
    return 0


# --------------------------------------------------------------------------
# open (the opening book)
# --------------------------------------------------------------------------

def cmd_open_position(args: argparse.Namespace) -> int:
    _, security_id = _resolve(args, args.security)
    document: dict[str, Any] = {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": "opening_position",
        "effective_date": args.date or _today(),
        "recorded_at": _now(),
        "security_id": security_id,
        "quantity": to_string(Decimal(args.quantity)),
    }
    if args.unit_cost is not None:
        document["cost_basis_status"] = "known"
        document["unit_cost"] = _money_document(args.unit_cost, args.currency)
    else:
        document["cost_basis_status"] = "unknown"
    if args.note:
        document["note"] = args.note

    event_id = _commit(_ledger(args), document, allow_duplicate=args.allow_duplicate)
    _report(document, event_id, "opened position")
    print(f"  {document['quantity']} shares of {security_id}")
    if document["cost_basis_status"] == "unknown":
        print("  cost basis unknown -- P&L will not be reported for this position")
    return 0


def cmd_open_cash(args: argparse.Namespace) -> int:
    document = {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": "opening_cash",
        "effective_date": args.date or _today(),
        "recorded_at": _now(),
        "cash_amount": _money_document(args.amount, args.currency),
    }
    if args.note:
        document["note"] = args.note
    event_id = _commit(_ledger(args), document, allow_duplicate=args.allow_duplicate)
    _report(document, event_id, "opened cash")
    print(f"  {document['cash_amount']['amount']} {args.currency}")
    return 0


# --------------------------------------------------------------------------
# trade / cash
# --------------------------------------------------------------------------

def cmd_trade_record(args: argparse.Namespace) -> int:
    _, security_id = _resolve(args, args.security)
    document: dict[str, Any] = {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": args.side,
        "effective_date": args.date or _today(),
        "recorded_at": _now(),
        "security_id": security_id,
        "quantity": to_string(Decimal(args.quantity)),
        "price": _money_document(args.price, args.currency),
    }
    if args.fee is not None:
        document["fee"] = _money_document(args.fee, args.currency)
    if args.decision:
        document["decision_id"] = args.decision
    if args.note:
        document["note"] = args.note

    event_id = _commit(_ledger(args), document, allow_duplicate=args.allow_duplicate)
    consideration = Money.parse(args.price, args.currency).scaled_by(Decimal(args.quantity))
    _report(document, event_id, f"recorded {args.side}")
    print(f"  {document['quantity']} x {args.price} = {consideration}")
    if args.fee:
        print(f"  fee {args.fee} {args.currency}")
    return 0


def cmd_cash_record(args: argparse.Namespace) -> int:
    document: dict[str, Any] = {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": args.kind,
        "effective_date": args.date or _today(),
        "recorded_at": _now(),
        "cash_amount": _money_document(args.amount, args.currency),
    }
    if args.kind == "dividend":
        if not args.security:
            raise FundError("a dividend needs --security: cash with no source is not traceable")
        _, document["security_id"] = _resolve(args, args.security)
    if args.note:
        document["note"] = args.note

    event_id = _commit(_ledger(args), document, allow_duplicate=args.allow_duplicate)
    _report(document, event_id, f"recorded {args.kind}")
    print(f"  {args.amount} {args.currency}")
    return 0


def cmd_adjust(args: argparse.Namespace) -> int:
    _, security_id = _resolve(args, args.security)
    document = {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": "quantity_adjustment",
        "effective_date": args.date or _today(),
        "recorded_at": _now(),
        "security_id": security_id,
        "quantity": to_string(Decimal(args.quantity)),
        "adjustment_reason": args.reason,
        "note": args.note,
    }
    event_id = _commit(_ledger(args), document, allow_duplicate=args.allow_duplicate)
    _report(document, event_id, "recorded adjustment")
    print(f"  {args.reason}: {document['quantity']} shares of {security_id}")
    return 0


# --------------------------------------------------------------------------
# correct
# --------------------------------------------------------------------------

def cmd_correct(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    originals = [e for e in ledger.account_events() if e["event_id"] == args.event_id]
    if not originals:
        raise FundError(f"no such event: {args.event_id}")
    original = originals[0]

    if args.void:
        document: dict[str, Any] = {
            "event_id": ids.new_id(ids.ACCOUNT_EVENT),
            "event_type": "correction",
            "effective_date": args.date or _today(),
            "recorded_at": _now(),
            "corrects_event_id": args.event_id,
            "note": args.note,
        }
        event_id = _commit(ledger, document, allow_duplicate=True)
        print(f"voided     {args.event_id}")
        print(f"  by       {event_id}")
        print(f"  reason   {args.note}")
        return 0

    if args.quantity is None and args.price is None and args.date is None:
        raise FundError(
            "nothing to correct: pass --quantity, --price or --date, or --void to retract it"
        )

    replacement = {k: v for k, v in original.items() if k not in {"event_id", "recorded_at"}}
    replacement["event_id"] = ids.new_id(ids.ACCOUNT_EVENT)
    replacement["recorded_at"] = _now()
    replacement["corrects_event_id"] = args.event_id
    replacement["note"] = args.note
    if args.quantity is not None:
        replacement["quantity"] = to_string(Decimal(args.quantity))
    if args.price is not None:
        replacement["price"] = _money_document(args.price, original["price"]["currency"])
    if args.date is not None:
        replacement["effective_date"] = args.date

    event_id = _commit(ledger, replacement, allow_duplicate=True)
    print(f"corrected  {args.event_id}")
    print(f"  by       {event_id}")
    for key in ("quantity", "price", "effective_date"):
        if original.get(key) != replacement.get(key):
            print(f"  {key}: {original.get(key)} -> {replacement.get(key)}")
    print("  the original row is untouched; the projection honours the correction")
    return 0


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def cmd_events(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    security_id = None
    if args.security:
        _, security_id = _resolve(args, args.security)
    events = ledger.account_events(security_id=security_id)
    if not events:
        print("no events recorded yet")
        return 0

    superseded = {e["corrects_event_id"] for e in events if e.get("corrects_event_id")}
    print(f"{'DATE':<12} {'TYPE':<20} {'SECURITY':<20} {'DETAIL':<24} ID")
    for event in events:
        detail = ""
        if "quantity" in event:
            detail = f"{event['quantity']} sh"
            if "price" in event:
                detail += f" @ {event['price']['amount']}"
        elif "cash_amount" in event:
            detail = f"{event['cash_amount']['amount']} {event['cash_amount']['currency']}"
        mark = "  (superseded)" if event["event_id"] in superseded else ""
        print(f"{event['effective_date']:<12} {event['event_type']:<20} "
              f"{event.get('security_id', '-'):<20} {detail:<24} {event['event_id']}{mark}")
    return 0


def _price_map(args: argparse.Namespace, master: dict[str, Any], currency: str) -> dict[str, Money]:
    prices: dict[str, Money] = {}
    if args.prices:
        raw = json.loads(Path(args.prices).read_text(encoding="utf-8"))
        for token, amount in raw.items():
            prices[instruments.resolve(master, token)] = Money.parse(str(amount), currency)
    for pair in args.price or []:
        token, _, amount = pair.partition("=")
        if not amount:
            raise FundError(f"--price expects TICKER=AMOUNT, got {pair!r}")
        prices[instruments.resolve(master, token)] = Money.parse(amount, currency)
    return prices


def cmd_positions(args: argparse.Namespace) -> int:
    loaded = policy_module.load()
    currency = loaded["measurement"]["base_currency"]
    ledger = _ledger(args)
    master = _master(args)

    state = projection.project(ledger.account_events())
    if not state.open_positions() and state.cash_in(currency).is_zero():
        print("the book is empty")
        return 0

    prices = _price_map(args, master, currency)
    valuation = projection.value(state, prices, as_of=args.as_of or _today(), base_currency=currency)

    print(f"AS OF {valuation.as_of}   base currency {currency}")
    print()
    print(f"{'TICKER':<8} {'QUANTITY':>14} {'PRICE':>12} {'VALUE':>16} {'WEIGHT':>9} {'UNREALIZED':>18}")
    for position in valuation.positions:
        ticker = instruments.ticker_for(master, position.security_id)
        price = format_display(position.price.amount) if position.price else "-"
        market_value = format_display(position.market_value.amount) if position.market_value else "-"
        weight = f"{position.weight * 100:.2f}%" if position.weight is not None else "-"
        if position.unrealized_pnl is not None:
            unrealized = format_display(position.unrealized_pnl.amount)
        else:
            unrealized = f"({position.unrealized_unavailable_reason})"
        print(f"{ticker:<8} {to_string(position.quantity):>14} {price:>12} "
              f"{market_value:>16} {weight:>9} {unrealized:>18}")

    print()
    cash_weight = f"{valuation.cash_weight * 100:.2f}%" if valuation.cash_weight is not None else "-"
    print(f"{'cash':<8} {'':>14} {'':>12} {format_display(valuation.cash.amount):>16} {cash_weight:>9}")
    if valuation.nav is not None:
        print(f"{'NAV':<8} {'':>14} {'':>12} {format_display(valuation.nav.amount):>16}")
    else:
        print(f"{'NAV':<8} {'':>14} {'':>12} {'unavailable':>16}")

    realized = projection.total_realized(state, currency)
    print()
    if realized is not None:
        print(f"realized P&L   {format_display(realized.amount)} {currency}")
    else:
        print("realized P&L   not computable (a disposal had no cost basis)")

    for warning in valuation.warnings:
        print(f"  ! {warning}")
    return 0


def cmd_policy_show(args: argparse.Namespace) -> int:
    loaded = policy_module.load()
    provisional = set(loaded["provisional_fields"])

    def show(pointer: str, label: str) -> None:
        value = policy_module.resolve_pointer(loaded, pointer)
        mark = "  (provisional)" if pointer in provisional else ""
        print(f"  {label:<34} {value}{mark}")

    print(f"capital policy {loaded['identity']['policy_version']}, "
          f"effective {loaded['identity']['effective_from']}")
    print()
    show("/measurement/base_currency", "base currency")
    show("/capacity/max_active_positions", "max active positions")
    show("/concentration/max_security_weight_bps", "max security weight (bp)")
    show("/concentration/max_issuer_weight_bps", "max issuer weight (bp)")
    show("/risk/position_loss_budget_bps_nav", "position loss budget (bp NAV)")
    show("/cash/operational_floor_bps_nav", "operational cash floor (bp NAV)")
    print(f"  {'readiness multipliers':<34} {loaded['sizing']['readiness_multipliers']}")
    print(f"  {'no-trade band':<34} {loaded['trading']['no_trade_band']}")
    print()
    print(f"{len(provisional)} field(s) marked provisional -- see config/fund/capital-policy.notes.md")
    return 0


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", type=Path, default=None, help="path to the ledger database")
    parser.add_argument("--instruments", type=Path, default=None, help="path to the instrument master")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def with_write_flags(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument("--date", help="effective date (YYYY-MM-DD), defaults to today")
        sub.add_argument("--note")
        sub.add_argument("--allow-duplicate", action="store_true",
                         help="record it even though an identical event already exists")
        return sub

    init = subparsers.add_parser("init", help="create the ledger and show what is configured")
    init.set_defaults(handler=cmd_init)

    instrument = subparsers.add_parser("instrument", help="register securities")
    instrument_sub = instrument.add_subparsers(dest="instrument_command", required=True)
    add = instrument_sub.add_parser("add", help="register a security and its listing")
    add.add_argument("--ticker", required=True)
    add.add_argument("--name", required=True, help="issuer legal name")
    add.add_argument("--issuer", help="existing issuer id, for a second share class")
    add.add_argument("--share-class")
    add.add_argument("--cik")
    add.add_argument("--mic", default="XNAS")
    add.add_argument("--currency", default="USD")
    add.set_defaults(handler=cmd_instrument_add)
    listing = instrument_sub.add_parser("list", help="show registered securities")
    listing.set_defaults(handler=cmd_instrument_list)

    opening = subparsers.add_parser("open", help="enter the opening book")
    opening_sub = opening.add_subparsers(dest="open_command", required=True)
    open_position = with_write_flags(opening_sub.add_parser("position", help="an existing holding"))
    open_position.add_argument("--security", required=True, help="ticker or security id")
    open_position.add_argument("--quantity", required=True)
    open_position.add_argument("--unit-cost", help="average cost per share; omit if it is unknown")
    open_position.add_argument("--currency", default="USD")
    open_position.set_defaults(handler=cmd_open_position)
    open_cash = with_write_flags(opening_sub.add_parser("cash", help="the opening cash balance"))
    open_cash.add_argument("--amount", required=True)
    open_cash.add_argument("--currency", default="USD")
    open_cash.set_defaults(handler=cmd_open_cash)

    trade = subparsers.add_parser("trade", help="record fills")
    trade_sub = trade.add_subparsers(dest="trade_command", required=True)
    record = with_write_flags(trade_sub.add_parser("record", help="record a buy or a sell"))
    record.add_argument("side", choices=["buy", "sell"])
    record.add_argument("--security", required=True, help="ticker or security id")
    record.add_argument("--quantity", required=True)
    record.add_argument("--price", required=True, help="execution price per share")
    record.add_argument("--fee")
    record.add_argument("--currency", default="USD")
    record.add_argument("--decision", help="the decision id this fill executes")
    record.set_defaults(handler=cmd_trade_record)

    cash = subparsers.add_parser("cash", help="record cash movements")
    cash_sub = cash.add_subparsers(dest="cash_command", required=True)
    cash_record = with_write_flags(cash_sub.add_parser("record", help="deposit, withdrawal, dividend or fee"))
    cash_record.add_argument("kind", choices=["deposit", "withdrawal", "dividend", "fee"])
    cash_record.add_argument("--amount", required=True, help="positive magnitude; direction comes from the kind")
    cash_record.add_argument("--currency", default="USD")
    cash_record.add_argument("--security", help="required for a dividend")
    cash_record.set_defaults(handler=cmd_cash_record)

    adjust = with_write_flags(subparsers.add_parser("adjust", help="a share count change with no trade"))
    adjust.add_argument("--security", required=True)
    adjust.add_argument("--quantity", required=True, help="signed: negative removes shares")
    adjust.add_argument("--reason", required=True,
                        choices=["stock_split", "reverse_split", "stock_dividend", "spin_off",
                                 "broker_reconciliation"])
    adjust.set_defaults(handler=cmd_adjust)

    correct = subparsers.add_parser("correct", help="supersede or void an earlier event")
    correct.add_argument("event_id")
    correct.add_argument("--note", required=True, help="why -- an unexplained correction is a data error")
    correct.add_argument("--void", action="store_true", help="the event should never have existed")
    correct.add_argument("--quantity")
    correct.add_argument("--price")
    correct.add_argument("--date")
    correct.set_defaults(handler=cmd_correct)

    events = subparsers.add_parser("events", help="list the ledger")
    events.add_argument("--security")
    events.set_defaults(handler=cmd_events)

    positions = subparsers.add_parser("positions", help="positions, cash, NAV and weights")
    positions.add_argument("--price", action="append", metavar="TICKER=AMOUNT")
    positions.add_argument("--prices", help="JSON file of {ticker: price}")
    positions.add_argument("--as-of")
    positions.set_defaults(handler=cmd_positions)

    policy_parser = subparsers.add_parser("policy", help="inspect the capital policy")
    policy_sub = policy_parser.add_subparsers(dest="policy_command", required=True)
    policy_show = policy_sub.add_parser("show", help="the numbers that bind capital decisions")
    policy_show.set_defaults(handler=cmd_policy_show)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except FundError as exc:
        print(f"{PROGRAM}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
