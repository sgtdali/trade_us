import pytest
from pathlib import Path
from adapter.portfolio import (
    load_portfolio,
    upsert_position,
    delete_position,
    enrich_portfolio,
    PortfolioError,
)
from adapter.watchlist import (
    load_watchlist,
    upsert_watchlist_item,
    delete_watchlist_item,
    enrich_watchlist,
    WatchlistError,
)

def test_portfolio_crud(tmp_path: Path):
    # Initial load
    p = load_portfolio(tmp_path)
    assert p["positions"] == []

    # Add AAPL
    updated = upsert_position(tmp_path, {
        "ticker": "AAPL",
        "shares": 10,
        "avg_cost": 150.0,
        "target_price": 200.0,
        "stop_loss": 130.0,
        "position_type": "Long",
        "conviction": "High",
        "notes": "Test AAPL position",
    })
    assert len(updated["positions"]) == 1
    assert updated["positions"][0]["ticker"] == "AAPL"
    assert updated["positions"][0]["shares"] == 10.0
    assert updated["total_cost"] == 1500.0

    # Add MSFT
    updated = upsert_position(tmp_path, {
        "ticker": "MSFT",
        "shares": 5,
        "avg_cost": 400.0,
    })
    assert len(updated["positions"]) == 2

    # Delete AAPL
    after_del = delete_position(tmp_path, "AAPL")
    assert len(after_del["positions"]) == 1
    assert after_del["positions"][0]["ticker"] == "MSFT"

    # Validation errors
    with pytest.raises(PortfolioError):
        upsert_position(tmp_path, {"ticker": "INVALID_123_$$$", "shares": 10, "avg_cost": 100})

    with pytest.raises(PortfolioError):
        upsert_position(tmp_path, {"ticker": "NVDA", "shares": -5, "avg_cost": 100})


def test_watchlist_crud(tmp_path: Path):
    w = load_watchlist(tmp_path)
    assert w["items"] == []

    updated = upsert_watchlist_item(tmp_path, {
        "ticker": "NVDA",
        "target_entry": 110.0,
        "priority": "A",
        "catalyst": "Q2 Earnings",
        "watch_reason": "Wait for dip",
    })
    assert len(updated["items"]) == 1
    assert updated["items"][0]["ticker"] == "NVDA"
    assert updated["items"][0]["priority"] == "A"

    # Delete
    after_del = delete_watchlist_item(tmp_path, "NVDA")
    assert len(after_del["items"]) == 0

    with pytest.raises(WatchlistError):
        delete_watchlist_item(tmp_path, "NVDA")
