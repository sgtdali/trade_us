import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from adapter.pei_workflow import (
    PeiWorkflowError,
    append_events,
    approve_draft,
    approve_system_event,
    attach_result,
    check_triggers,
    latest_candidates,
    make_event,
    next_items,
    prepare_work_item,
    project,
    read_events,
    start_idea,
    evaluate_trigger,
    validate_draft,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "schemas" / "pei-workflow-event.schema.json").write_bytes(
        (REPO_ROOT / "schemas" / "pei-workflow-event.schema.json").read_bytes()
    )
    (tmp_path / "config" / "pei-workflows.json").write_bytes(
        (REPO_ROOT / "config" / "pei-workflows.json").read_bytes()
    )
    (tmp_path / "scripts" / "us_pei_pack.py").write_text("# test stub\n", encoding="utf-8")
    return tmp_path


def _source(repo: Path, name: str = "result.md") -> tuple[Path, dict]:
    path = repo / "pei" / "2026-08-12" / "shortlist" / "idea" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Result\n\nCompany-specific evidence and rejection.\n", encoding="utf-8")
    artifact = {
        "role": "result",
        "path": path.relative_to(repo).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    return path, artifact


def _candidate_event(
    artifact: dict,
    *,
    ticker: str = "GOOGL",
    bucket: str = "A",
    mapped: str | None = "comps",
    route_status: str = "supported",
    triggers: list | None = None,
    review_date: str | None = None,
) -> dict:
    payload = {
        "bucket": bucket,
        "setup": "Operating growth with a valuation question.",
        "variant_wedge": "Core economics may be stronger than the headline.",
        "first_rejection": "The denominator may not be recurring.",
        "suggested_workflow": mapped or "financials-normalizer",
        "mapped_workflow": mapped,
        "route_status": route_status,
    }
    if triggers is not None:
        payload["triggers"] = triggers
    if review_date is not None:
        payload["manual_review_date"] = review_date
    return make_event(
        event_id=f"CANDIDATE-{ticker}", event_type="candidate_screened",
        run_id="IDEA-20260812-test", ticker=ticker,
        source_artifacts=[artifact], payload=payload,
        recorded_at="2026-08-12T12:00:00+00:00",
    )


def _write_draft(repo: Path, events: list[dict]) -> Path:
    path = repo / "draft.json"
    path.write_text(json.dumps({"events": events}, indent=2), encoding="utf-8")
    return path


def test_approved_screen_projects_to_prerequisite_work_item(tmp_path):
    repo = _workspace(tmp_path)
    _, artifact = _source(repo)
    event = _candidate_event(artifact)
    draft = _write_draft(repo, [event])

    report = validate_draft(draft, repo_root=repo)
    assert report["status"] == "valid"
    approve_draft(draft, repo_root=repo)

    items = next_items(repo)
    assert len(items) == 1
    assert items[0]["requested_workflow"] == "comps"
    assert items[0]["workflow"] == "tearsheet"
    assert "once tearsheet" in items[0]["reason"]


def test_b_candidate_requires_trigger_or_dated_review(tmp_path):
    repo = _workspace(tmp_path)
    _, artifact = _source(repo)
    draft = _write_draft(repo, [_candidate_event(
        artifact, bucket="B", mapped=None, route_status="unsupported",
    )])

    report = validate_draft(draft, repo_root=repo)
    assert report["status"] == "rejected"
    assert any("B candidate needs" in error for error in report["errors"])

    reviewed = _candidate_event(
        artifact, bucket="B", mapped=None, route_status="unsupported",
        review_date="2026-08-19",
    )
    reviewed["event_id"] = "CANDIDATE-GOOGL-REVIEWED"
    report = validate_draft(_write_draft(repo, [reviewed]), repo_root=repo)
    assert report["status"] == "valid"


def test_unknown_workflow_is_rejected(tmp_path):
    repo = _workspace(tmp_path)
    _, artifact = _source(repo)
    event = _candidate_event(
        artifact, mapped="financials-normalizer", route_status="supported",
    )
    report = validate_draft(_write_draft(repo, [event]), repo_root=repo)
    assert report["status"] == "rejected"
    assert any("not in the catalog" in error for error in report["errors"])


def test_date_trigger_moves_waiting_candidate_to_ready(tmp_path):
    repo = _workspace(tmp_path)
    _, artifact = _source(repo)
    trigger = {
        "trigger_id": "NFLX-REVIEW",
        "type": "date_due",
        "check_cadence": "weekly",
        "next_check_date": "2026-08-19",
        "date": "2026-08-19",
        "on_match": "request_workflow",
        "workflow": "earnings_deep_dive",
        "date_status": "analyst_deadline",
    }
    event = _candidate_event(
        artifact, ticker="NFLX", bucket="B", mapped=None,
        route_status="unsupported", triggers=[trigger],
    )
    draft = _write_draft(repo, [event])
    approve_draft(draft, repo_root=repo)

    assert check_triggers(repo_root=repo, today=date(2026, 8, 18)) == []
    added = check_triggers(repo_root=repo, today=date(2026, 8, 19))
    assert len(added) == 1
    candidate = latest_candidates(project(read_events(repo)))["NFLX"]
    assert candidate["state"] == "ready"
    assert candidate["next_workflow"] == "earnings_deep_dive"


def test_waiting_status_exposes_trigger_date_and_route(tmp_path):
    repo = _workspace(tmp_path)
    _, artifact = _source(repo)
    candidate = _candidate_event(artifact, ticker="NVDA", mapped="earnings_preview")
    waiting = make_event(
        event_id="WAIT-NVDA", event_type="waiting_for_trigger",
        run_id=candidate["run_id"], ticker="NVDA", source_artifacts=[artifact],
        payload={"triggers": [{
            "trigger_id": "NVDA-PRINT", "type": "date_due",
            "check_cadence": "event_driven", "next_check_date": "2026-08-26",
            "date": "2026-08-26", "on_match": "request_workflow",
            "workflow": "earnings_deep_dive", "date_status": "confirmed",
        }]},
        recorded_at="2026-08-12T13:00:00+00:00",
    )
    state = project([approve_system_event(candidate), approve_system_event(waiting)])
    nvda = latest_candidates(state)["NVDA"]
    assert nvda["status_reason"] == (
        "waiting for date_due on 2026-08-26 -> earnings_deep_dive"
    )


def test_start_prepare_and_attach_are_persisted_without_chat_state(tmp_path):
    repo = _workspace(tmp_path)

    def fake_runner(command, **kwargs):
        out = Path(command[command.index("--out") + 1])
        if "--only" in command:
            ticker = command[command.index("--only") + 1]
            step = command[command.index("--for") + 1]
            target = out / "2026-08-12" / ticker / step
        else:
            target = out / "2026-08-12" / "shortlist" / "idea"
        target.mkdir(parents=True, exist_ok=True)
        (target / "pack.json").write_text('{"companies": []}\n', encoding="utf-8")
        (target / "instructions.md").write_text("instructions\n", encoding="utf-8")
        (target / "manifest.json").write_text("{}\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    run_id, idea_dir = start_idea(
        ["GOOGL"], repo_root=repo, no_refresh=True, runner=fake_runner,
    )
    answer = repo / "answer.md"
    answer.write_text("# Screen result\n", encoding="utf-8")
    attach_result(run_id, answer, repo_root=repo)
    assert (idea_dir / "result.md").is_file()
    with pytest.raises(PeiWorkflowError, match="already been attached"):
        attach_result(run_id, answer, repo_root=repo)

    _, artifact = _source(repo, "candidate-source.md")
    candidate = _candidate_event(artifact)
    candidate["run_id"] = run_id
    candidate["event_id"] = "CANDIDATE-RUN"
    approve_draft(_write_draft(repo, [candidate]), repo_root=repo)
    item = next_items(repo)[0]
    prepared = prepare_work_item(
        item["work_item_id"], repo_root=repo, no_refresh=True, runner=fake_runner,
    )
    assert (prepared / "pack.json").is_file()
    state = project(read_events(repo))
    assert latest_candidates(state)["GOOGL"]["state"] == "in_progress"
    continued = next_items(repo)
    assert continued[0]["action"] == "attach_result"
    assert continued[0]["work_item_id"] == item["work_item_id"]


def test_duplicate_system_event_is_rejected(tmp_path):
    repo = _workspace(tmp_path)
    event = approve_system_event(make_event(
        event_id="SAME", event_type="legacy_imported", run_id="RUN", ticker=None,
        payload={"state": "screen_recorded", "tickers": [], "artifact_dir": "pei"},
    ))
    append_events([event], repo_root=repo)
    with pytest.raises(PeiWorkflowError, match="duplicate event_id"):
        append_events([event], repo_root=repo)


def test_completion_without_prepared_work_is_rejected(tmp_path):
    repo = _workspace(tmp_path)
    _, artifact = _source(repo)
    candidate = _candidate_event(artifact, mapped="tearsheet")
    completion = make_event(
        event_id="COMPLETE-EARLY", event_type="workflow_completed",
        run_id=candidate["run_id"], ticker="GOOGL",
        source_artifacts=[artifact], payload={"workflow": "tearsheet"},
        recorded_at="2026-08-12T13:00:00+00:00",
    )
    report = validate_draft(_write_draft(repo, [candidate, completion]), repo_root=repo)
    assert report["status"] == "rejected"
    assert any("requires an in_progress candidate" in error for error in report["errors"])


@pytest.mark.parametrize(
    ("trigger", "document", "expected"),
    [
        ({
            "type": "event_window", "date": "2026-08-26", "lead_days": 14,
            "next_check_date": "2026-08-12",
        }, None, True),
        ({
            "type": "metric_condition", "metric_path": "/companies/META/value",
            "operator": ">=", "value": 10, "next_check_date": "2026-08-12",
        }, {"companies": [{"ticker": "META", "value": 12}]}, True),
        ({
            "type": "new_filing", "metric_path": "/companies/CRM/filing",
            "baseline": "2026-05-28", "next_check_date": "2026-08-12",
        }, {"companies": [{"ticker": "CRM", "filing": "2026-08-20"}]}, True),
        ({
            "type": "metric_condition", "metric_path": "/companies/META/missing",
            "operator": ">=", "value": 10, "next_check_date": "2026-08-12",
        }, {"companies": [{"ticker": "META", "value": 12}]}, False),
    ],
)
def test_trigger_types_are_fail_closed(trigger, document, expected):
    matched, _ = evaluate_trigger(
        trigger, today=date(2026, 8, 12), document=document,
    )
    assert matched is expected
