"""Pure, side-effect-free valuation-input resolver
(docs/valuation-t70-05-financial-basis-input-resolver-specification.md
Section 14).

:func:`resolve_valuation_inputs` performs no file reads, no writes, no
environment access, and no process clock -- it is a deterministic function
of its :class:`ValuationInputRequest`. It never selects a valuation
method, scenario, or recommendation; it only assembles the capital-basis
facts a later (out-of-scope for T70-B) method engine would consume.

Deliberate T70-B scope simplifications (documented, not silently assumed):

* The capital ledger (debt/lease/cash/NCI/preferred/equity-method
  components, all sourced from :class:`FinancialBasis`) is only converted
  into the target reporting currency when
  ``financial_basis.reporting_currency == request.reporting_currency``.
  A genuine mismatch there is reported as a blocking finding rather than
  invented via an assumed FX pair -- only the *price* (a single scalar,
  with an explicit direct/inverse FX observation attached to the market
  snapshot) is actually currency-converted in this PR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from typing import Any, Mapping

from ...public.financial_basis import CompanySpecificBasis, FieldValue, FinancialBasis
from ...public.method_basis import MethodBasis
from ..canonical import normalize_decimal
from ..catalogs import CatalogRegistry
from ..validation.findings import Finding
from .capital import FormulaOutcome, Operand, evaluate_formula

_LEDGER_CATALOG = "valuation.formulas.capital_basis"


def _base_amount(value: str, unit: str | None) -> Decimal:
    """Convert governed financial-statement amount scales to base currency."""
    multipliers = {
        "unit": Decimal("1"),
        "thousand": Decimal("1000"),
        "million": Decimal("1000000"),
        "billion": Decimal("1000000000"),
    }
    decimal_value = Decimal(value)
    normalized_unit = (unit or "").lower()
    scale_name, separator, currency_suffix = normalized_unit.partition("_")
    multiplier = (
        multipliers.get(scale_name)
        if separator and len(currency_suffix) == 3 and currency_suffix.isalpha()
        else Decimal("1") if normalized_unit in {"units", "shares"} else None
    )
    if multiplier is None:
        return decimal_value
    with localcontext() as context:
        context.prec = 50
        return decimal_value * multiplier


def _operand_from_field(fv: FieldValue) -> Operand:
    if fv.status == "available":
        return Operand("available", _base_amount(fv.value, fv.unit))
    return Operand(fv.status, reason_codes=fv.reason_codes)


def _envelope(outcome_or_field: FormulaOutcome | FieldValue, *, unit: str | None = None, currency: str | None = None) -> dict[str, Any]:
    if isinstance(outcome_or_field, FormulaOutcome):
        status, value, reasons = outcome_or_field.status, outcome_or_field.value, outcome_or_field.reason_codes
        resolved_unit = unit
    else:
        status, value, reasons = outcome_or_field.status, (Decimal(outcome_or_field.value) if outcome_or_field.value is not None else None), outcome_or_field.reason_codes
        resolved_unit = unit or outcome_or_field.unit
    envelope: dict[str, Any] = {"status": status}
    if status == "available":
        envelope["value"] = normalize_decimal(value)
        if resolved_unit:
            envelope["unit"] = resolved_unit
        if currency:
            envelope["currency"] = currency
    else:
        envelope["reason_codes"] = [{"code": rc, "severity": "warning"} for rc in (reasons or ("status.required_observation_missing",))]
    return envelope


@dataclass(frozen=True)
class ValuationInputRequest:
    financial_basis: FinancialBasis
    market_snapshot: Mapping[str, Any]
    market_snapshot_reference: Mapping[str, str]
    context_id: str
    as_of_date: str
    cutoff_instant: str
    reporting_currency: str
    catalog_registry: CatalogRegistry
    purpose: str = "current"
    company_specific: CompanySpecificBasis | None = None
    method_basis: MethodBasis | None = None


@dataclass(frozen=True)
class ValuationInputResolutionResult:
    valuation_inputs: Mapping[str, Any] | None
    findings: tuple[Finding, ...] = field(default_factory=tuple)


def _select_fx_rate(market_snapshot: Mapping[str, Any], *, native_currency: str, target_currency: str) -> tuple[Decimal | None, str | None]:
    """Direct-then-inverse FX selection (docs/valuation-t70-04-market-registry-snapshot-specification.md
    Section 8 / ``val.policy.market_input.fx_direct_then_inverse``). Returns
    ``(native_per... target_per_native_rate, reason_code_if_unavailable)``.
    Triangulation is never attempted -- no locked catalog entry in T70-B
    names a permitted pivot currency."""
    if native_currency == target_currency:
        return Decimal(1), None
    for fx in market_snapshot.get("fx_observations", ()):
        if fx["base_currency"] == native_currency and fx["quote_currency"] == target_currency:
            return Decimal(fx["rate"]), None
    for fx in market_snapshot.get("fx_observations", ()):
        if fx["base_currency"] == target_currency and fx["quote_currency"] == native_currency:
            rate = Decimal(fx["rate"])
            if rate == 0:
                return None, "capital.fx_missing_or_invalid"
            return Decimal(1) / rate, None
    return None, "capital.fx_missing_or_invalid"


def resolve_valuation_inputs(request: ValuationInputRequest, registry: CatalogRegistry) -> ValuationInputResolutionResult:
    findings: list[Finding] = []
    basis = request.financial_basis
    snapshot = request.market_snapshot

    if snapshot.get("snapshot_identity", {}).get("ticker") != basis.ticker:
        findings.append(Finding(rule_id="VAL-MI-001", severity="blocker", scope="artifact", reason_code="identity.reference_invalid", message="market snapshot ticker does not match FinancialBasis ticker"))
        return ValuationInputResolutionResult(valuation_inputs=None, findings=tuple(findings))
    if snapshot.get("temporal_context", {}).get("cutoff_instant") != request.cutoff_instant:
        findings.append(Finding(rule_id="VAL-TIME-001", severity="blocker", scope="artifact", reason_code="temporal.cutoff_violation", message="market snapshot cutoff_instant does not match the requested cutoff_instant"))
        return ValuationInputResolutionResult(valuation_inputs=None, findings=tuple(findings))
    if snapshot.get("freshness_summary", {}).get("current_use_state") == "blocked":
        findings.append(Finding(rule_id="VAL-MI-007", severity="blocker", scope="artifact", reason_code="freshness.required_input_expired", message="market snapshot is not current-use eligible"))
        return ValuationInputResolutionResult(valuation_inputs=None, findings=tuple(findings))

    # --- price basis --------------------------------------------------
    native_currency = snapshot["instrument"]["trading_currency"]
    native_price = Decimal(snapshot["price_observation"]["price"])
    fx_rate, fx_reason = _select_fx_rate(snapshot, native_currency=native_currency, target_currency=request.reporting_currency)
    if fx_rate is None:
        findings.append(Finding(rule_id="VAL-MI-006", severity="error", scope="artifact", reason_code=fx_reason, message="no eligible FX conversion path to the target reporting currency"))
        reporting_price_outcome = FormulaOutcome(status="unavailable", reason_codes=(fx_reason,))
    else:
        reporting_price_outcome = FormulaOutcome(status="available", value=native_price * fx_rate)

    price_basis = {
        "price_observation_ref": snapshot["price_observation"]["observation_id"],
        "mode": snapshot["price_observation"]["mode"],
        "native_price": _envelope(FormulaOutcome(status="available", value=native_price), currency=native_currency),
        "reporting_currency_price": _envelope(reporting_price_outcome, currency=request.reporting_currency),
        "price_unit": snapshot["instrument"].get("price_unit", "per_share"),
        "current_use_eligible": snapshot.get("freshness_summary", {}).get("current_use_state") == "eligible",
    }

    # --- share basis (market-supplied, reconciled against FinancialBasis) --
    market_share_basis = snapshot["share_basis"]
    spot_basic_shares = Decimal(market_share_basis["spot_basic_shares_outstanding"])
    basis_issued_available = basis.issued_shares.status == "available" and basis.treasury_shares.status == "available"
    reconciliation_status = "unreconciled"
    if basis_issued_available:
        fb_spot = Decimal(basis.issued_shares.value) - Decimal(basis.treasury_shares.value)
        reconciliation_status = "reconciled" if fb_spot == spot_basic_shares else "unreconciled"
        if fb_spot != spot_basic_shares:
            findings.append(Finding(rule_id="VAL-MI-005", severity="warning", scope="artifact", reason_code="capital.price_share_basis_mismatch", message="FinancialBasis-derived share count disagrees with the market-supplied share count; market-supplied value is used, never averaged"))

    share_basis = {
        "basis_type": "spot_basic_shares_outstanding",
        "spot_basic_shares_outstanding": _envelope(FormulaOutcome(status="available", value=spot_basic_shares), unit="shares"),
        "effective_date": market_share_basis["effective_date"],
        "reconciliation_status": reconciliation_status,
    }

    # --- market cap ------------------------------------------------------
    market_cap_entry = registry.select_entry(_LEDGER_CATALOG, "val.formula.capital.market_cap_spot_basic").entry
    market_cap_outcome = evaluate_formula(market_cap_entry, {
        "price_native_per_share": Operand("available", native_price),
        "spot_basic_shares_outstanding": Operand("available", spot_basic_shares),
        "unit_multiplier": Operand("available", Decimal(snapshot["instrument"].get("unit_multiplier", "1"))),
    })

    # market_cap_outcome is always denominated in native_currency (the
    # instrument's own trading currency) -- it must never be combined
    # directly with FinancialBasis's reporting-currency capital ledger, or
    # reported as though it were already in the reporting currency,
    # without first being run through the same currency_convert formula
    # used elsewhere for exactly this purpose
    # (val.formula.capital.currency_convert: amount_target = amount_source
    # * fx_target_per_source). ``fx_rate`` here is target_per_native (see
    # ``_select_fx_rate``), the exact fx_target_per_source shape the
    # formula expects -- never inverted.
    currency_convert_entry = registry.select_entry(_LEDGER_CATALOG, "val.formula.capital.currency_convert").entry
    if fx_rate is None:
        market_cap_reporting_outcome = FormulaOutcome(status="unavailable", reason_codes=(fx_reason,))
    else:
        market_cap_reporting_outcome = evaluate_formula(currency_convert_entry, {
            "amount_source": Operand(market_cap_outcome.status, market_cap_outcome.value, market_cap_outcome.reason_codes),
            "fx_target_per_source": Operand("available", fx_rate),
        })

    market_cap_basis = {
        "formula_ref": market_cap_entry["entry_id"],
        "reconciliation_status": reconciliation_status,
        "status": market_cap_outcome.status,
        "native_total_market_cap": _envelope(market_cap_outcome, currency=native_currency),
    }
    if market_cap_reporting_outcome.status == "available":
        market_cap_basis["reporting_currency_total_market_cap"] = _envelope(market_cap_reporting_outcome, currency=request.reporting_currency)

    # --- capital ledger (only computed in financial_basis's own currency) -
    currency_ok = basis.reporting_currency == request.reporting_currency
    if not currency_ok:
        findings.append(Finding(
            rule_id="VAL-ACC-001", severity="error", scope="artifact", reason_code="capital.price_share_basis_mismatch",
            message=(
                f"FinancialBasis reporting_currency {basis.reporting_currency!r} does not match the requested "
                f"valuation reporting_currency {request.reporting_currency!r}; the capital ledger is not converted "
                "in T70-B and is reported unavailable rather than guessed"
            ),
        ))

    def _blocked_by_currency() -> FormulaOutcome:
        return FormulaOutcome(status="unavailable", reason_codes=("capital.price_share_basis_mismatch",))

    if currency_ok:
        debt_entry = registry.select_entry(_LEDGER_CATALOG, "val.formula.capital.financial_debt_ex_lease").entry
        debt_outcome = evaluate_formula(debt_entry, {
            "short_term_borrowings": _operand_from_field(basis.short_term_borrowings),
            "current_portion_long_term_borrowings": _operand_from_field(basis.current_portion_long_term_borrowings),
            "long_term_borrowings": _operand_from_field(basis.long_term_borrowings),
            "eligible_interest_bearing_other_debt": _operand_from_field(basis.eligible_interest_bearing_other_debt),
        })

        lease_entry = registry.select_entry(_LEDGER_CATALOG, "val.formula.capital.lease_liability_total").entry
        lease_outcome = evaluate_formula(lease_entry, {
            "current_lease_liability": _operand_from_field(basis.current_lease_liability),
            "noncurrent_lease_liability": _operand_from_field(basis.noncurrent_lease_liability),
        })

        cash_entry = registry.select_entry(_LEDGER_CATALOG, "val.formula.capital.eligible_cash_total").entry
        cash_outcome = evaluate_formula(cash_entry, {
            "eligible_cash_component": [_operand_from_field(fv) for fv in basis.eligible_cash_components],
        })

        net_debt_ex_entry = registry.select_entry(_LEDGER_CATALOG, "val.formula.capital.net_debt_ex_lease").entry
        net_debt_ex_outcome = evaluate_formula(net_debt_ex_entry, {
            "financial_debt_ex_lease": Operand(debt_outcome.status, debt_outcome.value, debt_outcome.reason_codes),
            "eligible_cash_total": Operand(cash_outcome.status, cash_outcome.value, cash_outcome.reason_codes),
        })
        net_debt_incl_entry = registry.select_entry(_LEDGER_CATALOG, "val.formula.capital.net_debt_incl_lease").entry
        net_debt_incl_outcome = evaluate_formula(net_debt_incl_entry, {
            "financial_debt_ex_lease": Operand(debt_outcome.status, debt_outcome.value, debt_outcome.reason_codes),
            "lease_liability_total": Operand(lease_outcome.status, lease_outcome.value, lease_outcome.reason_codes),
            "eligible_cash_total": Operand(cash_outcome.status, cash_outcome.value, cash_outcome.reason_codes),
        })

        ev_ex_entry = registry.select_entry(_LEDGER_CATALOG, "val.formula.capital.enterprise_value_ex_lease").entry
        ev_ex_outcome = evaluate_formula(ev_ex_entry, {
            # The catalog input is literally named "market_cap_native", but
            # this ledger's other operands (net_debt_ex_lease, NCI,
            # preferred, equity-method) are all in basis.reporting_currency
            # -- under currency_ok, basis.reporting_currency ==
            # request.reporting_currency, so the currency-consistent
            # operand here is market_cap_reporting_outcome, never the raw
            # native-currency market_cap_outcome (see the market-cap
            # section above for why).
            "market_cap_native": Operand(market_cap_reporting_outcome.status, market_cap_reporting_outcome.value, market_cap_reporting_outcome.reason_codes),
            "net_debt_ex_lease": Operand(net_debt_ex_outcome.status, net_debt_ex_outcome.value, net_debt_ex_outcome.reason_codes),
            "noncontrolling_interests": _operand_from_field(basis.noncontrolling_interests),
            "preferred_equity": _operand_from_field(basis.preferred_equity),
            "equity_method_adjustment": _operand_from_field(basis.equity_method_adjustment),
        })
        ev_incl_entry = registry.select_entry(_LEDGER_CATALOG, "val.formula.capital.enterprise_value_incl_lease").entry
        ev_incl_outcome = evaluate_formula(ev_incl_entry, {
            "enterprise_value_ex_lease": Operand(ev_ex_outcome.status, ev_ex_outcome.value, ev_ex_outcome.reason_codes),
            "lease_liability_total": Operand(lease_outcome.status, lease_outcome.value, lease_outcome.reason_codes),
        })
    else:
        debt_outcome = lease_outcome = cash_outcome = net_debt_ex_outcome = net_debt_incl_outcome = ev_ex_outcome = ev_incl_outcome = _blocked_by_currency()

    if net_debt_ex_outcome.status == "available" and net_debt_incl_outcome.status == "available" and lease_outcome.status == "available":
        if net_debt_incl_outcome.value - net_debt_ex_outcome.value != lease_outcome.value:
            findings.append(Finding(rule_id="VAL-ACC-007", severity="blocker", scope="artifact", reason_code="capital.lease_double_count", message="net_debt_incl_lease - net_debt_ex_lease does not equal lease_liability_total"))
            return ValuationInputResolutionResult(valuation_inputs=None, findings=tuple(findings))

    ledger: list[dict[str, Any]] = []

    def _component(component_id: str, component_type: str, field_value: FieldValue, *, sign: str, lease_scope: str = "not_applicable", inclusion_role: str = "included") -> None:
        source_id = field_value.source_id or f"unavailable:{component_id}"
        normalized = field_value
        if field_value.status == "available":
            normalized = FieldValue(status="available", value=str(_base_amount(field_value.value, field_value.unit)), unit=field_value.currency, currency=field_value.currency, source_id=field_value.source_id)
        ledger.append({
            "component_id": component_id,
            "component_type": component_type,
            "amount": _envelope(normalized, unit=normalized.unit, currency=basis.reporting_currency),
            "lease_scope": lease_scope,
            "inclusion_role": inclusion_role if field_value.status == "available" else "unresolved",
            "sign_in_bridge": sign,
            "status": field_value.status,
            "lineage": {"source_id": source_id},
        })

    if currency_ok:
        # Same currency-consistency rationale as the EV formula's
        # market_cap_native operand above: this component's amount must be
        # in basis.reporting_currency, which under currency_ok equals
        # request.reporting_currency -- market_cap_reporting_outcome, never
        # the raw native-currency market_cap_outcome.
        _market_cap_field = FieldValue(
            status=market_cap_reporting_outcome.status,
            value=str(market_cap_reporting_outcome.value) if market_cap_reporting_outcome.value is not None else None,
            currency=basis.reporting_currency if market_cap_reporting_outcome.status == "available" else None,
            source_id="derived:market_cap" if market_cap_reporting_outcome.status == "available" else None,
            reason_codes=market_cap_reporting_outcome.reason_codes,
        )
        _component("comp-market-cap", "ordinary_equity_market_cap", _market_cap_field, sign="add")
        _component("comp-debt-current", "financial_debt_current", basis.short_term_borrowings, sign="add")
        _component("comp-debt-current-portion", "financial_debt_current", basis.current_portion_long_term_borrowings, sign="add")
        _component("comp-debt-noncurrent", "financial_debt_noncurrent", basis.long_term_borrowings, sign="add")
        _component("comp-lease-current", "lease_liability_current", basis.current_lease_liability, sign="add", lease_scope="lease_inclusive", inclusion_role="conditional_included")
        _component("comp-lease-noncurrent", "lease_liability_noncurrent", basis.noncurrent_lease_liability, sign="add", lease_scope="lease_inclusive", inclusion_role="conditional_included")
        for i, cash_component in enumerate(basis.eligible_cash_components):
            _component(f"comp-cash-{i}", "eligible_cash", cash_component, sign="subtract")
        _component("comp-nci", "noncontrolling_interests", basis.noncontrolling_interests, sign="add")
        _component("comp-preferred", "preferred_equity", basis.preferred_equity, sign="add")
        _component("comp-equity-method", "equity_method_investment", basis.equity_method_adjustment, sign="add")

    ev_family = []
    if currency_ok:
        ev_family.append({
            "ev_basis_id": "ev-ex-lease",
            "basis_type": "lease_exclusive",
            "market_cap_ref": "comp-market-cap",
            "enterprise_value": _envelope(ev_ex_outcome, currency=basis.reporting_currency),
            "formula_ref": ev_ex_entry["entry_id"],
            "status": ev_ex_outcome.status,
        })
        ev_family.append({
            "ev_basis_id": "ev-incl-lease",
            "basis_type": "lease_inclusive",
            "market_cap_ref": "comp-market-cap",
            "enterprise_value": _envelope(ev_incl_outcome, currency=basis.reporting_currency),
            "formula_ref": ev_incl_entry["entry_id"],
            "status": ev_incl_outcome.status,
        })

    capabilities = [
        {"capability_id": "cap-market-cap", "capability_type": "market_cap", "state": "available" if market_cap_outcome.status == "available" else "unavailable"},
        {"capability_id": "cap-ev-ex-lease", "capability_type": "enterprise_value_ex_lease", "state": "available" if currency_ok and ev_ex_outcome.status == "available" else "unavailable"},
        {"capability_id": "cap-ev-incl-lease", "capability_type": "enterprise_value_incl_lease", "state": "available" if currency_ok and ev_incl_outcome.status == "available" else "unavailable"},
    ]

    earnings_bases, cash_flow_bases, book_equity_basis, distribution_basis = _build_method_bases(
        request.method_basis, spot_basic_shares=spot_basic_shares, reporting_currency=basis.reporting_currency, registry=registry,
    )

    company_specific_inputs = _build_company_specific_inputs(request.company_specific)

    financial_basis_refs = [
        {"source_id": ref.source_id, "period_end": ref.period_end.isoformat(), "period_type": ref.period_type}
        for ref in basis.financial_period_refs
    ]

    lineage = [
        {"node_id": snapshot["artifact_id"], "node_type": "market_snapshot", "relation": "calculated_from", "artifact_ref": dict(request.market_snapshot_reference)},
    ]
    for ref in financial_basis_refs:
        lineage.append({"node_id": ref["source_id"], "node_type": "financial_period", "relation": "calculated_from"})

    valuation_inputs: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_type": "valuation_inputs",
        "owner_type": "generated",
        "input_identity": {"ticker": basis.ticker, "context_id": request.context_id, "purpose": request.purpose},
        "temporal_context": {"as_of_date": request.as_of_date, "cutoff_instant": request.cutoff_instant},
        "market_snapshot_ref": dict(request.market_snapshot_reference),
        "financial_basis_refs": sorted(financial_basis_refs, key=lambda r: (r["period_end"], r["period_type"], r["source_id"])),
        "reporting_currency_basis": {
            "valuation_reporting_currency": request.reporting_currency,
            "financial_presentation_currency": basis.reporting_currency,
            "accounting_translation_mode": "not_required" if native_currency == request.reporting_currency else "valuation_date_stock_conversion",
        },
        "price_basis": price_basis,
        "share_basis": share_basis,
        "market_cap_basis": market_cap_basis,
        "capital_structure_ledger": ledger,
        "ev_basis_family": ev_family,
        "input_capabilities": capabilities,
        "data_confidence": dict(snapshot.get("data_confidence", {"level": "insufficient"})),
        "validation_summary": {
            "market_cap_reconciled": reconciliation_status == "reconciled",
            "capital_ledger_no_double_count": True,
            "publication_basis_eligible": snapshot.get("freshness_summary", {}).get("current_use_state") == "eligible",
        },
        "lineage": sorted(lineage, key=lambda entry: (entry["node_id"], entry["relation"])),
    }
    if company_specific_inputs is not None:
        valuation_inputs["company_specific_inputs"] = company_specific_inputs
    if earnings_bases:
        valuation_inputs["earnings_bases"] = earnings_bases
    if cash_flow_bases:
        valuation_inputs["cash_flow_bases"] = cash_flow_bases
    if book_equity_basis is not None:
        valuation_inputs["book_equity_basis"] = book_equity_basis
    if distribution_basis is not None:
        valuation_inputs["distribution_basis"] = distribution_basis

    return ValuationInputResolutionResult(valuation_inputs=valuation_inputs, findings=tuple(findings))


_EARNINGS_FCF_CATALOG = "valuation.formulas.capital_basis"


def _build_method_bases(
    method_basis: MethodBasis | None, *, spot_basic_shares: Decimal, reporting_currency: str, registry: CatalogRegistry,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    """T71-B method-basis projection into the frozen valuation-input
    artifact (docs/valuation-t71-04-*.md): exact earnings/EBIT/EBITDA/
    EBITDAR/book-equity/FCF/dividend-event operands, never read directly
    from :class:`~fundamental_pipeline.public.method_basis.MethodBasis` by
    the T71 method engine -- only through this governed, hashed,
    schema-validated artifact. Returns empty/``None`` when no
    ``method_basis`` was supplied (T70-only callers are unaffected)."""
    if method_basis is None:
        return [], [], None, None

    period_variant = method_basis.period_variant  # "fy" | "true_ttm" | "unavailable"
    period_anchor_ref = method_basis.financial_period_refs[0].source_id if method_basis.financial_period_refs else ""

    def _earnings_entry(
        basis_id: str,
        earnings_type: str,
        field_value: FieldValue,
        *,
        variant_override: str | None = None,
        reconciliation_status: str | None = None,
        comparability: str | None = None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "earnings_basis_id": basis_id,
            "earnings_type": earnings_type,
            "period_anchor_ref": period_anchor_ref,
            "amount": _envelope(field_value, currency=reporting_currency if field_value.status == "available" else None),
            "status": field_value.status,
        }
        variant = variant_override if variant_override is not None else period_variant
        if variant in ("fy", "true_ttm"):
            entry["period_variant"] = variant
        if reconciliation_status:
            entry["reconciliation_status"] = reconciliation_status
        if comparability:
            entry["comparability"] = comparability
        return entry

    earnings_bases = [
        _earnings_entry("earn-parent-net-income", "reported_parent_net_income", method_basis.parent_net_income),
        _earnings_entry("earn-total-net-income", "reported_total_net_income", method_basis.total_net_income),
        _earnings_entry("earn-core-ebit", "reported_core_ebit", method_basis.core_ebit),
        # canonical_ebitda/ebitdar are never TTM-assembled (see
        # method_basis.py's MethodBasis docstring) -- their own
        # per-field period_variant is used here, never the basis-wide
        # ``period_variant`` (which may be "true_ttm" for the OTHER
        # earnings entries even while EBITDA/EBITDAR fell back to a
        # plain FY figure).
        _earnings_entry(
            "earn-ebitda",
            "company_adjusted_apm",
            method_basis.canonical_ebitda,
            variant_override=method_basis.canonical_ebitda_period_variant,
            reconciliation_status=method_basis.canonical_ebitda_reconciliation_status,
            comparability=method_basis.canonical_ebitda_comparability,
        ),
        _earnings_entry("earn-ebitdar", "company_adjusted_apm", method_basis.canonical_ebitdar, variant_override=method_basis.canonical_ebitdar_period_variant),
    ]

    cash_flow_bases: list[dict[str, Any]] = []

    cfo_val = _base_amount(method_basis.cfo.value, method_basis.cfo.unit) if method_basis.cfo.status == "available" else None
    capex_val = _base_amount(method_basis.capex.value, method_basis.capex.unit) if method_basis.capex.status == "available" else None
    lease_val = _base_amount(method_basis.lease_principal_paid.value, method_basis.lease_principal_paid.unit) if method_basis.lease_principal_paid.status == "available" else None

    cfo_operand = Operand(method_basis.cfo.status, cfo_val, method_basis.cfo.reason_codes)
    capex_operand = Operand(method_basis.capex.status, capex_val, method_basis.capex.reason_codes)
    lease_operand = Operand(method_basis.lease_principal_paid.status, lease_val, method_basis.lease_principal_paid.reason_codes)

    standard_entry_ref = registry.select_entry(_EARNINGS_FCF_CATALOG, "val.formula.capital.fcf_standard_equity").entry
    standard_outcome = evaluate_formula(standard_entry_ref, {"cfo": cfo_operand, "capex_standard": capex_operand})
    cash_flow_bases.append({
        "cash_flow_basis_id": "cf-fcf-standard",
        "cash_flow_type": "standard_fcf",
        "period_anchor_ref": period_anchor_ref,
        **({"period_variant": period_variant} if period_variant in ("fy", "true_ttm") else {}),
        "amount": _envelope(standard_outcome, unit="units", currency=reporting_currency),
        "formula_ref": standard_entry_ref["entry_id"],
        "status": standard_outcome.status,
    })

    after_lease_entry_ref = registry.select_entry(_EARNINGS_FCF_CATALOG, "val.formula.capital.fcf_after_lease_equity").entry
    after_lease_outcome = evaluate_formula(after_lease_entry_ref, {"cfo": cfo_operand, "capex_standard": capex_operand, "lease_principal_paid": lease_operand})
    cash_flow_bases.append({
        "cash_flow_basis_id": "cf-fcf-after-lease",
        "cash_flow_type": "after_lease_fcf",
        "period_anchor_ref": period_anchor_ref,
        **({"period_variant": period_variant} if period_variant in ("fy", "true_ttm") else {}),
        "amount": _envelope(after_lease_outcome, unit="units", currency=reporting_currency),
        "formula_ref": after_lease_entry_ref["entry_id"],
        "status": after_lease_outcome.status,
    })

    parent_ni_val = _base_amount(method_basis.parent_net_income.value, method_basis.parent_net_income.unit) if method_basis.parent_net_income.status == "available" else None
    total_ni_val = _base_amount(method_basis.total_net_income.value, method_basis.total_net_income.unit) if method_basis.total_net_income.status == "available" else None
    parent_ni_operand = Operand(method_basis.parent_net_income.status, parent_ni_val, method_basis.parent_net_income.reason_codes)
    total_ni_operand = Operand(method_basis.total_net_income.status, total_ni_val, method_basis.total_net_income.reason_codes)

    # Parent-attributed FCF variants (2026-07-22, AEFES onboarding -- see
    # catalogs.py module docstring and
    # wiki/systems/valuation-pipeline.md#serbest-nakit-akışı-yönteminin-nci-atfı-2026-07-22):
    # fcf_yield.standard_equity/after_lease_equity divide by a parent-only
    # market cap, so their FCF numerator must be attributed to the parent
    # too -- via the same net-income ownership split IFRS already
    # discloses, since CFO itself is never split by ownership.
    standard_parent_entry_ref = registry.select_entry(_EARNINGS_FCF_CATALOG, "val.formula.capital.fcf_standard_equity_parent_share").entry
    standard_parent_outcome = evaluate_formula(standard_parent_entry_ref, {
        "cfo": cfo_operand, "capex_standard": capex_operand,
        "parent_net_income": parent_ni_operand, "total_net_income": total_ni_operand,
    })
    cash_flow_bases.append({
        "cash_flow_basis_id": "cf-fcf-standard-parent-share",
        "cash_flow_type": "standard_fcf_parent_share",
        "period_anchor_ref": period_anchor_ref,
        **({"period_variant": period_variant} if period_variant in ("fy", "true_ttm") else {}),
        "amount": _envelope(standard_parent_outcome, unit="units", currency=reporting_currency),
        "formula_ref": standard_parent_entry_ref["entry_id"],
        "status": standard_parent_outcome.status,
    })

    after_lease_parent_entry_ref = registry.select_entry(_EARNINGS_FCF_CATALOG, "val.formula.capital.fcf_after_lease_equity_parent_share").entry
    after_lease_parent_outcome = evaluate_formula(after_lease_parent_entry_ref, {
        "cfo": cfo_operand, "capex_standard": capex_operand, "lease_principal_paid": lease_operand,
        "parent_net_income": parent_ni_operand, "total_net_income": total_ni_operand,
    })
    cash_flow_bases.append({
        "cash_flow_basis_id": "cf-fcf-after-lease-parent-share",
        "cash_flow_type": "after_lease_fcf_parent_share",
        "period_anchor_ref": period_anchor_ref,
        **({"period_variant": period_variant} if period_variant in ("fy", "true_ttm") else {}),
        "amount": _envelope(after_lease_parent_outcome, unit="units", currency=reporting_currency),
        "formula_ref": after_lease_parent_entry_ref["entry_id"],
        "status": after_lease_parent_outcome.status,
    })

    # FCFE requires a net-borrowing/lease bridge this PR does not source
    # (docs/valuation-t67-03-*.md Section 9): always unavailable, never a
    # silent fallback to standard_fcf under a different label.
    cash_flow_bases.append({
        "cash_flow_basis_id": "cf-fcfe",
        "cash_flow_type": "fcfe",
        "period_anchor_ref": period_anchor_ref,
        **({"period_variant": period_variant} if period_variant in ("fy", "true_ttm") else {}),
        "amount": {"status": "unavailable", "reason_codes": [{"code": "method.cash_flow_claim_mismatch", "severity": "warning"}]},
        "formula_ref": "val.formula.method.fcfe_yield",
        "status": "unavailable",
    })

    # parent_equity is always sourced from the MOST RECENT period
    # (method_basis.py's primary_ctx -- a point-in-time balance-sheet
    # figure, never TTM-assembled), which is not necessarily
    # financial_period_refs[0] (found 2026-07-26, ARCLK: refs are ordered
    # [FY, latest quarter, prior-year quarter], so the generic
    # period_anchor_ref above pointed at 2025-FY while parent_equity was
    # actually 2026-Q1's). Anchor book equity to whichever ref has the
    # latest period_end instead of reusing the generic first-ref anchor.
    book_equity_period_ref = max(method_basis.financial_period_refs, key=lambda r: r.period_end) if method_basis.financial_period_refs else None
    book_equity_basis = {
        "book_equity_basis_id": "book-equity-parent",
        "period_anchor_ref": book_equity_period_ref.source_id if book_equity_period_ref else period_anchor_ref,
        "amount": _envelope(method_basis.parent_equity, currency=reporting_currency if method_basis.parent_equity.status == "available" else None),
        "status": method_basis.parent_equity.status,
    }

    distribution_basis = _build_distribution_basis(method_basis.cash_dividends_paid_total, spot_basic_shares=spot_basic_shares, reporting_currency=reporting_currency)

    return earnings_bases, cash_flow_bases, book_equity_basis, distribution_basis


def _build_distribution_basis(cash_dividends_paid_total: FieldValue, *, spot_basic_shares: Decimal, reporting_currency: str) -> dict[str, Any]:
    if cash_dividends_paid_total.status != "available":
        return {
            "dividend_per_share": {"status": "unavailable", "reason_codes": [{"code": "method.dividend_event_missing", "severity": "warning"}]},
            "status": "unavailable",
        }

    total = _base_amount(cash_dividends_paid_total.value, cash_dividends_paid_total.unit)
    if total == 0:
        return {
            "dividend_per_share": _envelope(FormulaOutcome(status="available", value=Decimal(0)), currency=reporting_currency),
            "event_type": "no_dividend_governed",
            "formula_ref": "derived:dividend_per_share=cash_dividends_paid_total/spot_basic_shares_outstanding",
            "status": "available",
        }
    if spot_basic_shares <= 0:
        return {
            "dividend_per_share": {"status": "calculation_blocked", "reason_codes": [{"code": "method.denominator_zero", "severity": "warning"}]},
            "status": "calculation_blocked",
        }
    per_share = total / spot_basic_shares
    return {
        "dividend_per_share": _envelope(FormulaOutcome(status="available", value=per_share), currency=reporting_currency),
        "event_type": "trailing_paid_12m",
        "formula_ref": "derived:dividend_per_share=cash_dividends_paid_total/spot_basic_shares_outstanding",
        "status": "available",
    }


def _build_company_specific_inputs(company_specific: CompanySpecificBasis | None) -> dict[str, Any] | None:
    if company_specific is None or company_specific.module == "generic":
        return {"module": "generic"}
    result: dict[str, Any] = {"module": company_specific.module, "period_anchor_ref": company_specific.period_anchor_source_id}
    for schema_field, field_value in company_specific.fields.items():
        result[schema_field] = _envelope(field_value)
    return result
