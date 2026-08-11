"""Source-manifest and metric-provenance validation.

Every source-grounded record (direct financial metric, financial-operational
metric, historical-series metric, risk evidence item) must resolve an
*effective* source_id that exists in the ticker's source manifest, and that
source_id's declared manifest path must agree with the record's own
source_file when the record claims to cite a raw source document directly.
Generated derived ratios, signals, summaries, and reports are exempt: their
provenance is through formula/rule ids and ``generated_from`` references,
not source_id.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import UnsafePathError
from ..paths import ensure_inside_repo, is_drive_archived, repo_path
from .result import ValidationFinding, ValidationResult


def validate_source_manifest(manifest: dict | None, ticker: str, data_root: Path | None = None) -> ValidationResult:
    result = ValidationResult()
    if manifest is None:
        result.add(ValidationFinding("source_manifest_missing", "error", f"No source manifest for {ticker}."))
        return result

    seen_ids: set[str] = set()
    for source in manifest.get("sources", []):
        source_id = source.get("source_id")
        if source_id in seen_ids:
            result.add(ValidationFinding("duplicate_source_id", "error", f"Duplicate source_id: {source_id}"))
        seen_ids.add(source_id)

        try:
            resolved = ensure_inside_repo(repo_path(source["path"], root=data_root), root=data_root)
        except UnsafePathError as e:
            result.add(ValidationFinding("source_path_escapes_repo", "error", str(e), source_id))
            continue
        if not resolved.exists():
            if is_drive_archived(source["path"], root=data_root):
                result.add(ValidationFinding("source_path_drive_archived", "info", f"Source path is Drive-archived, not present locally: {source['path']}", source_id))
            else:
                result.add(ValidationFinding("source_path_missing", "error", f"Source path does not exist: {source['path']}", source_id))

        if source.get("currency") is None or source.get("scale") is None:
            result.add(ValidationFinding("source_metadata_incomplete", "info", "currency/scale not populated for this source; provenance completeness is reduced but not blocked.", source_id))

    return result


def _check_effective_source_id(
    *,
    provenance: dict | None,
    manifest_by_id: dict[str, dict],
    file_label: str,
    record_label: str,
    result: ValidationResult,
    require_path_match: bool,
) -> None:
    if not provenance:
        result.add(ValidationFinding("missing_provenance", "error", f"{record_label}: no source provenance.", file_label, record_label))
        return
    source_id = provenance.get("source_id")
    if not source_id:
        result.add(ValidationFinding("missing_source_id", "error", f"{record_label}: provenance has no source_id.", file_label, record_label))
        return
    manifest_source = manifest_by_id.get(source_id)
    if manifest_source is None:
        result.add(ValidationFinding("unknown_source_id", "error", f"{record_label}: provenance.source_id {source_id!r} does not resolve in the source manifest.", file_label, record_label))
        return
    source_file = provenance.get("source_file")
    if require_path_match:
        if source_file is not None and source_file != manifest_source.get("path"):
            result.add(ValidationFinding(
                "source_id_file_mismatch", "error",
                f"{record_label}: provenance.source_id {source_id!r} resolves to manifest path "
                f"{manifest_source.get('path')!r}, which disagrees with this record's source_file {source_file!r}.",
                file_label, record_label,
            ))


def validate_metric_provenance(direct_financials: dict, manifest: dict | None, file_label: str) -> ValidationResult:
    """Every direct metric's provenance must carry a source_id that
    resolves in the manifest and whose declared source_file agrees with
    the manifest's path for that source_id. (Schema validation already
    requires ``source_id``/``source_file`` to be present; this layer
    checks that they actually agree with the manifest.)"""
    result = ValidationResult()
    manifest_by_id = {s["source_id"]: s for s in (manifest or {}).get("sources", [])}

    for section in ("income_statement", "balance_sheet", "cash_flow_statement", "commitments"):
        for m in direct_financials.get(section, []):
            if m.get("data_type") != "direct":
                continue
            _check_effective_source_id(
                provenance=m.get("provenance"), manifest_by_id=manifest_by_id,
                file_label=file_label, record_label=m["metric_id"], result=result, require_path_match=True,
            )
    return result


def validate_financial_operational_provenance(finops_data: dict, manifest: dict | None, file_label: str) -> ValidationResult:
    """Financial-operational metrics resolve an effective source_id either
    from their own ``provenance.source_id`` override or from the file's
    ``default_source_id``; at least one of the two must be present and
    resolve in the manifest for every direct (non-derived) metric."""
    result = ValidationResult()
    manifest_by_id = {s["source_id"]: s for s in (manifest or {}).get("sources", [])}
    default_source_id = finops_data.get("default_source_id")

    for m in finops_data.get("metrics", []):
        if m.get("data_type") not in (None, "direct"):
            continue  # derived/passthrough metrics carry no source_id requirement
        provenance = m.get("provenance") or {}
        effective_source_id = provenance.get("source_id") or default_source_id
        label = m["metric_id"]
        if not effective_source_id:
            result.add(ValidationFinding("missing_source_id", "error", f"{label}: no per-metric source_id override and the file has no default_source_id.", file_label, label))
            continue
        if effective_source_id not in manifest_by_id:
            result.add(ValidationFinding("unknown_source_id", "error", f"{label}: effective source_id {effective_source_id!r} does not resolve in the source manifest.", file_label, label))


    return result


def validate_series_provenance(series_data: dict, manifest: dict | None, file_label: str) -> ValidationResult:
    """Historical-series metrics resolve an effective source_id from a
    per-metric ``provenance.source_id`` override or the series-level
    ``default_source_id``."""
    result = ValidationResult()
    manifest_by_id = {s["source_id"]: s for s in (manifest or {}).get("sources", [])}
    default_source_id = series_data.get("default_source_id")

    for period_entry in series_data.get("periods", []):
        for metric_id, entry in period_entry.get("metrics", {}).items():
            provenance = entry.get("provenance") or {}
            effective_source_id = provenance.get("source_id") or default_source_id
            label = f"{period_entry.get('period')}:{metric_id}"
            if not effective_source_id:
                result.add(ValidationFinding("missing_source_id", "error", f"{label}: no per-metric source_id override and the series has no default_source_id.", file_label, label))
                continue
            if effective_source_id not in manifest_by_id:
                result.add(ValidationFinding("unknown_source_id", "error", f"{label}: effective source_id {effective_source_id!r} does not resolve in the source manifest.", file_label, label))
    return result


def validate_risk_evidence_provenance(risks_data: dict, manifest: dict | None, file_label: str) -> ValidationResult:
    """Every risk evidence item must carry a source_id. When the evidence
    cites a raw source document directly (``source_file`` under ``raw/``),
    that source_id's manifest path must match. When it instead cites
    another normalized pipeline file (e.g. a computed ratio quoted from
    ``data/financial/TICKER/PERIOD.json``), only the source_id itself needs
    to resolve in the manifest -- it names the source backing the *cited
    file's* own metrics, not the cited file itself, so no path-equality
    check applies."""
    result = ValidationResult()
    manifest_by_id = {s["source_id"]: s for s in (manifest or {}).get("sources", [])}
    for risk in risks_data.get("risks", []):
        for i, evidence in enumerate(risk.get("evidence", [])):
            label = f"{risk['risk_id']}[{i}]"
            source_file = evidence.get("source_file") or ""
            is_raw_reference = source_file.startswith("raw/")
            _check_effective_source_id(
                provenance=evidence, manifest_by_id=manifest_by_id,
                file_label=file_label, record_label=label, result=result, require_path_match=is_raw_reference,
            )
    return result
