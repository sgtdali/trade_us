"""Orchestrates fetch -> capture -> normalize -> validate -> transactional
bundle write, plus structural ``fx-bundle validate`` and recompute-and-
compare ``fx-bundle replay``. This is the only module in the FX ingestion
namespace that touches the filesystem or a provider.

Structurally parallel to ``ingestion.eod.service``, reusing
``ingestion.eod.providers.yfinance_provider.YFinanceProvider`` (the network
adapter) and ``ingestion.eod.models.EndOfDayFetchRequest`` unchanged, per
this package's reuse boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ...canonical import canonical_bytes
from ...safe_json import read_safe_json
from ...schemas import iter_schema_errors
from ...transaction import TransactionResult, WriteTarget, check_transaction, execute_transaction
from ...validation.findings import Finding, has_blocking, sort_findings
from ..eod.errors import ProviderConfigError
from ..eod.models import EndOfDayFetchRequest, ProviderConfig
from ..eod.providers.base import EndOfDayMarketProvider
from .capture import build_fx_provider_extract, parse_fx_provider_extract
from .errors import FxBundleIntegrityError, FxIngestionError
from .normalize import build_normalized_fx_rows
from .validation import validate_and_quarantine_fx_rows, validate_fx_request_and_mapping

REQUEST_FILE = "request.json"
PROVIDER_EXTRACT_FILE = "fx-provider-extract.json"
RATE_SERIES_FILE = "fx-rate-series.json"
VALIDATION_FILE = "validation.json"
BUNDLE_MANIFEST_FILE = "bundle-manifest.json"
BUNDLE_FILES = (REQUEST_FILE, PROVIDER_EXTRACT_FILE, RATE_SERIES_FILE, VALIDATION_FILE)


def load_fx_provider_config(path: Path) -> ProviderConfig:
    try:
        document = read_safe_json(path, label=path.name)
    except Exception as exc:  # noqa: BLE001 - re-raised as the ingestion-typed bootstrap error
        raise ProviderConfigError(f"could not read FX provider config {path.name}: {exc}") from exc
    return ProviderConfig.from_dict(document)


def _finding_to_dict(finding: Finding) -> dict:
    d: dict = {
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


@dataclass(frozen=True)
class FxIngestionRunResult:
    overall_status: str  # "valid" | "invalid"
    findings: tuple[Finding, ...]
    transaction: TransactionResult | None = None

    @property
    def ok(self) -> bool:
        return self.overall_status == "valid"


def _build_targets(
    *,
    provider_config: ProviderConfig,
    requests: Sequence[EndOfDayFetchRequest],
    series_list,
    retrieved_at: str,
    provider_library_version: str,
    pair_currencies: Mapping[str, tuple[str, str]],
) -> tuple[list[WriteTarget], list[Finding], dict]:
    findings: list[Finding] = []

    for series in series_list:
        if series.status == "failed":
            findings.append(Finding(
                rule_id="FXING-FETCH-001", severity="blocker", scope="bundle",
                reason_code="provider.fetch_failed",
                message=f"provider fetch failed for {series.internal_ticker!r} ({series.provider_symbol!r}): {series.error_reason}",
                artifact_id=series.internal_ticker,
            ))

    extract = build_fx_provider_extract(
        provider_config=provider_config, requests=requests, series_list=series_list,
        retrieved_at=retrieved_at, provider_library_version=provider_library_version,
        pair_currencies=pair_currencies,
    )
    for error in iter_schema_errors("fx-provider-extract", extract):
        findings.append(Finding(rule_id="FXING-SCHEMA-001", severity="blocker", scope="bundle", reason_code="identity.schema_violation", message=f"fx-provider-extract schema violation: {error.message}"))

    ok_series = [s for s in series_list if s.status == "ok"]
    rows = build_normalized_fx_rows(ok_series, pair_currencies=pair_currencies)
    rows, quarantine_findings = validate_and_quarantine_fx_rows(
        rows, start_date_inclusive=requests[0].start_date_inclusive, end_date_exclusive=requests[0].end_date_exclusive,
    )
    findings.extend(quarantine_findings)

    for series in ok_series:
        valid_count = sum(1 for r in rows if r["pair_id"] == series.internal_ticker and r["row_status"] == "valid")
        if valid_count == 0:
            findings.append(Finding(
                rule_id="FXING-ROW-003", severity="blocker", scope="bundle",
                reason_code="pair.no_valid_close_rows",
                message=f"pair {series.internal_ticker!r} has no valid FX close row in the requested range",
                artifact_id=series.internal_ticker,
            ))

    rate_series = {
        "schema_version": "1.0.0",
        "artifact_type": "fx_rate_series",
        "provider_id": "yfinance",
        "rows": rows,
    }
    for error in iter_schema_errors("fx-rate-series", rate_series):
        findings.append(Finding(rule_id="FXING-SCHEMA-002", severity="blocker", scope="bundle", reason_code="identity.schema_violation", message=f"fx-rate-series schema violation: {error.message}"))

    sorted_findings = sort_findings(findings)
    validation_doc = {
        "schema_version": "1.0.0",
        "artifact_type": "fx_ingestion_validation",
        "findings": [_finding_to_dict(f) for f in sorted_findings],
    }
    schema_errors = list(iter_schema_errors("fx-ingestion-validation", validation_doc))
    if schema_errors:
        raise FxIngestionError(f"internal error: generated validation.json failed its own schema: {schema_errors[0].message}")

    request_doc = {
        "schema_version": "1.0.0",
        "artifact_type": "fx_ingestion_request",
        "provider": extract["provider"],
        "request": extract["request"],
    }

    overall_status = "invalid" if has_blocking(sorted_findings) else "valid"
    valid_row_count = sum(1 for r in rows if r["row_status"] == "valid")
    quarantined_row_count = sum(1 for r in rows if r["row_status"] == "quarantined")

    bundle_files_meta = [
        {"relative_path": REQUEST_FILE},
        {"relative_path": PROVIDER_EXTRACT_FILE},
        {"relative_path": RATE_SERIES_FILE},
        {"relative_path": VALIDATION_FILE},
    ]
    bundle_manifest = {
        "schema_version": "1.0.0",
        "artifact_type": "fx_ingestion_bundle",
        "provider_id": "yfinance",
        "provider_library_version": provider_library_version,
        "requested_pairs": [r.internal_ticker for r in requests],
        "overall_status": overall_status,
        "valid_row_count": valid_row_count,
        "quarantined_row_count": quarantined_row_count,
        "finding_counts": _finding_counts(sorted_findings),
        "bundle_files": bundle_files_meta,
    }

    targets = [
        WriteTarget(relative_path=REQUEST_FILE, content=canonical_bytes(request_doc)),
        WriteTarget(relative_path=PROVIDER_EXTRACT_FILE, content=canonical_bytes(extract)),
        WriteTarget(relative_path=RATE_SERIES_FILE, content=canonical_bytes(rate_series)),
        WriteTarget(relative_path=VALIDATION_FILE, content=canonical_bytes(validation_doc)),
        WriteTarget(relative_path=BUNDLE_MANIFEST_FILE, content=canonical_bytes(bundle_manifest)),
    ]
    return targets, sorted_findings, bundle_manifest


def run_fetch_fx(
    *,
    provider: EndOfDayMarketProvider,
    provider_config: ProviderConfig,
    requested_pairs: Sequence[str],
    start_date_inclusive: str,
    end_date_exclusive: str,
    timeout: float,
    retrieved_at: str,
    provider_library_version: str,
    output_dir: Path,
    check_only: bool = False,
) -> FxIngestionRunResult:
    """``check_only`` is not exposed on the ``market-ingestion fx fetch``
    CLI command (a live pilot fetch is inherently non-idempotent against a
    real provider), but is used directly by the fixture materializer to
    drift-check the committed synthetic fixture bundles against a
    deterministic mocked provider, the same way ``run_fetch`` in the
    sibling EOD ingestion namespace does."""
    mapping_findings = validate_fx_request_and_mapping(provider_config, requested_pairs)
    if has_blocking(mapping_findings):
        return FxIngestionRunResult(overall_status="invalid", findings=tuple(sort_findings(mapping_findings)), transaction=None)

    requests = [
        EndOfDayFetchRequest(
            internal_ticker=pair_id,
            provider_symbol=provider_config.active_fx_mapping(pair_id).provider_symbol,
            start_date_inclusive=start_date_inclusive,
            end_date_exclusive=end_date_exclusive,
            timeout=timeout,
        )
        for pair_id in requested_pairs
    ]
    pair_currencies = {
        pair_id: (provider_config.active_fx_mapping(pair_id).base_currency, provider_config.active_fx_mapping(pair_id).quote_currency)
        for pair_id in requested_pairs
    }

    series_list = provider.fetch(requests)

    targets, findings, bundle_manifest = _build_targets(
        provider_config=provider_config, requests=requests, series_list=series_list,
        retrieved_at=retrieved_at, provider_library_version=provider_library_version,
        pair_currencies=pair_currencies,
    )
    transaction_result = check_transaction(output_dir, targets) if check_only else execute_transaction(output_dir, targets)
    return FxIngestionRunResult(overall_status=bundle_manifest["overall_status"], findings=tuple(findings), transaction=transaction_result)


def _load_bundle_files(root: Path) -> dict[str, dict]:
    documents: dict[str, dict] = {}
    for name in BUNDLE_FILES + (BUNDLE_MANIFEST_FILE,):
        path = root / name
        if not path.exists():
            raise FxBundleIntegrityError(f"missing expected FX bundle file: {name}")
        documents[name] = read_safe_json(path, label=name)
    return documents


_SCHEMA_KEY_BY_FILE = {
    PROVIDER_EXTRACT_FILE: "fx-provider-extract",
    RATE_SERIES_FILE: "fx-rate-series",
    VALIDATION_FILE: "fx-ingestion-validation",
    BUNDLE_MANIFEST_FILE: "fx-ingestion-bundle",
}


def validate_fx_bundle(root: Path) -> list[Finding]:
    """Structural validation only: schema conformance and bundle-manifest
    referential integrity (exact file set) against the files actually
    present under ``root``. Does not re-derive normalized rows from the
    provider extract -- that full economic recompute is ``replay``'s
    job."""
    findings: list[Finding] = []

    try:
        documents = _load_bundle_files(root)
    except FxBundleIntegrityError as exc:
        return [Finding(rule_id="FXING-BUNDLE-001", severity="blocker", scope="bundle", reason_code="identity.resource_missing", message=str(exc))]

    present_json_files = {p.name for p in root.glob("*.json")}
    expected_json_files = set(BUNDLE_FILES + (BUNDLE_MANIFEST_FILE,))
    unexpected = present_json_files - expected_json_files
    if unexpected:
        findings.append(Finding(rule_id="FXING-BUNDLE-002", severity="error", scope="bundle", reason_code="identity.unexpected_governed_file", message=f"unexpected governed JSON file(s) under bundle root: {sorted(unexpected)}"))

    for name, schema_key in _SCHEMA_KEY_BY_FILE.items():
        for error in iter_schema_errors(schema_key, documents[name]):
            pointer = "/" + "/".join(str(p) for p in error.path)
            findings.append(Finding(rule_id="FXING-SCHEMA-010", severity="error", scope="artifact", reason_code="identity.schema_violation", json_pointer=pointer, relative_path=name, message=error.message))

    manifest = documents[BUNDLE_MANIFEST_FILE]
    manifest_files_by_path = {f["relative_path"] for f in manifest.get("bundle_files", [])}
    if manifest_files_by_path != set(BUNDLE_FILES):
        findings.append(Finding(rule_id="FXING-BUNDLE-003", severity="blocker", scope="bundle", reason_code="identity.reference_invalid", message="bundle-manifest.bundle_files does not name exactly the four expected bundle files"))

    return sort_findings(findings)


def replay_fx_bundle(root: Path, *, check_only: bool) -> tuple[TransactionResult, list[Finding]]:
    """Reload ``fx-provider-extract.json``, regenerate ``fx-rate-
    series.json``/``validation.json``/``bundle-manifest.json`` from it, and
    either compare (``check_only=True``, zero writes) or write the
    regenerated bytes in place. ``request.json`` and ``fx-provider-
    extract.json`` are treated as immutable inputs -- replay never
    regenerates or overwrites either of them."""
    extract_path = root / PROVIDER_EXTRACT_FILE
    request_path = root / REQUEST_FILE
    if not extract_path.exists():
        raise FxBundleIntegrityError(f"missing {PROVIDER_EXTRACT_FILE}; cannot replay")
    if not request_path.exists():
        raise FxBundleIntegrityError(f"missing {REQUEST_FILE}; cannot replay")
    extract = read_safe_json(extract_path, label=PROVIDER_EXTRACT_FILE)

    series_list = parse_fx_provider_extract(extract)
    request_meta = extract["request"]
    pair_currencies = {
        pair_id: (currencies["base_currency"], currencies["quote_currency"])
        for pair_id, currencies in request_meta["resolved_pair_currencies"].items()
    }

    ok_series = [s for s in series_list if s.status == "ok"]
    rows = build_normalized_fx_rows(ok_series, pair_currencies=pair_currencies)
    rows, quarantine_findings = validate_and_quarantine_fx_rows(
        rows, start_date_inclusive=request_meta["start_date_inclusive"], end_date_exclusive=request_meta["end_date_exclusive"],
    )

    findings: list[Finding] = []
    for series in series_list:
        if series.status == "failed":
            findings.append(Finding(rule_id="FXING-FETCH-001", severity="blocker", scope="bundle", reason_code="provider.fetch_failed", message=f"provider fetch failed for {series.internal_ticker!r}: {series.error_reason}", artifact_id=series.internal_ticker))
    findings.extend(quarantine_findings)
    for series in ok_series:
        valid_count = sum(1 for r in rows if r["pair_id"] == series.internal_ticker and r["row_status"] == "valid")
        if valid_count == 0:
            findings.append(Finding(rule_id="FXING-ROW-003", severity="blocker", scope="bundle", reason_code="pair.no_valid_close_rows", message=f"pair {series.internal_ticker!r} has no valid FX close row in the requested range", artifact_id=series.internal_ticker))

    rate_series = {
        "schema_version": "1.0.0",
        "artifact_type": "fx_rate_series",
        "provider_id": "yfinance",
        "rows": rows,
    }

    sorted_findings = sort_findings(findings)
    validation_doc = {
        "schema_version": "1.0.0",
        "artifact_type": "fx_ingestion_validation",
        "findings": [_finding_to_dict(f) for f in sorted_findings],
    }

    overall_status = "invalid" if has_blocking(sorted_findings) else "valid"
    bundle_manifest = {
        "schema_version": "1.0.0",
        "artifact_type": "fx_ingestion_bundle",
        "provider_id": "yfinance",
        "provider_library_version": extract["provider"]["provider_library_version"],
        "requested_pairs": request_meta["requested_pairs"],
        "overall_status": overall_status,
        "valid_row_count": sum(1 for r in rows if r["row_status"] == "valid"),
        "quarantined_row_count": sum(1 for r in rows if r["row_status"] == "quarantined"),
        "finding_counts": _finding_counts(sorted_findings),
        "bundle_files": [
            {"relative_path": REQUEST_FILE},
            {"relative_path": PROVIDER_EXTRACT_FILE},
            {"relative_path": RATE_SERIES_FILE},
            {"relative_path": VALIDATION_FILE},
        ],
    }

    targets = [
        WriteTarget(relative_path=RATE_SERIES_FILE, content=canonical_bytes(rate_series)),
        WriteTarget(relative_path=VALIDATION_FILE, content=canonical_bytes(validation_doc)),
        WriteTarget(relative_path=BUNDLE_MANIFEST_FILE, content=canonical_bytes(bundle_manifest)),
    ]

    if check_only:
        return check_transaction(root, targets), sorted_findings
    return execute_transaction(root, targets), sorted_findings
