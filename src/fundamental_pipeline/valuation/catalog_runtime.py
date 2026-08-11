"""Catalog assembly and immutable runtime registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from ..paths import repo_path
from .canonical import canonical_text
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
from .catalog_shared import _SHARED_CATALOG_ENTRIES
from .errors import CatalogError
from .safe_json import read_safe_json
from .schemas import iter_schema_errors

CATALOG_SCHEMA_VERSION = "1.0.0"
CATALOG_VERSION = "1.0.0"
EFFECTIVE_FROM = "2026-07-15"

_COMPARISON_CATALOG_SOURCE_ORDER: list[tuple[str, str, list[dict[str, Any]]]] = [
    ("valuation.policies.comparison_ranking", "comparison/comparison-ranking-policies.json", _RANKING_POLICY_ENTRIES),
    ("valuation.policies.strategy_diagnostic", "comparison/strategy-diagnostic-policies.json", [_MAGIC_FORMULA_DIAGNOSTIC_ENTRY, _PIOTROSKI_DIAGNOSTIC_ENTRY]),
]


def build_all_comparison_catalogs() -> dict[str, dict[str, Any]]:
    return {
        relative_filename: build_catalog(catalog_id, entries)
        for catalog_id, relative_filename, entries in _COMPARISON_CATALOG_SOURCE_ORDER
    }


def build_comparison_everything() -> dict[str, dict[str, Any]]:
    return build_all_comparison_catalogs()


def render_comparison_canonical_files() -> dict[str, str]:
    """Return ``{relative_filename_under_config_valuation_comparison:
    canonical_text}`` for the T74-A comparison/diagnostic policy
    catalogs."""
    return {name: canonical_text(doc) for name, doc in build_comparison_everything().items()}


def load_comparison_catalog_registry(*, repo_root: Path | None = None) -> "CatalogRegistry":
    """Load and return the T74-A comparison/diagnostic policy catalogs
    directly from ``repo_root/config/valuation/comparison`` -- entirely
    independent of :func:`load_catalog_registry`'s T70/T71 registry."""
    root = repo_root if repo_root is not None else repo_path()
    comparison_dir = root / "config" / "valuation" / "comparison"
    catalogs_by_id = _load_catalog_directory(comparison_dir)
    return CatalogRegistry(catalogs_by_id)


_CATALOG_SOURCE_ORDER: list[tuple[str, str, list[dict[str, Any]]]] = [
    ("valuation.formulas.capital_basis", "capital-basis-formulas.json", _CAPITAL_BASIS_ENTRIES),
    ("valuation.policies.market_input", "market-input-policies.json", _MARKET_INPUT_POLICY_ENTRIES),
    ("valuation.policies.status_confidence_assessment", "status-confidence-assessment-policies.json", _STATUS_CONFIDENCE_POLICY_ENTRIES),
    ("valuation.catalogs.shared", "shared-catalog.json", _SHARED_CATALOG_ENTRIES),
    ("valuation.formulas.methods", "valuation-method-formulas.json", _METHOD_FORMULA_ENTRIES),
    ("valuation.policies.applicability", "company-sector-applicability-policies.json", _APPLICABILITY_POLICY_ENTRIES),
    ("valuation.policies.method_sets", "method-set-policies.json", _METHOD_SET_POLICY_ENTRIES),
]

def _sorted_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(entries, key=lambda e: e["entry_id"])


def build_catalog(catalog_id: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Assemble one catalog envelope (with entries in canonical
    lexicographic-by-entry_id order). Pure function of
    ``catalog_id``/``entries``; never reads or writes files."""
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "catalog_id": catalog_id,
        "catalog_version": CATALOG_VERSION,
        "lifecycle_status": "approved",
        "effective_from": EFFECTIVE_FROM,
        "entries": _sorted_entries(entries),
    }


def build_all_catalogs() -> dict[str, dict[str, Any]]:
    """Return ``{relative_filename: catalog_envelope}`` for all four
    physical catalogs."""
    return {
        relative_filename: build_catalog(catalog_id, entries)
        for catalog_id, relative_filename, entries in _CATALOG_SOURCE_ORDER
    }


def build_everything() -> dict[str, dict[str, Any]]:
    """Return ``{relative_filename_under_config_valuation: document}`` for
    all four catalogs -- everything that
    ``scripts/build_valuation_catalogs.py`` writes."""
    return build_all_catalogs()


def render_canonical_files() -> dict[str, str]:
    """Return ``{relative_filename: canonical_text}`` -- the exact bytes
    (as text) that must be written to ``config/valuation/`` for every
    generated resource."""
    return {name: canonical_text(doc) for name, doc in build_everything().items()}


# ---------------------------------------------------------------------------
# Loader: read bounded bytes -> parse -> schema-validate -> canonicalize
# without own content_hash -> recompute+verify content_hash -> verify
# expected logical ID/version -> verify manifest path -> verify lock
# membership -> return an immutable snapshot.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogSelection:
    """The result of :meth:`CatalogRegistry.select_entry`: the selected
    (frozen) entry, plus any non-fatal lifecycle warnings that apply to
    this selection. An empty ``warnings`` tuple means the selection is
    unremarkable (an ``approved`` catalog and entry)."""

    entry: MappingProxyType
    warnings: tuple[str, ...] = ()


def _deep_freeze(value: Any) -> Any:
    """Recursively convert a JSON-shaped value into an immutable
    equivalent: dict -> MappingProxyType (over an already-frozen dict),
    list -> tuple. Scalars are returned as-is (str/int/bool/None/float are
    already immutable in Python). Used so :class:`CatalogRegistry` can
    hand out its internal state directly without a caller being able to
    mutate it -- there is no mutable dict/list left to reach into at any
    depth."""
    if isinstance(value, dict):
        return MappingProxyType({k: _deep_freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(v) for v in value)
    return value


class CatalogRegistry:
    """An immutable in-memory view of the physical catalogs loaded from a
    ``config/valuation/**`` directory. Every value handed back by
    :meth:`catalog` is deep-frozen (:class:`types.MappingProxyType` for
    objects, ``tuple`` for arrays): a caller cannot mutate the registry's
    state through the returned value at any depth, and repeated calls
    return the same frozen structure rather than a fresh mutable copy."""

    def __init__(self, catalogs_by_id: dict[str, dict[str, Any]]):
        self._catalogs_by_id: MappingProxyType[str, Any] = _deep_freeze(dict(catalogs_by_id))

    def catalog(self, catalog_id: str) -> MappingProxyType[str, Any]:
        if catalog_id not in self._catalogs_by_id:
            raise CatalogError(f"unknown catalog_id: {catalog_id!r}")
        return self._catalogs_by_id[catalog_id]

    def select_entry(self, catalog_id: str, entry_id: str, *, mode: str = "generation") -> "CatalogSelection":
        """Look up one catalog entry by ID, enforcing lifecycle/version
        compatibility (docs/valuation-t70-02-schema-catalog-version-lock-specification.md
        Section 11 / T67.1's lifecycle contract):

        * ``approved`` catalog and entry: usable in either mode, no warning.
        * ``deprecated`` catalog/entry: usable in either mode (its exact
          locked version is still valid), but selecting it for
          ``mode="generation"`` (the default -- new output, not a replay
          of a historical fixture) carries a warning in the returned
          :class:`CatalogSelection`; ``mode="replay"`` carries none.
        * ``retired`` catalog/entry: replay-only (``mode="replay"``);
          selecting it for ``mode="generation"`` is a hard, fail-closed
          :class:`CatalogError`.
        * ``draft`` catalog/entry: never selectable through a locked
          registry in either mode (only ``approved``/``deprecated``/
          ``retired`` resources are ever loaded and locked in the first
          place) -- always a fail-closed :class:`CatalogError`.

        Unknown ``catalog_id``/``entry_id`` and unknown/missing
        ``lifecycle_status`` values are also fail-closed
        :class:`CatalogError`; this method never returns a best-effort
        entry.
        """
        if mode not in ("generation", "replay"):
            raise CatalogError(f"unsupported catalog selection mode: {mode!r}")

        catalog = self.catalog(catalog_id)
        warnings: list[str] = []
        catalog_warning = _check_lifecycle(scope=f"catalog {catalog_id!r}", lifecycle_status=catalog.get("lifecycle_status"), mode=mode)
        if catalog_warning:
            warnings.append(catalog_warning)

        entries = {entry["entry_id"]: entry for entry in catalog.get("entries", ())}
        if entry_id not in entries:
            raise CatalogError(f"{catalog_id}: unknown catalog entry_id {entry_id!r}")
        entry = entries[entry_id]
        entry_warning = _check_lifecycle(scope=f"{catalog_id}:{entry_id}", lifecycle_status=entry.get("lifecycle_status"), mode=mode)
        if entry_warning:
            warnings.append(entry_warning)
        return CatalogSelection(entry=entry, warnings=tuple(warnings))

    @property
    def catalog_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._catalogs_by_id))


def _check_lifecycle(*, scope: str, lifecycle_status: str | None, mode: str) -> str | None:
    """Return a warning message when ``lifecycle_status``/``mode`` is
    usable-but-notable, or ``None`` when it is unremarkable. Raises
    :class:`CatalogError` when the combination is not usable at all."""
    if lifecycle_status == "approved":
        return None
    if lifecycle_status == "draft":
        raise CatalogError(f"{scope}: lifecycle_status='draft' is never selectable through a locked registry")
    if lifecycle_status == "retired":
        if mode == "replay":
            return f"{scope}: lifecycle_status='retired', selected only because mode='replay'"
        raise CatalogError(f"{scope}: lifecycle_status='retired' is replay-only and unavailable for new generation")
    if lifecycle_status == "deprecated":
        if mode == "replay":
            return None
        return (
            f"{scope}: lifecycle_status='deprecated' selected for mode='generation'; "
            "prefer the current approved version for new output"
        )
    raise CatalogError(f"{scope}: unknown or missing lifecycle_status: {lifecycle_status!r}")


def load_catalog_registry(*, repo_root: Path | None = None) -> CatalogRegistry:
    """Load and return the physical catalogs directly from
    ``repo_root/config/valuation`` (defaults to the real repository root).

    Each ``*.json`` file directly under that directory is read, validated
    against the ``valuation-catalog`` schema, and indexed by its own
    ``catalog_id`` -- no manifest/lock indirection.
    """
    root = repo_root if repo_root is not None else repo_path()
    valuation_dir = root / "config" / "valuation"
    catalogs_by_id = _load_catalog_directory(valuation_dir)
    return CatalogRegistry(catalogs_by_id)


def _load_catalog_directory(directory: Path) -> dict[str, dict[str, Any]]:
    """Read every ``*.json`` file directly under ``directory``, validate it
    against the ``valuation-catalog`` schema, and index by ``catalog_id``."""
    catalogs_by_id: dict[str, dict[str, Any]] = {}
    if not directory.exists():
        return catalogs_by_id
    for path in sorted(directory.glob("*.json")):
        catalog_doc = read_safe_json(path, label=path.name)
        for error in iter_schema_errors("valuation-catalog", catalog_doc):
            raise CatalogError(f"{path.name}: fails valuation-catalog schema at {error.path}: {error.message}")
        catalog_id = catalog_doc.get("catalog_id")
        if not catalog_id:
            raise CatalogError(f"{path.name}: missing catalog_id")
        if catalog_id in catalogs_by_id:
            raise CatalogError(f"duplicate catalog_id {catalog_id!r} across catalog files")
        catalogs_by_id[catalog_id] = catalog_doc
    return catalogs_by_id
