"""Binding a monitoring rule to a real metric.

A rule says "gross margin, trailing twelve months, below 55%". Three things
have to be true for that to mean anything: the metric has to exist, the unit
has to be what the rule assumes, and the test has to make sense for the period
basis. None of them is guaranteed by the rule being well-formed JSON.

Binding is checked **twice**, and the second time is the one that matters.
At activation, a rule that does not bind is refused outright. At evaluation,
the binding is checked again against the catalog as it stands that day -- and
if it no longer holds, the result is ``unavailable``. Never ``not_breached``.
A metric that was renamed or restated has not told us the thesis is fine; it
has told us we are no longer measuring what we thought we were measuring.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from . import schemas
from .errors import FundError

CATALOG_RELATIVE_PATH = Path("config") / "pipeline" / "metric-catalog.json"

#: Period bases that describe a level, and those that describe a movement.
#: Testing an absolute threshold against a year-over-year change compares a
#: level to a delta, which is meaningless in a way that looks fine.
LEVEL_BASES = frozenset({"ttm", "latest_fy"})
CHANGE_BASES = frozenset({"latest_quarter_yoy", "latest_quarter_qoq", "change_from_baseline"})

PERCENT_UNITS = frozenset({"percent", "ratio"})


class MetricBindingError(FundError):
    """A rule does not bind to the metric catalog."""


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return {metric["metric_id"]: metric for metric in document["metrics"]}


def load_catalog(root: Path | None = None) -> dict[str, dict[str, Any]]:
    return _load(str((root or schemas.repo_root()) / CATALOG_RELATIVE_PATH))


def describe(metric_id: str, catalog: Mapping[str, Any]) -> str:
    metric = catalog.get(metric_id)
    if metric is None:
        return f"{metric_id} (not in the catalog)"
    units = "/".join(metric.get("allowed_units", []))
    return f"{metric_id} [{units}]"


def check_binding(rule: Mapping[str, Any], catalog: Mapping[str, Any]) -> None:
    """Raise unless this rule can be evaluated against this catalog."""
    metric_id = rule["metric_id"]
    metric = catalog.get(metric_id)
    if metric is None:
        raise MetricBindingError(
            f"rule {rule['rule_id']!r}: no metric {metric_id!r} in the catalog. "
            "A condition with no reliable metric behind it stays qualitative -- "
            "do not force it mechanical."
        )

    units = set(metric.get("allowed_units", []))
    period_basis = rule["period_basis"]
    test_type = rule["test_type"]

    if test_type == "absolute_value" and period_basis not in LEVEL_BASES:
        raise MetricBindingError(
            f"rule {rule['rule_id']!r}: absolute_value needs a level period basis "
            f"({', '.join(sorted(LEVEL_BASES))}), not {period_basis!r} -- "
            "comparing a threshold to a change measures nothing."
        )
    if test_type in {"percentage_change", "basis_point_change"} and period_basis not in CHANGE_BASES:
        raise MetricBindingError(
            f"rule {rule['rule_id']!r}: {test_type} needs a change period basis "
            f"({', '.join(sorted(CHANGE_BASES))}), not {period_basis!r}."
        )
    if test_type == "basis_point_change" and not (units & PERCENT_UNITS):
        raise MetricBindingError(
            f"rule {rule['rule_id']!r}: basis points only apply to a rate. "
            f"{describe(metric_id, catalog)} is not one."
        )
    if test_type == "percentage_change" and units and units <= PERCENT_UNITS:
        raise MetricBindingError(
            f"rule {rule['rule_id']!r}: {describe(metric_id, catalog)} is already a rate; "
            "a percentage change of a percentage is ambiguous. Use basis_point_change."
        )


def check_contract(contract: Mapping[str, Any], catalog: Mapping[str, Any]) -> list[str]:
    """Every binding problem in a contract, so they can be fixed in one pass."""
    problems: list[str] = []
    for rule in contract.get("mechanical_rules", []):
        try:
            check_binding(rule, catalog)
        except MetricBindingError as exc:
            problems.append(str(exc))
    return problems


def binding_signature(rule: Mapping[str, Any], catalog: Mapping[str, Any]) -> str:
    """A fingerprint of what the rule assumed about the metric.

    Recorded with each check so a later catalog change is detectable rather
    than silently absorbed.
    """
    metric = catalog.get(rule["metric_id"], {})
    units = ",".join(sorted(metric.get("allowed_units", [])))
    return f"{rule['metric_id']}|{units}|{metric.get('data_type', '?')}|{rule['period_basis']}"
