"""Storage for the sales manager: a local SQLite file or a PostgreSQL server (e.g. a free Neon database).

`Store(path_or_url)` picks the engine: a `postgresql://` URL uses PostgreSQL, anything else is a SQLite path.
Every public method runs in its own transaction, so the app behaves the same on both engines.
"""

import json
import random
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd

from .presets import DEFAULT_SETTINGS, PAYMENT_METHODS, PRESETS
from .pricing import compute_totals
from .security import (
    DUMMY_HASH, ROLE_RANK, ROLES, USERNAME_RE, check_secret_strength, clean_text, hash_secret, is_safe_identifier,
    verify_secret,
)

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
CREATE INDEX IF NOT EXISTS idx_appointments_start ON appointments(starts_at)
"""

# Columns added after the first release, applied to existing databases on start-up.
MIGRATIONS = [
    ("customers", "address", "TEXT NOT NULL DEFAULT ''"),
    # Who did it: names are stored as text so backups restore cleanly into any team.
    ("sales", "user_name", "TEXT NOT NULL DEFAULT ''"),
    ("invoices", "issued_by", "TEXT NOT NULL DEFAULT ''"),
    ("appointments", "created_by", "TEXT NOT NULL DEFAULT ''"),
    ("cash_closings", "closed_by", "TEXT NOT NULL DEFAULT ''"),
]

# Failed logins before an account is locked, and for how long. Each new lock doubles the wait (5, 10, 20 min…
# up to a day), so guessing a short PIN online stays impractical.
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 5
MAX_LOCKOUT_MINUTES = 24 * 60

# Insertion order respects foreign keys; deletion goes in reverse.
DATA_TABLES = ["products", "customers", "sales", "sale_items", "invoices", "appointments", "cash_closings"]
ALL_TABLES = ["settings", *DATA_TABLES]
# Tables any backup must have; newer ones are created when an older backup is opened.
CORE_TABLES = {"settings", "products", "customers", "sales", "sale_items"}

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ventas.db"


class SaleError(Exception):
    """Raised when a sale cannot be completed (e.g. insufficient stock)."""


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

    def schema(self) -> str:
        return SCHEMA.format(pk="INTEGER PRIMARY KEY AUTOINCREMENT", real="REAL")

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

    def schema(self) -> str:
        return SCHEMA.format(pk="INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY", real="DOUBLE PRECISION")

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
class Store:
    def __init__(self, path=DEFAULT_DB_PATH):
        self.db = _Postgres(str(path)) if _is_postgres(path) else _SQLite(str(path))
        with self.db.tx() as cur:
            for statement in filter(str.strip, self.db.schema().split(";")):
                cur.execute(statement)
            for table, column, ddl in MIGRATIONS:
                if column not in self.db.columns(cur, table):
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            self._insert_default_settings(cur)

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
        with self.db.tx() as cur:
            self._save_settings(cur, values)

    # ------------------------------------------------------------------ products
    def products(self, include_inactive: bool = False) -> pd.DataFrame:
        sql = "SELECT * FROM products"
        if not include_inactive:
            sql += " WHERE active = 1"
        return self._frame(sql + " ORDER BY category, name")

    def upsert_product(self, data: dict, product_id: int | None = None) -> int:
        fields = ["sku", "name", "category", "price", "cost", "stock", "min_stock", "track_stock", "active"]
        if not data.get("sku") or not data.get("name"):
            raise ValueError("Código y nombre son obligatorios.")
        data = {**data, "sku": clean_text(data["sku"], "Código", "short"), "name": clean_text(data["name"], "Nombre"),
                "category": clean_text(data.get("category") or "General", "Categoría", "short")}
        # Plain Python types: pandas/numpy scalars from the editor are not understood by every driver.
        values = [
            data.get(f) if isinstance(data.get(f), str) or data.get(f) is None
            else (float(data[f]) if f in ("price", "cost") else int(data[f]))
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

    def adjust_stock(self, product_id: int, delta: int) -> None:
        with self.db.tx() as cur:
            cur.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (int(delta), int(product_id)))

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
                    [*values, datetime.now().isoformat(timespec="seconds")],
                ).fetchone()
                return row["id"]
            cur.execute(
                f"UPDATE customers SET {', '.join(f + ' = ?' for f in fields)} WHERE id = ?",
                [*values, int(customer_id)],
            )
            return int(customer_id)

    # --------------------------------------------------------------------- sales
    def _next_number(self, cur: _Cursor, when: datetime) -> str:
        prefix = self._settings(cur).get("invoice_prefix", "VTA").strip() or "VTA"
        stem = f"{prefix}-{when.year}-"
        row = cur.execute(
            "SELECT number FROM sales WHERE number LIKE ? ORDER BY number DESC LIMIT 1", (stem + "%",)
        ).fetchone()
        seq = int(row["number"].rsplit("-", 1)[1]) + 1 if row else 1
        return f"{stem}{seq:05d}"

    def create_sale(
        self,
        cart: list[dict],
        payment_method: str,
        customer_id: int | None = None,
        discount_pct: float = 0.0,
        tax_rate: float | None = None,
        when: datetime | None = None,
        user_name: str = "",
    ) -> dict:
        """Register a sale atomically: validates stock, decrements it and numbers the receipt.

        `cart` items: {"product_id": int, "quantity": int}. Prices are read from the catalog.
        """
        if not cart:
            raise SaleError("El carrito está vacío.")
        when = when or datetime.now()
        customer_id = None if customer_id is None else int(customer_id)
        discount_pct = float(discount_pct)

        for attempt in range(3):
            try:
                with self.db.tx() as cur:
                    sale_id = self._insert_sale(
                        cur, cart, payment_method, customer_id, discount_pct, tax_rate, when, user_name
                    )
                return self.sale(sale_id)
            except self.db.integrity_errors:
                # Two devices took the same receipt number at the same moment: number it again.
                if attempt == 2:
                    raise SaleError("No se pudo registrar la venta. Inténtalo de nuevo.") from None
        raise AssertionError("unreachable")

    def _insert_sale(self, cur, cart, payment_method, customer_id, discount_pct, tax_rate, when, user_name="") -> int:
        if tax_rate is None:
            tax_rate = float(self._settings(cur).get("tax_rate", 0))
        lines = []
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
            lines.append({"product": p, "quantity": qty, "unit_price": p["price"]})

        totals = compute_totals(lines, discount_pct, tax_rate)
        row = cur.execute(
            "INSERT INTO sales(number, created_at, customer_id, payment_method, discount_pct, tax_rate, "
            "subtotal, discount, tax, total, user_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                self._next_number(cur, when),
                when.isoformat(timespec="seconds"),
                customer_id,
                payment_method,
                discount_pct,
                float(tax_rate),
                totals["subtotal"],
                totals["discount"],
                totals["tax"],
                totals["total"],
                user_name,
            ),
        ).fetchone()
        sale_id = row["id"]
        for line in lines:
            p = line["product"]
            cur.execute(
                "INSERT INTO sale_items(sale_id, product_id, name, quantity, unit_price, unit_cost) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sale_id, p["id"], p["name"], line["quantity"], p["price"], p["cost"]),
            )
            if p["track_stock"]:
                # Guarded decrement: protects against concurrent sales of the last units.
                updated = cur.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                    (line["quantity"], p["id"], line["quantity"]),
                ).rowcount
                if not updated:
                    raise SaleError(f"Stock insuficiente de «{p['name']}».")
        return sale_id

    def cancel_sale(self, sale_id: int) -> None:
        """Void a sale and return its units to stock. Sales are never deleted, to keep numbering intact."""
        sale_id = int(sale_id)
        with self.db.tx() as cur:
            sale = cur.execute("SELECT status FROM sales WHERE id = ?", (sale_id,)).fetchone()
            if sale is None or sale["status"] == "anulada":
                raise SaleError("La venta no existe o ya está anulada.")
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
            cur.execute("UPDATE sales SET status = 'anulada' WHERE id = ?", (sale_id,))

    def sale(self, sale_id: int) -> dict:
        sale_id = int(sale_id)
        with self.db.tx() as cur:
            row = cur.execute(
                "SELECT s.*, c.name AS customer_name, c.email AS customer_email, c.tax_id AS customer_tax_id "
                "FROM sales s LEFT JOIN customers c ON c.id = s.customer_id WHERE s.id = ?",
                (sale_id,),
            ).fetchone()
            if row is None:
                raise SaleError("Venta no encontrada.")
            items = cur.execute("SELECT * FROM sale_items WHERE sale_id = ? ORDER BY id", (sale_id,)).fetchall()
        return {**row, "items": items}

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
        """Line-level data of completed sales, with margin, for analytics."""
        sql = (
            "SELECT i.*, s.created_at, s.customer_id, s.discount_pct, p.category, "
            "i.quantity * i.unit_price * (1 - s.discount_pct / 100.0) AS revenue, "
            "i.quantity * i.unit_cost AS cost "
            "FROM sale_items i JOIN sales s ON s.id = i.sale_id "
            "JOIN products p ON p.id = i.product_id WHERE s.status = 'completada'"
        )
        params: list = []
        if start:
            sql += " AND s.created_at >= ?"
            params.append(start.isoformat(timespec="seconds"))
        if end:
            sql += " AND s.created_at < ?"
            params.append(end.isoformat(timespec="seconds"))
        df = self._frame(sql, params)
        df["created_at"] = pd.to_datetime(df["created_at"])
        # An empty result comes back with object columns; keep numeric types so analytics work with no sales.
        numeric = ["quantity", "unit_price", "unit_cost", "discount_pct", "revenue", "cost"]
        df[numeric] = df[numeric].astype(float)
        df["margin"] = df["revenue"] - df["cost"]
        return df

    # ------------------------------------------------------------------ invoices
    def _next_invoice_number(self, cur: _Cursor, when: datetime) -> str:
        series = (self._settings(cur).get("invoice_series") or "FAC").strip() or "FAC"
        stem = f"{series}-{when.year}-"
        row = cur.execute(
            "SELECT number FROM invoices WHERE number LIKE ? ORDER BY number DESC LIMIT 1", (stem + "%",)
        ).fetchone()
        seq = int(row["number"].rsplit("-", 1)[1]) + 1 if row else 1
        return f"{stem}{seq:04d}"

    def invoice_for_sale(self, sale_id: int) -> dict | None:
        with self.db.tx() as cur:
            return cur.execute("SELECT * FROM invoices WHERE sale_id = ?", (int(sale_id),)).fetchone()

    def create_invoice(self, sale_id: int, customer: dict, when: datetime | None = None, issued_by: str = "") -> dict:
        """Issue a full invoice for a completed sale. Invoices have their own correlative series per year."""
        name = clean_text(customer.get("name"), "Nombre", "name")
        tax_id = clean_text(customer.get("tax_id"), "NIF/CIF", "short")
        if not name or not tax_id:
            raise ValueError("Para emitir una factura hacen falta el nombre y el NIF/CIF del cliente.")
        address = clean_text(customer.get("address"), "Dirección", "address")
        email = clean_text(customer.get("email"), "Email", "email")
        when = when or datetime.now()
        sale_id = int(sale_id)
        for attempt in range(3):
            try:
                with self.db.tx() as cur:
                    sale = cur.execute("SELECT status, customer_id FROM sales WHERE id = ?", (sale_id,)).fetchone()
                    if sale is None or sale["status"] != "completada":
                        raise SaleError("Solo se pueden facturar ventas completadas.")
                    if cur.execute("SELECT id FROM invoices WHERE sale_id = ?", (sale_id,)).fetchone():
                        raise SaleError("Esta venta ya tiene factura.")
                    row = cur.execute(
                        "INSERT INTO invoices(number, sale_id, issued_at, customer_name, customer_tax_id, "
                        "customer_address, customer_email, issued_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                        (self._next_invoice_number(cur, when), sale_id, when.isoformat(timespec="seconds"),
                         name, tax_id, address, email, issued_by),
                    ).fetchone()
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
        if row is None:
            raise SaleError("Factura no encontrada.")
        return {**row, "sale": self.sale(row["sale_id"])}

    def invoices(self) -> pd.DataFrame:
        df = self._frame(
            "SELECT i.id, i.number, i.issued_at, i.customer_name, i.customer_tax_id, s.number AS sale_number, "
            "s.total FROM invoices i JOIN sales s ON s.id = i.sale_id ORDER BY i.number DESC"
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
                 datetime.now().isoformat(timespec="seconds"), created_by),
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
                        appt["customer_id"], float(discount_pct), None, datetime.now(), user_name,
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
        """Completed sales of one day, broken down by payment method."""
        start = datetime.combine(day, time.min)
        with self.db.tx() as cur:
            rows = cur.execute(
                "SELECT payment_method, status, total FROM sales WHERE created_at >= ? AND created_at < ?",
                (start.isoformat(timespec="seconds"), (start + timedelta(days=1)).isoformat(timespec="seconds")),
            ).fetchall()
        breakdown: dict[str, dict] = {}
        cancelled = 0
        for r in rows:
            if r["status"] != "completada":
                cancelled += 1
                continue
            entry = breakdown.setdefault(r["payment_method"], {"count": 0, "total": 0.0})
            entry["count"] += 1
            entry["total"] = round(entry["total"] + float(r["total"]), 2)
        return {
            "breakdown": breakdown,
            "count": sum(e["count"] for e in breakdown.values()),
            "total": round(sum(e["total"] for e in breakdown.values()), 2),
            "cash": breakdown.get("Efectivo", {}).get("total", 0.0),
            "cancelled": cancelled,
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
                     (when or datetime.now()).isoformat(timespec="seconds"), closed_by),
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
    _USER_FIELDS = "id, username, name, role, active, last_login, created_at"

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
                    (username, name, role, hash_secret(secret), datetime.now().isoformat(timespec="seconds")),
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
            self._audit(cur, by, "contraseña_cambiada", user["username"])

    def authenticate(self, username: str, secret: str, now: datetime | None = None) -> dict:
        """Check a login. Locks the account for a few minutes after repeated failures."""
        now = now or datetime.now()
        username = str(username or "").strip().lower()
        generic = AuthError("Usuario o contraseña incorrectos.")
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
                raise AuthError(f"Demasiados intentos fallidos. Vuelve a intentarlo en {minutes} min.")
            elif verify_secret(secret, user["secret_hash"]):
                cur.execute("UPDATE users SET failed_attempts = 0, lockouts = 0, locked_until = '', last_login = ? "
                            "WHERE id = ?",
                            (now.isoformat(timespec="seconds"), user["id"]))
                self._audit(cur, username, "acceso", "")
                return {k: user[k] for k in ("id", "username", "name", "role")}
            else:
                failed = user["failed_attempts"] + 1
                lockouts = user["lockouts"]
                if failed >= MAX_FAILED_LOGINS:
                    lock_minutes = min(LOCKOUT_MINUTES * 2 ** lockouts, MAX_LOCKOUT_MINUTES)
                    locked = (now + timedelta(minutes=lock_minutes)).isoformat(timespec="seconds")
                    failed, lockouts = 0, lockouts + 1
                cur.execute("UPDATE users SET failed_attempts = ?, lockouts = ?, locked_until = ? WHERE id = ?",
                            (failed, lockouts, locked, user["id"]))
                self._audit(cur, username, "acceso_fallido", "cuenta bloqueada" if locked else f"intento {failed}")
        if locked:
            minutes = round((datetime.fromisoformat(locked) - now).total_seconds() / 60)
            raise AuthError(f"Demasiados intentos fallidos. Cuenta bloqueada {minutes} minutos.")
        raise generic

    @staticmethod
    def _audit(cur, username: str, action: str, detail: str = "") -> None:
        cur.execute("INSERT INTO audit_log(happened_at, username, action, detail) VALUES (?, ?, ?, ?)",
                    (datetime.now().isoformat(timespec="seconds"), str(username)[:60], action, str(detail)[:500]))

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
        """Replace all data with a backup produced by `backup_bytes`. Validates it before touching anything."""
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

    def reset(self) -> None:
        with self.db.tx() as cur:
            self._replace(cur, {t: [] for t in DATA_TABLES})

    def load_preset(self, business_type: str, with_demo_sales: bool = True, seed: int = 7) -> None:
        """Replace all data with a preset catalog and, optionally, ~60 days of realistic demo activity.

        The data is built in a scratch in-memory database and copied over in one transaction, which keeps
        this fast on a remote server and leaves the current data untouched if anything fails.
        """
        preset = PRESETS[business_type]
        new_settings = {"business_type": business_type, "tax_rate": preset["tax_rate"]}
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
        now = datetime.now().replace(second=0, microsecond=0)
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

        # Closed tills for the last few days, with the small differences real counts have.
        for days_ago in range(5, 0, -1):
            day = (now - timedelta(days=days_ago)).date()
            expected = 150 + self.day_summary(day)["cash"]
            self.close_cash(day, 150, round(expected + rng.choice([0, 0, 0, -2.5, 1.2, 5]), 2),
                            when=datetime.combine(day, time(21, 30)))

        agenda = preset.get("agenda")
        if agenda:
            self._generate_demo_appointments(rng, agenda, customer_ids, products, now)

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
