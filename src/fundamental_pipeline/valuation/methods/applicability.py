"""Policy-driven applicability/method-set router (docs/valuation-t71-03-applicability-method-set-family-specification.md).

No ticker branch exists anywhere in this module -- it only reads the T71-A
``valuation.policies.applicability`` / ``valuation.policies.method_sets``
catalog *data* and applies the router precedence order over it. A new
ticker policy is added by extending
``config/valuation/company-sector-applicability-policies.json`` and
``config/valuation/method-set-policies.json`` (via
``fundamental_pipeline.valuation.catalogs``), never by editing this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ..catalogs import CatalogRegistry
from ..errors import ApplicabilityError

APPLICABILITY_CATALOG_ID = "valuation.policies.applicability"
METHOD_SET_CATALOG_ID = "valuation.policies.method_sets"

_UNSUPPORTED_DENY_ENTRY_ID = "val.policy.applicability.unsupported_company_type.deny"


@dataclass(frozen=True)
class CompanySelector:
    """The immutable router input (docs/valuation-t71-03-*.md Section 2).
    Every dimension must be supplied explicitly by the caller -- no
    dimension is ever heuristically inferred here."""

    ticker: str
    company_type: str
    sector_module: str


def resolve_method_set_entry(selector: CompanySelector, catalog_registry: CatalogRegistry) -> Mapping[str, Any]:
    """Return the exact ``valuation.policies.method_sets`` catalog entry
    for ``selector``.

    Router precedence (docs/valuation-t67-08-*.md Section 2 /
    docs/valuation-t71-03-*.md Section 3): an unsupported-company-type deny
    is checked first and can never be reversed by a later match; then an
    exact ticker policy; then the standard-corporate default. Raises
    :class:`ApplicabilityError` for an unknown/unregistered selector --
    there is no generic heuristic fallback.
    """
    applicability_catalog = catalog_registry.catalog(APPLICABILITY_CATALOG_ID)
    deny_entries = {e["entry_id"]: e for e in applicability_catalog.get("entries", ())}
    deny_entry = deny_entries.get(_UNSUPPORTED_DENY_ENTRY_ID)
    if deny_entry is not None:
        denied_types = set(deny_entry["body"]["selector"].get("company_type", ()))
        if selector.company_type in denied_types:
            raise ApplicabilityError(
                f"{selector.ticker}: company_type {selector.company_type!r} is not implemented -- "
                f"{deny_entry['body'].get('rule', 'no dedicated adapter exists')}"
            )

    method_sets_catalog = catalog_registry.catalog(METHOD_SET_CATALOG_ID)
    entries = method_sets_catalog.get("entries", ())

    exact_match: Mapping[str, Any] | None = None
    default_match: Mapping[str, Any] | None = None
    for entry in entries:
        entry_selector = entry["body"]["selector"]
        if (
            entry_selector.get("ticker") == selector.ticker
            and entry_selector.get("company_type") == selector.company_type
            and entry_selector.get("sector_module") == selector.sector_module
        ):
            exact_match = entry
            break
        if (
            entry_selector.get("ticker") is None
            and entry_selector.get("company_type") == selector.company_type
            and entry_selector.get("sector_module") == selector.sector_module
        ):
            default_match = entry

    resolved = exact_match if exact_match is not None else default_match
    if resolved is None:
        raise ApplicabilityError(
            f"no method-set policy resolves for ticker={selector.ticker!r} company_type={selector.company_type!r} "
            f"sector_module={selector.sector_module!r}; unknown/unregistered selectors fail closed, there is no "
            "generic fallback"
        )
    return resolved


def resolve_applicability_policy(applicability_policy_ref: str | None, catalog_registry: CatalogRegistry) -> Mapping[str, Any]:
    """Return the exact ``valuation.policies.applicability`` entry
    ``applicability_policy_ref`` names, or a synthetic
    ``conditional_data``/no-requirements entry when ``None`` (the
    unknown-ticker default method set's rows carry no exact per-method
    applicability policy ref -- docs/valuation-t71-03-*.md Section 10).
    Raises :class:`ApplicabilityError` for a configured row that names an
    applicability policy that does not exist in the catalog."""
    if applicability_policy_ref is None:
        return MappingProxyType({
            "entry_id": None,
            "body": MappingProxyType({"outcome": "conditional_data", "requires": ()}),
        })
    applicability_catalog = catalog_registry.catalog(APPLICABILITY_CATALOG_ID)
    entries = {e["entry_id"]: e for e in applicability_catalog.get("entries", ())}
    entry = entries.get(applicability_policy_ref)
    if entry is None:
        raise ApplicabilityError(f"configured row references unknown applicability_policy_ref: {applicability_policy_ref!r}")
    return entry
