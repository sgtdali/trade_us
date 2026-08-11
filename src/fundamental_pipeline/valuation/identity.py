"""Deterministic identity primitives: context IDs, artifact IDs, and
dependency hashes.

No filesystem path, current wall-clock time, username, hostname, process
ID, locale, or timezone participates in any derived identity. Same
semantic dimensions always produce the same ID/hash; a materially
different input always produces a different one.

Artifact ID namespaces (exact, per T70.3 and the T70-A coding-task
prompt's own binding section 10.2):

    market-snapshot:{ticker}:{as_of_date}:{context_id}
    valuation-inputs:{ticker}:{as_of_date}:{context_id}
    market-source-manifest:{subject}:{manifest_id}
    scenario-set:{ticker}:{as_of_date}:{context_id}  -- added by T72-A, same
    dimensional shape as valuation-inputs (context_id derived from a
    scenario-specific projection: ticker, valuation_as_of_date, purpose,
    financial_basis_ref, scenario_set_id, revision).

Deviation note: docs/valuation-t66-01-shared-definitions-specification.md
Section 4.2 separately gives a generic ``ft:<type>:sha256:<64-hex>``
pattern as "normatif" for generated artifact IDs. That pattern is
incompatible with the dimensional strings above (no ``ft:`` prefix, no
embedded content hash). The T70-A coding-task prompt's own Section 10.2
spells out the dimensional scheme verbatim and is the more specific,
directly-binding source for the three T70 artifact classes, so this
module implements that scheme. This is a recorded schema/identity
decision, not a silent resolution -- see the PR description and the
final implementation report's "Deviations or Contradictions" section.
"""

from __future__ import annotations

import hashlib
from typing import Mapping, Sequence

from .canonical import canonical_bytes
from .errors import IdentityError

_MARKET_SNAPSHOT = "market_snapshot"
_VALUATION_INPUTS = "valuation_inputs"
_MARKET_SOURCE_MANIFEST = "market_source_manifest"
_VALUATION_RESULTS = "valuation_results"
_VALUATION_COMPARISON = "valuation_comparison"

MARKET_SNAPSHOT_PURPOSES = frozenset({
    "current_valuation",
    "historical_valuation",
    "comparison",
    "diagnostic",
    "retrospective_reconstruction",
})

PRICE_MODE_PURPOSES: dict[str, frozenset[str]] = {
    "official_close": frozenset({"current_valuation", "comparison"}),
    "intraday": frozenset({"current_valuation", "comparison"}),
    "historical_close": frozenset({"historical_valuation", "comparison", "retrospective_reconstruction"}),
    "diagnostic_reference": frozenset({"diagnostic"}),
}


def derive_context_id(context_projection: Mapping) -> str:
    """Derive ``ctx-<24 lowercase hex chars>`` from the closed semantic
    context projection (ticker, as_of_date, cutoff_instant,
    reporting_currency, share_count_basis, financial_period_refs). The
    projection is hashed via the same canonical byte encoding used
    everywhere else in the valuation namespace."""
    digest = hashlib.sha256(canonical_bytes(dict(context_projection))).hexdigest()
    return f"ctx-{digest[:24]}"


def derive_artifact_id(artifact_type: str, dimensions: Mapping) -> str:
    """Derive a deterministic artifact ID for one of the three T70
    artifact namespaces. ``dimensions`` must contain exactly the fields
    the namespace requires; nothing else participates."""
    if artifact_type == _MARKET_SNAPSHOT:
        return _require_and_join("market-snapshot", dimensions, ("ticker", "as_of_date", "context_id"))
    if artifact_type == _VALUATION_INPUTS:
        return _require_and_join("valuation-inputs", dimensions, ("ticker", "as_of_date", "context_id"))
    if artifact_type == _MARKET_SOURCE_MANIFEST:
        return _require_and_join("market-source-manifest", dimensions, ("ticker", "manifest_id"))
    if artifact_type == _VALUATION_RESULTS:
        return _require_and_join("valuation-results", dimensions, ("ticker", "as_of_date", "context_id"))
    if artifact_type == _VALUATION_COMPARISON:
        return _require_and_join("valuation-comparison", dimensions, ("comparison_type", "context_id"))
    raise IdentityError(f"unknown artifact_type for ID derivation: {artifact_type!r}")


def _require_and_join(prefix: str, dimensions: Mapping, fields: Sequence[str]) -> str:
    values = []
    for field in fields:
        if field not in dimensions or dimensions[field] in (None, ""):
            raise IdentityError(f"{prefix}: missing required ID dimension {field!r}")
        value = dimensions[field]
        if not isinstance(value, str):
            raise IdentityError(f"{prefix}: ID dimension {field!r} must be a string, got {type(value).__name__}")
        if ":" in value:
            raise IdentityError(f"{prefix}: ID dimension {field!r} may not contain ':' ({value!r})")
        values.append(value)
    return ":".join([prefix, *values])
