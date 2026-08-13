from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from adapter.pei_record import (
    PeiRecordError,
    approve_draft,
    validate_draft,
    write_validation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and explicitly approve Codex-extracted PEI thesis records."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--draft", type=Path, required=True)
    validate_parser.add_argument("--output", type=Path)
    validate_parser.add_argument("--tracker-root", type=Path, default=Path("data/thesis-tracker"))

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--draft", type=Path, required=True)
    approve_parser.add_argument("--tracker-root", type=Path, default=Path("data/thesis-tracker"))
    approve_parser.add_argument("--allow-review", action="store_true")
    approve_parser.add_argument("--note")

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    tracker_root = args.tracker_root
    if not tracker_root.is_absolute():
        tracker_root = repo_root / tracker_root

    if args.command == "validate":
        report = validate_draft(
            args.draft, repo_root=repo_root, tracker_root=tracker_root,
        )
        output = args.output or args.draft.parent / "validation.json"
        write_validation_report(report, output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"validation: {output}")
        return 1 if report["status"] == "rejected" else 0

    try:
        target = approve_draft(
            args.draft, repo_root=repo_root, tracker_root=tracker_root,
            allow_review=args.allow_review, approval_note=args.note,
        )
    except PeiRecordError as exc:
        print(f"approval refused: {exc}")
        return 1
    print(f"approved: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
