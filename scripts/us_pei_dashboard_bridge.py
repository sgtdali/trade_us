from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows konsol kod sayfasi (ör. cp1254) pack/result icindeki bazi Unicode
# karakterleri (≤, →, …) yazamiyor; stdout/stdin'i acikca UTF-8'e zorla.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from adapter.pei_workflow import (  # noqa: E402
    CODEX_MODEL_DEFAULT,
    PeiWorkflowError,
    SKILL_MODEL_CONFIG,
    STEP_TO_SKILL,
    approve_draft,
    attach_result,
    check_triggers,
    generate_draft_events,
    latest_candidates,
    load_catalog,
    next_items,
    prepare_work_item,
    project,
    read_events,
    refresh_trigger_data,
    run_codex_analysis,
    safe_repo_path,
    start_idea,
    validate_draft,
    write_text_atomic,
)
from adapter.pei_record import PeiRecordError  # noqa: E402

from adapter.portfolio import (  # noqa: E402
    PortfolioError,
    delete_position,
    enrich_portfolio,
    load_portfolio,
    upsert_position,
)
from adapter.watchlist import (  # noqa: E402
    WatchlistError,
    delete_watchlist_item,
    enrich_watchlist,
    load_watchlist,
    upsert_watchlist_item,
)

SCRATCH_ROOT = REPO / "data" / "pei-workflow" / "dashboard-scratch"


def _scratch_dir(args: dict) -> Path:
    key = args.get("work_item_id") or args.get("run_id")
    if not key:
        raise PeiWorkflowError("work_item_id or run_id required")
    return SCRATCH_ROOT / key


UNIVERSE_FILE = REPO / "config" / "universes" / "us-live.json"


def cmd_universe(_args: dict) -> dict:
    data = json.loads(UNIVERSE_FILE.read_text(encoding="utf-8"))
    return {"members": data.get("members", [])}


def cmd_status(_args: dict) -> dict:
    events = read_events(REPO)
    state = project(events)
    return {
        "event_count": len(events),
        "last_event_at": state["last_event_at"],
        "candidates": sorted(latest_candidates(state).values(), key=lambda item: item["ticker"]),
        "next": next_items(REPO),
        "runs": sorted(
            state["runs"].values(), key=lambda item: item["last_event_at"] or "", reverse=True,
        ),
    }


def cmd_artifact(args: dict) -> dict:
    path = safe_repo_path(REPO, args["path"])
    if not path.is_file():
        raise PeiWorkflowError(f"artifact not found: {args['path']}")
    return {"content": path.read_text(encoding="utf-8")}


def cmd_prepare(args: dict) -> dict:
    artifact_dir = prepare_work_item(
        args["work_item_id"], repo_root=REPO, no_refresh=bool(args.get("no_refresh", True)),
    )
    return {"artifact_dir": artifact_dir.relative_to(REPO).as_posix()}


def cmd_attach_result(args: dict) -> dict:
    text = args.get("text", "")
    if not text.strip():
        raise PeiWorkflowError("yapistirilan sonuc bos olamaz")
    source = _scratch_dir(args) / "pasted-result.md"
    write_text_atomic(source, text)
    target = attach_result(
        args["run_id"], source, repo_root=REPO, work_item_id=args.get("work_item_id") or None,
    )
    return {"result_path": target.relative_to(REPO).as_posix()}


def cmd_run_codex(args: dict) -> dict:
    target = run_codex_analysis(
        args["run_id"], repo_root=REPO, work_item_id=args.get("work_item_id") or None,
    )
    return {"result_path": target.relative_to(REPO).as_posix()}


def cmd_validate(args: dict) -> dict:
    draft_path = _scratch_dir(args) / "draft.json"
    write_text_atomic(draft_path, args.get("draft", ""))
    report = validate_draft(draft_path, repo_root=REPO)
    write_text_atomic(
        draft_path.parent / "validation.json",
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    )
    return {"report": report}


def cmd_approve(args: dict) -> dict:
    draft_path = _scratch_dir(args) / "draft.json"
    write_text_atomic(draft_path, args.get("draft", ""))
    target = approve_draft(draft_path, repo_root=REPO)
    return {"approved_path": str(target)}


def cmd_events(args: dict) -> dict:
    events = read_events(REPO)
    limit = args.get("limit")
    ordered = list(reversed(events))
    if isinstance(limit, int) and limit > 0:
        ordered = ordered[:limit]
    return {"events": ordered, "total": len(events)}


def cmd_catalog(_args: dict) -> dict:
    catalog = load_catalog(REPO)
    # Panel, her workflow icin hangi skill'in ve codex modelinin/reasoning
    # effort'unun kullanilacagini gostersin diye zenginlestiriliyor -- ayri
    # bir endpoint yerine katalogla ayni yerde, cunku zaten workflow'a gore
    # gruplu.
    for workflow_id, definition in catalog.get("workflows", {}).items():
        skill = STEP_TO_SKILL.get(workflow_id)
        if not skill:
            continue
        model, effort = SKILL_MODEL_CONFIG.get(skill, CODEX_MODEL_DEFAULT)
        definition["skill"] = skill
        definition["codex_model"] = model
        definition["codex_effort"] = effort
    return catalog


THESIS_ROOT = REPO / "data" / "thesis-tracker"


def cmd_thesis(_args: dict) -> dict:
    theses = []
    if THESIS_ROOT.is_dir():
        for ticker_dir in sorted(THESIS_ROOT.iterdir()):
            if not ticker_dir.is_dir():
                continue
            for file in sorted(ticker_dir.glob("*.jsonl")):
                records = [
                    json.loads(line)
                    for line in file.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                if not records:
                    continue
                theses.append({
                    "ticker": ticker_dir.name,
                    "thesis_id": records[0].get("thesis_id", file.stem),
                    "file": file.relative_to(REPO).as_posix(),
                    "records": records,
                })
    return {"theses": theses}


def cmd_start_idea(args: dict) -> dict:
    tickers = args.get("tickers") or []
    if not tickers:
        raise PeiWorkflowError("tickers bos olamaz")
    run_id, artifact_dir = start_idea(
        tickers, repo_root=REPO, no_refresh=bool(args.get("no_refresh", True)),
    )
    return {"run_id": run_id, "artifact_dir": artifact_dir.relative_to(REPO).as_posix()}


def cmd_check_triggers(args: dict) -> dict:
    data_path = None
    if args.get("refresh"):
        data_path = refresh_trigger_data(repo_root=REPO)
    additions = check_triggers(repo_root=REPO, data_path=data_path)
    return {
        "additions": additions,
        "data_path": data_path.relative_to(REPO).as_posix() if data_path else None,
    }


def cmd_generate_draft(args: dict) -> dict:
    run_id = args.get("run_id")
    if not run_id:
        raise PeiWorkflowError("run_id required")
    draft_dict = generate_draft_events(REPO, run_id=run_id, work_item_id=args.get("work_item_id"))
    draft_json = json.dumps(draft_dict, indent=2, ensure_ascii=False)
    draft_path = _scratch_dir(args) / "draft.json"
    write_text_atomic(draft_path, draft_json)
    return {"draft_json": draft_json, "draft": draft_dict}


def cmd_portfolio_get(_args: dict) -> dict:
    return enrich_portfolio(REPO, load_portfolio(REPO))


def cmd_portfolio_update(args: dict) -> dict:
    return upsert_position(REPO, args)


def cmd_portfolio_delete(args: dict) -> dict:
    ticker = args.get("ticker")
    if not ticker:
        raise PortfolioError("ticker is required for delete")
    return delete_position(REPO, ticker)


def cmd_watchlist_get(_args: dict) -> dict:
    return enrich_watchlist(REPO, load_watchlist(REPO))


def cmd_watchlist_update(args: dict) -> dict:
    return upsert_watchlist_item(REPO, args)


def cmd_watchlist_delete(args: dict) -> dict:
    ticker = args.get("ticker")
    if not ticker:
        raise WatchlistError("ticker is required for delete")
    return delete_watchlist_item(REPO, ticker)


COMMANDS = {
    "status": cmd_status,
    "artifact": cmd_artifact,
    "prepare": cmd_prepare,
    "attach-result": cmd_attach_result,
    "run-codex": cmd_run_codex,
    "validate": cmd_validate,
    "approve": cmd_approve,
    "events": cmd_events,
    "catalog": cmd_catalog,
    "thesis": cmd_thesis,
    "start-idea": cmd_start_idea,
    "universe": cmd_universe,
    "check-triggers": cmd_check_triggers,
    "generate-draft": cmd_generate_draft,
    "portfolio-get": cmd_portfolio_get,
    "portfolio-update": cmd_portfolio_update,
    "portfolio-delete": cmd_portfolio_delete,
    "watchlist-get": cmd_watchlist_get,
    "watchlist-update": cmd_watchlist_update,
    "watchlist-delete": cmd_watchlist_delete,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(json.dumps({"error": f"unknown command, expected one of {list(COMMANDS)}"}))
        return 1
    command = sys.argv[1]
    raw = sys.stdin.read()
    try:
        args = json.loads(raw) if raw.strip() else {}
        result = COMMANDS[command](args)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (
        PeiWorkflowError,
        PeiRecordError,
        PortfolioError,
        WatchlistError,
        OSError,
        json.JSONDecodeError,
        KeyError,
    ) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
