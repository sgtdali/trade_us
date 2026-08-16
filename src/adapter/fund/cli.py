"""``fund`` -- the operator's surface.

Manual entry is the design, not a stopgap: roughly a dozen transactions a year
do not justify a broker integration, and typing them is the moment the owner
looks at what they actually did.

Every command that writes prints back what it wrote, including the identifier,
because in an append-only ledger the identifier is how a mistake gets fixed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from . import (
    cycle,
    decisions,
    dispatch,
    ids,
    instruments,
    jobs,
    metrics,
    monitoring,
    observers,
    packs,
    policy as policy_module,
    projection,
    quality as quality_module,
    recipes,
    report,
    screening,
    schemas,
    sizing,
    store,
    thesis as thesis_module,
)
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


def _price_map(args: argparse.Namespace, master: dict[str, Any], currency: str,
               *, pair_attr: str = "price", file_attr: str = "prices") -> dict[str, Money]:
    """Marking prices for the valuation.

    ``trade-preview`` uses --mark for these, because there --price already
    means the contemplated execution price. The two are different numbers and
    conflating them under one flag would be a quiet way to price a book at the
    price you hoped to pay.
    """
    prices: dict[str, Money] = {}
    path = getattr(args, file_attr, None)
    if path:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        for token, amount in raw.items():
            prices[instruments.resolve(master, token)] = Money.parse(str(amount), currency)
    for pair in getattr(args, pair_attr, None) or []:
        token, _, amount = pair.partition("=")
        if not amount:
            raise FundError(f"--{pair_attr} expects TICKER=AMOUNT, got {pair!r}")
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


# --------------------------------------------------------------------------
# assess -- stage one, with the capital consequence hidden
# --------------------------------------------------------------------------

MATERIAL_DOWNSIDE_DIFFERENCE = Decimal("0.05")  # 500 bp


def cmd_assess(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master, security_id = _resolve(args, args.security)

    if args.downside is None and not args.downside_unknown:
        raise FundError(
            "state the downside with --downside -0.30, or --downside-unknown with a reason.\n"
            "  An unstated downside is not a smaller one; policy makes the name "
            "ineligible for new risk."
        )

    prior = ledger.latest_assessment(security_id)
    mode = args.mode or ("update_against_prior" if prior else "de_novo")
    if mode != "de_novo" and prior is None:
        raise FundError(f"mode {mode!r} needs a previous assessment, and there is none")
    if prior is not None and mode == "de_novo" and not args.force_de_novo:
        raise FundError(
            f"{args.security} already has an assessment ({prior['assessment_id']}). "
            "Use --mode update_against_prior, or --force-de-novo to underwrite it from scratch."
        )
    if prior is not None and not args.change_driver:
        raise FundError("--change-driver is required when a previous assessment exists")

    if args.downside_unknown:
        downside: dict[str, Any] = {"status": "unknown", "reason": args.downside_reason or
                                    "not stated"}
    else:
        if not args.downside_scenario:
            raise FundError("--downside needs --downside-scenario: a number with no story is not a scenario")
        downside = {
            "status": "known",
            "return_fraction": to_string(Decimal(args.downside)),
            "scenario": args.downside_scenario,
        }

    material = False
    if prior is not None:
        if prior["readiness"] != args.readiness:
            material = True
        elif prior["downside"]["status"] != downside["status"]:
            material = True
        elif downside["status"] == "known":
            difference = abs(Decimal(downside["return_fraction"])
                             - Decimal(prior["downside"]["return_fraction"]))
            material = difference > MATERIAL_DOWNSIDE_DIFFERENCE
    if material and not args.rationale:
        raise FundError(
            "this is a material change (readiness moved, or the downside moved more than 500 bp). "
            "--rationale is required."
        )

    acceptance: dict[str, Any] = {
        "accepted_at": _now(),
        "mode": "acknowledged_without_full_adjudication" if args.acknowledge else "human_adjudicated",
        "critical_sources_checked": not args.sources_not_checked,
        "would_accept_downside_without_position": not args.would_not_accept,
    }
    if args.change_driver:
        acceptance["main_change_driver"] = args.change_driver
    if args.rationale:
        acceptance["rationale"] = args.rationale
    if args.minutes is not None:
        acceptance["minutes_spent"] = args.minutes

    if acceptance["mode"] == "human_adjudicated" and args.sources_not_checked:
        raise FundError(
            "if the critical sources were not checked, this is not a full adjudication: "
            "add --acknowledge (it will not support raising readiness)"
        )

    document: dict[str, Any] = {
        "assessment_id": ids.new_id(ids.ASSESSMENT),
        "security_id": security_id,
        "as_of": args.as_of or _today(),
        "assessment_mode": mode,
        "thesis_summary": args.summary,
        "readiness": args.readiness,
        "downside": downside,
        "evidence_date": args.evidence_date,
        "review_due": args.review_due,
        "human_authored": not args.from_model,
        "acceptance": acceptance,
    }
    if prior is not None:
        document["derived_from"] = prior["assessment_id"]

    result = _ledger(args).commit(
        [store.Write(kind=store.ASSESSMENT_RECORD.name, document=document)],
        allow_duplicate=True,
    )
    assessment_id = result.written[0]

    ticker = instruments.ticker_for(master, security_id)
    print(f"{ticker} -- RESEARCH JUDGEMENT")
    print()
    print(f"  {'Assessment':<18}{assessment_id}")
    print(f"  {'Mode':<18}{mode}")
    print(f"  {'Readiness':<18}{args.readiness}")
    if downside["status"] == "known":
        print(f"  {'Downside':<18}{Decimal(downside['return_fraction']) * 100:.2f}%")
        print(f"  {'Scenario':<18}{downside['scenario']}")
    else:
        print(f"  {'Downside':<18}unknown -- {downside['reason']}")
        print("                    policy: ineligible for new risk")
    print(f"  {'Evidence date':<18}{args.evidence_date}")
    print(f"  {'Review due':<18}{args.review_due}")
    if acceptance["mode"] == "acknowledged_without_full_adjudication":
        print("\n  acknowledged without full adjudication -- this cannot raise readiness")
    if args.would_not_accept:
        print("\n  ! you would NOT accept this downside from scratch;"
              " this assessment cannot support increasing risk")
    print("\n  Nothing above depends on what you own. Run `fund trade-preview` to see that.")
    return 0


def cmd_assessments(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    security_id = instruments.resolve(master, args.security) if args.security else None
    records = ledger.assessments(security_id=security_id)
    if not records:
        print("no assessments recorded yet")
        return 0
    print(f"{'AS OF':<12} {'TICKER':<8} {'READINESS':<11} {'DOWNSIDE':>9} {'REVIEW DUE':<12} ID")
    for record in records:
        ticker = instruments.ticker_for(master, record["security_id"])
        downside = record["downside"]
        shown = (f"{Decimal(downside['return_fraction']) * 100:.1f}%"
                 if downside["status"] == "known" else "unknown")
        print(f"{record['as_of']:<12} {ticker:<8} {record['readiness']:<11} {shown:>9} "
              f"{record['review_due']:<12} {record['assessment_id']}")
    return 0


# --------------------------------------------------------------------------
# trade-preview -- stage two, everything visible at once
# --------------------------------------------------------------------------

def _valuation(args: argparse.Namespace, ledger: store.Ledger, master: dict[str, Any],
               currency: str, *, pair_attr: str = "price",
               file_attr: str = "prices") -> tuple[Any, Any]:
    state = projection.project(ledger.account_events())
    prices = _price_map(args, master, currency, pair_attr=pair_attr, file_attr=file_attr)
    valuation = projection.value(state, prices, as_of=args.as_of or _today(),
                                 base_currency=currency)
    return state, valuation


def cmd_trade_preview(args: argparse.Namespace) -> int:
    loaded = policy_module.load()
    currency = loaded["measurement"]["base_currency"]
    ledger = _ledger(args)
    master, security_id = _resolve(args, args.security)

    if args.assessment:
        assessment = ledger.assessment(args.assessment)
        if assessment["security_id"] != security_id:
            raise FundError(
                f"assessment {args.assessment} is for {assessment['security_id']}, "
                f"not {security_id}"
            )
    else:
        assessment = ledger.latest_assessment(security_id)
        if assessment is None:
            raise FundError(
                f"{args.security} has no assessment. Run `fund assess {args.security}` first -- "
                "the research judgement is formed before its capital consequence is visible."
            )

    state, valuation = _valuation(args, ledger, master, currency,
                                  pair_attr="mark", file_attr="marks")
    preview = decisions.build_preview(
        loaded, state, valuation, assessment, master,
        action=args.side,
        quantity=Decimal(args.quantity),
        price=Money.parse(args.price, currency),
    )

    print(decisions.render(preview, instruments.ticker_for(master, security_id)))

    if not args.decide:
        print()
        print("  Nothing recorded. Add --decide accept|reduce|cancel|outside-policy "
              "with --rationale to freeze this decision.")
        return 0

    if args.decide in {"accept", "reduce", "outside-policy"} and args.side == "buy":
        if not assessment["acceptance"]["would_accept_downside_without_position"]:
            raise FundError(
                "this assessment records that you would not accept its downside from scratch, "
                "so it cannot support increasing risk. Reassess first."
            )

    document = decisions.build_decision(
        preview, loaded,
        as_of=args.as_of or _today(),
        recorded_at=_now(),
        decide=args.decide,
        rationale=args.rationale,
        reason_code=args.reason_code,
        mode="live" if args.live else "shadow",
        next_review=args.next_review,
    )
    result = ledger.commit([store.Write(kind=store.DECISION_RECORD.name, document=document)],
                           allow_duplicate=True)
    decision_id = result.written[0]

    print()
    print(f"decision   {decision_id}   ({document['outcome']['decision']}, {document['mode']})")
    print(f"  final quantity  {document['outcome']['final_quantity']}")
    if document["mode"] == "shadow":
        print("  shadow mode: nothing has been committed to the market.")
    if document["outcome"]["decision"] not in {"cancelled"}:
        print(f"  when the order fills:  fund trade-add --decision {decision_id} "
              f"--quantity <filled> --price <fill price>")
    return 0


def cmd_trade_add(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    decision = ledger.decision(args.decision)
    if decision["action"] not in {"buy", "sell"}:
        raise FundError(f"decision {args.decision} is a {decision['action']}, not a trade")

    currency = decision["contemplated"]["price"]["currency"]
    document: dict[str, Any] = {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "event_type": decision["action"],
        "effective_date": args.date or _today(),
        "recorded_at": _now(),
        "security_id": decision["security_id"],
        "quantity": to_string(Decimal(args.quantity)),
        "price": _money_document(args.price, currency),
        "decision_id": args.decision,
    }
    if args.fee is not None:
        document["fee"] = _money_document(args.fee, currency)
    if args.note:
        document["note"] = args.note

    event_id = _commit(ledger, document, allow_duplicate=args.allow_duplicate)
    ticker = instruments.ticker_for(master, decision["security_id"])
    _report(document, event_id, f"recorded {decision['action']}")
    print(f"  {ticker}  {document['quantity']} x {args.price}")
    print(f"  fills decision {args.decision}")

    decided = Decimal(decision["outcome"]["final_quantity"])
    filled = Decimal(document["quantity"])
    if filled != decided:
        print(f"  ! the decision was for {to_string(decided)} shares, this fill is "
              f"{to_string(filled)}")
    return 0


# --------------------------------------------------------------------------
# review -- the monthly capital session
# --------------------------------------------------------------------------

def cmd_review(args: argparse.Namespace) -> int:
    loaded = policy_module.load()
    currency = loaded["measurement"]["base_currency"]
    ledger = _ledger(args)
    master = _master(args)
    as_of = args.as_of or _today()

    state, valuation = _valuation(args, ledger, master, currency)
    if valuation.nav is None:
        print(f"AS OF {as_of}")
        print("NAV unavailable -- supply the missing prices before reviewing.")
        for warning in valuation.warnings:
            print(f"  ! {warning}")
        return 1

    ledger.record_price_marks([
        {"security_id": position.security_id, "as_of": as_of,
         "price": to_string(position.price.amount), "currency": currency}
        for position in valuation.positions if position.price is not None
    ])
    ledger.record_nav(as_of=as_of, nav=to_string(valuation.nav.amount),
                      cash=to_string(valuation.cash.amount), currency=currency,
                      recorded_at=_now())
    history = ledger.nav_history()
    peak = max(Decimal(row["nav"]) for row in history)
    drawdown = (valuation.nav.amount - peak) / peak if peak > 0 else Decimal(0)

    print(f"MONTHLY REVIEW -- {as_of}")
    print()
    print(f"  {'NAV':<18}{format_display(valuation.nav.amount)} {currency}")
    print(f"  {'Cash':<18}{format_display(valuation.cash.amount)} "
          f"({valuation.cash_weight * 100:.2f}%)")
    print(f"  {'Open positions':<18}{len(valuation.positions)} / "
          f"{loaded['capacity']['max_active_positions']}")
    if len(history) > 1:
        print(f"  {'Drawdown':<18}{drawdown * 100:.2f}% from a peak of {format_display(peak)} "
              f"({len(history)} marks since {history[0]['as_of']})")
        response = sizing.drawdown_response(loaded, drawdown)
        if response:
            print(f"  {'Ladder':<18}{response}")
    else:
        print(f"  {'Drawdown':<18}first mark recorded; a peak needs a second review")
    print()

    print(f"{'TICKER':<8} {'WEIGHT':>8} {'CEILING':>9} {'READINESS':<11} {'DOWNSIDE':>9} "
          f"{'REVIEW DUE':<12} STATUS")
    warnings: list[str] = []
    for position in valuation.positions:
        ticker = instruments.ticker_for(master, position.security_id)
        assessment = ledger.latest_assessment(position.security_id)
        weight = f"{position.weight * 100:.2f}%" if position.weight is not None else "-"

        if assessment is None:
            print(f"{ticker:<8} {weight:>8} {'-':>9} {'-':<11} {'-':>9} {'-':<12} NO ASSESSMENT")
            warnings.append(f"{ticker}: held with no assessment on file")
            continue

        downside = assessment["downside"]
        shown = (f"{Decimal(downside['return_fraction']) * 100:.1f}%"
                 if downside["status"] == "known" else "unknown")
        try:
            result = sizing.evaluate(
                loaded,
                readiness=assessment["readiness"],
                downside_status=downside["status"],
                downside_return_fraction=(Decimal(downside["return_fraction"])
                                          if downside["status"] == "known" else None),
                exposure=sizing.Exposure(
                    nav=valuation.nav.amount,
                    cash=valuation.cash.amount,
                    current_weight=position.weight or Decimal(0),
                    issuer_weight_excluding_security=decisions.issuer_weight_excluding(
                        valuation, master, position.security_id),
                ),
            )
            ceiling = f"{result.policy_compliant_max_weight * 100:.2f}%"
            over = (position.weight or Decimal(0)) > result.policy_compliant_max_weight
        except FundError:
            ceiling, over = "-", False

        overdue = assessment["review_due"] < as_of
        status = "OVER CEILING" if over else ("REVIEW DUE" if overdue else "ok")
        print(f"{ticker:<8} {weight:>8} {ceiling:>9} {assessment['readiness']:<11} {shown:>9} "
              f"{assessment['review_due']:<12} {status}")
        if over:
            warnings.append(f"{ticker}: weight {weight} is above its policy ceiling {ceiling}")
        if overdue:
            warnings.append(f"{ticker}: review was due {assessment['review_due']}")

    print()
    for warning in list(valuation.warnings) + warnings:
        print(f"  ! {warning}")

    if args.no_change:
        _, security_id = _resolve(args, args.no_change)
        if not args.rationale:
            raise FundError("--no-change needs --rationale: holding is a decision too")
        document = decisions.build_no_change(
            loaded,
            security_id=security_id,
            as_of=as_of,
            recorded_at=_now(),
            rationale=args.rationale,
            reason_code=args.reason_code or "review.thesis_intact",
            valuation=valuation,
            pending_review=args.pending_review,
            mode="live" if args.live else "shadow",
        )
        result = ledger.commit([store.Write(kind=store.DECISION_RECORD.name, document=document)],
                               allow_duplicate=True)
        print()
        print(f"decision   {result.written[0]}   ({document['outcome']['decision']})")
    else:
        print("  Holding is a decision: record it with "
              "--no-change TICKER --rationale '...'")
    return 0


def cmd_decisions(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    records = ledger.decisions()
    if not records:
        print("no decisions recorded yet")
        return 0
    print(f"{'AS OF':<12} {'TICKER':<8} {'ACTION':<10} {'OUTCOME':<30} {'MODE':<7} ID")
    for record in records:
        ticker = instruments.ticker_for(master, record["security_id"])
        print(f"{record['as_of']:<12} {ticker:<8} {record['action']:<10} "
              f"{record['outcome']['decision']:<30} {record['mode']:<7} {record['decision_id']}")
    return 0


# --------------------------------------------------------------------------
# thesis
# --------------------------------------------------------------------------

def _theses(ledger: store.Ledger) -> dict[str, thesis_module.ThesisHistory]:
    return thesis_module.project(ledger.thesis_events())


def _find_thesis(ledger: store.Ledger, master: dict[str, Any], token: str):
    theses = _theses(ledger)
    if token in theses:
        return theses[token]
    security_id = instruments.resolve(master, token)
    found = thesis_module.open_for_security(theses, security_id)
    if found is None:
        raise FundError(f"no open thesis for {token}")
    return found


def _commit_thesis(ledger: store.Ledger, document: dict[str, Any]) -> None:
    ledger.commit([store.Write(kind=store.THESIS_EVENT.name, document=document)],
                  allow_duplicate=True)


def cmd_thesis_open(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master, security_id = _resolve(args, args.security)

    existing = thesis_module.open_for_security(_theses(ledger), security_id)
    if existing is not None:
        raise FundError(
            f"{args.security} already has an open thesis ({existing.thesis_id}, "
            f"{existing.status}). Close it before opening another, or update it instead."
        )

    assessment_id = args.assessment or (
        (ledger.latest_assessment(security_id) or {}).get("assessment_id")
    )
    if not assessment_id:
        raise FundError(
            f"a thesis opens from an accepted assessment; run `fund assess {args.security}` first"
        )
    assessment = ledger.assessment(assessment_id)
    if assessment["security_id"] != security_id:
        raise FundError(f"assessment {assessment_id} is for {assessment['security_id']}")
    if assessment["acceptance"]["mode"] != "human_adjudicated":
        raise FundError(
            f"{assessment_id} was acknowledged without full adjudication; "
            "a thesis cannot open from it"
        )

    event = thesis_module.open_event(
        security_id=security_id,
        thesis_statement=args.statement or assessment["thesis_summary"],
        assessment_id=assessment_id,
        effective_date=args.as_of or _today(),
    )
    _commit_thesis(ledger, event)
    print(f"opened     {event['thesis_id']}")
    print(f"  {instruments.ticker_for(master, security_id)}  status active")
    print(f"  from assessment {assessment_id}")
    print("  next: attach a monitoring contract with `fund thesis contract`")
    return 0


def cmd_thesis_list(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    theses = _theses(ledger)
    if not theses:
        print("no theses opened yet")
        return 0
    print(f"{'TICKER':<8} {'STATUS':<16} {'OPENED':<12} {'RULES':>5} {'CHECKS':>6} ID")
    for history in sorted(theses.values(), key=lambda h: h.document["opened_at"]):
        document = history.document
        contract = document.get("monitoring_contract")
        rules = len(contract["mechanical_rules"]) if contract else 0
        checks = len(contract["qualitative_checks"]) if contract else 0
        ticker = instruments.ticker_for(master, document["security_id"])
        print(f"{ticker:<8} {document['status']:<16} {document['opened_at']:<12} "
              f"{rules:>5} {checks:>6} {document['thesis_id']}")
    return 0


def cmd_thesis_show(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    history = _find_thesis(ledger, master, args.thesis)
    document = history.document
    as_of = args.as_of or _today()

    print(f"{instruments.ticker_for(master, document['security_id'])} -- {document['thesis_id']}")
    print()
    print(f"  {'Status':<18}{document['status']}")
    if document.get("status_reason"):
        print(f"  {'Reason':<18}{document['status_reason']}")
    print(f"  {'Opened':<18}{document['opened_at']}")
    print(f"  {'Assessment':<18}{document.get('current_assessment_id', '-')}")
    print()
    print(f"  {document['thesis_statement']}")

    contract = document.get("monitoring_contract")
    if not contract:
        print("\n  NO MONITORING CONTRACT -- nothing is watching this thesis")
        return 0

    print(f"\nMONITORING CONTRACT v{contract['version']} "
          f"(from {contract['effective_from']})")
    if contract["mechanical_rules"]:
        print("\n  Mechanical")
        for rule in contract["mechanical_rules"]:
            print(f"    {rule['rule_id']:<24} {rule['metric_id']} {rule['period_basis']} "
                  f"{rule['operator']} {rule['threshold']} ({rule['test_type']})")
    if contract["qualitative_checks"]:
        print("\n  Qualitative")
        for check in contract["qualitative_checks"]:
            due = "DUE" if check["review_due"] <= as_of else check["review_due"]
            print(f"    {check['check_id']:<24} [{due}] {check['question']}")
            print(f"    {'':<24} on: {', '.join(check['review_on'])}")

    if history.transitions:
        print("\nHISTORY")
        for entry in history.transitions:
            if entry["event_type"] == "closed":
                print(f"  {entry['effective_date']}  closed ({entry['close_reason']}) "
                      f"-- {entry['reason']}")
            else:
                print(f"  {entry['effective_date']}  {entry['from_status']} -> "
                      f"{entry['to_status']} [{entry['actor']}] -- {entry['reason']}")
    return 0


def cmd_thesis_contract(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    history = _find_thesis(ledger, master, args.thesis)

    raw = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
    previous = history.document.get("monitoring_contract")
    version = raw.get("version") or ((previous["version"] + 1) if previous else 1)
    if previous and version <= previous["version"]:
        raise FundError(
            f"contract version {version} is not newer than the active v{previous['version']}; "
            "changing a threshold means a new version"
        )
    if previous and not (raw.get("change_reason") or args.reason):
        raise FundError("replacing an active contract requires --reason")

    contract = thesis_module.build_contract(
        version=version,
        effective_from=raw.get("effective_from") or args.as_of or _today(),
        mechanical_rules=raw.get("mechanical_rules", []),
        qualitative_checks=raw.get("qualitative_checks", []),
        change_reason=raw.get("change_reason") or args.reason,
    )

    # A rule that does not bind to the metric catalog cannot be evaluated, so
    # it must not be activated: a contract carrying rules that will only ever
    # return unavailable looks like monitoring and is not.
    problems = metrics.check_contract(contract, metrics.load_catalog())
    if problems:
        raise FundError(
            "this contract does not bind to the metric catalog, so it was not activated:\n  "
            + "\n  ".join(problems)
        )
    event = thesis_module.contract_event(
        thesis_id=history.thesis_id,
        contract=contract,
        effective_date=contract["effective_from"],
    )
    _commit_thesis(ledger, event)

    print(f"activated  monitoring contract v{version} on {history.thesis_id}")
    print(f"  {len(contract['mechanical_rules'])} mechanical rule(s), "
          f"{len(contract['qualitative_checks'])} qualitative check(s)")
    if previous:
        print(f"  v{previous['version']} is retained; checks already recorded keep their rule")
    return 0


def cmd_thesis_contract_template(args: argparse.Namespace) -> int:
    print(json.dumps({
        "version": 1,
        "effective_from": _today(),
        "mechanical_rules": [
            {
                "rule_id": "gross_margin_floor",
                "metric_id": "gross_margin",
                "period_basis": "ttm",
                "test_type": "absolute_value",
                "operator": "lt",
                "threshold": "0.55",
                "note": "Below this the pricing-power claim is not standing up",
            }
        ],
        "qualitative_checks": [
            {
                "check_id": "customer_concentration",
                "question": "Has the top-two customer share moved materially, "
                            "and is the reason structural?",
                "review_on": ["new_periodic_filing", "review_due"],
                "review_due": _today(),
            }
        ],
    }, indent=2))
    return 0


def cmd_thesis_status(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    history = _find_thesis(ledger, master, args.thesis)

    if history.status == thesis_module.REVIEW_REQUIRED and not args.resolution:
        raise FundError(
            "leaving review_required needs --resolution: whether the rule was wrong "
            "(measurement_error), the breach was real but changed nothing "
            "(decision_irrelevant_breach), or the thesis itself moved. Without it the "
            "thresholds cannot be calibrated, and the cause is not recoverable later."
        )
    event = thesis_module.status_event(
        thesis_id=history.thesis_id,
        from_status=history.status,
        to_status=args.to,
        reason=args.reason,
        effective_date=args.as_of or _today(),
        actor="human",
        resolution=args.resolution,
    )
    _commit_thesis(ledger, event)
    print(f"{history.thesis_id}  {history.status} -> {args.to}")
    print(f"  {args.reason}")
    return 0


def cmd_thesis_close(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    history = _find_thesis(ledger, master, args.thesis)

    thesis_module.check_transition(history.status, thesis_module.CLOSED, "human")
    event = thesis_module.close_event(
        thesis_id=history.thesis_id,
        close_reason=args.close_reason,
        reason=args.reason,
        effective_date=args.as_of or _today(),
        superseded_by=args.superseded_by,
    )
    _commit_thesis(ledger, event)
    print(f"closed     {history.thesis_id} ({args.close_reason})")
    print(f"  {args.reason}")
    return 0


def cmd_thesis_reviewed(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    history = _find_thesis(ledger, master, args.thesis)
    contract = history.document.get("monitoring_contract")
    if not contract:
        raise FundError("this thesis has no monitoring contract")
    if not any(check["check_id"] == args.check for check in contract["qualitative_checks"]):
        raise FundError(f"no qualitative check called {args.check!r} in the active contract")

    event = thesis_module.check_reviewed_event(
        thesis_id=history.thesis_id,
        check_id=args.check,
        next_review_due=args.next_due,
        effective_date=args.as_of or _today(),
    )
    _commit_thesis(ledger, event)
    print(f"reviewed   {args.check} on {history.thesis_id}")
    print(f"  next due {args.next_due}")
    return 0


# --------------------------------------------------------------------------
# check -- run the mechanical rules
# --------------------------------------------------------------------------

def cmd_check(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    history = _find_thesis(ledger, master, args.thesis)
    contract = history.document.get("monitoring_contract")
    if not contract:
        raise FundError(f"{history.thesis_id} has no monitoring contract; nothing to check")

    raw = json.loads(Path(args.observations).read_text(encoding="utf-8"))
    observations = [monitoring.Observation.from_document(entry)
                    for entry in (raw["observations"] if isinstance(raw, dict) else raw)]

    outcomes = monitoring.evaluate_contract(
        contract, observations, metrics.load_catalog(),
        max_evidence_age_days=args.max_evidence_age_days,
        as_of=args.as_of or _today(),
    )

    ticker = instruments.ticker_for(master, history.document["security_id"])
    print(f"{ticker} -- {history.thesis_id}   contract v{contract['version']}")
    print()
    writes = []
    rules_by_id = {rule["rule_id"]: rule for rule in contract["mechanical_rules"]}
    for outcome in outcomes:
        rule = rules_by_id[outcome.rule_id]
        marker = {"breached": "BREACHED", "not_breached": "ok", "unavailable": "UNAVAILABLE"}
        print(f"  {outcome.rule_id:<26} {marker[outcome.result]:<12} {outcome.detail or ''}")
        if outcome.result == monitoring.UNAVAILABLE:
            print(f"  {'':<26} reason: {outcome.reason}")
        writes.append(store.Write(
            kind=store.MONITORING_CHECK_RECORD.name,
            document=monitoring.build_record(
                outcome, rule,
                thesis_id=history.thesis_id,
                contract_version=contract["version"],
                evaluated_for=args.evaluated_for,
                evidence_accession=args.accession,
            ),
        ))

    try:
        ledger.commit(writes, allow_duplicate=True)
    except LedgerError as exc:
        raise FundError(
            f"these checks were already recorded for this evidence: {exc}"
        ) from exc

    print()
    print(f"  {monitoring.summarise(outcomes)}")
    unavailable = monitoring.unavailable_rules(outcomes)
    if unavailable:
        print("  ! an unavailable check is not a passed check -- these rules did not run")

    breaches = monitoring.breached_rules(outcomes)
    if not breaches:
        if not unavailable:
            print("  no rule was crossed. That is not the same as the thesis being healthy.")
        return 0

    if history.status != thesis_module.ACTIVE:
        print(f"\n  thesis is already {history.status}; no further status change")
        return 0

    event = thesis_module.status_event(
        thesis_id=history.thesis_id,
        from_status=thesis_module.ACTIVE,
        to_status=thesis_module.REVIEW_REQUIRED,
        reason="mechanical breach: " + ", ".join(o.rule_id for o in breaches),
        effective_date=args.as_of or _today(),
        actor="machine",
    )
    _commit_thesis(ledger, event)
    print(f"\n  thesis -> review_required")
    print("  the machine can do nothing further here: whether the thesis is broken")
    print("  is your judgement, not the rule's.")
    return 0


def cmd_checks(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    thesis_id = None
    if args.thesis:
        thesis_id = _find_thesis(ledger, master, args.thesis).thesis_id
    records = ledger.check_records(thesis_id=thesis_id)
    if not records:
        print("no checks recorded yet")
        return 0
    print(f"{'EVALUATED':<22} {'RULE':<26} {'V':>2} {'RESULT':<14} {'VALUE':>12} EVIDENCE")
    for record in records:
        print(f"{record['evaluated_at']:<22} {record['rule_id']:<26} "
              f"{record['contract_version']:>2} {record['result']:<14} "
              f"{record.get('observed_value', '-'):>12} "
              f"{record.get('evidence_accession', record['evaluated_for'])}")
    return 0


# --------------------------------------------------------------------------
# jobs, inbox, adjudication
# --------------------------------------------------------------------------

def cmd_job_open(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)

    if args.observation == "periodic_discovery":
        if args.security:
            raise FundError(
                "a screen is about a universe, not a security. Drop --security: "
                "telling the screen which name to look at is not screening."
            )
        return _open_discovery_job(args, ledger, master)

    if not args.security:
        raise FundError(f"a {args.observation} job needs --security")
    security_id = instruments.resolve(master, args.security)

    thesis_id = None
    if args.thesis or args.observation in {"mechanical_breach", "review_due"}:
        found = thesis_module.open_for_security(_theses(ledger), security_id)
        if found is None and args.observation in {"mechanical_breach", "review_due"}:
            raise FundError(f"{args.security} has no open thesis for a {args.observation} trigger")
        thesis_id = found.thesis_id if found else None

    contract_version = None
    if thesis_id:
        contract = _theses(ledger)[thesis_id].document.get("monitoring_contract")
        contract_version = contract["version"] if contract else None

    key = jobs.dedup_key(
        observation=args.observation,
        security_id=security_id,
        thesis_id=thesis_id,
        evidence_accession=args.accession,
        monitoring_contract_version=contract_version,
        review_due=args.review_due,
    )
    existing = ledger.job_for_dedup_key(key)
    if existing is not None:
        print(f"already open  {existing['job_id']} ({existing['status']})")
        print("  same evidence, same contract version: this is the same piece of work")
        return 0

    snapshot: dict[str, Any] = {
        "observation": args.observation,
        "observed_at": _now(),
    }
    for field, value in (("evidence_accession", args.accession),
                         ("evidence_date", args.evidence_date),
                         ("review_due", args.review_due)):
        if value:
            snapshot[field] = value
    if contract_version is not None:
        snapshot["monitoring_contract_version"] = contract_version

    document = jobs.new_job(
        trigger_snapshot=snapshot,
        rule_id=args.rule_id,
        rule_version=args.rule_version,
        recipe=args.recipe,
        assessment_mode=args.mode,
        security_id=security_id,
        dedup_key_value=key,
        thesis_id=thesis_id,
        decision_deadline=args.deadline,
    )
    ledger.save_job(document)
    print(f"opened     {document['job_id']}")
    print(f"  {instruments.ticker_for(master, security_id)}  {args.observation}  "
          f"-> {args.recipe} ({args.mode})")
    return 0


def _open_discovery_job(args: argparse.Namespace, ledger: store.Ledger,
                        master: dict[str, Any]) -> int:
    tuning = dispatch.load_tuning()
    universe_id = args.universe or tuning["discovery_universe"]
    as_of = args.as_of or _today()

    key = jobs.dedup_key(observation="periodic_discovery", security_id="-",
                         discovery_date=as_of)
    existing = ledger.job_for_dedup_key(key)
    if existing is not None:
        print(f"already open  {existing['job_id']} ({existing['status']})")
        return 0

    document = jobs.new_job(
        trigger_snapshot=screening.discovery_observation(as_of=as_of,
                                                         universe_id=universe_id),
        rule_id=args.rule_id if args.rule_id != "manual" else "periodic_discovery",
        rule_version=1,
        recipe="idea_generation",
        assessment_mode="de_novo",
        security_id=None,
        dedup_key_value=key,
    )
    document["trigger_snapshot"].pop("_security_id", None)
    document["trigger_snapshot"].pop("_thesis_id", None)
    ledger.save_job(document)
    print(f"opened     {document['job_id']}")
    print(f"  screen of {universe_id}")
    return 0


def load_universe(universe_id: str, root: Path | None = None) -> list[str]:
    path = (root or schemas.repo_root()) / "config" / "universes" / f"{universe_id}.json"
    if not path.is_file():
        raise FundError(
            f"no universe called {universe_id!r}. Available: "
            + ", ".join(sorted(p.stem for p in
                               (root or schemas.repo_root()).joinpath(
                                   "config", "universes").glob("*.json")))
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    return [member["ticker"] for member in document["members"]]


def cmd_job_result(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    document = ledger.job(args.job)

    proposal = None
    if args.proposal:
        proposal = json.loads(Path(args.proposal).read_text(encoding="utf-8"))

    artifact = {
        "relative_path": args.artifact,
        "digest": args.digest or ("sha256:" + hashlib.sha256(
            Path(args.artifact).read_bytes() if Path(args.artifact).is_file()
            else args.artifact.encode("utf-8")).hexdigest()),
    }

    updated = jobs.attach_result(document, artifact=artifact, proposed_assessment=proposal)
    try:
        schemas.validate(updated, schemas.RESEARCH_JOB_RECORD)
    except FundError as exc:
        failed = jobs.mark_contract_failed(document, f"result does not satisfy its contract: {exc}")
        ledger.save_job(failed)
        raise FundError(
            "the result does not satisfy its contract, so it will not be put in front of you.\n"
            f"  {exc}"
        ) from exc

    ledger.save_job(updated)
    print(f"attached   {args.job}")
    print(f"  status {updated['status']}")
    if proposal:
        print(f"  proposes readiness {proposal['readiness']}")
    print(f"  adjudicate with: fund adjudicate {args.job}")
    return 0


def cmd_job_fail(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    document = ledger.job(args.job)
    updated = jobs.fail_attempt(document, error_class=args.error_class, detail=args.detail)
    ledger.save_job(updated)

    print(f"failed     {args.job}  ({args.error_class})")
    print(f"  attempt {jobs.attempts_used(updated)} of at most {jobs.MAX_ATTEMPTS}")
    if jobs.stopped(updated):
        print("  automatic retry stopped -- this is in Q0 now, not forgotten and not repeating")
    return 0


def cmd_jobs(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    records = ledger.jobs(status=args.status)
    if not records:
        print("no jobs")
        return 0
    print(f"{'CREATED':<22} {'TICKER':<8} {'OBSERVATION':<22} {'RECIPE':<24} "
          f"{'STATUS':<22} ID")
    for record in records:
        # A screening job is about a universe and carries no security.
        ticker = (instruments.ticker_for(master, record["security_id"])
                  if record.get("security_id") else "--")
        print(f"{record['created_at']:<22} {ticker:<8} "
              f"{record['trigger_snapshot']['observation']:<22} {record['recipe']:<24} "
              f"{record['status']:<22} {record['job_id']}")
    return 0


def _funded_securities(ledger: store.Ledger) -> set[str]:
    state = projection.project(ledger.account_events())
    return set(state.open_positions())


def cmd_inbox(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    as_of = args.as_of or _today()

    queue = jobs.build_queue(ledger.jobs(), funded_security_ids=_funded_securities(ledger),
                             as_of=as_of)

    print(f"INBOX -- {as_of}")
    print()
    if queue.empty:
        print("  Nothing needs you today.")
        if queue.q2:
            print(f"  ({len(queue.q2)} item(s) recorded for information only)")
        return 0

    if queue.q0:
        print("Q0 -- BLOCKING")
        for item in queue.q0:
            ticker = instruments.ticker_for(master, item.job.get("security_id", "-"))
            print(f"  {ticker:<8} {item.reason}")
            if item.detail:
                print(f"  {'':<8} {item.detail}")
        print("  New risk should not be increased while these are open.")
        print()

    if queue.q1:
        print(f"Q1 -- NEEDS ADJUDICATION  ({jobs.total_estimate(queue)} min estimated)")
        for item in queue.q1:
            ticker = (instruments.ticker_for(master, item.job["security_id"])
                      if item.job.get("security_id") else "screen")
            deadline = item.job.get("decision_deadline")
            due = f"  due {deadline}" if deadline else ""
            estimate = f"~{item.estimate_minutes} min" if item.estimate_minutes else ""
            print(f"  {ticker:<8} {item.reason:<24} {estimate:<9}{due}")
            print(f"  {'':<8} fund adjudicate {item.job_id}")
        print()

    if queue.q2 and args.verbose:
        print("Q2 -- FOR INFORMATION")
        for item in queue.q2:
            ticker = instruments.ticker_for(master, item.job.get("security_id", "-"))
            print(f"  {ticker:<8} {item.reason}")
    elif queue.q2:
        print(f"Q2 -- {len(queue.q2)} item(s) for information (--verbose to see them)")
    return 0


def _render_adjudication(job: dict[str, Any], prior: dict[str, Any] | None,
                         checks: list[dict[str, Any]], ticker: str) -> None:
    proposal = job["result"]["proposed_assessment"]
    trigger = job["trigger_snapshot"]

    print(f"{ticker} -- ADJUDICATION   {job['job_id']}")
    print(f"  {'Triggered by':<20}{trigger['observation'].replace('_', ' ')}"
          f"{'  ' + trigger['evidence_accession'] if trigger.get('evidence_accession') else ''}")
    print(f"  {'Mode':<20}{job['assessment_mode']}")
    print(f"  {'Recipe':<20}{job['recipe']} (rule {job['rule_id']} v{job['rule_version']})")
    print()

    print("PROPOSED")
    print(f"  {'Readiness':<20}{proposal['readiness']}")
    downside = proposal["downside"]
    if downside["status"] == "known":
        print(f"  {'Downside':<20}{Decimal(downside['return_fraction']) * 100:.2f}%")
        print(f"  {'Scenario':<20}{downside['scenario']}")
    else:
        print(f"  {'Downside':<20}unknown -- {downside['reason']}")
    print(f"  {'Evidence date':<20}{proposal['evidence_date']}")
    print(f"  {'Review due':<20}{proposal['review_due']}")
    print()
    print(f"  {proposal['thesis_summary']}")

    if proposal.get("sources"):
        print("\nSOURCES")
        for source in proposal["sources"]:
            print(f"  {source}")
    print(f"\n  artifact: {job['result']['artifact']['relative_path']}")

    if prior is not None and job["assessment_mode"] != "de_novo":
        print("\nAGAINST THE PREVIOUS ACCEPTED JUDGEMENT")
        print(f"  {'readiness':<20}{prior['readiness']} -> {proposal['readiness']}")
        before = prior["downside"]
        if before["status"] == "known" and downside["status"] == "known":
            print(f"  {'downside':<20}{Decimal(before['return_fraction']) * 100:.2f}% -> "
                  f"{Decimal(downside['return_fraction']) * 100:.2f}%")
        else:
            print(f"  {'downside':<20}{before['status']} -> {downside['status']}")
        print(f"  {'evidence date':<20}{prior['evidence_date']} -> {proposal['evidence_date']}")
        material, why = jobs.material_change(proposal, prior)
        if material:
            print(f"  MATERIAL CHANGE: {why} -- a rationale is required")

    if checks:
        print("\nMECHANICAL CHECKS")
        for check in checks:
            value = check.get("observed_value", check.get("unavailable_reason", ""))
            print(f"  {check['rule_id']:<26} {check['result']:<14} {value}")

    print("\n  Not shown: position weight, cash, P&L, average cost, capital at risk.")
    print("  Judge the research. The capital consequence is a separate screen.")


def cmd_adjudicate(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    job = ledger.job(args.job)

    if job["status"] != jobs.AWAITING_ADJUDICATION:
        raise FundError(f"job {args.job} is {job['status']}, not awaiting adjudication")
    if job["recipe"] == "idea_generation":
        raise FundError(
            "a screen produces research candidates, not a judgement to adjudicate. "
            "Read its findings with `fund jobs`, then underwrite one:\n"
            "  fund job open --security <TICKER> --observation preview_without_assessment "
            "--recipe onboarding_underwrite --mode de_novo"
        )
    proposal = job.get("result", {}).get("proposed_assessment")
    if proposal is None:
        raise FundError(f"job {args.job} carries no proposed assessment to adjudicate")

    security_id = job["security_id"]
    ticker = instruments.ticker_for(master, security_id)
    prior = ledger.latest_assessment(security_id)
    checks = []
    if job.get("thesis_id"):
        checks = [c for c in ledger.check_records(thesis_id=job["thesis_id"])][-5:]

    chosen = [name for name in ("accept", "reject", "replace", "defer", "acknowledge")
              if getattr(args, name)]
    if not chosen:
        _render_adjudication(job, prior, checks, ticker)
        print()
        print("  Nothing recorded. Choose one:")
        print("    --accept       with --sources-checked / --would-accept / --change-driver")
        print("    --reject       --reason '...'   (a factual error: the proposal is refused)")
        print("    --replace      write your own judgement, linked to this proposal")
        print("    --defer        --reason '...'")
        print("    --acknowledge  you are skipping the review; readiness cannot rise")
        return 0
    if len(chosen) > 1:
        raise FundError(f"choose one outcome, not {len(chosen)}: {', '.join(chosen)}")
    action = chosen[0]

    if action == "reject":
        if not args.reason:
            raise FundError("--reject needs --reason")
        ledger.save_job(jobs.adjudicate(job, outcome="rejected", reason=args.reason,
                                        minutes_spent=args.minutes))
        print(f"rejected   {args.job}")
        print(f"  {args.reason}")
        print("  No assessment was written. The proposal is not silently corrected.")
        return 0

    if action == "defer":
        if not args.reason:
            raise FundError("--defer needs --reason")
        ledger.save_job(jobs.adjudicate(job, outcome="deferred", reason=args.reason,
                                        minutes_spent=args.minutes))
        print(f"deferred   {args.job}")
        print(f"  {args.reason}")
        print("  It stays in Q1.")
        return 0

    material, why = jobs.material_change(proposal, prior)

    if action == "replace":
        if not (args.readiness and (args.downside or args.downside_unknown) and args.summary):
            raise FundError(
                "--replace needs --summary, --readiness and either --downside with "
                "--downside-scenario or --downside-unknown with --downside-reason"
            )
        readiness = args.readiness
        summary = args.summary
        if args.downside_unknown:
            downside: dict[str, Any] = {"status": "unknown",
                                        "reason": args.downside_reason or "not stated"}
        else:
            if not args.downside_scenario:
                raise FundError("--downside needs --downside-scenario")
            downside = {"status": "known",
                        "return_fraction": to_string(Decimal(args.downside)),
                        "scenario": args.downside_scenario}
        human_authored = True
        outcome = "human_authored_replacement"
    else:
        readiness = proposal["readiness"]
        summary = proposal["thesis_summary"]
        downside = dict(proposal["downside"])
        human_authored = False
        outcome = ("acknowledged_without_full_adjudication" if action == "acknowledge"
                   else "accepted")

    if action == "accept" and not args.change_driver and prior is not None:
        raise FundError("--change-driver is required when a previous assessment exists")
    if material and action in {"accept", "replace"} and not args.rationale:
        raise FundError(f"this is a material change ({why}); --rationale is required")
    if action == "accept" and args.sources_not_checked:
        raise FundError(
            "if you did not check the critical sources this is not a full adjudication; "
            "use --acknowledge instead"
        )

    acceptance: dict[str, Any] = {
        "accepted_at": _now(),
        "mode": ("acknowledged_without_full_adjudication" if action == "acknowledge"
                 else "human_adjudicated"),
        "critical_sources_checked": not args.sources_not_checked and action != "acknowledge",
        "would_accept_downside_without_position": not args.would_not_accept,
    }
    if args.change_driver:
        acceptance["main_change_driver"] = args.change_driver
    if args.rationale:
        acceptance["rationale"] = args.rationale
    if args.minutes is not None:
        acceptance["minutes_spent"] = args.minutes

    assessment: dict[str, Any] = {
        "assessment_id": ids.new_id(ids.ASSESSMENT),
        "security_id": security_id,
        "as_of": args.as_of or _today(),
        "assessment_mode": job["assessment_mode"],
        "thesis_summary": summary,
        "readiness": readiness,
        "downside": downside,
        "evidence_date": proposal["evidence_date"],
        "review_due": proposal["review_due"],
        "human_authored": human_authored,
        "acceptance": acceptance,
        "source_artifact": job["result"]["artifact"],
    }
    if job.get("thesis_id"):
        assessment["thesis_id"] = job["thesis_id"]
    if prior is not None:
        assessment["derived_from"] = prior["assessment_id"]
    elif job["assessment_mode"] != "de_novo":
        raise FundError(
            f"mode {job['assessment_mode']} needs a previous assessment and there is none"
        )

    result = ledger.commit([store.Write(kind=store.ASSESSMENT_RECORD.name, document=assessment)],
                           allow_duplicate=True)
    assessment_id = result.written[0]

    ledger.save_job(jobs.adjudicate(job, outcome=outcome, assessment_id=assessment_id,
                                    reason=args.rationale or args.reason,
                                    minutes_spent=args.minutes))

    if job.get("thesis_id"):
        _commit_thesis(ledger, thesis_module.assessment_event(
            thesis_id=job["thesis_id"], assessment_id=assessment_id,
            effective_date=assessment["as_of"]))

    label = {"accepted": "accepted", "human_authored_replacement": "replaced",
             "acknowledged_without_full_adjudication": "acknowledged"}[outcome]
    print(f"{label:<10} {args.job}")
    print(f"  assessment {assessment_id}  readiness {readiness}")
    if outcome == "acknowledged_without_full_adjudication":
        print("  acknowledged without full adjudication -- this cannot raise readiness")
    if outcome == "human_authored_replacement":
        print(f"  your judgement, linked to the proposal it replaces")
    if job.get("thesis_id") and _theses(ledger)[job["thesis_id"]].status == \
            thesis_module.REVIEW_REQUIRED:
        print(f"  the thesis is still review_required -- resolve it with "
              f"`fund thesis status {job['thesis_id']} --to ...`")
    return 0


# --------------------------------------------------------------------------
# observe and run -- the automated half
# --------------------------------------------------------------------------

def _filings_from_file(path: str, master: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    resolved: dict[str, list[dict[str, Any]]] = {}
    for token, entries in raw.items():
        security_id = instruments.resolve(master, token)
        resolved[security_id] = [dict(entry, security_id=security_id) for entry in entries]
    return resolved


def _filings_from_sec(master: dict[str, Any], ledger: store.Ledger,
                      security_ids: list[str], as_of: str) -> dict[str, list[dict[str, Any]]]:
    from datetime import date as _date

    from ..sec_client import SecClient

    client = SecClient()
    found: dict[str, list[dict[str, Any]]] = {}
    for security_id in security_ids:
        cik = None
        for issuer in master["issuers"]:
            if issuer["issuer_id"] == instruments.issuer_of(master, security_id):
                cik = issuer.get("cik")
        if not cik:
            raise FundError(
                f"{instruments.ticker_for(master, security_id)} has no CIK on file; "
                "add it with `fund instrument add --cik ...` before observing"
            )
        observations = observers.all_unseen(
            client, security_id=security_id, cik=cik,
            seen_accessions=ledger.seen_accessions(security_id),
            as_of=_date.fromisoformat(as_of),
        )
        found[security_id] = [
            {"security_id": o.security_id, "accession": o.accession, "form": o.form,
             "filing_date": o.filing_date, "report_date": o.report_date}
            for o in observations
        ]
    return found


def cmd_observe(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    as_of = args.as_of or _today()
    theses = _theses(ledger)

    watched = {history.document["security_id"]: history
               for history in theses.values()
               if history.status != thesis_module.CLOSED}
    if not watched:
        print("no open theses; nothing is being watched")
        return 0

    if args.filings:
        candidates = _filings_from_file(args.filings, master)
    else:
        candidates = _filings_from_sec(master, ledger, sorted(watched), as_of)

    opened, skipped = 0, 0
    for security_id, entries in sorted(candidates.items()):
        if security_id not in watched:
            continue
        seen = ledger.seen_accessions(security_id)
        fresh = [e for e in entries if e["accession"] not in seen]
        if not fresh:
            continue

        ticker = instruments.ticker_for(master, security_id)
        ledger.record_observed_filings(fresh)

        # Bounded on purpose: the first run on a company with twenty years of
        # history should produce one piece of work, not eighty. The rest are
        # marked seen above, so they never resurface.
        newest = sorted(fresh, key=lambda e: (e["filing_date"], e["accession"]),
                        reverse=True)[:args.limit]
        for entry in newest:
            history = watched[security_id]
            rule = dispatch.match("new_periodic_filing", has_open_thesis=True)
            if rule is None:
                skipped += 1
                continue

            contract = history.document.get("monitoring_contract")
            key = jobs.dedup_key(
                observation=rule.observation,
                security_id=security_id,
                thesis_id=history.thesis_id,
                evidence_accession=entry["accession"],
                monitoring_contract_version=contract["version"] if contract else None,
            )
            if ledger.job_for_dedup_key(key) is not None:
                skipped += 1
                continue

            snapshot = {
                "observation": rule.observation,
                "observed_at": _now(),
                "evidence_accession": entry["accession"],
                "evidence_date": entry["filing_date"],
                "detail": f"{entry['form']} filed {entry['filing_date']}",
            }
            if contract:
                snapshot["monitoring_contract_version"] = contract["version"]

            document = jobs.new_job(
                trigger_snapshot=snapshot,
                rule_id=rule.rule_id,
                rule_version=rule.version,
                recipe=rule.recipe,
                assessment_mode=rule.assessment_mode,
                security_id=security_id,
                dedup_key_value=key,
                thesis_id=history.thesis_id,
            )
            ledger.save_job(document)
            opened += 1
            print(f"{ticker:<8} {entry['form']:<8} {entry['filing_date']}  "
                  f"-> {document['job_id']}")

    if not opened:
        print("nothing new" + (f" ({skipped} already known)" if skipped else ""))
    else:
        print()
        print(f"{opened} job(s) opened. Run them with `fund run <job_id>`.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    job = ledger.job(args.job)

    if job["status"] not in jobs.ATTEMPTABLE:
        raise FundError(f"job {args.job} is {job['status']}; it cannot be run")

    if job["recipe"] == "idea_generation":
        return _run_discovery(args, ledger, job)

    theses = _theses(ledger)
    history = theses.get(job.get("thesis_id") or "")
    thesis_document = history.document if history else None

    prior = ledger.latest_assessment(job["security_id"])
    checks = ledger.check_records(thesis_id=job["thesis_id"]) if job.get("thesis_id") else []
    due_questions = (thesis_module.due_qualitative_checks(thesis_document, args.as_of or _today())
                     if thesis_document else [])

    evidence = None
    accession = job["trigger_snapshot"].get("evidence_accession")
    if accession:
        evidence = {"accession": accession,
                    "date": job["trigger_snapshot"].get("evidence_date", "")}

    try:
        pack = packs.build_pack(
            job=job,
            ticker=instruments.ticker_for(master, job["security_id"]),
            thesis=thesis_document,
            prior_assessment=prior,
            check_outcomes=checks[-5:],
            due_questions=due_questions,
            evidence=evidence,
        )
    except packs.PackError as exc:
        raise FundError(str(exc)) from exc

    # Next to the ledger the artefacts belong to, not next to the repository.
    # A second ledger (a test, a scratch book) must not scatter run output into
    # the working tree.
    workdir = Path(args.workdir) if args.workdir else (
        ledger.path.parent / "runs" / job["job_id"])

    if args.dry_run:
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "pack.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
        print(f"pack written to {workdir / 'pack.json'} -- nothing was run")
        return 0

    if args.stub:
        executor = recipes.stub_executor(
            json.loads(Path(args.stub).read_text(encoding="utf-8")))
    else:
        plugin_root = _pei_plugin_root()
        executor = recipes.codex_executor(plugin_root=plugin_root,
                                          repo_root=schemas.repo_root())

    running = jobs.start_attempt(job)
    ledger.save_job(running)

    try:
        result = recipes.run(recipe=job["recipe"], pack=pack, executor=executor,
                             workdir=workdir)
    except recipes.ContractFailure as exc:
        ledger.save_job(jobs.mark_contract_failed(running, str(exc)))
        raise FundError(
            f"{exc}\n  This will not be put in front of you. "
            "'The output could not be read' is not 'the analyst had nothing to say'."
        ) from exc
    except recipes.RecipeError as exc:
        ledger.save_job(jobs.fail_attempt(running, error_class="skill_transport_error",
                                          detail=str(exc)))
        raise FundError(str(exc)) from exc

    proposal = result.proposed_assessment
    artifact_path = result.final.artifact_path
    # POSIX separators: the schema's relativePath rejects backslashes, and a
    # ledger written on Windows has to stay readable anywhere.
    if artifact_path.is_relative_to(schemas.repo_root()):
        relative_path = artifact_path.relative_to(schemas.repo_root()).as_posix()
    else:
        relative_path = f"external/{job['job_id']}/{artifact_path.name}"
    artifact = {
        "relative_path": relative_path,
        "digest": "sha256:" + hashlib.sha256(
            artifact_path.read_bytes()).hexdigest(),
        "media_type": "application/json",
    }

    updated = jobs.attach_result(ledger.job(args.job), artifact=artifact,
                                 proposed_assessment=proposal)
    ledger.save_job(updated)

    print(f"ran        {args.job}  ({job['recipe']})")
    for step in result.steps:
        print(f"  {step.skill:<22} {len(step.sidecar['findings'])} finding(s)")
    if proposal:
        print(f"  proposes readiness {proposal['readiness']}")
    print(f"  artifacts in {workdir}")
    print(f"  adjudicate with: fund adjudicate {args.job}")
    return 0


def _run_discovery(args: argparse.Namespace, ledger: store.Ledger,
                   job: dict[str, Any]) -> int:
    tuning = dispatch.load_tuning()
    universe_id = (job["trigger_snapshot"].get("detail", "")
                   .replace("periodic screen of ", "").strip()
                   or tuning["discovery_universe"])
    pipeline_pack = None
    if args.pack:
        pipeline_pack = json.loads(Path(args.pack).read_text(encoding="utf-8"))
    elif not args.no_data:
        pipeline_pack = _build_idea_pack(universe_id, ledger.path.parent / "packs",
                                         refresh=not args.no_refresh)

    pack = screening.build_universe_pack(
        job=job, universe=load_universe(universe_id), universe_id=universe_id,
        pipeline_pack=pipeline_pack)

    workdir = Path(args.workdir) if args.workdir else (
        ledger.path.parent / "runs" / job["job_id"])
    if args.dry_run:
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "pack.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
        print(f"pack written to {workdir / 'pack.json'} -- nothing was run")
        print(f"  {len(pack['universe'])} names, nothing about what you hold")
        return 0

    executor = (recipes.stub_executor(json.loads(Path(args.stub).read_text(encoding="utf-8")))
                if args.stub else
                recipes.codex_executor(plugin_root=_pei_plugin_root(),
                                       repo_root=schemas.repo_root()))

    running = jobs.start_attempt(job)
    ledger.save_job(running)
    try:
        result = recipes.run(recipe="idea_generation", pack=pack, executor=executor,
                             workdir=workdir)
    except recipes.ContractFailure as exc:
        ledger.save_job(jobs.mark_contract_failed(running, str(exc)))
        raise FundError(str(exc)) from exc
    except recipes.RecipeError as exc:
        ledger.save_job(jobs.fail_attempt(running, error_class="skill_transport_error",
                                          detail=str(exc)))
        raise FundError(str(exc)) from exc

    artifact_path = result.final.artifact_path
    artifact = {
        "relative_path": (artifact_path.relative_to(schemas.repo_root()).as_posix()
                          if artifact_path.is_relative_to(schemas.repo_root())
                          else f"external/{job['job_id']}/{artifact_path.name}"),
        "digest": "sha256:" + hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        "media_type": "application/json",
    }
    ledger.save_job(jobs.attach_result(ledger.job(job["job_id"]), artifact=artifact))

    findings = result.final.sidecar["findings"]
    print(f"screened   {universe_id}  ({len(pack['universe'])} names)")
    print(f"  {len(findings)} candidate finding(s)")
    for finding in findings[:10]:
        print(f"    {finding['statement'][:90]}")
    print()
    print("  These are research candidates, not judgements. Underwrite one with:")
    print("    fund job open --security <TICKER> --observation preview_without_assessment \\")
    print("      --recipe onboarding_underwrite --mode de_novo")
    return 0


def _build_idea_pack(universe_id: str, out: Path, *, refresh: bool) -> dict[str, Any]:
    """Run the existing SEC/valuation pipeline and read what it produced.

    Reused rather than reimplemented: the screening data is the same data the
    rest of this repository already knows how to build, and a second pipeline
    would be a second set of numbers to reconcile.
    """
    import subprocess

    out.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(schemas.repo_root() / "scripts" / "us_pei_pack.py"),
               "--for", "idea", "--out", str(out)]
    if not refresh:
        command.append("--no-refresh")

    print(f"  building the screening data ({universe_id})"
          + ("" if refresh else ", no refresh") + " ...")
    completed = subprocess.run(command, cwd=schemas.repo_root(), capture_output=True,
                               text=True, encoding="utf-8")
    if completed.returncode != 0:
        raise FundError(
            "the screening data could not be built:\n  "
            + (completed.stderr or completed.stdout or "").strip()[:800]
            + "\n  Run with --no-data to screen on ticker symbols alone, or pass an "
              "existing pack with --pack."
        )
    pack_path = out / "pack.json"
    if not pack_path.is_file():
        raise FundError(f"the pipeline produced no pack.json in {out}")
    document = json.loads(pack_path.read_text(encoding="utf-8"))
    print(f"  {len(document.get('companies', []))} companies, "
          f"{pack_path.stat().st_size // 1024} KB")
    return document


def _pei_plugin_root() -> Path:
    import os

    override = os.environ.get("PEI_PLUGIN_ROOT")
    if override:
        return Path(override)
    base = Path.home() / ".codex" / "plugins" / "cache" / "openai-curated-remote" / \
        "public-equity-investing"
    versions = sorted((p for p in base.glob("*") if p.is_dir()), reverse=True)
    if not versions:
        raise FundError(
            "the public-equity-investing plugin was not found. "
            "Set PEI_PLUGIN_ROOT to its directory."
        )
    return versions[0]


def cmd_dispatch_health(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    rows = dispatch.health(jobs=ledger.jobs(), as_of=args.as_of or _today())
    print(f"{'RULE':<28} {'V':>2} {'ON':<4} {'30D':>4} {'FAIL':>5} LAST DISPATCHED")
    for row in rows:
        print(f"{row['rule_id']:<28} {row['version']:>2} "
              f"{'yes' if row['enabled'] else 'no':<4} {row['jobs_30d']:>4} "
              f"{row['failures_30d']:>5} {row['last_dispatched'] or 'never'}")
        if row["never_fired"]:
            print(f"{'':<28} ! this rule has never fired -- is it reaching anything?")
    return 0


# --------------------------------------------------------------------------
# research-cycle -- the threshold where the system starts driving itself
# --------------------------------------------------------------------------

def cmd_research_cycle(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    as_of = args.as_of or _today()
    report = cycle.new_report(as_of)

    def persist(detail: str | None = None) -> None:
        ledger.record_cycle({
            "cycle_id": report.cycle_id,
            "started_at": report.started_at,
            "finished_at": report.finished_at,
            "as_of": report.as_of,
            "status": report.status,
            "observed": report.observed,
            "jobs_opened": len(report.jobs_opened),
            "jobs_run": len(report.jobs_run),
            "jobs_failed": len(report.jobs_failed),
            "detail": detail or ("; ".join(report.notes) or None),
        })

    persist()
    print(f"CYCLE {report.cycle_id[:8]} -- {as_of}")

    try:
        theses = _theses(ledger)
        watched = {h.document["security_id"]: h for h in theses.values()
                   if h.status != thesis_module.CLOSED}

        observations: list[dict[str, Any]] = []

        # 1. New evidence.
        if args.filings:
            candidates = _filings_from_file(args.filings, master)
        elif watched:
            candidates = _filings_from_sec(master, ledger, sorted(watched), as_of)
        else:
            candidates = {}

        for security_id, entries in sorted(candidates.items()):
            if security_id not in watched:
                continue
            seen = ledger.seen_accessions(security_id)
            fresh = [e for e in entries if e["accession"] not in seen]
            if not fresh:
                continue
            ledger.record_observed_filings(fresh)
            newest = sorted(fresh, key=lambda e: (e["filing_date"], e["accession"]),
                            reverse=True)[:args.limit]
            for entry in newest:
                observations.append({
                    "observation": "new_periodic_filing",
                    "observed_at": _now(),
                    "evidence_accession": entry["accession"],
                    "evidence_date": entry["filing_date"],
                    "detail": f"{entry['form']} filed {entry['filing_date']}",
                    "_security_id": security_id,
                    "_thesis_id": watched[security_id].thesis_id,
                })

            # Earnings evidence: the Item 2.02 filing itself, never a date.
            observations.extend(observers.earnings_observations(
                fresh, security_id=security_id, thesis_id=watched[security_id].thesis_id))

        # 2. Reviews that have come due.
        observations.extend(observers.review_due_observations(theses, as_of=as_of))

        # 3. Price moves large enough to be worth re-reading a thesis for.
        tuning = dispatch.load_tuning()
        if args.mark or args.marks:
            currency = policy_module.load()["measurement"]["base_currency"]
            marks = _price_map(args, master, currency, pair_attr="mark", file_attr="marks")
            ledger.record_price_marks([
                {"security_id": security_id, "as_of": as_of,
                 "price": to_string(money.amount), "currency": money.currency}
                for security_id, money in marks.items()
            ])
        for security_id, history in sorted(watched.items()):
            observations.extend(observers.price_shock_observations(
                ledger.price_marks(security_id),
                security_id=security_id,
                thesis_id=history.thesis_id,
                threshold_bps=tuning["price_shock_bps"],
                window_days=tuning["price_shock_window_days"],
                as_of=as_of,
            ))

        # 4. Discovery, if it is switched on. Last, and rate-limited by
        #    attention rather than cost: a candidate not yet underwritten is a
        #    reason not to raise another.
        discovery_rule = dispatch.match("periodic_discovery", has_open_thesis=False)
        if discovery_rule is not None:
            existing = ledger.jobs()
            by_security = {h.document["security_id"]: h for h in theses.values()}
            last = max(
                (job["created_at"][:10] for job in existing
                 if job["trigger_snapshot"]["observation"] == "periodic_discovery"),
                default=None)
            decision = screening.should_run(
                as_of=as_of,
                last_discovery=last,
                open_candidates=screening.count_open_candidates(
                    existing, theses_by_security=by_security),
                open_positions=len(_funded_securities(ledger)),
                max_active_positions=policy_module.load()["capacity"]["max_active_positions"],
                interval_days=tuning["discovery_interval_days"],
                max_open_candidates=tuning["max_open_candidates"],
            )
            if decision.should_run:
                observations.append(screening.discovery_observation(
                    as_of=as_of, universe_id=tuning["discovery_universe"]))
            else:
                report.notes.append(f"discovery skipped: {decision.reason}")

        report.observed = len(observations)

        # 3. Match, merge, deduplicate.
        planned, duplicates = cycle.plan_work(
            observations, theses=theses,
            already_open=lambda key: ledger.job_for_dedup_key(key) is not None)
        report.skipped_duplicates = duplicates

        for work in planned:
            document = cycle.to_job(work)
            ledger.save_job(document)
            report.jobs_opened.append(document["job_id"])
            ticker = instruments.ticker_for(master, work.security_id)
            print(f"  opened   {ticker:<8} {work.trigger['observation']:<22} "
                  f"{document['job_id']}")

        # 4. Run what is runnable, one at a time.
        if not args.observe_only:
            pending = [job for job in ledger.jobs() if cycle.runnable(job)]
            executor = None
            if args.stub:
                executor = recipes.stub_executor(
                    json.loads(Path(args.stub).read_text(encoding="utf-8")))

            def run_one(job: dict[str, Any]) -> None:
                run_args = argparse.Namespace(
                    ledger=args.ledger, instruments=args.instruments, job=job["job_id"],
                    stub=args.stub, workdir=None, dry_run=False, as_of=as_of)
                if cmd_run(run_args) != 0:  # pragma: no cover -- cmd_run raises instead
                    raise FundError(f"{job['job_id']} did not complete")

            cycle.run_serially(pending, run_one=run_one, report=report, limit=args.max_jobs)

    except Exception as exc:  # noqa: BLE001 -- the cycle records its own failure
        cycle.finish(report, failed=str(exc)[:500])
        persist()
        print(f"  CYCLE FAILED: {exc}")
        print("  This is recorded; tomorrow's summary will show it.")
        return 1

    cycle.finish(report)
    persist()

    print()
    print(f"  {report.summary()}")
    for job_id, error in report.jobs_failed:
        print(f"  ! {job_id}: {error}")
    if report.jobs_opened or report.jobs_failed:
        print("  See `fund inbox` in the morning.")
    return 0


def cmd_discovery_status(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    tuning = dispatch.load_tuning()
    rule = dispatch.match("periodic_discovery", has_open_thesis=False)
    theses = _theses(ledger)
    by_security = {h.document["security_id"]: h for h in theses.values()}
    existing = ledger.jobs()
    last = max((job["created_at"][:10] for job in existing
                if job["trigger_snapshot"]["observation"] == "periodic_discovery"), default=None)

    decision = screening.should_run(
        as_of=args.as_of or _today(),
        last_discovery=last,
        open_candidates=screening.count_open_candidates(existing, theses_by_security=by_security),
        open_positions=len(_funded_securities(ledger)),
        max_active_positions=policy_module.load()["capacity"]["max_active_positions"],
        interval_days=tuning["discovery_interval_days"],
        max_open_candidates=tuning["max_open_candidates"],
    )

    print("DISCOVERY")
    print(f"  {'enabled':<22}{'yes' if rule else 'no'}")
    if rule is None:
        print("  Switch it on in config/fund/dispatch-tuning.json once the monitoring of")
        print("  the book you already own is reliable. Until then discovery is a way of")
        print("  not looking at what is already there.")
        return 0
    print(f"  {'universe':<22}{tuning['discovery_universe']}")
    print(f"  {'interval':<22}{tuning['discovery_interval_days']} days")
    print(f"  {'open candidates':<22}{decision.open_candidates} "
          f"(limit {tuning['max_open_candidates']})")
    print(f"  {'runs tonight':<22}{'yes' if decision.should_run else 'no'} -- {decision.reason}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    as_of = args.as_of or _today()

    runs = ledger.cycle_runs()
    beat = cycle.heartbeat_from(runs, as_of=as_of)
    queue = jobs.build_queue(ledger.jobs(), funded_security_ids=_funded_securities(ledger),
                             as_of=as_of)

    print(f"STATUS -- {as_of}")
    print()
    print(f"  {'Cycle':<14}{beat.describe(as_of)}")
    if not beat.healthy:
        print("  ! the automation is not healthy; do not read a quiet inbox as good news")
    if runs:
        last = runs[-1]
        print(f"  {'Last run':<14}{last['observed']} observed, {last['jobs_opened']} opened, "
              f"{last['jobs_run']} run, {last['jobs_failed']} failed")
        if last.get("detail"):
            print(f"  {'':<14}{last['detail']}")

    print()
    print(f"  {'Q0':<14}{len(queue.q0)} blocking")
    print(f"  {'Q1':<14}{len(queue.q1)} needing judgement "
          f"({jobs.total_estimate(queue)} min)")
    print(f"  {'Q2':<14}{len(queue.q2)} for information")

    if queue.q0:
        print()
        for item in queue.q0:
            ticker = instruments.ticker_for(master, item.job.get("security_id", "-"))
            print(f"  ! {ticker:<8} {item.reason}")
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    """Print the Task Scheduler registration, rather than running it."""
    python = sys.executable
    repo = schemas.repo_root()
    command = (
        f'schtasks /Create /TN "fund-research-cycle" /SC DAILY /ST {args.at} '
        f'/TR "\\"{python}\\" -m adapter.fund.cli research-cycle" '
        f'/RL LIMITED /F'
    )
    print("Register the nightly cycle with:")
    print()
    print(f"  {command}")
    print()
    print("Then open the task in Task Scheduler and tick:")
    print("  - Run task as soon as possible after a scheduled start is missed")
    print("    (StartWhenAvailable). Without it, a machine that was off overnight")
    print("    skips the night entirely rather than catching up.")
    print("  - Stop the task if it runs longer than 2 hours.")
    print()
    print(f"Working directory: {repo}")
    print(f"Set PYTHONPATH={repo / 'src'} if the package is not installed.")
    print()
    print("Check it is actually running with `fund status` -- a scheduled task that")
    print("silently stopped looks exactly like a quiet market.")
    return 0


def _coverage_report(ledger: store.Ledger) -> list[quality_module.Coverage]:
    coverages = []
    for history in _theses(ledger).values():
        if history.status == thesis_module.CLOSED:
            continue
        coverages.append(quality_module.coverage_for(
            history.thesis_id,
            contract=history.document.get("monitoring_contract"),
            check_records=ledger.check_records(thesis_id=history.thesis_id),
            evidence_seen=len(ledger.observed_filings(history.document["security_id"])),
        ))
    return coverages


def cmd_quality(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    master = _master(args)
    as_of = args.as_of or _today()
    theses = _theses(ledger)

    print(f"QUALITY -- {as_of}")
    print()
    print("MONITORING COVERAGE")
    coverages = _coverage_report(ledger)
    if not coverages:
        print("  no open theses")
    for coverage in coverages:
        history = theses[coverage.thesis_id]
        ticker = instruments.ticker_for(master, history.document["security_id"])
        marker = {"healthy": "ok", "degraded": "DEGRADED", "blind": "BLIND"}[coverage.state]
        print(f"  {ticker:<8} {marker:<10} {coverage.detail}")
    blind = [c for c in coverages if c.blocks_new_risk]
    if blind:
        print(f"  ! {len(blind)} thesis/theses are blind: they are in Q0 and new risk "
              "should not be increased on them")

    print()
    print("DISPATCH")
    for row in dispatch.health(jobs=ledger.jobs(), as_of=as_of):
        state = "on" if row["enabled"] else "off"
        print(f"  {row['rule_id']:<32} {state:<4} {row['jobs_30d']:>3} in 30d, "
              f"{row['failures_30d']} failed, last {row['last_dispatched'] or 'never'}")
        if row["never_fired"]:
            print(f"  {'':<32} ! never fired -- is it reaching anything?")

    print()
    print("ADJUDICATION")
    assessments = {a["assessment_id"]: a for a in ledger.assessments()}
    adjudication = quality_module.adjudication_quality(ledger.jobs(), assessments)
    if not adjudication.total:
        print("  nothing adjudicated yet")
    else:
        print(f"  {'adjudicated':<26}{adjudication.total}")
        print(f"  {'accepted unchanged':<26}{adjudication.accepted_unchanged} "
              f"({adjudication.unchanged_share * 100:.0f}%)")
        print(f"  {'rejected':<26}{adjudication.rejected}")
        print(f"  {'replaced with own view':<26}{adjudication.replaced}")
        print(f"  {'acknowledged only':<26}{adjudication.acknowledged}")
    for warning in adjudication.warnings:
        print(f"  ! {warning}")

    print()
    print("WEEKLY LOAD")
    load = quality_module.weekly_load(ledger.jobs(), as_of=as_of)
    print(f"  {'minutes per week':<26}{load.minutes_per_week:.0f} over {load.weeks} weeks "
          f"(target {quality_module.WEEKLY_MINUTES_TARGET[0]}-"
          f"{quality_module.WEEKLY_MINUTES_TARGET[1]})")
    if load.unrecorded:
        print(f"  ! {load.unrecorded} adjudication(s) recorded no time; pass --minutes "
              "so this can be measured rather than guessed")
    if load.over_target:
        print("  ! the load is above target. Write down why -- a system that quietly grows "
              "from 20 minutes to two hours has become something else.")

    print()
    print("FALSE ALARMS")
    transitions = [t for history in theses.values() for t in history.transitions]
    alarms = quality_module.false_alarms(transitions, as_of=as_of, window_days=args.window)
    print(f"  {'reviews triggered':<26}{alarms.reviews_triggered} in {args.window} days "
          f"(target {quality_module.FALSE_ALARM_TARGET[0]}-"
          f"{quality_module.FALSE_ALARM_TARGET[1]})")
    print(f"  {'measurement error':<26}{alarms.measurement_error}")
    print(f"  {'real but irrelevant':<26}{alarms.decision_irrelevant}")
    print(f"  {'thesis actually moved':<26}{alarms.thesis_changed}")
    for warning in alarms.warnings:
        print(f"  ! {warning}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    loaded = policy_module.load()
    currency = loaded["measurement"]["base_currency"]
    ledger = _ledger(args)
    master = _master(args)
    as_of = args.as_of or _today()

    _, valuation = _valuation(args, ledger, master, currency)
    if valuation.nav is None:
        raise FundError(
            "NAV is unavailable, so the report cannot be built. Missing prices: "
            + ", ".join(valuation.missing_prices)
        )

    assessments = {
        position.security_id: ledger.latest_assessment(position.security_id)
        for position in valuation.positions
    }
    content = report.build(
        policy=loaded,
        valuation=valuation,
        master=master,
        assessments={k: v for k, v in assessments.items() if v is not None},
        decisions=ledger.decisions(),
        nav_history=ledger.nav_history(),
        as_of=as_of,
    )
    destination = Path(args.out) if args.out else schemas.repo_root() / "data" / "fund" / "report.html"
    written = report.write(destination, content)
    print(f"wrote  {written}")
    print("  read-only projection; regenerate after any change")
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

    def with_prices(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument("--price", action="append", metavar="TICKER=AMOUNT")
        sub.add_argument("--prices", help="JSON file of {ticker: price}")
        sub.add_argument("--as-of")
        return sub

    assess = subparsers.add_parser(
        "assess",
        help="stage one: form the research judgement, with no capital figures on screen",
    )
    assess.add_argument("security", help="ticker or security id")
    assess.add_argument("--summary", required=True, help="what the thesis actually claims")
    assess.add_argument("--readiness", required=True,
                        choices=["watchlist", "starter", "core", "exceptional"])
    assess.add_argument("--downside", help="negative fraction, e.g. -0.30")
    assess.add_argument("--downside-scenario", help="what happens in that case, and why")
    assess.add_argument("--downside-unknown", action="store_true")
    assess.add_argument("--downside-reason", help="why the downside cannot be stated")
    assess.add_argument("--evidence-date", required=True,
                        help="date of the newest evidence, not today's date")
    assess.add_argument("--review-due", required=True)
    assess.add_argument("--mode", choices=["de_novo", "update_against_prior",
                                           "independent_then_reconcile"])
    assess.add_argument("--force-de-novo", action="store_true",
                        help="underwrite from scratch even though a prior assessment exists")
    assess.add_argument("--change-driver", help="what changed since the last assessment")
    assess.add_argument("--rationale", help="required on a material change")
    assess.add_argument("--minutes", type=int)
    assess.add_argument("--from-model", action="store_true",
                        help="the content came from a skill; you are accepting it")
    assess.add_argument("--acknowledge", action="store_true",
                        help="you are skipping the full review; this cannot raise readiness")
    assess.add_argument("--sources-not-checked", action="store_true")
    assess.add_argument("--would-not-accept", action="store_true",
                        help="you would NOT accept this downside if you did not already own it")
    assess.add_argument("--as-of")
    assess.set_defaults(handler=cmd_assess)

    assessments = subparsers.add_parser("assessments", help="list accepted research judgements")
    assessments.add_argument("--security")
    assessments.set_defaults(handler=cmd_assessments)

    preview = subparsers.add_parser(
        "trade-preview", help="stage two: test a contemplated trade against the policy")
    preview.add_argument("security")
    preview.add_argument("side", choices=["buy", "sell"])
    preview.add_argument("--quantity", required=True)
    preview.add_argument("--price", required=True,
                         help="contemplated execution price per share")
    preview.add_argument("--mark", action="append", metavar="TICKER=AMOUNT",
                         help="marking price for valuing the rest of the book")
    preview.add_argument("--marks", help="JSON file of {ticker: price}")
    preview.add_argument("--as-of")
    preview.add_argument("--assessment", help="defaults to the latest for this security")
    preview.add_argument("--decide", choices=list(decisions.DECIDE_CHOICES),
                         help="freeze a decision record; omit to preview only")
    preview.add_argument("--rationale", default="")
    preview.add_argument("--reason-code", help="required with --decide outside-policy")
    preview.add_argument("--next-review")
    preview.add_argument("--live", action="store_true",
                         help="leave shadow mode for this decision")
    preview.set_defaults(handler=cmd_trade_preview)

    trade_add = with_write_flags(subparsers.add_parser(
        "trade-add", help="attach a fill to a decision"))
    trade_add.add_argument("--decision", required=True)
    trade_add.add_argument("--quantity", required=True)
    trade_add.add_argument("--price", required=True)
    trade_add.add_argument("--fee")
    trade_add.set_defaults(handler=cmd_trade_add)

    review = with_prices(subparsers.add_parser("review", help="the monthly capital session"))
    review.add_argument("--no-change", metavar="TICKER",
                        help="record that this position is deliberately unchanged")
    review.add_argument("--rationale")
    review.add_argument("--reason-code")
    review.add_argument("--pending-review", action="store_true",
                        help="an adjudication is still open on this name")
    review.add_argument("--live", action="store_true")
    review.set_defaults(handler=cmd_review)

    thesis_parser = subparsers.add_parser("thesis", help="open and steer theses")
    thesis_sub = thesis_parser.add_subparsers(dest="thesis_command", required=True)

    t_open = thesis_sub.add_parser("open", help="open a thesis from an accepted assessment")
    t_open.add_argument("security")
    t_open.add_argument("--assessment", help="defaults to the latest for this security")
    t_open.add_argument("--statement", help="defaults to the assessment's thesis summary")
    t_open.add_argument("--as-of")
    t_open.set_defaults(handler=cmd_thesis_open)

    t_list = thesis_sub.add_parser("list", help="every thesis and its status")
    t_list.set_defaults(handler=cmd_thesis_list)

    t_show = thesis_sub.add_parser("show", help="one thesis, its contract and its history")
    t_show.add_argument("thesis", help="thesis id or ticker")
    t_show.add_argument("--as-of")
    t_show.set_defaults(handler=cmd_thesis_show)

    t_contract = thesis_sub.add_parser(
        "contract", help="activate a monitoring contract version")
    t_contract.add_argument("thesis")
    t_contract.add_argument("--from", dest="from_file", required=True,
                            help="JSON file; see `fund thesis contract-template`")
    t_contract.add_argument("--reason", help="required when replacing an active contract")
    t_contract.add_argument("--as-of")
    t_contract.set_defaults(handler=cmd_thesis_contract)

    t_template = thesis_sub.add_parser("contract-template", help="print a starter contract")
    t_template.set_defaults(handler=cmd_thesis_contract_template)

    t_status = thesis_sub.add_parser("status", help="move a thesis through its lifecycle")
    t_status.add_argument("thesis")
    t_status.add_argument("--to", required=True,
                          choices=["active", "review_required", "broken", "closed"])
    t_status.add_argument("--reason", required=True)
    t_status.add_argument("--resolution",
                          choices=["measurement_error", "decision_irrelevant_breach",
                                   "thesis_confirmed", "thesis_adjusted", "thesis_broken"],
                          help="required when leaving review_required")
    t_status.add_argument("--as-of")
    t_status.set_defaults(handler=cmd_thesis_status)

    t_close = thesis_sub.add_parser("close", help="wind a thesis up")
    t_close.add_argument("thesis")
    t_close.add_argument("--close-reason", required=True,
                         choices=["thesis_played_out", "thesis_broken", "better_use_of_capital",
                                  "position_exited", "superseded_by_new_thesis"])
    t_close.add_argument("--reason", required=True)
    t_close.add_argument("--superseded-by")
    t_close.add_argument("--as-of")
    t_close.set_defaults(handler=cmd_thesis_close)

    t_reviewed = thesis_sub.add_parser("reviewed", help="mark a qualitative check as reviewed")
    t_reviewed.add_argument("thesis")
    t_reviewed.add_argument("--check", required=True)
    t_reviewed.add_argument("--next-due", required=True)
    t_reviewed.add_argument("--as-of")
    t_reviewed.set_defaults(handler=cmd_thesis_reviewed)

    research_cycle = subparsers.add_parser(
        "research-cycle",
        help="the nightly pass: observe, match, deduplicate, run, queue")
    research_cycle.add_argument("--filings", help="JSON file instead of SEC")
    research_cycle.add_argument("--mark", action="append", metavar="TICKER=AMOUNT",
                                help="today's marking price, kept as the price-shock baseline")
    research_cycle.add_argument("--marks", help="JSON file of {ticker: price}")
    research_cycle.add_argument("--stub", help="JSON file of prepared sidecars instead of codex")
    research_cycle.add_argument("--limit", type=int, default=1,
                                help="most recent filings per security")
    research_cycle.add_argument("--max-jobs", type=int, default=5,
                                help="how many jobs to run in one pass")
    research_cycle.add_argument("--observe-only", action="store_true",
                                help="open work but run nothing")
    research_cycle.add_argument("--as-of")
    research_cycle.set_defaults(handler=cmd_research_cycle)

    status = subparsers.add_parser(
        "status", help="is the automation actually running, and what is waiting")
    status.add_argument("--as-of")
    status.set_defaults(handler=cmd_status)

    schedule = subparsers.add_parser("schedule", help="print the Task Scheduler setup")
    schedule.add_argument("--at", default="03:30", help="local start time, HH:MM")
    schedule.set_defaults(handler=cmd_schedule)

    observe = subparsers.add_parser(
        "observe", help="look for new evidence and open the work it implies")
    observe.add_argument("--filings", help="JSON file of {ticker: [filings]} instead of SEC")
    observe.add_argument("--limit", type=int, default=1,
                         help="most recent filings per security to open work for")
    observe.add_argument("--as-of")
    observe.set_defaults(handler=cmd_observe)

    run_parser = subparsers.add_parser("run", help="run a job's recipe")
    run_parser.add_argument("job")
    run_parser.add_argument("--stub", help="JSON file of prepared sidecars instead of codex")
    run_parser.add_argument("--workdir")
    run_parser.add_argument("--dry-run", action="store_true",
                            help="write the pack and stop")
    run_parser.add_argument("--pack", help="screening: an existing us_pei_pack.py idea pack")
    run_parser.add_argument("--no-refresh", action="store_true",
                            help="screening: build the data from what is already cached")
    run_parser.add_argument("--no-data", action="store_true",
                            help="screening: send ticker symbols only (not a real screen)")
    run_parser.add_argument("--as-of")
    run_parser.set_defaults(handler=cmd_run)

    discovery = subparsers.add_parser(
        "discovery", help="whether the screen is on, and whether it runs tonight")
    discovery.add_argument("--as-of")
    discovery.set_defaults(handler=cmd_discovery_status)

    quality = subparsers.add_parser(
        "quality", help="is the monitoring alive, and is the judgement real")
    quality.add_argument("--window", type=int, default=365)
    quality.add_argument("--as-of")
    quality.set_defaults(handler=cmd_quality)

    dispatch_parser = subparsers.add_parser("dispatch", help="the dispatch table")
    dispatch_sub = dispatch_parser.add_subparsers(dest="dispatch_command", required=True)
    d_health = dispatch_sub.add_parser("health", help="per-rule activity")
    d_health.add_argument("--as-of")
    d_health.set_defaults(handler=cmd_dispatch_health)

    job_parser = subparsers.add_parser("job", help="research jobs")
    job_sub = job_parser.add_subparsers(dest="job_command", required=True)

    j_open = job_sub.add_parser("open", help="open a research job")
    j_open.add_argument("--security", help="not for a screen: that is about a universe")
    j_open.add_argument("--universe", help="which universe to screen")
    j_open.add_argument("--observation", required=True,
                        choices=["new_periodic_filing", "earnings_evidence", "review_due",
                                 "mechanical_breach", "price_shock",
                                 "preview_without_assessment", "periodic_discovery"])
    j_open.add_argument("--recipe", required=True,
                        choices=["deep_dive_then_tracker", "tracker", "blind_review",
                                 "onboarding_underwrite", "idea_generation"])
    j_open.add_argument("--mode", required=True,
                        choices=["de_novo", "update_against_prior",
                                 "independent_then_reconcile"])
    j_open.add_argument("--rule-id", default="manual")
    j_open.add_argument("--rule-version", type=int, default=1)
    j_open.add_argument("--thesis", action="store_true", help="attach the open thesis")
    j_open.add_argument("--accession")
    j_open.add_argument("--evidence-date")
    j_open.add_argument("--review-due")
    j_open.add_argument("--deadline", help="decision deadline; urgency is a date, not an amount")
    j_open.add_argument("--as-of")
    j_open.set_defaults(handler=cmd_job_open)

    j_result = job_sub.add_parser("result", help="attach a skill result to a job")
    j_result.add_argument("job")
    j_result.add_argument("--artifact", required=True)
    j_result.add_argument("--digest")
    j_result.add_argument("--proposal", help="JSON file holding the proposed assessment")
    j_result.set_defaults(handler=cmd_job_result)

    j_fail = job_sub.add_parser("fail", help="record a failed attempt")
    j_fail.add_argument("job")
    j_fail.add_argument("--error-class", required=True,
                        choices=["data_source_error", "skill_transport_error",
                                 "contract_error", "late_result"])
    j_fail.add_argument("--detail", required=True)
    j_fail.set_defaults(handler=cmd_job_fail)

    jobs_parser = subparsers.add_parser("jobs", help="list research jobs")
    jobs_parser.add_argument("--status")
    jobs_parser.set_defaults(handler=cmd_jobs)

    inbox = subparsers.add_parser("inbox", help="the daily queue")
    inbox.add_argument("--as-of")
    inbox.add_argument("--verbose", action="store_true")
    inbox.set_defaults(handler=cmd_inbox)

    adjudicate = subparsers.add_parser(
        "adjudicate", help="judge one research result -- exactly one, never in bulk")
    adjudicate.add_argument("job")
    adjudicate.add_argument("--accept", action="store_true")
    adjudicate.add_argument("--reject", action="store_true")
    adjudicate.add_argument("--replace", action="store_true",
                            help="write your own judgement instead")
    adjudicate.add_argument("--defer", action="store_true")
    adjudicate.add_argument("--acknowledge", action="store_true")
    adjudicate.add_argument("--reason")
    adjudicate.add_argument("--change-driver")
    adjudicate.add_argument("--rationale")
    adjudicate.add_argument("--minutes", type=int)
    adjudicate.add_argument("--sources-not-checked", action="store_true")
    adjudicate.add_argument("--would-not-accept", action="store_true")
    adjudicate.add_argument("--summary", help="with --replace")
    adjudicate.add_argument("--readiness", choices=["watchlist", "starter", "core", "exceptional"])
    adjudicate.add_argument("--downside")
    adjudicate.add_argument("--downside-scenario")
    adjudicate.add_argument("--downside-unknown", action="store_true")
    adjudicate.add_argument("--downside-reason")
    adjudicate.add_argument("--as-of")
    adjudicate.set_defaults(handler=cmd_adjudicate)

    check = subparsers.add_parser("check", help="run a thesis's mechanical rules")
    check.add_argument("thesis", help="thesis id or ticker")
    check.add_argument("--observations", required=True,
                       help="JSON file of measured values from the data layer")
    check.add_argument("--evaluated-for", default="manual",
                       choices=["new_periodic_filing", "earnings_release", "material_8k",
                                "review_due", "manual"])
    check.add_argument("--accession", help="the filing this evaluation rests on")
    check.add_argument("--max-evidence-age-days", type=int)
    check.add_argument("--as-of")
    check.set_defaults(handler=cmd_check)

    checks = subparsers.add_parser("checks", help="list recorded mechanical checks")
    checks.add_argument("--thesis")
    checks.set_defaults(handler=cmd_checks)

    report_parser = with_prices(subparsers.add_parser(
        "report", help="write the read-only HTML view"))
    report_parser.add_argument("--out", help="destination file")
    report_parser.set_defaults(handler=cmd_report)

    decisions_parser = subparsers.add_parser("decisions", help="list frozen decisions")
    decisions_parser.set_defaults(handler=cmd_decisions)

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
