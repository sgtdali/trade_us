"""Safe loading of an authored share-count ledger document -- the only
I/O this module performs. Mirrors
``engine.valuation.market.registry.load_market_source_manifest``'s
discipline: safe JSON read and schema validation, then structural/semantic
parsing via ``models.ShareCountLedger.from_dict``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...safe_json import read_safe_json
from ...schemas import iter_schema_errors
from .errors import LedgerError
from .models import ShareCountLedger


def load_ledger_document(path: Path) -> dict[str, Any]:
    """Safely read and schema-validate a share-count ledger document.
    Raises :class:`LedgerError` (never a raw parsing/KeyError) for any
    structural problem."""
    if not path.exists():
        raise LedgerError(f"missing share-count ledger: {path.name}")
    document = read_safe_json(path, label=path.name)
    if not isinstance(document, dict):
        raise LedgerError(f"{path.name}: ledger root must be a JSON object")

    schema_errors = list(iter_schema_errors("share-count-ledger", document))
    if schema_errors:
        first = schema_errors[0]
        pointer = "/" + "/".join(str(p) for p in first.path)
        raise LedgerError(f"{path.name}: fails share-count-ledger schema at {pointer}: {first.message}")

    return document


def load_ledger(path: Path) -> ShareCountLedger:
    """Load and fully parse a share-count ledger into its immutable model,
    raising :class:`LedgerError` for any structural, quote-unit-math, or
    source-reference problem."""
    document = load_ledger_document(path)
    return ShareCountLedger.from_dict(document)
