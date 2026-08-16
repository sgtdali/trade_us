"""Sizing under the capital policy: golden books and monotonicity properties.

The property tests sweep a grid rather than using a generator library, so the
suite gains no dependency and every failure is reproducible from its id. What
they assert is the part of the policy that has to hold no matter what: a policy
that could be made more permissive by making the news worse would not be a
risk framework, it would be a wish.
"""

from __future__ import annotations

import itertools
import json
from decimal import Decimal
from pathlib import Path

import pytest

from adapter.fund import ids, policy as policy_module, projection, sizing
from adapter.fund.money import Money, to_decimal, to_string

FIXTURES = Path(__file__).parent / "fixtures" / "fund" / "golden-books.json"
USD = "USD"


@pytest.fixture(scope="module")
def policy():
    return policy_module.load()


def golden_books():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))["books"]


def hydrate(event: dict) -> dict:
    """Turn a fixture's shorthand into a schema-valid account event."""
    document = {
        "event_id": ids.new_id(ids.ACCOUNT_EVENT),
        "recorded_at": "2026-08-16T00:00:00Z",
        **event,
    }
    for key in ("cash_amount", "price", "unit_cost", "fee"):
        if key in document and isinstance(document[key], str):
            document[key] = {"amount": document[key], "currency": USD}
    return document


def build(book: dict):
    state = projection.project([hydrate(event) for event in book["events"]])
    prices = {sid: Money.parse(price, USD) for sid, price in book["prices"].items()}
    valuation = projection.value(state, prices, as_of="2026-08-31", base_currency=USD)
    return state, valuation


# --------------------------------------------------------------- golden books

@pytest.mark.parametrize("book", golden_books(), ids=lambda b: b["name"])
def test_golden_book_matches_its_frozen_expectations(book):
    state, valuation = build(book)
    expected = book["expected"]

    assert to_string(valuation.nav.amount) == expected["nav"], book["description"]
    assert to_string(valuation.cash.amount) == expected["cash"]

    if "cash_weight" in expected:
        assert valuation.cash_weight == to_decimal(expected["cash_weight"])

    seen = {p.security_id: p for p in valuation.positions}
    assert set(seen) == set(expected["positions"])

    for security_id, wanted in expected["positions"].items():
        position = seen[security_id]
        assert to_string(position.quantity) == wanted["quantity"]
        assert to_string(position.market_value.amount) == wanted["market_value"]
        if "weight" in wanted:
            assert position.weight == to_decimal(wanted["weight"])
        if "cost_total" in wanted:
            assert to_string(position.cost_basis.total.amount) == wanted["cost_total"]
        if "cost_per_share" in wanted:
            assert to_string(position.cost_basis.per_share.amount) == wanted["cost_per_share"]
        if wanted.get("unrealized") is None and "unrealized" in wanted:
            assert position.unrealized_pnl is None
            assert position.unrealized_unavailable_reason == wanted["unrealized_reason"]
        elif "unrealized" in wanted:
            assert to_string(position.unrealized_pnl.amount) == wanted["unrealized"]

    realized = projection.total_realized(state, USD)
    assert to_string(realized.amount) == expected["realized_pnl"]


@pytest.mark.parametrize("book", [b for b in golden_books() if "breaches" in b["expected"]],
                         ids=lambda b: b["name"])
def test_golden_book_breaches_are_detected(book, policy):
    _, valuation = build(book)
    for security_id, wanted in book["expected"]["positions"].items():
        breaches = sizing.hard_breaches(
            policy,
            post_trade_weight=to_decimal(wanted["weight"]),
            post_trade_issuer_weight=to_decimal(wanted["weight"]),
            post_trade_cash=valuation.cash.amount,
            open_positions_after=len(valuation.positions),
        )
        assert set(book["expected"]["breaches"]).issubset(set(breaches))


def test_weights_and_cash_sum_to_one_in_every_golden_book():
    for book in golden_books():
        _, valuation = build(book)
        if valuation.nav is None or valuation.nav.amount == 0:
            continue
        total = sum((p.weight for p in valuation.positions), Decimal(0)) + valuation.cash_weight
        assert abs(total - Decimal(1)) < Decimal("1e-20"), book["name"]


# ------------------------------------------------------------ the worked case

def test_the_design_documents_worked_example(policy):
    """50 x $180 on a $100k book with a starter thesis and a -30% downside."""
    result = sizing.evaluate(
        policy,
        readiness="starter",
        downside_status="known",
        downside_return_fraction=Decimal("-0.30"),
        exposure=sizing.Exposure(nav=Decimal(100000), cash=Decimal(100000),
                                 current_weight=Decimal(0)),
    )
    assert result.binding_constraint == "downside_capacity"
    # 100 bp budget / 30% downside
    assert round(result.policy_compliant_max_weight, 6) == round(Decimal(1) / Decimal(30), 6)
    # 0.98 deployable / 10 slots x 0.5 starter
    assert result.ceiling("readiness_weight").max_weight == Decimal("0.049")
    assert result.ceiling("max_security_weight").max_weight == Decimal("0.1")

    allowed = sizing.whole_shares(sizing.quantity_for_weight(
        weight=result.policy_compliant_max_weight, nav=Decimal(100000), price=Decimal(180)))
    assert allowed == Decimal(18)


# --------------------------------------------------------------- properties

READINESS_ORDER = ["watchlist", "starter", "core"]
DOWNSIDES = ["-0.1", "-0.2", "-0.3", "-0.5", "-0.75", "-1"]
NAVS = ["50000", "100000", "1000000"]
WEIGHTS = ["0", "0.02", "0.05"]


def evaluate(policy, *, readiness="core", downside="-0.3", nav="100000",
             cash="100000", current_weight="0", issuer_other="0"):
    return sizing.evaluate(
        policy,
        readiness=readiness,
        downside_status="known",
        downside_return_fraction=to_decimal(downside),
        exposure=sizing.Exposure(
            nav=to_decimal(nav),
            cash=to_decimal(cash),
            current_weight=to_decimal(current_weight),
            issuer_weight_excluding_security=to_decimal(issuer_other),
        ),
    )


@pytest.mark.parametrize("readiness,nav", list(itertools.product(READINESS_ORDER, NAVS)))
def test_a_worse_downside_never_raises_the_ceiling(policy, readiness, nav):
    previous = None
    for downside in DOWNSIDES:  # increasingly bad
        result = evaluate(policy, readiness=readiness, downside=downside, nav=nav, cash=nav)
        ceiling = result.ceiling("downside_capacity").max_weight
        if previous is not None:
            assert ceiling <= previous, f"{downside} loosened the downside ceiling"
        previous = ceiling


@pytest.mark.parametrize("downside", DOWNSIDES)
def test_lower_readiness_never_raises_the_ceiling(policy, downside):
    previous = None
    for readiness in READINESS_ORDER:  # increasingly ready
        result = evaluate(policy, readiness=readiness, downside=downside)
        ceiling = result.ceiling("readiness_weight").max_weight
        if previous is not None:
            assert ceiling >= previous, f"{readiness} lowered the readiness ceiling"
        previous = ceiling


@pytest.mark.parametrize("downside,readiness", list(itertools.product(DOWNSIDES, READINESS_ORDER)))
def test_a_tighter_loss_budget_never_raises_the_ceiling(policy, downside, readiness):
    previous = None
    for budget in [200, 150, 100, 75, 50]:  # increasingly tight
        tightened = json.loads(json.dumps(policy))
        tightened["risk"]["position_loss_budget_bps_nav"] = budget
        result = evaluate(tightened, readiness=readiness, downside=downside)
        ceiling = result.policy_compliant_max_weight
        if previous is not None:
            assert ceiling <= previous, f"budget {budget} widened the ceiling"
        previous = ceiling


@pytest.mark.parametrize("current_weight", WEIGHTS)
def test_a_tighter_single_name_cap_never_raises_the_ceiling(policy, current_weight):
    previous = None
    for cap in [3000, 2000, 1500, 1000, 500, 200]:
        tightened = json.loads(json.dumps(policy))
        tightened["concentration"]["max_security_weight_bps"] = cap
        result = evaluate(tightened, current_weight=current_weight)
        if previous is not None:
            assert result.policy_compliant_max_weight <= previous
        previous = result.policy_compliant_max_weight


@pytest.mark.parametrize("issuer_other", ["0", "0.02", "0.05", "0.1", "0.2"])
def test_sibling_share_classes_eat_into_the_issuer_ceiling(policy, issuer_other):
    result = evaluate(policy, issuer_other=issuer_other)
    remaining = result.ceiling("issuer_capacity").max_weight
    cap = Decimal(policy["concentration"]["max_issuer_weight_bps"]) / Decimal(10000)
    assert remaining == max(cap - to_decimal(issuer_other), Decimal(0))


@pytest.mark.parametrize("cash", ["0", "1000", "2000", "5000", "100000"])
def test_the_operational_cash_floor_is_never_spendable(policy, cash):
    nav = Decimal(100000)
    floor = nav * Decimal(policy["cash"]["operational_floor_bps_nav"]) / Decimal(10000)
    result = evaluate(policy, nav=to_string(nav), cash=cash)
    spendable = result.ceiling("cash_capacity").max_weight * nav
    assert spendable <= max(to_decimal(cash) - floor, Decimal(0)) + Decimal("1e-18")


def test_an_unknown_downside_blocks_new_risk_without_forcing_a_sale(policy):
    result = sizing.evaluate(
        policy,
        readiness="core",
        downside_status="unknown",
        downside_return_fraction=None,
        exposure=sizing.Exposure(nav=Decimal(100000), cash=Decimal(50000),
                                 current_weight=Decimal("0.04")),
    )
    assert result.binding_constraint == "downside_capacity"
    # Exactly what is already held: no addition, and no forced reduction either.
    assert result.policy_compliant_max_weight == Decimal("0.04")


def test_watchlist_carries_no_capital(policy):
    result = evaluate(policy, readiness="watchlist")
    assert result.ceiling("readiness_weight").max_weight == Decimal(0)
    assert result.policy_compliant_max_weight == Decimal(0)
    assert result.binding_constraint == "readiness_weight"


def test_a_disabled_readiness_tier_is_not_a_free_pass(policy):
    result = evaluate(policy, readiness="exceptional")
    assert result.readiness_multiplier is None
    assert result.policy_compliant_max_weight == Decimal(0)


def test_readiness_can_never_widen_a_hard_limit(policy):
    """Even with a downside so mild the loss budget stops binding."""
    generous = json.loads(json.dumps(policy))
    generous["sizing"]["readiness_multipliers"]["core"] = "100"
    result = evaluate(generous, readiness="core", downside="-0.01")
    assert result.policy_compliant_max_weight <= Decimal("0.1")
    assert result.binding_constraint in {"max_security_weight", "issuer_capacity"}


# --------------------------------------------------------------- no-trade band

@pytest.mark.parametrize("target", ["0.01", "0.03", "0.05", "0.1"])
def test_drift_inside_the_band_is_not_a_trade(policy, target):
    target_weight = to_decimal(target)
    band = sizing.no_trade_band(policy, current_weight=target_weight, target_weight=target_weight)
    assert not band.trade_candidate

    just_inside = target_weight + band.half_width
    assert not sizing.no_trade_band(
        policy, current_weight=just_inside, target_weight=target_weight).trade_candidate


@pytest.mark.parametrize("target", ["0.01", "0.03", "0.05", "0.1"])
def test_the_band_never_shrinks_below_its_absolute_floor(policy, target):
    band = sizing.no_trade_band(policy, current_weight=to_decimal(target),
                                target_weight=to_decimal(target))
    absolute = Decimal(policy["trading"]["no_trade_band"]["absolute_bps"]) / Decimal(10000)
    assert band.half_width >= absolute


# ------------------------------------------------------------------- drawdown

@pytest.mark.parametrize("drawdown,expected", [
    ("-0.05", None),
    ("-0.10", "warn"),
    ("-0.14", "warn"),
    ("-0.15", "freeze_additions"),
    ("-0.19", "freeze_additions"),
    ("-0.20", "full_reunderwrite"),
    ("-0.40", "full_reunderwrite"),
])
def test_the_drawdown_ladder_reports_the_deepest_rung_reached(policy, drawdown, expected):
    assert sizing.drawdown_response(policy, to_decimal(drawdown)) == expected


def test_no_rung_of_the_ladder_sells_anything(policy):
    responses = {rung["response"] for rung in policy["risk"]["drawdown_response_ladder"]}
    assert responses <= {"warn", "freeze_additions", "full_reunderwrite"}
    assert policy["risk"]["automatic_liquidation"] == "disabled"


# --------------------------------------------------------------------- errors

def test_sizing_needs_a_positive_nav(policy):
    with pytest.raises(sizing.SizingError, match="positive NAV"):
        evaluate(policy, nav="0", cash="0")


def test_an_unknown_readiness_tier_is_refused(policy):
    with pytest.raises(sizing.SizingError, match="unknown readiness"):
        evaluate(policy, readiness="legendary")


def test_whole_shares_round_down(policy):
    assert sizing.whole_shares(Decimal("18.99")) == Decimal(18)
    assert sizing.whole_shares(Decimal("18")) == Decimal(18)
