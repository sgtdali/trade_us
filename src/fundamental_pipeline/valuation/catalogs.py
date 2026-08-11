"""Public compatibility facade for valuation catalog authoring and loading.

Catalog definitions live in domain modules; this module deliberately preserves
the established import surface for callers.
"""

from .catalog_capital import _CAPITAL_BASIS_ENTRIES
from .catalog_comparison import (
    _MAGIC_FORMULA_DIAGNOSTIC_ENTRY,
    _PIOTROSKI_DIAGNOSTIC_ENTRY,
    _RANKING_POLICY_ENTRIES,
)
from .catalog_methods import _METHOD_FORMULA_ENTRIES
from .catalog_policies import (
    _APPLICABILITY_POLICY_ENTRIES,
    _MARKET_INPUT_POLICY_ENTRIES,
    _METHOD_SET_POLICY_ENTRIES,
    _STATUS_CONFIDENCE_POLICY_ENTRIES,
)
from .catalog_runtime import (
    CATALOG_SCHEMA_VERSION,
    CATALOG_VERSION,
    EFFECTIVE_FROM,
    CatalogRegistry,
    CatalogSelection,
    build_all_catalogs,
    build_catalog,
    build_comparison_everything,
    build_all_comparison_catalogs,
    build_everything,
    load_catalog_registry,
    load_comparison_catalog_registry,
    render_canonical_files,
    render_comparison_canonical_files,
)
from .catalog_shared import _SHARED_CATALOG_ENTRIES
from .errors import CatalogError

__all__ = [
    "CATALOG_SCHEMA_VERSION", "CATALOG_VERSION", "EFFECTIVE_FROM",
    "CatalogError", "CatalogRegistry", "CatalogSelection",
    "build_all_catalogs", "build_catalog", "build_all_comparison_catalogs",
    "build_comparison_everything", "build_everything",
    "load_catalog_registry", "load_comparison_catalog_registry",
    "render_canonical_files", "render_comparison_canonical_files",
]
