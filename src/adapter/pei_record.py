from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import jsonschema


_THESIS_SLUG = re.compile(r"^[A-Z0-9.-]+-[0-9]{8}-[a-z0-9-]+$")


class PeiRecordError(RuntimeError):
    pass


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_repo_path(repo_root: Path, relative: str) -> Path:
    supplied = Path(relative)
    if supplied.is_absolute() or ".." in supplied.parts:
        raise PeiRecordError(f"source path must be repo-relative: {relative!r}")
    resolved = (repo_root / supplied).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise PeiRecordError(f"source path escapes repository: {relative!r}") from exc
    return resolved


def _load_schema(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "schemas" / "pei-thesis-record.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_errors(draft: dict[str, Any], repo_root: Path) -> list[str]:
    schema = _load_schema(repo_root)
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker(),
    )
    errors = []
    for error in sorted(validator.iter_errors(draft), key=lambda item: list(item.absolute_path)):
        location = "/" + "/".join(str(part) for part in error.absolute_path)
        errors.append(f"schema {location}: {error.message}")
    return errors


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def _json_pointer(document: Any, pointer: str) -> Any:
    current = document
    if pointer == "":
        return current
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise KeyError(pointer)
    return current


def _same_value(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual is expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        try:
            return Decimal(str(actual)) == Decimal(str(expected))
        except InvalidOperation:
            return False
    return actual == expected


def _evidence_items(draft: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    items: list[tuple[str, dict[str, Any]]] = []
    decision = draft.get("decision") or {}
    for evidence_index, evidence in enumerate(decision.get("evidence") or []):
        items.append((f"decision/evidence/{evidence_index}", evidence))
    for name, field in (draft.get("narrative") or {}).items():
        if not isinstance(field, dict):
            continue
        for evidence_index, evidence in enumerate(field.get("evidence") or []):
            items.append((f"narrative/{name}/evidence/{evidence_index}", evidence))
    override = decision.get("status_override_rationale")
    if isinstance(override, dict):
        for evidence_index, evidence in enumerate(override.get("evidence") or []):
            items.append((f"decision/status_override_rationale/evidence/{evidence_index}", evidence))
    for index, rule in enumerate(draft.get("rules") or []):
        for evidence_index, evidence in enumerate(rule.get("evidence") or []):
            items.append((f"rules/{index}/evidence/{evidence_index}", evidence))
    for index, catalyst in enumerate(draft.get("catalysts") or []):
        evidence = catalyst.get("evidence")
        if isinstance(evidence, dict):
            items.append((f"catalysts/{index}/evidence", evidence))
    for index, finding in enumerate(draft.get("unstructured_findings") or []):
        evidence = finding.get("evidence")
        if isinstance(evidence, dict):
            items.append((f"unstructured_findings/{index}/evidence", evidence))
    for index, pillar in enumerate(draft.get("thesis_pillars") or []):
        claim = pillar.get("claim") if isinstance(pillar, dict) else None
        if isinstance(claim, dict):
            for evidence_index, evidence in enumerate(claim.get("evidence") or []):
                items.append((f"thesis_pillars/{index}/claim/evidence/{evidence_index}", evidence))
        proof = pillar.get("next_proof_point") if isinstance(pillar, dict) else None
        evidence = proof.get("evidence") if isinstance(proof, dict) else None
        if isinstance(evidence, dict):
            items.append((f"thesis_pillars/{index}/next_proof_point/evidence", evidence))
    for index, ledger_item in enumerate(draft.get("evidence_ledger") or []):
        evidence = ledger_item.get("evidence") if isinstance(ledger_item, dict) else None
        if isinstance(evidence, dict):
            items.append((f"evidence_ledger/{index}/evidence", evidence))
    for index, observation in enumerate(draft.get("kpi_observations") or []):
        evidence = observation.get("evidence") if isinstance(observation, dict) else None
        if isinstance(evidence, dict):
            items.append((f"kpi_observations/{index}/evidence", evidence))
        proof = observation.get("next_proof_point") if isinstance(observation, dict) else None
        evidence = proof.get("evidence") if isinstance(proof, dict) else None
        if isinstance(evidence, dict):
            items.append((f"kpi_observations/{index}/next_proof_point/evidence", evidence))
    for index, question in enumerate(draft.get("open_questions") or []):
        evidence = question.get("evidence") if isinstance(question, dict) else None
        if isinstance(evidence, dict):
            items.append((f"open_questions/{index}/evidence", evidence))
    return items


def _tracker_file(tracker_root: Path, ticker: str, thesis_id: str) -> Path:
    return tracker_root / ticker / f"{thesis_id}.jsonl"


def _item_ids(items: list[Any], key: str) -> list[str]:
    return [
        item[key] for item in items
        if isinstance(item, dict) and isinstance(item.get(key), str)
    ]


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _existing_records(ticker_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not ticker_dir.exists():
        return records
    for path in sorted(ticker_dir.glob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PeiRecordError(f"invalid tracker JSON at {path}:{line_number}") from exc
            records.append(record)
    return records


def validate_draft(
    draft_path: Path,
    *,
    repo_root: Path | None = None,
    tracker_root: Path | None = None,
) -> dict[str, Any]:
    repo_root = (repo_root or _repo_root()).resolve()
    tracker_root = (tracker_root or repo_root / "data" / "thesis-tracker").resolve()
    errors: list[str] = []
    warnings: list[str] = []

    try:
        payload = draft_path.read_bytes()
        draft = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "status": "rejected", "draft": str(draft_path),
            "draft_sha256": None, "errors": [f"draft cannot be read: {exc}"],
            "warnings": [], "checked_at": _utc_now(),
        }
    if not isinstance(draft, dict):
        return {
            "status": "rejected", "draft": str(draft_path),
            "draft_sha256": _sha256_bytes(payload),
            "errors": ["draft root must be an object"], "warnings": [],
            "checked_at": _utc_now(),
        }

    errors.extend(_schema_errors(draft, repo_root))
    ticker = draft.get("ticker")
    thesis_id = draft.get("thesis_id")
    if isinstance(ticker, str) and isinstance(thesis_id, str):
        if not _THESIS_SLUG.fullmatch(thesis_id) or not thesis_id.startswith(f"{ticker}-"):
            errors.append("thesis_id must begin with ticker and include YYYYMMDD plus a slug")

    artifacts: dict[str, dict[str, Any]] = {}
    role_counts: dict[str, int] = {}
    artifact_bodies: dict[str, str] = {}
    for index, artifact in enumerate(draft.get("source_artifacts") or []):
        if not isinstance(artifact, dict):
            continue
        role = artifact.get("role")
        relative = artifact.get("path")
        digest = artifact.get("sha256")
        if isinstance(role, str):
            role_counts[role] = role_counts.get(role, 0) + 1
        if not isinstance(relative, str):
            continue
        if relative in artifacts:
            errors.append(f"duplicate source artifact path: {relative}")
            continue
        artifacts[relative] = artifact
        try:
            path = _safe_repo_path(repo_root, relative)
        except PeiRecordError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"source artifact does not exist: {relative}")
            continue
        actual_digest = _sha256_path(path)
        if isinstance(digest, str) and actual_digest != digest:
            errors.append(f"source artifact hash mismatch: {relative}")
        try:
            artifact_bodies[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"source artifact is not UTF-8 text: {relative}")

    if role_counts.get("result") != 1:
        errors.append("exactly one source artifact must have role=result")
    if role_counts.get("pack") != 1:
        errors.append("exactly one source artifact must have role=pack")

    result_paths = {
        path for path, artifact in artifacts.items() if artifact.get("role") == "result"
    }
    for location, evidence in _evidence_items(draft):
        source_path = evidence.get("source_path")
        quote = evidence.get("quote")
        if source_path not in result_paths:
            errors.append(f"{location}: evidence must cite the primary result artifact")
            continue
        body = artifact_bodies.get(source_path, "")
        if isinstance(quote, str) and _normalized_text(quote) not in _normalized_text(body):
            errors.append(f"{location}: quote not found in result artifact")

    pack_paths = [
        path for path, artifact in artifacts.items() if artifact.get("role") == "pack"
    ]
    pack_document: Any = None
    if len(pack_paths) == 1 and pack_paths[0] in artifact_bodies:
        try:
            pack_document = json.loads(artifact_bodies[pack_paths[0]])
        except json.JSONDecodeError:
            errors.append("pack source artifact is not valid JSON")
    pack_checks = draft.get("pack_checks") or []
    if not pack_checks:
        warnings.append("no pack_checks supplied; pack-sourced numbers were not cross-checked")
    elif pack_document is not None:
        for index, check in enumerate(pack_checks):
            if not isinstance(check, dict):
                continue
            pointer = check.get("json_pointer")
            if not isinstance(pointer, str):
                continue
            try:
                actual = _json_pointer(pack_document, pointer)
            except (KeyError, IndexError, ValueError):
                errors.append(f"pack_checks/{index}: JSON Pointer does not resolve: {pointer}")
                continue
            if not _same_value(actual, check.get("expected_value")):
                errors.append(
                    f"pack_checks/{index}: expected {check.get('expected_value')!r} "
                    f"but pack has {actual!r} at {pointer}"
                )

    existing_records: list[dict[str, Any]] = []
    if isinstance(ticker, str):
        try:
            existing_records = _existing_records(tracker_root / ticker)
        except PeiRecordError as exc:
            errors.append(str(exc))
    prior_thesis_records = [
        record for record in existing_records
        if isinstance(thesis_id, str) and record.get("thesis_id") == thesis_id
    ]

    if draft.get("schema_version") == 2:
        pillars = draft.get("thesis_pillars") or []
        ledger = draft.get("evidence_ledger") or []
        observations = draft.get("kpi_observations") or []
        questions = draft.get("open_questions") or []

        local_id_sets = {
            "thesis_pillars": _item_ids(pillars, "pillar_id"),
            "evidence_ledger": _item_ids(ledger, "evidence_id"),
            "kpi_observations": _item_ids(observations, "observation_id"),
            "open_questions": _item_ids(questions, "question_id"),
        }
        for collection, values in local_id_sets.items():
            for duplicate in sorted(_duplicates(values)):
                errors.append(f"{collection}: duplicate id: {duplicate}")

        prior_pillar_ids = {
            value for record in prior_thesis_records
            for value in _item_ids(record.get("thesis_pillars") or [], "pillar_id")
        }
        prior_rule_ids = {
            value for record in prior_thesis_records
            for value in _item_ids(record.get("rules") or [], "rule_id")
        }
        prior_evidence_ids = {
            value for record in prior_thesis_records
            for value in _item_ids(record.get("evidence_ledger") or [], "evidence_id")
        }
        prior_observation_ids = {
            value for record in prior_thesis_records
            for value in _item_ids(record.get("kpi_observations") or [], "observation_id")
        }
        known_pillar_ids = prior_pillar_ids | set(local_id_sets["thesis_pillars"])
        known_rule_ids = prior_rule_ids | set(_item_ids(draft.get("rules") or [], "rule_id"))
        known_evidence_ids = prior_evidence_ids | set(local_id_sets["evidence_ledger"])

        for duplicate in sorted(prior_evidence_ids & set(local_id_sets["evidence_ledger"])):
            errors.append(f"evidence_ledger: evidence_id already exists in thesis: {duplicate}")
        for duplicate in sorted(prior_observation_ids & set(local_id_sets["kpi_observations"])):
            errors.append(f"kpi_observations: observation_id already exists in thesis: {duplicate}")

        for index, item in enumerate(ledger):
            if not isinstance(item, dict):
                continue
            for pillar_id in item.get("pillar_ids") or []:
                if pillar_id not in known_pillar_ids:
                    errors.append(f"evidence_ledger/{index}: unknown pillar_id: {pillar_id}")
        for index, item in enumerate(observations):
            if not isinstance(item, dict):
                continue
            pillar_id = item.get("pillar_id")
            if isinstance(pillar_id, str) and pillar_id not in known_pillar_ids:
                errors.append(f"kpi_observations/{index}: unknown pillar_id: {pillar_id}")
            for rule_id in item.get("linked_rule_ids") or []:
                if rule_id not in known_rule_ids:
                    errors.append(f"kpi_observations/{index}: unknown rule_id: {rule_id}")
        for index, item in enumerate(questions):
            if not isinstance(item, dict):
                continue
            for pillar_id in item.get("pillar_ids") or []:
                if pillar_id not in known_pillar_ids:
                    errors.append(f"open_questions/{index}: unknown pillar_id: {pillar_id}")
        for index, item in enumerate(pillars):
            if not isinstance(item, dict):
                continue
            for rule_id in item.get("linked_rule_ids") or []:
                if rule_id not in known_rule_ids:
                    errors.append(f"thesis_pillars/{index}: unknown rule_id: {rule_id}")
            for evidence_id in item.get("latest_evidence_ids") or []:
                if evidence_id not in known_evidence_ids:
                    errors.append(f"thesis_pillars/{index}: unknown evidence_id: {evidence_id}")

        core_impaired = sum(
            1 for item in pillars
            if isinstance(item, dict)
            and item.get("priority") == "core"
            and item.get("status") in {"impaired", "broken"}
        )
        company_status = (draft.get("decision") or {}).get("company_thesis_status")
        override = (draft.get("decision") or {}).get("status_override_rationale")
        if core_impaired >= 2 and company_status not in {"impaired", "broken"} and not override:
            errors.append(
                "decision: multiple impaired core pillars require impaired/broken status "
                "or a sourced status_override_rationale"
            )
        elif core_impaired == 1 and company_status == "watch" and not override:
            errors.append(
                "decision: watch status with an impaired core pillar requires a sourced "
                "status_override_rationale"
            )

    for index, rule in enumerate(draft.get("rules") or []):
        if not isinstance(rule, dict):
            continue
        origin = rule.get("threshold_origin")
        approval = rule.get("threshold_approval_status")
        if origin == "draft_for_pm_confirmation" and approval != "pending":
            errors.append(f"rules/{index}: a draft threshold must remain pending")
        if origin == "approved_monitoring_rule" and approval != "approved":
            errors.append(f"rules/{index}: an approved monitoring rule must be approved")

    scenarios = draft.get("scenarios") or []
    if scenarios:
        total = sum(Decimal(str(item.get("probability_pct", 0))) for item in scenarios if isinstance(item, dict))
        if total != Decimal("100"):
            errors.append(f"scenario probabilities must sum to 100, got {total}")

    for index, finding in enumerate(draft.get("unstructured_findings") or []):
        if isinstance(finding, dict) and finding.get("needs_review"):
            warnings.append(f"unstructured_findings/{index} requires review")
    for index, item in enumerate(draft.get("review_items") or []):
        warnings.append(f"review_items/{index}: {item}")

    if isinstance(ticker, str) and isinstance(thesis_id, str):
        target = _tracker_file(tracker_root, ticker, thesis_id)
        operation = draft.get("thesis_operation")
        exists = target.is_file() and bool(target.read_text(encoding="utf-8").strip())
        if operation == "open_new" and exists:
            errors.append("open_new cannot target an existing thesis")
        if operation == "append_existing" and not exists:
            errors.append("append_existing requires an existing thesis")
        if operation == "supersede_existing":
            prior = draft.get("supersedes_thesis_id")
            if not isinstance(prior, str) or not _tracker_file(tracker_root, ticker, prior).is_file():
                errors.append("supersede_existing requires an existing supersedes_thesis_id")
            if exists:
                errors.append("supersede_existing must open a new thesis_id")

        existing = existing_records
        record_id = draft.get("record_id")
        result_hashes = {
            artifact.get("sha256") for artifact in draft.get("source_artifacts") or []
            if isinstance(artifact, dict) and artifact.get("role") == "result"
        }
        for record in existing:
            if record.get("record_id") == record_id:
                errors.append(f"record_id already exists: {record_id}")
                break
            prior_result_hashes = {
                artifact.get("sha256") for artifact in record.get("source_artifacts") or []
                if isinstance(artifact, dict) and artifact.get("role") == "result"
            }
            if result_hashes & prior_result_hashes:
                errors.append("the same result artifact has already been recorded")
                break

    status = "rejected" if errors else ("valid_with_review" if warnings else "valid")
    return {
        "status": status,
        "draft": str(draft_path),
        "draft_sha256": _sha256_bytes(payload),
        "errors": errors,
        "warnings": warnings,
        "checked_at": _utc_now(),
    }


def write_validation_report(report: dict[str, Any], output_path: Path) -> None:
    _write_text_atomic(output_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def approve_draft(
    draft_path: Path,
    *,
    repo_root: Path | None = None,
    tracker_root: Path | None = None,
    allow_review: bool = False,
    approval_note: str | None = None,
    approved_at: str | None = None,
) -> Path:
    repo_root = (repo_root or _repo_root()).resolve()
    tracker_root = (tracker_root or repo_root / "data" / "thesis-tracker").resolve()
    report = validate_draft(
        draft_path, repo_root=repo_root, tracker_root=tracker_root,
    )
    if report["status"] == "rejected":
        raise PeiRecordError("draft is rejected: " + "; ".join(report["errors"]))
    if report["status"] == "valid_with_review" and not allow_review:
        raise PeiRecordError(
            "draft requires review; pass allow_review only after explicit user confirmation"
        )

    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    if draft.get("record_approval") is not None:
        raise PeiRecordError("draft must not contain pre-approved record metadata")
    approved = dict(draft)
    approved["record_approval"] = {
        "status": "approved",
        "approved_at": approved_at or _utc_now(),
        "approval_mode": "explicit_user_confirmation",
        "note": approval_note,
    }
    schema_errors = _schema_errors(approved, repo_root)
    if schema_errors:
        raise PeiRecordError("approved record fails schema: " + "; ".join(schema_errors))

    target = _tracker_file(tracker_root, approved["ticker"], approved["thesis_id"])
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    line = json.dumps(approved, ensure_ascii=False, separators=(",", ":")) + "\n"
    _write_text_atomic(target, existing + line)
    return target


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_text = text.encode("utf-8", errors="replace").decode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="replace", newline="\n") as handle:
            handle.write(safe_text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
