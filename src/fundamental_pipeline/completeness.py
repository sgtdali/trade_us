"""Completeness reporting: how much of a company/period's required and
optional metric coverage is actually available, based on metric *status*
rather than just id presence.

A metric counts as available only when it is present, its status is
``available`` (or has no status field at all, which is the convention for
ordinary populated metrics), and it carries a non-null value. Metrics
explicitly marked ``not_applicable`` are excluded from the denominator
entirely (they were never expected for this company); ``unavailable``,
``not_disclosed``, and ``calculation_blocked`` count as present-but-missing.
"""

from __future__ import annotations

from .io import read_json
from .paths import repo_path

_MISSING_STATUSES = {"unavailable", "not_disclosed", "calculation_blocked", "not_comparable"}


def _index_metrics(*datasets: dict) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for data in datasets:
        if not data:
            continue
        for key, val in data.items():
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and item.get("metric_id"):
                        by_id[item["metric_id"]] = item
        if "metrics" in data:
            for item in data["metrics"]:
                if item.get("metric_id"):
                    by_id[item["metric_id"]] = item
    return by_id


def _metric_state(metric: dict | None) -> str:
    if metric is None:
        return "missing"
    status = metric.get("status")
    if status == "not_applicable":
        return "not_applicable"
    if status in _MISSING_STATUSES:
        return "missing"
    if metric.get("value") is None:
        return "missing"
    return "available"


def _block(metric_ids: list[str], by_id: dict[str, dict]) -> dict:
    applicable = 0
    available = 0
    missing_ids: list[str] = []
    for metric_id in metric_ids:
        state = _metric_state(by_id.get(metric_id))
        if state == "not_applicable":
            continue
        applicable += 1
        if state == "available":
            available += 1
        else:
            missing_ids.append(metric_id)
    completeness_pct = round((available / applicable * 100) if applicable else 100.0, 1)
    return {
        "applicable": applicable,
        "available": available,
        "missing": applicable - available,
        "missing_ids": missing_ids,
        "completeness_pct": completeness_pct,
    }


def _provenance_block(metric_ids: list[str], by_id: dict[str, dict]) -> dict:
    direct_ids = [mid for mid in metric_ids if by_id.get(mid, {}).get("data_type") == "direct"]
    with_provenance = [
        mid for mid in direct_ids
        if by_id[mid].get("provenance") and by_id[mid]["provenance"].get("source_file")
    ]
    applicable = len(direct_ids)
    available = len(with_provenance)
    return {
        "applicable": applicable,
        "available": available,
        "missing": applicable - available,
        "completeness_pct": round((available / applicable * 100) if applicable else 100.0, 1),
    }


def calculate(company_type: str, sector_module: str, *datasets: dict) -> dict:
    profiles = read_json(repo_path("config/pipeline/completeness-profiles.json"))["profiles"]
    profile = next(
        (p for p in profiles if p["company_type"] == company_type and p["sector_module"] == sector_module),
        {"required_metrics": [], "optional_metrics": []},
    )
    by_id = _index_metrics(*datasets)
    required_ids = profile["required_metrics"]
    optional_ids = profile["optional_metrics"]
    return {
        "company_type": company_type,
        "sector_module": sector_module,
        "required_metrics": _block(required_ids, by_id),
        "optional_metrics": _block(optional_ids, by_id),
        "provenance": _provenance_block(required_ids + optional_ids, by_id),
    }
