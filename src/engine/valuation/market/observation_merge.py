"""Merge two or more already-promoted market-observation-bundle.schema.json
files into one combined observation bundle for T70 snapshot generation
(e.g. an EOD-close price+share-count promotion's ``observations.json``
plus a separately-promoted FX ``observations.json``).

Merge is a pure set-union keyed on ``observation_id``: it never mutates,
drops, or reorders an input observation, and it never silently
deduplicates a colliding ``observation_id`` -- ``parse_observation_bundle``
(the sole runtime authority for the observation transport contract, see
``observations.py``) is reused unchanged against the concatenated
document, so a duplicate/NFC-colliding ID across two independently
promoted bundles fails exactly the same way a duplicate within one bundle
would.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Sequence

from ..canonical import canonical_bytes
from ..errors import DuplicateKeyError, MarketResolutionError, ResourceLimitError
from ..safe_json import read_safe_json
from ..schemas import iter_schema_errors
from ..transaction import TransactionResult, WriteTarget, check_transaction, execute_transaction
from ..validation.findings import Finding, has_blocking, sort_findings
from .observations import parse_observation_bundle

MERGED_BUNDLE_FILE = "merged-observations.json"
VALIDATION_FILE = "validation.json"
MERGE_MANIFEST_FILE = "merge-manifest.json"


def _finding_to_dict(finding: Finding) -> dict:
    d: dict[str, Any] = {
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "scope": finding.scope,
        "reason_code": finding.reason_code,
        "message": finding.message,
    }
    if finding.json_pointer:
        d["json_pointer"] = finding.json_pointer
    if finding.related_reference_ids:
        d["related_reference_ids"] = list(finding.related_reference_ids)
    if finding.message_params:
        d["message_params"] = finding.message_params
    return d


def _finding_counts(findings: Sequence[Finding]) -> dict:
    counts = {"blocker": 0, "error": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f.severity] += 1
    return counts


def build_observation_merge(
    *,
    input_documents: Sequence[tuple[str, dict]],
) -> tuple[dict | None, dict, dict]:
    """Pure merge engine. ``input_documents`` is an ordered sequence of
    ``(relative_path, document)`` pairs, each already safely parsed JSON
    (the caller -- ``merge_observation_bundles`` -- owns file I/O).
    Returns ``(output_bundle_doc_or_None, validation_doc, merge_manifest_doc)``;
    ``output_bundle_doc`` is ``None`` when the merge is invalid."""
    findings: list[Finding] = []
    input_meta: list[dict] = []
    all_raw_observations: list[Any] = []

    for relative_path, document in input_documents:
        schema_errors = list(iter_schema_errors("market-observation-bundle", document))
        for error in schema_errors:
            pointer = "/" + "/".join(str(p) for p in error.path)
            findings.append(Finding(
                rule_id="MERGE-SCHEMA-001", severity="blocker", scope="artifact",
                reason_code="identity.schema_violation", relative_path=relative_path,
                json_pointer=pointer, message=f"{relative_path}: {error.message}",
            ))
            continue
        try:
            parsed = parse_observation_bundle(document)
        except MarketResolutionError as exc:
            findings.append(Finding(
                rule_id="MERGE-PARSE-001", severity="blocker", scope="artifact",
                reason_code="identity.malformed_json", relative_path=relative_path,
                message=f"{relative_path}: {exc}",
            ))
            continue
        observation_count = len(parsed)
        input_meta.append({
            "relative_path": relative_path,
            "observation_count": observation_count,
        })
        all_raw_observations.extend(document.get("observations", []))

    output_bundle_doc: dict | None = None
    total_observation_count = 0

    if not has_blocking(findings):
        merged_raw = {"observations": all_raw_observations}
        try:
            merged_parsed = parse_observation_bundle(merged_raw)
        except MarketResolutionError as exc:
            findings.append(Finding(
                rule_id="MERGE-DUP-001", severity="blocker", scope="bundle",
                reason_code="identity.duplicate_row",
                message=f"merged bundle failed cross-input validation: {exc}",
            ))
        else:
            output_bundle_doc = merged_raw
            total_observation_count = len(merged_parsed)

    sorted_findings = sort_findings(findings)
    overall_status = "invalid" if has_blocking(sorted_findings) else "valid"

    validation_doc = {
        "schema_version": "1.0.0",
        "artifact_type": "market_observation_merge_validation",
        "findings": [_finding_to_dict(f) for f in sorted_findings],
    }

    merge_id_payload = {"inputs": input_meta}
    merge_id = "market-observation-merge:sha256:" + hashlib.sha256(canonical_bytes(merge_id_payload)).hexdigest()

    output_bundle_ref: dict | None = None
    if output_bundle_doc is not None:
        output_bundle_ref = {"relative_path": MERGED_BUNDLE_FILE}

    merge_manifest_doc = {
        "schema_version": "1.0.0",
        "artifact_type": "market_observation_merge_manifest",
        "merge_id": merge_id,
        "input_bundles": input_meta,
        "output_bundle": output_bundle_ref,
        "total_observation_count": total_observation_count,
        "overall_status": overall_status,
        "finding_counts": _finding_counts(sorted_findings),
    }

    return output_bundle_doc, validation_doc, merge_manifest_doc


def merge_observation_bundles(
    *,
    bundle_paths: Sequence[Path],
    output_dir: Path,
    check_only: bool = False,
) -> tuple[dict, dict, dict, TransactionResult]:
    """Filesystem orchestration: read+validate every input bundle, run the
    pure merge engine, schema-validate every generated document, and
    perform a transactional write. Returns ``(output_bundle_doc,
    validation_doc, merge_manifest_doc, transaction_result)`` --
    ``output_bundle_doc`` is ``{"observations": []}`` (never written) when
    the merge is invalid."""
    if len(bundle_paths) < 2:
        raise MarketResolutionError("observations merge requires at least two --bundle paths")

    input_documents: list[tuple[str, dict]] = []
    for path in bundle_paths:
        relative_path = str(path)
        try:
            document = read_safe_json(path, label=path.name)
        except (ResourceLimitError, DuplicateKeyError, FileNotFoundError) as exc:
            raise MarketResolutionError(f"could not read observation bundle {relative_path}: {exc}") from exc
        if not isinstance(document, dict):
            raise MarketResolutionError(f"{relative_path}: observation bundle root must be a JSON object")
        input_documents.append((relative_path, document))

    output_bundle_doc, validation_doc, merge_manifest_doc = build_observation_merge(input_documents=input_documents)

    for schema_key, document in (
        ("market-observation-merge-validation", validation_doc),
        ("market-observation-merge-manifest", merge_manifest_doc),
    ):
        errors = list(iter_schema_errors(schema_key, document))
        if errors:
            raise MarketResolutionError(
                f"internal error: generated {schema_key} document failed its own schema at {errors[0].message}"
            )

    targets = [
        WriteTarget(relative_path=VALIDATION_FILE, content=canonical_bytes(validation_doc)),
        WriteTarget(relative_path=MERGE_MANIFEST_FILE, content=canonical_bytes(merge_manifest_doc)),
    ]
    if output_bundle_doc is not None:
        errors = list(iter_schema_errors("market-observation-bundle", output_bundle_doc))
        if errors:
            raise MarketResolutionError(
                f"internal error: merged observation bundle failed its own schema at {errors[0].message}"
            )
        targets.append(WriteTarget(relative_path=MERGED_BUNDLE_FILE, content=canonical_bytes(output_bundle_doc)))

    transaction_result = check_transaction(output_dir, targets) if check_only else execute_transaction(output_dir, targets)
    return output_bundle_doc or {"observations": []}, validation_doc, merge_manifest_doc, transaction_result
