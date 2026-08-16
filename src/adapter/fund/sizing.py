"""Position sizing under the capital policy.

Pure functions over a frozen snapshot. Nothing here reads the ledger, the
clock or the network, which is what lets the property tests assert things like
'a worse downside can never raise a ceiling' across generated inputs.

The whole calculation is one line of arithmetic wrapped in bookkeeping::

    policy_compliant_max_weight = min(readiness_weight, downside_capacity,
                                      max_security_weight, issuer_capacity,
                                      cash_capacity)

The bookkeeping is the valuable part. Every ceiling is computed and kept even
when it does not bind, and the one that does bind is named, because "why only
this much?" is the question the owner will actually ask -- and an answer of
"the model said so" is how a policy stops being believed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from .errors import FundError
from .money import add, divide, multiply, to_decimal, to_string
from .policy import is_sentinel

CEILING_NAMES = (
    "readiness_weight",
    "downside_capacity",
    "max_security_weight",
    "issuer_capacity",
    "cash_capacity",
)


class SizingError(FundError):
    """The policy cannot produce a ceiling from these inputs."""


@dataclass(frozen=True)
class Ceiling:
    """One policy limit expressed as a maximum total weight for the security."""

    name: str
    max_weight: Decimal | None
    note: str

    @property
    def applies(self) -> bool:
        return self.max_weight is not None

    def to_document(self, binding: str) -> dict[str, Any]:
        document: dict[str, Any] = {
            "name": self.name,
            "status": "binding" if self.name == binding
            else ("computed" if self.applies else "not_applicable"),
            "note": self.note,
        }
        if self.max_weight is not None:
            document["max_weight"] = to_string(self.max_weight)
        return document


@dataclass(frozen=True)
class Exposure:
    """The book as it stands, from the security's point of view."""

    nav: Decimal
    cash: Decimal
    current_weight: Decimal
    issuer_weight_excluding_security: Decimal = Decimal(0)
    open_positions: int = 0


@dataclass(frozen=True)
class SizingResult:
    base_weight: Decimal
    readiness_multiplier: Decimal | None
    ceilings: tuple[Ceiling, ...]
    policy_compliant_max_weight: Decimal
    binding_constraint: str

    def ceiling(self, name: str) -> Ceiling:
        for entry in self.ceilings:
            if entry.name == name:
                return entry
        raise KeyError(name)


def _fraction(bps: int) -> Decimal:
    return divide(Decimal(bps), Decimal(10000))


def readiness_multiplier(policy: Mapping[str, Any], readiness: str) -> Decimal | None:
    """None means this readiness tier is switched off, not that it is zero."""
    multipliers = policy["sizing"]["readiness_multipliers"]
    if readiness not in multipliers:
        raise SizingError(f"unknown readiness tier: {readiness!r}")
    raw = multipliers[readiness]
    if is_sentinel(raw):
        return None
    return to_decimal(raw)


def base_weight(policy: Mapping[str, Any]) -> Decimal:
    """Equal-weight slice of the capital that may actually be deployed."""
    deployable = add(Decimal(1), -_fraction(policy["cash"]["operational_floor_bps_nav"]))
    slots = policy["capacity"]["max_active_positions"]
    return divide(deployable, Decimal(slots))


def downside_capacity(policy: Mapping[str, Any], downside_return_fraction: Decimal | None) -> Decimal | None:
    """How much weight the loss budget affords, given this downside.

    A worse downside buys a smaller position. This is where the sizing rule
    actually lives -- not in how confident anyone feels.
    """
    if downside_return_fraction is None:
        return None
    magnitude = abs(downside_return_fraction)
    if magnitude == 0:
        raise SizingError("a downside of zero is not a downside")
    return divide(_fraction(policy["risk"]["position_loss_budget_bps_nav"]), magnitude)


def evaluate(
    policy: Mapping[str, Any],
    *,
    readiness: str,
    downside_status: str,
    downside_return_fraction: Decimal | None,
    exposure: Exposure,
) -> SizingResult:
    """Compute every ceiling, then the binding one."""
    if exposure.nav <= 0:
        raise SizingError("sizing needs a positive NAV")

    slice_weight = base_weight(policy)
    multiplier = readiness_multiplier(policy, readiness)

    ceilings: list[Ceiling] = []

    if multiplier is None:
        ceilings.append(Ceiling("readiness_weight", Decimal(0),
                                f"readiness tier {readiness!r} is disabled by policy"))
    else:
        ceilings.append(Ceiling(
            "readiness_weight", multiply(slice_weight, multiplier),
            f"{to_string(slice_weight)} base x {to_string(multiplier)} ({readiness})",
        ))

    if downside_status == "unknown":
        treatment = policy["sizing"]["unknown_downside_treatment"]
        if treatment == "ineligible_for_new_risk":
            ceilings.append(Ceiling(
                "downside_capacity", exposure.current_weight,
                "downside unknown: no new risk, the existing position is left alone",
            ))
        else:
            ceilings.append(Ceiling("downside_capacity", Decimal(0),
                                    "downside unknown: treated as a total loss"))
    else:
        capacity = downside_capacity(policy, downside_return_fraction)
        budget_bps = policy["risk"]["position_loss_budget_bps_nav"]
        ceilings.append(Ceiling(
            "downside_capacity", capacity,
            f"{budget_bps} bp budget / {to_string(abs(downside_return_fraction or Decimal(0)))} downside",
        ))

    security_cap = _fraction(policy["concentration"]["max_security_weight_bps"])
    ceilings.append(Ceiling("max_security_weight", security_cap, "hard single-name wall"))

    issuer_cap = _fraction(policy["concentration"]["max_issuer_weight_bps"])
    remaining_issuer = add(issuer_cap, -exposure.issuer_weight_excluding_security)
    if remaining_issuer < 0:
        remaining_issuer = Decimal(0)
    ceilings.append(Ceiling(
        "issuer_capacity", remaining_issuer,
        f"{to_string(issuer_cap)} issuer cap less "
        f"{to_string(exposure.issuer_weight_excluding_security)} held in other share classes",
    ))

    floor = multiply(exposure.nav, _fraction(policy["cash"]["operational_floor_bps_nav"]))
    spendable = add(exposure.cash, -floor)
    if spendable < 0:
        spendable = Decimal(0)
    cash_ceiling = add(exposure.current_weight, divide(spendable, exposure.nav))
    ceilings.append(Ceiling(
        "cash_capacity", cash_ceiling,
        f"current weight plus spendable cash above the {policy['cash']['operational_floor_bps_nav']} bp floor",
    ))

    applicable = [c for c in ceilings if c.applies]
    if not applicable:  # pragma: no cover -- every branch above yields a number
        raise SizingError("no ceiling could be computed")

    lowest = min(c.max_weight for c in applicable)  # type: ignore[type-var]
    binding = next(c.name for c in applicable if c.max_weight == lowest)

    return SizingResult(
        base_weight=slice_weight,
        readiness_multiplier=multiplier,
        ceilings=tuple(ceilings),
        policy_compliant_max_weight=lowest,
        binding_constraint=binding,
    )


# --------------------------------------------------------------------------
# The no-trade band
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class BandResult:
    half_width: Decimal
    drift: Decimal
    trade_candidate: bool


def no_trade_band(policy: Mapping[str, Any], *, current_weight: Decimal,
                  target_weight: Decimal) -> BandResult:
    """Whether drift alone justifies a trade.

    The monthly rhythm is a rhythm for deciding again, not for trading again.
    Without this, a 3-18 month thesis would be nibbled at twelve times a year
    by rounding noise.
    """
    band = policy["trading"]["no_trade_band"]
    absolute = _fraction(band["absolute_bps"])
    relative = multiply(_fraction(band["relative_bps"]), target_weight)
    half_width = max(absolute, relative)
    drift = abs(add(current_weight, -target_weight))
    return BandResult(half_width=half_width, drift=drift, trade_candidate=drift > half_width)


# --------------------------------------------------------------------------
# Hard limits
# --------------------------------------------------------------------------

def hard_breaches(
    policy: Mapping[str, Any],
    *,
    post_trade_weight: Decimal,
    post_trade_issuer_weight: Decimal,
    post_trade_cash: Decimal,
    open_positions_after: int,
) -> tuple[str, ...]:
    """Limits that a decision may not cross, whatever the sizing says."""
    breaches: list[str] = []
    if post_trade_weight > _fraction(policy["concentration"]["max_security_weight_bps"]):
        breaches.append("policy.max_security_weight_exceeded")
    if post_trade_issuer_weight > _fraction(policy["concentration"]["max_issuer_weight_bps"]):
        breaches.append("policy.max_issuer_weight_exceeded")
    if post_trade_cash < 0:
        breaches.append("policy.leverage_required")
    if open_positions_after > policy["capacity"]["max_active_positions"]:
        breaches.append("policy.max_active_positions_exceeded")
    return tuple(breaches)


def drawdown_response(policy: Mapping[str, Any], drawdown_fraction: Decimal) -> str | None:
    """The deepest rung the current drawdown has reached. Never a sell."""
    ladder = sorted(policy["risk"]["drawdown_response_ladder"], key=lambda r: r["drawdown_bps"])
    reached: str | None = None
    for rung in ladder:
        if abs(drawdown_fraction) >= _fraction(rung["drawdown_bps"]):
            reached = rung["response"]
    return reached


def quantity_for_weight(*, weight: Decimal, nav: Decimal, price: Decimal) -> Decimal:
    if price <= 0:
        raise SizingError("price must be positive")
    return divide(multiply(weight, nav), price)


def whole_shares(quantity: Decimal) -> Decimal:
    """Round down. Rounding up would step over the ceiling that was just computed."""
    return quantity.to_integral_value(rounding="ROUND_FLOOR")


def describe_ceilings(result: SizingResult, ceilings: Sequence[str] = CEILING_NAMES) -> list[str]:
    lines = []
    for name in ceilings:
        ceiling = result.ceiling(name)
        if ceiling.max_weight is None:
            lines.append(f"{name}: not applicable ({ceiling.note})")
        else:
            marker = "  <-- binding" if name == result.binding_constraint else ""
            lines.append(f"{name}: {ceiling.max_weight * 100:.2f}%{marker}")
    return lines
