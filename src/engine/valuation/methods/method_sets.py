"""Typed configured-row expansion of a resolved method-set catalog entry
(docs/valuation-t71-03-applicability-method-set-family-specification.md
Section 4).

This module never selects a method set itself (that is
:func:`engine.valuation.methods.applicability.resolve_method_set_entry`);
it only turns one already-resolved method-set entry's ``configured_rows``
into typed, applicability-resolved :class:`ConfiguredRow` objects, in the
catalog's own declared order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..catalogs import CatalogRegistry
from ..errors import ApplicabilityError
from .applicability import resolve_applicability_policy


@dataclass(frozen=True)
class ConfiguredRow:
    method_id: str
    formula_id: str
    role: str
    applicability_policy_ref: str | None
    outcome: str
    requires: tuple[str, ...]


def resolve_configured_rows(method_set_entry: Mapping[str, Any], catalog_registry: CatalogRegistry) -> tuple[ConfiguredRow, ...]:
    """Expand ``method_set_entry["body"]["configured_rows"]`` (already in
    canonical catalog-declared order -- never reordered by value or
    status) into typed rows, resolving each row's exact applicability
    outcome and required-capability list from the applicability catalog.
    Raises :class:`ApplicabilityError` if a row is empty or references an
    unknown formula/policy."""
    raw_rows = method_set_entry["body"].get("configured_rows")
    if not raw_rows:
        raise ApplicabilityError(f"{method_set_entry['entry_id']}: method set has no configured_rows")

    rows: list[ConfiguredRow] = []
    for raw in raw_rows:
        policy_ref = raw.get("applicability_policy_ref")
        policy_entry = resolve_applicability_policy(policy_ref, catalog_registry)
        rows.append(ConfiguredRow(
            method_id=raw["method_id"],
            formula_id=raw["formula_id"],
            role=raw["role"],
            applicability_policy_ref=policy_ref,
            outcome=policy_entry["body"]["outcome"],
            requires=tuple(policy_entry["body"].get("requires", ())),
        ))
    return tuple(rows)
