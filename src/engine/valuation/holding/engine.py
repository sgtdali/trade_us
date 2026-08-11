"""Deterministic calculations for the separate holding NAV/SOTP model."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _canonical(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _evidence_refs(amount: dict[str, Any]) -> list[str]:
    evidence = amount.get("evidence")
    return [evidence["source_id"]] if isinstance(evidence, dict) and evidence.get("source_id") else []


def _available_amount(amount: dict[str, Any]) -> bool:
    return amount.get("status") == "available" and amount.get("value") is not None


def _within_twelve_months(value_date: str, as_of_date: str) -> bool:
    value = dt.date.fromisoformat(value_date)
    as_of = dt.date.fromisoformat(as_of_date)
    try:
        anniversary = value.replace(year=value.year + 1)
    except ValueError:
        anniversary = value.replace(year=value.year + 1, day=28)
    return as_of <= anniversary


def _select_record(records: list[dict[str, Any]], concept: str, as_of_date: str) -> dict[str, Any] | None:
    as_of = dt.date.fromisoformat(as_of_date)
    candidates = [
        record
        for record in records
        if record.get("concept") == concept
        and dt.datetime.fromisoformat(record["effective_at"].replace("Z", "+00:00")).date() <= as_of
    ]
    return max(candidates, key=lambda record: record["effective_at"], default=None)


def _latest_treasury_from_actions(
    actions: list[dict[str, Any]], as_of_date: str
) -> dict[str, Any] | None:
    candidates = [
        action
        for action in actions
        if action.get("post_treasury_quote_units") is not None
        and action.get("effective_date")
        and action["effective_date"] <= as_of_date
    ]
    action = max(candidates, key=lambda item: item["effective_date"], default=None)
    if action is None:
        return None
    return {
        "value": action["post_treasury_quote_units"],
        "effective_at": f"{action['effective_date']}T23:59:59Z",
        "source_refs": action.get("source_refs", []),
    }


def build_holding_inputs(
    asset_ledger: dict[str, Any],
    *,
    as_of_date: str,
    cutoff_instant: str,
    listed_prices: dict[str, dict[str, Any]],
    listed_share_bases: dict[str, dict[str, Any]] | None = None,
    share_ledger: dict[str, Any],
    holding_price: dict[str, Any] | None,
    asset_ledger_ref: str,
) -> dict[str, Any]:
    """Resolve a source-backed holding asset ledger into point-in-time inputs."""
    listed_share_bases = listed_share_bases or {}
    seen: set[str] = set()
    parents: dict[str, str | None] = {}
    blockers: set[str] = set()
    resolved: list[dict[str, Any]] = []

    for asset in asset_ledger["assets"]:
        asset_id = asset["economic_asset_id"]
        if asset_id in seen:
            raise ValueError(f"duplicate economic_asset_id: {asset_id}")
        seen.add(asset_id)
        parents[asset_id] = asset.get("included_in_asset_id")

    for asset_id, parent_id in parents.items():
        visited = {asset_id}
        cursor = parent_id
        while cursor is not None:
            if cursor not in parents:
                blockers.add("holding_asset_parent_missing")
                break
            if cursor in visited:
                blockers.add("holding_asset_inclusion_cycle")
                break
            visited.add(cursor)
            cursor = parents[cursor]

    for asset in sorted(asset_ledger["assets"], key=lambda item: item["economic_asset_id"]):
        asset_id = asset["economic_asset_id"]
        ownership = asset.get("ownership_pct")
        source_refs = [asset["evidence"]["source_id"]]
        proxy = asset["materiality_proxy"]
        proxy_value = _decimal(proxy["value"]) if _available_amount(proxy) else None
        row: dict[str, Any] = {
            "economic_asset_id": asset_id,
            "name": asset["name"],
            "status": "unavailable",
            "valuation_basis": "unavailable",
            "ownership_pct": ownership,
            "gross_value": None,
            "attributable_value": None,
            "value_date": None,
            "materiality_proxy": _canonical(proxy_value) if proxy_value is not None else None,
            "included_in_asset_id": asset.get("included_in_asset_id"),
            "source_refs": source_refs,
            "reason_codes": [],
        }
        if row["included_in_asset_id"] is not None:
            row.update(status="excluded", valuation_basis="included_in_parent")
            row["reason_codes"] = ["holding_asset_included_in_parent"]
            resolved.append(row)
            continue
        if ownership is None:
            row["reason_codes"] = ["holding_ownership_missing"]
            resolved.append(row)
            continue

        gross: Decimal | None = None
        value_date: str | None = None
        basis = "unavailable"
        if asset["asset_type"] in {"listed_subsidiary", "listed_investment"}:
            ticker = asset.get("listed_ticker")
            share_basis_key = ticker or asset_id
            external_share_basis = listed_share_bases.get(share_basis_key, {})
            units = asset.get("total_quote_units") or external_share_basis.get("total_quote_units")
            observation_key = ticker or asset_id
            observation = listed_prices.get(observation_key)
            if units is None:
                row["reason_codes"] = (
                    external_share_basis.get("reason_codes")
                    or ["holding_listed_share_basis_missing"]
                )
            elif observation is None or observation.get("trade_date") != as_of_date:
                row["reason_codes"] = ["holding_listed_same_date_price_missing"]
            else:
                gross = _decimal(observation["price"]) * _decimal(units)
                value_date = observation["trade_date"]
                basis = "listed_market_value"
                source_refs.extend(observation.get("source_refs", []))
                source_refs.extend(external_share_basis.get("source_refs", []))
        else:
            disclosed = asset["disclosed_value"]
            book = asset["book_value"]
            if _available_amount(disclosed) and _within_twelve_months(disclosed["value_date"], as_of_date):
                gross = _decimal(disclosed["value"])
                value_date = disclosed["value_date"]
                basis = "disclosed_value"
                source_refs.extend(_evidence_refs(disclosed))
            elif _available_amount(book):
                gross = _decimal(book["value"])
                value_date = book["value_date"]
                basis = "book_value"
                source_refs.extend(_evidence_refs(book))
            else:
                row["reason_codes"] = ["holding_asset_value_missing"]

        if gross is not None:
            attributable = (
                gross * _decimal(ownership)
                if basis == "listed_market_value"
                else gross
            )
            row.update(
                status="available",
                valuation_basis=basis,
                gross_value=_canonical(gross),
                attributable_value=_canonical(attributable),
                value_date=value_date,
                source_refs=sorted(set(source_refs)),
            )
        resolved.append(row)

    identified = sum(
        (_decimal(row["materiality_proxy"]) for row in resolved if row["materiality_proxy"] is not None and row["status"] != "excluded"),
        Decimal("0"),
    )
    unresolved = sum(
        (_decimal(row["materiality_proxy"]) for row in resolved if row["materiality_proxy"] is not None and row["status"] == "unavailable"),
        Decimal("0"),
    )
    materiality_unknown = any(
        row["status"] == "unavailable" and row["materiality_proxy"] is None
        for row in resolved
    )
    if materiality_unknown:
        blockers.add("holding_unresolved_materiality_unknown")
    unresolved_ratio = (unresolved / identified) if identified > 0 else Decimal("1")
    threshold = _decimal(asset_ledger["materiality_threshold"])
    if unresolved_ratio > threshold:
        blockers.add("holding_unresolved_materiality_above_threshold")

    records = share_ledger.get("records", [])
    issued = _select_record(records, "issued_shares", as_of_date)
    treasury = _select_record(records, "treasury_shares", as_of_date)
    if treasury is None:
        treasury = _latest_treasury_from_actions(share_ledger.get("corporate_actions", []), as_of_date)
    share_refs = sorted(set((issued or {}).get("source_refs", []) + (treasury or {}).get("source_refs", [])))
    if issued is not None and treasury is not None:
        outstanding = _decimal(issued["value"]) - _decimal(treasury["value"])
        share_basis = {
            "status": "available",
            "issued_shares": _canonical(_decimal(issued["value"])),
            "treasury_shares": _canonical(_decimal(treasury["value"])),
            "outstanding_shares": _canonical(outstanding),
            "source_refs": share_refs,
            "reason_codes": [],
        }
    else:
        reasons = []
        if issued is None:
            reasons.append("holding_issued_shares_missing")
        if treasury is None:
            reasons.append("holding_treasury_shares_missing")
        share_basis = {
            "status": "unavailable",
            "issued_shares": _canonical(_decimal(issued["value"])) if issued else None,
            "treasury_shares": _canonical(_decimal(treasury["value"])) if treasury else None,
            "outstanding_shares": None,
            "source_refs": share_refs,
            "reason_codes": reasons,
        }

    if holding_price and holding_price.get("trade_date") == as_of_date:
        market_cap = None
        reasons = []
        if share_basis["status"] == "available":
            market_cap = _decimal(holding_price["price"]) * _decimal(share_basis["outstanding_shares"])
        else:
            reasons = ["holding_market_cap_share_basis_unavailable"]
        holding_market = {
            "status": "available",
            "price": _canonical(_decimal(holding_price["price"])),
            "trade_date": as_of_date,
            "market_cap": _canonical(market_cap) if market_cap is not None else None,
            "source_refs": sorted(set(holding_price.get("source_refs", []))),
            "reason_codes": reasons,
        }
    else:
        holding_market = {
            "status": "unavailable",
            "price": None,
            "trade_date": None,
            "market_cap": None,
            "source_refs": [],
            "reason_codes": ["holding_same_date_price_missing"],
        }

    coverage_status = "insufficient" if blockers else "sufficient"
    return {
        "schema_version": "1.0.0",
        "artifact_type": "holding_valuation_inputs",
        "owner_type": "generated",
        "ticker": asset_ledger["ticker"],
        "as_of_date": as_of_date,
        "cutoff_instant": cutoff_instant,
        "reporting_currency": asset_ledger["reporting_currency"],
        "asset_ledger_ref": asset_ledger_ref,
        "resolved_assets": resolved,
        "parent_only_financial_position": asset_ledger["parent_only_financial_position"],
        "consolidated_financial_position": asset_ledger["consolidated_financial_position"],
        "share_basis": share_basis,
        "holding_market": holding_market,
        "materiality_threshold": asset_ledger["materiality_threshold"],
        "coverage": {
            "identified_proxy_value": _canonical(identified),
            "unresolved_proxy_value": _canonical(unresolved),
            "unresolved_ratio": None if materiality_unknown else float(unresolved_ratio),
            "status": coverage_status,
            "blocker_codes": sorted(blockers),
        },
        "lineage": {
            "source_ids": sorted(set(asset_ledger["lineage"]["source_ids"] + share_refs + holding_market["source_refs"])),
            "generated_at": cutoff_instant,
            "generator": "engine.valuation.holding.engine:build_holding_inputs",
        },
    }


def build_holding_results(inputs: dict[str, Any], *, input_ref: str) -> dict[str, Any]:
    """Calculate total NAV, per-share NAV and current discount/premium."""
    blockers = set(inputs["coverage"]["blocker_codes"])
    assets = [
        row for row in inputs["resolved_assets"]
        if row["status"] == "available" and row["included_in_asset_id"] is None
    ]
    asset_total = sum((_decimal(row["attributable_value"]) for row in assets), Decimal("0"))
    parent = inputs["parent_only_financial_position"]
    cash = parent["cash"]
    debt = parent["financial_debt"]
    net_cash = parent.get("net_cash")
    adjustments = parent["other_adjustments"]
    direct_net_cash_available = isinstance(net_cash, dict) and _available_amount(net_cash)
    separate_cash_debt_available = _available_amount(cash) and _available_amount(debt)
    if not direct_net_cash_available and not separate_cash_debt_available:
        if not _available_amount(cash):
            blockers.add("holding_parent_only_cash_missing")
        if not _available_amount(debt):
            blockers.add("holding_parent_only_debt_missing")
        blockers.add("holding_parent_only_net_cash_missing")
    unavailable_adjustments = [item for item in adjustments if not _available_amount(item["amount"])]
    if unavailable_adjustments:
        blockers.add("holding_parent_only_adjustment_missing")
    adjustment_total = sum(
        (_decimal(item["amount"]["value"]) for item in adjustments if _available_amount(item["amount"])),
        Decimal("0"),
    )
    nav_available = not blockers
    parent_net_cash = (
        _decimal(net_cash["value"])
        if direct_net_cash_available
        else _decimal(cash["value"]) - _decimal(debt["value"])
        if separate_cash_debt_available
        else None
    )
    nav = (
        asset_total + parent_net_cash + adjustment_total
        if nav_available else None
    )
    nav_bridge = {
        "status": "available" if nav_available else "unavailable",
        "attributable_asset_value": _canonical(asset_total),
        "parent_cash": _canonical(_decimal(cash["value"])) if _available_amount(cash) else None,
        "parent_financial_debt": _canonical(_decimal(debt["value"])) if _available_amount(debt) else None,
        "parent_net_cash": _canonical(parent_net_cash) if parent_net_cash is not None else None,
        "other_adjustments": _canonical(adjustment_total),
        "total_nav": _canonical(nav) if nav is not None else None,
        "reason_codes": sorted(blockers),
    }

    share_basis = inputs["share_basis"]
    if nav is not None and share_basis["status"] == "available":
        per_share = nav / _decimal(share_basis["outstanding_shares"])
        per_share_result = {"status": "available", "value": _canonical(per_share), "unit": "TRY/share", "reason_codes": []}
    else:
        reasons = sorted(blockers | set(share_basis["reason_codes"]))
        per_share_result = {"status": "unavailable", "value": None, "unit": "TRY/share", "reason_codes": reasons}

    market_cap = inputs["holding_market"].get("market_cap")
    if nav is not None and nav > 0 and market_cap is not None:
        discount = Decimal("1") - (_decimal(market_cap) / nav)
        discount_result = {"status": "available", "value": _canonical(discount), "unit": "ratio", "reason_codes": []}
    else:
        reasons = set(per_share_result["reason_codes"]) | set(inputs["holding_market"]["reason_codes"])
        if nav is not None and nav <= 0:
            reasons.add("holding_nav_not_positive")
        discount_result = {"status": "unavailable", "value": None, "unit": "ratio", "reason_codes": sorted(reasons)}

    basis_mix = {
        key: _canonical(sum((_decimal(row["attributable_value"]) for row in assets if row["valuation_basis"] == key), Decimal("0")))
        for key in ("listed_market_value", "disclosed_value", "book_value")
    }
    return {
        "schema_version": "1.0.0",
        "artifact_type": "holding_valuation_results",
        "owner_type": "generated",
        "ticker": inputs["ticker"],
        "as_of_date": inputs["as_of_date"],
        "reporting_currency": inputs["reporting_currency"],
        "model_id": "holding_nav_sotp_v1",
        "input_ref": input_ref,
        "asset_rows": inputs["resolved_assets"],
        "nav_bridge": nav_bridge,
        "per_share_nav": per_share_result,
        "observed_discount_premium": discount_result,
        "valuation_basis_mix": basis_mix,
        "coverage": inputs["coverage"],
        "blocker_codes": sorted(blockers | set(per_share_result["reason_codes"]) | set(discount_result["reason_codes"])),
        "lineage": {
            "source_ids": inputs["lineage"]["source_ids"],
            "generated_at": inputs["cutoff_instant"],
            "generator": "engine.valuation.holding.engine:build_holding_results",
        },
    }
