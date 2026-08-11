"""Authored valuation catalog definitions.

Kept by domain so catalog content remains reviewable without changing its
canonical structure.
"""

from __future__ import annotations

from typing import Any

_MARKET_INPUT_POLICY_ENTRIES: list[dict[str, Any]] = [
    {
        "entry_id": "val.policy.market_input.cutoff_strict",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Strict cutoff eligibility",
        "source_contract_refs": ["docs/valuation-t70-02-schema-catalog-version-lock-specification.md#8.2"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "market_input.cutoff",
            "rule": "An observation with information_available_at strictly after the governed cutoff_instant is never eligible for selection, regardless of authority or freshness.",
            "no_implicit_latest": True,
        },
    },
    {
        "entry_id": "val.policy.market_input.price_close_or_prior",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Close-or-prior price selection",
        "source_contract_refs": ["docs/valuation-t70-02-schema-catalog-version-lock-specification.md#8.2"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "market_input.price_selection",
            "rule": "Prefer the official close for the most recent eligible session; if unavailable, fall back to the most recent prior eligible close under the cutoff. No averaging across sessions or sources.",
            "averaging_fallback_forbidden": True,
        },
    },
    {
        "entry_id": "val.policy.market_input.share_count_contextual",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Contextual share count basis",
        "source_contract_refs": ["docs/valuation-t70-02-schema-catalog-version-lock-specification.md#8.2"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "market_input.share_count",
            "rule": "Basis is spot_basic_shares_outstanding, reconciled from issued_shares minus treasury_shares as of the same effective date as the selected price observation.",
        },
    },
    {
        "entry_id": "val.policy.market_input.fx_direct_then_inverse",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Direct-then-inverse FX path selection",
        "source_contract_refs": ["docs/valuation-t70-02-schema-catalog-version-lock-specification.md#8.2"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "market_input.fx_path",
            "rule": "Prefer a direct quoted rate; if unavailable, use its exact inverse; a triangulated path through exactly one pivot currency is allowed only when neither a direct nor inverse quote is available.",
        },
    },
    {
        "entry_id": "val.policy.market_input.freshness_default",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Default freshness classification",
        "source_contract_refs": ["docs/valuation-t70-02-schema-catalog-version-lock-specification.md#8.2"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "market_input.freshness",
            "rule": "Freshness state (fresh/acceptable/stale/expired/unknown) is classified per observation kind against T04-owned threshold tables, pinned by version; thresholds themselves are not redefined here.",
        },
    },
    {
        "entry_id": "val.policy.market_input.conflict_authority_first",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Authority-first conflict resolution",
        "source_contract_refs": ["docs/valuation-t70-02-schema-catalog-version-lock-specification.md#8.2"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "market_input.conflict",
            "rule": "Among independent conflicting candidate observations for the same field, prefer the higher authority_class; a same-authority-class conflict is never resolved by averaging and is reported as unresolved_blocking or unresolved_diagnostic per materiality.",
            "averaging_fallback_forbidden": True,
        },
    },
    {
        "entry_id": "val.policy.market_input.override_governed",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Governed manual override",
        "source_contract_refs": ["docs/valuation-t70-02-schema-catalog-version-lock-specification.md#8.2"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "market_input.override",
            "rule": "A selection may only be overridden by explicit, authored, provenance-preserving metadata; an override's rationale and original candidate are never discarded.",
        },
    },
]

# ---------------------------------------------------------------------------
# 3. valuation.policies.status_confidence_assessment (T70-A subset only:
#    status/freshness/confidence vocabulary and precedence needed by the
#    two schemas and base validation. The nine-dimension assessment
#    runtime itself (docs/valuation-t67-05-*.md Sections 8-13) is
#    out of scope for T70-A and intentionally not encoded here.)
# ---------------------------------------------------------------------------

_STATUS_CONFIDENCE_POLICY_ENTRIES: list[dict[str, Any]] = [
    {
        "entry_id": "val.policy.status.method_status_precedence",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Method/field status precedence order",
        "source_contract_refs": ["docs/valuation-t67-01-catalog-meta-contract.md#10", "docs/valuation-t67-05-status-confidence-assessment-policy-catalog.md#4"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "status.precedence",
            "ordered_precedence": [
                {"rank": 1, "status": "calculation_blocked", "trigger": "structural/version/identity conflict"},
                {"rank": 2, "status": "not_applicable", "trigger": "design/company mismatch"},
                {"rank": 3, "status": "insufficient_data", "trigger": "required contract coverage absent"},
                {"rank": 4, "status": "unavailable", "trigger": "single required observation absent"},
                {"rank": 5, "status": "not_meaningful", "trigger": "economic interpretation invalid"},
                {"rank": 6, "status": "not_comparable", "trigger": "comparison-only incompatibility"},
                {"rank": 7, "status": "available", "trigger": "all gates pass"},
            ],
        },
    },
    {
        "entry_id": "val.policy.status.freshness_state_vocab",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Freshness state vocabulary",
        "source_contract_refs": ["docs/valuation-t67-05-status-confidence-assessment-policy-catalog.md#2"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": ["fresh", "acceptable", "stale", "expired", "unknown"],
        },
    },
    {
        "entry_id": "val.policy.status.confidence_level_vocab",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Confidence level vocabulary",
        "source_contract_refs": ["docs/valuation-t67-05-status-confidence-assessment-policy-catalog.md#2"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": ["high", "medium", "low", "insufficient"],
        },
    },
    {
        "entry_id": "val.policy.status.confidence_propagation",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Criticality-based confidence propagation",
        "source_contract_refs": ["docs/valuation-t67-05-status-confidence-assessment-policy-catalog.md#5"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "confidence.propagation",
            "rules": [
                "A critical input at insufficient confidence forces the output to insufficient (canonical publication blocked).",
                "A critical input at low confidence caps the output at low.",
                "A critical input at minimum medium plus a material low elsewhere caps the output at medium.",
                "A contextual-only (non-critical) low does not automatically downgrade the output, but creates an explicit disclosure.",
                "Combined confidence is always a critical-min/cap policy, never an arithmetic mean.",
            ],
        },
    },
    {
        "entry_id": "val.policy.status.current_use_capability_propagation",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Freshness to current-use capability propagation",
        "source_contract_refs": ["docs/valuation-t67-05-status-confidence-assessment-policy-catalog.md#3"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "current_use.capability",
            "mapping": [
                {"worst_required_freshness": "fresh", "current_use_state": "canonical_current"},
                {"worst_required_freshness": "acceptable", "current_use_state": "current_with_disclosure"},
                {"worst_required_freshness": "stale", "current_use_state": "diagnostic_only"},
                {"worst_required_freshness": "expired", "current_use_state": "blocked"},
                {"worst_required_freshness": "unknown", "current_use_state": "blocked"},
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# 5. valuation.policies.applicability (T71-A: catalog content only -- the
#    T71-B router that resolves these against a company/ticker at runtime
#    does not exist yet in this PR).
# ---------------------------------------------------------------------------


def _applicability_entry(
    *,
    entry_id: str,
    label: str,
    ticker: str,
    company_type: str,
    sector_module: str,
    method_id: str,
    outcome: str,
    requires: list[str],
    source_contract_refs: list[str],
) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": label,
        "source_contract_refs": source_contract_refs,
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "applicability.company_method",
            "selector": {"ticker": ticker, "company_type": company_type, "sector_module": sector_module},
            "method_id": method_id,
            "outcome": outcome,
            "requires": requires,
        },
    }


_APPLICABILITY_POLICY_ENTRIES: list[dict[str, Any]] = [
    _applicability_entry(
        entry_id="val.policy.applicability.thyao.ev_ebitdar",
        label="THYAO: EV/EBITDAR lease-inclusive is primary",
        ticker="THYAO", company_type="standard_corporate", sector_module="aviation",
        method_id="val.method.ev_to_ebitdar.aviation_lease_inclusive", outcome="applicable_primary",
        requires=["capital.ev.lease_inclusive.available", "metric.canonical_aviation_ebitdar.available", "lease.reconciliation.passed"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#7"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.thyao.pe",
        label="THYAO: P/E is secondary",
        ticker="THYAO", company_type="standard_corporate", sector_module="aviation",
        method_id="val.method.pe.reported_parent", outcome="applicable_secondary",
        requires=["metric.parent_earnings.true_ttm.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#7"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.thyao.earnings_yield",
        label="THYAO: earnings yield is a diagnostic sibling of P/E",
        ticker="THYAO", company_type="standard_corporate", sector_module="aviation",
        method_id="val.method.earnings_yield.reported_parent", outcome="applicable_diagnostic",
        requires=["metric.parent_earnings.true_ttm.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#7"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.thyao.fcf_after_lease",
        label="THYAO: after-lease FCF yield is secondary/conditional",
        ticker="THYAO", company_type="standard_corporate", sector_module="aviation",
        method_id="val.method.fcf_yield.after_lease_equity", outcome="applicable_secondary",
        requires=["lease.principal.classification.complete"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#7"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.thyao.fcf_standard",
        label="THYAO: standard FCF yield is diagnostic",
        ticker="THYAO", company_type="standard_corporate", sector_module="aviation",
        method_id="val.method.fcf_yield.standard_equity", outcome="applicable_diagnostic",
        requires=["metric.standard_fcf.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#7"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.thyao.ev_ebit",
        label="THYAO: EV/EBIT lease-compatible is diagnostic",
        ticker="THYAO", company_type="standard_corporate", sector_module="aviation",
        method_id="val.method.ev_to_ebit.core", outcome="applicable_diagnostic",
        requires=["metric.core_ebit.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#7"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.thyao.pb",
        label="THYAO: P/B is diagnostic",
        ticker="THYAO", company_type="standard_corporate", sector_module="aviation",
        method_id="val.method.price_to_book.parent_equity", outcome="applicable_diagnostic",
        requires=["metric.parent_equity.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#7"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.thyao.ev_ebitda",
        label="THYAO: EV/EBITDA is conditional diagnostic (never primary)",
        ticker="THYAO", company_type="standard_corporate", sector_module="aviation",
        method_id="val.method.ev_to_ebitda.canonical", outcome="conditional_data",
        requires=["metric.canonical_ebitda.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#7"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.thyao.dividend_yield",
        label="THYAO: dividend yield is conditional on governed event data",
        ticker="THYAO", company_type="standard_corporate", sector_module="aviation",
        method_id="val.method.dividend_yield.cash_declared_paid", outcome="conditional_data",
        requires=["distribution.trailing_paid_history.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#7"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.eregl.pb",
        label="EREGL: P/B is primary/secondary",
        ticker="EREGL", company_type="standard_corporate", sector_module="generic",
        method_id="val.method.price_to_book.parent_equity", outcome="applicable_primary",
        requires=["metric.parent_equity.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#9"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.eregl.fcf_standard",
        label="EREGL: standard FCF yield is primary/secondary",
        ticker="EREGL", company_type="standard_corporate", sector_module="generic",
        method_id="val.method.fcf_yield.standard_equity", outcome="applicable_primary",
        requires=["metric.standard_fcf.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#9"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.eregl.ev_ebit",
        label="EREGL: EV/EBIT lease-exclusive is primary/secondary",
        ticker="EREGL", company_type="standard_corporate", sector_module="generic",
        method_id="val.method.ev_to_ebit.core", outcome="applicable_primary",
        requires=["metric.core_ebit.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#9"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.eregl.pe",
        label="EREGL: P/E is secondary",
        ticker="EREGL", company_type="standard_corporate", sector_module="generic",
        method_id="val.method.pe.reported_parent", outcome="applicable_secondary",
        requires=["metric.parent_earnings.true_ttm.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#9"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.eregl.earnings_yield",
        label="EREGL: earnings yield is a diagnostic sibling of P/E",
        ticker="EREGL", company_type="standard_corporate", sector_module="generic",
        method_id="val.method.earnings_yield.reported_parent", outcome="applicable_diagnostic",
        requires=["metric.parent_earnings.true_ttm.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#9"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.eregl.ev_ebitda",
        label="EREGL: EV/EBITDA is conditional until canonical EBITDA resolved",
        ticker="EREGL", company_type="standard_corporate", sector_module="generic",
        method_id="val.method.ev_to_ebitda.canonical", outcome="conditional_data",
        requires=["metric.canonical_ebitda.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#9"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.eregl.fcf_after_lease",
        label="EREGL: after-lease FCF yield is diagnostic conditional",
        ticker="EREGL", company_type="standard_corporate", sector_module="generic",
        method_id="val.method.fcf_yield.after_lease_equity", outcome="applicable_diagnostic",
        requires=["lease.principal.classification.complete"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#9"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.eregl.ev_ebitdar_incl",
        label="EREGL: lease-inclusive EV variant is diagnostic conditional",
        ticker="EREGL", company_type="standard_corporate", sector_module="generic",
        method_id="val.method.ev_to_ebitdar.aviation_lease_inclusive", outcome="not_applicable",
        requires=[],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#9"],
    ),
    _applicability_entry(
        entry_id="val.policy.applicability.eregl.dividend_yield",
        label="EREGL: dividend yield is conditional on governed event data",
        ticker="EREGL", company_type="standard_corporate", sector_module="generic",
        method_id="val.method.dividend_yield.cash_declared_paid", outcome="conditional_data",
        requires=["distribution.trailing_paid_history.available"],
        source_contract_refs=["docs/valuation-t67-08-company-sector-applicability-policy.md#9"],
    ),
    {
        "entry_id": "val.policy.applicability.unsupported_company_type.deny",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Unsupported company types (bank/insurance/reit/holding) fail closed for every current method",
        "source_contract_refs": ["docs/valuation-t67-08-company-sector-applicability-policy.md#4"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "applicability.company_type_gate",
            "selector": {"company_type": ["bank", "insurance", "reit", "holding"]},
            "outcome": "deferred_not_implemented",
            "rule": "No industrial P/E/P/B/EV/FCF method set is applied to an unsupported company type merely because a similarly named metric exists; a dedicated adapter is required and none exists yet.",
        },
    },
]

# ---------------------------------------------------------------------------
# 6. valuation.policies.method_sets (T71-A: catalog content only -- the
#    T71-B resolver that expands one of these for a given company at
#    runtime does not exist yet in this PR).
# ---------------------------------------------------------------------------


def _method_set_row(method_id: str, formula_id: str, role: str, applicability_policy_ref: str) -> dict[str, Any]:
    return {"method_id": method_id, "formula_id": formula_id, "role": role, "applicability_policy_ref": applicability_policy_ref}


_METHOD_SET_POLICY_ENTRIES: list[dict[str, Any]] = [
    {
        "entry_id": "val.policy.method_set.thyao.standard_corporate_aviation",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "THYAO current method set: standard_corporate + aviation",
        "source_contract_refs": ["docs/valuation-t71-03-applicability-method-set-family-specification.md#7"],
        "body": {
            "decision_type": "method_set",
            "selector": {"ticker": "THYAO", "company_type": "standard_corporate", "sector_module": "aviation"},
            "configured_rows": [
                _method_set_row("val.method.ev_to_ebitdar.aviation_lease_inclusive", "val.formula.method.ev_to_ebitdar.aviation_lease_inclusive", "primary", "val.policy.applicability.thyao.ev_ebitdar"),
                _method_set_row("val.method.pe.reported_parent", "val.formula.method.pe.reported_parent_fy", "secondary", "val.policy.applicability.thyao.pe"),
                _method_set_row("val.method.earnings_yield.reported_parent", "val.formula.method.earnings_yield.reported_parent_fy", "diagnostic", "val.policy.applicability.thyao.earnings_yield"),
                _method_set_row("val.method.fcf_yield.after_lease_equity", "val.formula.method.fcf_yield.after_lease_equity", "secondary", "val.policy.applicability.thyao.fcf_after_lease"),
                _method_set_row("val.method.fcf_yield.standard_equity", "val.formula.method.fcf_yield.standard_equity", "diagnostic", "val.policy.applicability.thyao.fcf_standard"),
                _method_set_row("val.method.ev_to_ebit.core", "val.formula.method.ev_to_ebit.core", "diagnostic", "val.policy.applicability.thyao.ev_ebit"),
                _method_set_row("val.method.price_to_book.parent_equity", "val.formula.method.price_to_book.parent_equity", "diagnostic", "val.policy.applicability.thyao.pb"),
                _method_set_row("val.method.ev_to_ebitda.canonical", "val.formula.method.ev_to_ebitda.canonical", "conditional", "val.policy.applicability.thyao.ev_ebitda"),
                _method_set_row("val.method.dividend_yield.cash_declared_paid", "val.formula.method.dividend_yield.cash_declared_paid", "conditional", "val.policy.applicability.thyao.dividend_yield"),
            ],
        },
    },
    {
        "entry_id": "val.policy.method_set.eregl.standard_corporate_generic",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "EREGL current method set: standard_corporate + generic",
        "source_contract_refs": ["docs/valuation-t71-03-applicability-method-set-family-specification.md#8"],
        "body": {
            "decision_type": "method_set",
            "selector": {"ticker": "EREGL", "company_type": "standard_corporate", "sector_module": "generic"},
            "configured_rows": [
                _method_set_row("val.method.price_to_book.parent_equity", "val.formula.method.price_to_book.parent_equity", "primary", "val.policy.applicability.eregl.pb"),
                _method_set_row("val.method.fcf_yield.standard_equity", "val.formula.method.fcf_yield.standard_equity", "primary", "val.policy.applicability.eregl.fcf_standard"),
                _method_set_row("val.method.ev_to_ebit.core", "val.formula.method.ev_to_ebit.core", "primary", "val.policy.applicability.eregl.ev_ebit"),
                _method_set_row("val.method.pe.reported_parent", "val.formula.method.pe.reported_parent_fy", "secondary", "val.policy.applicability.eregl.pe"),
                _method_set_row("val.method.earnings_yield.reported_parent", "val.formula.method.earnings_yield.reported_parent_fy", "diagnostic", "val.policy.applicability.eregl.earnings_yield"),
                _method_set_row("val.method.ev_to_ebitda.canonical", "val.formula.method.ev_to_ebitda.canonical", "conditional", "val.policy.applicability.eregl.ev_ebitda"),
                _method_set_row("val.method.fcf_yield.after_lease_equity", "val.formula.method.fcf_yield.after_lease_equity", "diagnostic", "val.policy.applicability.eregl.fcf_after_lease"),
                _method_set_row("val.method.dividend_yield.cash_declared_paid", "val.formula.method.dividend_yield.cash_declared_paid", "conditional", "val.policy.applicability.eregl.dividend_yield"),
            ],
        },
    },
    {
        "entry_id": "val.policy.method_set.standard_corporate_generic_default",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Default common conditional method set for an unknown registered standard_corporate + generic ticker",
        "source_contract_refs": ["docs/valuation-t71-03-applicability-method-set-family-specification.md#10"],
        "body": {
            "decision_type": "method_set",
            "selector": {"ticker": None, "company_type": "standard_corporate", "sector_module": "generic"},
            "configured_rows": [
                _method_set_row("val.method.pe.reported_parent", "val.formula.method.pe.reported_parent", "conditional", None),
                _method_set_row("val.method.earnings_yield.reported_parent", "val.formula.method.earnings_yield.reported_parent", "diagnostic", None),
                _method_set_row("val.method.price_to_book.parent_equity", "val.formula.method.price_to_book.parent_equity", "conditional", None),
                _method_set_row("val.method.fcf_yield.standard_equity", "val.formula.method.fcf_yield.standard_equity", "conditional", None),
                _method_set_row("val.method.ev_to_ebit.core", "val.formula.method.ev_to_ebit.core", "conditional", None),
                _method_set_row("val.method.ev_to_ebitda.canonical", "val.formula.method.ev_to_ebitda.canonical", "conditional", None),
            ],
        },
    },
]
