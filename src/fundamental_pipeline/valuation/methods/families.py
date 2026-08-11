"""Economic family dependence, coverage, and minimum-valid-family
sufficiency (docs/valuation-t71-03-*.md Sections 13-14,
docs/valuation-t67-08-*.md Section 11).

Inverse/sibling methods (P/E <-> earnings yield; EV/EBIT <-> EBIT/EV)
already share one ``economic_family_id`` at the catalog level (T71-A); this
module only aggregates already-evaluated results by that shared ID -- it
never re-derives family membership from a method name or ticker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .evaluator import MethodEvaluation

_VOTING_ROLES = frozenset({"primary", "secondary"})


@dataclass(frozen=True)
class FamilyCoverage:
    economic_family_id: str
    applicable_count: int
    available_count: int
    current_use_eligible: bool


def compute_family_coverage(evaluations: Sequence[MethodEvaluation]) -> tuple[FamilyCoverage, ...]:
    """One :class:`FamilyCoverage` per distinct ``economic_family_id``
    present among ``evaluations``, in lexicographic family-ID order
    (canonical, independent of evaluation list order). ``not_applicable``
    rows are excluded from ``applicable_count`` (docs/valuation-t71-05-*.md
    Section 9: N/A rows never enter the applicability denominator).
    ``current_use_eligible`` requires at least one **primary or secondary**
    role member to be available and current-use eligible -- a
    diagnostic-only family never satisfies this by itself."""
    by_family: dict[str, list[MethodEvaluation]] = {}
    for evaluation in evaluations:
        by_family.setdefault(evaluation.economic_family_id, []).append(evaluation)

    result: list[FamilyCoverage] = []
    for family_id in sorted(by_family):
        members = by_family[family_id]
        applicable = [m for m in members if m.status != "not_applicable"]
        available = [m for m in applicable if m.status == "available"]
        current_use_eligible = any(
            m.status == "available" and m.role in _VOTING_ROLES and m.current_use_eligible
            for m in members
        )
        result.append(FamilyCoverage(
            economic_family_id=family_id,
            applicable_count=len(applicable),
            available_count=len(available),
            current_use_eligible=current_use_eligible,
        ))
    return tuple(result)


def minimum_valid_family_satisfied(family_coverage: Sequence[FamilyCoverage]) -> bool:
    """At least one applicable primary/secondary economic family is
    available and current-use eligible (docs/valuation-t67-08-*.md
    Section 11). Same-family inverse siblings never raise this above one;
    a diagnostic-only bundle never satisfies it."""
    return any(fc.current_use_eligible for fc in family_coverage)
