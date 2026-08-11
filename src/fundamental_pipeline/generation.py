"""Output-path resolution, canonical serialization, transactional multi-file
writes, and drift detection against committed production outputs.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import DriftDetected, RollbackError, TransactionalWriteError
from .io import read_json
from .paths import repo_path, safe_ticker


def output_paths(ticker: str, period: str, output_root: Path | None = None) -> dict[str, Path]:
    """The four generated-output paths for a ticker/period, mirroring
    production layout under ``output_root`` (defaults to the repo root)."""
    ticker = safe_ticker(ticker)
    root = output_root if output_root is not None else repo_path()
    return {
        "derived": root / "data" / "financial" / ticker / f"{period}-derived-ratios.json",
        "signals": root / "data" / "signals" / ticker / f"{period}.json",
        "summaries": root / "data" / "summaries" / ticker / f"{period}.json",
        "report": root / "reports" / ticker / f"{period}-fundamental-analysis.md",
    }


def canonical_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


@dataclass
class DriftFinding:
    path: Path
    committed: str | None
    generated: str


def load_committed_outputs(ticker: str, period: str, root: Path | None = None) -> dict[str, dict | str | None]:
    """Load whichever of the four generated-output files
    (derived/signals/summaries/report) are currently committed for a
    ticker/period, keyed the same way :func:`output_paths` and
    :class:`~fundamental_pipeline.pipeline.GeneratedAnalysis` are. A key
    whose file does not exist maps to ``None`` (never silently omitted --
    callers that require every output present, such as full-mode
    ``validate``, can distinguish "not generated yet" from "generated and
    valid"). Used only for reading previously committed output for
    inspection/validation; never treated as an input to regeneration."""
    paths = output_paths(ticker, period, root)
    result: dict[str, dict | str | None] = {}
    for key, path in paths.items():
        if not path.exists():
            result[key] = None
        elif key == "report":
            result[key] = path.read_text(encoding="utf-8")
        else:
            result[key] = read_json(path)
    return result


def diff_against_committed(generated_by_path: dict[Path, str]) -> list[DriftFinding]:
    """Compare generated content (already canonically serialized, or plain
    text for the Markdown report) against whatever is currently committed
    at each path. Never writes anything."""
    findings = []
    for path, generated_text in generated_by_path.items():
        committed_text = path.read_text(encoding="utf-8") if path.exists() else None
        if committed_text != generated_text:
            findings.append(DriftFinding(path, committed_text, generated_text))
    return findings


def _fsync_file(f) -> None:
    """Best-effort durability: flush and fsync a just-written file. Some
    filesystems/platforms don't support this meaningfully; failures here are
    not fatal to the write itself."""
    try:
        f.flush()
        os.fsync(f.fileno())
    except OSError:
        pass


def _fsync_dir(path: Path) -> None:
    """Best-effort durability: fsync a directory after a rename into it, so
    the rename is less likely to be lost on an unclean shutdown. Optional by
    design -- not every OS/filesystem supports directory fsync."""
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_bundle_transactional(files_by_path: dict[Path, str]) -> None:
    """Write every file in the bundle, or roll back to the pre-call state.

    This is the strongest practical transactional guarantee available
    through ordinary filesystem operations. It is deliberately **not**
    described as "filesystem-atomic": no cross-directory, multi-file
    transaction primitive exists in POSIX or NTFS, so a truly indivisible
    multi-file commit is not achievable this way. What this function does
    guarantee:

    1. Every new file is fully written (and best-effort fsynced) to a temp
       path beside its target before any target is touched. A failure
       during this staging phase never modifies anything on disk -- only
       the staged temp files are removed.
    2. Every *existing* target is renamed aside to a backup path (not
       deleted) immediately before its replacement is attempted, so the
       original bytes survive under a recoverable name until the whole
       bundle has committed.
    3. If any replacement step fails, every already-replaced target from
       this call is restored from its backup, every newly-created target is
       removed, and all temporary/backup files are cleaned up -- the
       directory tree is left exactly as it was before the call, and
       :class:`~fundamental_pipeline.errors.TransactionalWriteError` is
       raised.
    4. If a rollback restoration itself fails partway (e.g. the filesystem
       became read-only mid-rollback), the backup file for that specific
       path is deliberately **not** deleted, and
       :class:`~fundamental_pipeline.errors.RollbackError` is raised naming
       every path that could not be restored and where its original bytes
       are still recoverable from. Silent data loss is never acceptable,
       even at the cost of not being able to claim a fully clean rollback.
    """
    for parent in {p.parent for p in files_by_path}:
        parent.mkdir(parents=True, exist_ok=True)

    staged: list[tuple[Path, str]] = []
    try:
        for path, text in files_by_path.items():
            fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                _fsync_file(f)
            staged.append((path, tmp_name))
    except BaseException as exc:
        for _, tmp_name in staged:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        raise TransactionalWriteError(f"Failed while staging output files; nothing was written to any target: {exc}") from exc

    backups: dict[Path, str] = {}
    newly_created: list[Path] = []

    def _restore_all() -> list[tuple[Path, str | None]]:
        failed: list[tuple[Path, str | None]] = []
        for path, backup_name in backups.items():
            try:
                os.replace(backup_name, path)
            except OSError:
                failed.append((path, backup_name))
        for path in newly_created:
            try:
                if path.exists():
                    os.remove(path)
            except OSError:
                failed.append((path, None))
        return failed

    def _cleanup_staged() -> None:
        for _, tmp_name in staged:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    try:
        for path, tmp_name in staged:
            existed = path.exists()
            if existed:
                bfd, backup_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".bak")
                os.close(bfd)
                os.remove(backup_name)  # reserve the name only; the rename below populates it
                os.replace(path, backup_name)
                backups[path] = backup_name
            os.replace(tmp_name, path)
            if not existed:
                newly_created.append(path)
            _fsync_dir(path.parent)
    except BaseException as exc:
        _cleanup_staged()
        failed = _restore_all()
        if failed:
            details = "; ".join(
                f"{path} (original bytes recoverable from backup file {backup})" if backup is not None
                else f"{path} (newly-created target could not be removed)"
                for path, backup in failed
            )
            raise RollbackError(
                f"Transactional write failed during replacement and rollback could not fully restore "
                f"prior state: {details}. Underlying failure: {exc}"
            ) from exc
        raise TransactionalWriteError(
            f"Transactional write failed during replacement; every previously-replaced target was "
            f"restored and every newly-created target was removed: {exc}"
        ) from exc

    for backup_name in backups.values():
        if os.path.exists(backup_name):
            os.remove(backup_name)


def write_bundle_atomic(files_by_path: dict[Path, str]) -> None:
    """Deprecated alias for :func:`write_bundle_transactional`, kept for
    backward compatibility with existing callers/tests."""
    write_bundle_transactional(files_by_path)


def check_no_drift(generated_by_path: dict[Path, str]) -> None:
    """Raise :class:`DriftDetected` listing every path whose generated
    content differs from what is currently committed. Used by ``--check``;
    never writes anything."""
    findings = diff_against_committed(generated_by_path)
    if findings:
        details = "\n".join(f"  - {f.path}" for f in findings)
        raise DriftDetected(f"Drift detected in {len(findings)} file(s):\n{details}")
