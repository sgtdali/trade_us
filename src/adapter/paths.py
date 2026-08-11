from __future__ import annotations

import re
from pathlib import Path

from .errors import SecDataError

_CIK_RE = re.compile(r"^[0-9]{10}$")
_ACCESSION_RE = re.compile(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,31}$")


def validate_cik(cik: str) -> str:
    if not _CIK_RE.fullmatch(cik):
        raise SecDataError(f"CIK must be exactly ten digits, got {cik!r}")
    return cik


def validate_accession(accession: str) -> str:
    if not _ACCESSION_RE.fullmatch(accession):
        raise SecDataError(f"invalid SEC accession number: {accession!r}")
    return accession


def validate_ticker(ticker: str) -> str:
    if not _TICKER_RE.fullmatch(ticker):
        raise SecDataError(f"invalid normalized ticker: {ticker!r}")
    return ticker


def ensure_inside(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise SecDataError(f"path escapes US workspace: {path}")
    return resolved


def filing_cache_dir(root: Path, cik: str, accession: str) -> Path:
    validate_cik(cik)
    validate_accession(accession)
    return ensure_inside(root, root / "raw-cache" / "sec" / cik / accession)
