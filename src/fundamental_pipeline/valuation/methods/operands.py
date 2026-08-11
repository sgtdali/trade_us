"""Immutable operand binding: compiled plan operand symbols -> exact
``valuation-inputs`` basis nodes (docs/valuation-t71-04-operand-binding-current-method-evaluator-specification.md
Section 2-7).

The binder only ever reads the frozen ``valuation-inputs`` artifact dict
(never a report, signal, summary, or raw source document) and the
compiled plan's own declarations. Missing, zero, and negative stay
distinct: a missing basis becomes a ``BoundOperand(status="unavailable")``,
never a fabricated zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any, Mapping

from ..errors import OperandBindingError
from .models import OperandDeclaration
from .numeric import to_exact_rational

#: economic_type -> where in a valuation-inputs artifact its candidate
#: basis node(s) live, and how to find the right one. "point_in_time"
#: economic types have no period_variant concept (a market cap, book
#: equity value, EV, price, or per-share dividend figure is always as-of a
#: single date, never a TTM/FY flow); "flow" economic types are read from
#: an array whose members carry an explicit period_variant tag.
_POINT_IN_TIME_ECONOMIC_TYPES = frozenset({
    "market_cap", "parent_equity", "enterprise_value_ex_lease", "enterprise_value_incl_lease",
    "dividend_per_share", "spot_price_per_share", "one",
})
_FLOW_ECONOMIC_TYPES = frozenset({
    "parent_net_income", "core_ebit", "canonical_ebitda", "canonical_ebitdar",
    "standard_fcf", "after_lease_fcf", "fcfe",
    "standard_fcf_parent_share", "after_lease_fcf_parent_share",
})

_EARNINGS_TYPE_BY_ECONOMIC_TYPE = {
    "parent_net_income": "reported_parent_net_income",
    "core_ebit": "reported_core_ebit",
}
_EARNINGS_BASIS_ID_BY_ECONOMIC_TYPE = {
    "canonical_ebitda": "earn-ebitda",
    "canonical_ebitdar": "earn-ebitdar",
}
_CASH_FLOW_TYPE_BY_ECONOMIC_TYPE = {
    "standard_fcf": "standard_fcf",
    "after_lease_fcf": "after_lease_fcf",
    "fcfe": "fcfe",
    "standard_fcf_parent_share": "standard_fcf_parent_share",
    "after_lease_fcf_parent_share": "after_lease_fcf_parent_share",
}


@dataclass(frozen=True)
class BoundOperand:
    symbol: str
    economic_type: str
    status: str
    value: Fraction | None
    basis_ref: str | None
    currency: str | None
    sign_state: str
    reason_codes: tuple[str, ...]

    @property
    def available(self) -> bool:
        return self.status == "available"


def _sign_state(value: Decimal) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


def _envelope_to_bound(symbol: str, economic_type: str, envelope: Mapping[str, Any] | None, *, basis_ref: str | None) -> BoundOperand:
    if not envelope or envelope.get("status") != "available":
        reason_codes = tuple(rc.get("code", "") for rc in (envelope or {}).get("reason_codes", ())) or ("status.required_observation_missing",)
        status = (envelope or {}).get("status", "unavailable")
        return BoundOperand(symbol=symbol, economic_type=economic_type, status=status, value=None, basis_ref=basis_ref, currency=None, sign_state="unknown", reason_codes=reason_codes)
    multipliers = {
        "units": Decimal("1"),
        "shares": Decimal("1"),
        "million_usd": Decimal("1000000"),
        "million_try": Decimal("1000000"),
        "thousand_usd": Decimal("1000"),
        "thousand_try": Decimal("1000"),
    }
    decimal_value = Decimal(envelope["value"])
    multiplier = multipliers.get(envelope.get("unit"))
    if multiplier is not None:
        with localcontext() as context:
            context.prec = 50
            decimal_value *= multiplier
    return BoundOperand(
        symbol=symbol, economic_type=economic_type, status="available",
        value=to_exact_rational(str(decimal_value)), basis_ref=basis_ref,
        currency=envelope.get("currency"), sign_state=_sign_state(decimal_value), reason_codes=(),
    )


def _unavailable(symbol: str, economic_type: str, reason_code: str) -> BoundOperand:
    return BoundOperand(symbol=symbol, economic_type=economic_type, status="unavailable", value=None, basis_ref=None, currency=None, sign_state="unknown", reason_codes=(reason_code,))


def _find_flow_basis(
    valuation_inputs: Mapping[str, Any], *, economic_type: str, required_period_rule: str | None,
) -> tuple[Mapping[str, Any] | None, str | None]:
    """Return ``(matching_entry_or_None, basis_ref_or_None)`` for a
    flow-type (earnings/cash-flow) economic type, searching
    ``earnings_bases``/``cash_flow_bases`` for candidates matching the
    exact economic type, then filtering by period compatibility
    (docs/valuation-t71-04-*.md Section 6): a ``required_period_rule`` of
    ``"true_ttm"``/``"fy"`` demands an exact tag match; ``None`` (the
    FCF/EV formulas, whose catalog operand declaration leaves period_rule
    unconstrained) accepts any *tagged* entry (never an untagged one --
    an untagged entry means the upstream basis could not classify a
    compatible true-TTM/FY period at all, so it is never silently treated
    as usable, i.e. no single-quarter annualization).
    """
    candidates: list[Mapping[str, Any]] = []
    if economic_type in _EARNINGS_TYPE_BY_ECONOMIC_TYPE:
        wanted = _EARNINGS_TYPE_BY_ECONOMIC_TYPE[economic_type]
        candidates = [e for e in valuation_inputs.get("earnings_bases", ()) if e.get("earnings_type") == wanted]
    elif economic_type in _EARNINGS_BASIS_ID_BY_ECONOMIC_TYPE:
        wanted_id = _EARNINGS_BASIS_ID_BY_ECONOMIC_TYPE[economic_type]
        candidates = [e for e in valuation_inputs.get("earnings_bases", ()) if e.get("earnings_basis_id") == wanted_id]
    elif economic_type in _CASH_FLOW_TYPE_BY_ECONOMIC_TYPE:
        wanted = _CASH_FLOW_TYPE_BY_ECONOMIC_TYPE[economic_type]
        candidates = [e for e in valuation_inputs.get("cash_flow_bases", ()) if e.get("cash_flow_type") == wanted]

    if not candidates:
        return None, None
    if len(candidates) > 1:
        # Conflicting eligible candidates: calculation_blocked, never
        # averaged or first-entry selected (docs/valuation-t71-04-*.md
        # Section 4). Surface as "found, but no matching tag" so the
        # caller emits calculation_blocked rather than unavailable.
        return {"status": "calculation_blocked"}, None

    entry = candidates[0]
    tag = entry.get("period_variant")
    basis_id_key = "earnings_basis_id" if "earnings_basis_id" in entry else "cash_flow_basis_id"
    basis_ref = entry.get(basis_id_key)

    if required_period_rule is not None:
        if tag != required_period_rule:
            return None, None
        return entry, basis_ref

    if tag is None:
        return None, None
    return entry, basis_ref


def bind_operand(
    declaration: OperandDeclaration, valuation_inputs: Mapping[str, Any],
) -> BoundOperand:
    """Bind one declared operand symbol against ``valuation_inputs``.
    Never raises for ordinary domain-invalid state (missing basis,
    conflicting candidates, wrong claim/currency) -- those become a
    non-``available`` :class:`BoundOperand`. Only a structurally malformed
    ``valuation_inputs`` argument (wrong Python type) raises
    :class:`OperandBindingError`."""
    if not isinstance(valuation_inputs, Mapping):
        raise OperandBindingError("valuation_inputs must be a mapping")

    symbol = declaration.operand_id
    economic_type = symbol  # T71-A operand IDs are the economic_type names themselves

    if economic_type == "one":
        return BoundOperand(symbol=symbol, economic_type=economic_type, status="available", value=Fraction(1), basis_ref=None, currency=None, sign_state="positive", reason_codes=())

    if economic_type == "market_cap":
        market_cap_basis = valuation_inputs.get("market_cap_basis", {})
        envelope = market_cap_basis.get("reporting_currency_total_market_cap") or market_cap_basis.get("native_total_market_cap")
        return _envelope_to_bound(symbol, economic_type, envelope, basis_ref="comp-market-cap")

    if economic_type == "parent_equity":
        book_equity_basis = valuation_inputs.get("book_equity_basis")
        if book_equity_basis is None:
            return _unavailable(symbol, economic_type, "method.period_basis_unavailable")
        return _envelope_to_bound(symbol, economic_type, book_equity_basis.get("amount"), basis_ref=book_equity_basis.get("book_equity_basis_id"))

    if economic_type in ("enterprise_value_ex_lease", "enterprise_value_incl_lease"):
        basis_type = "lease_exclusive" if economic_type == "enterprise_value_ex_lease" else "lease_inclusive"
        candidates = [e for e in valuation_inputs.get("ev_basis_family", ()) if e.get("basis_type") == basis_type]
        if not candidates:
            return _unavailable(symbol, economic_type, "method.lease_basis_mismatch" if basis_type == "lease_inclusive" else "method.period_basis_unavailable")
        entry = candidates[0]
        return _envelope_to_bound(symbol, economic_type, entry.get("enterprise_value"), basis_ref=entry.get("ev_basis_id"))

    if economic_type == "dividend_per_share":
        distribution_basis = valuation_inputs.get("distribution_basis")
        if distribution_basis is None:
            return _unavailable(symbol, economic_type, "method.dividend_event_missing")
        return _envelope_to_bound(symbol, economic_type, distribution_basis.get("dividend_per_share"), basis_ref="distribution-basis")

    if economic_type == "spot_price_per_share":
        price_basis = valuation_inputs.get("price_basis", {})
        envelope = price_basis.get("reporting_currency_price") or price_basis.get("native_price")
        return _envelope_to_bound(symbol, economic_type, envelope, basis_ref="price-basis")

    if economic_type in _FLOW_ECONOMIC_TYPES:
        entry, basis_ref = _find_flow_basis(valuation_inputs, economic_type=economic_type, required_period_rule=declaration.period_rule)
        if entry is not None and entry.get("status") == "calculation_blocked":
            return BoundOperand(symbol=symbol, economic_type=economic_type, status="calculation_blocked", value=None, basis_ref=None, currency=None, sign_state="unknown", reason_codes=("method.same_family_double_count",))
        if entry is None:
            reason = "method.lease_basis_mismatch" if economic_type in ("after_lease_fcf", "after_lease_fcf_parent_share") else "method.period_basis_unavailable"
            if economic_type == "canonical_ebitda":
                reason = "method.canonical_ebitda_unavailable"
            if economic_type == "canonical_ebitdar":
                reason = "method.ebitdar_reconciliation_failed"
            if economic_type in ("standard_fcf", "fcfe", "standard_fcf_parent_share"):
                reason = "method.cash_flow_claim_mismatch"
            return _unavailable(symbol, economic_type, reason)
        return _envelope_to_bound(symbol, economic_type, entry.get("amount"), basis_ref=basis_ref)

    raise OperandBindingError(f"unknown operand economic_type: {economic_type!r}")


def bind_operands(declarations: tuple[OperandDeclaration, ...], valuation_inputs: Mapping[str, Any]) -> dict[str, BoundOperand]:
    """Bind every declared operand symbol of a compiled plan. Returns a
    plain ``dict`` (the caller -- the evaluator -- treats it as read-only;
    :class:`BoundOperand` instances are themselves frozen)."""
    return {decl.operand_id: bind_operand(decl, valuation_inputs) for decl in declarations}
