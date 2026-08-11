"""Safe governed-root path handling for T70-B market/valuation-inputs
output artifacts.

Canonical relative paths (docs/valuation-t70-04-market-registry-snapshot-specification.md
Section 14, docs/valuation-t70-05-financial-basis-input-resolver-specification.md
Section 16):

    data/market/{TICKER}/{AS_OF_DATE}.json
    data/valuation-inputs/{TICKER}/{AS_OF_DATE}/{CONTEXT_ID}.json

This module only computes and safely resolves these dimensional paths; it
never infers a repository production root on its own -- every caller must
supply an explicit governed root (``--output-dir``/``--root``). Containment
and symlink-escape enforcement is delegated to
:func:`engine.valuation.references.safe_relative_path`, which
already resolves symlinks before checking containment.
"""

from __future__ import annotations

import re
from pathlib import Path

from .errors import ArtifactReferenceError
from .references import safe_relative_path

_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,31}$")
_ISO_DATE_RE = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
_CONTEXT_ID_RE = re.compile(r"^ctx-[0-9a-f]{24}$")

MARKET_SNAPSHOT_ROOT = "data/market"
VALUATION_INPUTS_ROOT = "data/valuation-inputs"
VALUATION_RESULTS_ROOT = "data/valuation-results"
VALUATION_COMPARISON_ROOT = "data/valuation-comparison"
HOLDING_ASSETS_ROOT = "data/holding-assets"
HOLDING_VALUATION_INPUTS_ROOT = "data/holding-valuation-inputs"
HOLDING_VALUATION_RESULTS_ROOT = "data/holding-valuation-results"

_COMPARISON_TYPE_RE = re.compile(r"^[a-z][a-z_]*$")


def validate_ticker_dimension(ticker: str) -> str:
    if not isinstance(ticker, str) or not _TICKER_RE.fullmatch(ticker):
        raise ArtifactReferenceError(f"invalid ticker path dimension: {ticker!r}")
    return ticker


def validate_date_dimension(as_of_date: str) -> str:
    if not isinstance(as_of_date, str) or not _ISO_DATE_RE.fullmatch(as_of_date):
        raise ArtifactReferenceError(f"invalid as_of_date path dimension: {as_of_date!r}")
    return as_of_date


def validate_context_id_dimension(context_id: str) -> str:
    if not isinstance(context_id, str) or not _CONTEXT_ID_RE.fullmatch(context_id):
        raise ArtifactReferenceError(f"invalid context_id path dimension: {context_id!r}")
    return context_id


def validate_comparison_type_dimension(comparison_type: str) -> str:
    if not isinstance(comparison_type, str) or not _COMPARISON_TYPE_RE.fullmatch(comparison_type):
        raise ArtifactReferenceError(f"invalid comparison_type path dimension: {comparison_type!r}")
    return comparison_type


def market_snapshot_relative_path(ticker: str, as_of_date: str) -> str:
    """``data/market/{TICKER}/{AS_OF_DATE}.json`` -- validates both
    dimensions before building the path so a malformed dimension never
    silently becomes part of a path string."""
    ticker = validate_ticker_dimension(ticker)
    as_of_date = validate_date_dimension(as_of_date)
    return f"{MARKET_SNAPSHOT_ROOT}/{ticker}/{as_of_date}.json"


def valuation_inputs_relative_path(ticker: str, as_of_date: str, context_id: str) -> str:
    """``data/valuation-inputs/{TICKER}/{AS_OF_DATE}/{CONTEXT_ID}.json``."""
    ticker = validate_ticker_dimension(ticker)
    as_of_date = validate_date_dimension(as_of_date)
    context_id = validate_context_id_dimension(context_id)
    return f"{VALUATION_INPUTS_ROOT}/{ticker}/{as_of_date}/{context_id}.json"


def valuation_results_relative_path(ticker: str, as_of_date: str, context_id: str) -> str:
    """``data/valuation-results/{TICKER}/{AS_OF_DATE}/{CONTEXT_ID}/current.json``
    (docs/valuation-t71-01-method-engine-architecture-file-plan.md
    Section 12's reserved production-compatible path; T71 never writes
    under the real, un-prefixed production root -- every caller supplies
    an explicit governed ``--output-dir``/``--root``)."""
    ticker = validate_ticker_dimension(ticker)
    as_of_date = validate_date_dimension(as_of_date)
    context_id = validate_context_id_dimension(context_id)
    return f"{VALUATION_RESULTS_ROOT}/{ticker}/{as_of_date}/{context_id}/current.json"


def holding_assets_relative_path(ticker: str, period: str) -> str:
    """``data/holding-assets/{TICKER}/{PERIOD}.json``."""
    ticker = validate_ticker_dimension(ticker)
    if not isinstance(period, str) or not re.fullmatch(r"[0-9]{4}-(?:Q[1-3]|FY)", period):
        raise ArtifactReferenceError(f"invalid holding period path dimension: {period!r}")
    return f"{HOLDING_ASSETS_ROOT}/{ticker}/{period}.json"


def holding_valuation_inputs_relative_path(ticker: str, as_of_date: str) -> str:
    """``data/holding-valuation-inputs/{TICKER}/{AS_OF_DATE}.json``."""
    return f"{HOLDING_VALUATION_INPUTS_ROOT}/{validate_ticker_dimension(ticker)}/{validate_date_dimension(as_of_date)}.json"


def holding_valuation_results_relative_path(ticker: str, as_of_date: str) -> str:
    """``data/holding-valuation-results/{TICKER}/{AS_OF_DATE}.json``."""
    return f"{HOLDING_VALUATION_RESULTS_ROOT}/{validate_ticker_dimension(ticker)}/{validate_date_dimension(as_of_date)}.json"


def comparison_relative_path(comparison_type: str, context_id: str) -> str:
    """``data/valuation-comparison/{COMPARISON_TYPE}/{CONTEXT_ID}.json``
    (T74-B). Comparison artifacts key on ``comparison_type``+``context_id``
    rather than ``ticker``+``as_of_date``, so no single-ticker path
    dimension applies uniformly across all four variants."""
    comparison_type = validate_comparison_type_dimension(comparison_type)
    context_id = validate_context_id_dimension(context_id)
    return f"{VALUATION_COMPARISON_ROOT}/{comparison_type}/{context_id}.json"


def resolve_governed_path(root: Path, relative_path: str) -> Path:
    """Resolve ``relative_path`` against the explicit governed ``root``,
    rejecting traversal, absolute paths, backslashes, NUL bytes, and
    symlink escape. Never resolves against an implicit repository
    production root -- ``root`` must always be supplied by the caller
    (an explicit ``--output-dir``/``--root`` CLI argument or a test
    ``tmp_path``)."""
    if "\x00" in relative_path:
        raise ArtifactReferenceError("relative_path must not contain a NUL byte")
    if not relative_path.endswith(".json"):
        raise ArtifactReferenceError("governed resources must use a '.json' relative_path")
    return safe_relative_path(root, relative_path)


def valuation_report_relative_path(ticker: str, as_of_date: str) -> str:
    """reports/valuation/{TICKER}/{AS_OF_DATE}-valuation-analysis.md"""
    ticker = validate_ticker_dimension(ticker)
    as_of_date = validate_date_dimension(as_of_date)
    return f"reports/valuation/{ticker}/{as_of_date}-valuation-analysis.md"


def resolve_governed_report_path(root: Path, relative_path: str) -> Path:
    """Resolve ``relative_path`` against the explicit governed ``root``,
    rejecting traversal, absolute paths, backslashes, NUL bytes, and
    symlink escape, specifically for Markdown reports ending in .md."""
    if "\x00" in relative_path:
        raise ArtifactReferenceError("relative_path must not contain a NUL byte")
    if not relative_path.endswith(".md"):
        raise ArtifactReferenceError("governed report resources must use a '.md' relative_path")
    return safe_relative_path(root, relative_path)


def ensure_regular_file(path: Path) -> None:
    """Reject a target that exists but is not a regular file (directory,
    device, FIFO, socket, or other special file)."""
    if path.exists() and not path.is_file():
        raise ArtifactReferenceError(f"governed target exists but is not a regular file: {path.name}")
