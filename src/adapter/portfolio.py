from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import SecDataError
from .paths import ensure_inside, validate_ticker


class PortfolioError(SecDataError):
    """Portfolio operations error."""


def portfolio_file_path(repo_root: Path) -> Path:
    target = repo_root / "data" / "portfolio" / "portfolio.json"
    return ensure_inside(repo_root, target)


def write_json_atomic(target: Path, data: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(target)


def load_portfolio(repo_root: Path) -> dict[str, Any]:
    path = portfolio_file_path(repo_root)
    if not path.is_file():
        return {
            "schema_version": 1,
            "updated_at": None,
            "positions": [],
        }
    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content) if content.strip() else {}
        if "positions" not in data or not isinstance(data["positions"], list):
            data["positions"] = []
        return data
    except (json.JSONDecodeError, OSError) as exc:
        raise PortfolioError(f"Failed to load portfolio file: {exc}") from exc


def get_latest_price_map(repo_root: Path) -> dict[str, float]:
    """Helper to pull latest known price per ticker from live data / PEI pack."""
    prices: dict[str, float] = {}
    try:
        # Search for recent pack.json files in pei/
        pei_dir = repo_root / "pei"
        if pei_dir.is_dir():
            for date_dir in sorted(pei_dir.iterdir(), reverse=True):
                pack_file = date_dir / "pack.json"
                if pack_file.is_file():
                    try:
                        content = pack_file.read_text(encoding="utf-8")
                        pack_data = json.loads(content)
                        records = pack_data.get("universe_records") or pack_data.get("records") or []
                        for r in records:
                            ticker = r.get("ticker")
                            price = r.get("closing_price_usd") or r.get("market_data", {}).get("closing_price_usd")
                            if ticker and price is not None and ticker not in prices:
                                try:
                                    prices[ticker.upper()] = float(price)
                                except (ValueError, TypeError):
                                    pass
                    except Exception:
                        pass
                if len(prices) > 0:
                    break
    except Exception:
        pass

    return prices


def enrich_portfolio(repo_root: Path, portfolio: dict[str, Any]) -> dict[str, Any]:
    prices = get_latest_price_map(repo_root)
    positions = portfolio.get("positions", [])
    enriched_positions = []

    total_value = 0.0
    total_cost = 0.0

    for pos in positions:
        ticker = pos.get("ticker", "").upper()
        shares = float(pos.get("shares", 0))
        avg_cost = float(pos.get("avg_cost", 0))

        # Use current price if available, fallback to avg_cost or stored price
        current_price = prices.get(ticker, float(pos.get("current_price") or avg_cost))
        cost_basis = shares * avg_cost
        market_value = shares * current_price
        unrealized_pnl = market_value - cost_basis
        unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100.0) if cost_basis > 0 else 0.0

        enriched = {
            **pos,
            "ticker": ticker,
            "shares": shares,
            "avg_cost": avg_cost,
            "current_price": round(current_price, 2),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
        }
        enriched_positions.append(enriched)
        total_value += market_value
        total_cost += cost_basis

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100.0) if total_cost > 0 else 0.0

    return {
        "schema_version": portfolio.get("schema_version", 1),
        "updated_at": portfolio.get("updated_at"),
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "positions": enriched_positions,
    }


def upsert_position(repo_root: Path, position_data: dict[str, Any]) -> dict[str, Any]:
    raw_ticker = str(position_data.get("ticker", "")).strip().upper()
    try:
        ticker = validate_ticker(raw_ticker)
    except SecDataError as exc:
        raise PortfolioError(str(exc)) from exc

    try:
        shares = float(position_data.get("shares", 0))
        avg_cost = float(position_data.get("avg_cost", 0))
    except (ValueError, TypeError) as exc:
        raise PortfolioError("shares and avg_cost must be numbers") from exc

    if shares <= 0:
        raise PortfolioError("shares must be greater than zero")
    if avg_cost < 0:
        raise PortfolioError("avg_cost cannot be negative")

    portfolio = load_portfolio(repo_root)
    positions = portfolio.get("positions", [])

    now_iso = datetime.now(timezone.utc).isoformat()
    new_entry = {
        "ticker": ticker,
        "shares": shares,
        "avg_cost": avg_cost,
        "target_price": float(position_data.get("target_price")) if position_data.get("target_price") is not None else None,
        "stop_loss": float(position_data.get("stop_loss")) if position_data.get("stop_loss") is not None else None,
        "position_type": position_data.get("position_type", "Long"),
        "conviction": position_data.get("conviction", "Medium"),
        "notes": str(position_data.get("notes", "")).strip(),
        "updated_at": now_iso,
    }

    # Replace existing or append
    idx = next((i for i, p in enumerate(positions) if p.get("ticker", "").upper() == ticker), None)
    if idx is not None:
        positions[idx] = new_entry
    else:
        positions.append(new_entry)

    portfolio["positions"] = positions
    portfolio["updated_at"] = now_iso
    write_json_atomic(portfolio_file_path(repo_root), portfolio)
    return enrich_portfolio(repo_root, portfolio)


def delete_position(repo_root: Path, ticker_raw: str) -> dict[str, Any]:
    try:
        ticker = validate_ticker(str(ticker_raw).strip().upper())
    except SecDataError as exc:
        raise PortfolioError(str(exc)) from exc
    portfolio = load_portfolio(repo_root)
    positions = portfolio.get("positions", [])

    filtered = [p for p in positions if p.get("ticker", "").upper() != ticker]
    if len(filtered) == len(positions):
        raise PortfolioError(f"Position not found: {ticker}")

    now_iso = datetime.now(timezone.utc).isoformat()
    portfolio["positions"] = filtered
    portfolio["updated_at"] = now_iso
    write_json_atomic(portfolio_file_path(repo_root), portfolio)
    return enrich_portfolio(repo_root, portfolio)
