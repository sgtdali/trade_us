"""Industrial-cycle (steel) sector IAS29/revaluation asset-base adapter
for the Magic Formula ROC axis (T74-B; docs/valuation-t74-05-piotroski-magic-diagnostic-specification.md
Section 12). Only decides whether ROC's asset base is currently
comparable for an industrial-cycle subject under hyperinflation/
revaluation accounting -- it never touches EY, and an unresolved gate
excludes/caps ROC, never automatically excludes EY (T68-07 Section 19).
"""

from __future__ import annotations


def lease_basis_compatible(*, ias29_revaluation_resolved: bool) -> bool:
    """``True`` only when the subject's IAS 29 hyperinflation/revaluation
    asset-base treatment has been explicitly resolved into a
    ROC-comparable basis. An unresolved gate makes ROC unavailable while
    EY may remain independently eligible."""
    return ias29_revaluation_resolved
