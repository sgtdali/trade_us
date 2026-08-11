from datetime import date

import pytest

from fundamental_pipeline_us.errors import FactSelectionError
from fundamental_pipeline_us.models import SecFact
from fundamental_pipeline_us.normalize import (
    _coherence_violation,
    _include_derived_gross_profit,
    _include_temporary_equity,
    _select_fact,
    _unique_fact,
    build_comparison_period_artifact,
)


def test_non_numeric_inline_xbrl_transform_error_is_not_selected():
    broken = SecFact(
        namespace="http://fasb.org/us-gaap/2025", concept="ShortTermInvestments",
        value="(ixTransformValueError)", unit="USD", context_id="broken",
        start_date=None, end_date=date(2026, 3, 31), dimensions=(), is_nil=False,
    )
    valid = SecFact(
        namespace="http://fasb.org/us-gaap/2025", concept="ShortTermInvestments",
        value="125000000", unit="USD", context_id="valid",
        start_date=None, end_date=date(2026, 3, 31), dimensions=(), is_nil=False,
    )

    selected = _select_fact(
        (broken, valid), date(2026, 3, 31), "Q1",
        {"metric_id": "financial_investments_current", "period_kind": "instant", "concepts": ["ShortTermInvestments"]},
    )

    assert selected is not None
    assert selected[0].value == "125000000"


def test_parent_temporary_equity_is_added_to_parent_and_total_equity():
    provenance = {"formula": None, "cell_or_range": "reported", "notes": "SEC fact."}
    statements = {"balance_sheet": [
        {"metric_id": "equity_attributable_to_parent", "value": 100, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
        {"metric_id": "total_equity", "value": 120, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
        {"metric_id": "noncontrolling_interests", "value": 20, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
    ]}
    temporary = SecFact(
        namespace="http://fasb.org/us-gaap/2025",
        concept="TemporaryEquityCarryingAmountAttributableToParent",
        value="44000000", unit="USD", context_id="temporary-equity",
        start_date=None, end_date=date(2026, 3, 31), dimensions=(), is_nil=False,
    )
    evidence = []

    _include_temporary_equity(
        statements=statements, selected_evidence=evidence, facts=(temporary,),
        period_end=date(2026, 3, 31), fiscal_period="Q1",
    )

    by_id = {row["metric_id"]: row for row in statements["balance_sheet"]}
    assert by_id["equity_attributable_to_parent"]["value"] == 144
    assert by_id["total_equity"]["value"] == 164
    assert by_id["noncontrolling_interests"]["value"] == 20
    assert evidence[0]["metric_id"] == "temporary_equity_attributable_parent_adjustment"


def test_dimensionless_preferred_stock_closes_mezzanine_equity_balance_gap():
    provenance = {"formula": None, "cell_or_range": "reported", "notes": "SEC fact."}
    statements = {"balance_sheet": [
        {"metric_id": "total_assets", "value": 1222.069, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
        {"metric_id": "total_liabilities", "value": 357.49, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
        {"metric_id": "equity_attributable_to_parent", "value": 40.091, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
        {"metric_id": "total_equity", "value": 40.091, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
    ]}
    preferred = SecFact(
        namespace="http://fasb.org/us-gaap/2022", concept="PreferredStockValue",
        value="824488000", unit="USD", context_id="balance-sheet",
        start_date=None, end_date=date(2022, 12, 31), dimensions=(), is_nil=False,
    )

    _include_temporary_equity(
        statements=statements, selected_evidence=[], facts=(preferred,),
        period_end=date(2022, 12, 31), fiscal_period="FY",
    )

    by_id = {row["metric_id"]: row for row in statements["balance_sheet"]}
    assert by_id["total_equity"]["value"] == pytest.approx(864.579)
    assert by_id["equity_attributable_to_parent"]["value"] == pytest.approx(864.579)


def test_preferred_stock_is_not_double_counted_when_balance_sheet_already_balances():
    provenance = {"formula": None, "cell_or_range": "reported", "notes": "SEC fact."}
    statements = {"balance_sheet": [
        {"metric_id": "total_assets", "value": 500, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
        {"metric_id": "total_liabilities", "value": 300, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
        {"metric_id": "equity_attributable_to_parent", "value": 200, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
        {"metric_id": "total_equity", "value": 200, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
    ]}
    preferred = SecFact(
        namespace="http://fasb.org/us-gaap/2022", concept="PreferredStockValue",
        value="50000000", unit="USD", context_id="balance-sheet",
        start_date=None, end_date=date(2022, 12, 31), dimensions=(), is_nil=False,
    )

    _include_temporary_equity(
        statements=statements, selected_evidence=[], facts=(preferred,),
        period_end=date(2022, 12, 31), fiscal_period="FY",
    )

    by_id = {row["metric_id"]: row for row in statements["balance_sheet"]}
    assert by_id["total_equity"]["value"] == 200


def test_dimensioned_temporary_equity_classes_are_aggregated():
    provenance = {"formula": None, "cell_or_range": "reported", "notes": "SEC fact."}
    statements = {"balance_sheet": [
        {"metric_id": "equity_attributable_to_parent", "value": 400, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
        {"metric_id": "total_equity", "value": 400, "comparison_value": None, "data_type": "direct", "provenance": dict(provenance)},
    ]}
    axis = "{http://fasb.org/us-gaap/2025}StatementClassOfStockAxis"
    facts = tuple(
        SecFact(
            namespace="http://fasb.org/us-gaap/2025",
            concept="TemporaryEquityCarryingAmountAttributableToParent",
            value=value, unit="USD", context_id=context_id,
            start_date=None, end_date=date(2026, 3, 31),
            dimensions=((axis, member),), is_nil=False,
        )
        for value, context_id, member in (
            ("824000000", "series-a", "SeriesAPreferredStockMember"),
            ("908000000", "series-b", "SeriesBPreferredStockMember"),
        )
    )

    _include_temporary_equity(
        statements=statements, selected_evidence=[], facts=facts,
        period_end=date(2026, 3, 31), fiscal_period="Q1",
    )

    by_id = {row["metric_id"]: row for row in statements["balance_sheet"]}
    assert by_id["equity_attributable_to_parent"]["value"] == 2132
    assert by_id["total_equity"]["value"] == 2132


def _fact(value: str, decimals: str) -> SecFact:
    return SecFact(
        namespace="http://fasb.org/us-gaap/2025", concept="PaymentsToAcquirePropertyPlantAndEquipment",
        value=value, unit="usd", context_id="c-1", start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31), dimensions=(), decimals=decimals, is_nil=False,
    )


def test_unique_fact_prefers_more_precise_xbrl_duplicate():
    selected = _unique_fact(
        [_fact("1279000000", "-6"), _fact("1300000000", "-8")],
        metric_id="cf_capex_ppe_intangible", concept="PaymentsToAcquirePropertyPlantAndEquipment",
    )
    assert selected.value == "1279000000"


def test_unique_fact_equal_precision_conflict_fails_closed():
    with pytest.raises(FactSelectionError):
        _unique_fact(
            [_fact("1279000000", "-6"), _fact("1280000000", "-6")],
            metric_id="cf_capex_ppe_intangible", concept="PaymentsToAcquirePropertyPlantAndEquipment",
        )


def test_unique_fact_accepts_equivalent_numeric_lexical_forms():
    selected = _unique_fact(
        [_fact("744000000", "0"), _fact("744000000.0", "0")],
        metric_id="net_profit_for_period",
        concept="NetIncomeLoss",
    )

    assert selected.value in {"744000000", "744000000.0"}


def test_build_comparison_period_artifact_projects_only_prior_ytd_flows():
    provenance = {
        "source_file": "raw/sec-filings/KO/accession.json",
        "source_type": "sec_inline_xbrl",
        "source_id": "sec-accession",
        "page": None,
        "sheet": "income_statement",
        "cell_or_range": "current",
        "formula": None,
        "notes": "current",
    }
    metric = {
        "metric_id": "revenue",
        "name": "Revenue",
        "value": 100,
        "unit": "million_usd",
        "period": "2026-Q2",
        "comparison_value": 90,
        "comparison_period": "2025-Q2",
        "change": None,
        "change_unit": None,
        "data_type": "direct",
        "status": "available",
        "reason": None,
        "provenance": provenance,
    }
    direct = {
        "schema_version": 1,
        "ticker": "KO",
        "period": "2026-Q2",
        "period_start": "2026-01-01",
        "period_end": "2026-06-30",
        "period_type": "quarterly",
        "currency": "USD",
        "scale": "million",
        "consolidation": "consolidated",
        "audit_status": "unaudited",
        "accounting_basis": "US_GAAP",
        "inflation_adjustment": {"status": "not_applicable", "standard": None},
        "restatement": {"status": "original", "restated_from_publication_date": None},
        "publication_date": "2026-07-25",
        "source_revision": "accession",
        "rounding": None,
        "income_statement": [metric],
        "balance_sheet": [{**metric, "metric_id": "total_assets"}],
        "cash_flow_statement": [],
    }
    evidence = {
        "filing": {"accession": "accession"},
        "selected_facts": [{
            "metric_id": "revenue",
            "comparison": {
                "namespace": "http://fasb.org/us-gaap/2025",
                "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                "context_id": "prior-ytd",
                "start_date": "2025-01-01",
                "end_date": "2025-06-30",
            },
        }],
    }

    result = build_comparison_period_artifact(direct, evidence)

    assert result is not None
    assert result["period"] == "2025-Q2"
    assert result["period_start"] == "2025-01-01"
    assert result["period_end"] == "2025-06-30"
    assert result["income_statement"][0]["value"] == 90
    assert result["income_statement"][0]["comparison_value"] is None
    assert result["balance_sheet"] == []


def test_build_comparison_period_artifact_includes_prior_fy_balance_sheet():
    provenance = {
        "source_file": "raw/sec-filings/KO/accession.json",
        "source_type": "sec_inline_xbrl",
        "source_id": "sec-accession",
        "page": None,
        "sheet": "balance_sheet",
        "cell_or_range": "current",
        "formula": None,
        "notes": "current",
    }
    metric = {
        "metric_id": "total_assets",
        "name": "Total assets",
        "value": 100,
        "unit": "million_usd",
        "period": "2025-FY",
        "comparison_value": 90,
        "comparison_period": "2024-FY",
        "change": None,
        "change_unit": None,
        "data_type": "direct",
        "status": "available",
        "reason": None,
        "provenance": provenance,
    }
    direct = {
        "schema_version": 1, "ticker": "KO", "period": "2025-FY",
        "period_start": "2025-01-01", "period_end": "2025-12-31",
        "period_type": "annual", "currency": "USD", "scale": "million",
        "consolidation": "consolidated", "audit_status": "audited",
        "accounting_basis": "US_GAAP",
        "inflation_adjustment": {"status": "not_applicable", "standard": None},
        "restatement": {"status": "original", "restated_from_publication_date": None},
        "publication_date": "2026-02-20", "source_revision": "accession",
        "rounding": None, "income_statement": [], "balance_sheet": [metric],
        "cash_flow_statement": [],
    }
    evidence = {
        "filing": {"accession": "accession"},
        "selected_facts": [{
            "metric_id": "total_assets",
            "comparison": {
                "namespace": "http://fasb.org/us-gaap/2025", "concept": "Assets",
                "context_id": "prior-fy", "start_date": None, "end_date": "2024-12-31",
            },
        }],
    }

    result = build_comparison_period_artifact(direct, evidence)

    assert result is not None
    assert result["period"] == "2024-FY"
    assert result["period_type"] == "annual"
    assert result["balance_sheet"][0]["value"] == 90


def test_missing_gross_profit_is_derived_from_revenue_and_negative_cost():
    provenance = {
        "source_file": "raw/sec-filings/WMT/accession.json",
        "source_type": "sec_inline_xbrl", "source_id": "sec-accession",
        "page": None, "sheet": "income_statement", "cell_or_range": "fact",
        "formula": None, "notes": None,
    }
    def metric(metric_id: str, value: int, comparison: int) -> dict:
        return {
            "metric_id": metric_id, "name": metric_id, "value": value,
            "unit": "million_usd", "period": "2026-FY",
            "comparison_value": comparison, "comparison_period": "2025-FY",
            "change": None, "change_unit": None, "data_type": "direct",
            "status": "available", "reason": None, "provenance": provenance,
        }
    statements = {
        "income_statement": [
            metric("revenue_total", 100, 90), metric("cost_of_sales", -70, -65)
        ],
        "balance_sheet": [], "cash_flow_statement": [],
    }

    _include_derived_gross_profit(statements)

    gross = next(item for item in statements["income_statement"] if item["metric_id"] == "gross_profit")
    assert gross["value"] == 30
    assert gross["comparison_value"] == 25
    assert gross["data_type"] == "derived"
    assert gross["provenance"]["formula"] == "gross_profit = revenue_total + cost_of_sales"


def _income_metric(metric_id: str, value: float, *, concept: str = "fact", derived: bool = False) -> dict:
    return {
        "metric_id": metric_id, "name": metric_id, "value": value,
        "unit": "million_usd", "period": "2024-FY",
        "comparison_value": None, "comparison_period": None,
        "change": None, "change_unit": None,
        "data_type": "derived" if derived else "direct",
        "status": "available", "reason": None,
        "provenance": {
            "source_file": "raw/sec-filings/GIS/accession.json",
            "source_type": "sec_inline_xbrl", "source_id": "sec-accession",
            "page": None, "sheet": "income_statement",
            "cell_or_range": "{http://fasb.org/us-gaap/2023}" + concept + "#ctx",
            "formula": None, "notes": None,
        },
    }


def test_revenue_below_cost_of_sales_is_flagged_impossible():
    """GIS tagged us-gaap:Revenues at 2,037.8 million USD for a year whose
    cost of goods sold was 12,925.1 million USD. Because gross profit is
    derived from those two operands, the shared revenue + cost ==
    gross_profit identity was tautological and passed. Closing a gap that
    exceeds all revenue would need other operating income larger than the
    issuer's entire top line, so the selected revenue concept is wrong."""
    violation = _coherence_violation([
        _income_metric("revenue_total", 2037.8, concept="Revenues"),
        _income_metric("cost_of_sales", -12925.1),
        _income_metric("gross_profit", -10887.3, derived=True),
        _income_metric("operating_profit_before_investment_activities", 3431.7),
    ])
    assert violation is not None and "exceeding all revenue" in violation


def test_operating_profit_above_gross_profit_is_not_a_violation():
    """Other operating income -- equity-method earnings from joint
    ventures, benefit-plan non-service income, divestiture gains --
    legitimately lifts operating profit above the gross line. GIS reports
    exactly that in 2026-Q1, and an earlier version of this gate halted
    that valid filing."""
    assert _coherence_violation([
        _income_metric("revenue_total", 4517.5),
        _income_metric("cost_of_sales", -2984.7),
        _income_metric("gross_profit", 1532.8, derived=True),
        _income_metric("operating_profit_before_investment_activities", 1725.8),
    ]) is None


def test_loss_making_issuer_with_negative_gross_profit_is_not_second_guessed():
    """A genuinely bad year -- negative gross profit and negative operating
    profit -- is a business result, not a selection error."""
    assert _coherence_violation([
        _income_metric("revenue_total", 100.0),
        _income_metric("cost_of_sales", -110.0),
        _income_metric("gross_profit", -10.0, derived=True),
        _income_metric("operating_profit_before_investment_activities", -30.0),
    ]) is None


def test_select_fact_walks_to_the_next_concept_when_asked_to_skip():
    """The mapping's concept order encodes a deliberate semantic preference
    and is never reordered; only a positive falsification lets a caller step
    past it."""
    revenues = SecFact(
        namespace="http://fasb.org/us-gaap/2023", concept="Revenues",
        value="2037800000", unit="USD", context_id="a",
        start_date=date(2023, 5, 29), end_date=date(2024, 5, 26), dimensions=(), is_nil=False,
    )
    contract = SecFact(
        namespace="http://fasb.org/us-gaap/2023",
        concept="RevenueFromContractWithCustomerExcludingAssessedTax",
        value="19857200000", unit="USD", context_id="b",
        start_date=date(2023, 5, 29), end_date=date(2024, 5, 26), dimensions=(), is_nil=False,
    )
    rule = {
        "metric_id": "revenue_total", "period_kind": "duration",
        "concepts": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
    }

    preferred = _select_fact((revenues, contract), date(2024, 5, 26), "FY", rule)
    assert preferred is not None and preferred[0].concept == "Revenues"

    fallback = _select_fact(
        (revenues, contract), date(2024, 5, 26), "FY", rule,
        skip_concepts=frozenset({"Revenues"}),
    )
    assert fallback is not None
    assert fallback[0].concept == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_comparison_window_picks_the_one_year_anniversary_not_an_adoption_balance():
    """The 320-410 day comparison window absorbs 52/53-week calendars, so two
    instants a day apart can both fall inside it. Filers routinely tag an
    opening balance the day after a year end when adopting a standard (ASC 842
    at 2019-01-01 beside the 2018-12-31 close, with different amounts), which
    made every affected quarter fail as an ambiguous fact."""
    from datetime import date as _date
    from fundamental_pipeline_us.normalize import _closest_to_one_year_prior

    def instant(end: _date, value: str) -> SecFact:
        return SecFact(
            namespace="http://fasb.org/us-gaap/2019", concept="PropertyPlantAndEquipmentNet",
            value=value, unit="USD", context_id=value, start_date=None, end_date=end,
            dimensions=(), is_nil=False,
        )

    year_end = instant(_date(2018, 12, 31), "598200000")
    adoption = instant(_date(2019, 1, 1), "563000000")

    kept = _closest_to_one_year_prior([adoption, year_end], _date(2019, 12, 31))
    assert [fact.value for fact in kept] == ["598200000"]

    # A genuine tie is left intact so it still fails closed downstream.
    a = instant(_date(2018, 12, 30), "1")
    b = instant(_date(2019, 1, 1), "2")
    assert len(_closest_to_one_year_prior([a, b], _date(2019, 12, 31))) == 2


def _income(metric_id: str, value: float, *, derived: bool = False) -> dict:
    return {
        "metric_id": metric_id, "name": metric_id, "value": value, "unit": "million_usd",
        "period": "2019-Q1", "comparison_value": None, "comparison_period": None,
        "change": None, "change_unit": None,
        "data_type": "derived" if derived else "direct",
        "status": "available", "reason": None,
        "provenance": {"source_file": "f", "source_type": "sec_inline_xbrl", "source_id": "s",
                       "page": None, "sheet": "income_statement", "cell_or_range": "c",
                       "formula": None, "notes": None},
    }


def _uncosted_call(facts, gross_derived=False):
    from datetime import date as _date
    from fundamental_pipeline_us.normalize import _include_uncosted_revenue

    statements = {"income_statement": [
        _income("revenue_total", 35069.0), _income("cost_of_sales", -30623.0),
        _income("gross_profit", 3688.0, derived=gross_derived),
    ], "balance_sheet": [], "cash_flow_statement": []}
    evidence: list = []
    _include_uncosted_revenue(
        statements, evidence, facts=facts, period_end=_date(2018, 11, 25),
        rules=[{"metric_id": "revenue_total", "name": "Net Revenue",
                "statement": "income_statement", "period_kind": "duration",
                "concepts": ["RevenueFromContractWithCustomerExcludingAssessedTax"]}],
        build_metric=lambda rule, sel: _income(rule["metric_id"], float(sel[0].value) / 1e6),
    )
    return {m["metric_id"]: m["value"] for m in statements["income_statement"]}


def _dimensioned(value: str):
    from datetime import date as _date
    return SecFact(
        namespace="http://fasb.org/us-gaap/2018",
        concept="RevenueFromContractWithCustomerExcludingAssessedTax",
        value=value, unit="USD", context_id=value, start_date=_date(2018, 9, 3),
        end_date=_date(2018, 11, 25), dimensions=(("axis", "member"),), is_nil=False,
    )


def test_uncosted_revenue_is_taken_from_a_disclosed_component():
    """Gross profit is struck against merchandise sales, so a membership
    warehouse's total revenue exceeds revenue + cost by exactly its membership
    fees (COST fiscal 2019 Q1: 758 of 35,069)."""
    result = _uncosted_call((_dimensioned("758000000"), _dimensioned("34311000000")))
    assert result["revenue_without_matched_cost_of_sales"] == 758.0


def test_uncosted_revenue_is_never_the_residual_itself():
    """The residual only says how much to look for. With no disclosed
    component matching it nothing is written, so the identity still fails --
    otherwise the check would close by construction and stop being a check."""
    assert "revenue_without_matched_cost_of_sales" not in _uncosted_call(
        (_dimensioned("34311000000"),)
    )


def test_uncosted_revenue_is_not_applied_to_a_derived_gross_profit():
    """A derived gross profit already equals revenue + cost, so any residual
    would be spurious."""
    assert "revenue_without_matched_cost_of_sales" not in _uncosted_call(
        (_dimensioned("758000000"),), gross_derived=True
    )


def _bs(assets, liabilities, equity, *, comp=None):
    def row(mid, value, comparison):
        return {"metric_id": mid, "value": value, "comparison_value": comparison}
    c = comp or (None, None, None)
    return {
        "total_assets": row("total_assets", assets, c[0]),
        "total_liabilities": row("total_liabilities", liabilities, c[1]),
        "total_equity": row("total_equity", equity, c[2]),
    }


def test_mezzanine_combination_closes_a_gap_only_together():
    """A sheet can carry more than one mezzanine line and only their sum is the
    residual. KHC's 2015 column is 8,343 short with 8,320 of preferred stock
    beside 23 of redeemable noncontrolling interest, so testing each candidate
    alone rejected both and left the year unbalanced."""
    from fundamental_pipeline_us.normalize import _closing_combination

    by_id = _bs(122973.0, 56737.0, 57893.0)
    assert _closing_combination(by_id, [23.0, 8320.0], field="value") == {0, 1}


def test_single_mezzanine_line_is_selected_alone():
    from fundamental_pipeline_us.normalize import _closing_combination

    by_id = _bs(100.0, 60.0, 39.0)
    assert _closing_combination(by_id, [1.0, 7.0], field="value") == {0}


def test_a_balanced_sheet_takes_no_mezzanine_adjustment():
    """PEP's 2017 column balances on its own; carrying its 41 of preferred
    stock across from the following year overstated it by exactly that."""
    from fundamental_pipeline_us.normalize import _closing_combination

    by_id = _bs(79804.0, 68823.0, 10981.0)
    assert _closing_combination(by_id, [41.0], field="value") == set()


def test_an_unexplained_gap_applies_nothing():
    from fundamental_pipeline_us.normalize import _closing_combination

    by_id = _bs(100.0, 60.0, 30.0)
    assert _closing_combination(by_id, [3.0, 4.0], field="value") == set()
