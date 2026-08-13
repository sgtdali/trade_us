"""The controlled public method-basis boundary (T71-B).

T70-A/T70-B built :mod:`engine.public.financial_basis`
strictly for the *capital* ledger (market cap / debt / lease / cash / NCI /
preferred / equity-method bridge) that the T70 EV/net-debt formulas need.
docs/valuation-t70-05-*.md Section 4's own "Capital components" list never
mentions earnings, cash flow, EBIT, EBITDA, or dividends -- so, as recorded
in docs/valuation-t70-t74-implementation-todo.md Section 10.5 item 5's
verified nuance, populating those was correctly left out of scope for
T70-B and assigned to T71 (the method engine) instead.

This module is that closing piece: a second, separate, immutable public
projection -- :class:`MethodBasis` -- built through the exact same
authored-period loading and point-in-time safety machinery as
:class:`~engine.public.financial_basis.FinancialBasis`
(reused directly, not duplicated), but scoped to the income-statement,
cash-flow-statement, and sector-operational facts the T71 current-method
engine needs: parent net income, core EBIT, canonical EBITDA/EBITDAR
(reported-only; no constructed bridge), parent book equity, CFO, capex,
lease principal paid, and aggregate cash dividends paid.

TTM (trailing-twelve-month) support, added 2026-07-26: when the resolved
primary period is a bare quarter (``"Y-Qn"``) and both its immediately
preceding fiscal year (``"Y-1-FY"``) and the same quarter one year earlier
(``"Y-1-Qn"``) are also present among the caller's ``financial_period_refs``,
the seven flow fields below are assembled as
``TTM = FY(Y-1) + Qn(Y) - Qn(Y-1)`` (cumulative KAP-style filings, so this
is subtraction of two cumulative figures plus a full prior year -- the
standard TTM-from-cumulative-quarters shortcut, not the four-discrete-
quarter summation described below). ``period_variant`` becomes
``"true_ttm"`` in that case.

**Known, deliberate limitation of this TTM assembly:** it is purely nominal
-- it does NOT correct for IAS 29 (TMS 29) hyperinflation restatement.
Turkish IAS-29 reporters (AEFES, ARCLK, EREGL, ...) restate each filing's
comparative figures to *that filing's own* balance-sheet-date purchasing
power, so ``FY(Y-1)``'s figures and ``Qn(Y-1)``'s figures are not
necessarily expressed in the same purchasing-power terms -- subtracting
them can carry a real (if usually modest, single-quarter) distortion this
code does not detect or correct. This was a deliberate, user-approved
scope decision (see wiki/systems/valuation-pipeline.md): a fully correct
fix would require a general price-index-based normalization layer that
does not exist in this repository. Every ``true_ttm`` result must be
labeled as an approximation wherever it is displayed (see
``config/valuation/reporting/labels.json``) -- never presented as exact.

This is a genuinely separate assembly path from
:func:`engine.periods.assemble_ttm` (which sums four already-
discrete quarters from a ``data/financial-series/{TICKER}/*.json`` history
file, THYAO/aviation's ``net_debt_to_ebitdar_ttm`` being the only current
user, via the older derivation engine in
:mod:`engine.derivation.engine`) -- that mechanism needs a
data shape (a pre-built discrete-quarter history) this module's callers do
not have. The two are not meant to be unified by this change.

canonical_ebitda/canonical_ebitdar are excluded from TTM assembly: they are
the company's own reported (non-IFRS) figures, not summable from IFRS
flow statements, and are essentially never disclosed on a discrete-quarter
basis anyway -- they are read from whichever of the current quarter or the
prior FY actually discloses one (preferring the current quarter), same as
before this change. ``parent_equity`` is a balance-sheet (point-in-time)
fact and was never subject to TTM to begin with.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..errors import PipelineError
from ..paths import safe_ticker
from .financial_basis import (
    FieldValue,
    FinancialPeriodRef,
    _field_from_metric,
    _load_period_contexts,
    _operational_field,
    _require_point_in_time_safe,
)

__all__ = ["MethodBasis", "MethodBasisError", "build_method_basis"]


class MethodBasisError(PipelineError):
    """A public MethodBasis boundary invariant was violated."""


#: engine.periods.Period.kind values that back an explicit FY
#: method-basis period variant. Every other kind (quarterly, half_year,
#: nine_month) projects period_variant="unavailable" -- T71 never
#: annualizes a partial period into a fabricated TTM/FY figure.
_FY_PERIOD_KINDS = frozenset({"annual"})


@dataclass(frozen=True)
class MethodBasis:
    """Immutable projection of the income-statement/cash-flow-statement/
    sector-operational facts the T71 current-method engine needs, on top
    of (never instead of) the capital-only :class:`~.financial_basis.FinancialBasis`.

    Every field is a :class:`~.financial_basis.FieldValue`: a missing fact
    stays ``unavailable``, never coerced to zero. ``canonical_ebitda`` and
    ``canonical_ebitdar`` are reported-only figures (the company's own
    disclosed ``ebitda_amount``/``ebitdar_amount``) -- this module never
    constructs an EBITDA/EBITDAR bridge from EBIT + D&A + rent, since no
    owning contract defines that bridge's exact component list.

    ``canonical_ebitda_period_variant``/``canonical_ebitdar_period_variant``
    are tracked SEPARATELY from the basis-wide ``period_variant``: EBITDA/
    EBITDAR are never TTM-assembled (see module docstring), so even when
    ``period_variant == "true_ttm"`` (the flow metrics genuinely are a TTM
    sum), a canonical EBITDA/EBITDAR figure sourced by falling back to the
    prior FY is still an as-disclosed FY figure, not a TTM one -- reusing
    the basis-wide flag for it would mislabel a stale FY number as "Son 12
    Ay (TTM)" in the report (found 2026-07-26, ARCLK: canonical EBITDA
    fell back to 2025-FY's 30.009 milyar TL unchanged, but was labeled
    TTM). Value is ``"fy"`` when sourced from an annual-kind context,
    ``""`` when sourced directly from a quarterly context that itself
    disclosed the figure (rare -- no accurate enum label applies to a
    single, non-TTM quarter; the report falls back to a plain period
    anchor rather than fabricating a "fy"/"true_ttm" claim).
    """

    ticker: str
    as_of_date: date
    reporting_currency: str
    period_variant: str  # "fy" | "true_ttm" | "unavailable"
    financial_period_refs: tuple[FinancialPeriodRef, ...]

    parent_net_income: FieldValue
    total_net_income: FieldValue
    core_ebit: FieldValue
    canonical_ebitda: FieldValue
    canonical_ebitda_period_variant: str
    canonical_ebitda_reconciliation_status: str
    canonical_ebitda_comparability: str
    canonical_ebitdar: FieldValue
    canonical_ebitdar_period_variant: str
    parent_equity: FieldValue

    cfo: FieldValue
    capex: FieldValue
    lease_principal_paid: FieldValue

    cash_dividends_paid_total: FieldValue


def _find_ttm_triple(contexts, primary_ctx):
    """Returns (fy_prior_ctx, qn_prior_year_ctx) for the TTM identity
    ``FY + Qn(current YTD) - Qn(prior-year YTD)``, or None when the three
    legs do not form one clean twelve-month window. primary_ctx itself is
    the "Qn(Y)" leg -- callers already have it.

    The legs are selected by ``period_end`` DATE, never by fiscal-year
    label arithmetic. An issuer whose fiscal year ends in January or
    February carries the same label year on its FY and on the quarters
    that follow it -- Kroger's ``2025-FY`` ended 2025-02-01 while its
    ``2025-Q2`` ended 2025-08-16 -- so the old ``fiscal_year - 1`` lookup
    silently found nothing and the entire basis fell back to a stale FY
    figure. Found 2026-08-04 in the US walk-forward backtest: KR priced a
    current market cap against fiscal-year earnings in 13 of 15 months.
    The date rule reduces to the old label arithmetic for December
    year-end issuers, so it is a generalization rather than a new
    convention."""
    if primary_ctx.period.kind != "quarterly":
        return None
    target_quarter = primary_ctx.period.quarter
    primary_end = primary_ctx.direct_financials["period_end"]

    # Most recent earlier YTD leg closing the same quarter number. Taking
    # the maximum (rather than the first match) keeps the window as short
    # as the authored data allows when several prior years are present.
    qn_prior_year_ctx = max(
        (
            c for c in contexts
            if c.period.kind == "quarterly"
            and c.period.quarter == target_quarter
            and c.direct_financials["period_end"] < primary_end
        ),
        key=lambda c: c.direct_financials["period_end"],
        default=None,
    )
    if qn_prior_year_ctx is None:
        return None
    prior_end = qn_prior_year_ctx.direct_financials["period_end"]

    # Exactly one fiscal year must close strictly between the two YTD
    # legs. That is what makes the sum a true twelve-month window: zero
    # such years means the legs are within one fiscal year, and more than
    # one means the prior YTD leg is stale by a year or more, which would
    # silently stretch the window instead of failing.
    fy_between = [
        c for c in contexts
        if c.period.kind == "annual"
        and prior_end < c.direct_financials["period_end"] < primary_end
    ]
    if len(fy_between) != 1:
        return None
    return fy_between[0], qn_prior_year_ctx


def _operational_context_value(financial_operational_data, metric_id: str, key: str, default: str) -> str:
    if not financial_operational_data:
        return default
    metric = next(
        (m for m in financial_operational_data.get("metrics", ()) if m.get("metric_id") == metric_id),
        None,
    )
    context = (metric or {}).get("context")
    if not isinstance(context, dict):
        return default
    value = context.get(key)
    return value if isinstance(value, str) and value else default


def _ttm_field(
    fy_prior_ctx, qn_prior_year_ctx, qn_current_ctx, metric_id: str, *, missing_reason: str, as_positive_outflow: bool = False
) -> FieldValue:
    """TTM = FY(Y-1) + Qn(Y) - Qn(Y-1), applied to one flow metric across
    the three authored periods' direct_financials. Purely nominal (see this
    module's docstring for the IAS-29 caveat) -- never attempts any
    purchasing-power correction. Falls back to "unavailable" (never a
    guess) if any of the three legs is itself unavailable, or if their
    units/currencies disagree (a genuine data problem, not something to
    paper over)."""
    from decimal import Decimal

    getter = _field_from_metric_as_positive_outflow if as_positive_outflow else _field_from_metric
    fy_field = getter(fy_prior_ctx.direct_financials, metric_id, missing_reason=missing_reason)
    qn_prior_field = getter(qn_prior_year_ctx.direct_financials, metric_id, missing_reason=missing_reason)
    qn_current_field = getter(qn_current_ctx.direct_financials, metric_id, missing_reason=missing_reason)

    legs = (fy_field, qn_prior_field, qn_current_field)
    if any(leg.status != "available" for leg in legs):
        return FieldValue(status="unavailable", reason_codes=("method.ttm_missing_constituent_period",))
    if len({leg.currency for leg in legs}) != 1:
        return FieldValue(status="unavailable", reason_codes=("method.ttm_missing_constituent_period",))

    scale_multipliers = {
        "unit": Decimal("1"),
        "units": Decimal("1"),
        "thousand": Decimal("1000"),
        "million": Decimal("1000000"),
        "billion": Decimal("1000000000"),
    }

    def _multiplier(unit: str | None) -> Decimal | None:
        if not unit:
            return None
        normalized = unit.lower()
        for scale_name, multiplier in scale_multipliers.items():
            if normalized == scale_name or normalized.startswith(f"{scale_name}_"):
                return multiplier
        return None

    multipliers = tuple(_multiplier(leg.unit) for leg in legs)
    if len({leg.unit for leg in legs}) == 1:
        multipliers = (Decimal("1"), Decimal("1"), Decimal("1"))
    elif any(multiplier is None for multiplier in multipliers):
        return FieldValue(status="unavailable", reason_codes=("method.ttm_missing_constituent_period",))

    fy_multiplier, prior_multiplier, current_multiplier = multipliers
    ttm_base = (
        Decimal(fy_field.value) * fy_multiplier
        + Decimal(qn_current_field.value) * current_multiplier
        - Decimal(qn_prior_field.value) * prior_multiplier
    )
    ttm_value = ttm_base / fy_multiplier
    return FieldValue(
        status="available",
        value=str(ttm_value),
        unit=fy_field.unit,
        currency=fy_field.currency,
        source_id=f"ttm:{fy_field.source_id}+{qn_current_field.source_id}-{qn_prior_field.source_id}",
    )


def _field_from_metric_as_positive_outflow(direct_financials, metric_id: str, *, missing_reason: str) -> FieldValue:
    """T67.3's FCF construction (``FCF_standard = CFO - capex_standard``)
    requires capex/lease-principal as a normalized *positive* outflow
    magnitude (docs/valuation-t67-03-*.md Section 7: "Capex sign source'tan
    normalized positive outflow olarak gelir"). The fundamental pipeline's
    own generic validator requires the opposite convention on the raw
    authored metric itself (a cash *outflow* line is stored signed
    negative -- confirmed by ``capex_sign_positive`` /
    ``lease_payments_sign_positive`` validation rules). This function
    bridges the two conventions by negating an available negative value;
    it never flips a positive raw value (which would silently hide a
    genuine sign anomaly in the source) and never invents a value that
    was not authored."""
    from decimal import Decimal

    field = _field_from_metric(direct_financials, metric_id, missing_reason=missing_reason)
    if field.status != "available":
        return field
    raw = Decimal(field.value)
    if raw > 0:
        return field
    return FieldValue(status="available", value=str(-raw), unit=field.unit, currency=field.currency, source_id=field.source_id)


def build_method_basis(
    *,
    data_root: Path | None,
    ticker: str,
    as_of_date: date,
    financial_period_refs: tuple[FinancialPeriodRef, ...],
    config_root: Path | None = None,
) -> MethodBasis:
    """Build an immutable :class:`MethodBasis` from exact authored
    fundamental periods -- the same ``financial_period_refs`` a caller
    would also pass to :func:`~.financial_basis.build_financial_basis`.
    Never reads a generated ratio/signal/summary/report file, and never
    scans for an implicit "latest" period."""
    ticker = safe_ticker(ticker)
    contexts = _load_period_contexts(
        data_root=data_root, ticker=ticker,
        financial_period_refs=financial_period_refs, config_root=config_root,
    )
    _require_point_in_time_safe(contexts, ticker=ticker, as_of_date=as_of_date)

    primary_ctx = max(contexts, key=lambda c: c.direct_financials["period_end"])
    reporting_currency = primary_ctx.direct_financials.get("currency")
    if not reporting_currency:
        raise MethodBasisError(f"authored direct financials for {ticker} declare no currency")

    ttm_triple = _find_ttm_triple(contexts, primary_ctx) if primary_ctx.period.kind == "quarterly" else None

    fy_contexts = [c for c in contexts if c.period.kind in _FY_PERIOD_KINDS]
    if ttm_triple is not None:
        fy_prior_ctx, qn_prior_year_ctx = ttm_triple
        period_variant = "true_ttm"

        def _ttm(metric_id: str, *, missing_reason: str, as_positive_outflow: bool = False) -> FieldValue:
            return _ttm_field(
                fy_prior_ctx, qn_prior_year_ctx, primary_ctx, metric_id,
                missing_reason=missing_reason, as_positive_outflow=as_positive_outflow,
            )

        # canonical_ebitda/ebitdar are never TTM-assembled (see module
        # docstring) -- read whichever of the current quarter or the prior
        # FY actually discloses one, preferring the more current figure.
        # Each fallback is tracked with its OWN period-variant (never the
        # basis-wide "true_ttm" flag above): a figure that fell back to the
        # prior FY is an as-disclosed FY number, not a TTM one.
        ebitda = _operational_field(primary_ctx.financial_operational_data, ("ebitda_amount",))
        if ebitda.status == "available":
            ebitda_period_variant = ""
            ebitda_doc = primary_ctx.financial_operational_data
        else:
            ebitda = _operational_field(fy_prior_ctx.financial_operational_data, ("ebitda_amount",))
            ebitda_period_variant = "fy" if ebitda.status == "available" else ""
            ebitda_doc = fy_prior_ctx.financial_operational_data
        ebitdar = _operational_field(primary_ctx.financial_operational_data, ("ebitdar_amount",))
        if ebitdar.status == "available":
            ebitdar_period_variant = ""
        else:
            ebitdar = _operational_field(fy_prior_ctx.financial_operational_data, ("ebitdar_amount",))
            ebitdar_period_variant = "fy" if ebitdar.status == "available" else ""

        return MethodBasis(
            ticker=ticker,
            as_of_date=as_of_date,
            reporting_currency=reporting_currency,
            period_variant=period_variant,
            financial_period_refs=tuple(financial_period_refs),
            parent_net_income=_ttm("net_profit_attributable_parent", missing_reason="method.period_basis_unavailable"),
            total_net_income=_ttm("net_profit_for_period", missing_reason="method.period_basis_unavailable"),
            core_ebit=_ttm("operating_profit_before_investment_activities", missing_reason="method.period_basis_unavailable"),
            canonical_ebitda=ebitda,
            canonical_ebitda_period_variant=ebitda_period_variant,
            canonical_ebitda_reconciliation_status=_operational_context_value(
                ebitda_doc, "ebitda_amount", "reconciliation_status", ""
            ),
            canonical_ebitda_comparability=_operational_context_value(
                ebitda_doc, "ebitda_amount", "comparability", ""
            ),
            canonical_ebitdar=ebitdar,
            canonical_ebitdar_period_variant=ebitdar_period_variant,
            parent_equity=_field_from_metric(primary_ctx.direct_financials, "equity_attributable_to_parent", missing_reason="method.period_basis_unavailable"),
            cfo=_ttm("cf_net_operating_activities", missing_reason="method.cash_flow_claim_mismatch"),
            capex=_ttm("cf_capex_ppe_intangible", missing_reason="method.cash_flow_claim_mismatch", as_positive_outflow=True),
            lease_principal_paid=_ttm("cf_lease_payments", missing_reason="method.lease_basis_mismatch", as_positive_outflow=True),
            cash_dividends_paid_total=_ttm("cf_dividends_paid", missing_reason="method.dividend_event_missing", as_positive_outflow=True),
        )

    if fy_contexts:
        flow_ctx = max(fy_contexts, key=lambda c: c.direct_financials["period_end"])
        period_variant = "fy"
    else:
        flow_ctx = primary_ctx
        period_variant = "fy" if primary_ctx.period.kind in _FY_PERIOD_KINDS else "unavailable"

    flow_ctx_ebitda = _operational_field(flow_ctx.financial_operational_data, ("ebitda_amount",))
    flow_ctx_ebitdar = _operational_field(flow_ctx.financial_operational_data, ("ebitdar_amount",))
    flow_ctx_is_fy = flow_ctx.period.kind in _FY_PERIOD_KINDS

    return MethodBasis(
        ticker=ticker,
        as_of_date=as_of_date,
        reporting_currency=reporting_currency,
        period_variant=period_variant,
        financial_period_refs=tuple(financial_period_refs),
        parent_net_income=_field_from_metric(flow_ctx.direct_financials, "net_profit_attributable_parent", missing_reason="method.period_basis_unavailable"),
        total_net_income=_field_from_metric(flow_ctx.direct_financials, "net_profit_for_period", missing_reason="method.period_basis_unavailable"),
        core_ebit=_field_from_metric(flow_ctx.direct_financials, "operating_profit_before_investment_activities", missing_reason="method.period_basis_unavailable"),
        canonical_ebitda=flow_ctx_ebitda,
        canonical_ebitda_period_variant="fy" if flow_ctx_is_fy and flow_ctx_ebitda.status == "available" else "",
        canonical_ebitda_reconciliation_status=_operational_context_value(
            flow_ctx.financial_operational_data, "ebitda_amount", "reconciliation_status", ""
        ),
        canonical_ebitda_comparability=_operational_context_value(
            flow_ctx.financial_operational_data, "ebitda_amount", "comparability", ""
        ),
        canonical_ebitdar=flow_ctx_ebitdar,
        canonical_ebitdar_period_variant="fy" if flow_ctx_is_fy and flow_ctx_ebitdar.status == "available" else "",
        parent_equity=_field_from_metric(primary_ctx.direct_financials, "equity_attributable_to_parent", missing_reason="method.period_basis_unavailable"),
        cfo=_field_from_metric(flow_ctx.direct_financials, "cf_net_operating_activities", missing_reason="method.cash_flow_claim_mismatch"),
        capex=_field_from_metric_as_positive_outflow(flow_ctx.direct_financials, "cf_capex_ppe_intangible", missing_reason="method.cash_flow_claim_mismatch"),
        lease_principal_paid=_field_from_metric_as_positive_outflow(flow_ctx.direct_financials, "cf_lease_payments", missing_reason="method.lease_basis_mismatch"),
        cash_dividends_paid_total=_field_from_metric_as_positive_outflow(flow_ctx.direct_financials, "cf_dividends_paid", missing_reason="method.dividend_event_missing"),
    )
