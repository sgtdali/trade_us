"""Method and bundle confidence (docs/valuation-t66-01-*.md Section 13,
docs/valuation-t67-05-*.md Section 5).

T71-B scope decision (recorded, not silent): the full multi-dimension
data/model confidence model (source authority, freshness, directness,
accounting comparability, period coverage, provenance completeness,
cross-source consistency / method applicability, denominator stability,
cycle sensitivity, ...) is not implemented here. Confidence is instead a
real, but binary, critical-input-availability cap: ``high`` when the
method's required operands are all available, ``insufficient`` when the
method itself is not available -- "critical-min/cap policy, never an
arithmetic mean" (docs/valuation-t66-01-*.md Section 13.4) is honored at
this coarser granularity. This is narrower than the full contract, not a
contradiction of it.
"""

from __future__ import annotations

from typing import Any


def propagated_confidence(*, available: bool, policy_ref: str) -> dict[str, Any]:
    if available:
        return {
            "level": "high",
            "critical_dimension_refs": [],
            "limiting_factor_refs": [],
            "noncritical_gap_refs": [],
            "policy_ref": policy_ref,
            "rationale_code": "confidence.no_critical_gap",
        }
    return {
        "level": "insufficient",
        "critical_dimension_refs": ["required_operand"],
        "limiting_factor_refs": ["required_operand"],
        "noncritical_gap_refs": [],
        "policy_ref": policy_ref,
        "rationale_code": "confidence.critical_input_insufficient",
    }


def bundle_confidence(*, any_current_use_available: bool, policy_ref: str) -> dict[str, Any]:
    """Bundle-level confidence: capped by whether at least one current-use
    eligible method exists, never a mean over every configured row's own
    confidence (docs/valuation-t67-05-*.md Section 5's "combined confidence
    is always a critical-min/cap policy")."""
    return propagated_confidence(available=any_current_use_available, policy_ref=policy_ref)
