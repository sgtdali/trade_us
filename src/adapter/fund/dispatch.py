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


#: F6 ships exactly one rule. The others are named in the design and arrive in
#: F8, each one verified on its own -- a table that fires five ways on the first
#: night is a table nobody can debug.
RULES: tuple[DispatchRule, ...] = (
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
)


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
