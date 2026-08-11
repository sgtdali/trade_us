"""Piotroski F-Score diagnostic engine (T74-B;
docs/valuation-t74-05-piotroski-magic-diagnostic-specification.md
Sections 2-8, 21; docs/valuation-t68-07-comparison-strategy-applicability-matrix.md
Sections 13-15; T67.7's exact nine canonical component IDs/formula refs).

Nine independent binary tests over already-resolved exact facts (this
engine never loads a fundamental source file or computes ROA/CFO/
leverage/current-ratio/gross-margin/asset-turnover itself -- that is
T71's method-family territory; :class:`PiotroskiFacts` carries the
already-exact envelope each test needs). A missing/unusable required
fact yields ``binary_value=None`` with a reason, never ``0`` (T74.5
Section 5). The standard total is an integer sum only when every
component is ``complete``; one missing/blocked/not-applicable component
makes the total ``null``, never a partial "x/9" score (T74.5 Section 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..methods.numeric import to_exact_rational
from .models import PIOTROSKI_COMPONENT_ORDER
from .policies import PiotroskiComponentPolicy, PiotroskiDiagnosticPolicy

Envelope = Mapping[str, Any]


@dataclass(frozen=True)
class PiotroskiFacts:
    """Already-exact facts for one company/period pair, one envelope
    (``{"status": ..., "value": ..., "reason_codes": [...]}`` or an
    unavailable-status envelope with no ``value``) per required input.
    ``current_refs``/``prior_refs``/``opening_balance_refs`` are the exact
    lineage refs every component result cites back to its source facts."""

    roa_t: Envelope
    roa_t1: Envelope
    cfo_t: Envelope
    cfoa_t: Envelope
    leverage_t: Envelope
    leverage_t1: Envelope
    current_ratio_t: Envelope
    current_ratio_t1: Envelope
    equity_issuance_amount_t: Envelope
    gross_margin_t: Envelope
    gross_margin_t1: Envelope
    asset_turnover_t: Envelope
    asset_turnover_t1: Envelope
    current_refs: tuple[str, ...] = ()
    prior_refs: tuple[str, ...] = ()
    opening_balance_refs: tuple[str, ...] = ()


def _available(envelope: Envelope) -> bool:
    return envelope.get("status") == "available" and "value" in envelope


def _compare(left: Envelope, right: Envelope | None, comparator: str) -> bool:
    """Exact-rational comparison of two envelope values (``right=None``
    means "compare against zero", e.g. ``roa_positive``'s ``ROA_t > 0``).
    Callers must have already verified both envelopes are available."""
    left_value = to_exact_rational(left["value"])
    right_value = to_exact_rational(right["value"]) if right is not None else to_exact_rational("0")
    if comparator == ">":
        return left_value > right_value
    if comparator == "<":
        return left_value < right_value
    if comparator == "==":
        return left_value == right_value
    if comparator == ">=":
        return left_value >= right_value
    if comparator == "<=":
        return left_value <= right_value
    if comparator == "!=":
        return left_value != right_value
    raise ValueError(f"unknown comparator: {comparator!r}")


def _result(
    policy: PiotroskiComponentPolicy, *, applicable: bool, envelopes: tuple[Envelope, ...],
    compare_fn, facts: PiotroskiFacts,
) -> dict[str, Any]:
    if not applicable:
        return {
            "component_id": policy.component_id, "applicability": "not_applicable", "status": "not_applicable",
            "binary_value": None, "current_refs": [], "prior_refs": [], "opening_balance_refs": [],
            "formula_ref": policy.formula_ref, "policy_ref": "val.policy.piotroski@1.0.0", "reason_codes": [],
        }
    if not all(_available(e) for e in envelopes):
        return {
            "component_id": policy.component_id, "applicability": "applicable", "status": "missing",
            "binary_value": None, "current_refs": list(facts.current_refs), "prior_refs": list(facts.prior_refs),
            "opening_balance_refs": list(facts.opening_balance_refs) if policy.requires_opening_balance else [],
            "formula_ref": policy.formula_ref, "policy_ref": "val.policy.piotroski@1.0.0",
            "reason_codes": [{"code": "comparison.piotroski_component_fact_missing", "severity": "info"}],
        }
    return {
        "component_id": policy.component_id, "applicability": "applicable", "status": "complete",
        "binary_value": 1 if compare_fn() else 0, "current_refs": list(facts.current_refs), "prior_refs": list(facts.prior_refs),
        "opening_balance_refs": list(facts.opening_balance_refs) if policy.requires_opening_balance else [],
        "formula_ref": policy.formula_ref, "policy_ref": "val.policy.piotroski@1.0.0", "reason_codes": [],
    }


def evaluate_piotroski(
    facts: PiotroskiFacts, *, company_type: str, policy: PiotroskiDiagnosticPolicy,
) -> dict[str, Any]:
    """Pure: evaluate all nine canonical Piotroski components against
    already-resolved exact ``facts`` and assemble the ``piotroskiComponents``
    variant shape. ``company_type`` not present in the compiled policy's
    own ``company_type_applicability`` (the single source of truth --
    T67.7's registered company-type list, never a second parallel
    vocabulary here) makes every component ``not_applicable`` (T74.5
    Section 2) -- this engine never applies a generic industrial fallback
    to a bank/insurance/REIT/holding."""
    applicable = company_type in policy.company_type_applicability
    policies_by_id = {c.component_id: c for c in policy.components}

    def _cmp(component_id: str, left: Envelope, right: Envelope | None) -> bool:
        return _compare(left, right, policies_by_id[component_id].comparator)

    components: list[dict[str, Any]] = []
    components.append(_result(policies_by_id["piot.roa_positive"], applicable=applicable, envelopes=(facts.roa_t,), compare_fn=lambda: _cmp("piot.roa_positive", facts.roa_t, None), facts=facts))
    components.append(_result(policies_by_id["piot.cfo_positive"], applicable=applicable, envelopes=(facts.cfo_t,), compare_fn=lambda: _cmp("piot.cfo_positive", facts.cfo_t, None), facts=facts))
    components.append(_result(policies_by_id["piot.delta_roa_positive"], applicable=applicable, envelopes=(facts.roa_t, facts.roa_t1), compare_fn=lambda: _cmp("piot.delta_roa_positive", facts.roa_t, facts.roa_t1), facts=facts))
    components.append(_result(policies_by_id["piot.accrual_quality"], applicable=applicable, envelopes=(facts.cfoa_t, facts.roa_t), compare_fn=lambda: _cmp("piot.accrual_quality", facts.cfoa_t, facts.roa_t), facts=facts))
    components.append(_result(policies_by_id["piot.leverage_decreased"], applicable=applicable, envelopes=(facts.leverage_t, facts.leverage_t1), compare_fn=lambda: _cmp("piot.leverage_decreased", facts.leverage_t, facts.leverage_t1), facts=facts))
    components.append(_result(policies_by_id["piot.current_ratio_increased"], applicable=applicable, envelopes=(facts.current_ratio_t, facts.current_ratio_t1), compare_fn=lambda: _cmp("piot.current_ratio_increased", facts.current_ratio_t, facts.current_ratio_t1), facts=facts))
    components.append(_result(policies_by_id["piot.no_external_equity_issuance"], applicable=applicable, envelopes=(facts.equity_issuance_amount_t,), compare_fn=lambda: _cmp("piot.no_external_equity_issuance", facts.equity_issuance_amount_t, None), facts=facts))
    components.append(_result(policies_by_id["piot.gross_margin_increased"], applicable=applicable, envelopes=(facts.gross_margin_t, facts.gross_margin_t1), compare_fn=lambda: _cmp("piot.gross_margin_increased", facts.gross_margin_t, facts.gross_margin_t1), facts=facts))
    components.append(_result(policies_by_id["piot.asset_turnover_increased"], applicable=applicable, envelopes=(facts.asset_turnover_t, facts.asset_turnover_t1), compare_fn=lambda: _cmp("piot.asset_turnover_increased", facts.asset_turnover_t, facts.asset_turnover_t1), facts=facts))

    assert tuple(c["component_id"] for c in components) == PIOTROSKI_COMPONENT_ORDER

    available_component_count = sum(1 for c in components if c["status"] == "complete")
    total = sum(c["binary_value"] for c in components) if available_component_count == 9 else None

    return {
        "variant_kind": "piotroski_diagnostic", "diagnostic_id": policy.diagnostic_id,
        "components": components, "available_component_count": available_component_count, "total": total,
    }
