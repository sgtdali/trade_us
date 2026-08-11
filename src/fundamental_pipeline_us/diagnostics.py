from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from fundamental_pipeline.io import read_json, write_json_atomic
from fundamental_pipeline.valuation.catalog_runtime import load_comparison_catalog_registry
from fundamental_pipeline.valuation.comparison.service import (
    generate_magic_formula_diagnostic,
    generate_piotroski_diagnostic,
)

from .errors import UsPipelineError


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCALE = {"unit": Decimal(1), "thousand": Decimal(1_000), "million": Decimal(1_000_000), "billion": Decimal(1_000_000_000)}


def generate_us_diagnostics(
    *, workspace: Path, ticker: str, as_of_date: str, generated_at: str,
    latest_fy: str, valuation_inputs_path: Path, company_type: str,
    annual_share_counts: tuple[int | None, int | None],
) -> None:
    current_year = int(latest_fy[:4])
    prior_fy = f"{current_year - 1}-FY"
    opening_fy = f"{current_year - 2}-FY"
    current = read_json(workspace / "data" / "financial" / ticker / f"{latest_fy}.json")
    prior = _maybe_read(workspace / "data" / "financial" / ticker / f"{prior_fy}.json")
    opening = _maybe_read(workspace / "data" / "financial" / ticker / f"{opening_fy}.json")
    valuation_inputs = read_json(valuation_inputs_path)

    facts_dir = workspace / "data" / "diagnostic-facts" / ticker / as_of_date
    piotroski = _piotroski_facts(
        ticker, latest_fy, prior_fy, opening_fy, current, prior, opening, annual_share_counts
    )
    magic = _magic_facts(current, valuation_inputs)
    piotroski_path = facts_dir / "piotroski-facts.json"
    magic_path = facts_dir / "magic-formula-facts.json"
    write_json_atomic(piotroski_path, piotroski)
    write_json_atomic(magic_path, magic)

    registry = load_comparison_catalog_registry(repo_root=_REPO_ROOT)
    piotroski_result = generate_piotroski_diagnostic(
        ticker=ticker,
        company_type=company_type,
        facts_path=piotroski_path,
        as_of_date=as_of_date,
        generated_at=generated_at,
        engine_version="1.0.0",
        comparison_registry=registry,
        output_dir=workspace,
    )
    _require_ok("Piotroski", piotroski_result)
    magic_result = generate_magic_formula_diagnostic(
        ticker=ticker,
        facts_path=magic_path,
        as_of_date=as_of_date,
        generated_at=generated_at,
        engine_version="1.0.0",
        comparison_registry=registry,
        output_dir=workspace,
    )
    _require_ok("Magic Formula", magic_result)


def _piotroski_facts(
    ticker: str, current_id: str, prior_id: str, opening_id: str,
    current: dict[str, Any], prior: dict[str, Any] | None, opening: dict[str, Any] | None,
    annual_share_counts: tuple[int | None, int | None],
) -> dict[str, Any]:
    current_values = _metric_values(current)
    prior_values = _metric_values(prior) if prior else {}
    opening_values = _metric_values(opening) if opening else {}
    assets_t = current_values.get("total_assets")
    assets_t1 = prior_values.get("total_assets")
    assets_t2 = opening_values.get("total_assets")
    net_income_t = current_values.get("net_profit_for_period")
    net_income_t1 = prior_values.get("net_profit_for_period")
    cfo_t = current_values.get("cf_net_operating_activities")
    latest_shares, prior_shares = annual_share_counts
    issuance = None
    if latest_shares is not None and prior_shares is not None:
        issuance = max(latest_shares - prior_shares, 0)

    def ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
        return numerator / denominator if numerator is not None and denominator not in (None, 0) else None

    def average(left: Decimal | None, right: Decimal | None) -> Decimal | None:
        return (left + right) / 2 if left is not None and right is not None else None

    facts = {
        "roa_t": _envelope(ratio(net_income_t, average(assets_t, assets_t1))),
        "roa_t1": _envelope(ratio(net_income_t1, average(assets_t1, assets_t2))),
        "cfo_t": _envelope(cfo_t),
        "cfoa_t": _envelope(ratio(cfo_t, assets_t)),
        "leverage_t": _envelope(ratio(current_values.get("borrowings_long_term"), assets_t)),
        "leverage_t1": _envelope(ratio(prior_values.get("borrowings_long_term"), assets_t1)),
        "current_ratio_t": _envelope(ratio(current_values.get("total_current_assets"), current_values.get("total_current_liabilities"))),
        "current_ratio_t1": _envelope(ratio(prior_values.get("total_current_assets"), prior_values.get("total_current_liabilities"))),
        "equity_issuance_amount_t": _envelope(Decimal(issuance) if issuance is not None else None),
        "gross_margin_t": _envelope(ratio(current_values.get("gross_profit"), current_values.get("revenue_total"))),
        "gross_margin_t1": _envelope(ratio(prior_values.get("gross_profit"), prior_values.get("revenue_total"))),
        "asset_turnover_t": _envelope(ratio(current_values.get("revenue_total"), assets_t)),
        "asset_turnover_t1": _envelope(ratio(prior_values.get("revenue_total"), assets_t1)),
        "current_refs": [f"data/financial/{ticker}/{current_id}.json"],
        "prior_refs": [f"data/financial/{ticker}/{prior_id}.json"] if prior else [],
        "opening_balance_refs": [f"data/financial/{ticker}/{opening_id}.json"] if opening else [],
    }
    return facts


def _magic_facts(financial: dict[str, Any], valuation_inputs: dict[str, Any]) -> dict[str, Any]:
    values = _metric_values(financial)
    multiplier = _SCALE[financial["scale"]]
    current_assets = values.get("total_current_assets")
    current_liabilities = values.get("total_current_liabilities")
    cash = values.get("cash_and_equivalents") or Decimal(0)
    investments = values.get("financial_investments_current") or Decimal(0)
    short_debt = values.get("borrowings_short_term") or Decimal(0)
    current_long_debt = values.get("borrowings_long_term_current_portion") or Decimal(0)
    nwc = None
    if current_assets is not None and current_liabilities is not None:
        nwc = ((current_assets - cash - investments) - (current_liabilities - short_debt - current_long_debt)) * multiplier

    ebit = None
    for basis in valuation_inputs.get("earnings_bases", []):
        if basis.get("earnings_basis_id") == "earn-core-ebit":
            ebit = _raw_basis_amount(basis.get("amount"))
            break
    enterprise_value = None
    for basis in valuation_inputs.get("ev_basis_family", []):
        if basis.get("basis_type") == "lease_exclusive" and basis.get("status") == "available":
            enterprise_value = Decimal(str(basis["enterprise_value"]["value"]))
            break

    return {
        "ebit": _envelope(ebit),
        "enterprise_value": _envelope(enterprise_value),
        "net_working_capital": _envelope(nwc),
        "net_operating_fixed_assets": _envelope(_scaled(values.get("property_plant_equipment"), multiplier)),
        "revenue": _envelope(_scaled(values.get("revenue_total"), multiplier)),
        "total_assets": _envelope(_scaled(values.get("total_assets"), multiplier)),
        "lease_basis_compatible": True,
    }


def _metric_values(document: dict[str, Any] | None) -> dict[str, Decimal]:
    if not document:
        return {}
    return {
        metric["metric_id"]: Decimal(str(metric["value"]))
        for section in ("income_statement", "balance_sheet", "cash_flow_statement")
        for metric in document.get(section, [])
        if metric.get("status") == "available" and metric.get("value") is not None
    }


def _envelope(value: Decimal | None) -> dict[str, Any]:
    if value is None:
        return {"status": "unavailable"}
    normalized = value.quantize(Decimal("0.000001"))
    return {"status": "available", "value": f"{normalized:f}"}


def _scaled(value: Decimal | None, multiplier: Decimal) -> Decimal | None:
    return value * multiplier if value is not None else None


def _raw_basis_amount(envelope: dict[str, Any] | None) -> Decimal | None:
    if not envelope or envelope.get("status") != "available":
        return None
    multiplier = Decimal(1)
    unit = envelope.get("unit") or ""
    for scale_name, scale_multiplier in _SCALE.items():
        if unit == scale_name or unit.startswith(f"{scale_name}_"):
            multiplier = scale_multiplier
            break
    return Decimal(str(envelope["value"])) * multiplier


def _maybe_read(path: Path) -> dict[str, Any] | None:
    return read_json(path) if path.exists() else None


def _require_ok(label: str, result) -> None:
    if result.ok:
        return
    details = "; ".join(f"{finding.rule_id}: {finding.message}" for finding in result.findings)
    raise UsPipelineError(f"{label} diagnostic failed: {details}")
