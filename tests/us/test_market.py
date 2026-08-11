import json
from datetime import date
from types import SimpleNamespace

import pytest

from engine.valuation.catalogs import load_catalog_registry
from adapter.errors import FactSelectionError
from adapter.market import (
    direct_share_count_as_int,
    generate_us_market_snapshot,
    select_direct_outstanding_shares,
    valuation_context_projection,
)
from adapter.models import SecFact
from adapter.xbrl import _canonical_unit


def _share_fact(value="4302549243", end_date=date(2026, 7, 27), context_id="c-21"):
    return SecFact(
        namespace="http://xbrl.sec.gov/dei/2026", concept="EntityCommonStockSharesOutstanding",
        value=value, unit="shares", context_id=context_id, start_date=None, end_date=end_date,
        dimensions=(), decimals="0", is_nil=False,
    )


def test_arelle_unit_ref_is_canonicalized_from_its_xbrl_measure():
    fact = SimpleNamespace(
        unitID="Unit_Standard_shares_HVWdo_HrZUua8EH47E9p5Q",
        unit=SimpleNamespace(measures=((SimpleNamespace(localName="shares"),), ())),
    )

    assert _canonical_unit(fact) == "shares"


def test_select_direct_outstanding_shares_uses_latest_fact():
    selected = select_direct_outstanding_shares(
        (_share_fact("4200000000", date(2026, 2, 19), "old"), _share_fact()),
        as_of=date(2026, 8, 3),
    )
    assert selected.value == "4302549243"


def test_select_direct_outstanding_shares_rejects_same_date_conflict():
    with pytest.raises(FactSelectionError):
        select_direct_outstanding_shares(
            (_share_fact(), _share_fact("4302549244", context_id="c-22")),
            as_of=date(2026, 8, 3),
        )


def test_direct_share_count_accepts_integral_decimal_lexical_form():
    assert direct_share_count_as_int(_share_fact("416000000.0")) == 416000000


def test_generate_us_market_snapshot_supports_sec_direct_share_basis(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "adapter.market._fetch_latest_close",
        lambda ticker, as_of: SimpleNamespace(
            trade_date="2026-07-31", close=SimpleNamespace(status="available", value="87.59")
        ),
    )
    monkeypatch.setattr("adapter.market._utc_now", lambda: "2026-08-03T12:00:00Z")
    snapshot_path = generate_us_market_snapshot(
        workspace=tmp_path, ticker="KO", exchange="NYSE", as_of_date="2026-08-03",
        cutoff_instant="2026-08-03T23:59:59Z", accession="0001628280-26-050503",
        facts=(_share_fact(),), catalog_registry=load_catalog_registry(),
        context_projection=valuation_context_projection(
            "KO", "2026-08-03", "2026-08-03T23:59:59Z", ("2026-Q2", "2025-FY")
        ),
    )
    import json

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["share_basis"]["derivation_method"] == "direct_reported"
    assert snapshot["share_basis"]["spot_basic_shares_outstanding"] == "4302549243"
    assert snapshot["price_observation"]["price"] == "87.59"

    monkeypatch.setattr(
        "adapter.market._fetch_latest_close",
        lambda *_args: pytest.fail("a pinned historical market input must be reused without refetching"),
    )
    rerun_path = generate_us_market_snapshot(
        workspace=tmp_path, ticker="KO", exchange="NYSE", as_of_date="2026-08-03",
        cutoff_instant="2026-08-03T23:59:59Z", accession="0001628280-26-050503",
        facts=(_share_fact(),), catalog_registry=load_catalog_registry(),
        context_projection=valuation_context_projection(
            "KO", "2026-08-03", "2026-08-03T23:59:59Z", ("2026-Q2", "2025-FY")
        ),
    )
    assert rerun_path.read_bytes() == snapshot_path.read_bytes()


def test_historical_market_observation_is_cutoff_bound(tmp_path):
    observation = {
        "ticker": "KO", "trade_date": "2024-12-31", "close": "62.26",
        "available_at": "2024-12-31T20:00:00Z",
        "ledger_frozen_at": "2026-08-04T00:00:00Z",
        "ledger_sha256": "a" * 64,
        "source_record_ref": "backtest-ledger:yfinance:KO:2024-12-31:raw-close",
    }
    snapshot_path = generate_us_market_snapshot(
        workspace=tmp_path, ticker="KO", exchange="NYSE", as_of_date="2024-12-31",
        cutoff_instant="2024-12-31T23:59:59Z", accession="0001628280-24-000001",
        facts=(_share_fact(end_date=date(2024, 12, 30)),),
        catalog_registry=load_catalog_registry(),
        context_projection=valuation_context_projection(
            "KO", "2024-12-31", "2024-12-31T23:59:59Z", ("2024-Q3", "2023-FY")
        ),
        historical_observation=observation,
        filing_available_at="2024-10-31T23:59:59Z",
    )
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["price_observation"]["price"] == "62.26"

    revised = {**observation, "close": "63.00"}
    generate_us_market_snapshot(
        workspace=tmp_path, ticker="KO", exchange="NYSE", as_of_date="2024-12-31",
        cutoff_instant="2024-12-31T23:59:59Z", accession="0001628280-24-000001",
        facts=(_share_fact(end_date=date(2024, 12, 30)),),
        catalog_registry=load_catalog_registry(),
        context_projection=valuation_context_projection(
            "KO", "2024-12-31", "2024-12-31T23:59:59Z", ("2024-Q3", "2023-FY")
        ),
        historical_observation=revised,
        filing_available_at="2024-10-31T23:59:59Z",
    )
    observations = json.loads(
        (tmp_path / "data/market-inputs/KO/2024-12-31/observations.json").read_text(encoding="utf-8")
    )["observations"]
    assert next(item for item in observations if item["observation_type"] == "price")["value"] == "63.00"

    future = {**observation, "available_at": "2025-01-02T20:00:00Z"}
    with pytest.raises(Exception, match="not available"):
        generate_us_market_snapshot(
            workspace=tmp_path / "future", ticker="KO", exchange="NYSE", as_of_date="2024-12-31",
            cutoff_instant="2024-12-31T23:59:59Z", accession="0001628280-24-000001",
            facts=(_share_fact(end_date=date(2024, 12, 30)),),
            catalog_registry=load_catalog_registry(),
            context_projection=valuation_context_projection(
                "KO", "2024-12-31", "2024-12-31T23:59:59Z", ("2024-Q3", "2023-FY")
            ),
            historical_observation=future,
            filing_available_at="2024-10-31T23:59:59Z",
        )
