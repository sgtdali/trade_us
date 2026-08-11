"""Filesystem orchestration for the share-count/corporate-action
promotion bridge -- the only module in this package that touches disk.

Sequence: load ledger, share-count manifest, corporate-action manifest,
and policy -> pure engine (``policy.build_promotion``) -> schema-validate
every generated document -> transactional write.
"""

from __future__ import annotations

from pathlib import Path

from ...canonical import canonical_bytes
from ...market.registry import check_manifest_authorization, load_market_source_manifest
from ...safe_json import read_safe_json
from ...schemas import iter_schema_errors
from ...transaction import WriteTarget, check_transaction, execute_transaction
from ...validation.findings import Finding
from .errors import PromotionImmutabilityError, PromotionPolicyError, ShareCountError
from .ledger import load_ledger
from .models import PromotionPolicy, PromotionRunResult
from .policy import build_promotion

OBSERVATIONS_FILE = "observations.json"
CORPORATE_ACTIONS_FILE = "corporate-actions.json"
VALIDATION_FILE = "validation.json"
PROMOTION_MANIFEST_FILE = "promotion-manifest.json"


def load_promotion_policy(path: Path) -> tuple[dict, PromotionPolicy]:
    """Safely read and schema-validate a share-count promotion policy
    document."""
    if not path.exists():
        raise PromotionPolicyError(f"missing share-count promotion policy: {path.name}")
    document = read_safe_json(path, label=path.name)
    if not isinstance(document, dict):
        raise PromotionPolicyError(f"{path.name}: policy root must be a JSON object")

    schema_errors = list(iter_schema_errors("share-count-promotion-policy", document))
    if schema_errors:
        first = schema_errors[0]
        pointer = "/" + "/".join(str(p) for p in first.path)
        raise PromotionPolicyError(f"{path.name}: fails share-count-promotion-policy schema at {pointer}: {first.message}")

    return document, PromotionPolicy.from_dict(document)


def validate_ledger(ledger_path: Path) -> list[Finding]:
    """Load+structurally-parse the ledger -- the
    ``share-count ledger-validate`` CLI command's whole implementation.
    Raises :class:`LedgerError` for a structural problem (there is no
    domain-eligibility concept at the ledger level alone -- eligibility is
    evaluated at promotion time against an explicit as-of date/cutoff)."""
    load_ledger(ledger_path)
    return []


def validate_manifest(manifest_path: Path, *, ticker: str, as_of_date: str) -> list[Finding]:
    """Load the manifest, then return its authorization
    findings (empty means authorized)."""
    manifest = load_market_source_manifest(manifest_path)
    problems = check_manifest_authorization(manifest, ticker=ticker, as_of_date=as_of_date)
    return [
        Finding(rule_id="SHARE-AUTH-001", severity="blocker", scope="bundle", reason_code="authorization.manifest_rejected", message=p)
        for p in problems
    ]


def promote(
    *,
    ledger_path: Path,
    share_manifest_path: Path,
    corporate_action_manifest_path: Path,
    policy_path: Path,
    ticker: str,
    as_of_date: str,
    cutoff_instant: str,
    output_dir: Path,
    check_only: bool = False,
) -> PromotionRunResult:
    """Deterministic offline promotion: an authored share-count ledger +
    an official share-count market-source manifest + an official
    corporate-action market-source manifest + a promotion policy -> a
    T70-observation-compatible ``observations.json`` plus a governed
    ``corporate-actions.json`` bundle.

    Raises a :mod:`errors` subclass (bootstrap-class: cannot proceed at
    all) for a structurally untrusted ledger/manifest/policy, or an
    attempt to overwrite a byte-different immutable prior promotion run.
    Ordinary domain-eligibility failures (missing treasury record,
    non-reconciling values, ...) are never raised -- they are reported
    inside a still-written, ``overall_status: "invalid"`` promotion
    bundle via :class:`PromotionRunResult.ok`.
    """
    ledger = load_ledger(ledger_path)
    share_manifest = load_market_source_manifest(share_manifest_path)
    corporate_action_manifest = load_market_source_manifest(corporate_action_manifest_path)
    policy_doc, policy = load_promotion_policy(policy_path)

    outcome = build_promotion(
        ledger=ledger,
        share_manifest=share_manifest,
        corporate_action_manifest=corporate_action_manifest,
        policy=policy,
        policy_doc=policy_doc,
        ticker=ticker,
        as_of_date=as_of_date,
        cutoff_instant=cutoff_instant,
    )

    for schema_key, document in (
        ("market-observation-bundle", outcome.observations_doc),
        ("corporate-action-bundle", outcome.corporate_actions_doc),
        ("share-count-promotion-validation", outcome.validation_doc),
        ("share-count-promotion-manifest", outcome.promotion_manifest_doc),
    ):
        errors = list(iter_schema_errors(schema_key, document))
        if errors:
            raise ShareCountError(
                f"internal error: generated {schema_key} document failed its own schema "
                f"at {errors[0].message}"
            )

    targets = [
        WriteTarget(relative_path=OBSERVATIONS_FILE, content=canonical_bytes(outcome.observations_doc)),
        WriteTarget(relative_path=CORPORATE_ACTIONS_FILE, content=canonical_bytes(outcome.corporate_actions_doc)),
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
