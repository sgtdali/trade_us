from decimal import Decimal
from pathlib import Path

from jinja2 import Environment

from fundamental_pipeline_us.reporting import (
    _build_ev_bridge,
    _build_ttm_earnings_bridges,
    _build_ttm_fcf_bridge,
    _date_gap_days,
    _fiscal_period_label,
    _fiscal_year_naming_note,
    _fmt_amount_millions,
    _fmt_peer_value,
    _fmt_scaled_amount,
    _maturity_coverage_notes,
    _matched_peer_comparisons,
    _ordered_comparisons,
    _peer_group,
    _peer_label,
    _review_required_signal_ids,
    _share_count_summary,
    _latest_available_annual_leases,
    _latest_comparisons,
    _validate_us_report_content,
)


def test_us_fiscal_period_labels_explain_ytd_and_non_calendar_years():
    assert _fiscal_period_label({
        "period": "2026-Q3", "period_type": "quarterly",
        "period_start": "2025-09-01", "period_end": "2026-05-10",
    }) == "fiscal Q3 2026 YTD (36 weeks) ended May 10, 2026"
    assert _fiscal_period_label({
        "period": "2026-FY", "period_type": "annual",
        "period_start": "2025-05-01", "period_end": "2026-04-30",
    }) == "2026 fiscal year ended April 30, 2026"


def test_us_fiscal_year_naming_note_explains_forward_label():
    note = _fiscal_year_naming_note(
        {"period": "2027-Q1", "period_end": "2026-04-30"},
        {"period": "2026-FY", "period_end": "2026-01-31"},
    )

    assert note is not None
    assert "labelled FY2027 even when it ends in 2026" in note


def test_us_template_is_separate_and_contains_only_english_section_titles():
    template = (
        Path(__file__).resolve().parents[2]
        / "templates" / "valuation" / "valuation-analysis-v1.en.md.j2"
    ).read_text(encoding="utf-8")
    assert "## 1. Executive Summary" in template
    assert "## 12. Source Summary" in template
    assert "## 10. Deterministic Financial Signals" in template
    assert "base-effect review required" in template
    assert "Parent-Attributed Free Cash Flow Yield (Proxy)" not in template
    assert "Positive Financial Signals" not in template
    assert "Negative Financial Signals" not in template
    assert "Business and Market Risks" not in template
    assert "Items to Monitor" not in template
    assert "risk_evidence_en" not in template
    assert "<details>" not in template
    assert "source_file" not in template
    assert "data/valuation-results" not in template
    assert "price_vs_sma_50.status == 'available'" in template
    assert "available_component_count" in template
    assert "**Peer cohort:**" in template
    assert "**Median basis:**" in template
    assert "**Comparable metrics:**" in template
    assert "**Omitted metrics:**" in template
    assert "**Decision weight:**" in template
    assert "The authored broad consumer-staples universe" not in template
    assert "Showing those medians would imply false comparability" not in template
    for turkish_title in ("Yönetici Özeti", "Değerleme", "Negatif Yönlü", "İzlenecek Gelişmeler"):
        assert turkish_title not in template


def test_us_maturity_schedule_renders_as_one_contiguous_markdown_table():
    template = (
        Path(__file__).resolve().parents[2]
        / "templates" / "valuation" / "valuation-analysis-v1.en.md.j2"
    ).read_text(encoding="utf-8")
    fragment = template.split("{% set maturity_rows", 1)[1].split(
        "{% set rate_rows", 1
    )[0]
    fragment = "{% set maturity_rows" + fragment
    rendered = Environment().from_string(fragment).render(
        debt={
            "maturity_profile": [
                {
                    "status": "reported", "liability_scope": "Long-term debt",
                    "maturity_bucket": "year 4", "value": 2143, "currency": "USD",
                },
                {
                    "status": "reported", "liability_scope": "Operating leases",
                    "maturity_bucket": "year 5", "value": 1796, "currency": "USD",
                },
            ]
        },
        fmt_number_en=lambda value, decimals: f"{value:,.{decimals}f}",
        fmt_scaled_amount_en=_fmt_scaled_amount,
    )

    assert "|---|---|---:|\n| Long-term debt" in rendered
    assert "USD |\n| Operating leases" in rendered
    table = rendered[
        rendered.index("| Liability scope") : rendered.index("The long-term-debt rows")
    ].strip()
    assert "\n\n" not in table


def test_us_signal_table_template_keeps_rows_contiguous():
    template = (
        Path(__file__).resolve().parents[2]
        / "templates" / "valuation" / "valuation-analysis-v1.en.md.j2"
    ).read_text(encoding="utf-8")
    signal_fragment = template.split("| Signal | Classification | Evidence |", 1)[1].split(
        "{% else %}", 1
    )[0]

    assert "%}\n| {{ signal_details" not in signal_fragment


def test_us_peer_comparison_labels_and_units_are_human_readable():
    assert _peer_label("val.method.earnings_yield.reported_parent") == "Earnings Yield"
    assert _fmt_peer_value(
        "val.method.earnings_yield.reported_parent",
        "0.025692184418321601578599574736228011618540517006362",
    ) == "2.57%"
    assert _fmt_peer_value("gross_margin", "25.14") == "25.14%"
    assert _fmt_peer_value("current_ratio", "0.771") == "0.77x"
    assert _fmt_peer_value("gross_margin", None) == "not available"


def test_us_money_and_debt_note_scales_are_explicit():
    assert _fmt_amount_millions({
        "status": "available", "value": "884938377749.9", "currency": "USD",
    }) == "884,938.4 million USD"
    assert _fmt_scaled_amount(2143, "USD", "million") == "2,143.0 million USD"


def test_us_ev_bridge_reconciles_noncontrolling_interests():
    def component(value: str) -> dict:
        return {"amount": {"status": "available", "value": value, "currency": "USD"}}

    ledger = {
        "comp-market-cap": component("1000"),
        "comp-debt-current": component("100"),
        "comp-debt-current-portion": component("20"),
        "comp-debt-noncurrent": component("300"),
        "comp-nci": component("40"),
        "comp-cash-0": component("60"),
        "comp-lease-current": component("10"),
        "comp-lease-noncurrent": component("30"),
    }
    ev_bases = {
        "ev-ex-lease": {"enterprise_value": {"status": "available", "value": "1400"}}
    }

    bridge = _build_ev_bridge(ledger, ev_bases)

    assert bridge is not None
    assert bridge["lease_exclusive_ev"] == 1400
    assert bridge["lease_exclusive_reconciled"] is True
    assert bridge["lease_inclusive_ev"] == 1440


def test_us_ttm_fcf_bridge_reconciles_parent_attribution():
    class Lookup:
        def __init__(self, values):
            self.values = values

        def get(self, metric_id):
            return self.values.get(metric_id)

    bridge = _build_ttm_fcf_bridge(
        Lookup({
            "free_cash_flow": {
                "value": -1946, "comparison_value": 425,
                "period": "2027-Q1", "comparison_period": "2026-Q1",
            }
        }),
        Lookup({"free_cash_flow": {"value": 14923, "period": "2026-FY"}}),
        {
            "val.method.fcf_yield.standard_equity": {
                "numerator": {"amount": {"value": "12343000000"}}
            }
        },
    )

    assert bridge is not None
    assert bridge["raw_ttm_fcf"] == 12552
    assert bridge["valuation_fcf"] == 12343
    assert bridge["attribution_adjustment"] == -209


def test_us_annual_lease_carrying_amounts_are_supplementary_when_latest_is_missing():
    class Lookup:
        def __init__(self, values):
            self.values = values

        def get(self, metric_id):
            return self.values.get(metric_id)

    fallback = _latest_available_annual_leases(
        Lookup({}),
        Lookup({
            "lease_liabilities_short_term": {
                "value": 321,
                "provenance": {"source_id": "sec-annual"},
            },
            "lease_liabilities_long_term": {"value": 1401},
        }),
        {"period": "2025-FY", "period_end": "2025-12-31"},
    )

    assert fallback == {
        "current": Decimal("321"),
        "noncurrent": Decimal("1401"),
        "total": Decimal("1722"),
        "period": "2025-FY",
        "period_end": "2025-12-31",
        "source_id": "sec-annual",
    }


def test_us_ttm_earnings_bridge_reconciles_method_operand():
    class Lookup:
        def __init__(self, values):
            self.values = values

        def get(self, metric_id):
            return self.values.get(metric_id)

    bridges = _build_ttm_earnings_bridges(
        Lookup({
            "net_profit_attributable_parent": {
                "value": 5330, "comparison_value": 4487,
                "period": "2027-Q1", "comparison_period": "2026-Q1",
            },
            "operating_profit_before_investment_activities": {
                "value": 7493, "comparison_value": 7135,
                "period": "2027-Q1", "comparison_period": "2026-Q1",
            },
        }),
        Lookup({
            "net_profit_attributable_parent": {"value": 21893, "period": "2026-FY"},
            "operating_profit_before_investment_activities": {"value": 29825, "period": "2026-FY"},
        }),
        {
            "val.method.pe.reported_parent": {
                "denominator": {"amount": {"value": "22736000000"}}
            },
            "val.method.ev_to_ebit.core": {
                "denominator": {"amount": {"value": "30183000000"}}
            },
        },
    )

    assert [bridge["calculated_ttm"] for bridge in bridges] == [22736, 30183]
    assert all(bridge["reconciled"] for bridge in bridges)


def test_us_ttm_bridge_treats_annual_latest_period_as_the_ttm():
    """A newly filed 10-K can be the most recent basis, making the latest
    period identical to the fiscal year. The bridge must then report the
    fiscal year itself instead of FY + FY - priorFY, which produced a
    nonsense TTM and made the report declare its own correct valuation
    operand irreconcilable (walk-forward backtest, 64 of 360 reports)."""
    class Lookup:
        def __init__(self, values):
            self.values = values

        def get(self, metric_id):
            return self.values.get(metric_id)

    annual = Lookup({
        "net_profit_attributable_parent": {
            "value": 1125.3, "comparison_value": 1661.3,
            "period": "2024-FY", "comparison_period": "2023-FY",
        },
    })
    bridges = _build_ttm_earnings_bridges(
        annual,
        annual,
        {"val.method.pe.reported_parent": {
            "denominator": {"amount": {"value": "1125300000"}}
        }},
    )

    assert [bridge["calculated_ttm"] for bridge in bridges] == [Decimal("1125.3")]
    assert bridges[0]["latest_is_annual"] is True
    assert bridges[0]["reconciled"] is True


def test_us_maturity_coverage_reports_missing_buckets_and_scopes():
    notes = _maturity_coverage_notes({
        "maturity_profile": [
            {
                "status": "reported", "liability_scope": "Long-term debt",
                "maturity_bucket": "next 12 months",
            },
            {
                "status": "reported", "liability_scope": "Operating leases",
                "maturity_bucket": "after year 5",
            },
        ]
    })

    assert any("Long-term debt: year 2" in note for note in notes)
    assert any("Operating leases: next 12 months" in note for note in notes)
    assert "Finance leases: no structured maturity schedule was disclosed or extracted." in notes


def test_us_share_count_summary_uses_million_shares_and_effective_date():
    summary = _share_count_summary({
        "share_basis": {
            "spot_basic_shares_outstanding": "7971728290",
            "effective_date": "2026-05-27",
            "derivation_method": "direct_reported",
        }
    })

    assert summary is not None
    assert summary["shares_millions"] == Decimal("7971.72829")
    assert summary["effective_date"] == "2026-05-27"
    assert summary["derivation_method"] == "Direct Reported"


def test_us_report_omits_noncomparable_ytd_fcf_peer_margin():
    comparisons = [
        {
            "comparison_type": "sector_peer",
            "method_or_dimension_scope": {"scope_id": "free_cash_flow_margin"},
        },
        {
            "comparison_type": "sector_peer",
            "method_or_dimension_scope": {"scope_id": "gross_margin"},
        },
        {
            "comparison_type": "sector_peer",
            "method_or_dimension_scope": {"scope_id": "current_ratio"},
        },
    ]

    ordered = _ordered_comparisons(comparisons)

    assert [_item["method_or_dimension_scope"]["scope_id"] for _item in ordered] == [
        "current_ratio"
    ]


def test_us_report_keeps_only_latest_comparison_for_same_scope():
    comparisons = [
        {
            "artifact_id": "old",
            "comparison_type": "sector_peer",
            "method_or_dimension_scope": {"scope_id": "current_ratio"},
            "temporal_context": {"generated_at": "2026-08-03T23:59:59Z"},
        },
        {
            "artifact_id": "new",
            "comparison_type": "sector_peer",
            "method_or_dimension_scope": {"scope_id": "current_ratio"},
            "temporal_context": {"generated_at": "2026-08-04T06:37:53Z"},
        },
    ]

    assert [item["artifact_id"] for item in _latest_comparisons(comparisons)] == ["new"]


def test_us_peer_report_recomputes_median_within_subject_operating_model():
    universe = {
        "members": [
            {"member_id": "wmt", "ticker": "WMT", "classification_refs": ["SEC:Retail"]},
            {"member_id": "cost", "ticker": "COST", "classification_refs": ["SEC:Retail"]},
            {"member_id": "ko", "ticker": "KO", "classification_refs": ["SEC:Manufacturing"]},
        ]
    }
    group = _peer_group(universe, "WMT")
    comparisons = _matched_peer_comparisons([{
        "comparison_type": "sector_peer",
        "statistics_or_matrix": {
            "members": [
                {"member_ref": "wmt", "eligibility_state": "excluded_insufficient_data", "value": None},
                {"member_ref": "cost", "eligibility_state": "eligible", "value": "0.03"},
                {"member_ref": "ko", "eligibility_state": "eligible", "value": "0.05"},
            ]
        },
    }], group, "WMT")

    stats = comparisons[0]["statistics_or_matrix"]
    assert group["label"] == "Authored operating-model cohort: Retail"
    assert [member["ticker"] for member in group["members"]] == ["WMT", "COST"]
    assert stats["median"] == Decimal("0.03")
    assert stats["eligible_peer_count"] == 1
    assert stats["approved_primary_cohort_count"] == 2


def test_us_negative_cash_flow_comparison_period_is_review_required_not_positive():
    review_ids = _review_required_signal_ids({
        "signals": [
            {
                "signal_id": "free_cash_flow_trend",
                "value": "positive",
                "evidence": {"current_value": 6859, "current_comparison_value": -2142},
            },
            {
                "signal_id": "operating_cash_flow_trend",
                "value": "positive",
                "evidence": {"current_value": 7543, "current_comparison_value": -1391},
            },
        ]
    })

    assert review_ids == ["free_cash_flow_trend", "operating_cash_flow_trend"]


def test_us_validator_checks_visible_method_labels_without_rendering_machine_ids():
    current_results = {
        "method_results": [{
            "method_id": "val.method.pe.reported_parent",
            "economic_family_id": "val.family.pe",
            "canonical_value": {"status": "available", "value": "20"},
        }]
    }

    assert _validate_us_report_content("Price / Earnings: 20.0x", current_results) == []
    errors = _validate_us_report_content("Historical valuation evidence", current_results)
    assert any("Price / Earnings" in error for error in errors)


def test_us_market_financial_gap_uses_real_period_and_price_dates():
    assert _date_gap_days("2026-04-30", "2026-07-31") == 92
