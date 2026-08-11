"""Market-source manifest loading, identity, and authorization gate
(docs/valuation-t70-04-market-registry-snapshot-specification.md Section 4).

Before any observation may be selected, its declared manifest must:

1. parse safely and validate against ``market-source-manifest.schema.json``;
2. produce an exact governed identity (``manifest_version`` present -- a
   manifest that cannot produce this identity fails closed, it never
   silently invents a version);
3. have ``lifecycle_status == "active"``;
4. have an ``allowed_use.scope`` compatible with internal valuation
   (``internal_valuation`` only -- ``internal_research_only`` and
   ``not_licensed`` are both rejected for this use);
5. carry non-empty license evidence, retention policy, and revision
   policy (all structurally required by the schema already);
6. have ``effective_from <= as_of_date`` and (``effective_to`` is null or
   ``as_of_date <= effective_to``).

A schema-valid but unauthorized manifest is not eligible -- this module
never treats "parses" as "usable".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import DuplicateKeyError, MarketResolutionError, ResourceLimitError
from ..identity import derive_artifact_id
from ..safe_json import read_safe_json
from ..schemas import iter_schema_errors

_ELIGIBLE_USE_SCOPES = ("internal_valuation",)


def load_market_source_manifest(path: Path, *, label: str | None = None) -> dict[str, Any]:
    """Safely read and schema-validate a market-source manifest document.
    Raises :class:`MarketResolutionError` (never a raw parsing/KeyError)
    for any structural problem."""
    diagnostic_label = label if label is not None else path.name
    if not path.exists():
        raise MarketResolutionError(f"missing market-source manifest: {diagnostic_label}")
    try:
        document = read_safe_json(path, label=diagnostic_label)
    except (ResourceLimitError, DuplicateKeyError) as exc:
        raise MarketResolutionError(f"{diagnostic_label}: {exc}") from exc
    if not isinstance(document, dict):
        raise MarketResolutionError(f"{diagnostic_label}: manifest root must be a JSON object")

    schema_errors = list(iter_schema_errors("market-source-manifest", document))
    if schema_errors:
        first = schema_errors[0]
        pointer = "/" + "/".join(str(p) for p in first.path)
        raise MarketResolutionError(f"{diagnostic_label}: fails market-source-manifest schema at {pointer}: {first.message}")

    if (document.get("dataset_identity") or {}).get("dataset_kind") == "fx":
        pair_identity = document.get("pair_identity") or {}
        pair_id, base, quote = pair_identity.get("pair_id"), pair_identity.get("base_currency"), pair_identity.get("quote_currency")
        if pair_id != f"{base}/{quote}":
            raise MarketResolutionError(
                f"{diagnostic_label}: pair_identity.pair_id {pair_id!r} is inconsistent with "
                f"base_currency/quote_currency ({base!r}/{quote!r}); pair_id must be exactly 'BASE/QUOTE'"
            )
        if base == quote:
            raise MarketResolutionError(f"{diagnostic_label}: pair_identity base_currency and quote_currency must not be equal, both are {base!r}")

    return document


def _pair_slug(pair_id: str) -> str:
    """``USD/TRY`` -> ``USD-TRY`` -- the canonical filesystem/identity-safe
    slug for an FX pair (a single path segment/ID dimension may never
    contain ``/``)."""
    return pair_id.replace("/", "-")


def manifest_artifact_id(manifest: dict[str, Any]) -> str:
    """Derive the manifest's exact governed identity:
    ``market-source-manifest:{subject}:{manifest_id}`` for an equity
    (price/share_count/corporate_action) manifest, or
    ``market-source-manifest:{BASE-QUOTE}:{manifest_version}`` for an FX
    manifest (``pair_identity.pair_id`` slugified). Fails closed with
    :class:`MarketResolutionError` when ``manifest_version`` or the
    dataset-appropriate subject identity is absent -- a missing dimension
    is never silently invented."""
    manifest_version = manifest.get("manifest_version")
    if not manifest_version:
        raise MarketResolutionError(
            f"manifest {manifest.get('manifest_id')!r}: cannot derive an exact identity without "
            "'manifest_version'; this is a fail-closed condition, not an invented default"
        )
    dataset_kind = (manifest.get("dataset_identity") or {}).get("dataset_kind")
    if dataset_kind == "fx":
        pair_id = (manifest.get("pair_identity") or {}).get("pair_id")
        if not pair_id:
            raise MarketResolutionError(f"manifest {manifest.get('manifest_id')!r}: FX manifest is missing pair_identity.pair_id")
        subject = _pair_slug(pair_id)
    else:
        subject = manifest.get("ticker")
        if not subject:
            raise MarketResolutionError(f"manifest {manifest.get('manifest_id')!r}: equity manifest is missing 'ticker'")
    return derive_artifact_id("market_source_manifest", {"ticker": subject, "manifest_id": manifest.get("manifest_id")})


def market_source_manifest_relative_path(*, ticker: str | None = None, pair_id: str | None = None, manifest_id: str, primary: bool = False) -> str:
    """The one governed canonical path function for a market-source
    manifest reference -- never scattered inline f-string path
    construction. Exactly one of ``ticker``/``pair_id`` must be supplied.

    Equity (unchanged from before this FX migration):

        data/market-source-manifests/{TICKER}.json                    (primary=True)
        data/market-source-manifests/{TICKER}.{manifest_id}.json      (primary=False)

    FX:

        data/market-source-manifests/fx/{BASE-QUOTE}.{manifest_id}.json
    """
    if (ticker is None) == (pair_id is None):
        raise MarketResolutionError("market_source_manifest_relative_path: exactly one of ticker/pair_id must be supplied")
    if pair_id is not None:
        pair_prefix = pair_id.lower().replace("/", "") + "-"
        filename_suffix = manifest_id[len(pair_prefix):] if manifest_id.startswith(pair_prefix) else manifest_id
        return f"data/market-source-manifests/fx/{_pair_slug(pair_id)}.{filename_suffix}.json"
    if primary:
        return f"data/market-source-manifests/{ticker}.json"
    return f"data/market-source-manifests/{ticker}.{manifest_id}.json"


def check_manifest_authorization(
    manifest: dict[str, Any],
    *,
    ticker: str | None = None,
    pair: str | None = None,
    as_of_date: str,
) -> list[str]:
    """Return an ordered list of human-readable authorization violations
    (empty means authorized). Structural schema validity is assumed to
    already hold (call :func:`load_market_source_manifest` first).

    Exactly one of ``ticker``/``pair`` must be supplied -- ``pair`` checks
    an FX manifest's ``pair_identity.pair_id`` against the expected
    ``BASE/QUOTE`` subject instead of ``ticker`` against the equity
    ``ticker`` field. Every other check (lifecycle, scope, evidence, and
    effective window) is dataset-kind-agnostic and applies identically to
    both."""
    if (ticker is None) == (pair is None):
        raise MarketResolutionError("check_manifest_authorization: exactly one of ticker/pair must be supplied")

    problems: list[str] = []

    if pair is not None:
        actual_pair = (manifest.get("pair_identity") or {}).get("pair_id")
        if actual_pair != pair:
            problems.append(f"manifest pair_identity.pair_id {actual_pair!r} does not match requested pair {pair!r}")
    else:
        if manifest.get("ticker") != ticker:
            problems.append(f"manifest ticker {manifest.get('ticker')!r} does not match requested ticker {ticker!r}")

    if manifest.get("lifecycle_status") != "active":
        problems.append(f"manifest lifecycle_status {manifest.get('lifecycle_status')!r} is not 'active'")

    allowed_use = manifest.get("allowed_use") or {}
    scope = allowed_use.get("scope")
    if scope not in _ELIGIBLE_USE_SCOPES:
        problems.append(f"manifest allowed_use.scope {scope!r} is not compatible with internal valuation")

    if not (manifest.get("license_evidence") or {}).get("evidence_ref"):
        problems.append("manifest license_evidence.evidence_ref is missing")
    if not (manifest.get("retention_policy") or {}).get("policy_id"):
        problems.append("manifest retention_policy.policy_id is missing")
    if not (manifest.get("revision_policy") or {}).get("policy_id"):
        problems.append("manifest revision_policy.policy_id is missing")

    effective_from = manifest.get("effective_from")
    if effective_from is not None and as_of_date < effective_from:
        problems.append(f"as_of_date {as_of_date!r} is before manifest effective_from {effective_from!r}")
    effective_to = manifest.get("effective_to")
    if effective_to and as_of_date > effective_to:
        problems.append(f"as_of_date {as_of_date!r} is after manifest effective_to {effective_to!r}")

    return problems
