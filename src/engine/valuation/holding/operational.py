"""Reported holding EBITDA diagnostics, separate from NAV arithmetic."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any


_UNIT_MULTIPLIERS = {
    "try": Decimal(1),
    "thousand_try": Decimal(1_000),
    "million_try": Decimal(1_000_000),
    "billion_try": Decimal(1_000_000_000),
}


def _metric(document: dict[str, Any] | None, metric_id: str) -> dict[str, Any] | None:
    if not document:
        return None
    return next(
        (item for item in document.get("metrics", []) if item.get("metric_id") == metric_id),
        None,
    )


def _available_value(metric: dict[str, Any] | None) -> Decimal | None:
    if not metric or metric.get("value") is None:
        return None
    multiplier = _UNIT_MULTIPLIERS.get(metric.get("unit"))
    return Decimal(str(metric["value"])) * multiplier if multiplier is not None else None


def _source_refs(document: dict[str, Any] | None, metric: dict[str, Any] | None) -> list[str]:
    if not document or not metric:
        return []
    source_id = (metric.get("provenance") or {}).get("source_id") or document.get("default_source_id")
    return [source_id] if source_id else []


def _read(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def build_holding_operational_summary(
    repo_root: Path,
    ticker: str,
    current_period: str,
) -> dict[str, Any]:
    directory = repo_root / "data" / "financial-operational" / ticker
    current_doc = _read(directory / f"{current_period}.json")
    current_metric = _metric(current_doc, "ebitda_amount")
    current_value = _available_value(current_metric)
    current = {
        "status": "available" if current_value is not None else "unavailable",
        "value": format(current_value, "f") if current_value is not None else None,
        "period": current_period,
        "source_refs": _source_refs(current_doc, current_metric),
        "reason_codes": [] if current_value is not None else ["holding_current_ebitda_unavailable"],
    }

    ltm_metric = _metric(current_doc, "ebitda_ltm_amount")
    ltm_value = _available_value(ltm_metric)
    if ltm_value is not None:
        return {
            "current_ebitda": current,
            "ttm_ebitda": {
                "status": "available",
                "value": format(ltm_value, "f"),
                "period": f"{current_period}-LTM",
                "derivation": "company_reported_ltm",
                "source_refs": _source_refs(current_doc, ltm_metric),
                "reason_codes": [],
            },
        }

    if not current_period.endswith("-FY") and current_metric and current_metric.get("comparison_value") is not None:
        year = int(current_period[:4])
        fy_period = f"{year - 1}-FY"
        fy_doc = _read(directory / f"{fy_period}.json")
        fy_metric = _metric(fy_doc, "ebitda_amount")
        fy_value = _available_value(fy_metric)
        current_context = current_metric.get("context") or {}
        fy_context = (fy_metric or {}).get("context") or {}
        same_definition = (
            current_context.get("ebitda_definition")
            and current_context.get("ebitda_definition") == fy_context.get("ebitda_definition")
        )
        same_power_date = (
            current_context.get("purchasing_power_date")
            and current_context.get("purchasing_power_date") == fy_context.get("purchasing_power_date")
        )
        multiplier = _UNIT_MULTIPLIERS.get(current_metric.get("unit"))
        if current_value is not None and fy_value is not None and multiplier and same_definition and same_power_date:
            comparable = Decimal(str(current_metric["comparison_value"])) * multiplier
            derived = fy_value + current_value - comparable
            return {
                "current_ebitda": current,
                "ttm_ebitda": {
                    "status": "available",
                    "value": format(derived, "f"),
                    "period": f"{current_period}-TTM",
                    "derivation": "fy_plus_current_ytd_minus_prior_ytd_same_basis",
                    "source_refs": sorted(
                        set(_source_refs(current_doc, current_metric) + _source_refs(fy_doc, fy_metric))
                    ),
                    "reason_codes": [],
                },
            }

    return {
        "current_ebitda": current,
        "ttm_ebitda": {
            "status": "unavailable",
            "value": None,
            "period": f"{current_period}-TTM",
            "derivation": None,
            "source_refs": [],
            "reason_codes": ["holding_ttm_ebitda_same_basis_unavailable"],
        },
    }
