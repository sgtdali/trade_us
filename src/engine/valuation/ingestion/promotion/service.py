"""Filesystem orchestration for the EOD-close promotion bridge -- the only
module in this package that touches disk.

Sequence (see the repository's temporary-use-exception decision
document): structural bundle validation -> replay --check (no drift) ->
load manifest and policy -> pure engine (``policy.build_promotion``)
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
from ..eod.service import (
    BUNDLE_MANIFEST_FILE,
    PRICE_SERIES_FILE,
    PROVIDER_EXTRACT_FILE,
    REQUEST_FILE,
    replay_bundle as replay_ingestion_bundle,
    validate_bundle as validate_ingestion_bundle,
)
from .errors import PromotionError, PromotionImmutabilityError, PromotionPolicyError, SourceBundleUntrustedError
from .models import PromotionPolicy, PromotionRunResult
from .policy import build_promotion
from .validation import check_manifest_authorization_findings

OBSERVATIONS_FILE = "observations.json"
VALIDATION_FILE = "validation.json"
PROMOTION_MANIFEST_FILE = "promotion-manifest.json"


def load_promotion_policy(path: Path) -> tuple[dict, PromotionPolicy]:
    """Safely read and schema-validate a promotion policy document."""
    if not path.exists():
        raise PromotionPolicyError(f"missing promotion policy: {path.name}")
    document = read_safe_json(path, label=path.name)
    if not isinstance(document, dict):
        raise PromotionPolicyError(f"{path.name}: policy root must be a JSON object")

    schema_errors = list(iter_schema_errors("eod-close-promotion-policy", document))
    if schema_errors:
        first = schema_errors[0]
        pointer = "/" + "/".join(str(p) for p in first.path)
        raise PromotionPolicyError(f"{path.name}: fails eod-close-promotion-policy schema at {pointer}: {first.message}")

    return document, PromotionPolicy.from_dict(document)


def _assert_bundle_trustworthy(bundle_root: Path) -> None:
    structural_findings = validate_ingestion_bundle(bundle_root)
    if has_blocking(structural_findings):
        messages = "; ".join(f"{f.rule_id}: {f.message}" for f in structural_findings)
        raise SourceBundleUntrustedError(f"source ingestion bundle failed structural validation: {messages}")

    transaction_result, _replay_findings = replay_ingestion_bundle(bundle_root, check_only=True)
    if transaction_result.status == "drift":
        changed = [d.relative_path for d in transaction_result.diffs]
        raise SourceBundleUntrustedError(
            f"source ingestion bundle failed replay re-derivation (drift in {sorted(changed)}); "
            "promotion never reads economic data out of a bundle it cannot reproduce byte-for-byte "
            "from its own immutable provider-extract.json"
        )


def validate_manifest(manifest_path: Path, *, ticker: str, as_of_date: str) -> list[Finding]:
    """Load the manifest, then return its authorization
    findings (empty means authorized) -- the ``price manifest-validate``
    CLI command's whole implementation."""
    manifest = load_market_source_manifest(manifest_path)
    return check_manifest_authorization_findings(manifest, ticker=ticker, as_of_date=as_of_date)


def promote(
    *,
    bundle_root: Path,
    manifest_path: Path,
    policy_path: Path,
    ticker: str,
    as_of_date: str,
    cutoff_instant: str,
    effective_at: str,
    output_dir: Path,
    check_only: bool = False,
) -> PromotionRunResult:
    """Deterministic offline promotion: validated EOD ingestion bundle +
    market-source manifest + promotion policy -> a T70-observation-
    compatible ``observations.json``/``validation.json``/
    ``promotion-manifest.json`` triple.

    Raises a :mod:`errors` subclass (bootstrap-class: cannot proceed at
    all) for a structurally untrusted bundle, an unloadable manifest/
    policy, or an attempt to overwrite a byte-different immutable prior
    promotion run. Ordinary domain-eligibility failures (research-only
    bundle, expired authorization, quarantined-only rows, ...) are never
    raised -- they are reported inside a still-written, ``overall_status:
    "invalid"`` promotion bundle via :class:`PromotionRunResult.ok`.
    """
    _assert_bundle_trustworthy(bundle_root)

    bundle_request_doc = read_safe_json(bundle_root / REQUEST_FILE, label=REQUEST_FILE)
    bundle_manifest_doc = read_safe_json(bundle_root / BUNDLE_MANIFEST_FILE, label=BUNDLE_MANIFEST_FILE)
    provider_extract_doc = read_safe_json(bundle_root / PROVIDER_EXTRACT_FILE, label=PROVIDER_EXTRACT_FILE)
    price_series_doc = read_safe_json(bundle_root / PRICE_SERIES_FILE, label=PRICE_SERIES_FILE)

    manifest = load_market_source_manifest(manifest_path)
    policy_doc, policy = load_promotion_policy(policy_path)

    outcome = build_promotion(
        bundle_request_doc=bundle_request_doc,
        bundle_manifest_doc=bundle_manifest_doc,
        provider_extract_doc=provider_extract_doc,
        price_series_doc=price_series_doc,
        manifest=manifest,
        policy_doc=policy_doc,
        policy=policy,
        ticker=ticker,
        as_of_date=as_of_date,
        cutoff_instant=cutoff_instant,
        effective_at=effective_at,
    )

    for schema_key, document in (
        ("market-observation-bundle", outcome.observations_doc),
        ("eod-close-promotion-validation", outcome.validation_doc),
        ("eod-close-promotion-manifest", outcome.promotion_manifest_doc),
    ):
        errors = list(iter_schema_errors(schema_key, document))
        if errors:
            raise PromotionError(
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
        raise PromotionImmutabilityError(
            f"--output-dir already contains different promotion output for: {changed}; "
            "a promotion run is immutable once written -- rerunning with identical inputs is a "
            "no-op, but different inputs must target a new --output-dir"
        )

    transaction_result = check_result if check_only else execute_transaction(output_dir, targets)
    return PromotionRunResult(outcome=outcome, transaction=transaction_result)
