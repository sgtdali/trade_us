"""The dispatch table.

There is no capability router here, and that is a decision rather than an
omission. A dispatch rule grants the authority to spend money, call a model and
create work. Opening that to arbitrary configuration means building a small
rule language and a small permission system without noticing -- and then
maintaining both.

So the table is closed, typed, and lives in code. What the owner may change is
narrow and named: whether a rule is enabled, its price threshold, its cooldown,
and its calendar window. Adding a rule is a code change with a version bump,
which is the point: it should be visible in the history that the system was
given a new reason to act on its own.

Each job copies the rule_id and rule_version it matched, so a later edit to
this table cannot rewrite why work was done last March.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .errors import FundError


class DispatchError(FundError):
    """No rule matched, or a rule was misconfigured."""


@dataclass(frozen=True)
class DispatchRule:
    rule_id: str
    version: int
    observation: str
    recipe: str
    assessment_mode: str
    requires_open_thesis: bool
    description: str
    #: What the owner may tune, and nothing else.
    enabled: bool = True
    cooldown_days: int = 0

    def matches(self, observation: str, *, has_open_thesis: bool) -> bool:
        if not self.enabled or observation != self.observation:
            return False
        return has_open_thesis if self.requires_open_thesis else True


#: Each rule was added and verified on its own. A table that fires five ways on
#: the first night is a table nobody can debug.
_BASE_RULES: tuple[DispatchRule, ...] = (
    DispatchRule(
        rule_id="new_filing_open_thesis",
        version=1,
        observation="new_periodic_filing",
        recipe="deep_dive_then_tracker",
        assessment_mode="update_against_prior",
        requires_open_thesis=True,
        description="A new 10-Q or 10-K on a company we have a thesis about is read, "
                    "and the reading is judged against what we previously believed.",
    ),
    DispatchRule(
        rule_id="earnings_evidence_open_thesis",
        version=1,
        observation="earnings_evidence",
        recipe="deep_dive_then_tracker",
        assessment_mode="update_against_prior",
        requires_open_thesis=True,
        description="An Item 2.02 results filing has actually landed. The trigger is the "
                    "filing, never the expected date: a date is an estimate, and research "
                    "fired at an estimate is research against numbers that do not exist yet.",
    ),
    DispatchRule(
        rule_id="review_due_open_thesis",
        version=1,
        observation="review_due",
        recipe="tracker",
        assessment_mode="update_against_prior",
        requires_open_thesis=True,
        description="A qualitative check has come due. It runs whether or not new evidence "
                    "arrived -- a review that only happens when someone remembers it is "
                    "not a review.",
    ),
    DispatchRule(
        rule_id="price_shock_open_thesis",
        version=1,
        observation="price_shock",
        recipe="blind_review",
        assessment_mode="independent_then_reconcile",
        requires_open_thesis=True,
        description="The market has moved sharply against, or with, the thesis. The first "
                    "pass is deliberately blind -- neither the previous judgement nor the "
                    "position is shown -- because a large move is precisely when a prior "
                    "view is hardest to re-examine honestly.",
    ),
    DispatchRule(
        rule_id="periodic_discovery",
        version=1,
        observation="periodic_discovery",
        recipe="idea_generation",
        assessment_mode="de_novo",
        requires_open_thesis=False,
        description="A low-frequency screen for names we have no view on. Off by default: "
                    "monitoring the book you already own has to be reliable first, or "
                    "discovery becomes a way of not looking at what is already there.",
        enabled=False,
    ),
    DispatchRule(
        rule_id="mechanical_breach_open_thesis",
        version=1,
        observation="mechanical_breach",
        recipe="tracker",
        assessment_mode="update_against_prior",
        requires_open_thesis=True,
        description="A monitoring rule was crossed. The reading has to address the breach; "
                    "whether the thesis is broken remains the owner's judgement.",
    ),
)


TUNING_RELATIVE_PATH = "config/fund/dispatch-tuning.json"

#: What the owner may change without touching code. Deliberately four knobs:
#: anything more expressive becomes a rule language, and a rule language needs
#: a permission model nobody asked for.
TUNABLE_FIELDS = ("enabled", "cooldown_days", "price_shock_bps",
                  "price_shock_window_days", "discovery_interval_days",
                  "max_open_candidates", "discovery_universe")

DEFAULT_TUNING: dict[str, Any] = {
    "price_shock_bps": 2000,
    "price_shock_window_days": 30,
    "discovery_interval_days": 30,
    "max_open_candidates": 3,
    "discovery_universe": "sp500",
}


def load_tuning(root: Any = None) -> dict[str, Any]:
    """Owner settings, if any. Absent means defaults, not an error."""
    import json
    from pathlib import Path

    from . import schemas

    path = Path(root or schemas.repo_root()) / TUNING_RELATIVE_PATH
    settings = dict(DEFAULT_TUNING)
    if not path.is_file():
        return settings
    raw = json.loads(path.read_text(encoding="utf-8"))
    unknown = set(raw) - set(TUNABLE_FIELDS) - {"rules"}
    if unknown:
        raise DispatchError(
            f"{path} sets fields that are not tunable: {', '.join(sorted(unknown))}. "
            f"Only {', '.join(TUNABLE_FIELDS)} may be changed without a code change."
        )
    settings.update({k: v for k, v in raw.items() if k != "rules"})
    settings["rules"] = raw.get("rules", {})
    return settings


def apply_tuning(rules: tuple[DispatchRule, ...], settings: Mapping[str, Any]
                 ) -> tuple[DispatchRule, ...]:
    from dataclasses import replace

    per_rule = settings.get("rules", {}) or {}
    tuned = []
    for rule in rules:
        overrides = per_rule.get(rule.rule_id, {})
        unknown = set(overrides) - {"enabled", "cooldown_days"}
        if unknown:
            raise DispatchError(
                f"{rule.rule_id}: {', '.join(sorted(unknown))} is not tunable"
            )
        tuned.append(replace(rule, **overrides))
    return tuple(tuned)


RULES: tuple[DispatchRule, ...] = _BASE_RULES


def rules_by_id() -> dict[str, DispatchRule]:
    return {rule.rule_id: rule for rule in RULES}


def match(observation: str, *, has_open_thesis: bool) -> DispatchRule | None:
    """The rule for this observation, if the table has one.

    Returns None rather than raising: an observation with no rule is normal
    (a filing on a company we do not follow), not an error.
    """
    for rule in RULES:
        if rule.matches(observation, has_open_thesis=has_open_thesis):
            return rule
    return None


def require(observation: str, *, has_open_thesis: bool) -> DispatchRule:
    rule = match(observation, has_open_thesis=has_open_thesis)
    if rule is None:
        raise DispatchError(
            f"no dispatch rule for {observation!r}"
            + ("" if has_open_thesis else " without an open thesis")
        )
    return rule


def health(
    rules: Sequence[DispatchRule] = RULES,
    *,
    jobs: Sequence[Mapping[str, Any]] = (),
    as_of: str,
    window_days: int = 30,
) -> list[dict[str, Any]]:
    """Per-rule activity, so a rule that quietly stopped firing is visible.

    A dispatch table is a thing that fails silently by construction: nothing
    happening looks exactly like nothing needing to happen.
    """
    from datetime import date, timedelta

    cutoff = (date.fromisoformat(as_of) - timedelta(days=window_days)).isoformat()
    report = []
    for rule in rules:
        matched = [job for job in jobs if job.get("rule_id") == rule.rule_id]
        recent = [job for job in matched if job["created_at"][:10] >= cutoff]
        failures = [job for job in recent if job["status"] in {"failed", "contract_failed"}]
        report.append({
            "rule_id": rule.rule_id,
            "version": rule.version,
            "enabled": rule.enabled,
            "last_dispatched": max((job["created_at"] for job in matched), default=None),
            f"jobs_{window_days}d": len(recent),
            f"failures_{window_days}d": len(failures),
            "never_fired": not matched,
        })
    return report
