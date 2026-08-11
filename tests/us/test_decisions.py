import json
from pathlib import Path

import pytest

from fundamental_pipeline_us.decisions import (
    _canonicalize_contract_enums,
    _extract_last_json,
    _metric_dictionary,
    _numeric_evidence_checks,
    _render,
    _first_sentence,
    _validate_portfolio_decision,
    _validate_direct_decision,
    _validate_decision,
)
from fundamental_pipeline_us.errors import UsPipelineError


def _decision() -> dict:
    return {
        "yargi": "sartli",
        "alinmaz_nedeni": None,
        "tez": "A testable mechanism.",
        "tez_testleri": [{
            "metric_id": "current_ratio", "baseline": 1.1,
            "expected_direction": "stay_above", "deadline_period": "2027-Q2",
            "failure_condition": "current_ratio falls below 1.0",
        }],
        "belirleyici_veriler": [
            {"tur": "sayisal", "reported_value": 12399.1, "report_section": "5"},
            {"tur": "sayisal", "reported_value": 2.57, "report_section": "8"},
            {"tur": "anlati", "report_section": "11", "alinti": "constraint"},
        ],
        "tezi_bozacak_kosullar": ["condition"],
        "belirsizlik": ["uncertainty"],
        "guven": "orta",
    }


def test_extract_last_json_ignores_cli_banner_and_prompt_echo():
    output = (
        'banner {"example": 1}\nfinal\n```json\n'
        '{"yargi": "sartli", "nested": {"metric_id": "current_ratio"}}\n```'
    )
    assert _extract_last_json(output) == {
        "yargi": "sartli", "nested": {"metric_id": "current_ratio"},
    }


def test_render_removes_multiline_comment_before_replacing():
    template = "<!-- {{REPORT}}\nmetadata -->\nBody {{REPORT}}"
    assert _render(template, {"REPORT": "REPORT_TEXT"}) == "Body REPORT_TEXT\n"


def test_metric_dictionary_falls_back_from_empty_latest_period(tmp_path):
    financial = tmp_path / "data" / "financial" / "TEST"
    financial.mkdir(parents=True)
    for period, period_end, value in (
        ("2025-Q3", "2025-03-31", 1.25),
        ("2025-FY", "2025-06-30", None),
    ):
        (financial / f"{period}.json").write_text(json.dumps({
            "period": period, "period_end": period_end,
        }), encoding="utf-8")
        (financial / f"{period}-derived-ratios.json").write_text(json.dumps({
            "period": period,
            "liquidity": [{
                "metric_id": "current_ratio", "value": value,
                "unit": "ratio", "period": period,
            }],
        }), encoding="utf-8")

    metrics, prompt = _metric_dictionary(tmp_path, "TEST")

    assert metrics == {"current_ratio": 1.25}
    assert "period 2025-Q3" in prompt


def test_numeric_evidence_uses_displayed_report_scale_and_section():
    report = "## 5. Capital\nMarket cap: 12,399.1 million USD\n## 8. Peers\nYield: 2.57%\n"
    checks = _numeric_evidence_checks(_decision(), report)
    assert [item["status"] for item in checks] == ["verified", "verified"]


def test_numeric_evidence_understands_english_down_as_negative_sign():
    payload = _decision()
    payload["belirleyici_veriler"] = [{
        "tur": "sayisal", "reported_value": -32.7, "report_section": "10",
    }]
    report = "## 10. Signals\nOperating cash flow was Down 32.7% year over year.\n"
    assert _numeric_evidence_checks(payload, report)[0]["status"] == "verified"


def test_validate_decision_rejects_unknown_metric_and_wrong_baseline():
    payload = _decision()
    payload["tez_testleri"][0]["metric_id"] = "invented_metric"
    with pytest.raises(UsPipelineError, match="unknown metric_id"):
        _validate_decision(payload, {"current_ratio": 1.1})

    payload = _decision()
    payload["tez_testleri"][0]["baseline"] = 9.9
    with pytest.raises(UsPipelineError, match="baseline does not match"):
        _validate_decision(payload, {"current_ratio": 1.1})


def test_canonicalize_contract_enums_maps_only_lossless_confidence_aliases():
    payload = _canonicalize_contract_enums({"guven": "medium", "yargi": "sartli"})
    assert payload["guven"] == "orta"
    assert payload["contract_normalizations"] == [{
        "field": "guven", "from": "medium", "to": "orta",
        "reason": "lossless English-to-canonical enum mapping",
    }]
    assert _canonicalize_contract_enums({"guven": " Medium Confidence "})["guven"] == "orta"
    assert _canonicalize_contract_enums({"guven": "ORTA"})["guven"] == "orta"


def test_us_cli_exposes_run_decisions_command():
    from fundamental_pipeline_us.cli import build_parser

    args = build_parser().parse_args([
        "run-decisions", "--as-of", "2026-08-03",
        "--tickers", "BJ", "COST", "--max-workers", "2",
    ])
    assert args.tickers == ["BJ", "COST"]
    assert args.max_workers == 2


def test_validate_direct_decision_requires_reasoning():
    payload = _decision()
    with pytest.raises(UsPipelineError, match="gerekce"):
        _validate_direct_decision(payload, {"current_ratio": 1.1})
    payload["gerekce"] = "Report-only reasoning."
    _validate_direct_decision(payload, {"current_ratio": 1.1})


def test_direct_output_schema_is_valid_json_and_requires_three_evidence_items():
    schema = json.loads((
        Path(__file__).resolve().parents[2] / "us" / "config" / "karar-katmani" /
        "schemas" / "direct-decision.v1.schema.json"
    ).read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["belirleyici_veriler"]["minItems"] == 3
    evidence = schema["properties"]["belirleyici_veriler"]["items"]
    assert set(evidence["required"]) == set(evidence["properties"])


def test_first_sentence_compacts_rejected_company_reason():
    assert _first_sentence("  First reason.  More detail follows. ") == "First reason."


def test_validate_portfolio_decision_enforces_two_fixed_slots_and_cash():
    payload = {
        "karar_turu": "ilk_olusum",
        "pozisyonlar": [{
            "ticker": "DG", "agirlik": 0.5, "karar": "ekle",
            "gerekce": "reason", "tez": "thesis", "izleme_kosullari": [],
        }],
        "nakit_orani": 0.5,
        "nakit_gerekcesi": "Second slot is not justified.",
        "reddedilen_adaylar": [
            {"ticker": "BJ", "gerekce": "reason"},
            {"ticker": "TGT", "gerekce": "reason"},
        ],
        "itiraz_edilen_elemeler": [{"ticker": "COST", "gerekce": "review"}],
        "guven": "orta",
        "portfoy_gerekcesi": "Portfolio reasoning.",
    }
    _validate_portfolio_decision(
        payload, candidate_tickers={"BJ", "DG", "TGT"},
        rejected_tickers={"COST", "KR", "WMT"},
    )
    payload["nakit_orani"] = 0.0
    with pytest.raises(UsPipelineError, match="nakit_orani"):
        _validate_portfolio_decision(
            payload, candidate_tickers={"BJ", "DG", "TGT"},
            rejected_tickers={"COST", "KR", "WMT"},
        )


def test_portfolio_output_schema_is_strict():
    schema = json.loads((
        Path(__file__).resolve().parents[2] / "us" / "config" / "karar-katmani" /
        "schemas" / "portfolio-decision.v1.schema.json"
    ).read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
