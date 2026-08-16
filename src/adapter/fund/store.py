"""The ledger: SQLite storage and the single write gate.

Two rules shape everything here.

**One way in.** Every write goes through :func:`Ledger.commit`. Not because a
second write path would be untidy, but because validation, digesting,
duplicate detection and batch atomicity are guarantees, and a guarantee with a
bypass is a habit.

**Nothing is edited.** ``account_event`` rows are immutable, enforced by
triggers rather than convention -- a stray ``UPDATE`` from a future maintenance
script has to fail loudly rather than quietly rewrite history. A mistake is
fixed by recording another event that supersedes or voids the first.

The row's authority is its ``document`` column: the exact JSON that passed the
schema. The other columns are extracted from it for lookup and constraints,
never as a second source of truth.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

from . import schemas
from .errors import LedgerError

DEFAULT_RELATIVE_PATH = Path("data") / "fund" / "ledger.sqlite3"

#: Fields that describe the bookkeeping of a row rather than the economic fact
#: it records. Excluded from the content digest so that entering the same trade
#: twice is detected as the duplicate it is.
VOLATILE_FIELDS = frozenset({"event_id", "recorded_at", "note"})

BUSY_TIMEOUT_MS = 10_000


# --------------------------------------------------------------------------
# Migrations
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


_MIGRATION_0001 = Migration(
    version=1,
    name="account_event ledger",
    statements=(
        """
        CREATE TABLE account_event (
            event_id           TEXT PRIMARY KEY,
            event_type         TEXT NOT NULL,
            effective_date     TEXT NOT NULL,
            recorded_at        TEXT NOT NULL,
            security_id        TEXT,
            currency           TEXT,
            decision_id        TEXT,
            corrects_event_id  TEXT REFERENCES account_event(event_id),
            content_digest     TEXT NOT NULL,
            document           TEXT NOT NULL
        )
        """,
        # Ordering for replay: effective_date first because that is the economic
        # order, event_id second because UUIDv7 breaks ties by entry order.
        "CREATE INDEX account_event_replay ON account_event (effective_date, event_id)",
        "CREATE INDEX account_event_by_security ON account_event (security_id, effective_date)",
        "CREATE INDEX account_event_by_digest ON account_event (content_digest)",
        # An event may be superseded at most once. Two rows both claiming to
        # replace the same event would leave the projection with no defensible
        # answer about which one counts.
        """
        CREATE UNIQUE INDEX account_event_one_correction
            ON account_event (corrects_event_id)
            WHERE corrects_event_id IS NOT NULL
        """,
        # The opening book can only be opened once. This is what stops a
        # re-run of the import from doubling every position and the cash.
        # Corrections are exempt: they carry corrects_event_id.
        """
        CREATE UNIQUE INDEX account_event_single_opening_position
            ON account_event (security_id)
            WHERE event_type = 'opening_position' AND corrects_event_id IS NULL
        """,
        """
        CREATE UNIQUE INDEX account_event_single_opening_cash
            ON account_event (currency)
            WHERE event_type = 'opening_cash' AND corrects_event_id IS NULL
        """,
        """
        CREATE TRIGGER account_event_immutable_update
        BEFORE UPDATE ON account_event
        BEGIN
            SELECT RAISE(ABORT,
                'account_event rows are immutable: record a correcting event instead');
        END
        """,
        """
        CREATE TRIGGER account_event_immutable_delete
        BEFORE DELETE ON account_event
        BEGIN
            SELECT RAISE(ABORT,
                'account_event rows cannot be deleted: record a correction event instead');
        END
        """,
    ),
)

MIGRATIONS: tuple[Migration, ...] = (_MIGRATION_0001,)


# --------------------------------------------------------------------------
# Record kinds
# --------------------------------------------------------------------------

def _money_currency(document: Mapping[str, Any]) -> str | None:
    for key in ("cash_amount", "price", "unit_cost"):
        value = document.get(key)
        if isinstance(value, Mapping) and "currency" in value:
            return str(value["currency"])
    return None


def _account_event_columns(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_type": document["event_type"],
        "effective_date": document["effective_date"],
        "recorded_at": document["recorded_at"],
        "security_id": document.get("security_id"),
        "currency": _money_currency(document),
        "decision_id": document.get("decision_id"),
        "corrects_event_id": document.get("corrects_event_id"),
    }


@dataclass(frozen=True)
class RecordKind:
    name: str
    table: str
    schema_id: str
    id_field: str
    columns: Callable[[Mapping[str, Any]], dict[str, Any]]


ACCOUNT_EVENT = RecordKind(
    name="account_event",
    table="account_event",
    schema_id=schemas.ACCOUNT_EVENT,
    id_field="event_id",
    columns=_account_event_columns,
)

RECORD_KINDS: dict[str, RecordKind] = {ACCOUNT_EVENT.name: ACCOUNT_EVENT}


# --------------------------------------------------------------------------
# Canonical bytes and digests
# --------------------------------------------------------------------------

def canonical_json(document: Mapping[str, Any]) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_digest(document: Mapping[str, Any]) -> str:
    """Digest of the economic content, ignoring bookkeeping fields.

    Two rows with the same digest describe the same fact. That is a duplicate
    to warn about, not automatically an error -- buying the same size twice on
    one day is unusual but legal.
    """
    economic = {key: value for key, value in document.items() if key not in VOLATILE_FIELDS}
    payload = canonical_json(economic).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


# --------------------------------------------------------------------------
# Commit results
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DuplicateWarning:
    kind: str
    record_id: str
    digest: str
    existing_ids: tuple[str, ...]


@dataclass(frozen=True)
class CommitResult:
    written: tuple[str, ...] = ()
    duplicates: tuple[DuplicateWarning, ...] = ()


@dataclass(frozen=True)
class Write:
    kind: str
    document: Mapping[str, Any]


@dataclass
class Ledger:
    path: Path
    _root: Path | None = field(default=None, repr=False)

    # -- connection -------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None puts sqlite3 in autocommit mode so transactions
        # are opened explicitly with BEGIN IMMEDIATE. The default would emit a
        # deferred BEGIN, which upgrades to a write lock only at the first
        # write -- and can then fail with SQLITE_BUSY mid-transaction, after
        # some work is already done.
        connection = sqlite3.connect(self.path, isolation_level=None, timeout=BUSY_TIMEOUT_MS / 1000)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _write_transaction(self, connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        connection.execute("COMMIT")

    # -- migrations -------------------------------------------------------

    def migrate(self) -> int:
        with self.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version    INTEGER PRIMARY KEY,
                    name       TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied = {
                int(row["version"])
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            pending = [m for m in MIGRATIONS if m.version not in applied]
            if not pending:
                return max(applied, default=0)
            with self._write_transaction(connection):
                for migration in pending:
                    for statement in migration.statements:
                        connection.execute(statement)
                    connection.execute(
                        "INSERT INTO schema_migrations (version, name, applied_at) "
                        "VALUES (?, ?, datetime('now'))",
                        (migration.version, migration.name),
                    )
            return max(m.version for m in MIGRATIONS)

    def schema_version(self) -> int:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT MAX(version) AS version FROM schema_migrations"
            ).fetchone()
            return int(row["version"]) if row and row["version"] is not None else 0

    # -- the write gate ---------------------------------------------------

    def commit(self, writes: Sequence[Write], *, allow_duplicate: bool = False) -> CommitResult:
        """Validate and append a batch. All of it lands, or none of it does.

        Batch atomicity matters more than it looks: an opening book is many
        events describing one state, and a half-written opening book is a book
        that reconciles against nothing.
        """
        if not writes:
            return CommitResult()

        prepared: list[tuple[RecordKind, dict[str, Any], str, str]] = []
        for write in writes:
            kind = RECORD_KINDS.get(write.kind)
            if kind is None:
                raise LedgerError(f"unknown record kind: {write.kind!r}")
            document = dict(write.document)
            schemas.validate(document, kind.schema_id, self._root)
            record_id = document.get(kind.id_field)
            if not isinstance(record_id, str):
                raise LedgerError(f"{kind.name} is missing {kind.id_field}")
            prepared.append((kind, document, record_id, content_digest(document)))

        seen_ids = [record_id for _, _, record_id, _ in prepared]
        if len(set(seen_ids)) != len(seen_ids):
            raise LedgerError("the same identifier appears twice in one batch")

        duplicates: list[DuplicateWarning] = []
        written: list[str] = []

        with self.connection() as connection:
            with self._write_transaction(connection):
                for kind, document, record_id, digest in prepared:
                    existing = [
                        str(row[kind.id_field])
                        for row in connection.execute(
                            f"SELECT {kind.id_field} FROM {kind.table} WHERE content_digest = ?",  # noqa: S608
                            (digest,),
                        )
                    ]
                    if existing:
                        warning = DuplicateWarning(
                            kind=kind.name,
                            record_id=record_id,
                            digest=digest,
                            existing_ids=tuple(existing),
                        )
                        if not allow_duplicate:
                            raise LedgerError(
                                f"{kind.name} duplicates an existing record "
                                f"({', '.join(existing)}); pass allow_duplicate to record it anyway"
                            )
                        duplicates.append(warning)

                    columns = kind.columns(document)
                    columns[kind.id_field] = record_id
                    columns["content_digest"] = digest
                    columns["document"] = canonical_json(document)

                    names = ", ".join(columns)
                    placeholders = ", ".join("?" for _ in columns)
                    try:
                        connection.execute(
                            f"INSERT INTO {kind.table} ({names}) VALUES ({placeholders})",  # noqa: S608
                            tuple(columns.values()),
                        )
                    except sqlite3.IntegrityError as exc:
                        raise LedgerError(f"{kind.name} {record_id} rejected by the ledger: {exc}") from exc
                    written.append(record_id)

        return CommitResult(written=tuple(written), duplicates=tuple(duplicates))

    # -- reading ----------------------------------------------------------

    def account_events(self, *, security_id: str | None = None) -> list[dict[str, Any]]:
        """Every account event in replay order."""
        query = "SELECT document FROM account_event"
        params: tuple[Any, ...] = ()
        if security_id is not None:
            query += " WHERE security_id = ?"
            params = (security_id,)
        query += " ORDER BY effective_date, event_id"
        with self.connection() as connection:
            return [json.loads(row["document"]) for row in connection.execute(query, params)]

    def find_by_digest(self, digest: str) -> list[str]:
        with self.connection() as connection:
            return [
                str(row["event_id"])
                for row in connection.execute(
                    "SELECT event_id FROM account_event WHERE content_digest = ?", (digest,)
                )
            ]

    def count(self, table: str = "account_event") -> int:
        if table not in {kind.table for kind in RECORD_KINDS.values()}:
            raise LedgerError(f"unknown table: {table!r}")
        with self.connection() as connection:
            return int(connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])  # noqa: S608


def open_ledger(path: Path | None = None, root: Path | None = None) -> Ledger:
    resolved_root = root or schemas.repo_root()
    ledger = Ledger(path=path or resolved_root / DEFAULT_RELATIVE_PATH, _root=root)
    ledger.migrate()
    return ledger


def events_from(documents: Iterable[Mapping[str, Any]]) -> list[Write]:
    return [Write(kind=ACCOUNT_EVENT.name, document=document) for document in documents]
