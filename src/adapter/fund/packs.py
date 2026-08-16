"""Building what the analyst sees.

Two rules govern this module, and both are enforced by tests rather than by
care.

**No capital reaches a skill.** Not the weight, not the cash, not the P&L, not
the average cost, not the amount at risk. Telling a model "82 basis points are
riding on this" does not improve the analysis; it gives the model a reason to
defend the position. Where seriousness genuinely needs communicating, it is
communicated as a date -- ``decision_deadline`` -- which changes how much care
is warranted without hinting at which answer is convenient.

**Qualitative questions are put in front of it explicitly.** A deep dive will
not spontaneously check whether customer concentration moved just because the
contract says someone should. If the contract has a question due, the question
goes in the pack, in words.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .errors import FundError

#: Anything resembling these must never appear in a pack. Checked structurally
#: by walk_for_capital_leaks, which is cheap insurance against a future field
#: being added to a snapshot that gets embedded here by accident.
FORBIDDEN_KEYS = frozenset({
    "weight", "current_weight", "post_trade_weight", "nav", "cash", "cash_amount",
    "market_value", "unrealized_pnl", "realized_pnl", "cost_basis", "unit_cost",
    "average_cost", "quantity", "position_quantity", "downside_cost_bps_nav",
    "policy_compliant_max_weight", "capital_at_risk", "consideration", "price",
})


class PackError(FundError):
    """A pack could not be built, or would have leaked something."""


def walk_for_capital_leaks(node: Any, path: str = "") -> list[str]:
    """Every forbidden key found anywhere in the structure."""
    leaks: list[str] = []
    if isinstance(node, Mapping):
        for key, value in node.items():
            here = f"{path}/{key}"
            if key in FORBIDDEN_KEYS:
                leaks.append(here)
            leaks.extend(walk_for_capital_leaks(value, here))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            leaks.extend(walk_for_capital_leaks(value, f"{path}/{index}"))
    return leaks


def build_pack(
    *,
    job: Mapping[str, Any],
    ticker: str,
    thesis: Mapping[str, Any] | None,
    prior_assessment: Mapping[str, Any] | None,
    check_outcomes: Sequence[Mapping[str, Any]] = (),
    due_questions: Sequence[Mapping[str, Any]] = (),
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the pack for one research job.

    What goes in is decided by the assessment mode. de_novo shows no prior
    judgement at all; independent_then_reconcile withholds it for the first
    pass and reconciles afterwards; update_against_prior requires it, because
    the question there is specifically what changed.
    """
    mode = job["assessment_mode"]

    pack: dict[str, Any] = {
        "pack_version": 1,
        "job_id": job["job_id"],
        "ticker": ticker,
        "security_id": job["security_id"],
        "assessment_mode": mode,
        "recipe": job["recipe"],
        "trigger": {
            "observation": job["trigger_snapshot"]["observation"],
            "detail": job["trigger_snapshot"].get("detail", ""),
        },
        "instructions": _instructions(mode, job["recipe"]),
    }

    if job.get("decision_deadline"):
        pack["decision_deadline"] = job["decision_deadline"]

    if evidence:
        pack["evidence"] = dict(evidence)

    if thesis is not None:
        pack["thesis"] = {
            "thesis_id": thesis["thesis_id"],
            "opened_at": thesis["opened_at"],
            "status": thesis["status"],
            "statement": thesis["thesis_statement"],
        }
        contract = thesis.get("monitoring_contract")
        if contract:
            pack["monitoring_contract"] = {
                "version": contract["version"],
                "mechanical_rules": [
                    {k: rule[k] for k in ("rule_id", "metric_id", "period_basis",
                                          "test_type", "operator", "threshold")}
                    for rule in contract["mechanical_rules"]
                ],
            }

    if check_outcomes:
        pack["mechanical_check_results"] = [
            {
                "rule_id": outcome["rule_id"],
                "result": outcome["result"],
                "observed_value": outcome.get("observed_value"),
                "threshold": outcome.get("threshold"),
                "unavailable_reason": outcome.get("unavailable_reason"),
            }
            for outcome in check_outcomes
        ]
        pack["mechanical_check_note"] = (
            "not_breached means one rule held. It does not mean the thesis is healthy. "
            "unavailable means the check could not be made -- treat it as unknown, "
            "never as unchanged."
        )

    # The questions the contract says are due, written out. Nothing here relies
    # on the skill deciding to look.
    if due_questions:
        pack["questions_you_must_answer"] = [
            {"check_id": check["check_id"], "question": check["question"],
             "last_reviewed_at": check.get("last_reviewed_at")}
            for check in due_questions
        ]

    if mode == "update_against_prior":
        if prior_assessment is None:
            raise PackError(
                "update_against_prior needs the previous judgement: the whole point "
                "of the mode is measuring what changed"
            )
        pack["previous_judgement"] = _prior_view(prior_assessment)
    elif mode == "independent_then_reconcile":
        pack["previous_judgement_withheld"] = (
            "Form your own view first. The previous judgement is deliberately not "
            "shown on this pass and will be reconciled afterwards."
        )
    # de_novo: nothing about a prior view, by construction.

    leaks = walk_for_capital_leaks(pack)
    if leaks:
        raise PackError(
            "this pack would have shown the analyst capital information: "
            + ", ".join(leaks)
        )
    return pack


def _prior_view(assessment: Mapping[str, Any]) -> dict[str, Any]:
    downside = assessment["downside"]
    view: dict[str, Any] = {
        "assessment_id": assessment["assessment_id"],
        "as_of": assessment["as_of"],
        "readiness": assessment["readiness"],
        "thesis_summary": assessment["thesis_summary"],
        "evidence_date": assessment["evidence_date"],
        "downside_status": downside["status"],
    }
    if downside["status"] == "known":
        view["downside_return_fraction"] = downside["return_fraction"]
        view["downside_scenario"] = downside["scenario"]
    else:
        view["downside_unknown_reason"] = downside["reason"]
    return view


_MODE_INSTRUCTIONS = {
    "de_novo": "Underwrite this name from scratch. There is no prior judgement to defer to.",
    "update_against_prior": "State what has changed since the previous judgement and why. "
                            "If nothing material changed, say so plainly -- 'no change' is a "
                            "real finding, not a failure to find something.",
    "independent_then_reconcile": "Form your view without reference to any prior judgement. "
                                  "You will be asked to reconcile the difference separately.",
}

_RECIPE_INSTRUCTIONS = {
    "deep_dive_then_tracker": "Read the new filing closely, then update the thesis tracker.",
    "tracker": "Update the thesis tracker against the evidence provided.",
    "blind_review": "Review this name as though seeing it for the first time.",
    "onboarding_underwrite": "Produce an initial underwriting view.",
    "idea_generation": "Screen for research candidates. Do not produce capital judgements.",
}


def _instructions(mode: str, recipe: str) -> list[str]:
    return [
        _RECIPE_INSTRUCTIONS.get(recipe, recipe),
        _MODE_INSTRUCTIONS.get(mode, mode),
        "Position size, cash, P&L and capital at risk are deliberately not in this pack. "
        "Do not speculate about them; they are not inputs to the judgement you are making.",
        "State the downside as a scenario with a number, or say plainly that it cannot be "
        "stated and why. An unstated downside is not a smaller one.",
    ]
