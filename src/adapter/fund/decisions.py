"""Trade previews and the decisions they freeze.

This is the second of the two stages. The first -- ``fund assess`` -- forms the
research judgement with the capital consequence hidden. Here that judgement is
already frozen, and everything the policy has to say about it becomes visible
at once: every ceiling, which one binds, what the position would cost the fund
if the downside happened, and whether the drift even justifies trading.

The split is the mechanism, not a formality. Asked "will you accept a 30% fall"
while looking at a screen that says the answer means selling, people find
reasons the fall is really 20%.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from . import ids, sizing
from .errors import FundError
from .money import Money, add, divide, format_display, multiply, to_decimal, to_string
from .projection import PortfolioState, Valuation

DECIDE_CHOICES = ("accept", "reduce", "cancel", "outside-policy")


class DecisionError(FundError):
    """A preview or decision could not be formed from these inputs."""


@dataclass(frozen=True)
class Preview:
    security_id: str
    action: str
    quantity: Decimal
    price: Money
    consideration: Money

    nav: Money
    cash_before: Money
    cash_after: Money
    current_weight: Decimal
    post_trade_weight: Decimal
    open_positions_before: int
    open_positions_after: int

    assessment: Mapping[str, Any]
    result: sizing.SizingResult
    band: sizing.BandResult
    breaches: tuple[str, ...]
    downside_cost_bps_nav: Decimal | None
    policy_compliant_quantity: Decimal

    @property
    def within_policy(self) -> bool:
        return self.post_trade_weight <= self.result.policy_compliant_max_weight and not self.breaches


def _weight(valuation: Valuation, security_id: str) -> Decimal:
    return valuation.weight_of(security_id) or Decimal(0)


def issuer_weight_excluding(
    valuation: Valuation, master: Mapping[str, Any], security_id: str
) -> Decimal:
    """Exposure to the same issuer through its other share classes."""
    from . import instruments

    try:
        issuer = instruments.issuer_of(dict(master), security_id)
    except Exception:  # noqa: BLE001 -- an unregistered security has no siblings
        return Decimal(0)

    total = Decimal(0)
    for position in valuation.positions:
        if position.security_id == security_id or position.weight is None:
            continue
        try:
            if instruments.issuer_of(dict(master), position.security_id) == issuer:
                total = add(total, position.weight)
        except Exception:  # noqa: BLE001
            continue
    return total


def build_preview(
    policy: Mapping[str, Any],
    state: PortfolioState,
    valuation: Valuation,
    assessment: Mapping[str, Any],
    master: Mapping[str, Any],
    *,
    action: str,
    quantity: Decimal,
    price: Money,
) -> Preview:
    if action not in {"buy", "sell"}:
        raise DecisionError(f"a preview needs buy or sell, got {action!r}")
    if valuation.nav is None:
        raise DecisionError(
            "NAV is unavailable, so no weight can be computed. "
            "Supply the missing prices before previewing a trade."
        )

    security_id = assessment["security_id"]
    nav = valuation.nav
    cash_before = valuation.cash
    current_weight = _weight(valuation, security_id)
    held = state.positions.get(security_id)
    held_quantity = held.quantity if held else Decimal(0)

    consideration = price.scaled_by(quantity)
    if action == "sell":
        if quantity > held_quantity:
            raise DecisionError(
                f"selling {to_string(quantity)} but only {to_string(held_quantity)} are held"
            )
        cash_after = cash_before + consideration
        post_value = add(multiply(current_weight, nav.amount), -consideration.amount)
    else:
        cash_after = cash_before - consideration
        post_value = add(multiply(current_weight, nav.amount), consideration.amount)

    post_trade_weight = divide(post_value, nav.amount)
    if post_trade_weight < 0:
        post_trade_weight = Decimal(0)

    open_before = len(valuation.positions)
    open_after = open_before
    if action == "buy" and held_quantity == 0:
        open_after += 1
    if action == "sell" and quantity == held_quantity:
        open_after -= 1

    downside = assessment["downside"]
    downside_fraction = (
        to_decimal(downside["return_fraction"]) if downside["status"] == "known" else None
    )

    exposure = sizing.Exposure(
        nav=nav.amount,
        cash=cash_before.amount,
        current_weight=current_weight,
        issuer_weight_excluding_security=issuer_weight_excluding(valuation, master, security_id),
        open_positions=open_before,
    )
    result = sizing.evaluate(
        policy,
        readiness=assessment["readiness"],
        downside_status=downside["status"],
        downside_return_fraction=downside_fraction,
        exposure=exposure,
    )

    band = sizing.no_trade_band(
        policy,
        current_weight=current_weight,
        target_weight=min(result.policy_compliant_max_weight, post_trade_weight),
    )

    post_issuer_weight = add(exposure.issuer_weight_excluding_security, post_trade_weight)
    breaches = sizing.hard_breaches(
        policy,
        post_trade_weight=post_trade_weight,
        post_trade_issuer_weight=post_issuer_weight,
        post_trade_cash=cash_after.amount,
        open_positions_after=open_after,
    )

    downside_cost = (
        multiply(multiply(post_trade_weight, abs(downside_fraction)), Decimal(10000))
        if downside_fraction is not None
        else None
    )

    headroom = add(result.policy_compliant_max_weight, -current_weight)
    if headroom < 0:
        headroom = Decimal(0)
    allowed_quantity = sizing.whole_shares(
        sizing.quantity_for_weight(weight=headroom, nav=nav.amount, price=price.amount)
    )

    return Preview(
        security_id=security_id,
        action=action,
        quantity=quantity,
        price=price,
        consideration=consideration,
        nav=nav,
        cash_before=cash_before,
        cash_after=cash_after,
        current_weight=current_weight,
        post_trade_weight=post_trade_weight,
        open_positions_before=open_before,
        open_positions_after=open_after,
        assessment=assessment,
        result=result,
        band=band,
        breaches=breaches,
        downside_cost_bps_nav=downside_cost,
        policy_compliant_quantity=allowed_quantity,
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render(preview: Preview, ticker: str) -> str:
    assessment = preview.assessment
    downside = assessment["downside"]
    lines: list[str] = []

    lines.append(f"{ticker} -- {preview.action.upper()} PREVIEW")
    lines.append("")
    lines.append(f"{'Contemplated':<22}{to_string(preview.quantity)} x "
                 f"{format_display(preview.price.amount)} = {format_display(preview.consideration.amount)}")
    lines.append(f"{'NAV':<22}{format_display(preview.nav.amount)}")
    lines.append(f"{'Cash':<22}{format_display(preview.cash_before.amount)} -> "
                 f"{format_display(preview.cash_after.amount)}")
    lines.append(f"{'Weight':<22}{preview.current_weight * 100:.2f}% -> "
                 f"{preview.post_trade_weight * 100:.2f}%")
    lines.append(f"{'Open positions':<22}{preview.open_positions_before} -> {preview.open_positions_after}")
    lines.append("")

    lines.append("FROZEN RESEARCH")
    lines.append(f"{'Assessment':<22}{assessment['assessment_id']}")
    lines.append(f"{'Readiness':<22}{assessment['readiness']}")
    if downside["status"] == "known":
        lines.append(f"{'Downside':<22}{to_decimal(downside['return_fraction']) * 100:.2f}%")
    else:
        lines.append(f"{'Downside':<22}unknown -- {downside['reason']}")
    lines.append(f"{'Evidence date':<22}{assessment['evidence_date']}")
    lines.append(f"{'Review due':<22}{assessment['review_due']}")
    if not assessment["acceptance"]["would_accept_downside_without_position"]:
        lines.append("  ! the owner answered NO to accepting this downside from scratch")
    lines.append("")

    lines.append("POLICY CHECK")
    for name in sizing.CEILING_NAMES:
        ceiling = preview.result.ceiling(name)
        label = name.replace("_", " ")
        if ceiling.max_weight is None:
            lines.append(f"{label:<22}n/a")
        else:
            marker = "   <-- binding" if name == preview.result.binding_constraint else ""
            lines.append(f"{label:<22}{ceiling.max_weight * 100:.2f}%{marker}")
    lines.append(f"{'Policy ceiling':<22}{preview.result.policy_compliant_max_weight * 100:.2f}%")
    if preview.downside_cost_bps_nav is not None:
        lines.append(f"{'Downside cost':<22}{preview.downside_cost_bps_nav:.0f} bp of NAV")
    lines.append("")

    if preview.band.trade_candidate:
        lines.append(f"NO-TRADE BAND        drift {preview.band.drift * 100:.2f}% exceeds "
                     f"{preview.band.half_width * 100:.2f}% -- trading is justified")
    else:
        lines.append(f"NO-TRADE BAND        drift {preview.band.drift * 100:.2f}% is inside "
                     f"{preview.band.half_width * 100:.2f}% -- drift alone is not a reason to trade")
    lines.append("")

    if preview.within_policy:
        lines.append("RESULT               WITHIN POLICY")
    else:
        lines.append("RESULT               OUTSIDE POLICY")
        lines.append(f"{'Policy-compliant':<22}~{to_string(preview.policy_compliant_quantity)} shares"
                     f" / {format_display(multiply(preview.policy_compliant_quantity, preview.price.amount))}")
        for breach in preview.breaches:
            lines.append(f"  ! {breach}")
        lines.append("")
        lines.append("  --decide reduce           take the policy-compliant size")
        lines.append("  --decide cancel           record that this was considered and dropped")
        lines.append("  --decide outside-policy   overrule, with a reason code and a rationale")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# Freezing the decision
# --------------------------------------------------------------------------

def build_decision(
    preview: Preview,
    policy: Mapping[str, Any],
    *,
    as_of: str,
    recorded_at: str,
    decide: str,
    rationale: str,
    reason_code: str | None = None,
    mode: str = "shadow",
    next_review: str | None = None,
) -> dict[str, Any]:
    if decide not in DECIDE_CHOICES:
        raise DecisionError(f"unknown decision: {decide!r}")
    if decide == "outside-policy" and not reason_code:
        raise DecisionError("recording a decision outside policy requires --reason-code")
    if decide == "accept" and not preview.within_policy:
        raise DecisionError(
            "this trade is outside policy. Use --decide reduce to take the compliant size, "
            "--decide cancel, or --decide outside-policy with a reason code."
        )

    final_quantity = preview.quantity
    if decide == "reduce":
        final_quantity = preview.policy_compliant_quantity
        if final_quantity <= 0:
            raise DecisionError(
                "the policy-compliant size is zero shares; there is nothing to reduce to"
            )
    elif decide == "cancel":
        final_quantity = Decimal(0)

    outcome_decision = {
        "accept": "executed_as_previewed",
        "reduce": "reduced_to_policy_limit",
        "cancel": "cancelled",
        "outside-policy": "recorded_outside_policy",
    }[decide]

    ceilings = [c.to_document(preview.result.binding_constraint) for c in preview.result.ceilings]

    document: dict[str, Any] = {
        "decision_id": ids.new_id(ids.DECISION),
        "as_of": as_of,
        "recorded_at": recorded_at,
        "policy_version": policy["identity"]["policy_version"],
        "assessment_id": preview.assessment["assessment_id"],
        "security_id": preview.security_id,
        "action": preview.action,
        "contemplated": {
            "quantity": to_string(preview.quantity),
            "price": preview.price.to_document(),
            "consideration": preview.consideration.to_document(),
        },
        "pre_trade": {
            "nav": preview.nav.to_document(),
            "cash": preview.cash_before.to_document(),
            "position_quantity": to_string(
                divide(multiply(preview.current_weight, preview.nav.amount), preview.price.amount)
                if preview.current_weight else Decimal(0)
            ),
            "current_weight": to_string(preview.current_weight),
            "open_positions": preview.open_positions_before,
        },
        "frozen_research": {
            "readiness": preview.assessment["readiness"],
            "downside_status": preview.assessment["downside"]["status"],
            "evidence_date": preview.assessment["evidence_date"],
            "review_due": preview.assessment["review_due"],
        },
        "policy_evaluation": {
            "ceilings": ceilings,
            "policy_compliant_max_weight": to_string(preview.result.policy_compliant_max_weight),
            "binding_constraint": preview.result.binding_constraint,
            "post_trade_weight": to_string(preview.post_trade_weight),
            "within_policy": preview.within_policy,
            "policy_compliant_quantity": to_string(preview.policy_compliant_quantity),
            "no_trade_band": {
                "half_width": to_string(preview.band.half_width),
                "drift": to_string(preview.band.drift),
                "trade_candidate": preview.band.trade_candidate,
            },
        },
        "outcome": {
            "decision": outcome_decision,
            "final_quantity": to_string(final_quantity),
            "rationale": rationale,
        },
        "mode": mode,
    }

    if preview.assessment["downside"]["status"] == "known":
        document["frozen_research"]["downside_return_fraction"] = \
            preview.assessment["downside"]["return_fraction"]
    if preview.downside_cost_bps_nav is not None:
        document["policy_evaluation"]["downside_cost_bps_nav"] = \
            to_string(preview.downside_cost_bps_nav)
    if preview.breaches:
        document["policy_evaluation"]["hard_breaches"] = list(preview.breaches)
    if reason_code:
        document["outcome"]["reason_code"] = reason_code
    if next_review:
        document["outcome"]["next_review"] = next_review

    return document


def build_no_change(
    policy: Mapping[str, Any],
    *,
    security_id: str,
    as_of: str,
    recorded_at: str,
    rationale: str,
    reason_code: str,
    valuation: Valuation,
    pending_review: bool = False,
    assessment_id: str | None = None,
    mode: str = "shadow",
) -> dict[str, Any]:
    """A review that changes nothing is a decision and gets a record.

    Without it, 'I looked and held' and 'I never looked' leave the same trace.
    """
    if valuation.nav is None:
        raise DecisionError("recording no_change needs a NAV")

    current_weight = _weight(valuation, security_id)
    document: dict[str, Any] = {
        "decision_id": ids.new_id(ids.DECISION),
        "as_of": as_of,
        "recorded_at": recorded_at,
        "policy_version": policy["identity"]["policy_version"],
        "security_id": security_id,
        "action": "no_change",
        "pre_trade": {
            "nav": valuation.nav.to_document(),
            "cash": valuation.cash.to_document(),
            "position_quantity": "0",
            "current_weight": to_string(current_weight),
            "open_positions": len(valuation.positions),
        },
        "frozen_research": {
            "readiness": "watchlist",
            "downside_status": "unknown",
            "evidence_date": as_of,
        },
        "policy_evaluation": {
            "ceilings": [{"name": "max_security_weight", "status": "computed",
                          "max_weight": to_string(
                              divide(Decimal(policy["concentration"]["max_security_weight_bps"]),
                                     Decimal(10000)))}],
            "policy_compliant_max_weight": to_string(
                divide(Decimal(policy["concentration"]["max_security_weight_bps"]), Decimal(10000))),
            "binding_constraint": "none",
            "post_trade_weight": to_string(current_weight),
            "within_policy": True,
        },
        "outcome": {
            "decision": "no_change_with_pending_review" if pending_review else "no_change",
            "rationale": rationale,
            "reason_code": reason_code,
        },
        "mode": mode,
    }
    if assessment_id:
        document["assessment_id"] = assessment_id
        document["frozen_research"]["readiness"] = "watchlist"
    return document
