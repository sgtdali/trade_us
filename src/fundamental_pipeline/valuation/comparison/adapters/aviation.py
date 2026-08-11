"""Aviation sector lease/fleet operating-capital adapter for the Magic
Formula ROC axis (T74-B; docs/valuation-t74-05-piotroski-magic-diagnostic-specification.md
Section 12). Only decides whether ROC's capital basis is currently
resolvable for an aviation-sector subject -- it never touches EY, and it
never assigns a company-quality judgment. Missing/incompatible basis
means "adapter required, ROC unavailable", not "adverse company".
"""

from __future__ import annotations

#: The one lease/fleet basis ROC's ``tangible_operating_capital`` accepts
#: for an aviation subject: capitalized-lease (IFRS 16) fleet with the
#: fleet/ROU operating-capital adapter actually applied, so EV, EBIT, and
#: operating-capital all share the same lease basis (T74.5 Section 12).
REQUIRED_LEASE_BASIS = "ifrs16_capitalized_with_fleet_adapter"


def lease_basis_compatible(*, declared_lease_basis: str | None, fleet_adapter_available: bool) -> bool:
    """``True`` only when both the declared lease basis matches the one
    ROC-compatible aviation convention AND a real fleet/ROU
    operating-capital adapter is actually available for this subject.
    Either condition failing makes ROC unavailable while EY may remain
    independently eligible."""
    return fleet_adapter_available and declared_lease_basis == REQUIRED_LEASE_BASIS
