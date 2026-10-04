"""Storage for the sales manager: a local SQLite file or a PostgreSQL server (e.g. a free Neon database).

`Store(path_or_url)` picks the engine: a `postgresql://` URL uses PostgreSQL, anything else is a SQLite path.
Every public method runs in its own transaction, so the app behaves the same on both engines.
"""

import json
import random
import re
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd

from .presets import DEFAULT_SETTINGS, PAYMENT_METHODS, PRESETS
from .pricing import PROMO_KINDS, PROMO_SCOPES, apply_promotions, compute_totals, tax_breakdown
from .store_orders import OrdersMixin
from .store_purchases import PurchasesMixin
from .store_intel import IntelligenceMixin
from .store_refunds import RefundsMixin
from .store_billing import BillingMixin
from .store_sessions import SessionsMixin
from .store_privacy import PrivacyMixin
from .security import (
    DUMMY_HASH, RECOVERY_CODE_COUNT, RECOVERY_ITERATIONS, ROLE_RANK, ROLES, USERNAME_RE, check_secret_strength,
    clean_text, hash_secret, is_safe_identifier, new_recovery_code, normalize_recovery_code, verify_secret, verify_totp,
)
from . import clock

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id {pk},
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'General',
    price {real} NOT NULL CHECK (price >= 0),
    cost {real} NOT NULL DEFAULT 0 CHECK (cost >= 0),
    stock INTEGER NOT NULL DEFAULT 0,
    min_stock INTEGER NOT NULL DEFAULT 0,
    track_stock INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS customers (
    id {pk},
    name TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    tax_id TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sales (
    id {pk},
    number TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    payment_method TEXT NOT NULL,
    discount_pct {real} NOT NULL DEFAULT 0,
    tax_rate {real} NOT NULL DEFAULT 0,
    subtotal {real} NOT NULL,
    discount {real} NOT NULL,
    tax {real} NOT NULL,
    total {real} NOT NULL,
    status TEXT NOT NULL DEFAULT 'completada'
);
CREATE TABLE IF NOT EXISTS sale_items (
    id {pk},
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price {real} NOT NULL,
    unit_cost {real} NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id {pk},
    number TEXT UNIQUE NOT NULL,
    sale_id INTEGER UNIQUE NOT NULL REFERENCES sales(id),
    issued_at TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    customer_tax_id TEXT NOT NULL DEFAULT '',
    customer_address TEXT NOT NULL DEFAULT '',
    customer_email TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS appointments (
    id {pk},
    starts_at TEXT NOT NULL,
    duration_min INTEGER NOT NULL CHECK (duration_min > 0),
    customer_id INTEGER REFERENCES customers(id),
    customer_name TEXT NOT NULL DEFAULT '',
    product_id INTEGER REFERENCES products(id),
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pendiente',
    sale_id INTEGER REFERENCES sales(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cash_closings (
    id {pk},
    day TEXT UNIQUE NOT NULL,
    opening_float {real} NOT NULL DEFAULT 0,
    cash_sales {real} NOT NULL DEFAULT 0,
    expected_cash {real} NOT NULL,
    counted_cash {real} NOT NULL,
    difference {real} NOT NULL,
    total_sales {real} NOT NULL,
    sales_count INTEGER NOT NULL,
    breakdown TEXT NOT NULL DEFAULT '{{}}',
    notes TEXT NOT NULL DEFAULT '',
    closed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sale_payments (
    id {pk},
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    method TEXT NOT NULL,
    amount {real} NOT NULL,
    tendered {real} NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS promotions (
    id {pk},
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    value {real} NOT NULL DEFAULT 0,
    buy INTEGER NOT NULL DEFAULT 0,
    pay INTEGER NOT NULL DEFAULT 0,
    scope TEXT NOT NULL DEFAULT 'todo',
    target TEXT NOT NULL DEFAULT '',
    days TEXT NOT NULL DEFAULT '0123456',
    start_time TEXT NOT NULL DEFAULT '',
    end_time TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS loyalty_moves (
    id {pk},
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    sale_id INTEGER REFERENCES sales(id),
    points INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payments_sale ON sale_payments(sale_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_customer ON loyalty_moves(customer_id);
CREATE TABLE IF NOT EXISTS refunds (
    id {pk},
    number TEXT UNIQUE NOT NULL,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    created_at TEXT NOT NULL,
    user_name TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    method TEXT NOT NULL,
    base {real} NOT NULL,
    tax {real} NOT NULL,
    total {real} NOT NULL
);
CREATE TABLE IF NOT EXISTS refund_items (
    id {pk},
    refund_id INTEGER NOT NULL REFERENCES refunds(id) ON DELETE CASCADE,
    sale_item_id INTEGER NOT NULL REFERENCES sale_items(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    net_amount {real} NOT NULL,
    unit_cost {real} NOT NULL
);
CREATE TABLE IF NOT EXISTS credit_notes (
    id {pk},
    number TEXT UNIQUE NOT NULL,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    refund_id INTEGER UNIQUE NOT NULL REFERENCES refunds(id),
    issued_at TEXT NOT NULL,
    issued_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_refunds_sale ON refunds(sale_id);
CREATE TABLE IF NOT EXISTS dining_tables (
    id {pk},
    name TEXT NOT NULL,
    zone TEXT NOT NULL DEFAULT 'Sala',
    seats INTEGER NOT NULL DEFAULT 4,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
    id {pk},
    table_id INTEGER REFERENCES dining_tables(id),
    label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'abierta',
    opened_at TEXT NOT NULL,
    opened_by TEXT NOT NULL DEFAULT '',
    guests INTEGER NOT NULL DEFAULT 0,
    closed_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS order_items (
    id {pk},
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    notes TEXT NOT NULL DEFAULT '',
    added_by TEXT NOT NULL DEFAULT '',
    added_at TEXT NOT NULL,
    kitchen TEXT NOT NULL DEFAULT 'pendiente',
    sale_id INTEGER REFERENCES sales(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_one_open_per_table ON orders(table_id) WHERE status = 'abierta';
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE TABLE IF NOT EXISTS suppliers (
    id {pk},
    name TEXT NOT NULL,
    tax_id TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS recurring_expenses (
    id {pk},
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount {real} NOT NULL,
    day_of_month INTEGER NOT NULL,
    method TEXT NOT NULL DEFAULT 'Transferencia',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id {pk},
    number TEXT UNIQUE NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(id),
    status TEXT NOT NULL DEFAULT 'borrador',
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL DEFAULT '',
    received_by TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    total {real} NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS purchase_items (
    id {pk},
    po_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_cost {real} NOT NULL,
    received INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS expenses (
    id {pk},
    day TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount {real} NOT NULL,
    method TEXT NOT NULL DEFAULT 'Transferencia',
    supplier_id INTEGER REFERENCES suppliers(id),
    purchase_id INTEGER REFERENCES purchase_orders(id),
    recurring_id INTEGER REFERENCES recurring_expenses(id),
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_expenses_day ON expenses(day);
CREATE TABLE IF NOT EXISTS users (
    id {pk},
    username TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    secret_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    lockouts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT NOT NULL DEFAULT '',
    last_login TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id {pk},
    happened_at TEXT NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_happened ON audit_log(happened_at);
CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_appointments_start ON appointments(starts_at);
CREATE TABLE IF NOT EXISTS stock_moves (
    id {pk},
    product_id INTEGER NOT NULL REFERENCES products(id),
    delta INTEGER NOT NULL,
    stock_after INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    user_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stock_moves_product ON stock_moves(product_id);
CREATE TABLE IF NOT EXISTS recovery_codes (
    id {pk},
    user_id INTEGER NOT NULL REFERENCES users(id),
    code_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    used_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS counters (
    series TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id {pk},
    user_id INTEGER NOT NULL REFERENCES users(id),
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    ended_at TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS pos_carts (
    user_id INTEGER PRIMARY KEY,
    cart TEXT NOT NULL DEFAULT '{{}}',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS billing_records (
    id {pk},
    kind TEXT NOT NULL,
    invoice_type TEXT NOT NULL DEFAULT '',
    number TEXT NOT NULL,
    issued_on TEXT NOT NULL,
    issuer_tax_id TEXT NOT NULL,
    tax_total TEXT NOT NULL DEFAULT '',
    amount_total TEXT NOT NULL DEFAULT '',
    breakdown TEXT NOT NULL DEFAULT '[]',
    previous_hash TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    hash TEXT UNIQUE NOT NULL,
    source TEXT,
    source_id INTEGER
)
"""

# Columns added after the first release, applied to existing databases on start-up.
MIGRATIONS = [
    ("customers", "address", "TEXT NOT NULL DEFAULT ''"),
    # Who did it: names are stored as text so backups restore cleanly into any team.
    ("sales", "user_name", "TEXT NOT NULL DEFAULT ''"),
    ("invoices", "issued_by", "TEXT NOT NULL DEFAULT ''"),
    ("appointments", "created_by", "TEXT NOT NULL DEFAULT ''"),
    ("cash_closings", "closed_by", "TEXT NOT NULL DEFAULT ''"),
    # Promotions, loyalty and the per-line share of the final base (exact analytics with any discount).
    ("sale_items", "line_discount", "{real} NOT NULL DEFAULT 0"),
    ("sale_items", "promo_name", "TEXT NOT NULL DEFAULT ''"),
    ("sale_items", "net_amount", "{real}"),
    ("sales", "promo_discount", "{real} NOT NULL DEFAULT 0"),
    ("sales", "loyalty_discount", "{real} NOT NULL DEFAULT 0"),
    ("sales", "points_redeemed", "INTEGER NOT NULL DEFAULT 0"),
    ("sales", "points_earned", "INTEGER NOT NULL DEFAULT 0"),
    ("products", "supplier_id", "INTEGER"),
    ("sales", "voided_by", "TEXT NOT NULL DEFAULT ''"),
    ("sales", "voided_at", "TEXT"),
    # Two-step verification secret (TOTP) of administrators who turn it on.
    ("users", "totp_secret", "TEXT NOT NULL DEFAULT ''"),
    # Who authorised a manual discount above the staff limit.
    ("sales", "discount_approved_by", "TEXT NOT NULL DEFAULT ''"),
    # VAT per product (empty: the business default) and each sold or returned line's base, VAT and final price,
    # so tickets, invoices and returns break VAT down per rate. Prices include VAT (see _migrate_prices).
    ("products", "tax_rate", "{real}"),
    ("sale_items", "tax_rate", "{real}"),
    ("sale_items", "tax_amount", "{real}"),
    ("sale_items", "gross_amount", "{real}"),
    ("refund_items", "tax_rate", "{real}"),
    ("refund_items", "tax_amount", "{real}"),
    # Income tax withheld on invoices of professionals to companies (retención de IRPF).
    ("invoices", "irpf_rate", "{real} NOT NULL DEFAULT 0"),
    ("invoices", "irpf_amount", "{real} NOT NULL DEFAULT 0"),
    # Data protection: consent to marketing (and when it was given or withdrawn) and erasure.
    ("customers", "marketing_consent", "INTEGER NOT NULL DEFAULT 0"),
    ("customers", "consent_at", "TEXT NOT NULL DEFAULT ''"),
    ("customers", "anonymized_at", "TEXT NOT NULL DEFAULT ''"),
]

# An account locks for a fixed, short time after many failures. A long or growing lock would let anyone who knows a
# username keep the business out of its own till; guessing is slowed per device instead (ui/auth.py), PINs are
# long enough to make it impractical, and administrators can always get back in with a recovery code.
MAX_FAILED_LOGINS = 10
LOCKOUT_MINUTES = 15

# Insertion order respects foreign keys; deletion goes in reverse.
DATA_TABLES = ["products", "stock_moves", "customers", "sales", "sale_items", "invoices", "appointments", "cash_closings",
               "sale_payments", "promotions", "loyalty_moves", "refunds", "refund_items", "credit_notes",
               "dining_tables", "orders", "order_items", "suppliers", "recurring_expenses", "purchase_orders",
               "purchase_items", "expenses", "billing_records"]
ALL_TABLES = ["settings", *DATA_TABLES]
# Tables any backup must have; newer ones are created when an older backup is opened.
CORE_TABLES = {"settings", "products", "customers", "sales", "sale_items"}

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ventas.db"


class SaleError(Exception):
    """Raised when a sale cannot be completed (e.g. insufficient stock)."""


def _vat(value) -> float | None:
    """A product's VAT rate, or None for «the business default»."""
    if value is None or value == "" or (isinstance(value, float) and value != value):  # NaN from the editor
        return None
    rate = float(value)
    if not 0 <= rate <= 100:
        raise ValueError("El IVA debe estar entre 0 y 100 %.")
    return rate


class FiscalDataError(ValueError):
    """Raised when an operation would delete or replace real sales, invoices or cash closings."""


# Records a business must keep (invoices: 4 years for tax, 6 under the Commercial Code). Once real ones exist,
# nothing in the app may delete or replace them.
FISCAL_TABLES = ["sales", "invoices", "refunds", "credit_notes", "cash_closings", "billing_records"]
FISCAL_DATA_MESSAGE = ("Este negocio ya tiene ventas, facturas o cierres de caja reales y la ley obliga a conservarlos, "
                       "así que no se pueden borrar ni sustituir desde la app.")


# Billing records (VERI*FACTU) are append-only: the database itself refuses to change or delete them.
APPEND_ONLY_MESSAGE = "Los registros de facturación no se pueden modificar ni borrar"


class AuthError(Exception):
    """Raised when a login fails. The message is safe to show: it never reveals whether a user exists."""


# --------------------------------------------------------------------------- engines
class _Cursor:
    """Uniform cursor: `?` placeholders and rows returned as dicts on both engines."""

    def __init__(self, cur, pyformat: bool):
        self._cur = cur
        self._pyformat = pyformat

    def _sql(self, sql: str) -> str:
        return sql.replace("%", "%%").replace("?", "%s") if self._pyformat else sql

    def execute(self, sql: str, params=()):
        self._cur.execute(self._sql(sql), tuple(params))
        return self

    def executemany(self, sql: str, seq) -> None:
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


class _SQLite:
    label = "archivo local (SQLite)"
    persistent_in_cloud = False

    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
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
            cur = self._conn.cursor()
            try:
                yield _Cursor(cur, pyformat=False)
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    def columns(self, cur: _Cursor, table: str) -> set[str]:
        return {r["name"] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}

    def make_append_only(self, cur: _Cursor, table: str) -> None:
        """Rows of `table` can be added but never changed or deleted, not even with direct SQL."""
        for event in ("UPDATE", "DELETE"):
            cur.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{event.lower()} BEFORE {event} ON {table} "
                        f"BEGIN SELECT RAISE(ABORT, '{APPEND_ONLY_MESSAGE}'); END")

    def before_reload(self, cur: _Cursor, tables: list[str]) -> None:
        # Restart id counters; explicit ids inserted afterwards move them forward again.
        cur.execute(
            f"DELETE FROM sqlite_sequence WHERE name IN ({', '.join('?' * len(tables))})", tables
        )

    def after_reload(self, cur: _Cursor, tables: list[str]) -> None:
        pass

    def close(self) -> None:
        self._conn.close()


class _Postgres:
    label = "PostgreSQL en la nube"
    persistent_in_cloud = True

    def __init__(self, url: str):
        import psycopg
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        # A small pool that re-checks connections before use: free cloud databases (Neon) close idle
        # connections when they suspend, and the app must reconnect transparently.
        # prepare_threshold=None keeps it compatible with connection poolers (PgBouncer).
        self._pool = ConnectionPool(
            _secure_url(url),
            min_size=1,
            max_size=5,
            open=True,
            check=ConnectionPool.check_connection,
            kwargs={"row_factory": dict_row, "prepare_threshold": None, "connect_timeout": 15},
        )
        try:
            self._pool.wait(timeout=30)
        except Exception:
            self._pool.close()
            raise
        self.integrity_errors = (psycopg.errors.IntegrityError,)

    real = "DOUBLE PRECISION"

    def schema(self) -> str:
        return SCHEMA.format(pk="INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY", real=self.real)

    @contextmanager
    def tx(self):
        # The pool commits when the block succeeds and rolls back on any exception.
        with self._pool.connection() as conn, conn.cursor() as cur:
            yield _Cursor(cur, pyformat=True)

    def columns(self, cur: _Cursor, table: str) -> set[str]:
        rows = cur.execute(
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ?",
            (table,),
        ).fetchall()
        return {r["name"] for r in rows}

    def make_append_only(self, cur: _Cursor, table: str) -> None:
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

    def before_reload(self, cur: _Cursor, tables: list[str]) -> None:
        pass

    def after_reload(self, cur: _Cursor, tables: list[str]) -> None:
        # Rows were inserted with explicit ids: move each identity past the highest one.
        for table in tables:
            if table != "settings":
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
                )

    def close(self) -> None:
        self._pool.close()


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


def _secure_url(url: str) -> str:
    """Require TLS for any remote PostgreSQL server unless the URL already sets an sslmode."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    if parts.hostname not in LOCAL_HOSTS and "sslmode" not in query:
        query["sslmode"] = "require"
    return urlunsplit(parts._replace(query=urlencode(query)))


def _is_postgres(target) -> bool:
    return str(target).startswith(("postgresql://", "postgres://"))


# ----------------------------------------------------------------------------- store
class Store(RefundsMixin, OrdersMixin, PurchasesMixin, IntelligenceMixin, BillingMixin, SessionsMixin,
            PrivacyMixin):
    SaleError = SaleError
    def __init__(self, path=DEFAULT_DB_PATH):
        self.db = _Postgres(str(path)) if _is_postgres(path) else _SQLite(str(path))
        with self.db.tx() as cur:
            for statement in filter(str.strip, self.db.schema().split(";")):
                cur.execute(statement)
            for table, column, ddl in MIGRATIONS:
                if column not in self.db.columns(cur, table):
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl.format(real=self.db.real)}")
            self.db.make_append_only(cur, "billing_records")
            self._backfill_payments(cur)
            had_mode = "demo_mode" in self._settings(cur)
            had_gross = "prices_include_tax" in self._settings(cur)
            self._insert_default_settings(cur)
            if not had_gross:
                self._migrate_prices(cur)
            if not had_mode:
                # Databases from before this setting: only the demo generator creates purchases signed «Demo».
                demo = cur.execute("SELECT 1 FROM purchase_orders WHERE created_by = 'Demo' LIMIT 1").fetchone()
                self._save_settings(cur, {"demo_mode": "si" if demo else "no"})

    @staticmethod
    def _migrate_prices(cur: _Cursor) -> None:
        """Databases from before prices included VAT stored them without it: convert once (price × (1 + VAT))."""
        rate = float(cur.execute("SELECT value FROM settings WHERE key = 'tax_rate'").fetchone()["value"] or 0)
        rows = cur.execute("SELECT id, price FROM products").fetchall()
        cur.executemany("UPDATE products SET price = ? WHERE id = ?",
                        [(round(float(r["price"]) * (1 + rate / 100) + 1e-9, 2), r["id"]) for r in rows])
        cur.execute("UPDATE settings SET value = 'si' WHERE key = 'prices_include_tax'")

    @property
    def backend_label(self) -> str:
        return self.db.label

    @property
    def persistent_in_cloud(self) -> bool:
        return self.db.persistent_in_cloud

    def close(self) -> None:
        self.db.close()

    def _frame(self, sql: str, params=()) -> pd.DataFrame:
        with self.db.tx() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            columns = cur.columns
        return pd.DataFrame([list(r.values()) for r in rows], columns=columns)

    # ------------------------------------------------------------------ settings
    @staticmethod
    def _insert_default_settings(cur: _Cursor) -> None:
        cur.executemany(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
            DEFAULT_SETTINGS.items(),
        )

    @staticmethod
    def _settings(cur: _Cursor) -> dict:
        return {r["key"]: r["value"] for r in cur.execute("SELECT key, value FROM settings").fetchall()}

    @staticmethod
    def _save_settings(cur: _Cursor, values: dict) -> None:
        cur.executemany(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(k, str(v)) for k, v in values.items()],
        )

    def settings(self) -> dict:
        with self.db.tx() as cur:
            return self._settings(cur)

    def save_settings(self, values: dict) -> None:
        if "timezone" in values:
            clock.zone(values["timezone"])  # rejects unknown zones
        with self.db.tx() as cur:
            self._save_settings(cur, values)

    # ------------------------------------------------------------------ products
    def products(self, include_inactive: bool = False) -> pd.DataFrame:
        """Catalog. `price` includes VAT; `vat` is the rate that applies and `net_price` the price without it."""
        sql = "SELECT * FROM products"
        if not include_inactive:
            sql += " WHERE active = 1"
        df = self._frame(sql + " ORDER BY category, name")
        default = float(self.settings().get("tax_rate") or 0)
        df["vat"] = pd.to_numeric(df["tax_rate"], errors="coerce").fillna(default).astype(float)
        df["net_price"] = (df["price"].astype(float) / (1 + df["vat"] / 100)).round(4)
        return df

    def upsert_product(self, data: dict, product_id: int | None = None) -> int:
        fields = ["sku", "name", "category", "price", "cost", "stock", "min_stock", "track_stock", "active", "tax_rate"]
        if not data.get("sku") or not data.get("name"):
            raise ValueError("Código y nombre son obligatorios.")
        data = {**data, "sku": clean_text(data["sku"], "Código", "short"), "name": clean_text(data["name"], "Nombre"),
                "category": clean_text(data.get("category") or "General", "Categoría", "short")}
        # Plain Python types: pandas/numpy scalars from the editor are not understood by every driver.
        data["tax_rate"] = _vat(data.get("tax_rate"))
        values = [
            data.get(f) if isinstance(data.get(f), str) or data.get(f) is None
            else (float(data[f]) if f in ("price", "cost", "tax_rate") else int(data[f]))
            for f in fields
        ]
        try:
            with self.db.tx() as cur:
                if product_id is None:
                    row = cur.execute(
                        f"INSERT INTO products({', '.join(fields)}) VALUES ({', '.join('?' * len(fields))}) "
                        "RETURNING id",
                        values,
                    ).fetchone()
                    return row["id"]
                cur.execute(
                    f"UPDATE products SET {', '.join(f + ' = ?' for f in fields)} WHERE id = ?",
                    [*values, int(product_id)],
                )
                return int(product_id)
        except self.db.integrity_errors as exc:
            raise ValueError(f"No se pudo guardar: el código '{data['sku']}' ya existe o hay valores inválidos.") from exc

    PRODUCT_EDITABLE = ("sku", "name", "category", "price", "cost", "min_stock", "track_stock", "active", "tax_rate")

    def update_product(self, product_id: int, changes: dict) -> None:
        """Save only the fields that were edited, so a stale screen never overwrites what others changed (stock
        sold meanwhile, a price set from another device). Stock goes through `adjust_stock`."""
        changes = {k: v for k, v in changes.items() if k in self.PRODUCT_EDITABLE}
        if not changes:
            return
        if "sku" in changes or "name" in changes:
            if not str(changes.get("sku", "x")).strip() or not str(changes.get("name", "x")).strip():
                raise ValueError("Código y nombre son obligatorios.")
        cleaners = {"sku": lambda v: clean_text(v, "Código", "short"), "name": lambda v: clean_text(v, "Nombre"),
                    "category": lambda v: clean_text(v or "General", "Categoría", "short"),
                    "price": float, "cost": float, "min_stock": int, "track_stock": int, "active": int,
                    "tax_rate": _vat}
        values = {k: cleaners[k](v) for k, v in changes.items()}
        try:
            with self.db.tx() as cur:
                cur.execute(f"UPDATE products SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?",
                            [*values.values(), int(product_id)])
        except self.db.integrity_errors as exc:
            raise ValueError("No se pudo guardar: el código ya existe o hay valores inválidos.") from exc

    def adjust_stock(self, product_id: int, delta: int, reason: str = "Ajuste manual", user_name: str = "") -> int:
        """Add or remove units on top of the current stock (never a stale absolute value) and record who did it."""
        delta = int(delta)
        reason = clean_text(reason, "Motivo", "short")
        with self.db.tx() as cur:
            row = cur.execute("UPDATE products SET stock = stock + ? WHERE id = ? AND stock + ? >= 0 RETURNING stock",
                              (delta, int(product_id), delta)).fetchone()
            if row is None:
                raise ValueError("El stock no puede quedar en negativo.")
            if delta:
                cur.execute("INSERT INTO stock_moves(product_id, delta, stock_after, reason, user_name, created_at) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (int(product_id), delta, row["stock"], reason, str(user_name)[:120],
                             clock.now().isoformat(timespec="seconds")))
            return int(row["stock"])

    def stock_moves(self, limit: int = 100) -> pd.DataFrame:
        df = self._frame("SELECT m.created_at, p.sku, p.name, m.delta, m.stock_after, m.reason, m.user_name "
                         "FROM stock_moves m JOIN products p ON p.id = m.product_id ORDER BY m.id DESC LIMIT ?",
                         (int(limit),))
        df["created_at"] = pd.to_datetime(df["created_at"])
        return df

    # ----------------------------------------------------------------- customers
    def customers(self) -> pd.DataFrame:
        return self._frame("SELECT * FROM customers ORDER BY name")

    def upsert_customer(self, data: dict, customer_id: int | None = None) -> int:
        if not str(data.get("name") or "").strip():
            raise ValueError("El nombre del cliente es obligatorio.")
        limits = {"name": ("Nombre", "name"), "email": ("Email", "email"), "phone": ("Teléfono", "short"),
                  "tax_id": ("Identificación fiscal", "short"), "notes": ("Notas", "notes"),
                  "address": ("Dirección", "address")}
        fields = list(limits)
        if customer_id is not None:
            fields = [f for f in fields if f in data]  # an update only touches the fields it was given
        values = [clean_text(data.get(f), *limits[f]) for f in fields]
        with self.db.tx() as cur:
            if customer_id is None:
                row = cur.execute(
                    f"INSERT INTO customers({', '.join(fields)}, created_at) "
                    f"VALUES ({', '.join('?' * len(fields))}, ?) RETURNING id",
                    [*values, clock.now().isoformat(timespec="seconds")],
                ).fetchone()
                return row["id"]
            cur.execute(
                f"UPDATE customers SET {', '.join(f + ' = ?' for f in fields)} WHERE id = ?",
                [*values, int(customer_id)],
            )
            return int(customer_id)

    # --------------------------------------------------------------------- sales
    @staticmethod
    def _take_number(cur: _Cursor, table: str, stem: str, width: int) -> str:
        """Next correlative number of a series (e.g. `VTA-2026-`), with no gaps, no yearly limit and no clashes.

        One counter row per series is incremented inside the caller's transaction: concurrent sales wait for it
        instead of colliding, and a sale that fails gives its number back. A missing counter (new series, or data
        just restored) starts after the highest number already in `table`.
        """
        if cur.execute("SELECT value FROM counters WHERE series = ?", (stem,)).fetchone() is None:
            used = [r["number"][len(stem):] for r in cur.execute(
                f"SELECT number FROM {table} WHERE substr(number, 1, ?) = ?", (len(stem), stem)
            ).fetchall()]
            first = max((int(n) for n in used if n.isdigit()), default=0) + 1
        else:
            first = 1  # ignored: the row exists, so the conflict branch increments it
        row = cur.execute(
            "INSERT INTO counters(series, value) VALUES (?, ?) "
            "ON CONFLICT(series) DO UPDATE SET value = counters.value + 1 RETURNING value",
            (stem, first),
        ).fetchone()
        return f"{stem}{int(row['value']):0{width}d}"

    def _next_number(self, cur: _Cursor, when: datetime) -> str:
        prefix = self._settings(cur).get("invoice_prefix", "VTA").strip() or "VTA"
        return self._take_number(cur, "sales", f"{prefix}-{when.year}-", 5)

    def create_sale(
        self,
        cart: list[dict],
        payment_method: str = "Tarjeta",
        customer_id: int | None = None,
        discount_pct: float = 0.0,
        tax_rate: float | None = None,
        when: datetime | None = None,
        user_name: str = "",
        payments: list[dict] | None = None,
        redeem_points: int = 0,
        apply_promos: bool = True,
        max_discount: float | None = None,
        discount_approved_by: str = "",
    ) -> dict:
        """Register a sale atomically: prices, promotions and points, stock, payments and receipt number.

        `cart` items: {"product_id": int, "quantity": int}. Prices are read from the catalog. `payments` is an
        optional list of {"method", "amount", "tendered"} for mixed or split payments; by default the whole
        total is paid with `payment_method`.
        """
        if not cart:
            raise SaleError("El carrito está vacío.")
        when = when or clock.now()
        customer_id = None if customer_id is None else int(customer_id)
        for attempt in range(3):
            try:
                with self.db.tx() as cur:
                    sale_id = self._insert_sale(
                        cur, cart, payment_method, customer_id, float(discount_pct), tax_rate, when, user_name,
                        payments=payments, redeem_points=int(redeem_points or 0), apply_promos=apply_promos,
                        max_discount=max_discount, discount_approved_by=discount_approved_by,
                    )
                return self.sale(sale_id)
            except self.db.integrity_errors:
                # Two devices took the same receipt number at the same moment: number it again.
                if attempt == 2:
                    raise SaleError("No se pudo registrar la venta. Inténtalo de nuevo.") from None
        raise AssertionError("unreachable")

    def quote(self, cart: list[dict], customer_id: int | None = None, discount_pct: float = 0.0,
              redeem_points: int = 0, when: datetime | None = None, apply_promos: bool = True) -> dict:
        """Price a cart without saving anything: what the till shows before charging."""
        with self.db.tx() as cur:
            q = self._quote(cur, cart, float(discount_pct), None, None if customer_id is None else int(customer_id),
                            int(redeem_points or 0), when or clock.now(), apply_promos)
        return {
            "lines": [{"product_id": p["id"], "name": p["name"], **line} for p, line in q["lines"]],
            "totals": q["totals"], "tax_rate": q["tax_rate"], "points_earned": q["points_earned"],
            "points_balance": q["points_balance"], "loyalty": q["loyalty"],
        }

    def _loyalty_settings(self, settings: dict) -> dict:
        def number(key, default):
            try:
                return float(settings.get(key) or default)
            except ValueError:
                return float(default)
        return {
            "enabled": settings.get("loyalty_enabled", "si") == "si",
            "per_euro": max(0.0, number("points_per_euro", 1)),
            "value": max(0.0, number("point_value", 0.01)),
            "min_redeem": int(number("min_redeem_points", 100)),
        }

    @staticmethod
    def _points(cur, customer_id: int) -> int:
        row = cur.execute("SELECT COALESCE(SUM(points), 0) AS n FROM loyalty_moves WHERE customer_id = ?",
                          (int(customer_id),)).fetchone()
        return int(row["n"])

    def customer_points(self, customer_id: int) -> int:
        with self.db.tx() as cur:
            return self._points(cur, customer_id)

    def _quote(self, cur, cart, discount_pct, tax_rate, customer_id, redeem_points, when, apply_promos) -> dict:
        settings = self._settings(cur)
        if tax_rate is None:
            tax_rate = float(settings.get("tax_rate", 0))
        products = []
        for item in cart:
            qty = int(item["quantity"])
            if qty <= 0:
                raise SaleError("Las cantidades deben ser mayores que cero.")
            p = cur.execute(
                "SELECT * FROM products WHERE id = ? AND active = 1", (int(item["product_id"]),)
            ).fetchone()
            if p is None:
                raise SaleError("Uno de los productos ya no está disponible.")
            if p["track_stock"] and p["stock"] < qty:
                raise SaleError(f"Stock insuficiente de «{p['name']}»: quedan {p['stock']}.")
            products.append((p, qty))
        promos = cur.execute("SELECT * FROM promotions WHERE active = 1").fetchall() if apply_promos else []
        priced = apply_promotions(
            [{"product_id": p["id"], "category": p["category"], "quantity": q, "unit_price": p["price"],
              "tax_rate": p["tax_rate"] if p["tax_rate"] is not None else tax_rate}
             for p, q in products], promos, when,
        )

        loyalty = self._loyalty_settings(settings)
        enabled = loyalty["enabled"] and customer_id is not None
        balance = self._points(cur, customer_id) if customer_id is not None else 0
        if redeem_points < 0:
            raise SaleError("Los puntos a canjear no pueden ser negativos.")
        if redeem_points:
            if not enabled:
                raise SaleError("Para canjear puntos elige un cliente (y activa la fidelización).")
            if redeem_points > balance:
                raise SaleError(f"El cliente solo tiene {balance} puntos.")
            if redeem_points < loyalty["min_redeem"]:
                raise SaleError(f"Se canjean a partir de {loyalty['min_redeem']} puntos.")
        loyalty_amount = round(redeem_points * loyalty["value"], 2)
        totals = compute_totals(priced, discount_pct, tax_rate, loyalty_amount)
        if loyalty_amount and loyalty_amount - totals["loyalty_discount"] > 0.02:
            raise SaleError("Los puntos superan el importe de la venta: canjea menos puntos.")
        earned = int(totals["total"] * loyalty["per_euro"]) if enabled else 0
        return {"lines": list(zip([p for p, _ in products], priced)), "totals": totals, "tax_rate": tax_rate,
                "points_earned": earned, "points_balance": balance, "points_redeemed": redeem_points,
                "loyalty": loyalty}

    @staticmethod
    def _normalize_payments(payments, payment_method: str, total: float) -> list[dict]:
        if payments is None:
            return [{"method": payment_method, "amount": total, "tendered": 0.0}] if total > 0 else []
        clean = []
        for pay in payments:
            method, amount = str(pay.get("method") or ""), round(float(pay.get("amount") or 0), 2)
            tendered = round(float(pay.get("tendered") or 0), 2)
            if method not in PAYMENT_METHODS:
                raise SaleError(f"Forma de pago no válida: {method or '—'}.")
            if amount <= 0:
                continue
            if tendered and tendered < amount:
                raise SaleError("El efectivo entregado es menor que el importe.")
            clean.append({"method": method, "amount": amount, "tendered": tendered})
        paid = round(sum(p["amount"] for p in clean), 2)
        if abs(paid - round(total, 2)) > 0.005:
            raise SaleError(f"Los pagos suman {paid:.2f} y el total es {total:.2f}.")
        return clean

    def _insert_sale(self, cur, cart, payment_method, customer_id, discount_pct, tax_rate, when, user_name="",
                     payments=None, redeem_points=0, apply_promos=True, max_discount=None,
                     discount_approved_by="") -> int:
        if max_discount is not None and discount_pct > max_discount + 1e-9 and not discount_approved_by:
            raise SaleError(f"Un descuento de más del {max_discount:g} % necesita la autorización de un encargado.")
        q = self._quote(cur, cart, discount_pct, tax_rate, customer_id, redeem_points, when, apply_promos)
        t = q["totals"]
        pays = self._normalize_payments(payments, payment_method, t["total"])
        methods = {p["method"] for p in pays}
        label = methods.pop() if len(methods) == 1 else ("Mixto" if pays else payment_method)
        number = self._next_number(cur, when)
        row = cur.execute(
            "INSERT INTO sales(number, created_at, customer_id, payment_method, discount_pct, tax_rate, "
            "subtotal, discount, tax, total, user_name, promo_discount, loyalty_discount, points_redeemed, "
            "points_earned, discount_approved_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                number, when.isoformat(timespec="seconds"), customer_id, label,
                discount_pct, float(q["tax_rate"]), t["subtotal"], t["discount"], t["tax"], t["total"], user_name,
                t["promo_discount"], t["loyalty_discount"], q["points_redeemed"], q["points_earned"],
                str(discount_approved_by)[:120],
            ),
        ).fetchone()
        sale_id = row["id"]
        if discount_approved_by:
            self._audit(cur, user_name, "descuento_autorizado",
                        f"{discount_pct:g} % autorizado por {discount_approved_by}")
        for (p, line), net, vat, gross in zip(q["lines"], t["net_amounts"], t["tax_amounts"], t["gross_amounts"]):
            cur.execute(
                "INSERT INTO sale_items(sale_id, product_id, name, quantity, unit_price, unit_cost, line_discount, "
                "promo_name, net_amount, tax_rate, tax_amount, gross_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sale_id, p["id"], p["name"], line["quantity"], p["price"], p["cost"], line["line_discount"],
                 line["promo_name"], net, float(line["tax_rate"]), vat, gross),
            )
            if p["track_stock"]:
                # Guarded decrement: protects against concurrent sales of the last units.
                updated = cur.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                    (line["quantity"], p["id"], line["quantity"]),
                ).rowcount
                if not updated:
                    raise SaleError(f"Stock insuficiente de «{p['name']}».")
        cur.executemany("INSERT INTO sale_payments(sale_id, method, amount, tendered) VALUES (?, ?, ?, ?)",
                        [(sale_id, p["method"], p["amount"], p["tendered"]) for p in pays])
        self._register_issue(cur, "F2", number, when, t["tax"], t["total"], t["taxes"], "sale", sale_id)
        stamp = when.isoformat(timespec="seconds")
        if q["points_redeemed"]:
            cur.execute("INSERT INTO loyalty_moves(customer_id, sale_id, points, reason, created_at) "
                        "VALUES (?, ?, ?, 'canje', ?)", (customer_id, sale_id, -q["points_redeemed"], stamp))
        if q["points_earned"]:
            cur.execute("INSERT INTO loyalty_moves(customer_id, sale_id, points, reason, created_at) "
                        "VALUES (?, ?, ?, 'compra', ?)", (customer_id, sale_id, q["points_earned"], stamp))
        return sale_id

    def _backfill_payments(self, cur) -> None:
        """Sales from before mixed payments get one payment row with their single method."""
        cur.execute(
            "INSERT INTO sale_payments(sale_id, method, amount, tendered) "
            "SELECT s.id, s.payment_method, s.total, 0 FROM sales s WHERE s.total > 0 AND NOT EXISTS "
            "(SELECT 1 FROM sale_payments p WHERE p.sale_id = s.id)"
        )

    # ---------------------------------------------------------------- promotions
    def promotions(self) -> pd.DataFrame:
        return self._frame("SELECT * FROM promotions ORDER BY active DESC, name")

    def save_promotion(self, data: dict, promotion_id: int | None = None) -> int:
        name = clean_text(data.get("name"), "Nombre", required=True)
        kind, scope = data.get("kind"), data.get("scope", "todo")
        if kind not in PROMO_KINDS or scope not in PROMO_SCOPES:
            raise ValueError("Tipo o alcance de promoción no válido.")
        value, buy, pay = float(data.get("value") or 0), int(data.get("buy") or 0), int(data.get("pay") or 0)
        if kind == "porcentaje" and not 0 < value <= 100:
            raise ValueError("El descuento debe estar entre 1 y 100 %.")
        if kind == "nxm" and not (buy >= 2 and 0 <= pay < buy):
            raise ValueError("En «lleva N, paga M», N debe ser al menos 2 y M menor que N (p. ej. 3x2).")
        target = clean_text(data.get("target"), "Destino", "short")
        if scope != "todo" and not target:
            raise ValueError("Elige la categoría o el producto al que se aplica.")
        days = "".join(sorted({d for d in str(data.get("days") or "") if d in "0123456"}))
        if not days:
            raise ValueError("Elige al menos un día de la semana.")
        start, end = str(data.get("start_time") or ""), str(data.get("end_time") or "")
        for t in (start, end):
            if t and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
                raise ValueError("Las horas deben tener el formato HH:MM.")
        if bool(start) != bool(end) or (start and start == end):
            raise ValueError("Indica hora de inicio y de fin distintas, o deja ambas vacías para todo el día.")
        values = (name, kind, value, buy, pay, scope, target if scope != "todo" else "", days, start, end,
                  int(bool(data.get("active", 1))))
        fields = "name, kind, value, buy, pay, scope, target, days, start_time, end_time, active"
        with self.db.tx() as cur:
            if promotion_id is None:
                return cur.execute(f"INSERT INTO promotions({fields}) VALUES ({', '.join('?' * 11)}) RETURNING id",
                                   values).fetchone()["id"]
            cur.execute(f"UPDATE promotions SET {', '.join(f + ' = ?' for f in fields.split(', '))} WHERE id = ?",
                        (*values, int(promotion_id)))
            return int(promotion_id)

    def set_promotion_active(self, promotion_id: int, active: bool) -> None:
        with self.db.tx() as cur:
            cur.execute("UPDATE promotions SET active = ? WHERE id = ?", (int(active), int(promotion_id)))

    def delete_promotion(self, promotion_id: int) -> None:
        with self.db.tx() as cur:
            cur.execute("DELETE FROM promotions WHERE id = ?", (int(promotion_id),))

    def points_by_customer(self) -> pd.DataFrame:
        df = self._frame("SELECT customer_id, COALESCE(SUM(points), 0) AS points FROM loyalty_moves GROUP BY customer_id")
        df["points"] = df["points"].astype(int) if not df.empty else df["points"]
        return df

    def cancel_sale(self, sale_id: int, by: str = "", when: datetime | None = None) -> None:
        """Void a sale and return its units to stock. Sales are never deleted, to keep numbering intact."""
        sale_id = int(sale_id)
        stamp = (when or clock.now()).isoformat(timespec="seconds")
        with self.db.tx() as cur:
            sale = cur.execute("SELECT status FROM sales WHERE id = ?", (sale_id,)).fetchone()
            if sale is None or sale["status"] == "anulada":
                raise SaleError("La venta no existe o ya está anulada.")
            if cur.execute("SELECT id FROM refunds WHERE sale_id = ?", (sale_id,)).fetchone():
                raise SaleError("Esta venta tiene devoluciones: usa «Devolver» para el resto de unidades.")
            invoice = cur.execute("SELECT number FROM invoices WHERE sale_id = ?", (sale_id,)).fetchone()
            if invoice:
                raise SaleError(
                    f"Esta venta tiene la factura {invoice['number']}. Una venta facturada no se puede anular "
                    "aquí: hay que emitir una factura rectificativa."
                )
            items = cur.execute("SELECT product_id, quantity FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall()
            for item in items:
                cur.execute(
                    "UPDATE products SET stock = stock + ? WHERE id = ? AND track_stock = 1",
                    (item["quantity"], item["product_id"]),
                )
            cur.execute("UPDATE sales SET status = 'anulada', voided_by = ?, voided_at = ? WHERE id = ?",
                        (by, stamp, sale_id))
            self._register_cancellation(cur, "sale", sale_id)
            # Undo the points this sale earned or spent.
            moves = cur.execute("SELECT customer_id, SUM(points) AS n FROM loyalty_moves WHERE sale_id = ? "
                                "GROUP BY customer_id", (sale_id,)).fetchall()
            for m in moves:
                if m["n"]:
                    cur.execute("INSERT INTO loyalty_moves(customer_id, sale_id, points, reason, created_at) "
                                "VALUES (?, ?, ?, 'anulación', ?)",
                                (m["customer_id"], sale_id, -int(m["n"]), stamp))

    def sale(self, sale_id: int) -> dict:
        sale_id = int(sale_id)
        with self.db.tx() as cur:
            row = cur.execute(
                "SELECT s.*, c.name AS customer_name, c.email AS customer_email, c.tax_id AS customer_tax_id, "
                "c.phone AS customer_phone "
                "FROM sales s LEFT JOIN customers c ON c.id = s.customer_id WHERE s.id = ?",
                (sale_id,),
            ).fetchone()
            if row is None:
                raise SaleError("Venta no encontrada.")
            items = cur.execute("SELECT * FROM sale_items WHERE sale_id = ? ORDER BY id", (sale_id,)).fetchall()
            payments = cur.execute("SELECT method, amount, tendered FROM sale_payments WHERE sale_id = ? ORDER BY id",
                                   (sale_id,)).fetchall()
            billing = self._billing_record(cur, "sale", sale_id)
        return {**row, "items": items, "payments": payments, "taxes": tax_breakdown(items, row["tax_rate"]),
                "billing": billing}

    def sales(self, start: datetime | None = None, end: datetime | None = None, include_cancelled=True) -> pd.DataFrame:
        sql = (
            "SELECT s.*, COALESCE(c.name, 'Cliente general') AS customer_name "
            "FROM sales s LEFT JOIN customers c ON c.id = s.customer_id WHERE 1 = 1"
        )
        params: list = []
        if start:
            sql += " AND s.created_at >= ?"
            params.append(start.isoformat(timespec="seconds"))
        if end:
            sql += " AND s.created_at < ?"
            params.append(end.isoformat(timespec="seconds"))
        if not include_cancelled:
            sql += " AND s.status = 'completada'"
        df = self._frame(sql + " ORDER BY s.created_at DESC", params)
        df["created_at"] = pd.to_datetime(df["created_at"])
        money = ["subtotal", "discount", "tax", "total", "discount_pct", "tax_rate"]
        df[money] = df[money].astype(float)
        return df

    def sale_lines(self, start: datetime | None = None, end: datetime | None = None) -> pd.DataFrame:
        """Line-level data of completed sales, with margin, for analytics. Returns appear as negative lines on
        the day they happened, so revenue, margins and demand are always net of returns."""
        def window(column: str) -> tuple[str, list]:
            sql, params = "", []
            if start:
                sql += f" AND {column} >= ?"
                params.append(start.isoformat(timespec="seconds"))
            if end:
                sql += f" AND {column} < ?"
                params.append(end.isoformat(timespec="seconds"))
            return sql, params

        sold_where, sold_params = window("s.created_at")
        back_where, back_params = window("r.created_at")
        sql = (
            "SELECT i.sale_id, i.product_id, i.name, i.quantity, i.unit_price, i.unit_cost, s.created_at, "
            "s.customer_id, s.discount_pct, p.category, "
            "COALESCE(i.net_amount, i.quantity * i.unit_price * (1 - s.discount_pct / 100.0)) AS revenue, "
            "i.quantity * i.unit_cost AS cost "
            "FROM sale_items i JOIN sales s ON s.id = i.sale_id "
            "JOIN products p ON p.id = i.product_id WHERE s.status = 'completada'" + sold_where +
            " UNION ALL "
            "SELECT r.sale_id, ri.product_id, ri.name, -ri.quantity, 0, ri.unit_cost, r.created_at, "
            "s.customer_id, 0, p.category, -ri.net_amount, -(ri.quantity * ri.unit_cost) "
            "FROM refund_items ri JOIN refunds r ON r.id = ri.refund_id JOIN sales s ON s.id = r.sale_id "
            "JOIN products p ON p.id = ri.product_id WHERE 1 = 1" + back_where
        )
        df = self._frame(sql, [*sold_params, *back_params])
        df["created_at"] = pd.to_datetime(df["created_at"])
        # An empty result comes back with object columns; keep numeric types so analytics work with no sales.
        numeric = ["quantity", "unit_price", "unit_cost", "discount_pct", "revenue", "cost"]
        df[numeric] = df[numeric].astype(float)
        df["margin"] = df["revenue"] - df["cost"]
        return df

    # ------------------------------------------------------------------ invoices
    def _next_invoice_number(self, cur: _Cursor, when: datetime) -> str:
        series = (self._settings(cur).get("invoice_series") or "FAC").strip() or "FAC"
        return self._take_number(cur, "invoices", f"{series}-{when.year}-", 4)

    def invoice_for_sale(self, sale_id: int) -> dict | None:
        with self.db.tx() as cur:
            return cur.execute("SELECT * FROM invoices WHERE sale_id = ?", (int(sale_id),)).fetchone()

    IRPF_RATES = (0.0, 7.0, 15.0, 19.0)

    def create_invoice(self, sale_id: int, customer: dict, when: datetime | None = None, issued_by: str = "",
                       irpf_rate: float = 0.0) -> dict:
        """Issue a full invoice for a completed sale. Invoices have their own correlative series per year.

        `irpf_rate` is the income tax a company withholds from a professional's invoice (7 % or 15 % usually);
        it is applied to the taxable base and shown as «Retención IRPF», lowering what the customer pays."""
        settings = self.settings()
        if not settings.get("tax_id", "").strip() or not settings.get("address", "").strip():
            raise ValueError("Para emitir facturas, completa primero tu NIF y tu dirección en Configuración: "
                             "son obligatorios en toda factura.")
        irpf_rate = float(irpf_rate or 0)
        if irpf_rate not in self.IRPF_RATES:
            raise ValueError("Retención de IRPF no válida.")
        name = clean_text(customer.get("name"), "Nombre", "name")
        tax_id = clean_text(customer.get("tax_id"), "NIF/CIF", "short")
        if not name or not tax_id:
            raise ValueError("Para emitir una factura hacen falta el nombre y el NIF/CIF del cliente.")
        address = clean_text(customer.get("address"), "Dirección", "address")
        email = clean_text(customer.get("email"), "Email", "email")
        when = when or clock.now()
        sale_id = int(sale_id)
        for attempt in range(3):
            try:
                with self.db.tx() as cur:
                    sale = cur.execute("SELECT status, customer_id, tax, total FROM sales WHERE id = ?",
                                       (sale_id,)).fetchone()
                    if sale is None or sale["status"] != "completada":
                        raise SaleError("Solo se pueden facturar ventas completadas.")
                    if cur.execute("SELECT id FROM invoices WHERE sale_id = ?", (sale_id,)).fetchone():
                        raise SaleError("Esta venta ya tiene factura.")
                    base = cur.execute("SELECT COALESCE(SUM(net_amount), 0) AS b FROM sale_items WHERE sale_id = ?",
                                       (sale_id,)).fetchone()["b"]
                    irpf_amount = round(float(base) * irpf_rate / 100 + 1e-9, 2)
                    number = self._next_invoice_number(cur, when)
                    row = cur.execute(
                        "INSERT INTO invoices(number, sale_id, issued_at, customer_name, customer_tax_id, "
                        "customer_address, customer_email, issued_by, irpf_rate, irpf_amount) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                        (number, sale_id, when.isoformat(timespec="seconds"),
                         name, tax_id, address, email, issued_by, irpf_rate, irpf_amount),
                    ).fetchone()
                    # The full invoice replaces the simplified one (ticket) the customer already had.
                    self._register_issue(cur, "F3", number, when, sale["tax"], sale["total"],
                                         self._sale_breakdown(cur, sale_id), "invoice", row["id"])
                    if sale["customer_id"] is not None:
                        # Remember the fiscal data on the customer, without overwriting what is already there.
                        cur.execute(
                            "UPDATE customers SET tax_id = CASE WHEN tax_id = '' THEN ? ELSE tax_id END, "
                            "address = CASE WHEN address = '' THEN ? ELSE address END WHERE id = ?",
                            (tax_id, address, sale["customer_id"]),
                        )
                return self.invoice(row["id"])
            except self.db.integrity_errors:
                if attempt == 2:
                    raise SaleError("No se pudo emitir la factura. Inténtalo de nuevo.") from None
        raise AssertionError("unreachable")

    def invoice(self, invoice_id: int) -> dict:
        with self.db.tx() as cur:
            row = cur.execute("SELECT * FROM invoices WHERE id = ?", (int(invoice_id),)).fetchone()
            billing = self._billing_record(cur, "invoice", invoice_id) if row else None
        if row is None:
            raise SaleError("Factura no encontrada.")
        return {**row, "sale": self.sale(row["sale_id"]), "billing": billing}

    def invoices(self) -> pd.DataFrame:
        df = self._frame(
            "SELECT i.id, i.number, i.issued_at, i.customer_name, i.customer_tax_id, s.number AS sale_number, "
            "s.total FROM invoices i JOIN sales s ON s.id = i.sale_id ORDER BY i.id DESC"
        )
        df["issued_at"] = pd.to_datetime(df["issued_at"])
        df["total"] = df["total"].astype(float)
        return df

    # -------------------------------------------------------------- appointments
    def appointments(self, start: datetime, end: datetime) -> pd.DataFrame:
        df = self._frame(
            "SELECT a.*, COALESCE(c.name, a.customer_name) AS who, c.phone AS customer_phone, "
            "p.name AS service, p.price AS price "
            "FROM appointments a LEFT JOIN customers c ON c.id = a.customer_id "
            "LEFT JOIN products p ON p.id = a.product_id "
            "WHERE a.starts_at >= ? AND a.starts_at < ? ORDER BY a.starts_at",
            (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
        )
        df["starts_at"] = pd.to_datetime(df["starts_at"])
        return df

    def create_appointment(
        self,
        starts_at: datetime,
        duration_min: int,
        product_id: int | None = None,
        customer_id: int | None = None,
        customer_name: str = "",
        notes: str = "",
        allow_overlap: bool = False,
        created_by: str = "",
    ) -> int:
        duration_min = int(duration_min)
        if not 0 < duration_min <= 24 * 60:
            raise ValueError("La duración debe estar entre 1 minuto y 24 horas.")
        customer_name = clean_text(customer_name, "Cliente", "name")
        notes = clean_text(notes, "Notas", "notes")
        if customer_id is None and not customer_name:
            raise ValueError("Indica el cliente de la cita.")
        starts_at = starts_at.replace(second=0, microsecond=0)
        ends_at = starts_at + timedelta(minutes=duration_min)
        with self.db.tx() as cur:
            # Look at the same day only; a single agenda cannot hold two appointments at once.
            day_start = starts_at.replace(hour=0, minute=0)
            others = cur.execute(
                "SELECT a.starts_at, a.duration_min, COALESCE(c.name, a.customer_name) AS who "
                "FROM appointments a LEFT JOIN customers c ON c.id = a.customer_id "
                "WHERE a.starts_at >= ? AND a.starts_at < ? AND a.status IN ('pendiente', 'completada')",
                (day_start.isoformat(timespec="seconds"), (day_start + timedelta(days=1)).isoformat(timespec="seconds")),
            ).fetchall()
            for o in [] if allow_overlap else others:
                o_start = datetime.fromisoformat(o["starts_at"])
                o_end = o_start + timedelta(minutes=o["duration_min"])
                if starts_at < o_end and o_start < ends_at:
                    raise ValueError(
                        f"Ese hueco se solapa con la cita de {o['who']} "
                        f"({o_start:%H:%M}–{o_end:%H:%M}). Elige otra hora."
                    )
            row = cur.execute(
                "INSERT INTO appointments(starts_at, duration_min, customer_id, customer_name, product_id, notes, "
                "created_at, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (starts_at.isoformat(timespec="seconds"), duration_min,
                 None if customer_id is None else int(customer_id), customer_name,
                 None if product_id is None else int(product_id), notes,
                 clock.now().isoformat(timespec="seconds"), created_by),
            ).fetchone()
            return row["id"]

    APPOINTMENT_STATUSES = ("pendiente", "completada", "cancelada", "no_presentado")

    def set_appointment_status(self, appointment_id: int, status: str) -> None:
        if status not in self.APPOINTMENT_STATUSES:
            raise ValueError("Estado de cita no válido.")
        with self.db.tx() as cur:
            appt = cur.execute("SELECT sale_id FROM appointments WHERE id = ?", (int(appointment_id),)).fetchone()
            if appt is None:
                raise ValueError("Cita no encontrada.")
            if appt["sale_id"] is not None:
                raise ValueError("Esta cita ya está cobrada.")
            cur.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, int(appointment_id)))

    def charge_appointment(
        self, appointment_id: int, payment_method: str, discount_pct: float = 0.0, user_name: str = ""
    ) -> dict:
        """Charge an appointment's service: registers the sale and marks the appointment as done, atomically."""
        appointment_id = int(appointment_id)
        for attempt in range(3):
            try:
                with self.db.tx() as cur:
                    appt = cur.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
                    if appt is None or appt["status"] != "pendiente":
                        raise SaleError("Solo se pueden cobrar citas pendientes.")
                    if appt["product_id"] is None:
                        raise SaleError("La cita no tiene servicio asociado: cóbrala desde Vender.")
                    sale_id = self._insert_sale(
                        cur, [{"product_id": appt["product_id"], "quantity": 1}], payment_method,
                        appt["customer_id"], float(discount_pct), None, clock.now(), user_name,
                    )
                    cur.execute(
                        "UPDATE appointments SET status = 'completada', sale_id = ? WHERE id = ?",
                        (sale_id, appointment_id),
                    )
                return self.sale(sale_id)
            except self.db.integrity_errors:
                if attempt == 2:
                    raise SaleError("No se pudo cobrar la cita. Inténtalo de nuevo.") from None
        raise AssertionError("unreachable")

    # -------------------------------------------------------------- cash closing
    def day_summary(self, day: date) -> dict:
        """Completed sales of one day, broken down by how they were paid (mixed payments split per method)."""
        start = datetime.combine(day, time.min)
        with self.db.tx() as cur:
            rows = cur.execute(
                "SELECT s.id, s.status, p.method, p.amount FROM sales s LEFT JOIN sale_payments p ON p.sale_id = s.id "
                "WHERE s.created_at >= ? AND s.created_at < ?",
                (start.isoformat(timespec="seconds"), (start + timedelta(days=1)).isoformat(timespec="seconds")),
            ).fetchall()
        breakdown: dict[str, dict] = {}
        completed, cancelled = set(), set()
        for r in rows:
            if r["status"] != "completada":
                cancelled.add(r["id"])
                continue
            completed.add(r["id"])
            if r["method"] is None:
                continue
            entry = breakdown.setdefault(r["method"], {"count": 0, "total": 0.0})
            entry["count"] += 1
            entry["total"] = round(entry["total"] + float(r["amount"]), 2)
        refunds = self.refunds_by_method(day)
        for method, amount in refunds.items():
            entry = breakdown.setdefault(method, {"count": 0, "total": 0.0})
            entry["refunded"] = amount
            entry["total"] = round(entry["total"] - amount, 2)  # net of what was handed back
        return {
            "breakdown": breakdown,
            "count": len(completed),
            "total": round(sum(e["total"] for e in breakdown.values()), 2),
            "cash": breakdown.get("Efectivo", {}).get("total", 0.0),
            "cancelled": len(cancelled),
            "refunded": round(sum(refunds.values()), 2),
        }

    def close_cash(
        self, day: date, opening_float: float, counted_cash: float, notes: str = "", when: datetime | None = None,
        closed_by: str = "",
    ) -> dict:
        """Record the end-of-day cash count. Expected cash = opening float + cash sales of the day."""
        if opening_float < 0 or counted_cash < 0:
            raise ValueError("Los importes no pueden ser negativos.")
        notes = clean_text(notes, "Notas", "notes")
        summary = self.day_summary(day)
        expected = round(float(opening_float) + summary["cash"], 2)
        try:
            with self.db.tx() as cur:
                cur.execute(
                    "INSERT INTO cash_closings(day, opening_float, cash_sales, expected_cash, counted_cash, "
                    "difference, total_sales, sales_count, breakdown, notes, closed_at, closed_by) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (day.isoformat(), float(opening_float), summary["cash"], expected, float(counted_cash),
                     round(float(counted_cash) - expected, 2), summary["total"], summary["count"],
                     json.dumps(summary["breakdown"], ensure_ascii=False), notes,
                     (when or clock.now()).isoformat(timespec="seconds"), closed_by),
                )
        except self.db.integrity_errors as exc:
            raise ValueError("La caja de ese día ya está cerrada. Reábrela si necesitas repetir el cierre.") from exc
        return self.cash_closing(day)

    def cash_closing(self, day: date) -> dict | None:
        with self.db.tx() as cur:
            row = cur.execute("SELECT * FROM cash_closings WHERE day = ?", (day.isoformat(),)).fetchone()
        if row:
            row = {**row, "breakdown": json.loads(row["breakdown"] or "{}")}
        return row

    def reopen_cash(self, day: date) -> None:
        with self.db.tx() as cur:
            cur.execute("DELETE FROM cash_closings WHERE day = ?", (day.isoformat(),))

    def cash_closings(self) -> pd.DataFrame:
        df = self._frame(
            "SELECT day, total_sales, sales_count, expected_cash, counted_cash, difference, closed_at "
            "FROM cash_closings ORDER BY day DESC"
        )
        for col in ("total_sales", "expected_cash", "counted_cash", "difference"):
            df[col] = df[col].astype(float)
        return df

    # --------------------------------------------------------------------- users
    # Users and the audit log are never part of backups or templates: credentials stay on the server.
    _USER_FIELDS = ("id, username, name, role, active, last_login, created_at, "
                    "CASE WHEN totp_secret <> '' THEN 1 ELSE 0 END AS two_factor")

    def has_users(self) -> bool:
        with self.db.tx() as cur:
            return cur.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] > 0

    def users(self) -> pd.DataFrame:
        return self._frame(f"SELECT {self._USER_FIELDS} FROM users ORDER BY active DESC, name")

    def user(self, user_id: int) -> dict | None:
        with self.db.tx() as cur:
            return cur.execute(f"SELECT {self._USER_FIELDS} FROM users WHERE id = ?", (int(user_id),)).fetchone()

    def create_user(self, name: str, username: str, role: str, secret: str, by: str = "") -> int:
        name = clean_text(name, "Nombre", required=True)
        username = str(username or "").strip().lower()
        if not USERNAME_RE.fullmatch(username):
            raise ValueError("El usuario debe tener de 3 a 30 caracteres: letras minúsculas, números, punto, guion "
                             "o guion bajo.")
        if role not in ROLES:
            raise ValueError("Rol no válido.")
        check_secret_strength(secret, role)
        try:
            with self.db.tx() as cur:
                row = cur.execute(
                    "INSERT INTO users(username, name, role, secret_hash, created_at) VALUES (?, ?, ?, ?, ?) "
                    "RETURNING id",
                    (username, name, role, hash_secret(secret), clock.now().isoformat(timespec="seconds")),
                ).fetchone()
                self._audit(cur, by or username, "usuario_creado", f"{username} ({ROLES[role]})")
                return row["id"]
        except self.db.integrity_errors as exc:
            raise ValueError(f"Ya existe un usuario «{username}».") from exc

    def _active_admins(self, cur) -> int:
        return cur.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND active = 1").fetchone()["n"]

    def update_user(self, user_id: int, *, name: str | None = None, role: str | None = None,
                    active: bool | None = None, by: str = "") -> None:
        user_id = int(user_id)
        with self.db.tx() as cur:
            user = cur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if user is None:
                raise ValueError("Usuario no encontrado.")
            new_role = role if role is not None else user["role"]
            new_active = int(active) if active is not None else user["active"]
            if new_role not in ROLES:
                raise ValueError("Rol no válido.")
            losing_admin = user["role"] == "admin" and user["active"] and (new_role != "admin" or not new_active)
            if losing_admin and self._active_admins(cur) <= 1:
                raise ValueError("Debe quedar al menos un administrador activo.")
            new_name = clean_text(name, "Nombre", required=True) if name is not None else user["name"]
            cur.execute("UPDATE users SET name = ?, role = ?, active = ? WHERE id = ?",
                        (new_name, new_role, new_active, user_id))
            if not new_active:
                self._end_user_sessions(cur, user_id)
            self._audit(cur, by, "usuario_modificado",
                        f"{user['username']}: rol {ROLES[new_role]}, {'activo' if new_active else 'desactivado'}")

    def set_user_secret(self, user_id: int, secret: str, by: str = "") -> None:
        with self.db.tx() as cur:
            user = cur.execute("SELECT username, role FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if user is None:
                raise ValueError("Usuario no encontrado.")
            check_secret_strength(secret, user["role"])
            cur.execute("UPDATE users SET secret_hash = ?, failed_attempts = 0, lockouts = 0, locked_until = '' "
                        "WHERE id = ?",
                        (hash_secret(secret), int(user_id)))
            self._end_user_sessions(cur, user_id)
            self._audit(cur, by, "contraseña_cambiada", user["username"])

    def authorize(self, username: str, secret: str, needed: str = "encargado", otp: str = "",
                  purpose: str = "") -> dict:
        """A manager confirms an action at someone else's till. Same checks, lockout and log as a login."""
        user = self.authenticate(username, secret, otp=otp, purpose=purpose or "autorización")
        if not self.can(user["role"], needed):
            raise AuthError("Esa persona no puede autorizarlo: hace falta un encargado o el administrador.")
        return user

    def authenticate(self, username: str, secret: str, now: datetime | None = None, otp: str = "",
                     purpose: str = "") -> dict:
        """Check a login (and the two-step code when the account has it). Locks the account briefly after many
        failures. The error never says which part was wrong, nor whether the user exists."""
        now = now or clock.now()
        username = str(username or "").strip().lower()
        generic = AuthError("Usuario, contraseña o código incorrectos.")
        locked = ""
        with self.db.tx() as cur:
            user = cur.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if user is None or not user["active"]:
                verify_secret(secret, DUMMY_HASH)  # same work as a real check: no hints from timing
                self._audit(cur, username, "acceso_fallido", "usuario inexistente o desactivado")
                user = None
            if user is None:
                pass  # the failed attempt is recorded; raise once the transaction has committed
            elif user["locked_until"] and datetime.fromisoformat(user["locked_until"]) > now:
                minutes = max(1, round((datetime.fromisoformat(user["locked_until"]) - now).total_seconds() / 60))
                raise AuthError(f"Demasiados intentos fallidos. Vuelve a intentarlo en {minutes} min. Si eres el "
                                "administrador, puedes entrar con un código de recuperación.")
            elif verify_secret(secret, user["secret_hash"]) and (
                    not user["totp_secret"] or verify_totp(user["totp_secret"], otp)):
                if purpose:  # an authorisation, not a sign-in
                    cur.execute("UPDATE users SET failed_attempts = 0, locked_until = '' WHERE id = ?", (user["id"],))
                    self._audit(cur, username, "autorizacion", purpose)
                else:
                    cur.execute("UPDATE users SET failed_attempts = 0, lockouts = 0, locked_until = '', last_login = ? "
                                "WHERE id = ?", (now.isoformat(timespec="seconds"), user["id"]))
                    self._audit(cur, username, "acceso", "")
                return {k: user[k] for k in ("id", "username", "name", "role")}
            else:
                failed = user["failed_attempts"] + 1
                if failed >= MAX_FAILED_LOGINS:
                    locked = (now + timedelta(minutes=LOCKOUT_MINUTES)).isoformat(timespec="seconds")
                    failed = 0
                cur.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                            (failed, locked, user["id"]))
                self._audit(cur, username, "acceso_fallido", "cuenta bloqueada" if locked else f"intento {failed}")
        if locked:
            raise AuthError(f"Demasiados intentos fallidos. Cuenta bloqueada {LOCKOUT_MINUTES} minutos.")
        raise generic

    def change_own_secret(self, user_id: int, current: str, new: str) -> None:
        """A person changes their own PIN or password, proving they know the current one."""
        with self.db.tx() as cur:
            user = cur.execute("SELECT username, role, secret_hash FROM users WHERE id = ? AND active = 1",
                               (int(user_id),)).fetchone()
            if user is None or not verify_secret(current, user["secret_hash"]):
                raise ValueError("El PIN o contraseña actual no es correcto.")
            if verify_secret(new, user["secret_hash"]):
                raise ValueError("El nuevo PIN o contraseña debe ser distinto del actual.")
            check_secret_strength(new, user["role"])
            cur.execute("UPDATE users SET secret_hash = ? WHERE id = ?", (hash_secret(new), int(user_id)))
            self._end_user_sessions(cur, user_id)  # other devices must sign in again with the new one
            self._audit(cur, user["username"], "contraseña_cambiada", "por la propia persona")

    # ------------------------------------------------- administrator recovery codes
    def create_recovery_codes(self, user_id: int, by: str = "") -> list[str]:
        """New single-use codes for an administrator; the previous unused ones stop working. Shown only once."""
        codes = [new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        stamp = clock.now().isoformat(timespec="seconds")
        with self.db.tx() as cur:
            user = cur.execute("SELECT username, role FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if user is None or user["role"] != "admin":
                raise ValueError("Solo los administradores tienen códigos de recuperación.")
            cur.execute("DELETE FROM recovery_codes WHERE user_id = ? AND used_at = ''", (int(user_id),))
            cur.executemany("INSERT INTO recovery_codes(user_id, code_hash, created_at) VALUES (?, ?, ?)",
                            [(int(user_id), hash_secret(normalize_recovery_code(c), RECOVERY_ITERATIONS), stamp)
                             for c in codes])
            self._audit(cur, by or user["username"], "codigos_recuperacion_generados", user["username"])
        return codes

    def recovery_codes_left(self, user_id: int) -> int:
        with self.db.tx() as cur:
            return int(cur.execute("SELECT COUNT(*) AS n FROM recovery_codes WHERE user_id = ? AND used_at = ''",
                                   (int(user_id),)).fetchone()["n"])

    def recover_with_code(self, username: str, code: str, new_secret: str) -> dict:
        """An administrator who forgot the password, lost the phone or is locked out sets a new password with one
        of their recovery codes. It also unlocks the account and turns two-step verification off (set it up again).
        """
        username = str(username or "").strip().lower()
        code = normalize_recovery_code(code)
        generic = AuthError("Usuario o código de recuperación incorrectos.")
        with self.db.tx() as cur:
            user = cur.execute("SELECT * FROM users WHERE username = ? AND active = 1 AND role = 'admin'",
                               (username,)).fetchone()
            rows = [] if user is None else cur.execute(
                "SELECT id, code_hash FROM recovery_codes WHERE user_id = ? AND used_at = ''", (user["id"],)).fetchall()
            match = next((r for r in rows if verify_secret(code, r["code_hash"])), None)
            if match is None:
                self._audit(cur, username, "recuperacion_fallida", "")
            else:
                check_secret_strength(new_secret, "admin")
                cur.execute("UPDATE recovery_codes SET used_at = ? WHERE id = ?",
                            (clock.now().isoformat(timespec="seconds"), match["id"]))
                cur.execute("UPDATE users SET secret_hash = ?, totp_secret = '', failed_attempts = 0, lockouts = 0, "
                            "locked_until = '' WHERE id = ?", (hash_secret(new_secret), user["id"]))
                self._end_user_sessions(cur, user["id"])
                self._audit(cur, username, "acceso_recuperado", "con código de recuperación")
                return {k: user[k] for k in ("id", "username", "name", "role")}
        raise generic

    # ------------------------------------------------- two-step verification (TOTP)
    def enable_two_factor(self, user_id: int, secret: str, code: str) -> None:
        if not verify_totp(secret, code):
            raise ValueError("El código no es correcto. Comprueba que la hora del móvil es la correcta y prueba otra vez.")
        with self.db.tx() as cur:
            user = cur.execute("SELECT username FROM users WHERE id = ?", (int(user_id),)).fetchone()
            cur.execute("UPDATE users SET totp_secret = ? WHERE id = ?", (secret, int(user_id)))
            self._audit(cur, user["username"], "verificacion_dos_pasos", "activada")

    def disable_two_factor(self, user_id: int, code: str) -> None:
        with self.db.tx() as cur:
            user = cur.execute("SELECT username, totp_secret FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if not user or not verify_totp(user["totp_secret"], code):
                raise ValueError("El código no es correcto.")
            cur.execute("UPDATE users SET totp_secret = '' WHERE id = ?", (int(user_id),))
            self._audit(cur, user["username"], "verificacion_dos_pasos", "desactivada")

    @staticmethod
    def _audit(cur, username: str, action: str, detail: str = "") -> None:
        cur.execute("INSERT INTO audit_log(happened_at, username, action, detail) VALUES (?, ?, ?, ?)",
                    (clock.now().isoformat(timespec="seconds"), str(username)[:60], action, str(detail)[:500]))

    def audit(self, username: str, action: str, detail: str = "") -> None:
        with self.db.tx() as cur:
            self._audit(cur, username, action, detail)

    def audit_log(self, limit: int = 300) -> pd.DataFrame:
        df = self._frame("SELECT happened_at, username, action, detail FROM audit_log ORDER BY id DESC LIMIT ?",
                         (int(limit),))
        df["happened_at"] = pd.to_datetime(df["happened_at"])
        return df

    @staticmethod
    def can(role: str, needed: str) -> bool:
        return ROLE_RANK.get(role, -1) >= ROLE_RANK[needed]

    # ------------------------------------------------------- bulk copy & backups
    def _export(self, tables: list[str]) -> dict[str, list[dict]]:
        with self.db.tx() as cur:
            return {
                t: cur.execute(f"SELECT * FROM {t} ORDER BY {'key' if t == 'settings' else 'id'}").fetchall()
                for t in tables
            }

    def _replace(self, cur: _Cursor, data: dict[str, list[dict]]) -> None:
        """Replace the contents of the given tables, keeping ids. Callers pass all of DATA_TABLES together."""
        tables = [t for t in ALL_TABLES if t in data]
        for table in reversed(tables):
            cur.execute(f"DELETE FROM {table}")
        cur.execute("DELETE FROM counters")  # numbering restarts from the data that is loaded
        cur.execute("DELETE FROM pos_carts")  # tickets in progress point to products that are being replaced
        self.db.before_reload(cur, tables)
        for table in tables:
            rows = data[table]
            if rows:
                # Column names come from a file the user uploaded: keep only real, well-formed columns.
                known = self.db.columns(cur, table)
                columns = [col for col in rows[0] if col in known and is_safe_identifier(col)]
                cur.executemany(
                    f"INSERT INTO {table}({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                    ([r[c] for c in columns] for r in rows),
                )
        self.db.after_reload(cur, tables)
        self._backfill_payments(cur)

    REQUIRED_TABLES = CORE_TABLES

    def backup_bytes(self) -> bytes:
        """The whole database as a SQLite file, whichever engine holds it."""
        data = self._export(ALL_TABLES)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.db"
            copy = Store(path)
            try:
                with copy.db.tx() as cur:
                    copy._replace(cur, data)
            finally:
                copy.close()
            return path.read_bytes()

    def restore(self, data: bytes) -> None:
        """Replace all data with a backup produced by `backup_bytes`. Validates it before touching anything.

        Only into a demonstration or a business without sales yet (e.g. moving to a new database): restoring
        over real records would destroy everything issued after the copy was made.
        """
        self._guard_replace()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "restore.db"
            path.write_bytes(data)
            try:
                check = sqlite3.connect(path)
                try:
                    tables = {r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                    ok = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                finally:
                    check.close()
            except sqlite3.DatabaseError as exc:
                raise ValueError("El archivo no es una copia de seguridad válida.") from exc
            if not ok or not self.REQUIRED_TABLES <= tables:
                raise ValueError("El archivo no es una copia de seguridad de este gestor o está dañado.")
            source = Store(path)  # also upgrades backups made by older versions
            try:
                rows = source._export(ALL_TABLES)
            finally:
                source.close()
        with self.db.tx() as cur:
            self._replace(cur, rows)
            self._insert_default_settings(cur)

    # ---------------------------------------------------------------- demo setup
    def is_empty(self) -> bool:
        with self.db.tx() as cur:
            return cur.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"] == 0

    # ------------------------------------------------- demonstration vs real data
    def is_demo(self) -> bool:
        return self.settings().get("demo_mode") == "si"

    def has_fiscal_records(self) -> bool:
        with self.db.tx() as cur:
            return any(cur.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone() for t in FISCAL_TABLES)

    def can_replace_data(self) -> bool:
        """Demonstration data, or a business with no sales yet, may be wiped; real fiscal records never."""
        with self.db.tx() as cur:
            if cur.execute("SELECT 1 FROM billing_records LIMIT 1").fetchone():
                return False  # chained billing records are never wiped, whatever the mode says
        return self.is_demo() or not self.has_fiscal_records()

    def _guard_replace(self) -> None:
        if not self.can_replace_data():
            raise FiscalDataError(FISCAL_DATA_MESSAGE)

    def reset(self) -> None:
        """Delete all data (to start for real after a demonstration). Refused once there are real records."""
        self._guard_replace()
        with self.db.tx() as cur:
            self._replace(cur, {t: [] for t in DATA_TABLES})
            self._save_settings(cur, {"demo_mode": "no"})

    def load_preset(self, business_type: str, with_demo_sales: bool = True, seed: int = 7) -> None:
        """Replace all data with a preset catalog and, optionally, ~60 days of realistic demo activity.

        The data is built in a scratch in-memory database and copied over in one transaction, which keeps
        this fast on a remote server and leaves the current data untouched if anything fails.
        """
        self._guard_replace()
        preset = PRESETS[business_type]
        new_settings = {"business_type": business_type, "tax_rate": preset["tax_rate"],
                        "demo_mode": "si" if with_demo_sales else "no"}
        scratch = Store(":memory:")
        try:
            scratch.save_settings({**self.settings(), **new_settings})
            scratch._populate(preset, with_demo_sales, seed)
            data = scratch._export(DATA_TABLES)
        finally:
            scratch.close()
        with self.db.tx() as cur:
            self._replace(cur, data)
            self._save_settings(cur, new_settings)

    def _populate(self, preset: dict, with_demo_sales: bool, seed: int) -> None:
        for promo in preset.get("promotions", []):
            self.save_promotion({"days": "0123456", **promo})
        targets = {}
        for row in preset["catalog"]:
            sku, name, category, price, cost, stock, min_stock = row[:7]
            track = row[7] if len(row) > 7 else preset["track_stock"]
            pid = self.upsert_product(
                {
                    "sku": sku,
                    "name": name,
                    "category": category,
                    "price": price,
                    "cost": cost,
                    # Ample stock while generating demo history; the target level is set afterwards.
                    "stock": (10_000 if with_demo_sales else stock) if track else 0,
                    "min_stock": min_stock if track else 0,
                    "track_stock": int(track),
                    "active": 1,
                }
            )
            targets[pid] = stock if track else 0
        if not with_demo_sales:
            return
        try:
            self._generate_demo_sales(seed, preset)
        finally:
            with self.db.tx() as cur:
                cur.executemany("UPDATE products SET stock = ? WHERE id = ?", [(v, k) for k, v in targets.items()])

    def _generate_demo_sales(self, seed: int, preset: dict) -> None:
        rng = random.Random(seed)
        names = [
            ("Lucía Fernández", "lucia@example.com"),
            ("Martín Gómez", "martin@example.com"),
            ("Sofía Ruiz", "sofia@example.com"),
            ("Distribuciones Norte S.L.", "compras@norte.example.com"),
            ("Carlos Méndez", "carlos@example.com"),
            ("Valentina Ortiz", "valentina@example.com"),
        ]
        customer_ids = [self.upsert_customer({"name": n, "email": e}) for n, e in names]
        products = self.products()
        now = clock.now().replace(second=0, microsecond=0)
        for days_ago in range(60, -1, -1):
            day = now - timedelta(days=days_ago)
            weekend_boost = 1.5 if day.weekday() >= 4 else 1.0
            low, high = preset.get("demo_sales_per_day", (1, 5))
            for _ in range(int(rng.randint(low, high) * weekend_boost)):
                when = day.replace(hour=rng.randint(9, 20), minute=rng.randint(0, 59))
                if when > now:
                    continue
                picks = products.sample(
                    n=rng.randint(1, min(preset.get("demo_max_items", 3), len(products))),
                    random_state=rng.randint(0, 10**6),
                )
                cart = [{"product_id": int(pid), "quantity": rng.randint(1, preset.get("demo_max_quantity", 3))} for pid in picks["id"]]
                # Customers who stopped buying a while ago give the follow-up automation something to show.
                pool = customer_ids if days_ago > 40 else customer_ids[:4]
                customer = rng.choice(pool + [None, None])
                self.create_sale(
                    cart,
                    payment_method=rng.choice(PAYMENT_METHODS[:4]),
                    customer_id=customer,
                    discount_pct=rng.choice([0, 0, 0, 5, 10]),
                    when=when,
                    user_name=rng.choice(["Marta", "Diego", "Sara"]),  # demo team, shown in the Panel
                )

        # One seller with more voids and returns than the rest, for the team alert to show.
        recent = self.sales(start=now - timedelta(days=12), include_cancelled=False)
        diego = recent[recent["user_name"] == "Diego"].head(5)
        for i, (sale_id, created) in enumerate(zip(diego["id"], diego["created_at"])):
            later = min(created.to_pydatetime() + timedelta(minutes=20), now)
            if i < 2:
                self.cancel_sale(int(sale_id), by="Marta", when=later)
            else:
                item = self.returnable(int(sale_id))[0]
                self.create_refund(int(sale_id), {item["id"]: 1}, "Efectivo", "El cliente no quedó satisfecho",
                                   user_name="Marta", when=later)

        # Closed tills for the last few days, with the small differences real counts have.
        for days_ago in range(5, 0, -1):
            day = (now - timedelta(days=days_ago)).date()
            expected = 150 + self.day_summary(day)["cash"]
            self.close_cash(day, 150, round(expected + rng.choice([0, 0, 0, -2.5, 1.2, 5]), 2),
                            when=datetime.combine(day, time(21, 30)))

        agenda = preset.get("agenda")
        if agenda:
            self._generate_demo_appointments(rng, agenda, customer_ids, products, now)
        if preset.get("tables"):
            self._generate_demo_tables(rng, preset["tables"], products)
        self._generate_demo_purchasing(rng, preset, products, now)

    def _generate_demo_purchasing(self, rng, preset: dict, products, now) -> None:
        supplier_ids = [self.save_supplier({"name": name, "email": email, "tax_id": tax})
                        for name, email, tax in preset.get("suppliers", [])]
        if supplier_ids:
            for i, pid in enumerate(products["id"]):
                self.set_product_supplier(int(pid), supplier_ids[i % len(supplier_ids)])
        for category, description, amount, day in preset.get("fixed_costs", []):
            self.save_recurring(category, description, amount, day)
        self.apply_recurring(until=now.date(), since=(now - timedelta(days=60)).date())
        # One past delivery (already received and paid) and one order waiting to be sent.
        tracked = products[products["track_stock"] == 1]
        if not tracked.empty and supplier_ids:
            def items_from(supplier_id):  # each order only carries products that supplier provides
                own = [p for i, (_, p) in enumerate(products.iterrows())
                       if supplier_ids[i % len(supplier_ids)] == supplier_id and p["track_stock"] == 1]
                return [{"product_id": int(p["id"]), "quantity": rng.randint(10, 30), "unit_cost": float(p["cost"])}
                        for p in own[:3]]
            if items := items_from(supplier_ids[0]):
                past = self.create_purchase(supplier_ids[0], items, created_by="Demo", when=now - timedelta(days=20))
                self.receive_purchase(past, received_by="Demo", when=now - timedelta(days=18))
            if items := items_from(supplier_ids[-1])[:2]:
                self.create_purchase(supplier_ids[-1], items, "Pendiente de enviar", created_by="Demo")
        for days_ago, category, description, amount in [(25, "Marketing", "Anuncios en redes sociales", 120),
                                                         (12, "Mantenimiento", "Revisión de equipos", 85)]:
            self.add_expense((now - timedelta(days=days_ago)).date(), category, description, amount,
                             created_by="Demo")

    def _generate_demo_tables(self, rng, layout: dict, products) -> None:
        table_ids = [self.save_table(name, zone, seats) for zone, tables in layout.items() for name, seats in tables]
        waiters = ["Marta", "Diego", "Sara"]
        statuses = ["servido", "servido", "listo", "preparando", "pendiente"]
        for table_id in rng.sample(table_ids, k=min(4, len(table_ids))):
            order_id = self.open_order(table_id, guests=rng.randint(2, 5), opened_by=rng.choice(waiters))
            for _ in range(rng.randint(2, 5)):
                pid = int(rng.choice(list(products["id"])))
                category = products.set_index("id").loc[pid, "category"]
                note = rng.choice({"Principales": ["", "", "poco hecho", "al punto"],
                                   "Entrantes": ["", "", "para compartir", "sin cebolla"]}.get(category, [""]))
                item = self.add_order_item(order_id, pid, rng.randint(1, 3), note, added_by=rng.choice(waiters))
                self.set_kitchen_status(item, rng.choice(statuses))

    def _generate_demo_appointments(self, rng, agenda, customer_ids, products, now) -> None:
        walk_ins = ["Laura Pérez", "Javier Romero", "Elena Castro", "Pablo Navarro", "Marta Gil"]
        for days_ahead in range(7):
            day = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0)
            for hour in sorted(rng.sample(agenda["hours"], k=min(len(agenda["hours"]), rng.randint(2, 4)))):
                starts = day + timedelta(hours=hour)
                if starts <= now:
                    continue
                known = rng.random() < 0.6
                if agenda["single"]:
                    product, notes = int(rng.choice(list(products["id"]))), ""
                else:
                    product, notes = None, f"Mesa para {rng.randint(2, 6)} personas"
                self.create_appointment(
                    starts, agenda["duration"], product_id=product,
                    customer_id=rng.choice(customer_ids) if known else None,
                    customer_name="" if known else rng.choice(walk_ins),
                    notes=notes, allow_overlap=not agenda["single"],
                )
