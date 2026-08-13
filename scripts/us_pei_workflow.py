from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from adapter.pei_workflow import (
    PeiWorkflowError,
    approve_draft,
    attach_result,
    check_triggers,
    latest_candidates,
    next_items,
    prepare_work_item,
    project,
    read_events,
    refresh_trigger_data,
    start_idea,
    validate_draft,
    write_text_atomic,
)


def _status_payload() -> dict:
    events = read_events(REPO)
    state = project(events)
    return {
        "event_count": len(events),
        "last_event_at": state["last_event_at"],
        "runs": sorted(state["runs"].values(), key=lambda item: item["run_id"]),
        "candidates": sorted(
            latest_candidates(state).values(), key=lambda item: item["ticker"],
        ),
        "next": next_items(REPO),
    }


def _print_status(payload: dict) -> None:
    print(f"olay: {payload['event_count']}  son: {payload['last_event_at'] or '-'}")
    if not payload["candidates"]:
        print("aday kaydi yok")
        return
    print("\nTicker  Bucket  Durum          Siradaki")
    print("------  ------  -------------  --------------------")
    effective = {item["ticker"]: item for item in payload["next"]}
    for item in payload["candidates"]:
        route = item.get("next_workflow") or "-"
        next_item = effective.get(item["ticker"])
        if next_item and next_item["workflow"] != next_item["requested_workflow"]:
            route = f"{next_item['workflow']} -> {next_item['requested_workflow']}"
        print(
            f"{item['ticker']:<6}  {str(item['bucket'] or '-'):<6}  "
            f"{item['state']:<13}  {route}"
        )
    attention = [
        item for item in payload["candidates"]
        if item["state"] in {"blocked", "waiting"} and item.get("status_reason")
    ]
    if attention:
        print("\nBekleyen / blokeli:")
        for item in attention:
            print(f"- {item['ticker']}: {item['status_reason']}")


def _print_next(items: list[dict]) -> None:
    if not items:
        print("hazir is yok")
        return
    for index, item in enumerate(items, 1):
        print(f"{index}. {item['ticker']} — {item['workflow']}")
        print(f"   neden: {item['reason']}")
        if item["action"] == "attach_result":
            print(f"   dosyalar: {item['artifact_dir']}/pack.json + instructions.md")
            for artifact in item.get("required_context_artifacts", []):
                print(f"             {artifact}")
            print("   sonraki: ChatGPT cevabini bu oturuma getir; Codex sonucu work item'a baglar")
        else:
            print(f"   komut: python scripts/us_pei_workflow.py prepare {item['work_item_id']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Session-independent PEI workflow orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start-idea")
    start_parser.add_argument("--tickers", required=True)
    start_parser.add_argument("--no-refresh", action="store_true")

    attach_parser = subparsers.add_parser("attach-result")
    attach_parser.add_argument("--run-id", required=True)
    attach_parser.add_argument("--file", type=Path, required=True)
    attach_parser.add_argument("--work-item")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--draft", type=Path, required=True)
    validate_parser.add_argument("--output", type=Path)

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--draft", type=Path, required=True)
    approve_parser.add_argument("--allow-review", action="store_true")
    approve_parser.add_argument("--note")
    approve_parser.add_argument("--legacy", action="store_true")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true")

    next_parser = subparsers.add_parser("next")
    next_parser.add_argument("--json", action="store_true")

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("work_item_id")
    prepare_parser.add_argument("--no-refresh", action="store_true")

    trigger_parser = subparsers.add_parser("check-triggers")
    trigger_parser.add_argument("--refresh", action="store_true")
    trigger_parser.add_argument("--data", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "start-idea":
            run_id, artifact_dir = start_idea(
                args.tickers.split(","), repo_root=REPO, no_refresh=args.no_refresh,
            )
            print(f"run_id: {run_id}")
            print(f"artefaktlar: {artifact_dir.relative_to(REPO)}")
        elif args.command == "attach-result":
            target = attach_result(
                args.run_id, args.file, repo_root=REPO, work_item_id=args.work_item,
            )
            print(f"result: {target.relative_to(REPO)}")
            print("siradaki: Codex ile workflow event taslagi cikar, validate ve approve et")
        elif args.command == "validate":
            report = validate_draft(args.draft, repo_root=REPO)
            output = args.output or args.draft.parent / "validation.json"
            write_text_atomic(output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print(f"validation: {output}")
            return 1 if report["status"] == "rejected" else 0
        elif args.command == "approve":
            target = approve_draft(
                args.draft, repo_root=REPO, allow_review=args.allow_review,
                note=args.note,
                approval_mode="legacy_import" if args.legacy else "explicit_user_confirmation",
            )
            print(f"approved: {target.relative_to(REPO)}")
        elif args.command == "status":
            payload = _status_payload()
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else "", end="")
            if not args.json:
                _print_status(payload)
        elif args.command == "next":
            items = next_items(REPO)
            if args.json:
                print(json.dumps(items, ensure_ascii=False, indent=2))
            else:
                _print_next(items)
        elif args.command == "prepare":
            target = prepare_work_item(
                args.work_item_id, repo_root=REPO, no_refresh=args.no_refresh,
            )
            print(f"hazir: {target.relative_to(REPO)}")
            print("ChatGPT'ye pack.json, instructions.md ve listelenen context artefaktlarini ver")
        elif args.command == "check-triggers":
            data_path = args.data
            if args.refresh:
                data_path = refresh_trigger_data(repo_root=REPO) or data_path
            additions = check_triggers(repo_root=REPO, data_path=data_path)
            print(f"tetiklenen: {len(additions)}")
            if data_path:
                print(f"veri: {data_path.relative_to(REPO) if data_path.is_relative_to(REPO) else data_path}")
        return 0
    except (PeiWorkflowError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"workflow error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
