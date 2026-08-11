"""Path- and ticker-safety validation, wrapping the primitives in
:mod:`fundamental_pipeline.paths` as structured findings."""

from __future__ import annotations

from pathlib import Path

from ..errors import UnsafePathError
from ..paths import ensure_inside_repo, is_drive_archived, repo_path, safe_ticker
from .result import ValidationFinding, ValidationResult


def validate_ticker_and_paths(ticker: str, referenced_paths: list[str], data_root: Path | None = None) -> ValidationResult:
    result = ValidationResult()
    try:
        safe_ticker(ticker)
    except UnsafePathError as e:
        result.add(ValidationFinding("unsafe_ticker", "error", str(e)))
        return result

    for rel_path in referenced_paths:
        try:
            resolved = ensure_inside_repo(repo_path(rel_path, root=data_root), root=data_root)
        except UnsafePathError as e:
            result.add(ValidationFinding("path_escapes_repo", "error", str(e), rel_path))
            continue
        if not resolved.exists():
            if is_drive_archived(rel_path, root=data_root):
                result.add(ValidationFinding("referenced_path_drive_archived", "info", f"Referenced path is Drive-archived, not present locally: {rel_path}", rel_path))
            else:
                result.add(ValidationFinding("referenced_path_missing", "error", f"Referenced path does not exist: {rel_path}", rel_path))
    return result
