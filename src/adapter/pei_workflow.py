from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import jsonschema


class PeiWorkflowError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_text = text.encode("utf-8", errors="replace").decode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="replace", newline="\n") as handle:
            handle.write(safe_text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def safe_repo_path(repo_root: Path, relative: str) -> Path:
    supplied = Path(relative)
    if supplied.is_absolute() or ".." in supplied.parts:
        raise PeiWorkflowError(f"repo-relative path required: {relative!r}")
    resolved = (repo_root / supplied).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise PeiWorkflowError(f"path escapes repository: {relative!r}") from exc
    return resolved


def repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise PeiWorkflowError(f"path is outside repository: {path}") from exc


def load_catalog(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "pei-workflows.json"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PeiWorkflowError(f"workflow catalog cannot be read: {exc}") from exc
    workflows = catalog.get("workflows")
    if catalog.get("schema_version") != 1 or not isinstance(workflows, dict):
        raise PeiWorkflowError("workflow catalog has an unsupported shape")
    for name, definition in workflows.items():
        if not isinstance(definition, dict):
            raise PeiWorkflowError(f"workflow definition must be an object: {name}")
        for dependency in definition.get("required_workflows", []):
            if dependency not in workflows:
                raise PeiWorkflowError(f"unknown prerequisite {dependency!r} for {name!r}")
    return catalog


def load_event_schema(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "schemas" / "pei-workflow-event.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def schema_errors(event: dict[str, Any], repo_root: Path) -> list[str]:
    validator = jsonschema.Draft202012Validator(
        load_event_schema(repo_root), format_checker=jsonschema.FormatChecker(),
    )
    errors = []
    for error in sorted(validator.iter_errors(event), key=lambda item: list(item.absolute_path)):
        location = "/" + "/".join(str(part) for part in error.absolute_path)
        errors.append(f"schema {location}: {error.message}")
    return errors


def events_path(repo_root: Path) -> Path:
    return repo_root / "data" / "pei-workflow" / "events.jsonl"


def read_events(repo_root: Path, ledger_path: Path | None = None) -> list[dict[str, Any]]:
    path = ledger_path or events_path(repo_root)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PeiWorkflowError(f"invalid workflow JSON at {path}:{line_number}") from exc
        if not isinstance(event, dict):
            raise PeiWorkflowError(f"workflow event is not an object at {path}:{line_number}")
        errors = schema_errors(event, repo_root)
        if errors:
            raise PeiWorkflowError(f"invalid workflow event at {path}:{line_number}: {errors[0]}")
        event_id = event["event_id"]
        if event_id in ids:
            raise PeiWorkflowError(f"duplicate event_id in workflow ledger: {event_id}")
        ids.add(event_id)
        events.append(event)
    return events


def make_event(
    *,
    event_id: str,
    event_type: str,
    run_id: str,
    ticker: str | None,
    payload: dict[str, Any],
    source_artifacts: list[dict[str, Any]] | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "event_id": event_id,
        "event_type": event_type,
        "recorded_at": recorded_at or utc_now(),
        "run_id": run_id,
        "ticker": ticker,
        "source_artifacts": source_artifacts or [],
        "payload": payload,
    }


def approve_system_event(event: dict[str, Any], *, mode: str = "system_action", note: str | None = None) -> dict[str, Any]:
    approved = dict(event)
    approved["approval"] = {
        "status": "approved",
        "approved_at": utc_now(),
        "approval_mode": mode,
        "note": note,
    }
    return approved


def _load_draft_events(draft_path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    payload = draft_path.read_bytes()
    decoded = json.loads(payload.decode("utf-8"))
    if isinstance(decoded, dict) and isinstance(decoded.get("events"), list):
        values = decoded["events"]
    elif isinstance(decoded, list):
        values = decoded
    elif isinstance(decoded, dict):
        values = [decoded]
    else:
        raise PeiWorkflowError("draft must be an event, an event array, or an object with events")
    if not all(isinstance(item, dict) for item in values):
        raise PeiWorkflowError("every draft event must be an object")
    return payload, values


def validate_draft(
    draft_path: Path,
    *,
    repo_root: Path,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        draft_bytes, draft_events = _load_draft_events(draft_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, PeiWorkflowError) as exc:
        return {
            "status": "rejected", "draft": str(draft_path), "draft_sha256": None,
            "errors": [f"draft cannot be read: {exc}"], "warnings": [],
            "checked_at": utc_now(),
        }

    try:
        existing = read_events(repo_root, ledger_path)
        catalog = load_catalog(repo_root)["workflows"]
    except PeiWorkflowError as exc:
        errors.append(str(exc))
        existing, catalog = [], {}

    known_ids = {item["event_id"] for item in existing}
    draft_ids: set[str] = set()
    existing_result_hashes = {
        artifact["sha256"]
        for event in existing if event.get("event_type") == "result_attached"
        for artifact in event.get("source_artifacts", []) if artifact.get("role") == "result"
    }
    draft_result_hashes: set[str] = set()
    manual_review_tickers = {
        (event.get("run_id"), event.get("ticker"))
        for event in draft_events if event.get("event_type") == "manual_review_required"
    }

    def validate_trigger(trigger: dict[str, Any], trigger_prefix: str) -> None:
        trigger_workflow = trigger.get("workflow")
        if trigger_workflow is not None and trigger_workflow not in catalog:
            errors.append(f"{trigger_prefix}: unsupported workflow: {trigger_workflow!r}")
        trigger_type = trigger.get("type")
        if trigger_type in {"new_filing", "metric_condition"} and not trigger.get("metric_path"):
            errors.append(f"{trigger_prefix}: {trigger_type} requires metric_path")
        if trigger_type == "new_filing" and "baseline" not in trigger:
            errors.append(f"{trigger_prefix}: new_filing requires baseline")
        if trigger_type == "metric_condition" and (
            not trigger.get("operator") or "value" not in trigger
        ):
            errors.append(f"{trigger_prefix}: metric_condition requires operator and value")
        if trigger_type == "event_window" and not trigger.get("date"):
            errors.append(f"{trigger_prefix}: event_window requires date")

    for index, event in enumerate(draft_events):
        prefix = f"events/{index}"
        if "approval" in event:
            errors.append(f"{prefix}: draft event must not contain approval metadata")
        for error in schema_errors(event, repo_root):
            errors.append(f"{prefix}: {error}")
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            if event_id in known_ids or event_id in draft_ids:
                errors.append(f"{prefix}: duplicate event_id: {event_id}")
            draft_ids.add(event_id)

        for artifact in event.get("source_artifacts", []):
            if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
                continue
            try:
                path = safe_repo_path(repo_root, artifact["path"])
            except PeiWorkflowError as exc:
                errors.append(f"{prefix}: {exc}")
                continue
            if not path.is_file():
                errors.append(f"{prefix}: source artifact does not exist: {artifact['path']}")
                continue
            if sha256_path(path) != artifact.get("sha256"):
                errors.append(f"{prefix}: source hash mismatch: {artifact['path']}")
            if event.get("event_type") == "result_attached" and artifact.get("role") == "result":
                digest = artifact.get("sha256")
                if digest in existing_result_hashes or digest in draft_result_hashes:
                    errors.append(f"{prefix}: result artifact has already been attached")
                draft_result_hashes.add(digest)

        payload = event.get("payload") or {}
        workflow = payload.get("workflow")
        if event.get("event_type") in {
            "workflow_requested", "workflow_prepared", "workflow_completed", "trigger_satisfied",
        } and workflow not in catalog:
            errors.append(f"{prefix}: unsupported workflow: {workflow!r}")
        if event.get("event_type") == "candidate_screened":
            mapped = payload.get("mapped_workflow")
            route_status = payload.get("route_status")
            if mapped is not None and mapped not in catalog:
                errors.append(f"{prefix}: mapped_workflow is not in the catalog: {mapped!r}")
            if route_status == "supported" and mapped is None:
                errors.append(f"{prefix}: supported route requires mapped_workflow")
            if route_status != "supported" and mapped is not None:
                errors.append(f"{prefix}: non-supported route cannot carry mapped_workflow")
            if payload.get("bucket") == "B":
                has_trigger = bool(payload.get("triggers"))
                has_review = bool(payload.get("manual_review_date")) or (
                    event.get("run_id"), event.get("ticker")
                ) in manual_review_tickers
                if not has_trigger and not has_review:
                    errors.append(f"{prefix}: B candidate needs a trigger or dated manual review")
            for trigger_index, trigger in enumerate(payload.get("triggers") or []):
                validate_trigger(trigger, f"{prefix}/payload/triggers/{trigger_index}")
        elif event.get("event_type") == "waiting_for_trigger":
            for trigger_index, trigger in enumerate(payload.get("triggers") or []):
                validate_trigger(trigger, f"{prefix}/payload/triggers/{trigger_index}")

        transition_state = project([*existing, *draft_events[:index]])
        if isinstance(event.get("ticker"), str):
            transition_key = f"{event.get('run_id')}:{event.get('ticker')}"
            before = transition_state["candidates"].get(transition_key)
            if event.get("event_type") == "workflow_completed":
                if before is None or before.get("state") != "in_progress":
                    errors.append(f"{prefix}: workflow_completed requires an in_progress candidate")
                elif before.get("next_workflow") != payload.get("workflow"):
                    errors.append(f"{prefix}: completed workflow does not match prepared workflow")
            if event.get("event_type") == "trigger_satisfied" and (
                before is None or before.get("state") != "waiting"
            ):
                errors.append(f"{prefix}: trigger_satisfied requires a waiting candidate")

    status = "rejected" if errors else ("valid_with_review" if warnings else "valid")
    return {
        "status": status,
        "draft": str(draft_path),
        "draft_sha256": hashlib.sha256(draft_bytes).hexdigest(),
        "event_count": len(draft_events),
        "errors": errors,
        "warnings": warnings,
        "checked_at": utc_now(),
    }


def append_events(
    events: Iterable[dict[str, Any]],
    *,
    repo_root: Path,
    ledger_path: Path | None = None,
) -> Path:
    path = ledger_path or events_path(repo_root)
    existing = read_events(repo_root, path)
    existing_ids = {item["event_id"] for item in existing}
    additions = list(events)
    addition_ids: set[str] = set()
    for event in additions:
        errors = schema_errors(event, repo_root)
        if errors:
            raise PeiWorkflowError("event fails schema: " + "; ".join(errors))
        if event.get("approval", {}).get("status") != "approved":
            raise PeiWorkflowError("only approved workflow events may be appended")
        event_id = event["event_id"]
        if event_id in existing_ids or event_id in addition_ids:
            raise PeiWorkflowError(f"duplicate event_id: {event_id}")
        addition_ids.add(event_id)
    lines = [json.dumps(item, ensure_ascii=False, separators=(",", ":")) for item in existing + additions]
    write_text_atomic(path, "\n".join(lines) + ("\n" if lines else ""))
    return path


def approve_draft(
    draft_path: Path,
    *,
    repo_root: Path,
    ledger_path: Path | None = None,
    allow_review: bool = False,
    note: str | None = None,
    approval_mode: str = "explicit_user_confirmation",
) -> Path:
    report = validate_draft(draft_path, repo_root=repo_root, ledger_path=ledger_path)
    if report["status"] == "rejected":
        raise PeiWorkflowError("draft is rejected: " + "; ".join(report["errors"]))
    if report["status"] == "valid_with_review" and not allow_review:
        raise PeiWorkflowError("draft requires explicit review acceptance")
    _, draft_events = _load_draft_events(draft_path)
    approved = []
    approved_at = utc_now()
    for event in draft_events:
        item = dict(event)
        item["approval"] = {
            "status": "approved",
            "approved_at": approved_at,
            "approval_mode": approval_mode,
            "note": note,
        }
        approved.append(item)
    return append_events(approved, repo_root=repo_root, ledger_path=ledger_path)


def _candidate_default(run_id: str, ticker: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "ticker": ticker,
        "state": "screened",
        "bucket": None,
        "setup": None,
        "variant_wedge": None,
        "first_rejection": None,
        "suggested_workflow": None,
        "next_workflow": None,
        "target_workflow": None,
        "triggers": [],
        "manual_review_date": None,
        "status_reason": None,
        "completed_workflows": [],
        "corrections": [],
        "last_event_at": None,
    }


def project(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    state: dict[str, Any] = {"runs": {}, "candidates": {}, "work_items": {}, "last_event_at": None}
    for event in events:
        run_id = event["run_id"]
        ticker = event.get("ticker")
        event_type = event["event_type"]
        payload = event.get("payload") or {}
        state["last_event_at"] = event["recorded_at"]
        run = state["runs"].setdefault(run_id, {
            "run_id": run_id, "state": "unknown", "artifact_dir": None,
            "tickers": [], "result_path": None, "last_event_at": None,
        })
        run["last_event_at"] = event["recorded_at"]
        if event_type in {"idea_run_started", "legacy_imported"}:
            run.update({
                "state": payload.get("state", "waiting_for_result"),
                "artifact_dir": payload.get("artifact_dir"),
                "tickers": payload.get("tickers", run["tickers"]),
            })
        elif event_type == "result_attached" and ticker is None:
            run["state"] = "result_attached"
            run["result_path"] = payload.get("result_path")
        elif event_type == "screen_run_recorded":
            run["state"] = "screen_recorded"

        if ticker is None:
            continue
        key = f"{run_id}:{ticker}"
        candidate = state["candidates"].setdefault(key, _candidate_default(run_id, ticker))
        candidate["last_event_at"] = event["recorded_at"]
        if event_type == "candidate_screened":
            candidate.update({
                "bucket": payload.get("bucket"),
                "setup": payload.get("setup"),
                "variant_wedge": payload.get("variant_wedge"),
                "first_rejection": payload.get("first_rejection"),
                "suggested_workflow": payload.get("suggested_workflow"),
                "target_workflow": payload.get("mapped_workflow"),
                "triggers": payload.get("triggers", []),
                "manual_review_date": payload.get("manual_review_date"),
            })
            bucket = payload.get("bucket")
            if bucket == "A":
                candidate["next_workflow"] = payload.get("mapped_workflow")
                candidate["state"] = "ready" if payload.get("mapped_workflow") else "blocked"
                candidate["status_reason"] = (
                    None if payload.get("mapped_workflow") else
                    f"unsupported route: {payload.get('suggested_workflow')}"
                )
            elif bucket == "B":
                # B, "hicbir sey yapma, tarihi bekle" degil -- agy'nin B icin
                # bulduğu spesifik eksik-kapatici rota (ör. financials-
                # normalizer, comps-valuation, earnings-preview, scenario)
                # varsa hemen calistirilir; sonucu A'ya terfi ya da
                # thesis-tracker'a (izlemede kal) karar verir. Rota yoksa
                # (agy hicbir sey onermedi ya da kataloğumuzda karsiligi
                # yoksa) eskisi gibi trigger/manual_review_date'i bekler --
                # o guvenlik agi kaldirilmadi, yalniz rota varken artik
                # oncelikli degil.
                mapped = payload.get("mapped_workflow")
                if mapped:
                    candidate["next_workflow"] = mapped
                    candidate["state"] = "ready"
                    candidate["status_reason"] = (
                        f"B bucket -- watchlist research: {payload.get('suggested_workflow')}"
                    )
                else:
                    candidate["next_workflow"] = None
                    candidate["state"] = "waiting" if (
                        payload.get("triggers") or payload.get("manual_review_date")
                    ) else "blocked"
                    candidate["status_reason"] = (
                        f"manual review due {payload.get('manual_review_date')}"
                        if payload.get("manual_review_date") else "waiting for trigger"
                    )
            else:
                candidate["next_workflow"] = None
                candidate["state"] = "deprioritized"
                candidate["status_reason"] = "deprioritized until a later screen"
        elif event_type == "workflow_requested":
            candidate["state"] = "ready"
            candidate["next_workflow"] = payload.get("workflow")
            candidate["target_workflow"] = payload.get("workflow")
        elif event_type == "workflow_prepared":
            candidate["state"] = "in_progress"
            candidate["next_workflow"] = payload.get("workflow")
            candidate["target_workflow"] = payload.get("requested_workflow", payload.get("workflow"))
            work_item_id = payload.get("work_item_id")
            if work_item_id:
                state["work_items"][work_item_id] = {
                    **payload, "run_id": run_id, "ticker": ticker, "state": "prepared",
                }
        elif event_type == "workflow_completed":
            workflow = payload.get("workflow")
            if workflow and workflow not in candidate["completed_workflows"]:
                candidate["completed_workflows"].append(workflow)
            resume = payload.get("resume_workflow")
            if resume and resume != workflow:
                candidate["state"] = "ready"
                candidate["next_workflow"] = resume
                candidate["target_workflow"] = resume
            elif payload.get("next_workflow"):
                candidate["state"] = "ready"
                candidate["next_workflow"] = payload["next_workflow"]
                candidate["target_workflow"] = payload["next_workflow"]
            else:
                candidate["state"] = "completed"
                candidate["next_workflow"] = None
        elif event_type == "waiting_for_trigger":
            candidate["state"] = "waiting"
            candidate["triggers"] = payload.get("triggers", [])
            triggers = candidate["triggers"]
            if triggers:
                first = triggers[0]
                target = first.get("workflow") or "manual_review"
                due = first.get("date") or first.get("next_check_date") or "unscheduled"
                candidate["status_reason"] = (
                    f"waiting for {first.get('type')} on {due} -> {target}"
                )
            else:
                candidate["status_reason"] = "waiting for an unspecified trigger"
        elif event_type == "trigger_satisfied":
            candidate["state"] = "ready"
            candidate["next_workflow"] = payload.get("workflow")
            candidate["target_workflow"] = payload.get("workflow")
        elif event_type == "manual_review_required":
            candidate["state"] = "blocked"
            candidate["manual_review_date"] = payload.get("review_date")
            candidate["status_reason"] = payload.get("reason")
        elif event_type == "candidate_deprioritized":
            candidate["state"] = "deprioritized"
            candidate["next_workflow"] = None
        elif event_type == "source_interpretation_corrected":
            candidate["corrections"].append(payload)
            # Bir duzeltme, orijinal candidate_screened'in rotasini da
            # degistirebilir -- ör. o an kataloğumuzda olmayan bir skill
            # (initiating-coverage gibi) sonradan eklendiginde, eski
            # kaydi EZMEDEN (append-only) rotayi guncel kataloga gore
            # yeniden turetiriz. `mapped_workflow` payload'da varsa
            # candidate_screened'deki A/B mantigiyla ayni sekilde
            # next_workflow/state yeniden hesaplanir.
            if "promoted_to" in payload:
                # B->A otomatik terfi (evaluate_promotion). Insan onayi
                # yok -- karar agy'nin resolved/unresolved/indeterminate
                # ciktisina dayanir, bu event onu kalici hale getirir.
                candidate["bucket"] = payload.get("promoted_to")
            if "mapped_workflow" in payload:
                mapped = payload.get("mapped_workflow")
                candidate["target_workflow"] = mapped
                if candidate.get("bucket") in ("A", "B"):
                    candidate["next_workflow"] = mapped
                    candidate["state"] = "ready" if mapped else candidate["state"]
                    candidate["status_reason"] = (
                        payload.get("reason")
                        or (f"corrected route: {mapped}" if mapped else candidate["status_reason"])
                    )
        elif event_type == "thesis_opened":
            candidate["state"] = "thesis_opened"
            candidate["next_workflow"] = None
            candidate["status_reason"] = f"thesis opened: {payload.get('thesis_id')}"
    return state


def _first_missing_prerequisite(
    workflow: str,
    completed: set[str],
    catalog: dict[str, Any],
    seen: set[str] | None = None,
) -> str | None:
    seen = seen or set()
    if workflow in seen:
        raise PeiWorkflowError(f"workflow prerequisite cycle at {workflow}")
    seen.add(workflow)
    for dependency in catalog[workflow].get("required_workflows", []):
        if dependency in completed:
            continue
        nested = _first_missing_prerequisite(dependency, completed, catalog, seen)
        return nested or dependency
    return None


def next_items(repo_root: Path, *, ledger_path: Path | None = None) -> list[dict[str, Any]]:
    events = read_events(repo_root, ledger_path)
    projection = project(events)
    catalog = load_catalog(repo_root)["workflows"]
    items: list[dict[str, Any]] = []
    priority = {"A": 0, "B": 1, "C": 2, "Reject": 3, None: 4}
    for candidate in latest_candidates(projection).values():
        if candidate["state"] == "in_progress":
            work_item = next(
                (
                    item for item in projection["work_items"].values()
                    if item["run_id"] == candidate["run_id"]
                    and item["ticker"] == candidate["ticker"]
                    and item["state"] == "prepared"
                ),
                None,
            )
            if work_item:
                items.append({
                    "work_item_id": work_item["work_item_id"],
                    "run_id": candidate["run_id"],
                    "ticker": candidate["ticker"],
                    "bucket": candidate["bucket"],
                    "workflow": work_item["workflow"],
                    "requested_workflow": work_item.get(
                        "requested_workflow", work_item["workflow"],
                    ),
                    "reason": "pack hazir; ChatGPT sonucu bekleniyor",
                    "action": "attach_result",
                    "artifact_dir": work_item["artifact_dir"],
                    "required_context_artifacts": work_item.get(
                        "required_context_artifacts", [],
                    ),
                })
            continue
        if candidate["state"] != "ready" or not candidate.get("next_workflow"):
            continue
        target = candidate["next_workflow"]
        if target not in catalog:
            continue
        missing = _first_missing_prerequisite(
            target, set(candidate["completed_workflows"]), catalog,
        )
        effective = missing or target
        work_item_id = f"WI-{candidate['run_id']}-{candidate['ticker']}-{effective}"
        items.append({
            "work_item_id": work_item_id,
            "run_id": candidate["run_id"],
            "ticker": candidate["ticker"],
            "bucket": candidate["bucket"],
            "workflow": effective,
            "requested_workflow": target,
            "reason": (
                f"{target} icin once {effective} gerekli"
                if missing else f"{candidate['bucket']} bucket ve desteklenen rota"
            ),
            "action": "prepare",
        })
    action_priority = {"attach_result": 0, "prepare": 1}
    return sorted(items, key=lambda item: (
        action_priority[item["action"]], priority[item["bucket"]],
        item["ticker"], item["workflow"],
    ))


def latest_candidates(projection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for candidate in projection["candidates"].values():
        prior = latest.get(candidate["ticker"])
        if prior is None or (candidate.get("last_event_at") or "") > (prior.get("last_event_at") or ""):
            latest[candidate["ticker"]] = candidate
    return latest


def _artifact(role: str, repo_root: Path, path: Path) -> dict[str, Any]:
    return {"role": role, "path": repo_relative(repo_root, path), "sha256": sha256_path(path)}


def _event_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}-{stamp}"


def _locate_single(root: Path, name: str) -> Path:
    matches = sorted(root.rglob(name))
    if len(matches) != 1:
        raise PeiWorkflowError(f"expected one {name} below {root}, found {len(matches)}")
    return matches[0]


def start_idea(
    tickers: list[str],
    *,
    repo_root: Path,
    no_refresh: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[str, Path]:
    normalized = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
    if not normalized or len(set(normalized)) != len(normalized):
        raise PeiWorkflowError("tickers must be a non-empty unique list")
    run_id = f"IDEA-{date.today():%Y%m%d}-{datetime.now(timezone.utc):%H%M%S%f}"
    run_root = repo_root / "data" / "pei-workflow" / "runs" / run_id
    command = [
        sys.executable, str(repo_root / "scripts" / "us_pei_pack.py"),
        "--for", "idea", "--tickers", ",".join(normalized), "--out", str(run_root),
    ]
    if no_refresh:
        command.append("--no-refresh")
    completed = runner(command, cwd=repo_root, text=True, capture_output=True)
    if completed.returncode:
        raise PeiWorkflowError(f"idea pack failed: {(completed.stderr or completed.stdout).strip()}")
    pack = _locate_single(run_root, "pack.json")
    artifact_dir = pack.parent
    event = make_event(
        event_id=_event_id("IDEA-START"), event_type="idea_run_started",
        run_id=run_id, ticker=None,
        source_artifacts=[
            _artifact("pack", repo_root, pack),
            _artifact("instructions", repo_root, artifact_dir / "instructions.md"),
        ],
        payload={
            "state": "waiting_for_result", "tickers": normalized,
            "artifact_dir": repo_relative(repo_root, artifact_dir), "command": command,
        },
    )
    append_events([approve_system_event(event)], repo_root=repo_root)
    return run_id, artifact_dir


def attach_result(
    run_id: str,
    source: Path,
    *,
    repo_root: Path,
    work_item_id: str | None = None,
) -> Path:
    if not source.is_file():
        raise PeiWorkflowError(f"result file does not exist: {source}")
    events = read_events(repo_root)
    projection = project(events)
    if work_item_id:
        work_item = projection["work_items"].get(work_item_id)
        if not work_item or work_item["run_id"] != run_id:
            raise PeiWorkflowError(f"unknown work item for run: {work_item_id}")
        target_dir = safe_repo_path(repo_root, work_item["artifact_dir"])
        ticker = work_item["ticker"]
        workflow = work_item["workflow"]
    else:
        run = projection["runs"].get(run_id)
        if not run or not run.get("artifact_dir"):
            raise PeiWorkflowError(f"unknown run: {run_id}")
        target_dir = safe_repo_path(repo_root, run["artifact_dir"])
        ticker = None
        workflow = "idea"
    target = target_dir / "result.md"
    incoming = source.read_bytes()
    incoming_hash = hashlib.sha256(incoming).hexdigest()
    for event in events:
        if event["event_type"] != "result_attached":
            continue
        if any(
            artifact.get("role") == "result" and artifact.get("sha256") == incoming_hash
            for artifact in event.get("source_artifacts", [])
        ):
            raise PeiWorkflowError("the same result artifact has already been attached")
    if target.exists() and target.read_bytes() != incoming:
        raise PeiWorkflowError(f"result already exists with different content: {target}")
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    manifest = target_dir / "manifest.json"
    if manifest.is_file():
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["result_sha256"] = sha256_path(target)
        write_text_atomic(manifest, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    event = make_event(
        event_id=_event_id("RESULT"), event_type="result_attached", run_id=run_id,
        ticker=ticker, source_artifacts=[_artifact("result", repo_root, target)],
        payload={
            "result_path": repo_relative(repo_root, target), "workflow": workflow,
            "work_item_id": work_item_id,
        },
    )
    append_events([approve_system_event(event)], repo_root=repo_root)
    return target


# Katalog workflow'undan eklentideki gercek skill klasoru adina esleme.
# config/pei-workflows.json'daki her workflow, plugin'in skills/ altinda
# ayni islevi goren bir klasore karsilik gelir (isimler farkli yazilir).
STEP_TO_SKILL = {
    "idea": "idea-generation",
    "tearsheet": "company-tearsheet",
    "earnings_preview": "earnings-preview",
    "earnings_deep_dive": "earnings-deep-dive",
    "comps": "comps-valuation",
    "pitch": "long-short-pitch",
    "thesis_tracker": "thesis-tracker",
    "scenario": "scenario-sensitivity-generator",
    "initiating_coverage": "initiating-coverage",
}

CODEX_ANALYSIS_TIMEOUT_SECONDS = 900

# Skill -> (model, reasoning effort). Gorevin karmasikligina/hata maliyetine
# gore secildi -- yalniz maliyet degil. Terra = gpt-5.6-terra (dengeli,
# fact-gathering + orta senteze uygun), Sol = gpt-5.6-sol (frontier; yatirim
# karari/model mimarisi/hata-avlama gibi hata maliyeti yuksek isler), Luna =
# gpt-5.6-luna (hizli/ucuz; tekrarlayan izleme veya dusuk-riskli isler).
# `codex -c model_reasoning_effort=<level>` ile verilir (--effort diye ayri
# bir bayrak yok, agy'nin bayragiyla karistirilmasin). Kataloğumuzda henuz
# olmayan skill'ler de dahil -- eklendikce hazir olsun diye.
SKILL_MODEL_CONFIG: dict[str, tuple[str, str]] = {
    "idea-generation": ("gpt-5.6-terra", "high"),
    "company-tearsheet": ("gpt-5.6-terra", "medium"),
    "financials-normalizer": ("gpt-5.6-terra", "high"),
    "initiating-coverage": ("gpt-5.6-sol", "xhigh"),
    "earnings-preview": ("gpt-5.6-sol", "high"),
    "earnings-deep-dive": ("gpt-5.6-sol", "high"),
    "comps-valuation": ("gpt-5.6-terra", "high"),
    "three-statement-model-builder": ("gpt-5.6-sol", "xhigh"),
    "dcf-model-builder": ("gpt-5.6-sol", "high"),
    "equity-model-update": ("gpt-5.6-terra", "high"),
    "model-audit-tieout": ("gpt-5.6-sol", "xhigh"),
    "scenario-sensitivity-generator": ("gpt-5.6-terra", "high"),
    "event-driven-analyzer": ("gpt-5.6-sol", "xhigh"),
    "economic-impact-report": ("gpt-5.6-sol", "high"),
    "long-short-pitch": ("gpt-5.6-sol", "xhigh"),
    "portfolio-risk-management": ("gpt-5.6-sol", "xhigh"),
    "thesis-tracker": ("gpt-5.6-luna", "medium"),
    "catalyst-calendar": ("gpt-5.6-luna", "low"),
    "memo-builder": ("gpt-5.6-sol", "high"),
    "meeting-prep": ("gpt-5.6-terra", "medium"),
    "deck-report-qc": ("gpt-5.6-terra", "high"),
    "user-context": ("gpt-5.6-luna", "low"),
}
CODEX_MODEL_DEFAULT: tuple[str, str] = ("gpt-5.6-sol", "high")


def _find_pei_plugin_root() -> Path | None:
    """~/.codex/plugins/cache altindaki public-equity-investing eklenti kokunu bulur.

    Surum klasoru (ör. 0.1.31) makineden makineye ve zamanla degisir; en
    yuksek surumu secer. PEI_PLUGIN_ROOT ortam degiskeni ile override
    edilebilir.
    """
    override = os.environ.get("PEI_PLUGIN_ROOT")
    if override:
        path = Path(override)
        return path if path.is_dir() else None
    base = (Path.home() / ".codex" / "plugins" / "cache" / "openai-curated-remote"
            / "public-equity-investing")
    if not base.is_dir():
        return None
    versions = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name)
    return versions[-1] if versions else None


def run_codex_analysis(
    run_id: str,
    *,
    repo_root: Path,
    work_item_id: str | None = None,
    timeout: int = CODEX_ANALYSIS_TIMEOUT_SECONDS,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path:
    """codex CLI (ChatGPT/Codex, gercek PEI eklentisiyle) calistirip ciktiyi kaydeder.

    Tarayicida ChatGPT'ye pack.json + instructions.md yapistirip cevabi elle
    kopyalamanin otomatik esdegeri. pack.json/instructions.md zaten hazir
    olmali (start_idea / prepare_work_item). Eklenti Codex CLI'da resmi bir
    marketplace olarak kayitli degil (yalnizca disk uzerinde bir cache), bu
    yuzden --add-dir ile eklenti kokune dosya-sistemi erisimi verilip ilgili
    SKILL.md'yi kendi okumasi istenir; boylece skill'in kendi operating
    rules/output contract'i (sadece bizim instructions.md'miz degil) gercekten
    uygulanir. Rota onerileri kataloğumuzda olmayan gercek skill isimlerine
    (ör. equity-model-update) cikabilir -- bilinerek serbest birakildi,
    generate_draft_events'teki route_unsupported/manual_review_required kapisi
    bunu zaten guvenli sekilde yakalar.

    Donen result.md, elle yapistirilanla ayni yoldan (attach_result ->
    generate_draft_events -> agy cikarimi -> validate_draft -> approve_draft)
    gecer; bu fonksiyon yalniz "sonucu nasil ürettik" kismini degistirir.
    """
    events = read_events(repo_root)
    projection = project(events)
    if work_item_id:
        work_item = projection["work_items"].get(work_item_id)
        if not work_item or work_item["run_id"] != run_id:
            raise PeiWorkflowError(f"unknown work item for run: {work_item_id}")
        artifact_dir = safe_repo_path(repo_root, work_item["artifact_dir"])
        workflow = work_item["workflow"]
    else:
        run = projection["runs"].get(run_id)
        if not run or not run.get("artifact_dir"):
            raise PeiWorkflowError(f"unknown run: {run_id}")
        artifact_dir = safe_repo_path(repo_root, run["artifact_dir"])
        workflow = "idea"

    pack_path = artifact_dir / "pack.json"
    instructions_path = artifact_dir / "instructions.md"
    if not pack_path.is_file() or not instructions_path.is_file():
        raise PeiWorkflowError(f"pack.json/instructions.md bulunamadi: {artifact_dir}")

    skill_name = STEP_TO_SKILL.get(workflow)
    if not skill_name:
        raise PeiWorkflowError(f"codex icin skill eslesmesi yok: {workflow}")

    plugin_root = _find_pei_plugin_root()
    if plugin_root is None:
        raise PeiWorkflowError(
            "public-equity-investing eklenti koku bulunamadi "
            "(~/.codex/plugins/cache/openai-curated-remote/public-equity-investing). "
            "PEI_PLUGIN_ROOT ortam degiskeniyle elle belirtin."
        )
    skill_path = plugin_root / "skills" / skill_name / "SKILL.md"
    if not skill_path.is_file():
        raise PeiWorkflowError(f"SKILL.md bulunamadi: {skill_path}")

    output_file = artifact_dir / "codex-result.md"
    prompt = (
        f"Your PEI plugin skill files live at {plugin_root}. Load and follow "
        f"{skill_path} (and any shared contracts/playbooks it references, "
        "such as ../public-equity-investing/SKILL.md and ../../shared/ "
        "files) for analytical method and operating rules. Then, in your "
        "working directory, read instructions.md and pack.json and complete "
        "the task exactly as instructions.md specifies -- instructions.md "
        "governs deliverable format, scope and source-of-truth rules; "
        "SKILL.md governs how to do the analysis. Use web search for news, "
        "events and commentary the pack does not contain."
    )

    model, effort = SKILL_MODEL_CONFIG.get(skill_name, CODEX_MODEL_DEFAULT)

    # shell=True gerekli: codex Windows'ta npm .cmd sarmalayicisi olarak
    # kurulu, shell=False CreateProcess PATHEXT'i cozemiyor (FileNotFoundError).
    # Prompt argv yerine stdin'den verilir -- cmd.exe'nin &, %, ^ gibi ozel
    # karakterleri argv icinde bozma riskini tamamen ortadan kaldirir.
    # --model/-c model_reasoning_effort GLOBAL bayraklar, "exec"ten ONCE
    # gelmeli (--search ile ayni yer) -- exec'in kendi --effort'u yok.
    command = [
        "codex", "--search", "-m", model, "-c", f"model_reasoning_effort={effort}",
        "exec", "-C", str(artifact_dir), "--add-dir", str(plugin_root),
        "-s", "read-only", "-o", str(output_file), "-",
    ]
    try:
        completed = runner(
            command, cwd=repo_root, input=prompt, text=True, capture_output=True,
            encoding="utf-8", timeout=timeout, shell=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PeiWorkflowError(f"codex CLI calistirilamadi: {exc}") from exc
    if completed.returncode != 0:
        raise PeiWorkflowError(
            f"codex CLI basarisiz (exit {completed.returncode}): "
            f"{(completed.stderr or completed.stdout).strip()[:1000]}"
        )
    if not output_file.is_file() or not output_file.read_text(encoding="utf-8").strip():
        raise PeiWorkflowError("codex bir sonuc dosyasi uretmedi")

    return attach_result(run_id, output_file, repo_root=repo_root, work_item_id=work_item_id)


AGY_MODEL = "gemini-3.6-flash-medium"
# Windows komut satiri sinirinin (~32767 kar) altinda kalmak icin guvenli tavan.
AGY_MAX_INLINE_CHARS = 24000


# "Akilli" tipografi karakterleri (en/em dash, kivrik tirnak) Windows'ta
# subprocess.run'un agy.exe'ye komut satiri argumani olarak aktardigi
# metinde kayboluyor -- Turkce aksanli harfler (ç, ş, ğ, ı, ö, ü) etkilenmiyor,
# yalniz bu belirli noktalama kumesi. Kaynak dosyanin kendisi dogru UTF-8;
# sorun agy'ye giden argv'de. Guvenli ASCII esdegerine indirgeniyor --
# anlam kaybolmaz, yalniz tipografi.
_AGY_CLI_UNSAFE_CHARS = {
    "–": "-", "—": "--", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...",
    "±": "+/-", "×": "x", "°": " derece", "→": "->", "≈": "~",
}


_TURKISH_SAFE_CHARS = set("çÇşŞğĞıİöÖüÜ")


def _sanitize_for_agy_cli(text: str) -> str:
    for bad, good in _AGY_CLI_UNSAFE_CHARS.items():
        text = text.replace(bad, good)
    # Bilinen listenin disinda kalan, ASCII olmayan ve Turkce de olmayan her
    # karakter icin genel bir yedek: aksanli Latin harflerini NFKD ile temel
    # harfe indirger (é -> e), gercekten karsiligi olmayanlari (emoji vb.) "?"
    # ile degistirir. Boylece bilmedigimiz baska bir karakter de argv'de
    # sessizce bozulmaz.
    out = []
    for ch in text:
        if ord(ch) < 128 or ch in _TURKISH_SAFE_CHARS:
            out.append(ch)
            continue
        base = "".join(
            c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)
        )
        out.append(base if base and ord(base[0]) < 128 else "?")
    return "".join(out)


def call_agy_structured(
    repo_root: Path,
    *,
    task: str,
    result_text: str,
    schema_filename: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """agy (Gemini CLI) ile semaya zorlanmis genel amacli cikarim cagrisi.

    Regex/tablo ayrıştırma yerine gercek bir LLM cagrisi -- ChatGPT'nin cevabi
    tablo olsun ya da duzyazi olsun calisir. `--json-schema` ile agy'nin kendi
    strict semasi zorlanir; sonuc `structured_output` alanindan okunur
    (`response` alani agy'nin kendi onarim denemelerini de icerebilir, guvenilmez).
    """
    result_text = _sanitize_for_agy_cli(result_text)
    if len(result_text) > AGY_MAX_INLINE_CHARS:
        raise PeiWorkflowError(
            f"Sonuc metni cok uzun ({len(result_text)} karakter, sinir "
            f"{AGY_MAX_INLINE_CHARS}). agy komut satiri sinirini asiyor; "
            "sonucu bolup ayri ayri isleyin."
        )

    schema_path = repo_root / "schemas" / schema_filename
    if not schema_path.is_file():
        raise PeiWorkflowError(f"extraction semasi bulunamadi: {schema_path}")

    prompt = (
        f"{task} Yalniz metinde acikca yazan bilgiyi cikar, yorum ekleme; "
        "bir alan metinde yoksa null birak, uydurma.\n\n---\n" + result_text
    )

    try:
        completed = runner(
            [
                "agy", "--model", AGY_MODEL, "--output-format", "json",
                "--json-schema", str(schema_path), f"--print={prompt}",
            ],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PeiWorkflowError(f"agy CLI calistirilamadi: {exc}") from exc

    if completed.returncode != 0:
        raise PeiWorkflowError(
            f"agy CLI basarisiz (exit {completed.returncode}): "
            f"{(completed.stderr or completed.stdout).strip()[:500]}"
        )

    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PeiWorkflowError(f"agy ciktisi JSON degil: {exc}") from exc

    if parsed.get("status") != "SUCCESS":
        raise PeiWorkflowError(f"agy hata dondurdu: {parsed.get('error') or parsed}")

    structured = parsed.get("structured_output")
    if not isinstance(structured, dict):
        raise PeiWorkflowError("agy structured_output beklenen sekilde degil")

    return structured


def extract_candidates_via_agy(
    repo_root: Path,
    result_text: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, Any]]:
    """Idea-generation serbest metnini agy ile aday listesine cikarir."""
    structured = call_agy_structured(
        repo_root,
        task=(
            "Asagidaki metin bir idea-generation hisse taramasi ciktisidir. "
            "Icindeki HER aday sirket icin semaya uygun JSON uret."
        ),
        result_text=result_text,
        schema_filename="pei-idea-screen-extraction.schema.json",
        runner=runner,
    )
    if not isinstance(structured.get("candidates"), list):
        raise PeiWorkflowError("agy structured_output beklenen sekilde degil (candidates yok)")
    return structured["candidates"]


# B kokenli bir aday, hicbir zaman A'ya terfi etmeden bu "karar katmani"
# skill'lerine gecemez -- comps/earnings-preview/scenario gibi arastirma
# adimlarinin kendi "next_route" onerisine korlemene guvenmek, idea-
# generation'in B siniflandirmasini dolanmis olurdu (bkz. ADBE ornegi:
# comps "pitch dusunulebilir" dedi diye otomatik pitch'e gecmek).
GATED_DECISION_WORKFLOWS = {"pitch", "portfolio_risk_management", "memo_builder"}
# Terfi kosulu saglanmadiginda (unresolved/indeterminate) B, insanla
# beklemek yerine otomatik olarak izleme hattina duser.
PROMOTION_FALLBACK_WORKFLOW = "thesis_tracker"


def evaluate_promotion(
    repo_root: Path,
    *,
    b_reason_text: str,
    evidence_text: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """B->A terfi kapisini insansiz degerlendirir (agy, Gemini flash).

    Workflow'un kendi "next_route" onerisine (ör. "pitch dusunulebilir")
    guvenmek yerine, idea-generation'in B'ye sebep olan orijinal gerekcesini
    (b_reason_text) yeni adimin urettigi somut kanitla (evidence_text)
    karsilastirip resolved/unresolved/indeterminate karari verdirir. Workflow
    kendi kendini "cozuldu" ilan etmez -- bu ayri, kucuk ve ucuz bir agy
    cagrisidir (web aramasi yok, Sol/Terra degil).
    """
    combined = (
        "=== B siniflandirmasinin orijinal gerekcesi (idea-generation) ===\n"
        + b_reason_text
        + "\n\n=== Yeni workflow'un urettigi kanit ===\n"
        + evidence_text
    )
    return call_agy_structured(
        repo_root,
        task=(
            "Asagida iki blok var: once bir hissenin neden 'B -- watchlist' "
            "kovasina dustugunun orijinal gerekcesi, sonra o gerekceyi "
            "kapatmak icin calistirilan bir arastirma adiminin urettigi "
            "kanit. GOREV: orijinal B gerekcesindeki engel/soru, ikinci "
            "bloktaki somut kanitla gercekten kapandi mi? Yalniz ikinci "
            "bloktaki metinde acikca yazan kanita dayan, yorum katma ya da "
            "kendi gorusunu uydurma. Kanit net ve olumluysa 'resolved', "
            "engel hala gecerliyse 'unresolved', kanit yetersiz/belirsizse "
            "'indeterminate' don. confidence 0-1 arasi bir sayi olsun."
        ),
        result_text=combined,
        schema_filename="pei-promotion-evaluation-extraction.schema.json",
        runner=runner,
    )


# Her workflow tipinin docs/pei-workflow.md SS3'te tanimli, farkli "Kaydet"
# alanlari var. Skill'in kendi kapali sozlugune sahip oldugu yerlerde semadaki
# enum bunu yansitir; serbest metin alanlar duzyazi kalir.
WORKFLOW_EXTRACTION = {
    "tearsheet": {
        "schema": "pei-tearsheet-extraction.schema.json",
        "task": (
            "Asagidaki metin bir company-tearsheet ciktisidir. Tearsheet'in "
            "kendi sozlesmesi geregi HUKUM icermez (add/trim/watch gibi bir "
            "pozisyon aksiyonu yazma). Yalniz onerilen sonraki adimi ve veri "
            "bosluklarini semaya uygun JSON olarak cikar."
        ),
    },
    "earnings_preview": {
        "schema": "pei-earnings-preview-extraction.schema.json",
        "task": (
            "Asagidaki metin bir earnings-preview ciktisidir. Beklenti "
            "cubugunu (metrik + esik), 3-6 hisse-hareket ettirici KPI'yi, "
            "pozisyon aksiyonunu, call-question falsifier'larini ve onerilen "
            "sonraki adimi (next_route) semaya uygun JSON olarak cikar. "
            "position_action alani icin YALNIZ su degerlerden birini kullan: "
            "add, press, hold, trim, exit, hedge, watchlist, wait_for_proof "
            "-- metinde acikca yoksa null."
        ),
    },
    "comps": {
        "schema": "pei-comps-extraction.schema.json",
        "task": (
            "Asagidaki metin bir comps-valuation ciktisidir. Fiyatin ima "
            "ettigi beklentiyi, yukselisin kaynak dagilimini ve hangi "
            "carpanin varsayildigini semaya uygun JSON olarak cikar."
        ),
    },
    "pitch": {
        "schema": "pei-pitch-extraction.schema.json",
        "task": (
            "Asagidaki metin bir long-short-pitch ciktisidir. "
            "Actionability hukmunu, variant perception'i, "
            "what-must-be-true listesini, kill criteria'yi ve katalizoru "
            "(varsa tarihiyle) semaya uygun JSON olarak cikar. "
            "actionability alani icin YALNIZ su degerlerden birini kullan: "
            "actionable_candidate, watchlist, pass_for_now, red_team_only "
            "-- metinde acikca yoksa null."
        ),
    },
    "scenario": {
        "schema": "pei-scenario-extraction.schema.json",
        "task": (
            "Asagidaki metin bir scenario-sensitivity-generator ciktisidir. "
            "Once kirilan surucuyu (primary driver), skew etiketini, "
            "PM aksiyonunu ve o aksiyona bagli sayisal/tarihli esigi, "
            "goruşu degistirecek kaniti ve onerilen sonraki adimi semaya "
            "uygun JSON olarak cikar. Yalniz metinde acikca yazan bilgiyi "
            "cikar, bir alan metinde yoksa null birak, uydurma."
        ),
    },
    "initiating_coverage": {
        "schema": "pei-initiating-coverage-extraction.schema.json",
        "task": (
            "Asagidaki metin bir initiating-coverage ciktisidir. Arastirma "
            "gorusunu, hedef fiyati, cari fiyati, yukselis yuzdesini, "
            "underwriting durumunu (ör. preliminary initiation underwrite, "
            "watchlist initiation, full initiation), kanit guvenini, tez "
            "sutunlarini (thesis_pillars), tezi curutecek kanitlari "
            "(kill_criteria) ve onerilen sonraki adimi semaya uygun JSON "
            "olarak cikar. Yalniz metinde acikca yazan bilgiyi cikar, bir "
            "alan metinde yoksa null/bos liste birak, uydurma."
        ),
    },
}


WORKFLOW_MAP = {
    "long-short-pitch": "pitch",
    "pitch": "pitch",
    "earnings-preview": "earnings_preview",
    "preview": "earnings_preview",
    "earnings-deep-dive": "earnings_deep_dive",
    "deep-dive": "earnings_deep_dive",
    "deepdive": "earnings_deep_dive",
    "comps-valuation": "comps",
    "comps": "comps",
    "company-tearsheet": "tearsheet",
    "tearsheet": "tearsheet",
    "thesis-tracker": "thesis_tracker",
    "scenario-sensitivity-generator": "scenario",
    "scenario-sensitivity": "scenario",
    "initiating-coverage": "initiating_coverage",
    "initiating_coverage": "initiating_coverage",
    "initiation": "initiating_coverage",
}


def generate_draft_events(
    repo_root: Path,
    run_id: str,
    work_item_id: str | None = None,
) -> dict[str, Any]:
    events = read_events(repo_root)
    projection = project(events)
    catalog = load_catalog(repo_root)["workflows"]

    # Locate result artifact
    result_path: Path | None = None
    target_ticker: str | None = None
    target_workflow: str = "idea"
    requested_workflow: str | None = None

    if work_item_id:
        work_item = projection["work_items"].get(work_item_id)
        if work_item:
            target_ticker = work_item["ticker"]
            target_workflow = work_item["workflow"]
            requested_workflow = work_item.get("requested_workflow", target_workflow)
            target_dir = safe_repo_path(repo_root, work_item["artifact_dir"])
            result_path = target_dir / "result.md"
    else:
        run = projection["runs"].get(run_id)
        if run and run.get("artifact_dir"):
            target_dir = safe_repo_path(repo_root, run["artifact_dir"])
            result_path = target_dir / "result.md"

    # Also check dashboard scratch
    scratch_key = work_item_id or run_id
    scratch_pasted = repo_root / "data" / "pei-workflow" / "dashboard-scratch" / scratch_key / "pasted-result.md"
    if scratch_pasted.is_file():
        result_path = scratch_pasted

    if not result_path or not result_path.is_file():
        raise PeiWorkflowError("Sonuç dosyası bulunamadı. Lütfen önce 'Kaydet ve Bağla' ile sonucu kaydedin.")

    result_text = result_path.read_text(encoding="utf-8")
    result_artifact = _artifact("result", repo_root, result_path)

    draft_events: list[dict[str, Any]] = []
    review_date = (date.today() + timedelta(days=7)).isoformat()

    if target_workflow == "idea":
        # Candidate screen run output -- agy (Gemini CLI) ile semaya
        # zorlanmis gercek LLM cikarimi. Regex/tablo ayristirma degil.
        candidates = extract_candidates_via_agy(repo_root, result_text)
        for c in candidates:
            raw_ticker = str(c.get("ticker", "")).strip().upper()
            if not raw_ticker:
                continue

            bucket = c.get("bucket") or "B"
            suggested = c.get("suggested_workflow") or ""

            # Map to catalog workflow -- deterministik, LLM'e birakilmaz.
            mapped_workflow: str | None = None
            route_status = "unsupported" if suggested else "not_requested"
            for key, val in WORKFLOW_MAP.items():
                if key in suggested.lower():
                    if val in catalog:
                        mapped_workflow = val
                        route_status = "supported"
                        break

            payload: dict[str, Any] = {
                "bucket": bucket,
                "setup": c.get("setup") or "",
                "variant_wedge": c.get("variant_wedge") or "",
                "first_rejection": c.get("first_rejection") or "",
                "suggested_workflow": suggested or None,
                "mapped_workflow": mapped_workflow,
                "route_status": route_status,
            }

            if bucket == "B":
                payload["manual_review_date"] = c.get("manual_review_date") or review_date

            draft_events.append(make_event(
                event_id=_event_id(f"SCREEN-{raw_ticker}"),
                event_type="candidate_screened",
                run_id=run_id,
                ticker=raw_ticker,
                source_artifacts=[result_artifact],
                payload=payload,
                recorded_at=utc_now(),
            ))
    else:
        # Single workflow event (e.g. tearsheet, preview, pitch)
        source_artifacts = [result_artifact]
        if target_dir and target_dir.is_dir():
            pack_file = target_dir / "pack.json"
            if pack_file.is_file():
                source_artifacts.append(_artifact("pack", repo_root, pack_file))
            inst_file = target_dir / "instructions.md"
            if inst_file.is_file():
                source_artifacts.append(_artifact("instructions", repo_root, inst_file))

        payload: dict[str, Any] = {"workflow": target_workflow}
        if work_item_id:
            payload["work_item_id"] = work_item_id

        extraction = WORKFLOW_EXTRACTION.get(target_workflow)
        if extraction:
            structured = call_agy_structured(
                repo_root,
                task=extraction["task"],
                result_text=result_text,
                schema_filename=extraction["schema"],
            )
            payload.update(structured)
        else:
            # Katalogda tanimli olmayan/henuz semasi olmayan bir workflow --
            # eskisi gibi ChatGPT'nin kendi yazdigi ```json``` blogu varsa onu
            # al, yoksa payload yalniz workflow/work_item_id ile kalir.
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", result_text, re.DOTALL)
            if json_match:
                try:
                    parsed_json = json.loads(json_match.group(1))
                    if isinstance(parsed_json, dict):
                        payload.update(parsed_json)
                except json.JSONDecodeError:
                    pass

        # Rotalar bir zincir degil, her isim icin ayri ayri sorulan bagimsiz
        # kapilardir (docs/pei-akis-diyagram.md Faz 1) -- idea-generation'in
        # aylar once verdigi statik hedef (requested_workflow) degil, BU
        # adimin kendi guncel next_route/suggested_workflow onerisi esas
        # alinir; sadece o katalogda karsiliksizsa eski statik hedefe
        # dusulur. target_workflow burada hazirlanan ADIM (ör. tearsheet);
        # asagidaki next_workflow farkliysa bu sadece bir on kosuldu, zincir
        # burada durmamali.
        fresh_route = payload.get("next_route") or payload.get("suggested_workflow")
        mapped_next: str | None = None
        route_unsupported = False
        if fresh_route:
            for key, val in WORKFLOW_MAP.items():
                if key in fresh_route.lower() and val in catalog and val != target_workflow:
                    mapped_next = val
                    break
            else:
                route_unsupported = True
        promotion_events: list[dict[str, Any]] = []
        if mapped_next:
            payload["next_workflow"] = mapped_next
            # B kokenli bir aday, hicbir zaman A'ya terfi etmeden karar
            # katmani skill'lerine (pitch/portfolio-risk/memo-builder)
            # gecemez -- bu adimin kendi "pitch dusunulebilir" gibi bir
            # onerisine korlemene guvenmek yerine, agy'ye (insan degil)
            # orijinal B gerekcesiyle bu adimin urettigi kaniti karsilastirtip
            # gercekten resolved mi diye sorulur. Degilse otomatik olarak
            # thesis_tracker'a duser, insan beklemez.
            candidate = (
                projection["candidates"].get(f"{run_id}:{target_ticker}")
                if target_ticker else None
            )
            if candidate and candidate.get("bucket") == "B" and mapped_next in GATED_DECISION_WORKFLOWS:
                b_reason_text = "\n".join(filter(None, [
                    f"Setup: {candidate.get('setup')}",
                    f"Variant wedge (ne olursa yatirilabilir hale gelir): {candidate.get('variant_wedge')}",
                    f"First rejection: {candidate.get('first_rejection')}",
                ]))
                evaluation = evaluate_promotion(
                    repo_root, b_reason_text=b_reason_text, evidence_text=result_text,
                )
                payload["promotion_evaluation"] = evaluation
                if evaluation.get("resolution_status") == "resolved":
                    promotion_events.append(make_event(
                        event_id=_event_id(f"PROMOTE-{target_ticker}"),
                        event_type="source_interpretation_corrected",
                        run_id=run_id, ticker=target_ticker,
                        source_artifacts=source_artifacts,
                        payload={
                            "promoted_to": "A",
                            "mapped_workflow": mapped_next,
                            "resolution_status": "resolved",
                            "confidence": evaluation.get("confidence"),
                            "reason": evaluation.get("reason")
                                      or f"B->A promotion gate passed for {mapped_next}",
                        },
                        recorded_at=utc_now(),
                    ))
                else:
                    payload["next_workflow"] = PROMOTION_FALLBACK_WORKFLOW
        elif not route_unsupported and requested_workflow and requested_workflow != target_workflow:
            # Bu adim kendi rotasini onermedi (bos/None) -- eski, daha az
            # bilgili hedefe duselim, makul bir varsayilan.
            payload["next_workflow"] = requested_workflow
        # route_unsupported: bu adim acikca bir rota onerdi ama katalogda
        # karsiligi yok (ör. "initiating coverage"). Eski statik hedefe
        # (requested_workflow) SESSIZCE dusulmez -- bu, modelin taze
        # onerisini gormezden gelip uydurma bir esdegerlik kurmak olurdu.
        # candidate_screened'deki route_status="unsupported" ile ayni ilke:
        # katalogda olmayan oneri calistirilmaz, insan kararina birakilir.

        draft_events.append(make_event(
            event_id=_event_id(f"COMPLETE-{target_ticker or 'WORKFLOW'}"),
            event_type="workflow_completed",
            run_id=run_id,
            ticker=target_ticker,
            source_artifacts=source_artifacts,
            payload=payload,
            recorded_at=utc_now(),
        ))
        draft_events.extend(promotion_events)

        if route_unsupported:
            draft_events.append(make_event(
                event_id=_event_id(f"REVIEW-{target_ticker or 'WORKFLOW'}"),
                event_type="manual_review_required",
                run_id=run_id,
                ticker=target_ticker,
                source_artifacts=source_artifacts,
                payload={
                    "review_date": date.today().isoformat(),
                    "reason": f"unsupported route: {fresh_route}",
                },
                recorded_at=utc_now(),
            ))

    return {"events": draft_events}


def prepare_work_item(
    work_item_id: str,
    *,
    repo_root: Path,
    no_refresh: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path:
    item = next((
        value for value in next_items(repo_root)
        if value["work_item_id"] == work_item_id and value["action"] == "prepare"
    ), None)
    if item is None:
        raise PeiWorkflowError(f"work item is not currently ready: {work_item_id}")
    catalog = load_catalog(repo_root)["workflows"]
    step = catalog[item["workflow"]].get("pack_step")
    if not step:
        raise PeiWorkflowError(f"workflow has no pack preparation step: {item['workflow']}")
    work_root = repo_root / "data" / "pei-workflow" / "runs" / item["run_id"] / "work" / work_item_id
    command = [
        sys.executable, str(repo_root / "scripts" / "us_pei_pack.py"),
        "--only", item["ticker"], "--for", step, "--out", str(work_root),
    ]
    if no_refresh:
        command.append("--no-refresh")
    completed = runner(command, cwd=repo_root, text=True, capture_output=True)
    if completed.returncode:
        raise PeiWorkflowError(f"pack preparation failed: {(completed.stderr or completed.stdout).strip()}")
    pack = _locate_single(work_root, "pack.json")
    artifact_dir = pack.parent
    prior_results = []
    for event in read_events(repo_root):
        if event["run_id"] != item["run_id"] or event.get("ticker") != item["ticker"]:
            continue
        if event["event_type"] != "workflow_completed":
            continue
        prior_results.extend(
            artifact for artifact in event.get("source_artifacts", [])
            if artifact.get("role") == "result"
        )
    event = make_event(
        event_id=_event_id("PREPARED"), event_type="workflow_prepared",
        run_id=item["run_id"], ticker=item["ticker"],
        source_artifacts=[
            _artifact("pack", repo_root, pack),
            _artifact("instructions", repo_root, artifact_dir / "instructions.md"),
            *prior_results,
        ],
        payload={
            "workflow": item["workflow"],
            "requested_workflow": item["requested_workflow"],
            "work_item_id": work_item_id,
            "artifact_dir": repo_relative(repo_root, artifact_dir),
            "required_context_artifacts": [artifact["path"] for artifact in prior_results],
            "command": command,
        },
    )
    append_events([approve_system_event(event)], repo_root=repo_root)
    return artifact_dir


def json_pointer(document: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    current = document
    tokens = pointer[1:].split("/") if pointer != "/" else []
    index = 0
    while index < len(tokens):
        token = tokens[index].replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[token]
        elif isinstance(current, list):
            if token.isdigit():
                current = current[int(token)]
            else:
                current = next(item for item in current if item.get("ticker") == token)
        else:
            raise KeyError(pointer)
        index += 1
    return current


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "<":
        return actual < expected
    if operator == "<=":
        return actual <= expected
    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    if operator == ">=":
        return actual >= expected
    if operator == ">":
        return actual > expected
    raise PeiWorkflowError(f"unsupported trigger operator: {operator}")


def evaluate_trigger(trigger: dict[str, Any], *, today: date, document: Any | None) -> tuple[bool, str]:
    kind = trigger["type"]
    if kind == "date_due":
        due = date.fromisoformat(trigger.get("date") or trigger["next_check_date"])
        return today >= due, f"date {today} >= {due}"
    if kind == "event_window":
        event_date = date.fromisoformat(trigger["date"])
        opens = event_date - timedelta(days=int(trigger.get("lead_days", 0)))
        return opens <= today <= event_date, f"event window {opens}..{event_date}"
    if document is None:
        return False, "no current data document"
    try:
        actual = json_pointer(document, trigger["metric_path"])
    except (KeyError, IndexError, StopIteration, TypeError, ValueError):
        return False, f"metric path unavailable: {trigger.get('metric_path')}"
    if kind == "new_filing":
        matched = actual != trigger.get("baseline")
        return matched, f"current={actual!r}, baseline={trigger.get('baseline')!r}"
    if kind == "metric_condition":
        matched = _compare(actual, trigger["operator"], trigger.get("value"))
        return matched, f"{actual!r} {trigger['operator']} {trigger.get('value')!r}"
    raise PeiWorkflowError(f"unsupported trigger type: {kind}")


def check_triggers(
    *,
    repo_root: Path,
    today: date | None = None,
    data_path: Path | None = None,
) -> list[dict[str, Any]]:
    today = today or date.today()
    document = json.loads(data_path.read_text(encoding="utf-8")) if data_path else None
    current = project(read_events(repo_root))
    additions = []
    for candidate in latest_candidates(current).values():
        if candidate["state"] != "waiting":
            continue
        for trigger in candidate.get("triggers", []):
            matched, detail = evaluate_trigger(trigger, today=today, document=document)
            if not matched:
                continue
            workflow = trigger.get("workflow")
            if workflow is None:
                event_type = "manual_review_required"
                payload = {"review_date": today.isoformat(), "reason": detail, "trigger_id": trigger["trigger_id"]}
            else:
                event_type = "trigger_satisfied"
                payload = {"workflow": workflow, "reason": detail, "trigger_id": trigger["trigger_id"]}
            additions.append(approve_system_event(make_event(
                event_id=_event_id("TRIGGER"), event_type=event_type,
                run_id=candidate["run_id"], ticker=candidate["ticker"], payload=payload,
            )))
            break
        else:
            review_date = candidate.get("manual_review_date")
            if review_date and today >= date.fromisoformat(review_date):
                additions.append(approve_system_event(make_event(
                    event_id=_event_id("REVIEW"), event_type="manual_review_required",
                    run_id=candidate["run_id"], ticker=candidate["ticker"],
                    payload={"review_date": review_date, "reason": "scheduled manual review is due"},
                )))
    if additions:
        append_events(additions, repo_root=repo_root)
    return additions


def refresh_trigger_data(
    *,
    repo_root: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path | None:
    projection = project(read_events(repo_root))
    tickers = sorted({
        candidate["ticker"]
        for candidate in latest_candidates(projection).values()
        if candidate["state"] == "waiting"
        and any(trigger.get("type") in {"new_filing", "metric_condition"}
                for trigger in candidate.get("triggers", []))
    })
    if not tickers:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    check_root = repo_root / "data" / "pei-workflow" / "checks" / stamp
    command = [
        sys.executable, str(repo_root / "scripts" / "us_pei_pack.py"),
        "--for", "idea", "--tickers", ",".join(tickers), "--out", str(check_root),
    ]
    completed = runner(command, cwd=repo_root, text=True, capture_output=True)
    if completed.returncode:
        raise PeiWorkflowError(f"trigger refresh failed: {(completed.stderr or completed.stdout).strip()}")
    return _locate_single(check_root, "pack.json")
