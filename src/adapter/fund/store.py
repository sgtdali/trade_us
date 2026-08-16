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
from datetime import datetime, timezone
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

_MIGRATION_0002 = Migration(
    version=2,
    name="assessment and decision records",
    statements=(
        """
        CREATE TABLE assessment_record (
            assessment_id   TEXT PRIMARY KEY,
            security_id     TEXT NOT NULL,
            thesis_id       TEXT,
            as_of           TEXT NOT NULL,
            readiness       TEXT NOT NULL,
            review_due      TEXT NOT NULL,
            derived_from    TEXT REFERENCES assessment_record(assessment_id),
            content_digest  TEXT NOT NULL,
            document        TEXT NOT NULL
        )
        """,
        "CREATE INDEX assessment_by_security ON assessment_record (security_id, as_of)",
        "CREATE INDEX assessment_by_review_due ON assessment_record (review_due)",
        """
        CREATE TRIGGER assessment_immutable_update
        BEFORE UPDATE ON assessment_record
        BEGIN
            SELECT RAISE(ABORT,
                'assessment records are immutable: write a new assessment with derived_from instead');
        END
        """,
        """
        CREATE TRIGGER assessment_immutable_delete
        BEFORE DELETE ON assessment_record
        BEGIN
            SELECT RAISE(ABORT, 'assessment records cannot be deleted');
        END
        """,
        """
        CREATE TABLE decision_record (
            decision_id     TEXT PRIMARY KEY,
            as_of           TEXT NOT NULL,
            security_id     TEXT NOT NULL,
            assessment_id   TEXT REFERENCES assessment_record(assessment_id),
            action          TEXT NOT NULL,
            decision        TEXT NOT NULL,
            mode            TEXT NOT NULL,
            content_digest  TEXT NOT NULL,
            document        TEXT NOT NULL
        )
        """,
        "CREATE INDEX decision_by_security ON decision_record (security_id, as_of)",
        "CREATE INDEX decision_by_date ON decision_record (as_of)",
        """
        CREATE TRIGGER decision_immutable_update
        BEFORE UPDATE ON decision_record
        BEGIN
            SELECT RAISE(ABORT,
                'decision records are immutable: they answer what was known that day');
        END
        """,
        """
        CREATE TRIGGER decision_immutable_delete
        BEFORE DELETE ON decision_record
        BEGIN
            SELECT RAISE(ABORT, 'decision records cannot be deleted');
        END
        """,
    ),
)

_MIGRATION_0003 = Migration(
    version=3,
    name="nav snapshots",
    statements=(
        # Drawdown needs a history, and a projection cannot invent one: without
        # a price series there is no way to know what NAV was last month. So it
        # is recorded as the reviews happen, and the peak is honestly described
        # as the peak since tracking began.
        """
        CREATE TABLE nav_snapshot (
            as_of        TEXT PRIMARY KEY,
            nav          TEXT NOT NULL,
            cash         TEXT NOT NULL,
            currency     TEXT NOT NULL,
            recorded_at  TEXT NOT NULL
        )
        """,
    ),
)

_MIGRATION_0004 = Migration(
    version=4,
    name="thesis event stream",
    statements=(
        """
        CREATE TABLE thesis_event (
            thesis_event_id  TEXT PRIMARY KEY,
            thesis_id        TEXT NOT NULL,
            event_type       TEXT NOT NULL,
            effective_date   TEXT NOT NULL,
            recorded_at      TEXT NOT NULL,
            actor            TEXT NOT NULL,
            security_id      TEXT,
            content_digest   TEXT NOT NULL,
            document         TEXT NOT NULL
        )
        """,
        "CREATE INDEX thesis_event_replay ON thesis_event (thesis_id, effective_date, recorded_at)",
        "CREATE INDEX thesis_event_by_security ON thesis_event (security_id)",
        """
        CREATE TRIGGER thesis_event_immutable_update
        BEFORE UPDATE ON thesis_event
        BEGIN
            SELECT RAISE(ABORT,
                'thesis events are immutable: record another transition instead');
        END
        """,
        """
        CREATE TRIGGER thesis_event_immutable_delete
        BEFORE DELETE ON thesis_event
        BEGIN
            SELECT RAISE(ABORT, 'thesis events cannot be deleted');
        END
        """,
    ),
)

_MIGRATION_0005 = Migration(
    version=5,
    name="monitoring check records",
    statements=(
        """
        CREATE TABLE monitoring_check_record (
            check_record_id    TEXT PRIMARY KEY,
            thesis_id          TEXT NOT NULL,
            rule_id            TEXT NOT NULL,
            contract_version   INTEGER NOT NULL,
            result             TEXT NOT NULL,
            evidence_accession TEXT,
            evaluated_at       TEXT NOT NULL,
            content_digest     TEXT NOT NULL,
            document           TEXT NOT NULL
        )
        """,
        "CREATE INDEX check_by_thesis ON monitoring_check_record (thesis_id, evaluated_at)",
        "CREATE INDEX check_by_rule ON monitoring_check_record (thesis_id, rule_id, evaluated_at)",
        # One filing evaluates one rule once. Re-running the cycle over the same
        # evidence must not manufacture a second opinion about it.
        """
        CREATE UNIQUE INDEX check_once_per_evidence
            ON monitoring_check_record (thesis_id, rule_id, contract_version, evidence_accession)
            WHERE evidence_accession IS NOT NULL
        """,
        """
        CREATE TRIGGER check_record_immutable_update
        BEFORE UPDATE ON monitoring_check_record
        BEGIN
            SELECT RAISE(ABORT, 'monitoring check records are immutable');
        END
        """,
        """
        CREATE TRIGGER check_record_immutable_delete
        BEFORE DELETE ON monitoring_check_record
        BEGIN
            SELECT RAISE(ABORT, 'monitoring check records cannot be deleted');
        END
        """,
    ),
)

_MIGRATION_0006 = Migration(
    version=6,
    name="research jobs",
    statements=(
        # A job is a sequence of immutable revisions, not a row that changes.
        # Every write stays on the one commit path and the attempt history
        # cannot be quietly rewritten.
        """
        CREATE TABLE research_job (
            job_id          TEXT NOT NULL,
            revision        INTEGER NOT NULL,
            status          TEXT NOT NULL,
            dedup_key       TEXT NOT NULL,
            security_id     TEXT NOT NULL,
            thesis_id       TEXT,
            created_at      TEXT NOT NULL,
            written_at      TEXT NOT NULL,
            content_digest  TEXT NOT NULL,
            document        TEXT NOT NULL,
            PRIMARY KEY (job_id, revision)
        )
        """,
        "CREATE INDEX job_by_status ON research_job (status, created_at)",
        "CREATE INDEX job_by_thesis ON research_job (thesis_id, created_at)",
        # One dedup key opens one job, ever. Re-running the cycle over the same
        # evidence must not produce a second opinion about it.
        """
        CREATE UNIQUE INDEX job_one_per_dedup_key
            ON research_job (dedup_key) WHERE revision = 1
        """,
        """
        CREATE TRIGGER research_job_immutable_update
        BEFORE UPDATE ON research_job
        BEGIN
            SELECT RAISE(ABORT, 'job revisions are immutable: write the next revision');
        END
        """,
        """
        CREATE TRIGGER research_job_immutable_delete
        BEFORE DELETE ON research_job
        BEGIN
            SELECT RAISE(ABORT, 'job revisions cannot be deleted');
        END
        """,
    ),
)

_MIGRATION_0007 = Migration(
    version=7,
    name="observed filings",
    statements=(
        # The watermark is "the last thing I actually saw", not "the last time I
        # looked". That distinction is what lets a machine that was switched off
        # for a week catch up instead of skipping the week.
        """
        CREATE TABLE observed_filing (
            security_id   TEXT NOT NULL,
            accession     TEXT NOT NULL,
            form          TEXT NOT NULL,
            filing_date   TEXT NOT NULL,
            report_date   TEXT,
            first_seen_at TEXT NOT NULL,
            PRIMARY KEY (security_id, accession)
        )
        """,
        "CREATE INDEX observed_filing_by_date ON observed_filing (security_id, filing_date)",
    ),
)

MIGRATIONS: tuple[Migration, ...] = (
    _MIGRATION_0001, _MIGRATION_0002, _MIGRATION_0003, _MIGRATION_0004, _MIGRATION_0005,
    _MIGRATION_0006, _MIGRATION_0007,
)


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


def _assessment_columns(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "security_id": document["security_id"],
        "thesis_id": document.get("thesis_id"),
        "as_of": document["as_of"],
        "readiness": document["readiness"],
        "review_due": document["review_due"],
        "derived_from": document.get("derived_from"),
    }


def _decision_columns(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "as_of": document["as_of"],
        "security_id": document["security_id"],
        "assessment_id": document.get("assessment_id"),
        "action": document["action"],
        "decision": document["outcome"]["decision"],
        "mode": document["mode"],
    }


ACCOUNT_EVENT = RecordKind(
    name="account_event",
    table="account_event",
    schema_id=schemas.ACCOUNT_EVENT,
    id_field="event_id",
    columns=_account_event_columns,
)

ASSESSMENT_RECORD = RecordKind(
    name="assessment_record",
    table="assessment_record",
    schema_id=schemas.ASSESSMENT_RECORD,
    id_field="assessment_id",
    columns=_assessment_columns,
)

DECISION_RECORD = RecordKind(
    name="decision_record",
    table="decision_record",
    schema_id=schemas.DECISION_RECORD,
    id_field="decision_id",
    columns=_decision_columns,
)

THESIS_EVENT = RecordKind(
    name="thesis_event",
    table="thesis_event",
    schema_id=schemas.THESIS_EVENT,
    id_field="thesis_event_id",
    columns=lambda document: {
        "thesis_id": document["thesis_id"],
        "event_type": document["event_type"],
        "effective_date": document["effective_date"],
        "recorded_at": document["recorded_at"],
        "actor": document["actor"],
        "security_id": document.get("security_id"),
    },
)

MONITORING_CHECK_RECORD = RecordKind(
    name="monitoring_check_record",
    table="monitoring_check_record",
    schema_id=schemas.MONITORING_CHECK_RECORD,
    id_field="check_record_id",
    columns=lambda document: {
        "thesis_id": document["thesis_id"],
        "rule_id": document["rule_id"],
        "contract_version": document["contract_version"],
        "result": document["result"],
        "evidence_accession": document.get("evidence_accession"),
        "evaluated_at": document["evaluated_at"],
    },
)

RESEARCH_JOB = RecordKind(
    name="research_job",
    table="research_job",
    schema_id=schemas.RESEARCH_JOB_RECORD,
    id_field="job_id",
    columns=lambda document: {
        "status": document["status"],
        "dedup_key": document["dedup_key"],
        "security_id": document["security_id"],
        "thesis_id": document.get("thesis_id"),
        "created_at": document["created_at"],
    },
)

RECORD_KINDS: dict[str, RecordKind] = {
    kind.name: kind
    for kind in (ACCOUNT_EVENT, ASSESSMENT_RECORD, DECISION_RECORD, THESIS_EVENT,
                 MONITORING_CHECK_RECORD, RESEARCH_JOB)
}


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
    #: Columns the record kind cannot derive from the document alone -- the
    #: revision number of a job, for instance, which depends on what is
    #: already stored.
    extra_columns: Mapping[str, Any] | None = None


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

        prepared: list[tuple[RecordKind, dict[str, Any], str, str, Write]] = []
        for write in writes:
            kind = RECORD_KINDS.get(write.kind)
            if kind is None:
                raise LedgerError(f"unknown record kind: {write.kind!r}")
            document = dict(write.document)
            schemas.validate(document, kind.schema_id, self._root)
            record_id = document.get(kind.id_field)
            if not isinstance(record_id, str):
                raise LedgerError(f"{kind.name} is missing {kind.id_field}")
            prepared.append((kind, document, record_id, content_digest(document), write))

        seen_ids = [record_id for _, _, record_id, _, write in prepared
                    if not (write.extra_columns or {}).get("revision")]
        if len(set(seen_ids)) != len(seen_ids):
            raise LedgerError("the same identifier appears twice in one batch")

        duplicates: list[DuplicateWarning] = []
        written: list[str] = []

        with self.connection() as connection:
            with self._write_transaction(connection):
                for kind, document, record_id, digest, write in prepared:
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
                    if write.extra_columns:
                        columns.update(write.extra_columns)
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

    def assessments(self, *, security_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT document FROM assessment_record"
        params: tuple[Any, ...] = ()
        if security_id is not None:
            query += " WHERE security_id = ?"
            params = (security_id,)
        query += " ORDER BY as_of, assessment_id"
        with self.connection() as connection:
            return [json.loads(row["document"]) for row in connection.execute(query, params)]

    def assessment(self, assessment_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT document FROM assessment_record WHERE assessment_id = ?", (assessment_id,)
            ).fetchone()
        if row is None:
            raise LedgerError(f"no such assessment: {assessment_id}")
        return json.loads(row["document"])

    def latest_assessment(self, security_id: str) -> dict[str, Any] | None:
        found = self.assessments(security_id=security_id)
        return found[-1] if found else None

    def decisions(self, *, security_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT document FROM decision_record"
        params: tuple[Any, ...] = ()
        if security_id is not None:
            query += " WHERE security_id = ?"
            params = (security_id,)
        query += " ORDER BY as_of, decision_id"
        with self.connection() as connection:
            return [json.loads(row["document"]) for row in connection.execute(query, params)]

    def decision(self, decision_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT document FROM decision_record WHERE decision_id = ?", (decision_id,)
            ).fetchone()
        if row is None:
            raise LedgerError(f"no such decision: {decision_id}")
        return json.loads(row["document"])

    def record_nav(self, *, as_of: str, nav: str, cash: str, currency: str, recorded_at: str) -> None:
        """Upsert today's mark. Re-running a review must not create a second peak."""
        with self.connection() as connection:
            with self._write_transaction(connection):
                connection.execute(
                    "INSERT INTO nav_snapshot (as_of, nav, cash, currency, recorded_at) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(as_of) DO UPDATE SET nav = excluded.nav, cash = excluded.cash, "
                    "currency = excluded.currency, recorded_at = excluded.recorded_at",
                    (as_of, nav, cash, currency, recorded_at),
                )

    def nav_history(self) -> list[dict[str, str]]:
        with self.connection() as connection:
            return [
                {key: row[key] for key in row.keys()}
                for row in connection.execute(
                    "SELECT as_of, nav, cash, currency FROM nav_snapshot ORDER BY as_of"
                )
            ]

    def thesis_events(self, *, thesis_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT document FROM thesis_event"
        params: tuple[Any, ...] = ()
        if thesis_id is not None:
            query += " WHERE thesis_id = ?"
            params = (thesis_id,)
        query += " ORDER BY effective_date, recorded_at, thesis_event_id"
        with self.connection() as connection:
            return [json.loads(row["document"]) for row in connection.execute(query, params)]

    def check_records(self, *, thesis_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT document FROM monitoring_check_record"
        params: tuple[Any, ...] = ()
        if thesis_id is not None:
            query += " WHERE thesis_id = ?"
            params = (thesis_id,)
        query += " ORDER BY evaluated_at, check_record_id"
        with self.connection() as connection:
            return [json.loads(row["document"]) for row in connection.execute(query, params)]

    def save_job(self, document: Mapping[str, Any]) -> int:
        """Append the next revision of a job. Returns the revision written."""
        job_id = document["job_id"]
        with self.connection() as connection:
            row = connection.execute(
                "SELECT MAX(revision) AS revision FROM research_job WHERE job_id = ?", (job_id,)
            ).fetchone()
        revision = int(row["revision"] or 0) + 1
        self.commit(
            [Write(kind=RESEARCH_JOB.name, document=document,
                   extra_columns={"revision": revision,
                                  "written_at": datetime.now(timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ")})],
            allow_duplicate=True,
        )
        return revision

    def jobs(self, *, status: str | None = None) -> list[dict[str, Any]]:
        """The latest revision of every job."""
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT j.document FROM research_job j
                JOIN (SELECT job_id, MAX(revision) AS revision FROM research_job GROUP BY job_id) m
                  ON j.job_id = m.job_id AND j.revision = m.revision
                ORDER BY j.created_at, j.job_id
                """
            ).fetchall()
        documents = [json.loads(row["document"]) for row in rows]
        if status is not None:
            documents = [d for d in documents if d["status"] == status]
        return documents

    def job(self, job_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT document FROM research_job WHERE job_id = ? "
                "ORDER BY revision DESC LIMIT 1", (job_id,)
            ).fetchone()
        if row is None:
            raise LedgerError(f"no such job: {job_id}")
        return json.loads(row["document"])

    def job_revisions(self, job_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return [
                json.loads(row["document"])
                for row in connection.execute(
                    "SELECT document FROM research_job WHERE job_id = ? ORDER BY revision",
                    (job_id,))
            ]

    def job_for_dedup_key(self, dedup_key: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT job_id FROM research_job WHERE dedup_key = ? AND revision = 1",
                (dedup_key,)).fetchone()
        return self.job(str(row["job_id"])) if row else None

    def seen_accessions(self, security_id: str) -> set[str]:
        with self.connection() as connection:
            return {
                str(row["accession"])
                for row in connection.execute(
                    "SELECT accession FROM observed_filing WHERE security_id = ?",
                    (security_id,))
            }

    def record_observed_filings(self, observations: Sequence[Mapping[str, Any]]) -> int:
        """Mark filings as seen. Idempotent: seeing one twice records it once."""
        if not observations:
            return 0
        seen_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.connection() as connection:
            with self._write_transaction(connection):
                before = connection.execute(
                    "SELECT COUNT(*) AS n FROM observed_filing").fetchone()["n"]
                connection.executemany(
                    "INSERT OR IGNORE INTO observed_filing "
                    "(security_id, accession, form, filing_date, report_date, first_seen_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [(o["security_id"], o["accession"], o["form"], o["filing_date"],
                      o.get("report_date"), seen_at) for o in observations],
                )
                after = connection.execute(
                    "SELECT COUNT(*) AS n FROM observed_filing").fetchone()["n"]
        return int(after) - int(before)

    def observed_filings(self, security_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM observed_filing"
        params: tuple[Any, ...] = ()
        if security_id is not None:
            query += " WHERE security_id = ?"
            params = (security_id,)
        query += " ORDER BY security_id, filing_date DESC"
        with self.connection() as connection:
            return [{k: row[k] for k in row.keys()}
                    for row in connection.execute(query, params)]

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
