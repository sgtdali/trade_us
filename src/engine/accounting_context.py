"""Accounting-context extraction and comparison-context resolution for
normalized direct-financial and historical-series files.

The controlled vocabularies here are the single source of truth for what
counts as a valid accounting-context value; schemas and validators both
import from this module rather than duplicating the enums.
"""

from __future__ import annotations

from .periods import AccountingContext

SCALE_VALUES = frozenset({"unit", "thousand", "million", "billion"})
ACCOUNTING_BASIS_VALUES = frozenset({"IFRS", "TFRS", "US_GAAP", "other", "undetermined"})
AUDIT_STATUS_VALUES = frozenset({"audited", "reviewed_interim", "unaudited", "undetermined"})
INFLATION_STATUS_VALUES = frozenset({"applied", "not_applied", "not_applicable", "undetermined"})
RESTATEMENT_STATUS_VALUES = frozenset({"original", "restated", "not_applicable", "undetermined"})
CONSOLIDATION_VALUES = frozenset({"consolidated", "unconsolidated", "combined", "undetermined"})


def context_from_direct_financials(data: dict) -> AccountingContext:
    """The accounting context that applies to a direct-financials file's
    ``value`` (current-period) figures."""
    return AccountingContext(
        currency=data.get("currency"),
        scale=data.get("scale"),
        consolidation=data.get("consolidation"),
        accounting_basis=data.get("accounting_basis"),
        inflation_adjustment_status=(data.get("inflation_adjustment") or {}).get("status"),
        restatement_status=(data.get("restatement") or {}).get("status"),
        publication_date=data.get("publication_date"),
        source_revision=data.get("source_revision"),
    )


def comparison_context_from_direct_financials(data: dict) -> AccountingContext:
    """The effective accounting context for a direct-financials file's
    ``comparison_value`` figures.

    Default rule: current and comparison figures are assumed to come from
    the same filing/context (the common case: a quarterly report shows
    both periods' columns side by side), so this inherits the current
    context wholesale unless the file declares an explicit
    ``comparison_accounting_context`` override -- which only needs to name
    the fields that actually differ; any field it omits still inherits
    from the current context.
    """
    base = context_from_direct_financials(data)
    override = data.get("comparison_accounting_context") or {}
    if not override:
        return base
    inflation = override.get("inflation_adjustment")
    restatement = override.get("restatement")
    return AccountingContext(
        currency=override.get("currency", base.currency),
        scale=override.get("scale", base.scale),
        consolidation=override.get("consolidation", base.consolidation),
        accounting_basis=override.get("accounting_basis", base.accounting_basis),
        inflation_adjustment_status=(inflation or {}).get("status") if inflation is not None else base.inflation_adjustment_status,
        restatement_status=(restatement or {}).get("status") if restatement is not None else base.restatement_status,
        publication_date=override.get("publication_date", base.publication_date),
        source_revision=override.get("source_revision", base.source_revision),
    )


def context_from_series(series_data: dict, period_entry: dict | None = None) -> AccountingContext:
    """The effective accounting context for one period entry of a
    historical-series file: series-level ``accounting_context_defaults``
    with an optional period-level ``accounting_context`` override merged
    on top (only the fields the override actually names are replaced)."""
    defaults = series_data.get("accounting_context_defaults") or {}
    override = (period_entry or {}).get("accounting_context") or {}
    inflation = override.get("inflation_adjustment", defaults.get("inflation_adjustment"))
    restatement = override.get("restatement", defaults.get("restatement"))
    return AccountingContext(
        currency=override.get("currency", defaults.get("currency", series_data.get("currency"))),
        scale=override.get("scale", defaults.get("scale")),
        consolidation=override.get("consolidation", defaults.get("consolidation")),
        accounting_basis=override.get("accounting_basis", defaults.get("accounting_basis")),
        inflation_adjustment_status=(inflation or {}).get("status"),
        restatement_status=(restatement or {}).get("status"),
        publication_date=override.get("publication_date", defaults.get("publication_date")),
        source_revision=override.get("source_revision", defaults.get("source_revision")),
    )
