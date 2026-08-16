"""Folding the event stream into positions, cash and NAV.

Nothing here is stored. Every number this module returns is recomputed from the
ledger on demand, which is what makes the ledger the only thing that has to be
right: a projection cannot drift from its source if it has no life of its own.

Two refusals are deliberate and load-bearing:

* A position whose cost basis is unknown reports **no** unrealized P&L. Not
  zero, not the market value -- nothing. Writing zero would silently claim the
  shares were free and turn a 100% phantom gain loose in every report.
* A NAV missing a price for a held security is **unavailable**, not partial.
  The policy says fail_closed, and a NAV quietly short one position is worse
  than no NAV, because it looks like an answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

from .errors import ProjectionError
from .money import Money, add, divide, multiply, to_decimal, to_string, zero

CASH_IN = frozenset({"opening_cash", "deposit", "dividend"})
CASH_OUT = frozenset({"withdrawal", "fee"})


@dataclass(frozen=True)
class CostBasis:
    """What a position cost, when that is actually knowable."""

    status: str  # "known" | "unknown"
    total: Money | None = None
    per_share: Money | None = None

    @property
    def known(self) -> bool:
        return self.status == "known"

    @staticmethod
    def unknown() -> "CostBasis":
        return CostBasis(status="unknown")


@dataclass
class Position:
    security_id: str
    quantity: Decimal
    cost_basis: CostBasis

    @property
    def is_open(self) -> bool:
        return self.quantity != 0


@dataclass
class PortfolioState:
    """Positions and cash as of the last event folded in."""

    positions: dict[str, Position] = field(default_factory=dict)
    cash: dict[str, Money] = field(default_factory=dict)
    realized_pnl: dict[str, Money] = field(default_factory=dict)
    realized_pnl_complete: bool = True
    events_applied: int = 0
    events_superseded: int = 0
    warnings: list[str] = field(default_factory=list)

    def open_positions(self) -> dict[str, Position]:
        return {sid: p for sid, p in self.positions.items() if p.is_open}

    def cash_in(self, currency: str) -> Money:
        return self.cash.get(currency, zero(currency))


# --------------------------------------------------------------------------
# Folding
# --------------------------------------------------------------------------

def _superseded_ids(events: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(event["corrects_event_id"])
        for event in events
        if event.get("corrects_event_id")
    }


def _money(document: Mapping[str, Any]) -> Money:
    return Money.from_document(document)


def _credit(state: PortfolioState, amount: Money) -> None:
    state.cash[amount.currency] = state.cash_in(amount.currency) + amount


def _debit(state: PortfolioState, amount: Money) -> None:
    state.cash[amount.currency] = state.cash_in(amount.currency) - amount


def _position(state: PortfolioState, security_id: str) -> Position:
    if security_id not in state.positions:
        state.positions[security_id] = Position(
            security_id=security_id,
            quantity=Decimal(0),
            cost_basis=CostBasis(status="known", total=None, per_share=None),
        )
    return state.positions[security_id]


def _add_realized(state: PortfolioState, amount: Money) -> None:
    state.realized_pnl[amount.currency] = (
        state.realized_pnl.get(amount.currency, zero(amount.currency)) + amount
    )


def _rebase(position: Position, new_total: Money | None, quantity: Decimal) -> None:
    """Recompute per-share cost after the quantity or the total moved."""
    if new_total is None or quantity == 0:
        position.cost_basis = CostBasis(status=position.cost_basis.status, total=new_total)
        return
    position.cost_basis = CostBasis(
        status=position.cost_basis.status,
        total=new_total,
        per_share=Money(divide(new_total.amount, quantity), new_total.currency),
    )


def project(events: Iterable[Mapping[str, Any]]) -> PortfolioState:
    """Fold events, in the order given, into a portfolio state.

    Corrections are honoured here rather than at read time: an event named by
    some later event's ``corrects_event_id`` is skipped entirely, and the
    correcting event -- whether a replacement or a bare void -- takes its place.
    """
    ordered = list(events)
    superseded = _superseded_ids(ordered)
    state = PortfolioState()

    for event in ordered:
        event_id = str(event.get("event_id", ""))
        if event_id in superseded:
            state.events_superseded += 1
            continue

        event_type = event["event_type"]

        if event_type == "correction":
            # A pure void. Its only effect was removing its target above.
            state.events_applied += 1
            continue

        if event_type == "opening_position":
            position = _position(state, event["security_id"])
            quantity = to_decimal(event["quantity"])
            position.quantity = add(position.quantity, quantity)
            if event["cost_basis_status"] == "known":
                per_share = _money(event["unit_cost"])
                _rebase(position, per_share.scaled_by(quantity), position.quantity)
            else:
                # The position carries the gap; the book-wide realized total is
                # still complete until one of these shares is actually sold.
                position.cost_basis = CostBasis.unknown()
                state.warnings.append(
                    f"{event['security_id']}: opening cost basis unknown, "
                    "P&L is not computed for this position"
                )

        elif event_type == "buy":
            position = _position(state, event["security_id"])
            quantity = to_decimal(event["quantity"])
            consideration = _money(event["price"]).scaled_by(quantity)
            if "fee" in event:
                consideration = consideration + _money(event["fee"])
            _debit(state, consideration)
            position.quantity = add(position.quantity, quantity)
            if position.cost_basis.known:
                previous = position.cost_basis.total or zero(consideration.currency)
                _rebase(position, previous + consideration, position.quantity)

        elif event_type == "sell":
            position = _position(state, event["security_id"])
            quantity = to_decimal(event["quantity"])
            if quantity > position.quantity:
                raise ProjectionError(
                    f"{event['security_id']}: selling {to_string(quantity)} shares "
                    f"but only {to_string(position.quantity)} are held -- "
                    "shorting is disabled, so this is a data error"
                )
            gross = _money(event["price"]).scaled_by(quantity)
            fee = _money(event["fee"]) if "fee" in event else None
            proceeds = gross - fee if fee else gross
            _credit(state, proceeds)

            if position.cost_basis.known and position.cost_basis.per_share is not None:
                released = position.cost_basis.per_share.scaled_by(quantity)
                _add_realized(state, proceeds - released)
                remaining_total = (position.cost_basis.total or zero(gross.currency)) - released
                position.quantity = add(position.quantity, -quantity)
                _rebase(position, remaining_total, position.quantity)
            else:
                position.quantity = add(position.quantity, -quantity)
                state.realized_pnl_complete = False

        elif event_type == "quantity_adjustment":
            position = _position(state, event["security_id"])
            position.quantity = add(position.quantity, to_decimal(event["quantity"]))
            if position.quantity < 0:
                raise ProjectionError(
                    f"{event['security_id']}: adjustment drives the share count negative"
                )
            # A split changes the count, not what was paid.
            _rebase(position, position.cost_basis.total, position.quantity)

        elif event_type in CASH_IN:
            _credit(state, _money(event["cash_amount"]))

        elif event_type in CASH_OUT:
            _debit(state, _money(event["cash_amount"]))

        else:  # pragma: no cover -- the schema's enum is closed
            raise ProjectionError(f"unhandled event_type: {event_type!r}")

        state.events_applied += 1

    for currency, balance in state.cash.items():
        if balance.amount < 0:
            state.warnings.append(
                f"cash in {currency} is negative ({balance}) -- leverage is disabled, "
                "so this points at a missing deposit or a mis-entered fill"
            )

    return state


# --------------------------------------------------------------------------
# Valuation
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PositionValuation:
    security_id: str
    quantity: Decimal
    price: Money | None
    market_value: Money | None
    weight: Decimal | None
    cost_basis: CostBasis
    unrealized_pnl: Money | None
    unrealized_unavailable_reason: str | None


@dataclass(frozen=True)
class Valuation:
    as_of: str
    base_currency: str
    nav: Money | None
    cash: Money
    invested: Money | None
    positions: tuple[PositionValuation, ...]
    missing_prices: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def nav_available(self) -> bool:
        return self.nav is not None

    def weight_of(self, security_id: str) -> Decimal | None:
        for position in self.positions:
            if position.security_id == security_id:
                return position.weight
        return None

    @property
    def cash_weight(self) -> Decimal | None:
        if self.nav is None or self.nav.amount == 0:
            return None
        return divide(self.cash.amount, self.nav.amount)


def value(
    state: PortfolioState,
    prices: Mapping[str, Money],
    *,
    as_of: str,
    base_currency: str,
) -> Valuation:
    """Price a state. Missing a single price makes NAV unavailable, not partial."""
    foreign = sorted(currency for currency in state.cash if currency != base_currency)
    if foreign:
        raise ProjectionError(
            f"cash held in {', '.join(foreign)} but the base currency is {base_currency}: "
            "conversion needs a dated rate, which this version does not carry"
        )
    cash = state.cash_in(base_currency)

    open_positions = state.open_positions()
    missing = tuple(sorted(sid for sid in open_positions if sid not in prices))

    invested: Money | None = zero(base_currency)
    priced: list[tuple[Position, Money, Money]] = []
    for security_id, position in sorted(open_positions.items()):
        price = prices.get(security_id)
        if price is None:
            invested = None
            continue
        if price.currency != base_currency:
            raise ProjectionError(
                f"{security_id} priced in {price.currency}, base currency is {base_currency}"
            )
        market_value = price.scaled_by(position.quantity)
        priced.append((position, price, market_value))
        if invested is not None:
            invested = invested + market_value

    nav = cash + invested if invested is not None else None

    valuations: list[PositionValuation] = []
    for security_id, position in sorted(open_positions.items()):
        price = prices.get(security_id)
        market_value = price.scaled_by(position.quantity) if price else None

        weight: Decimal | None = None
        if nav is not None and market_value is not None and nav.amount != 0:
            weight = divide(market_value.amount, nav.amount)

        unrealized: Money | None = None
        reason: str | None = None
        if not position.cost_basis.known:
            reason = "cost_basis_unknown"
        elif market_value is None:
            reason = "price_unavailable"
        elif position.cost_basis.total is None:
            reason = "cost_basis_unknown"
        else:
            unrealized = market_value - position.cost_basis.total

        valuations.append(
            PositionValuation(
                security_id=security_id,
                quantity=position.quantity,
                price=price,
                market_value=market_value,
                weight=weight,
                cost_basis=position.cost_basis,
                unrealized_pnl=unrealized,
                unrealized_unavailable_reason=reason,
            )
        )

    warnings = list(state.warnings)
    if missing:
        warnings.append(
            "NAV unavailable: no price for " + ", ".join(missing)
        )

    return Valuation(
        as_of=as_of,
        base_currency=base_currency,
        nav=nav,
        cash=cash,
        invested=invested,
        positions=tuple(valuations),
        missing_prices=missing,
        warnings=tuple(warnings),
    )


def deployable_capital_fraction(valuation: Valuation, operational_floor_bps: int) -> Decimal:
    """Share of NAV that may be put to work, after the operational cash floor."""
    if valuation.nav is None or valuation.nav.amount <= 0:
        raise ProjectionError("deployable capital needs a positive NAV")
    floor = divide(Decimal(operational_floor_bps), Decimal(10000))
    return add(Decimal(1), -floor)


def total_realized(state: PortfolioState, base_currency: str) -> Money | None:
    """None when any disposal lacked a cost basis -- a partial total is a lie."""
    if not state.realized_pnl_complete:
        return None
    return state.realized_pnl.get(base_currency, zero(base_currency))


def multiply_quantity(quantity: Decimal, factor: Decimal) -> Decimal:
    return multiply(quantity, factor)
