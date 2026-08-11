"""The controlled public FinancialBasis boundary between the fundamental
pipeline and the valuation namespace.

T70-A defined the immutable value types (:class:`FieldValue`,
:class:`FinancialPeriodRef`, :class:`FinancialBasis`) and a stub
``build_financial_basis`` that always raised ``NotImplementedError``.
T70-B (this module) implements the operational projection: authored
fundamental company/period data -> a concrete, deeply-immutable
:class:`FinancialBasis`, per
docs/valuation-t70-05-financial-basis-input-resolver-specification.md.

Source-of-truth boundary (unchanged from T70-A, enforced by
``tests/unit/valuation/test_import_boundaries.py``): this module, and
everything else under ``fundamental_pipeline.public``, never imports
``fundamental_pipeline.valuation``. It also never reads committed
generated output (derived ratios, signals, summaries, reports) as a
FinancialBasis source -- only :mod:`fundamental_pipeline.context`'s
already-validated authored-input loading (``AnalysisContext``) and the
period model in :mod:`fundamental_pipeline.periods`.

Field-mapping decisions actually exercised by current authored production
data, recorded here rather than left implicit:

* ``short_term_borrowings`` <- authored metric_id ``borrowings_short_term``
* ``current_portion_long_term_borrowings`` <- ``borrowings_long_term_current_portion``
* ``long_term_borrowings`` <- ``borrowings_long_term``
* ``current_lease_liability`` <- ``lease_liabilities_short_term`` (present
  for some companies only; a company with no lease line item at all
  projects ``unavailable``, never zero)
* ``noncurrent_lease_liability`` <- ``lease_liabilities_long_term`` (same
  per-company availability as above)
* ``eligible_cash_components`` <- a single component from ``cash_and_equivalents``
  only. The capital-basis catalog's own applicability note for
  ``eligible_cash_total`` requires "policy-confirmed highly-liquid current
  financial investments" for anything beyond unrestricted cash/equivalents;
  no such policy-confirmation flag exists in current authored data, so
  ``financial_investments_current``/``financial_investments_noncurrent``/
  ``derivative_financial_assets``/``equity_method_investments`` are
  deliberately NOT auto-included here (that would require guessing
  accounting semantics the source data does not state).
* ``noncontrolling_interests`` <- authored metric_id ``noncontrolling_interests``
  (the balance-sheet, point-in-time line -- never the income-statement
  ``net_profit_attributable_noncontrolling`` flow, which is a different
  concept).
* ``issued_shares``, ``treasury_shares``, ``preferred_equity``,
  ``eligible_interest_bearing_other_debt``, ``equity_method_adjustment``:
  no authored fundamental-pipeline field exists for any of these today
  (confirmed by exhaustive search across ``data/financial/**``) --
  ``issued_shares``/``treasury_shares`` are a *market*-side concept
  (``market-snapshot.schema.json``'s ``share_basis``), not a fundamental
  disclosure, so they are correctly absent from FinancialBasis's own
  authored projection. ``equity_method_investments`` exists on the balance
  sheet but has no proven exact semantic parity with the capital-basis
  catalog's *diagnostic, sign-reversed* ``equity_method_adjustment``
  operand, so it is left ``unavailable`` rather than guessed. All five
  fields are always projected as ``FieldValue(status="unavailable", ...)``
  for every currently-authored company -- this is an honest gap, not a
  silent zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Protocol

from ..context import AnalysisContext, build_context
from ..errors import ConfigError, PeriodError, PipelineError, UnsafePathError
from ..paths import safe_ticker
from ..validation.engine import validate_inputs

__all__ = [
    "FieldValue",
    "FinancialPeriodRef",
    "FinancialBasis",
    "FinancialBasisBuilder",
    "build_financial_basis",
    "CompanySpecificBasis",
    "build_company_specific_basis",
]


class FinancialBasisError(PipelineError):
    """A public FinancialBasis boundary invariant was violated."""


_AVAILABILITY_STATUSES = frozenset({
    "available", "not_applicable", "not_meaningful", "unavailable",
    "calculation_blocked", "insufficient_data",
})

#: fundamental_pipeline.periods.Period.kind -> valuation-inputs schema's
#: financial_basis_refs[].period_type vocabulary. "ttm" has no Period.kind
#: counterpart (TTM is an assembled value, not an authored period label) and
#: is therefore never produced by this mapping.
_PERIOD_TYPE_FROM_KIND = {
    "annual": "annual",
    "quarterly": "quarterly",
    "half_year": "half_year",
    "nine_month": "nine_month",
}


@dataclass(frozen=True)
class FieldValue:
    """One capital-basis fact with an explicit availability status. Missing
    facts are never represented as zero: a non-``available`` status
    forbids ``value`` and requires at least one reason code.

    Per docs/valuation-t70-05-financial-basis-input-resolver-specification.md
    Section 4 ("Every component carries value state, decimal/unit/currency,
    source/derivation lineage and reason codes."), a ``FinancialBasis``
    capital-component value carries its own ``unit``/``currency`` (from
    the authored metric, e.g. ``"million_usd"``/``"USD"``) and
    ``source_id`` (the authored metric's ``provenance.source_id`` for a
    directly authored fact, or a ``"derived:<label>"`` marker for a value
    this projection itself computes, e.g. market cap = price x shares --
    "source/derivation lineage" per the same spec sentence covers both).
    This is enforced by :func:`_field_from_metric`, the sole builder T70.5
    capital components go through -- not by this dataclass itself, since
    :class:`FieldValue` is also reused by :class:`CompanySpecificBasis`'s
    operational KPI fields (a distinct, T66.3-governed, often non-monetary
    contract -- e.g. load factor, ASK -- whose source data has no
    equivalent per-metric provenance/currency to carry)."""

    status: str
    value: str | None = None
    unit: str | None = None
    currency: str | None = None
    source_id: str | None = None
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in _AVAILABILITY_STATUSES:
            raise FinancialBasisError(f"unknown availability status: {self.status!r}")
        if self.status == "available":
            if self.value is None:
                raise FinancialBasisError("status='available' requires a non-null value")
        else:
            if self.value is not None:
                raise FinancialBasisError(f"status={self.status!r} forbids a value; missing is never zero")
            if not self.reason_codes:
                raise FinancialBasisError(f"status={self.status!r} requires at least one reason code")


@dataclass(frozen=True)
class FinancialPeriodRef:
    """An exact reference to one authored financial period backing a
    FinancialBasis instance. ``source_id`` is the authored period
    identifier used to locate the period (``fundamental_pipeline.periods``'
    ``period_id`` form, e.g. ``"2026-Q1"``/``"2025-FY"``) -- not a raw
    document provenance ``source_id`` (a different, narrower concept:
    individual metrics may cite different raw-document source IDs within
    one authored period)."""

    source_id: str
    period_end: date
    period_type: str  # "annual" | "quarterly" | "half_year" | "nine_month" | "ttm"


@dataclass(frozen=True)
class FinancialBasis:
    """Immutable, controlled projection of the capital-basis facts a
    valuation input resolver needs. Every capital-ledger field is a
    :class:`FieldValue`, never a bare number -- an absent fact stays
    absent, it is never coerced to zero.

    Field set is closed to exactly what
    ``config/valuation/capital-basis-formulas.json`` requires as operands
    (spot_basic_shares / market_cap_spot_basic / financial_debt_ex_lease /
    lease_liability_total / eligible_cash_total / enterprise value and net
    debt bridges). No field is invented merely to look complete.
    """

    ticker: str
    as_of_date: date
    reporting_currency: str
    financial_period_refs: tuple[FinancialPeriodRef, ...]

    issued_shares: FieldValue
    treasury_shares: FieldValue

    short_term_borrowings: FieldValue
    current_portion_long_term_borrowings: FieldValue
    long_term_borrowings: FieldValue
    eligible_interest_bearing_other_debt: FieldValue

    current_lease_liability: FieldValue
    noncurrent_lease_liability: FieldValue

    eligible_cash_components: tuple[FieldValue, ...]

    noncontrolling_interests: FieldValue
    preferred_equity: FieldValue
    equity_method_adjustment: FieldValue

    def __post_init__(self) -> None:
        if not self.financial_period_refs:
            raise FinancialBasisError("FinancialBasis requires at least one financial_period_refs entry")


class FinancialBasisBuilder(Protocol):
    """The T70-B builder signature. Declared here so downstream code has
    one stable import path independent of the concrete implementation
    below."""

    def __call__(
        self,
        *,
        data_root: object,
        ticker: str,
        as_of_date: date,
        financial_period_refs: tuple[FinancialPeriodRef, ...],
    ) -> FinancialBasis: ...


def _load_period_contexts(
    *, data_root: Path | None, ticker: str, financial_period_refs: tuple[FinancialPeriodRef, ...]
) -> list[AnalysisContext]:
    if not financial_period_refs:
        raise FinancialBasisError("at least one financial_period_refs entry is required")

    contexts: list[AnalysisContext] = []
    for ref in financial_period_refs:
        period_id = ref.source_id
        try:
            ctx = build_context(ticker, period_id, data_root=data_root)
        except (ConfigError, PeriodError, UnsafePathError) as exc:
            raise FinancialBasisError(
                f"cannot build authored context for period ref {ref.source_id!r}: {exc}"
            ) from exc

        if ctx.direct_financials is None:
            raise FinancialBasisError(f"no authored direct financials for {ticker} period {period_id!r}")

        validation = validate_inputs(ctx)
        if not validation.ok:
            messages = "; ".join(str(f) for f in validation.errors)
            raise FinancialBasisError(f"authored inputs failed validation for {ticker} {period_id!r}: {messages}")

        declared_end = ctx.direct_financials.get("period_end")
        if declared_end != ref.period_end.isoformat():
            raise FinancialBasisError(
                f"financial_period_refs period_end {ref.period_end.isoformat()!r} does not match authored "
                f"period_end {declared_end!r} for period {period_id!r}"
            )

        declared_type = _PERIOD_TYPE_FROM_KIND.get(ctx.period.kind)
        if declared_type != ref.period_type:
            raise FinancialBasisError(
                f"financial_period_refs period_type {ref.period_type!r} does not match the derived period_type "
                f"{declared_type!r} (from authored period kind {ctx.period.kind!r}) for period {period_id!r}"
            )

        contexts.append(ctx)

    for other in contexts[1:]:
        problems = _cross_period_accounting_problems(
            contexts[0].direct_financials,
            other.direct_financials,
        )
        if problems:
            raise FinancialBasisError(
                f"financial_period_refs are not accounting-compatible with each other: {'; '.join(problems)}"
            )

    period_types = {c.period.kind for c in contexts}
    _ALLOWED_MIXED = frozenset({"annual", "quarterly"})
    if len(period_types) > 1 and not period_types.issubset(_ALLOWED_MIXED):
        raise FinancialBasisError(
            f"financial_period_refs mixes unsupported period types {sorted(period_types)} -- "
            "only annual+quarterly mixing is permitted for flow/spot valuation basis splitting"
        )

    return contexts


def _require_point_in_time_safe(contexts: list[AnalysisContext], *, ticker: str, as_of_date: date) -> None:
    """docs/valuation-t70-05-financial-basis-input-resolver-specification.md
    Section 6: "publication/availability satisfies cutoff context",
    "restatements use the revision known at cutoff", "no implicit 'latest'
    lookup". ``as_of_date`` is this API's only temporal input (per its own
    Section 3 signature, there is no separate ``cutoff_instant``), so it is
    the point-in-time boundary every authored period is checked against --
    a period whose own ``period_end`` or declared ``publication_date``
    postdates ``as_of_date`` fails closed rather than silently entering
    the projection."""
    as_of_iso = as_of_date.isoformat()
    for ctx in contexts:
        direct_financials = ctx.direct_financials
        period_end = direct_financials.get("period_end")
        if period_end is not None and period_end > as_of_iso:
            raise FinancialBasisError(
                f"{ticker} period {ctx.period.id!r}: period_end {period_end!r} is after as_of_date "
                f"{as_of_iso!r} -- a balance sheet dated after the valuation date can never be used"
            )
        publication_date = direct_financials.get("publication_date")
        if publication_date is not None and publication_date > as_of_iso:
            raise FinancialBasisError(
                f"{ticker} period {ctx.period.id!r}: publication_date {publication_date!r} is after "
                f"as_of_date {as_of_iso!r} -- this period was not yet published as of the valuation date"
            )
        restatement = direct_financials.get("restatement") or {}
        if restatement.get("status") == "restated":
            restated_from = restatement.get("restated_from_publication_date")
            if restated_from is not None and restated_from > as_of_iso:
                raise FinancialBasisError(
                    f"{ticker} period {ctx.period.id!r}: restated_from_publication_date {restated_from!r} "
                    f"is after as_of_date {as_of_iso!r} -- the revision known at cutoff cannot be a future restatement"
                )


def _accounting_context(direct_financials: Mapping):
    from ..periods import AccountingContext

    return AccountingContext(
        currency=direct_financials.get("currency"),
        scale=direct_financials.get("scale"),
        consolidation=direct_financials.get("consolidation"),
        accounting_basis=direct_financials.get("accounting_basis"),
        inflation_adjustment_status=(direct_financials.get("inflation_adjustment") or {}).get("status"),
        restatement_status=(direct_financials.get("restatement") or {}).get("status"),
    )


def _cross_period_accounting_problems(left: Mapping, right: Mapping) -> list[str]:
    """Return genuine accounting incompatibilities between separate filings.

    ``scale`` is a representation choice (unit/thousand/million), not an
    accounting-policy difference. Every projected monetary field carries
    its own explicit unit and downstream arithmetic normalizes that unit,
    so separate periods may safely use different scales. Currency,
    consolidation, accounting basis and inflation treatment remain
    fail-closed compatibility gates.
    """
    return [
        problem
        for problem in _accounting_context(left).compatible_with(_accounting_context(right))
        if not problem.startswith("scale mismatch:")
    ]


def _find_metric(direct_financials: Mapping, metric_id: str) -> Mapping | None:
    for section in ("balance_sheet", "income_statement", "cash_flow_statement"):
        for item in direct_financials.get(section) or ():
            if item.get("metric_id") == metric_id:
                return item
    return None


def _field_from_metric(direct_financials: Mapping, metric_id: str, *, missing_reason: str) -> FieldValue:
    metric = _find_metric(direct_financials, metric_id)
    if metric is None or metric.get("value") is None:
        return FieldValue(status="unavailable", reason_codes=(missing_reason,))
    raw_value = metric["value"]
    if not isinstance(raw_value, (int, float)) or isinstance(raw_value, bool):
        return FieldValue(status="unavailable", reason_codes=(missing_reason,))
    unit = metric.get("unit")
    source_id = (metric.get("provenance") or {}).get("source_id")
    currency = direct_financials.get("currency")
    if not unit or not source_id or not currency:
        return FieldValue(status="unavailable", reason_codes=("capital.field_lineage_incomplete",))
    return FieldValue(status="available", value=str(Decimal(str(raw_value))), unit=unit, currency=currency, source_id=source_id)


_NOT_AUTHORED = FieldValue(status="unavailable", reason_codes=("capital.field_not_authored_in_fundamental_pipeline",))


def build_financial_basis(
    *,
    data_root: Path | None,
    ticker: str,
    as_of_date: date,
    financial_period_refs: tuple[FinancialPeriodRef, ...],
) -> FinancialBasis:
    """Build an immutable :class:`FinancialBasis` from exact authored
    fundamental periods.

    Flow (docs/valuation-t70-05-financial-basis-input-resolver-specification.md
    Section 6): validate ticker -> load company routing + exact requested
    authored periods via :func:`fundamental_pipeline.context.build_context`
    -> validate authored inputs (:func:`fundamental_pipeline.validation.engine.validate_inputs`)
    -> project canonical capital fields from the most recent period's
    direct financials -> deep-freeze (every field is already an immutable
    dataclass; ``eligible_cash_components`` and ``financial_period_refs``
    are tuples, never lists).

    No directory scan ever selects an implicit "latest" period -- every
    period is the caller's exact ``financial_period_refs`` entry, resolved
    only through ``fundamental_pipeline.context.build_context``. Never
    reads a generated ratio/signal/summary/report file.
    """
    ticker = safe_ticker(ticker)
    contexts = _load_period_contexts(data_root=data_root, ticker=ticker, financial_period_refs=financial_period_refs)
    _require_point_in_time_safe(contexts, ticker=ticker, as_of_date=as_of_date)

    # Balance-sheet (point-in-time) capital fields are projected from the
    # period with the latest period_end among the caller's exact,
    # already point-in-time-validated financial_period_refs -- never an
    # implicit directory-scan "latest"; every candidate has already been
    # proven not to postdate as_of_date by _require_point_in_time_safe
    # above. Multiple period refs are accepted (and their accounting
    # contexts cross-checked for compatibility above) but only the most
    # recent one supplies the point-in-time capital ledger.
    primary_ctx = max(contexts, key=lambda c: c.direct_financials["period_end"])
    direct_financials = primary_ctx.direct_financials

    reporting_currency = direct_financials.get("currency")
    if not reporting_currency:
        raise FinancialBasisError(f"authored direct financials for {ticker} declare no currency")

    eligible_cash_components: tuple[FieldValue, ...] = (
        _field_from_metric(direct_financials, "cash_and_equivalents", missing_reason="capital.cash_component_unresolved"),
    )

    basis = FinancialBasis(
        ticker=ticker,
        as_of_date=as_of_date,
        reporting_currency=reporting_currency,
        financial_period_refs=tuple(financial_period_refs),
        issued_shares=_NOT_AUTHORED,
        treasury_shares=_NOT_AUTHORED,
        short_term_borrowings=_field_from_metric(direct_financials, "borrowings_short_term", missing_reason="capital.cash_component_unresolved"),
        current_portion_long_term_borrowings=_field_from_metric(direct_financials, "borrowings_long_term_current_portion", missing_reason="capital.cash_component_unresolved"),
        long_term_borrowings=_field_from_metric(direct_financials, "borrowings_long_term", missing_reason="capital.cash_component_unresolved"),
        eligible_interest_bearing_other_debt=_NOT_AUTHORED,
        current_lease_liability=_field_from_metric(direct_financials, "lease_liabilities_short_term", missing_reason="capital.lease_disclosure_missing"),
        noncurrent_lease_liability=_field_from_metric(direct_financials, "lease_liabilities_long_term", missing_reason="capital.lease_disclosure_missing"),
        eligible_cash_components=eligible_cash_components,
        noncontrolling_interests=_field_from_metric(direct_financials, "noncontrolling_interests", missing_reason="capital.nci_claim_mismatch"),
        # No currently-authored production company discloses these two
        # metric_ids (confirmed by exhaustive search); they are looked up
        # generically rather than hard-coded unavailable so a company that
        # *does* author them (or a synthetic fixture that authors them
        # under this exact, purpose-built metric_id -- never the raw,
        # sign-unproven `equity_method_investments` balance-sheet figure)
        # is picked up through this same production code path, not a
        # parallel one.
        preferred_equity=_field_from_metric(direct_financials, "preferred_equity", missing_reason="capital.field_not_authored_in_fundamental_pipeline"),
        equity_method_adjustment=_field_from_metric(direct_financials, "equity_method_adjustment", missing_reason="capital.jv_paired_treatment_missing"),
    )
    return basis


@dataclass(frozen=True)
class CompanySpecificBasis:
    """Immutable, controlled projection of company-specific (sector
    module) operational KPIs an aviation/steel valuation-inputs
    ``company_specific_inputs`` block may cite. ``module`` mirrors
    ``valuation-inputs.schema.json``'s ``company_specific_inputs``
    discriminator exactly (``"generic"`` | ``"aviation"`` | ``"steel"``).
    ``fields`` is keyed by the exact closed schema field name for that
    module (e.g. ``"ask"``, ``"cask_ex_fuel"``) -- never a ticker-specific
    hard-coded constant, always routed through the company's actual
    ``sector_module``."""

    module: str
    period_anchor_source_id: str
    fields: Mapping[str, FieldValue] = field(default_factory=dict)


#: valuation-inputs.schema.json aviationInputs field -> authored
#: financial-operational metric_id. "passenger_load_factor" and
#: "rask" resolve against a small ordered candidate list because the
#: authored metric_id is period-shape-suffixed
#: (``passenger_load_factor_quarterly``/``_annual``) or has more than one
#: plausible authored counterpart (``rask_adjusted_cargo_capacity`` is
#: preferred over the narrower ``passenger_rask`` since schema "rask" is
#: the total, not passenger-only, unit-revenue figure).
_AVIATION_FIELD_CANDIDATES: Mapping[str, tuple[str, ...]] = {
    "ask": ("ask",),
    "rpk": ("rpk",),
    "passenger_load_factor": ("passenger_load_factor_quarterly", "passenger_load_factor_annual"),
    "rask": ("rask_adjusted_cargo_capacity",),
    "cask": ("cask",),
    "cask_ex_fuel": ("ex_fuel_cask",),
    "ebitdar": ("ebitdar_amount",),
}

#: No steel sector module is registered in
#: fundamental_pipeline.registry.sector_modules today (confirmed: EREGL
#: routes to "generic", not "steel"); this table is kept ready for when
#: one is, but is inert in current production routing.
_STEEL_FIELD_CANDIDATES: Mapping[str, tuple[str, ...]] = {
    "production_tonnes": ("production_tonnes",),
    "sales_tonnes": ("sales_tonnes",),
    "effective_capacity_tonnes": ("effective_capacity_tonnes",),
    "capacity_utilization": ("capacity_utilization",),
    "revenue_per_tonne": ("revenue_per_tonne",),
}


def _operational_field(financial_operational_data: Mapping | None, candidates: tuple[str, ...]) -> FieldValue:
    if financial_operational_data is None:
        return FieldValue(status="unavailable", reason_codes=("status.required_observation_missing",))
    for metric_id in candidates:
        for item in financial_operational_data.get("metrics", financial_operational_data.get("kpis", ())) or ():
            if item.get("metric_id") == metric_id and item.get("value") is not None:
                raw_value = item["value"]
                if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
                    return FieldValue(status="available", value=str(Decimal(str(raw_value))), unit=item.get("unit"))
    return FieldValue(status="unavailable", reason_codes=("status.required_observation_missing",))


def build_company_specific_basis(
    *,
    data_root: Path | None,
    ticker: str,
    as_of_date: date,
    financial_period_refs: tuple[FinancialPeriodRef, ...],
) -> CompanySpecificBasis:
    """Project the sector-module-routed company-specific operational
    fields a ``company_specific_inputs`` block may cite. Uses the same
    exact-period loading as :func:`build_financial_basis`; never scans for
    an implicit latest period and never fabricates a field a company's
    actual sector module does not define."""
    ticker = safe_ticker(ticker)
    contexts = _load_period_contexts(data_root=data_root, ticker=ticker, financial_period_refs=financial_period_refs)
    primary_ctx = max(contexts, key=lambda c: c.direct_financials["period_end"])
    primary_ref = max(financial_period_refs, key=lambda r: r.period_end)

    sector_module_id = primary_ctx.sector_module_id
    financial_operational_data = primary_ctx.financial_operational_data

    if sector_module_id == "aviation":
        fields = {
            schema_field: _operational_field(financial_operational_data, candidates)
            for schema_field, candidates in _AVIATION_FIELD_CANDIDATES.items()
        }
        return CompanySpecificBasis(module="aviation", period_anchor_source_id=primary_ref.source_id, fields=fields)

    if sector_module_id == "steel":
        fields = {
            schema_field: _operational_field(financial_operational_data, candidates)
            for schema_field, candidates in _STEEL_FIELD_CANDIDATES.items()
        }
        return CompanySpecificBasis(module="steel", period_anchor_source_id=primary_ref.source_id, fields=fields)

    return CompanySpecificBasis(module="generic", period_anchor_source_id=primary_ref.source_id, fields={})
