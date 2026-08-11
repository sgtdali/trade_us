"""Recomputed coverage (docs/valuation-t71-05-*.md Section 10, docs/valuation-t68-04-*.md
Section 18). Never trusts a caller-supplied count -- everything here is
recomputed from the actual evaluation list every time.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..methods.evaluator import MethodEvaluation
from ..methods.families import FamilyCoverage, minimum_valid_family_satisfied
from ..methods.numeric import divide_exact, project_canonical_scalar, to_exact_rational


def compute_coverage(evaluations: Sequence[MethodEvaluation], family_coverage: Sequence[FamilyCoverage]) -> dict[str, Any]:
    configured_count = len(evaluations)
    applicable = [e for e in evaluations if e.status != "not_applicable"]
    available = [e for e in applicable if e.status == "available"]
    unavailable = [e for e in applicable if e.status == "unavailable"]
    not_applicable = [e for e in evaluations if e.status == "not_applicable"]

    if applicable:
        ratio = project_canonical_scalar(divide_exact(to_exact_rational(str(len(available))), to_exact_rational(str(len(applicable)))))
    else:
        ratio = "0"

    return {
        "configured_method_count": configured_count,
        "applicable_method_count": len(applicable),
        "available_method_count": len(available),
        "unavailable_method_count": len(unavailable),
        "not_applicable_method_count": len(not_applicable),
        "coverage_ratio": ratio,
        "primary_family_available": minimum_valid_family_satisfied(family_coverage),
        "current_use_method_count": sum(1 for e in evaluations if e.current_use_eligible),
        "method_status_refs": [e.formula_id for e in available],
        "family_coverage": [
            {
                "economic_family_id": fc.economic_family_id,
                "applicable_count": fc.applicable_count,
                "available_count": fc.available_count,
                "current_use_eligible": fc.current_use_eligible,
            }
            for fc in family_coverage
        ],
    }
