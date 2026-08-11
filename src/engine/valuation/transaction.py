"""Generic multi-file governed-root transactional writer with staged
promotion and exact rollback (docs/valuation-t70-06-validation-cli-transaction-specification.md
Section 9).

Protocol:

1. Resolve and safety-check every target path under the governed root.
2. Capture pre-existing bytes (or "did not exist") for every target.
3. Stage each target's canonical bytes into a same-directory temporary
   file, flush+fsync+close it, then reopen and re-read the staged bytes to
   verify they match exactly.
4. Promote every staged file atomically (``os.replace``) in deterministic
   sorted relative-path order.
5. Re-read every promoted target and verify its final bytes.
6. On any failure at any stage: restore every already-promoted target to
   its captured pre-existing bytes (or remove it, if it did not exist
   before this call), remove any leftover staged temporary files, and
   raise :class:`~engine.valuation.errors.TransactionError`
   (or :class:`~engine.valuation.errors.RollbackError` if
   the restoration itself could not fully complete).

Check mode (``check_only=True``) never creates a directory, a temporary
file, or any other filesystem state under the governed root -- it only
reads existing bytes (if any) and compares them to the in-memory expected
bytes.

A ``fault_hook`` callable is a deterministic test seam: it is invoked with
``(stage, relative_path)`` at each of the points named above and may raise
to simulate a failure at that exact point, so tests can prove the rollback
guarantee at every stage and every promotion index.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .errors import RollbackError, TransactionError
from .paths import ensure_regular_file, resolve_governed_path

FaultHook = Callable[[str, "str | None"], None]



@dataclass(frozen=True)
class WriteTarget:
    """One file to write within a transaction: a governed-root-relative
    path and its exact, already-canonicalized bytes."""

    relative_path: str
    content: bytes


@dataclass(frozen=True)
class TargetDiff:
    relative_path: str
    state: str  # "identical" | "missing" | "changed"


@dataclass(frozen=True)
class TransactionResult:
    status: str  # "written" | "no_op" | "drift"
    root: str
    written_paths: tuple[str, ...] = ()
    unchanged_paths: tuple[str, ...] = ()
    diffs: tuple[TargetDiff, ...] = ()


def _noop_hook(stage: str, relative_path: str | None) -> None:
    return None


def check_transaction(root: Path, targets: Sequence[WriteTarget]) -> TransactionResult:
    """Compare ``targets`` against the governed root's current bytes
    without performing any filesystem write. Returns ``status="no_op"``
    when every target is byte-identical to what already exists, otherwise
    ``status="drift"`` with one :class:`TargetDiff` per target."""
    ordered = sorted(targets, key=lambda t: t.relative_path)
    diffs: list[TargetDiff] = []
    unchanged: list[str] = []
    for target in ordered:
        absolute = resolve_governed_path(root, target.relative_path)
        ensure_regular_file(absolute)
        if not absolute.exists():
            diffs.append(TargetDiff(target.relative_path, "missing"))
            continue
        existing = absolute.read_bytes()
        if existing == target.content:
            unchanged.append(target.relative_path)
        else:
            diffs.append(TargetDiff(target.relative_path, "changed"))
    status = "no_op" if not diffs else "drift"
    return TransactionResult(
        status=status,
        root=str(root),
        unchanged_paths=tuple(unchanged),
        diffs=tuple(diffs),
    )


def execute_transaction(
    root: Path,
    targets: Sequence[WriteTarget],
    *,
    delete_paths: Sequence[str] = (),
    fault_hook: FaultHook = _noop_hook,
) -> TransactionResult:
    """Write every target under ``root`` transactionally. If every target
    is already byte-identical on disk, performs zero writes and returns
    ``status="no_op"``. Otherwise stages and promotes every target (even
    the already-identical ones are re-verified, never partially skipped),
    returning ``status="written"``. On any failure, restores exact prior
    state and raises :class:`TransactionError`/:class:`RollbackError`.
    """
    ordered = sorted(targets, key=lambda t: t.relative_path)
    ordered_deletes = sorted(delete_paths)
    resolved: list[tuple[WriteTarget, Path]] = []
    for target in ordered:
        absolute = resolve_governed_path(root, target.relative_path)
        ensure_regular_file(absolute)
        resolved.append((target, absolute))
    resolved_deletes: list[tuple[str, Path]] = []
    for relative_path in ordered_deletes:
        absolute = resolve_governed_path(root, relative_path)
        ensure_regular_file(absolute)
        resolved_deletes.append((relative_path, absolute))

    duplicate_paths = [t.relative_path for t in ordered] + ordered_deletes
    if len(set(duplicate_paths)) != len(duplicate_paths):
        raise TransactionError("duplicate relative_path within one transaction")

    pre_existing: dict[str, bytes | None] = {}
    staged: dict[str, Path] = {}
    promoted: list[str] = []
    try:
        fault_hook("preflight", None)

        for target, absolute in resolved:
            pre_existing[target.relative_path] = absolute.read_bytes() if absolute.exists() else None
        for relative_path, absolute in resolved_deletes:
            pre_existing[relative_path] = absolute.read_bytes() if absolute.exists() else None

        if all(
            pre_existing[target.relative_path] == target.content
            for target, _ in resolved
        ) and all(pre_existing[relative_path] is None for relative_path, _ in resolved_deletes):
            return TransactionResult(
                status="no_op",
                root=str(root),
                unchanged_paths=tuple(t.relative_path for t, _ in resolved),
            )

        for target, absolute in resolved:
            absolute.parent.mkdir(parents=True, exist_ok=True)
            fault_hook("stage", target.relative_path)
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{absolute.name}.", suffix=".tmp", dir=str(absolute.parent)
            )
            tmp_path = Path(tmp_name)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(target.content)
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                tmp_path.unlink(missing_ok=True)
                raise
            staged[target.relative_path] = tmp_path

            fault_hook("staged_verify", target.relative_path)
            restaged = tmp_path.read_bytes()
            if restaged != target.content:
                raise TransactionError(f"staged content mismatch for {target.relative_path}")

        for index, (target, absolute) in enumerate(resolved):
            fault_hook("promote", target.relative_path)
            os.replace(staged[target.relative_path], absolute)
            promoted.append(target.relative_path)

        for relative_path, absolute in resolved_deletes:
            fault_hook("delete", relative_path)
            if absolute.exists():
                absolute.unlink()
            promoted.append(relative_path)

        fault_hook("post_verify", None)
        for target, absolute in resolved:
            final_bytes = absolute.read_bytes()
            if final_bytes != target.content:
                raise TransactionError(f"post-promotion verification failed for {target.relative_path}")
        for relative_path, absolute in resolved_deletes:
            if absolute.exists():
                raise TransactionError(f"post-delete verification failed for {relative_path}")

    except BaseException as exc:
        _rollback(resolved + [(WriteTarget(relative_path, b""), absolute) for relative_path, absolute in resolved_deletes], pre_existing, promoted, staged)
        if isinstance(exc, TransactionError):
            raise
        raise TransactionError(f"transaction failed: {exc}") from exc

    return TransactionResult(
        status="written",
        root=str(root),
        written_paths=tuple(t.relative_path for t, _ in resolved) + tuple(ordered_deletes),
    )


def _rollback(
    resolved: list[tuple[WriteTarget, Path]],
    pre_existing: dict[str, bytes | None],
    promoted: list[str],
    staged: dict[str, Path],
) -> None:
    by_relpath = {t.relative_path: absolute for t, absolute in resolved}
    unrestored: list[str] = []

    for relative_path in promoted:
        absolute = by_relpath[relative_path]
        original = pre_existing[relative_path]
        try:
            if original is None:
                absolute.unlink(missing_ok=True)
            else:
                absolute.write_bytes(original)
        except OSError:
            unrestored.append(relative_path)

    for relative_path, tmp_path in staged.items():
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    if unrestored:
        raise RollbackError(
            f"rollback could not restore prior bytes for: {sorted(unrestored)}"
        )
