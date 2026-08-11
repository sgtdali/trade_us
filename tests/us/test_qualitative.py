from datetime import date
from pathlib import Path

import jsonschema

from adapter.models import FilingRef, SecFact
from adapter.qualitative import (
    _extract_debt_and_lease_note_details,
    _extract_item_1a,
    _keyword_centered_excerpt,
    _select_risk_evidence,
    build_and_write_debt_profile,
)


def _filing() -> FilingRef:
    return FilingRef(
        cik="0000021344", accession="0000000000-26-000001", form="10-Q",
        filing_date=date(2026, 7, 29), report_date=date(2026, 7, 3),
        primary_document="ko.htm",
    )


def test_extract_item_1a_prefers_substantive_uppercase_section(tmp_path: Path):
    document = tmp_path / "filing.htm"
    document.write_text(
        "<html><body><p>ITEM 1A. RISK FACTORS</p><p>" +
        ("Cybersecurity and competition may adversely affect our business. " * 30) +
        "</p><p>ITEM 1B. UNRESOLVED STAFF COMMENTS</p></body></html>",
        encoding="utf-8",
    )

    section = _extract_item_1a(document)

    assert section is not None
    assert "Cybersecurity" in section
    assert "UNRESOLVED" not in section


def test_extract_item_1a_accepts_dash_heading_and_skips_table_of_contents(tmp_path: Path):
    document = tmp_path / "filing.htm"
    document.write_text(
        "<html><body><p>Item 1A. Risk Factors 9 Item 1B. Comments 18</p>"
        "<p>Item 1A—Risk Factors</p><p>The risks described below could materially affect us. " +
        ("Supply chain disruption and cybersecurity incidents may affect operations. " * 30) +
        "</p><p>Item 1B—Unresolved Staff Comments</p></body></html>",
        encoding="utf-8",
    )

    section = _extract_item_1a(document)

    assert section is not None
    assert section.startswith("The risks described below")
    assert "Unresolved Staff Comments" not in section


def test_extract_item_1a_prefers_short_no_material_change_section_over_toc_leak(tmp_path: Path):
    document = tmp_path / "filing.htm"
    document.write_text(
        "<html><body><p>Item 1A. Risk Factors</p><p>" +
        ("Financial statements and supply chain discussion. " * 80) +
        "</p><p>Item 1B. Other</p>"
        "<p>Item 1A. Risk Factors</p>"
        "<p>No material change in the risk factors discussed in our Form 10-K has occurred. "
        "Investors should review the annual risk factors for the complete discussion. "
        "This quarterly report does not identify a new category of risk.</p>"
        "<p>Item 1B. Other Information</p></body></html>",
        encoding="utf-8",
    )

    section = _extract_item_1a(document)

    assert section is not None
    assert section.startswith("No material change")
    assert "Financial statements" not in section


def test_risk_evidence_is_unique_and_excerpt_keeps_matching_keyword():
    sentences = [
        "Geopolitical instability may cause supply chain disruptions and other business effects, including cybersecurity incidents and data breach costs.",
        "A separate cybersecurity failure or data breach could adversely affect customers and operations.",
    ]
    used = {sentences[0]}

    selected = _select_risk_evidence(
        sentences, ("cybersecurity", "data breach"), used
    )
    excerpt = _keyword_centered_excerpt(
        selected, ("cybersecurity", "data breach"), 12
    )

    assert selected == sentences[1]
    assert "cybersecurity" in excerpt.lower()
    assert excerpt.count("Table of Contents") == 0


def test_keyword_centered_excerpt_removes_sec_table_artifact():
    excerpt = _keyword_centered_excerpt(
        "Economic conditions and inflation may affect results.17Table of ContentsCalendar details",
        ("inflation", "economic condition"),
        20,
    )

    assert "inflation" in excerpt.lower()
    assert "Table of Contents" not in excerpt


def test_debt_profile_uses_only_reported_xbrl_totals(tmp_path: Path):
    workspace = tmp_path / "us"
    provenance = {
        "source_file": "raw/sec-filings/KO/accession.json",
        "source_type": "sec_inline_xbrl",
        "source_id": "sec-accession",
        "page": None,
        "sheet": "balance_sheet",
        "cell_or_range": "us-gaap:LongTermDebtCurrent#c1",
        "formula": None,
        "notes": None,
    }
    def metric(metric_id: str, value: int) -> dict:
        return {"metric_id": metric_id, "value": value, "status": "available", "provenance": provenance}
    direct = {
        "period_end": "2026-07-03", "currency": "USD", "scale": "million",
        "balance_sheet": [
            metric("borrowings_short_term", 100),
            metric("borrowings_long_term_current_portion", 200),
            metric("borrowings_long_term", 300),
            metric("cash_and_equivalents", 50),
        ],
    }

    artifact = build_and_write_debt_profile(
        workspace=workspace, ticker="KO", period_id="2026-Q2",
        direct=direct, filing=_filing(),
    )

    schema = __import__("json").loads(
        (Path(__file__).resolve().parents[2] / "schemas" / "debt-profile.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(artifact, schema)
    assert artifact["extraction_method"] == "sec_xbrl"
    assert artifact["diagnostics"]["near_term_debt_share"]["value"] == 0.5
    assert artifact["diagnostics"]["refinancing_pressure"]["level"] == "high"
    assert artifact["maturity_profile"] == []


def test_annual_note_details_extract_maturities_rates_and_currency_profile():
    filing = FilingRef(
        cik="0000021344", accession="0000000000-26-000002", form="10-K",
        filing_date=date(2026, 2, 20), report_date=date(2025, 12, 31),
        primary_document="annual.htm",
    )
    facts = (
        SecFact("http://fasb.org/us-gaap/2025", "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths", "120000000", "usd", "c1", None, filing.report_date),
        SecFact("http://fasb.org/us-gaap/2025", "OperatingLeaseWeightedAverageDiscountRatePercent", "0.045", "number", "c2", None, filing.report_date),
        SecFact(
            "http://fasb.org/us-gaap/2025", "DebtInstrumentFaceAmount", "500000000", "eur", "c3", None, date(2030, 1, 1),
            (("{http://fasb.org/us-gaap/2025}DebtInstrumentAxis", "{issuer}EuroNotesMember"),),
        ),
    )

    details = _extract_debt_and_lease_note_details(facts, filing, "KO")

    assert details["maturity_profile"][0]["value"] == 120
    assert details["weighted_average_rates"][0]["rate_pct"] == 4.5
    assert details["currency_profile"][0]["debt_currency"] == "EUR"
    assert details["currency_profile"][0]["value"] == 500
