import json
from pathlib import Path

from .errors import UnsafePathError

REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_path(*parts: str, root: Path | None = None) -> Path:
    """Join ``parts`` onto ``root`` (defaults to the real repository root).

    ``root`` lets callers point company-specific data lookups at an
    isolated fixture or output directory (e.g. for tests, or ``--output-dir``)
    while shared, versioned pipeline configuration under ``config/pipeline``
    and ``config/taxonomies`` keeps resolving against the real repository.
    """
    base = root if root is not None else REPO_ROOT
    return base.joinpath(*parts)


def safe_ticker(ticker: str) -> str:
    if ticker != ticker.upper() or not ticker.replace('.', '').replace('-', '').isalnum() or '..' in ticker or '/' in ticker or '\\' in ticker:
        raise UnsafePathError(f"Unsafe or non-normalized ticker: {ticker}")
    return ticker


def ensure_inside_repo(path: Path, root: Path | None = None) -> Path:
    resolved = path.resolve()
    base = (root if root is not None else REPO_ROOT).resolve()
    if base not in resolved.parents and resolved != base:
        raise UnsafePathError(f"Path escapes repository: {path}")
    return resolved


def is_drive_archived(rel_path: str, root: Path | None = None) -> bool:
    """Whether a ``raw/{TICKER}/...`` path that does not exist locally is
    nonetheless accounted for in that ticker's Google Drive manifest.

    Raw source documents are archived to Drive and deliberately excluded
    from git (see ``wiki/systems/ham-veri-toplama.md``); only
    ``raw/{TICKER}/.drive-manifest.json`` (a relative-path -> drive_file_id
    lookup) is committed. A manifest path under ``raw/`` that has no local
    file but *is* listed in that manifest is not missing data, just
    Drive-only storage.
    """
    parts = Path(rel_path).parts
    if len(parts) < 3 or parts[0] != "raw":
        return False
    ticker = parts[1]
    remainder = "/".join(parts[2:])
    manifest_path = repo_path("raw", ticker, ".drive-manifest.json", root=root)
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return remainder in manifest
