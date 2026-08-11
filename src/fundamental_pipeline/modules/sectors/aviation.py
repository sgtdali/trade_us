"""Aviation sector module: unit-economics KPI profile for airlines.

KPI ids are the canonical ids actually produced by financial-operational
normalization (see ``data/financial-operational/{TICKER}/{period}.json``),
not aspirational placeholders. ``landing_count`` was dropped during the
2026-07 metric-id audit: no normalized source ever populated it and no
formula, signal, or completeness profile depended on it.
"""

from .base import SectorModule

REQUIRED_AVIATION_KPIS = (
    "ask",
    "passenger_count",
    "passenger_load_factor_quarterly",
    "rask_adjusted_cargo_capacity",
)

OPTIONAL_AVIATION_KPIS = (
    "rpk",
    "cargo_tonnage",
    "aircraft_count",
    "destination_count",
    "passenger_rask",
    "passenger_yield",
    "cask",
    "ex_fuel_cask",
    "fuel_unit_cost",
    "fuel_consumption",
    "fuel_total_expense",
    "fuel_expense_share",
    "ebitdar_amount",
    "ebitdar_margin",
    "ebitda_amount",
    "ebitda_margin",
)

AVIATION_KPIS = REQUIRED_AVIATION_KPIS + OPTIONAL_AVIATION_KPIS

MODULE = SectorModule("aviation", "Aviation", "implemented", ("standard_corporate",), AVIATION_KPIS)
