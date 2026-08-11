from decimal import Decimal

from fundamental_pipeline_us.diagnostics import _magic_facts, _piotroski_facts


def _financial(year: int, assets: int) -> dict:
    def metric(metric_id: str, value: int) -> dict:
        return {"metric_id": metric_id, "value": value, "status": "available"}
    return {
        "scale": "million",
        "income_statement": [
            metric("net_profit_for_period", year - 2000),
            metric("revenue_total", 100),
            metric("gross_profit", 60),
        ],
        "balance_sheet": [
            metric("total_assets", assets), metric("borrowings_long_term", 20),
            metric("total_current_assets", 50), metric("total_current_liabilities", 25),
            metric("cash_and_equivalents", 10), metric("property_plant_equipment", 30),
        ],
        "cash_flow_statement": [metric("cf_net_operating_activities", 15)],
    }


def test_piotroski_facts_use_three_annual_periods_and_share_delta():
    facts = _piotroski_facts(
        "KO", "2025-FY", "2024-FY", "2023-FY",
        _financial(2025, 110), _financial(2024, 100), _financial(2023, 90),
        (1000, 990),
    )

    assert facts["roa_t"]["status"] == "available"
    assert facts["roa_t1"]["status"] == "available"
    assert facts["equity_issuance_amount_t"]["value"] == "10.000000"
    assert facts["current_ratio_t"]["value"] == "2.000000"


def test_magic_facts_use_raw_currency_basis():
    inputs = {
        "earnings_bases": [{
            "earnings_basis_id": "earn-core-ebit",
            "amount": {"status": "available", "value": "12", "unit": "million_usd"},
        }],
        "ev_basis_family": [{
            "basis_type": "lease_exclusive", "status": "available",
            "enterprise_value": {"value": "500000000"},
        }],
    }

    facts = _magic_facts(_financial(2025, 110), inputs)

    assert facts["ebit"]["value"] == "12000000.000000"
    assert facts["revenue"]["value"] == "100000000.000000"
    assert Decimal(facts["net_working_capital"]["value"]) == Decimal("15000000.000000")
