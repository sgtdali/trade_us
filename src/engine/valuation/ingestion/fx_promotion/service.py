"""Filesystem orchestration for the FX-close promotion bridge -- the only
module in this package that touches disk.

Structurally parallel to ``ingestion.promotion.service``. Sequence:
structural bundle validation -> replay --check (no drift) -> load
manifest and policy -> pure engine (``policy.build_fx_promotion``)
-> schema-validate every generated document -> transactional write.
"""

from __future__ import annotations

from pathlib import Path

from ...canonical import canonical_bytes
from ...market.registry import load_market_source_manifest
from ...safe_json import read_safe_json
from ...schemas import iter_schema_errors
from ...transaction import WriteTarget, check_transaction, execute_transaction
from ...validation.findings import Finding, has_blocking
from ..fx.service import (
    BUNDLE_MANIFEST_FILE,
    PROVIDER_EXTRACT_FILE,
    RATE_SERIES_FILE,
    REQUEST_FILE,
    replay_fx_bundle as replay_ingestion_bundle,
    validate_fx_bundle as validate_ingestion_bundle,
)
from .errors import FxPromotionError, FxPromotionImmutabilityError, FxPromotionPolicyError, FxSourceBundleUntrustedError
from .models import FxPromotionPolicy, FxPromotionRunResult
from .policy import build_fx_promotion
from .validation import check_manifest_authorization_findings

OBSERVATIONS_FILE = "observations.json"
VALIDATION_FILE = "validation.json"
PROMOTION_MANIFEST_FILE = "promotion-manifest.json"


def load_fx_promotion_policy(path: Path) -> tuple[dict, FxPromotionPolicy]:
    """Safely read and schema-validate an FX promotion policy document."""
    if not path.exists():
        raise FxPromotionPolicyError(f"missing FX promotion policy: {path.name}")
    document = read_safe_json(path, label=path.name)
    if not isinstance(document, dict):
        raise FxPromotionPolicyError(f"{path.name}: policy root must be a JSON object")

    schema_errors = list(iter_schema_errors("fx-close-promotion-policy", document))
    if schema_errors:
        first = schema_errors[0]
        pointer = "/" + "/".join(str(p) for p in first.path)
        raise FxPromotionPolicyError(f"{path.name}: fails fx-close-promotion-policy schema at {pointer}: {first.message}")

    return document, FxPromotionPolicy.from_dict(document)


def _assert_bundle_trustworthy(bundle_root: Path) -> None:
    structural_findings = validate_ingestion_bundle(bundle_root)
    if has_blocking(structural_findings):
        messages = "; ".join(f"{f.rule_id}: {f.message}" for f in structural_findings)
        raise FxSourceBundleUntrustedError(f"source FX ingestion bundle failed structural validation: {messages}")

    transaction_result, _replay_findings = replay_ingestion_bundle(bundle_root, check_only=True)
    if transaction_result.status == "drift":
        changed = [d.relative_path for d in transaction_result.diffs]
        raise FxSourceBundleUntrustedError(
            f"source FX ingestion bundle failed replay re-derivation (drift in {sorted(changed)}); "
            "promotion never reads economic data out of a bundle it cannot reproduce byte-for-byte "
            "from its own immutable fx-provider-extract.json"
        )


def validate_manifest(manifest_path: Path, *, pair_id: str, as_of_date: str) -> list[Finding]:
    """Load+hash-verify the manifest, then return its authorization
    findings (empty means authorized) -- the ``fx manifest-validate`` CLI
    command's whole implementation."""
    manifest = load_market_source_manifest(manifest_path)
    return check_manifest_authorization_findings(manifest, pair_id=pair_id, as_of_date=as_of_date)


def promote(
    *,
    bundle_root: Path,
    manifest_path: Path,
    policy_path: Path,
    pair_id: str,
    as_of_date: str,
    cutoff_instant: str,
    effective_at: str,
    output_dir: Path,
    check_only: bool = False,
) -> FxPromotionRunResult:
    """Deterministic offline promotion: validated FX ingestion bundle +
    market-source manifest + promotion policy -> a T70-observation-
    compatible ``observations.json``/``validation.json``/
    ``promotion-manifest.json`` triple.

    Raises a :mod:`errors` subclass (bootstrap-class: cannot proceed at
    all) for a structurally untrusted bundle, an unloadable manifest/
    policy, or an attempt to overwrite a byte-different immutable prior
    promotion run. Ordinary domain-eligibility failures are never raised
    -- they are reported inside a still-written, ``overall_status:
    "invalid"`` promotion bundle via :class:`FxPromotionRunResult.ok`.
    """
    _assert_bundle_trustworthy(bundle_root)

    bundle_request_doc = read_safe_json(bundle_root / REQUEST_FILE, label=REQUEST_FILE)
    bundle_manifest_doc = read_safe_json(bundle_root / BUNDLE_MANIFEST_FILE, label=BUNDLE_MANIFEST_FILE)
    provider_extract_doc = read_safe_json(bundle_root / PROVIDER_EXTRACT_FILE, label=PROVIDER_EXTRACT_FILE)
    rate_series_doc = read_safe_json(bundle_root / RATE_SERIES_FILE, label=RATE_SERIES_FILE)

    manifest = load_market_source_manifest(manifest_path)
    policy_doc, policy = load_fx_promotion_policy(policy_path)

    outcome = build_fx_promotion(
        bundle_request_doc=bundle_request_doc,
        bundle_manifest_doc=bundle_manifest_doc,
        provider_extract_doc=provider_extract_doc,
        rate_series_doc=rate_series_doc,
        manifest=manifest,
        policy_doc=policy_doc,
        policy=policy,
        pair_id=pair_id,
        as_of_date=as_of_date,
        cutoff_instant=cutoff_instant,
        effective_at=effective_at,
    )

    for schema_key, document in (
        ("market-observation-bundle", outcome.observations_doc),
        ("fx-close-promotion-validation", outcome.validation_doc),
        ("fx-close-promotion-manifest", outcome.promotion_manifest_doc),
    ):
        errors = list(iter_schema_errors(schema_key, document))
        if errors:
            raise FxPromotionError(
                f"internal error: generated {schema_key} document failed its own schema "
                f"at {errors[0].message}"
            )

    targets = [
        WriteTarget(relative_path=OBSERVATIONS_FILE, content=canonical_bytes(outcome.observations_doc)),
        WriteTarget(relative_path=VALIDATION_FILE, content=canonical_bytes(outcome.validation_doc)),
        WriteTarget(relative_path=PROMOTION_MANIFEST_FILE, content=canonical_bytes(outcome.promotion_manifest_doc)),
    ]

    check_result = check_transaction(output_dir, targets)
    changed = sorted(d.relative_path for d in check_result.diffs if d.state == "changed")
    if changed:
        raise FxPromotionImmutabilityError(
            f"--output-dir already contains different promotion output for: {changed}; "
            "a promotion run is immutable once written -- rerunning with identical inputs is a "
            "no-op, but different inputs must target a new --output-dir"
        )

    transaction_result = check_result if check_only else execute_transaction(output_dir, targets)
    return FxPromotionRunResult(outcome=outcome, transaction=transaction_result)
