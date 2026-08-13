import hashlib
import json
from pathlib import Path

import pytest

from adapter.pei_record import PeiRecordError, approve_draft, validate_draft


REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _workspace(tmp_path: Path, *, ticker: str = "VZ", price: float = 47.27):
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir(parents=True)
    (schema_dir / "pei-thesis-record.schema.json").write_bytes(
        (REPO_ROOT / "schemas" / "pei-thesis-record.schema.json").read_bytes()
    )
    source_dir = tmp_path / "pei" / "2026-08-12" / ticker / "pitch"
    source_dir.mkdir(parents=True)
    result = source_dir / "result.md"
    result.write_text(
        "# Pitch\n\nUpgrade only if service revenue growth is at least 3.0% by October.\n"
        "The next earnings print is the proof point.\n",
        encoding="utf-8",
    )
    pack = source_dir / "pack.json"
    pack.write_text(json.dumps({
        "intended_step": "pitch",
        "companies": [{"ticker": ticker, "closing_price_usd": price}],
    }), encoding="utf-8")
    return result, pack


def _draft(
    tmp_path: Path,
    *,
    ticker: str = "VZ",
    thesis_id: str = "VZ-20260812-operational-stabilization",
    metric: str = "mobility_and_broadband_service_revenue_growth_pct",
    price: float = 47.27,
) -> Path:
    result, pack = _workspace(tmp_path, ticker=ticker, price=price)
    result_rel = result.relative_to(tmp_path).as_posix()
    pack_rel = pack.relative_to(tmp_path).as_posix()
    draft = {
        "schema_version": 1,
        "record_id": f"{thesis_id}-OPEN",
        "thesis_id": thesis_id,
        "ticker": ticker,
        "recorded_at": "2026-08-12",
        "event_type": "thesis_opened",
        "thesis_operation": "open_new",
        "supersedes_thesis_id": None,
        "source_artifacts": [
            {"role": "result", "path": result_rel, "sha256": _sha(result)},
            {"role": "pack", "path": pack_rel, "sha256": _sha(pack)},
        ],
        "decision": {
            "pitch_verdict": "watchlist",
            "company_thesis_status": "untested",
            "security_thesis_readiness": "conditional",
            "position_action": "wait_for_proof",
            "position_status": "no_position",
            "evidence": [{
                "source_path": result_rel,
                "heading": "Pitch",
                "quote": "Upgrade only if service revenue growth is at least 3.0% by October.",
            }],
        },
        "narrative": {
            "thesis": {
                "text": "Operating stabilization may become a durable cash-flow inflection.",
                "evidence": [{"source_path": result_rel, "heading": "Pitch", "quote": "Upgrade only if service revenue growth is at least 3.0% by October."}],
            },
            "variant_perception": {
                "text": "Stabilization may be structural rather than temporary.",
                "evidence": [{"source_path": result_rel, "heading": "Pitch", "quote": "Upgrade only if service revenue growth is at least 3.0% by October."}],
            },
            "priced_in": {
                "text": "The current price reflects partial stabilization.",
                "evidence": [{"source_path": result_rel, "heading": "Pitch", "quote": "Upgrade only if service revenue growth is at least 3.0% by October."}],
            },
            "decision_rationale": {
                "text": "Wait for another quarter of proof or a better price.",
                "evidence": [{"source_path": result_rel, "heading": "Pitch", "quote": "The next earnings print is the proof point."}],
            },
        },
        "rules": [{
            "rule_id": f"{ticker}-ENTRY-1",
            "rule_type": "entry",
            "logic": "all_of",
            "conditions": [{
                "metric": metric, "operator": ">=", "value": 3.0, "unit": "pct",
            }],
            "test_date": "2026-10-20",
            "date_status": "estimated",
            "action": "propose_starter_long",
            "threshold_origin": "draft_for_pm_confirmation",
            "threshold_approval_status": "pending",
            "evidence": [{
                "source_path": result_rel,
                "heading": "Pitch",
                "quote": "Upgrade only if service revenue growth is at least 3.0% by October.",
            }],
        }],
        "catalysts": [{
            "event": "Next earnings print",
            "date": "2026-10-20",
            "date_status": "estimated",
            "evidence": {
                "source_path": result_rel,
                "heading": "Pitch",
                "quote": "The next earnings print is the proof point.",
            },
        }],
        "scenarios": [
            {"name": "downside", "probability_pct": 25, "target_date": "2027-08-12", "target_price": 41.65, "return_pct": -11.9, "status": "analyst_assumption"},
            {"name": "base", "probability_pct": 50, "target_date": "2027-08-12", "target_price": 51.56, "return_pct": 9.1, "status": "analyst_assumption"},
            {"name": "upside", "probability_pct": 25, "target_date": "2027-08-12", "target_price": 60.0, "return_pct": 26.9, "status": "analyst_assumption"},
        ],
        "data_gaps": ["earnings-call transcript"],
        "unstructured_findings": [],
        "pack_checks": [{
            "json_pointer": "/companies/0/closing_price_usd",
            "expected_value": price,
        }],
    }
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _v2_draft(tmp_path: Path) -> Path:
    path = _draft(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    result_path = payload["source_artifacts"][0]["path"]
    rule_id = payload["rules"][0]["rule_id"]
    proof = {
        "description": "Next earnings print",
        "date": "2026-10-20",
        "date_status": "estimated",
        "evidence": {
            "source_path": result_path,
            "heading": "Pitch",
            "quote": "The next earnings print is the proof point.",
        },
    }
    payload.update({
        "schema_version": 2,
        "thesis_pillars": [{
            "pillar_id": "P1",
            "name": "Operating stabilization",
            "claim": {
                "text": "Service revenue growth must prove the stabilization.",
                "evidence": [{
                    "source_path": result_path,
                    "heading": "Pitch",
                    "quote": "Upgrade only if service revenue growth is at least 3.0% by October.",
                }],
            },
            "priority": "core",
            "status": "untested",
            "kpi_metrics": ["mobility_and_broadband_service_revenue_growth_pct"],
            "linked_rule_ids": [rule_id],
            "latest_evidence_ids": ["E001"],
            "model_linkages": ["revenue_growth"],
            "next_proof_point": proof,
        }],
        "evidence_ledger": [{
            "evidence_id": "E001",
            "observed_at": "2026-08-12",
            "period": "Q2 2026",
            "pillar_ids": ["P1"],
            "signal": "untested",
            "fact": "The next earnings print remains the proof point.",
            "evidence": {
                "source_path": result_path,
                "heading": "Pitch",
                "quote": "The next earnings print is the proof point.",
            },
            "source_type": "analyst_pitch",
            "quality": "medium",
            "interpretation": "The thesis still requires a dated operating test.",
            "model_impact": None,
            "valuation_impact": None,
            "confidence_impact": "neutral",
            "action_implication": "wait_for_proof",
            "next_step": "Review the next earnings print.",
        }],
        "kpi_observations": [{
            "observation_id": "KPI001",
            "kpi": "Service revenue growth threshold",
            "pillar_id": "P1",
            "period": "Q3 2026",
            "observed_at": "2026-08-12",
            "prior_value": None,
            "current_value": 3.0,
            "unit": "pct_threshold",
            "status": "untested",
            "trend": "unknown",
            "evidence": {
                "source_path": result_path,
                "heading": "Pitch",
                "quote": "Upgrade only if service revenue growth is at least 3.0% by October.",
            },
            "linked_rule_ids": [rule_id],
            "next_proof_point": proof,
        }],
        "open_questions": [{
            "question_id": "Q001",
            "question": "Will service revenue growth clear the entry threshold?",
            "pillar_ids": ["P1"],
            "decision_impact": "high",
            "required_source": "next earnings release",
            "due_date": "2026-10-20",
            "date_status": "estimated",
            "status": "open",
        }],
    })
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_validates_company_specific_metric_without_closed_kpi_vocabulary(tmp_path):
    draft = _draft(
        tmp_path,
        ticker="AAPL",
        thesis_id="AAPL-20260812-supply-ai-inflection",
        metric="Siri_AI_public_beta_supported_English_markets",
        price=304.91,
    )

    report = validate_draft(
        draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker",
    )

    assert report["status"] == "valid"
    assert report["errors"] == []


def test_v1_record_remains_valid_after_schema_v2_is_added(tmp_path):
    draft = _draft(tmp_path)

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")

    assert report["status"] == "valid"


def test_v2_record_requires_monitoring_collections(tmp_path):
    draft = _draft(tmp_path)
    payload = json.loads(draft.read_text(encoding="utf-8"))
    payload["schema_version"] = 2
    draft.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")

    assert report["status"] == "rejected"
    assert any("thesis_pillars" in error for error in report["errors"])


def test_v2_monitoring_fields_validate_with_source_quotes_and_references(tmp_path):
    draft = _v2_draft(tmp_path)

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")

    assert report["status"] == "valid"
    assert report["errors"] == []


def test_v2_rejects_unknown_pillar_reference(tmp_path):
    draft = _v2_draft(tmp_path)
    payload = json.loads(draft.read_text(encoding="utf-8"))
    payload["kpi_observations"][0]["pillar_id"] = "P404"
    draft.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")

    assert report["status"] == "rejected"
    assert any("unknown pillar_id: P404" in error for error in report["errors"])


def test_v2_rejects_unverifiable_ledger_quote(tmp_path):
    draft = _v2_draft(tmp_path)
    payload = json.loads(draft.read_text(encoding="utf-8"))
    payload["evidence_ledger"][0]["evidence"]["quote"] = "This ledger quote was invented by the extractor."
    draft.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")

    assert report["status"] == "rejected"
    assert any("evidence_ledger/0/evidence" in error and "quote not found" in error for error in report["errors"])


def test_v2_rejects_reused_evidence_and_kpi_ids_on_append(tmp_path):
    draft = _v2_draft(tmp_path)
    tracker = tmp_path / "tracker"
    approve_draft(draft, repo_root=tmp_path, tracker_root=tracker)

    payload = json.loads(draft.read_text(encoding="utf-8"))
    result = tmp_path / payload["source_artifacts"][0]["path"]
    result.write_text(
        result.read_text(encoding="utf-8") + "A later result supplies new evidence.\n",
        encoding="utf-8",
    )
    payload["source_artifacts"][0]["sha256"] = _sha(result)
    payload["record_id"] = "VZ-20260812-operational-stabilization-EVIDENCE-20261020"
    payload["recorded_at"] = "2026-10-20"
    payload["event_type"] = "evidence_update"
    payload["thesis_operation"] = "append_existing"
    draft.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tracker)

    assert report["status"] == "rejected"
    assert any("evidence_id already exists" in error for error in report["errors"])
    assert any("observation_id already exists" in error for error in report["errors"])


def test_v2_reconciles_aggregate_status_with_impaired_core_pillars(tmp_path):
    draft = _v2_draft(tmp_path)
    payload = json.loads(draft.read_text(encoding="utf-8"))
    payload["thesis_pillars"][0]["status"] = "impaired"
    second = json.loads(json.dumps(payload["thesis_pillars"][0]))
    second["pillar_id"] = "P2"
    second["name"] = "Cash conversion"
    second["linked_rule_ids"] = []
    payload["thesis_pillars"].append(second)
    draft.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")

    assert report["status"] == "rejected"
    assert any("multiple impaired core pillars" in error for error in report["errors"])


def test_rejects_evidence_quote_not_present_in_result(tmp_path):
    draft = _draft(tmp_path)
    payload = json.loads(draft.read_text(encoding="utf-8"))
    payload["rules"][0]["evidence"][0]["quote"] = "This sentence was invented by the extractor."
    draft.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")

    assert report["status"] == "rejected"
    assert any("quote not found" in error for error in report["errors"])


def test_rejects_undated_rule(tmp_path):
    draft = _draft(tmp_path)
    payload = json.loads(draft.read_text(encoding="utf-8"))
    del payload["rules"][0]["test_date"]
    draft.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")

    assert report["status"] == "rejected"
    assert any("test_date" in error for error in report["errors"])


def test_rejects_pack_value_mismatch(tmp_path):
    draft = _draft(tmp_path)
    payload = json.loads(draft.read_text(encoding="utf-8"))
    payload["pack_checks"][0]["expected_value"] = 99.99
    draft.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")

    assert report["status"] == "rejected"
    assert any("pack has" in error for error in report["errors"])


def test_approval_is_append_only_and_duplicate_result_is_refused(tmp_path):
    draft = _draft(tmp_path)
    tracker = tmp_path / "tracker"

    target = approve_draft(
        draft, repo_root=tmp_path, tracker_root=tracker,
        approved_at="2026-08-12T12:00:00+00:00",
    )

    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["record_approval"]["status"] == "approved"
    assert rows[0]["rules"][0]["threshold_approval_status"] == "pending"
    with pytest.raises(PeiRecordError, match="rejected"):
        approve_draft(draft, repo_root=tmp_path, tracker_root=tracker)


def test_same_ticker_can_open_multiple_dated_theses(tmp_path):
    first_root = tmp_path / "first"
    first = _draft(first_root)
    tracker = tmp_path / "tracker"
    first_target = approve_draft(first, repo_root=first_root, tracker_root=tracker)

    second_root = tmp_path / "second"
    second = _draft(
        second_root,
        thesis_id="VZ-20270315-frontier-synergy",
    )
    second_payload = json.loads(second.read_text(encoding="utf-8"))
    second_result = second_root / second_payload["source_artifacts"][0]["path"]
    second_result.write_text(
        second_result.read_text(encoding="utf-8") + "Frontier creates a separate synergy thesis.\n",
        encoding="utf-8",
    )
    second_payload["source_artifacts"][0]["sha256"] = _sha(second_result)
    second.write_text(json.dumps(second_payload), encoding="utf-8")
    second_target = approve_draft(second, repo_root=second_root, tracker_root=tracker)

    assert first_target != second_target
    assert first_target.is_file()
    assert second_target.is_file()


def test_review_warning_requires_explicit_allow_review(tmp_path):
    draft = _draft(tmp_path)
    payload = json.loads(draft.read_text(encoding="utf-8"))
    result_path = payload["source_artifacts"][0]["path"]
    payload["unstructured_findings"] = [{
        "text": "Satellite risk needs manual classification.",
        "evidence": {
            "source_path": result_path,
            "heading": "Pitch",
            "quote": "The next earnings print is the proof point.",
        },
        "needs_review": True,
    }]
    draft.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")

    assert report["status"] == "valid_with_review"
    with pytest.raises(PeiRecordError, match="requires review"):
        approve_draft(draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker")
    target = approve_draft(
        draft, repo_root=tmp_path, tracker_root=tmp_path / "tracker",
        allow_review=True,
    )
    assert target.is_file()
