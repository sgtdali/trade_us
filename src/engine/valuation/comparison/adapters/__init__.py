"""T74-B Magic Formula ROC sector adapters (docs/valuation-t74-05-piotroski-magic-diagnostic-specification.md
Section 12).

Each adapter answers exactly one question -- "is ROC's operating-capital
basis currently resolvable for this sector_module?" -- and never touches
EY or assigns a company-quality judgment. Adapters never branch on
``ticker`` (only on the caller-supplied ``sector_module`` string, the
same company-selector catalog value T71/T72/T73 already use for
method/adapter routing).
"""

from __future__ import annotations

from . import aviation, industrial_cycle

_ADAPTERS = {"aviation": aviation, "industrial_cycle": industrial_cycle}


def resolve_adapter(sector_module: str | None):
    """Return the adapter module for ``sector_module``, or ``None`` if no
    sector adapter applies (a standard-corporate subject -- not an
    error; standard subjects need no lease/revaluation gate at all)."""
    if sector_module is None:
        return None
    return _ADAPTERS.get(sector_module)
