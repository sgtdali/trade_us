"""Market snapshot service adapter: loads local files, calls the pure
resolver, derives identity, revalidates, and performs
check/transactional-write behavior
(docs/valuation-t70-04-market-registry-snapshot-specification.md Section 15).

This is the only module in the market package that touches the
filesystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..canonical import canonical_bytes
from ..catalogs import CatalogRegistry
from ..errors import DuplicateKeyError, MarketResolutionError, ResourceLimitError
from ..identity import derive_artifact_id, derive_context_id
from ..paths import market_snapshot_relative_path, resolve_governed_path
from ..safe_json import read_safe_json
from ..schemas import iter_definition_errors
from ..schemas import iter_schema_errors
from ..transaction import TransactionResult, WriteTarget, check_transaction, execute_transaction
from ..validation.findings import Finding, sort_findings
from .corporate_actions import parse_corporate_action_bundle
from .observations import parse_observation_bundle
from .registry import check_manifest_authorization, load_market_source_manifest, manifest_artifact_id, market_source_manifest_relative_path
from .resolver import MarketResolutionRequest, resolve_market_snapshot


class MarketGenerationResult:
    def __init__(self, *, findings: tuple[Finding, ...], snapshot: dict[str, Any] | None, transaction: TransactionResult | None):
        self.findings = findings
        self.snapshot = snapshot
        self.transaction = transaction

    @property
    def ok(self) -> bool:
        return not any(f.severity in ("blocker", "error") for f in self.findings)


def generate_market_snapshot(
    *,
    manifest_path: Path,
    observations_path: Path,
    ticker: str,
    as_of_date: str,
    cutoff_instant: str,
    context_projection: dict[str, Any],
    catalog_registry: CatalogRegistry,
    output_dir: Path,
    check_only: bool = False,
    additional_manifest_paths: tuple[Path, ...] = (),
    overrides_path: Path | None = None,
    corporate_actions_path: Path | None = None,
) -> MarketGenerationResult:
    """``additional_manifest_paths`` names zero or more independent
    additional market-source manifests (e.g. a ``licensed_vendor``
    cross-check alongside a ``primary_official`` exchange feed) so
    authority-first comparison can genuinely rank observations from
    different sources against each other, not just within one manifest
    (docs/valuation-t05-price-basis-contract.md Section 11.1). Each is
    loaded and authorized exactly like the primary manifest.

    ``overrides_path`` optionally names a local ``{"overrides": [...]}``
    file of governed manual override records (docs/valuation-t70-04-*.md
    Section 11); each is only consumed by the resolver if it validly
    resolves an otherwise-unresolved conflict -- it is never applied
    speculatively.

    ``corporate_actions_path`` optionally names a governed corporate-
    action bundle (schemas/corporate-action-bundle.schema.json, e.g.
    produced by ``engine.valuation.ingestion.share_count``'s
    promotion engine). When absent, ``corporate_action_state`` in the
    resulting snapshot is byte-for-byte identical to prior behavior
    (``events: []``, ``coverage_status: "unknown"``)."""
    findings: list[Finding] = []

    try:
        manifest = load_market_source_manifest(manifest_path)
    except MarketResolutionError as exc:
        return MarketGenerationResult(
            findings=(Finding(rule_id="VAL-ID-101", severity="blocker", scope="bundle", reason_code="identity.resource_missing", message=str(exc)),),
            snapshot=None, transaction=None,
        )

    auth_problems = check_manifest_authorization(manifest, ticker=ticker, as_of_date=as_of_date)
    if auth_problems:
        for problem in auth_problems:
            findings.append(Finding(rule_id="VAL-MI-001", severity="blocker", scope="artifact", reason_code="identity.reference_invalid", message=problem))
        return MarketGenerationResult(findings=tuple(sort_findings(findings)), snapshot=None, transaction=None)

    mid = manifest_artifact_id(manifest)
    manifest_ref = {
        "artifact_id": mid,
        "artifact_type": "market_source_manifest",
        # The canonical, repository-relative location a market-source
        # manifest for this ticker is owned under (docs T57's repository
        # paths contract), independent of the arbitrary filesystem path
        # --manifest was actually read from -- no absolute host path or
        # caller-local layout ever enters a reference, and T70-B does not
        # require (or create) data/market-source-manifests/ to physically
        # exist for this reference to be well-formed.
        "relative_path": market_source_manifest_relative_path(ticker=ticker, manifest_id=manifest.get("manifest_id", ""), primary=True),
    }

    additional_manifests: list[Mapping[str, Any]] = []
    additional_manifest_refs: list[dict[str, Any]] = []
    for extra_path in additional_manifest_paths:
        try:
            extra_manifest = load_market_source_manifest(extra_path)
        except MarketResolutionError as exc:
            return MarketGenerationResult(
                findings=(Finding(rule_id="VAL-ID-101", severity="blocker", scope="bundle", reason_code="identity.resource_missing", message=str(exc)),),
                snapshot=None, transaction=None,
            )
        # FX manifests identify a currency pair rather than an equity ticker.
        # They are still parsed and pinned in the snapshot, but applying the
        # equity-ticker authorization predicate to them would reject every
        # legitimate FX observation before the resolver can evaluate it.
        is_fx = extra_manifest.get("dataset_identity", {}).get("dataset_kind") == "fx"
        extra_auth_problems = check_manifest_authorization(
            extra_manifest,
            pair=(extra_manifest.get("pair_identity") or {}).get("pair_id") if is_fx else None,
            ticker=None if is_fx else ticker,
            as_of_date=as_of_date,
        )
        if extra_auth_problems:
            for problem in extra_auth_problems:
                findings.append(Finding(rule_id="VAL-MI-001", severity="blocker", scope="artifact", reason_code="identity.reference_invalid", message=problem))
            return MarketGenerationResult(findings=tuple(sort_findings(findings)), snapshot=None, transaction=None)
        additional_manifests.append(extra_manifest)
        extra_mid = manifest_artifact_id(extra_manifest)
        additional_manifest_refs.append({
            "artifact_id": extra_mid,
            "artifact_type": "market_source_manifest",
            # See the primary manifest_ref comment above: this convention
            # (ticker + this manifest's own manifest_id) is not yet
            # ratified by a T57 revision covering multi-manifest-per-ticker
            # governed paths -- it is a documented, minimal extension of
            # the existing single-manifest convention, not an invented
            # arbitrary path.
            "relative_path": market_source_manifest_relative_path(
                pair_id=(extra_manifest.get("pair_identity") or {}).get("pair_id") if is_fx else None,
                ticker=None if is_fx else ticker,
                manifest_id=extra_manifest.get("manifest_id", ""),
            ),
        })

    try:
        observation_document = read_safe_json(observations_path, label=observations_path.name)
        observations = parse_observation_bundle(observation_document)
    except (MarketResolutionError, ResourceLimitError, DuplicateKeyError) as exc:
        return MarketGenerationResult(
            findings=(Finding(rule_id="VAL-ID-102", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message=str(exc)),),
            snapshot=None, transaction=None,
        )

    overrides: tuple[Mapping[str, Any], ...] = ()
    if overrides_path is not None:
        try:
            overrides_document = read_safe_json(overrides_path, label=overrides_path.name)
        except (ResourceLimitError, DuplicateKeyError) as exc:
            return MarketGenerationResult(
                findings=(Finding(rule_id="VAL-ID-102", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message=str(exc)),),
                snapshot=None, transaction=None,
            )
        if not isinstance(overrides_document, dict) or not isinstance(overrides_document.get("overrides"), list):
            return MarketGenerationResult(
                findings=(Finding(rule_id="VAL-ID-103", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message="overrides file root must be a JSON object with an 'overrides' array"),),
                snapshot=None, transaction=None,
            )
        override_findings: list[Finding] = []
        seen_override_ids: set[str] = set()
        validated_overrides: list[Mapping[str, Any]] = []
        instrument_currency = manifest.get("instrument_identity", {}).get("trading_currency")
        for index, override in enumerate(overrides_document["overrides"]):
            pointer = f"/overrides/{index}"
            if not isinstance(override, dict):
                override_findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="blocker", scope="bundle", reason_code="identity.schema_violation", json_pointer=pointer, message=f"override {index}: must be a JSON object"))
                continue
            schema_errors = list(iter_definition_errors("market-snapshot", "governedOverride", override))
            for error in schema_errors:
                suffix = "/" + "/".join(str(p) for p in error.path) if error.path else ""
                override_findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="blocker", scope="bundle", reason_code="identity.schema_violation", json_pointer=pointer + suffix, artifact_id=str(override.get("override_id", "")), message=f"governed override schema violation: {error.message}"))
            override_id = override.get("override_id")
            if isinstance(override_id, str):
                if override_id in seen_override_ids:
                    override_findings.append(Finding(rule_id="VAL-ID-102", severity="blocker", scope="bundle", reason_code="identity.duplicate_key", json_pointer=pointer, artifact_id=override_id, message=f"duplicate governed override_id {override_id!r}"))
                seen_override_ids.add(override_id)
            dim = override.get("target_dimension")
            unit = override.get("replacement_unit")
            currency = override.get("replacement_currency")
            compatible = (
                (dim == "price" and unit == instrument_currency and currency == instrument_currency)
                or (dim in {"issued_shares", "treasury_shares", "spot_basic_shares_outstanding"} and unit == "shares" and currency is None)
            )
            if not compatible:
                override_findings.append(Finding(rule_id="VAL-MI-001", severity="blocker", scope="bundle", reason_code="capital.price_share_basis_mismatch", json_pointer=pointer, artifact_id=str(override_id or ""), message="governed override replacement unit/currency is not compatible with target_dimension"))
            if not schema_errors and compatible and isinstance(override_id, str) and override_id in seen_override_ids:
                validated_overrides.append(override)
        if override_findings:
            return MarketGenerationResult(findings=tuple(sort_findings(override_findings)), snapshot=None, transaction=None)
        overrides = tuple(validated_overrides)

    context_id = derive_context_id(context_projection)

    instrument_identity = manifest.get("instrument_identity", {})

    corporate_action_bundle = None
    if corporate_actions_path is not None:
        try:
            ca_document = read_safe_json(corporate_actions_path, label=corporate_actions_path.name)
        except (MarketResolutionError, ResourceLimitError, DuplicateKeyError) as exc:
            return MarketGenerationResult(
                findings=(Finding(rule_id="VAL-ID-102", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message=str(exc)),),
                snapshot=None, transaction=None,
            )
        if not isinstance(ca_document, dict):
            return MarketGenerationResult(
                findings=(Finding(rule_id="VAL-ID-103", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message="corporate-action bundle root must be a JSON object"),),
                snapshot=None, transaction=None,
            )
        ca_schema_errors = list(iter_schema_errors("corporate-action-bundle", ca_document))
        if ca_schema_errors:
            for error in ca_schema_errors:
                pointer = "/" + "/".join(str(p) for p in error.path)
                findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="blocker", scope="bundle", reason_code="identity.schema_violation", json_pointer=pointer, message=error.message))
            return MarketGenerationResult(findings=tuple(sort_findings(findings)), snapshot=None, transaction=None)
        try:
            corporate_action_bundle = parse_corporate_action_bundle(ca_document)
        except MarketResolutionError as exc:
            return MarketGenerationResult(
                findings=(Finding(rule_id="VAL-ID-102", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message=str(exc)),),
                snapshot=None, transaction=None,
            )
        if corporate_action_bundle.ticker != ticker or corporate_action_bundle.instrument_id != instrument_identity.get("instrument_id", ""):
            return MarketGenerationResult(
                findings=(Finding(rule_id="VAL-MI-001", severity="blocker", scope="bundle", reason_code="identity.reference_invalid", message="corporate-action bundle ticker/instrument_id does not match the requested snapshot"),),
                snapshot=None, transaction=None,
            )

    request = MarketResolutionRequest(
        ticker=ticker,
        instrument_id=instrument_identity.get("instrument_id", ""),
        instrument_type=instrument_identity.get("instrument_type", "ordinary_share"),
        trading_currency=instrument_identity.get("trading_currency", ""),
        as_of_date=as_of_date,
        cutoff_instant=cutoff_instant,
        context_id=context_id,
        manifest=manifest,
        manifest_reference=manifest_ref,
        observations=observations,
        catalog_registry=catalog_registry,
        additional_manifests=tuple(additional_manifests),
        additional_manifest_references=tuple(additional_manifest_refs),
        purpose=context_projection["purpose"],
        primary_price_mode=context_projection["primary_price_mode"],
        overrides=overrides,
        corporate_action_bundle=corporate_action_bundle,
    )
    result = resolve_market_snapshot(request)
    findings.extend(result.findings)
    if result.snapshot is None:
        return MarketGenerationResult(findings=tuple(sort_findings(findings)), snapshot=None, transaction=None)

    unhashed = dict(result.snapshot)
    artifact_id = derive_artifact_id("market_snapshot", {
        "ticker": ticker, "as_of_date": as_of_date, "context_id": context_id,
    })
    unhashed["artifact_id"] = artifact_id

    final_errors = list(iter_schema_errors("market-snapshot", unhashed))
    if final_errors:
        for error in final_errors:
            pointer = "/" + "/".join(str(p) for p in error.path)
            findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", reason_code="identity.schema_violation", json_pointer=pointer, message=error.message))
        return MarketGenerationResult(findings=tuple(sort_findings(findings)), snapshot=None, transaction=None)

    relative_path = market_snapshot_relative_path(ticker, as_of_date)
    target = WriteTarget(relative_path=relative_path, content=canonical_bytes(unhashed))

    if check_only:
        transaction_result = check_transaction(output_dir, [target])
    else:
        transaction_result = execute_transaction(output_dir, [target])

    return MarketGenerationResult(findings=tuple(sort_findings(findings)), snapshot=unhashed, transaction=transaction_result)


def validate_market_snapshot(
    *,
    manifest_path: Path,
    snapshot_path: Path,
    catalog_registry: CatalogRegistry,
) -> list[Finding]:
    """Independently recompute and verify a committed market-snapshot
    artifact's schema and source-manifest reference. Never trusts a
    stored derived value merely because it is schema-valid."""
    findings: list[Finding] = []

    try:
        manifest = load_market_source_manifest(manifest_path)
    except MarketResolutionError as exc:
        findings.append(Finding(rule_id="VAL-ID-101", severity="blocker", scope="bundle", reason_code="identity.resource_missing", message=str(exc)))
        return sort_findings(findings)

    if not snapshot_path.exists():
        findings.append(Finding(rule_id="VAL-ID-101", severity="blocker", scope="bundle", reason_code="identity.resource_missing", message=f"missing snapshot: {snapshot_path.name}"))
        return sort_findings(findings)

    try:
        snapshot = read_safe_json(snapshot_path, label=snapshot_path.name)
    except Exception as exc:  # noqa: BLE001 - reported as a typed finding, not a crash
        findings.append(Finding(rule_id="VAL-ID-102", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message=str(exc)))
        return sort_findings(findings)

    if not isinstance(snapshot, dict):
        findings.append(Finding(rule_id="VAL-ID-103", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message="snapshot root must be a JSON object"))
        return sort_findings(findings)

    for error in iter_schema_errors("market-snapshot", snapshot):
        pointer = "/" + "/".join(str(p) for p in error.path)
        findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", json_pointer=pointer, message=error.message))
    if findings:
        return sort_findings(findings)

    identity = snapshot.get("snapshot_identity", {})
    expected_artifact_id = derive_artifact_id("market_snapshot", {
        "ticker": identity.get("ticker", ""), "as_of_date": snapshot.get("temporal_context", {}).get("as_of_date", ""), "context_id": identity.get("context_id", ""),
    })
    if snapshot.get("artifact_id") != expected_artifact_id:
        findings.append(Finding(rule_id="VAL-ID-004", severity="blocker", scope="artifact", reason_code="identity.reference_invalid", message="recomputed artifact_id does not match stored artifact_id"))

    manifest_refs = snapshot.get("source_manifest_refs", [])
    manifest_id = manifest_artifact_id(manifest)
    if not any(ref.get("artifact_id") == manifest_id for ref in manifest_refs):
        findings.append(Finding(rule_id="VAL-MI-002", severity="blocker", scope="artifact", reason_code="identity.reference_invalid", message="snapshot does not reference the supplied manifest's exact identity"))

    share_basis = snapshot.get("share_basis", {})
    try:
        from decimal import Decimal
        spot = Decimal(share_basis.get("spot_basic_shares_outstanding", "0"))
        has_issued = "issued_shares" in share_basis
        has_treasury = "treasury_shares" in share_basis
        if has_issued != has_treasury:
            findings.append(Finding(rule_id="VAL-MI-005", severity="blocker", scope="artifact", reason_code="capital.price_share_basis_mismatch", message="issued_shares and treasury_shares must either both be present or both be absent"))
        elif has_issued:
            issued = Decimal(share_basis["issued_shares"])
            treasury = Decimal(share_basis["treasury_shares"])
            if issued - treasury != spot:
                findings.append(Finding(rule_id="VAL-MI-005", severity="blocker", scope="artifact", reason_code="capital.price_share_basis_mismatch", message="issued_shares - treasury_shares does not recompute to spot_basic_shares_outstanding"))
        elif share_basis.get("derivation_method") != "direct_reported" or share_basis.get("reconciliation_status") != "direct_reported":
            findings.append(Finding(rule_id="VAL-MI-005", severity="blocker", scope="artifact", reason_code="capital.price_share_basis_mismatch", message="a direct outstanding-share basis must declare direct_reported derivation and reconciliation"))
        if spot <= 0:
            findings.append(Finding(rule_id="VAL-MI-005", severity="blocker", scope="artifact", reason_code="capital.nonpositive_basic_shares", message="spot_basic_shares_outstanding must be strictly positive"))
    except Exception:  # noqa: BLE001
        findings.append(Finding(rule_id="VAL-MI-005", severity="blocker", scope="artifact", reason_code="capital.price_share_basis_mismatch", message="share_basis values are not valid decimals"))

    return sort_findings(findings)
