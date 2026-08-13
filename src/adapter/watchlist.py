from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import SecDataError
from .paths import ensure_inside, validate_ticker
from .portfolio import get_latest_price_map, write_json_atomic


class WatchlistError(SecDataError):
    """Watchlist operations error."""


def watchlist_file_path(repo_root: Path) -> Path:
    target = repo_root / "data" / "watchlist" / "watchlist.json"
    return ensure_inside(repo_root, target)


def load_watchlist(repo_root: Path) -> dict[str, Any]:
    path = watchlist_file_path(repo_root)
    if not path.is_file():
        return {
            "schema_version": 1,
            "updated_at": None,
            "items": [],
        }
    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content) if content.strip() else {}
        if "items" not in data or not isinstance(data["items"], list):
            data["items"] = []
        return data
    except (json.JSONDecodeError, OSError) as exc:
        raise WatchlistError(f"Failed to load watchlist file: {exc}") from exc


def enrich_watchlist(repo_root: Path, watchlist: dict[str, Any]) -> dict[str, Any]:
    prices = get_latest_price_map(repo_root)
    items = watchlist.get("items", [])
    enriched_items = []

    for item in items:
        ticker = item.get("ticker", "").upper()
        target_entry = float(item.get("target_entry")) if item.get("target_entry") is not None else None
        current_price = prices.get(ticker, float(item.get("current_price") or 0))

        distance_pct = None
        if target_entry and target_entry > 0 and current_price > 0:
            distance_pct = round(((current_price - target_entry) / target_entry) * 100.0, 2)

        enriched = {
            **item,
            "ticker": ticker,
            "current_price": round(current_price, 2) if current_price > 0 else None,
            "target_entry": round(target_entry, 2) if target_entry else None,
            "distance_to_target_pct": distance_pct,
        }
        enriched_items.append(enriched)

    return {
        "schema_version": watchlist.get("schema_version", 1),
        "updated_at": watchlist.get("updated_at"),
        "total_items": len(enriched_items),
        "items": enriched_items,
    }


def upsert_watchlist_item(repo_root: Path, item_data: dict[str, Any]) -> dict[str, Any]:
    raw_ticker = str(item_data.get("ticker", "")).strip().upper()
    try:
        ticker = validate_ticker(raw_ticker)
    except SecDataError as exc:
        raise WatchlistError(str(exc)) from exc

    target_entry = None
    if item_data.get("target_entry") is not None:
        try:
            target_entry = float(item_data["target_entry"])
        except (ValueError, TypeError) as exc:
            raise WatchlistError("target_entry must be a number") from exc

    watchlist = load_watchlist(repo_root)
    items = watchlist.get("items", [])

    now_iso = datetime.now(timezone.utc).isoformat()
    new_entry = {
        "ticker": ticker,
        "target_entry": target_entry,
        "priority": item_data.get("priority", "B"),
        "catalyst": str(item_data.get("catalyst", "")).strip(),
        "watch_reason": str(item_data.get("watch_reason", "")).strip(),
        "alert_condition": str(item_data.get("alert_condition", "")).strip(),
        "added_at": item_data.get("added_at") or now_iso,
        "updated_at": now_iso,
    }

    idx = next((i for i, item in enumerate(items) if item.get("ticker", "").upper() == ticker), None)
    if idx is not None:
        items[idx] = new_entry
    else:
        items.append(new_entry)

    watchlist["items"] = items
    watchlist["updated_at"] = now_iso
    write_json_atomic(watchlist_file_path(repo_root), watchlist)
    return enrich_watchlist(repo_root, watchlist)


def delete_watchlist_item(repo_root: Path, ticker_raw: str) -> dict[str, Any]:
    try:
        ticker = validate_ticker(str(ticker_raw).strip().upper())
    except SecDataError as exc:
        raise WatchlistError(str(exc)) from exc
    watchlist = load_watchlist(repo_root)
    items = watchlist.get("items", [])

    filtered = [item for item in items if item.get("ticker", "").upper() != ticker]
    if len(filtered) == len(items):
        raise WatchlistError(f"Watchlist item not found: {ticker}")

    now_iso = datetime.now(timezone.utc).isoformat()
    watchlist["items"] = filtered
    watchlist["updated_at"] = now_iso
    write_json_atomic(watchlist_file_path(repo_root), watchlist)
    return enrich_watchlist(repo_root, watchlist)
