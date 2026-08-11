"""Authored valuation catalog definitions.

Kept by domain so catalog content remains reviewable without changing its
canonical structure.
"""

from __future__ import annotations

from typing import Any

_SHARED_CATALOG_ENTRIES: list[dict[str, Any]] = [
    {
        "entry_id": "shared.vocab.unit_family",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Unit family vocabulary",
        "source_contract_refs": ["docs/valuation-t67-09-units-reasons-rounding-traceability.md#2"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": [
                "amount", "price_per_share", "shares", "ratio", "percentage_display",
                "multiple", "rate", "per_unit_operating", "duration", "rank", "score_integer",
            ],
        },
    },
    {
        "entry_id": "shared.vocab.scale",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Amount scale vocabulary and multipliers",
        "source_contract_refs": ["docs/valuation-t67-09-units-reasons-rounding-traceability.md#3"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": [
                {"scale_id": "units", "multiplier": "1"},
                {"scale_id": "thousands", "multiplier": "1000"},
                {"scale_id": "millions", "multiplier": "1000000"},
                {"scale_id": "billions", "multiplier": "1000000000"},
            ],
        },
    },
    {
        "entry_id": "shared.vocab.availability_status",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Availability status vocabulary",
        "source_contract_refs": ["docs/valuation-t67-01-catalog-meta-contract.md#10"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": ["available", "not_applicable", "not_meaningful", "unavailable", "calculation_blocked", "insufficient_data", "not_comparable"],
        },
    },
    {
        "entry_id": "shared.vocab.artifact_type",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Artifact type vocabulary (T70-A scope)",
        "source_contract_refs": ["docs/valuation-t70-01-implementation-architecture-file-plan.md"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": ["market_snapshot", "valuation_inputs", "market_source_manifest"],
        },
    },
    {
        "entry_id": "shared.vocab.direction",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Directionality vocabulary",
        "source_contract_refs": ["docs/valuation-t67-09-units-reasons-rounding-traceability.md#6"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": [
                "higher_is_more_attractive", "lower_is_more_attractive", "higher_is_higher_risk",
                "lower_is_higher_risk", "neutral_contextual", "not_rankable",
            ],
        },
    },
    {
        "entry_id": "shared.vocab.method_role",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Method role vocabulary",
        "source_contract_refs": ["docs/valuation-t67-09-units-reasons-rounding-traceability.md#7"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": ["primary", "secondary", "diagnostic", "conditional", "deferred"],
        },
    },
    {
        "entry_id": "shared.policy.rounding_default",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Default rounding policy (half-even, display stage only)",
        "source_contract_refs": ["docs/valuation-t67-09-units-reasons-rounding-traceability.md#4"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "rounding",
            "rounding_mode": "ROUND_HALF_EVEN",
            "rule": "Rounding is applied only at the final display stage, per unit family; canonical/intermediate arithmetic values are never rounded, and a display-rounded value is never fed back into a formula, rank, or validation as an input.",
        },
    },
    {
        "entry_id": "shared.reason_codes.capital",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Capital-basis reason codes",
        "source_contract_refs": ["docs/valuation-t67-02-capital-basis-formula-catalog.md#8"],
        "body": {
            "decision_type": "reason_code_registry",
            "codes": [
                {"code": "capital.price_share_basis_mismatch", "severity": "error", "recoverability": "resolve_reference"},
                {"code": "capital.nonpositive_basic_shares", "severity": "blocker", "recoverability": "correct_authored_revision"},
                {"code": "capital.corporate_action_coverage_gap", "severity": "error", "recoverability": "add_missing_source"},
                {"code": "capital.fx_missing_or_invalid", "severity": "error", "recoverability": "add_missing_source"},
                {"code": "capital.cash_component_unresolved", "severity": "warning", "recoverability": "resolve_accounting_basis"},
                {"code": "capital.noncurrent_investment_ineligible", "severity": "info", "recoverability": "resolve_accounting_basis"},
                {"code": "capital.lease_disclosure_missing", "severity": "warning", "recoverability": "add_missing_source"},
                {"code": "capital.lease_double_count", "severity": "blocker", "recoverability": "correct_authored_revision"},
                {"code": "capital.nci_claim_mismatch", "severity": "error", "recoverability": "resolve_accounting_basis"},
                {"code": "capital.jv_paired_treatment_missing", "severity": "warning", "recoverability": "resolve_accounting_basis"},
                {"code": "capital.ev_bridge_reconciliation_failed", "severity": "blocker", "recoverability": "regenerate_generated_artifact"},
            ],
        },
    },
    {
        "entry_id": "shared.reason_codes.identity_temporal",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Identity, temporal, and status reason codes used by T70-A base validation",
        "source_contract_refs": ["docs/valuation-t66-09-cross-schema-validation-fixtures-migration.md"],
        "body": {
            "decision_type": "reason_code_registry",
            "codes": [
                {"code": "identity.content_hash_mismatch", "severity": "blocker", "recoverability": "regenerate_generated_artifact"},
                {"code": "identity.catalog_version_unknown", "severity": "blocker", "recoverability": "migrate_version"},
                {"code": "identity.duplicate_key", "severity": "blocker", "recoverability": "correct_authored_revision"},
                {"code": "identity.reference_invalid", "severity": "error", "recoverability": "resolve_reference"},
                {"code": "temporal.cutoff_violation", "severity": "blocker", "recoverability": "exclude_ineligible_observation"},
                {"code": "status.required_observation_missing", "severity": "error", "recoverability": "add_missing_source"},
                {"code": "status.contract_coverage_insufficient", "severity": "error", "recoverability": "add_missing_source"},
                {"code": "status.economic_interpretation_invalid", "severity": "warning", "recoverability": "resolve_accounting_basis"},
                {"code": "freshness.required_input_stale", "severity": "warning", "recoverability": "regenerate_generated_artifact"},
                {"code": "freshness.required_input_expired", "severity": "error", "recoverability": "regenerate_generated_artifact"},
                {"code": "confidence.critical_input_low", "severity": "warning", "recoverability": "resolve_accounting_basis"},
                {"code": "confidence.critical_input_insufficient", "severity": "error", "recoverability": "add_missing_source"},
            ],
        },
    },
    # -- T71-A additions below: method engine vocabulary, numeric context,
    #    and method/applicability reason codes. Nothing above this line is
    #    modified by T71-A.
    {
        "entry_id": "shared.vocab.economic_family",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Economic family vocabulary (T71 current-method scope)",
        "source_contract_refs": ["docs/valuation-t67-09-units-reasons-rounding-traceability.md#9"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": [
                "val.family.parent_earnings_valuation",
                "val.family.parent_book_valuation",
                "val.family.equity_free_cash_flow_yield",
                "val.family.enterprise_core_operating_earnings",
                "val.family.enterprise_ebitda",
                "val.family.aviation_ebitdar",
                "val.family.dividend_distribution_yield",
            ],
        },
    },
    {
        "entry_id": "shared.vocab.applicability_outcome",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Applicability outcome vocabulary",
        "source_contract_refs": ["docs/valuation-t67-08-company-sector-applicability-policy.md#3"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": [
                "applicable_primary", "applicable_secondary", "applicable_diagnostic",
                "conditional_data", "conditional_adapter", "not_applicable", "deferred_not_implemented",
            ],
        },
    },
    {
        "entry_id": "shared.vocab.guard_type",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Method guard-plan step type vocabulary",
        "source_contract_refs": ["docs/valuation-t71-02-formula-ast-catalog-compilation-specification.md#4"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": [
                "required_available", "denominator_nonzero", "denominator_positive",
                "claim_match", "currency_match", "scale_match", "period_match",
                "accounting_match", "lease_match", "capability_required",
                "reconciliation_required", "sign_constraint",
            ],
        },
    },
    {
        "entry_id": "shared.vocab.method_ast_operator",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Closed method-formula AST operator vocabulary",
        "source_contract_refs": ["docs/valuation-t71-02-formula-ast-catalog-compilation-specification.md#3"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": ["operand", "constant", "add", "subtract", "multiply", "divide", "negate", "scale_convert"],
        },
    },
    {
        "entry_id": "shared.vocab.method_operand_economic_type",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Method operand economic-type vocabulary (T71 current-method scope)",
        "source_contract_refs": ["docs/valuation-t71-04-operand-binding-current-method-evaluator-specification.md#3"],
        "body": {
            "decision_type": "controlled_vocabulary",
            "values": [
                "market_cap", "parent_net_income", "parent_equity", "standard_fcf",
                "after_lease_fcf", "fcfe", "enterprise_value_ex_lease",
                "enterprise_value_incl_lease", "core_ebit", "canonical_ebitda",
                "canonical_ebitdar", "dividend_per_share", "spot_price_per_share", "one",
            ],
        },
    },
    {
        "entry_id": "val.numeric.context.method.v1",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Method arithmetic context: 50-digit ROUND_HALF_EVEN, exact-rational reconciliation",
        "source_contract_refs": ["docs/valuation-t71-02-formula-ast-catalog-compilation-specification.md#8"],
        "body": {
            "decision_type": "policy_decision",
            "policy_family": "numeric.arithmetic_context",
            "precision_significant_digits": 50,
            "rounding_mode": "ROUND_HALF_EVEN",
            "min_exponent": -1000,
            "max_exponent": 1000,
            "traps": ["invalid_operation", "division_by_zero", "overflow", "underflow"],
            "silent_clamping_forbidden": True,
            "negative_zero_rejected": True,
            "ambient_context_independent": True,
        },
    },
    {
        "entry_id": "shared.reason_codes.method",
        "entry_version": "1.0.0",
        "lifecycle_status": "approved",
        "label": "Current-method and applicability reason codes",
        "source_contract_refs": [
            "docs/valuation-t67-03-valuation-method-formula-catalog.md#20",
            "docs/valuation-t67-08-company-sector-applicability-policy.md#16",
        ],
        "body": {
            "decision_type": "reason_code_registry",
            "codes": [
                {"code": "method.period_basis_unavailable", "severity": "error", "recoverability": "add_missing_source"},
                {"code": "method.single_quarter_annualization_forbidden", "severity": "blocker", "recoverability": "none"},
                {"code": "method.parent_claim_mismatch", "severity": "blocker", "recoverability": "resolve_accounting_basis"},
                {"code": "method.denominator_zero", "severity": "warning", "recoverability": "none"},
                {"code": "method.denominator_negative", "severity": "warning", "recoverability": "none"},
                {"code": "method.enterprise_value_nonpositive", "severity": "warning", "recoverability": "none"},
                {"code": "method.cash_flow_claim_mismatch", "severity": "error", "recoverability": "resolve_accounting_basis"},
                {"code": "method.lease_basis_mismatch", "severity": "error", "recoverability": "add_missing_source"},
                {"code": "method.canonical_ebitda_unavailable", "severity": "error", "recoverability": "add_missing_source"},
                {"code": "method.ebitdar_reconciliation_failed", "severity": "blocker", "recoverability": "resolve_accounting_basis"},
                {"code": "method.dividend_event_missing", "severity": "error", "recoverability": "add_missing_source"},
                {"code": "method.same_family_double_count", "severity": "blocker", "recoverability": "correct_authored_revision"},
                {"code": "applicability.company_type_not_implemented", "severity": "info", "recoverability": "none"},
                {"code": "applicability.sector_adapter_missing", "severity": "info", "recoverability": "none"},
                {"code": "applicability.ticker_policy_missing", "severity": "info", "recoverability": "none"},
                {"code": "applicability.primary_method_data_missing", "severity": "error", "recoverability": "add_missing_source"},
                {"code": "applicability.lease_adapter_required", "severity": "info", "recoverability": "none"},
                {"code": "applicability.canonical_ebitda_required", "severity": "info", "recoverability": "none"},
                {"code": "applicability.peer_universe_not_approved", "severity": "info", "recoverability": "none"},
                {"code": "applicability.history_capability_missing", "severity": "info", "recoverability": "none"},
                {"code": "applicability.scenario_capability_missing", "severity": "info", "recoverability": "none"},
                {"code": "applicability.no_valid_primary_secondary_family", "severity": "warning", "recoverability": "none"},
            ],
        },
    },
]
