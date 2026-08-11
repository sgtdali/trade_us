from pathlib import Path

from fundamental_pipeline_us.non_gaap import build_financial_operational_artifact


def test_non_gaap_artifact_does_not_invent_issuer_reported_values(tmp_path: Path):
    artifact = build_financial_operational_artifact(
        workspace=tmp_path,
        ticker="KO",
        period_id="2025-FY",
        period_start="2025-01-01",
        period_end="2025-12-31",
        filing_caches=(),
        fallback_source_id="sec-annual-accession",
    )

    assert artifact["default_source_id"] == "sec-annual-accession"
    assert [metric["status"] for metric in artifact["metrics"]] == [
        "unavailable", "unavailable",
    ]
    assert artifact["metrics"][0]["reason"] == "issuer_reported_ebitda_not_found"
    assert artifact["metrics"][1]["reason"] == "issuer_reported_net_debt_apm_not_found"
