"""Temporary FX-close-to-T70-observation promotion bridge.

Structurally parallel to the sibling ``ingestion.promotion`` package (the
generic EOD-close promotion bridge), but promotes a normalized FX rate
row into an ``observation_type="fx"``/``fx_mode="market_close"``
observation instead of an equity ``price`` observation. Always the
**unadjusted** close only, never ``adjusted_close`` (docs/temporary-
yfinance-usdtry-internal-valuation-exception.md).
"""

from __future__ import annotations
