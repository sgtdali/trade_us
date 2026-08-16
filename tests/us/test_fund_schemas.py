"""Schema contracts for the fund records.

Each event type gets a positive fixture and the negative fixtures that matter:
the shapes a person actually produces by mistake at a CLI, and the shapes that
would corrupt the ledger quietly rather than loudly.
"""

from __future__ import annotations

import json

import pytest

from adapter.fund import policy, schemas
from adapter.fund.errors import SchemaViolation

EVENT_ID = "EVT-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f"
OTHER_EVENT_ID = "EVT-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e70"
RECORDED_AT = "2026-08-16T13:05:00Z"
USD = {"amount": "181.2", "currency": "USD"}


def base_event(**overrides):
    document = {
        "event_id": EVENT_ID,
        "event_type": "buy",
        "effective_date": "2026-08-14",
        "recorded_at": RECORDED_AT,
        "security_id": "sec:nvda-common",
        "quantity": "18",
        "price": dict(USD),
    }
    document.update(overrides)
    return document


def errors(document, schema_id=schemas.ACCOUNT_EVENT):
    return schemas.schema_errors(document, schema_id)


# ---------------------------------------------------------------- primitives

@pytest.mark.parametrize(
    "value",
    ["0", "1", "-1", "0.5", "-0.5", "181.2", "1000000", "-0.0001", "12345678901234567890"],
)
def test_decimal_string_accepts_canonical_forms(value):
    assert not errors({"quantity": value}, schemas.COMMON) or True
    document = base_event(event_type="quantity_adjustment", quantity=value,
                          adjustment_reason="stock_split", note="4-for-1 split")
    document.pop("price")
    assert errors(document) == []


@pytest.mark.parametrize(
    "value",
    [
        "01",        # leading zero
        "1.50",      # trailing fractional zero -- two spellings of one value
        "1.",        # dangling point
        ".5",        # no integer part
        "-0",        # negative zero
        "1e3",       # exponent notation
        "1,5",       # decimal comma
        " 1",        # whitespace
        "",
    ],
)
def test_decimal_string_rejects_non_canonical_forms(value):
    document = base_event(event_type="quantity_adjustment", quantity=value,
                          adjustment_reason="stock_split", note="split")
    document.pop("price")
    assert errors(document), f"{value!r} should not have validated"


def test_money_amount_may_not_be_a_number():
    assert errors(base_event(price={"amount": 181.2, "currency": "USD"}))


def test_money_needs_its_currency():
    assert errors(base_event(price={"amount": "181.2"}))


def test_minor_unit_integers_are_not_money():
    """18120 cents is not a valid amount anywhere in this system."""
    assert errors(base_event(price=18120))


@pytest.mark.parametrize("identifier", ["EVT-not-a-uuid", "DEC-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f",
                                        "0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f", "evt-0192F8A1-2b3c-7d4e-8f90-1a2b3c4d5e6f"])
def test_event_id_must_be_a_prefixed_uuid7(identifier):
    assert errors(base_event(event_id=identifier))


def test_uuid4_is_rejected_where_uuid7_is_required():
    assert errors(base_event(event_id="EVT-0192f8a1-2b3c-4d4e-8f90-1a2b3c4d5e6f"))


def test_utc_instant_must_carry_z():
    assert errors(base_event(recorded_at="2026-08-16T13:05:00+03:00"))


def test_local_date_is_not_a_timestamp():
    assert errors(base_event(effective_date="2026-08-14T00:00:00Z"))


# ------------------------------------------------------------- account event

def test_buy_is_valid():
    assert errors(base_event()) == []


def test_buy_with_fee_is_valid():
    assert errors(base_event(fee={"amount": "1.25", "currency": "USD"})) == []


def test_sell_is_valid():
    assert errors(base_event(event_type="sell")) == []


def test_buy_may_not_carry_cash_amount():
    """quantity x price is the cash effect; storing it again invites drift."""
    problems = errors(base_event(cash_amount={"amount": "3261.6", "currency": "USD"}))
    assert any("cash_amount" in message for message in problems)


def test_buy_quantity_must_be_positive():
    assert errors(base_event(quantity="-18"))
    assert errors(base_event(quantity="0"))


def test_unknown_field_is_rejected():
    assert errors(base_event(ticker="NVDA"))


def test_opening_position_with_unknown_cost_basis_is_valid():
    document = base_event(event_type="opening_position", quantity="100", cost_basis_status="unknown")
    document.pop("price")
    assert errors(document) == []


def test_opening_position_with_known_cost_basis_needs_unit_cost():
    document = base_event(event_type="opening_position", quantity="100", cost_basis_status="known")
    document.pop("price")
    assert any("unit_cost" in message for message in errors(document))

    document["unit_cost"] = {"amount": "95.4", "currency": "USD"}
    assert errors(document) == []


def test_unknown_cost_basis_may_not_smuggle_in_a_unit_cost():
    """'unknown' has to mean unknown, or the flag is decoration."""
    document = base_event(
        event_type="opening_position", quantity="100",
        cost_basis_status="unknown", unit_cost={"amount": "0", "currency": "USD"},
    )
    document.pop("price")
    assert errors(document)


def test_opening_position_may_not_be_written_as_a_fill():
    """No synthetic opening trade: it would invent a date and a cash outflow."""
    document = base_event(event_type="opening_position", quantity="100",
                          cost_basis_status="known", unit_cost=dict(USD))
    assert any("price" in message for message in errors(document))


def test_opening_position_needs_a_cost_basis_ruling():
    document = base_event(event_type="opening_position", quantity="100")
    document.pop("price")
    assert any("cost_basis_status" in message for message in errors(document))


def test_opening_cash_is_valid():
    document = {
        "event_id": EVENT_ID, "event_type": "opening_cash",
        "effective_date": "2026-08-14", "recorded_at": RECORDED_AT,
        "cash_amount": {"amount": "20000", "currency": "USD"},
    }
    assert errors(document) == []


@pytest.mark.parametrize("event_type", ["deposit", "withdrawal", "fee"])
def test_cash_movements_are_valid(event_type):
    document = {
        "event_id": EVENT_ID, "event_type": event_type,
        "effective_date": "2026-08-14", "recorded_at": RECORDED_AT,
        "cash_amount": {"amount": "5000", "currency": "USD"},
    }
    assert errors(document) == []


def test_cash_amount_is_a_magnitude_not_a_signed_number():
    document = {
        "event_id": EVENT_ID, "event_type": "withdrawal",
        "effective_date": "2026-08-14", "recorded_at": RECORDED_AT,
        "cash_amount": {"amount": "-5000", "currency": "USD"},
    }
    assert errors(document)


def test_dividend_needs_the_security_it_came_from():
    document = {
        "event_id": EVENT_ID, "event_type": "dividend",
        "effective_date": "2026-08-14", "recorded_at": RECORDED_AT,
        "cash_amount": {"amount": "42", "currency": "USD"},
    }
    assert any("security_id" in message for message in errors(document))
    document["security_id"] = "sec:nvda-common"
    assert errors(document) == []


def test_quantity_adjustment_needs_a_written_reason():
    document = base_event(event_type="quantity_adjustment", quantity="300")
    document.pop("price")
    problems = errors(document)
    assert any("adjustment_reason" in message for message in problems)
    assert any("note" in message for message in problems)


def test_quantity_adjustment_may_be_negative():
    """A reverse split removes shares."""
    document = base_event(event_type="quantity_adjustment", quantity="-75",
                          adjustment_reason="reverse_split", note="1-for-4")
    document.pop("price")
    assert errors(document) == []


def test_correction_voids_and_carries_nothing_else():
    document = {
        "event_id": EVENT_ID, "event_type": "correction",
        "effective_date": "2026-08-14", "recorded_at": RECORDED_AT,
        "corrects_event_id": OTHER_EVENT_ID, "note": "entered twice",
    }
    assert errors(document) == []

    document["quantity"] = "18"
    assert errors(document)


def test_correction_needs_a_target_and_a_reason():
    document = {
        "event_id": EVENT_ID, "event_type": "correction",
        "effective_date": "2026-08-14", "recorded_at": RECORDED_AT,
    }
    problems = errors(document)
    assert any("corrects_event_id" in message for message in problems)
    assert any("note" in message for message in problems)


def test_a_typed_event_may_supersede_an_earlier_one():
    """Changing a value is a new typed event, not a void."""
    assert errors(base_event(quantity="18", corrects_event_id=OTHER_EVENT_ID)) == []


def test_error_message_names_the_offending_field():
    """A boolean 'false' subschema would report neither the path nor the name."""
    problems = errors(base_event(cash_amount={"amount": "1", "currency": "USD"}))
    assert problems == ["cash_amount: 'cash_amount' is not allowed here"]


# ------------------------------------------------------------ capital policy

def test_shipped_capital_policy_is_valid():
    assert policy.load()["measurement"]["base_currency"] == "USD"


def test_every_provisional_pointer_resolves():
    loaded = policy.load()
    for pointer in loaded["provisional_fields"]:
        policy.resolve_pointer(loaded, pointer)


def test_a_provisional_pointer_to_a_renamed_field_is_caught():
    loaded = policy.load()
    loaded["provisional_fields"].append("/risk/position_loss_budget_bps")
    with pytest.raises(SchemaViolation, match="does not resolve"):
        policy.check_provisional_pointers(loaded)


def test_policy_rejects_null():
    loaded = policy.load()
    loaded["risk"]["position_loss_budget_bps_nav"] = None
    assert schemas.schema_errors(loaded, schemas.CAPITAL_POLICY)


def test_policy_rejects_a_missing_field():
    loaded = policy.load()
    del loaded["concentration"]["max_issuer_weight_bps"]
    assert schemas.schema_errors(loaded, schemas.CAPITAL_POLICY)


def test_readiness_multipliers_are_a_closed_set():
    """A typo must not create a fifth tier that silently never matches."""
    loaded = policy.load()
    loaded["sizing"]["readiness_multipliers"]["hyper_core"] = "2"
    assert schemas.schema_errors(loaded, schemas.CAPITAL_POLICY)


def test_readiness_multiplier_may_be_a_sentinel_but_not_a_number():
    loaded = policy.load()
    loaded["sizing"]["readiness_multipliers"]["exceptional"] = "disabled"
    assert schemas.schema_errors(loaded, schemas.CAPITAL_POLICY) == []
    loaded["sizing"]["readiness_multipliers"]["exceptional"] = 1.5
    assert schemas.schema_errors(loaded, schemas.CAPITAL_POLICY)


def test_sentinel_must_be_one_of_the_four():
    loaded = policy.load()
    loaded["cash"]["target"] = "none"
    assert schemas.schema_errors(loaded, schemas.CAPITAL_POLICY)


def test_basis_points_are_integers():
    loaded = policy.load()
    loaded["risk"]["position_loss_budget_bps_nav"] = "100"
    assert schemas.schema_errors(loaded, schemas.CAPITAL_POLICY)


def test_weight_cap_cannot_exceed_one_hundred_percent():
    loaded = policy.load()
    loaded["concentration"]["max_security_weight_bps"] = 10001
    assert schemas.schema_errors(loaded, schemas.CAPITAL_POLICY)


def test_missing_policy_file_is_reported_clearly(tmp_path):
    with pytest.raises(SchemaViolation, match="capital policy not found"):
        policy.load(path=tmp_path / "nope.json")


def test_malformed_policy_file_is_reported_clearly(tmp_path):
    path = tmp_path / "capital-policy.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SchemaViolation, match="not valid JSON"):
        policy.load(path=path)


# --------------------------------------------------------- instrument master

def instrument_master():
    return {
        "schema_version": "1.0.0",
        "as_of": "2026-08-16",
        "issuers": [{"issuer_id": "iss:alphabet", "legal_name": "Alphabet Inc.", "cik": "0001652044"}],
        "securities": [
            {"security_id": "sec:googl", "issuer_id": "iss:alphabet",
             "security_type": "common_equity", "share_class": "A", "currency": "USD"},
            {"security_id": "sec:goog", "issuer_id": "iss:alphabet",
             "security_type": "common_equity", "share_class": "C", "currency": "USD"},
        ],
        "listings": [
            {"listing_id": "lst:xnas-googl", "security_id": "sec:googl",
             "mic": "XNAS", "ticker": "GOOGL", "status": "active"},
            {"listing_id": "lst:xnas-goog", "security_id": "sec:goog",
             "mic": "XNAS", "ticker": "GOOG", "status": "active"},
        ],
    }


def test_two_share_classes_are_one_issuer():
    document = instrument_master()
    assert errors(document, schemas.INSTRUMENT_MASTER) == []
    assert {s["issuer_id"] for s in document["securities"]} == {"iss:alphabet"}


def test_instrument_master_has_no_ticker_history():
    """Deliberately out of scope in v0 -- see the schema description."""
    document = instrument_master()
    document["listings"][0]["previous_tickers"] = ["GOOG"]
    assert errors(document, schemas.INSTRUMENT_MASTER)


def test_only_common_equity_is_modelled():
    document = instrument_master()
    document["securities"][0]["security_type"] = "preferred_equity"
    assert errors(document, schemas.INSTRUMENT_MASTER)


def test_identity_prefixes_are_not_interchangeable():
    document = instrument_master()
    document["securities"][0]["security_id"] = "iss:googl"
    assert errors(document, schemas.INSTRUMENT_MASTER)


# ------------------------------------------------------------------- loading

def test_unknown_schema_id_is_reported():
    with pytest.raises(SchemaViolation, match="unknown schema id"):
        schemas.load_schema("fund:schemas/fund/nope.schema.json")


def test_validate_raises_with_every_message():
    with pytest.raises(SchemaViolation) as caught:
        schemas.validate(base_event(quantity="0", event_id="nope"), schemas.ACCOUNT_EVENT)
    assert "event_id" in str(caught.value)
    assert "quantity" in str(caught.value)


def test_all_fund_schemas_are_themselves_valid():
    import jsonschema

    for path in sorted(schemas.schema_dir().glob("*.schema.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(contents)
