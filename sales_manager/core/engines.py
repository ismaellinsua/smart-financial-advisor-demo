"""The two database engines behind the store, with one interface: a local SQLite file or a PostgreSQL server.

Every transaction goes through `tx()`; cursors take `?` placeholders and return rows as dicts on both engines.
"""

import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import config
from .schema import APPEND_ONLY_MESSAGE, SCHEMA
from .security import is_safe_identifier


_WRITE_RE = re.compile(r"\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE)\b", re.IGNORECASE)
READ_TTL = 2.0  # seconds a small, often-read value (settings, locations) is reused within one server


class _ReadCache:
    """Settings and locations are read several times per click; with a remote database each read is a round trip.
    They are kept for READ_TTL seconds and dropped as soon as any transaction of this server writes anything."""

    def __init__(self):
        self._items, self._generation, self._lock = {}, 0, threading.Lock()

    def get(self, key, load):
        with self._lock:
            hit, generation = self._items.get(key), self._generation
        if hit and monotonic() - hit[0] < READ_TTL:
            return hit[1]
        value = load()
        with self._lock:
            if generation == self._generation:  # nothing was written while it loaded
                self._items[key] = (monotonic(), value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._generation += 1


class Cursor:
    """Uniform cursor: `?` placeholders and rows returned as dicts on both engines."""

    def __init__(self, cur, pyformat: bool):
        self._cur = cur
        self._pyformat = pyformat
        self.wrote = False

    def _note(self, sql: str) -> None:
        if not self.wrote and _WRITE_RE.match(sql):
            self.wrote = True

    def _sql(self, sql: str) -> str:
        return sql.replace("%", "%%").replace("?", "%s") if self._pyformat else sql

    def execute(self, sql: str, params=()):
        self._note(sql)
        self._cur.execute(self._sql(sql), tuple(params))
        return self

    def executemany(self, sql: str, seq) -> None:
        self._note(sql)
        rows = [tuple(p) for p in seq]
        if rows:
            self._cur.executemany(self._sql(sql), rows)

    @property
    def columns(self) -> list[str]:
        return [d[0] for d in self._cur.description]

    def _dict(self, row):
        if row is None or isinstance(row, dict):
            return row
        return dict(zip(self.columns, row))

    def fetchone(self):
        return self._dict(self._cur.fetchone())

    def fetchall(self) -> list[dict]:
        return [self._dict(r) for r in self._cur.fetchall()]

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    def query_rows(self, sql: str, params=()) -> tuple[list[tuple], list[str]]:
        """Plain tuples and column names, for building tables fast (no per-row dicts)."""
        if self._pyformat:
            from psycopg.rows import tuple_row

            previous, self._cur.row_factory = self._cur.row_factory, tuple_row
            try:
                self.execute(sql, params)
                return self._cur.fetchall(), self.columns
            finally:
                self._cur.row_factory = previous
        self.execute(sql, params)
        return self._cur.fetchall(), self.columns


class SQLiteEngine:
    label = "archivo local (SQLite)"
    persistent_in_cloud = False

    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.reads = _ReadCache()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()  # Streamlit serves each visitor from its own thread
        self.integrity_errors = (sqlite3.IntegrityError,)

    real = "REAL"

    def schema(self) -> str:
        return SCHEMA.format(pk="INTEGER PRIMARY KEY AUTOINCREMENT", real=self.real)

    @contextmanager
    def tx(self):
        with self._lock:
            cur = Cursor(self._conn.cursor(), pyformat=False)
            try:
                yield cur
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise
            finally:
                cur._cur.close()
                if cur.wrote:
                    self.reads.clear()

    def columns(self, cur: Cursor, table: str) -> set[str]:
        return {r["name"] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}

    def drop_day_unique(self, cur: Cursor) -> None:
        """Databases from before locations had `day UNIQUE` on cash closings; SQLite can only drop it by
        rebuilding the table (same columns and rows)."""
        sql = cur.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'cash_closings'").fetchone()
        if not sql or "day TEXT UNIQUE" not in sql["sql"]:
            return
        columns = [r["name"] for r in cur.execute("PRAGMA table_info(cash_closings)").fetchall()]
        definition = re.sub(r"\bday TEXT UNIQUE NOT NULL", "day TEXT NOT NULL", sql["sql"], count=1)
        cur.execute("ALTER TABLE cash_closings RENAME TO cash_closings_old")
        cur.execute(definition)
        cur.execute(f"INSERT INTO cash_closings({', '.join(columns)}) SELECT {', '.join(columns)} FROM cash_closings_old")
        cur.execute("DROP TABLE cash_closings_old")

    def make_append_only(self, cur: Cursor, table: str) -> None:
        """Rows of `table` can be added but never changed or deleted, not even with direct SQL."""
        for event in ("UPDATE", "DELETE"):
            cur.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{event.lower()} BEFORE {event} ON {table} "
                        f"BEGIN SELECT RAISE(ABORT, '{APPEND_ONLY_MESSAGE}'); END")

    def lock_migrations(self, cur: Cursor) -> None:
        pass  # one connection, already serialised by the store's lock

    def float_columns(self, cur: Cursor) -> list[tuple[str, str]]:
        return []  # SQLite has no exact decimal type; amounts are rounded to cents before they are written

    def before_reload(self, cur: Cursor, tables: list[str]) -> None:
        # Restart id counters; explicit ids inserted afterwards move them forward again.
        cur.execute(
            f"DELETE FROM sqlite_sequence WHERE name IN ({', '.join('?' * len(tables))})", tables
        )

    def after_reload(self, cur: Cursor, tables: list[str]) -> None:
        pass

    def close(self) -> None:
        self._conn.close()


def pool_size() -> int:
    """Connections each server keeps per database (DB_POOL_SIZE, default 5). Free plans allow few connections."""
    return config.integer("db_pool_size", low=1, high=50)


# Every user of the same database (each business's Store, the operator directory) shares one small pool.
_POOLS: dict = {}
_POOLS_LOCK = threading.Lock()


def acquire_pool(url: str):
    """(key, pool) for a PostgreSQL URL; call release_pool(key) when done with it."""
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    key = secure_url(url)
    with _POOLS_LOCK:
        entry = _POOLS.get(key)
        if entry is None:
            # Re-checks connections before use: free cloud databases (Neon) close idle connections when they
            # suspend, and the app must reconnect transparently.
            # prepare_threshold=None keeps it compatible with connection poolers (PgBouncer).
            pool = ConnectionPool(
                key,
                min_size=1,
                max_size=pool_size(),
                open=True,
                check=ConnectionPool.check_connection,
                kwargs={"row_factory": dict_row, "prepare_threshold": None, "connect_timeout": 15},
                configure=load_numbers,
            )
            try:
                pool.wait(timeout=30)
            except Exception:
                pool.close()
                raise
            entry = _POOLS[key] = [pool, 0]
        entry[1] += 1
        return key, entry[0]


def release_pool(key: str) -> None:
    with _POOLS_LOCK:
        entry = _POOLS.get(key)
        if entry is None:
            return
        entry[1] -= 1
        if entry[1] <= 0:
            del _POOLS[key]
            entry[0].close()


class PostgresEngine:
    label = "PostgreSQL en la nube"
    persistent_in_cloud = True

    def __init__(self, url: str, schema: str | None = None):
        import psycopg

        if schema is not None and not is_safe_identifier(schema):
            raise ValueError("Nombre de esquema no válido.")
        self._schema = schema
        self.reads = _ReadCache()
        self._key, self._pool = acquire_pool(url)
        self.integrity_errors = (psycopg.errors.IntegrityError,)

    # Exact decimals for every amount, rate and cost. Read back as Python floats (see load_numbers), as the
    # app has always used them, so totals summed in the database are exact and the code sees no difference.
    real = "NUMERIC(14,4)"

    def schema(self) -> str:
        return SCHEMA.format(pk="INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY", real=self.real)

    @contextmanager
    def tx(self):
        # The pool commits when the block succeeds and rolls back on any exception.
        wrapped = None
        try:
            with self._pool.connection() as conn, conn.cursor() as cur:
                if self._schema:
                    # Per transaction, so it also holds behind a transaction-pooling proxy (Neon's pooler, PgBouncer).
                    cur.execute(f'SET LOCAL search_path TO "{self._schema}"')
                wrapped = Cursor(cur, pyformat=True)
                yield wrapped
        finally:
            if wrapped is not None and wrapped.wrote:
                self.reads.clear()  # after the commit, so nobody re-reads the old values in between

    def columns(self, cur: Cursor, table: str) -> set[str]:
        rows = cur.execute(
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ?",
            (table,),
        ).fetchall()
        return {r["name"] for r in rows}

    def drop_day_unique(self, cur: Cursor) -> None:
        """Databases from before locations had `day UNIQUE` on cash closings."""
        cur.execute("ALTER TABLE cash_closings DROP CONSTRAINT IF EXISTS cash_closings_day_key")

    def make_append_only(self, cur: Cursor, table: str) -> None:
        """Rows of `table` can be added but never changed or deleted (nor truncated), not even with direct SQL."""
        if cur.execute("SELECT 1 FROM pg_trigger WHERE tgname = ? AND tgrelid = to_regclass(?)",
                       (f"{table}_no_truncate", table)).fetchone():
            return  # already in place; skip the DDL (and its table lock) on every start
        cur.execute("CREATE OR REPLACE FUNCTION append_only_guard() RETURNS trigger LANGUAGE plpgsql AS "
                    f"$$ BEGIN RAISE EXCEPTION '{APPEND_ONLY_MESSAGE}'; END $$")
        cur.execute(f"CREATE OR REPLACE TRIGGER {table}_no_change BEFORE UPDATE OR DELETE ON {table} "
                    "FOR EACH ROW EXECUTE FUNCTION append_only_guard()")
        cur.execute(f"CREATE OR REPLACE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
                    "FOR EACH STATEMENT EXECUTE FUNCTION append_only_guard()")

    def lock_migrations(self, cur: Cursor) -> None:
        # Two servers starting at once: the second waits here and then sees the first one's work recorded.
        cur.execute("LOCK TABLE schema_migrations IN SHARE ROW EXCLUSIVE MODE")

    def float_columns(self, cur: Cursor) -> list[tuple[str, str]]:
        rows = cur.execute(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = current_schema() "
            "AND data_type IN ('double precision', 'real') ORDER BY table_name, ordinal_position"
        ).fetchall()
        return [(r["table_name"], r["column_name"]) for r in rows]

    def before_reload(self, cur: Cursor, tables: list[str]) -> None:
        pass

    def after_reload(self, cur: Cursor, tables: list[str]) -> None:
        # Rows were inserted with explicit ids: move each identity past the highest one.
        for table in tables:
            if table != "settings":
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
                )

    def close(self) -> None:
        release_pool(self._key)


def load_numbers(conn) -> None:
    """NUMERIC values arrive as float (or int for whole-number aggregates such as SUM of quantities)."""
    from psycopg.adapt import Loader

    class NumberLoader(Loader):
        def load(self, data):
            text = bytes(data).decode()
            return int(text) if text.lstrip("-").isdigit() else float(text)

    conn.adapters.register_loader("numeric", NumberLoader)


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


def _root_certificates() -> str:
    """Mozilla's list of trusted certificate authorities (certifi), the same whatever OpenSSL libpq was built with."""
    try:
        import certifi
    except ImportError:  # pragma: no cover - certifi comes with Streamlit's dependencies
        return "system"
    return certifi.where()


def secure_url(url: str) -> str:
    """Remote PostgreSQL only over TLS, checking the server's certificate and name (verify-full), so nobody on the
    way can pose as the database. A URL that sets its own sslmode keeps it."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    if parts.hostname not in LOCAL_HOSTS:
        query.setdefault("sslmode", "verify-full")
        if query["sslmode"] in ("verify-ca", "verify-full"):
            query.setdefault("sslrootcert", _root_certificates())
    return urlunsplit(parts._replace(query=urlencode(query)))


def is_postgres(target) -> bool:
    return str(target).startswith(("postgresql://", "postgres://"))
