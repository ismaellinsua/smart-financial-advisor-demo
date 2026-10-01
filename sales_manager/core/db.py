"""Storage for the sales manager: a local SQLite file or a PostgreSQL server (e.g. a free Neon database).

`Store(path_or_url)` picks the engine: a `postgresql://` URL uses PostgreSQL, anything else is a SQLite path.
Every public method runs in its own transaction, so the app behaves the same on both engines.
"""

import random
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from .presets import DEFAULT_SETTINGS, PAYMENT_METHODS, PRESETS
from .pricing import compute_totals

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
    created_at TEXT NOT NULL
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
CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_items_sale ON sale_items(sale_id)
"""

# Insertion order respects foreign keys; deletion goes in reverse.
DATA_TABLES = ["products", "customers", "sales", "sale_items"]
ALL_TABLES = ["settings", *DATA_TABLES]

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ventas.db"


class SaleError(Exception):
    """Raised when a sale cannot be completed (e.g. insufficient stock)."""


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
            url,
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


def _is_postgres(target) -> bool:
    return str(target).startswith(("postgresql://", "postgres://"))


# ----------------------------------------------------------------------------- store
class Store:
    def __init__(self, path=DEFAULT_DB_PATH):
        self.db = _Postgres(str(path)) if _is_postgres(path) else _SQLite(str(path))
        with self.db.tx() as cur:
            for statement in filter(str.strip, self.db.schema().split(";")):
                cur.execute(statement)
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
        fields = ["name", "email", "phone", "tax_id", "notes"]
        values = [str(data.get(f) or "").strip() for f in fields]
        with self.db.tx() as cur:
            if customer_id is None:
                row = cur.execute(
                    "INSERT INTO customers(name, email, phone, tax_id, notes, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
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
                    sale_id = self._insert_sale(cur, cart, payment_method, customer_id, discount_pct, tax_rate, when)
                return self.sale(sale_id)
            except self.db.integrity_errors:
                # Two devices took the same receipt number at the same moment: number it again.
                if attempt == 2:
                    raise SaleError("No se pudo registrar la venta. Inténtalo de nuevo.") from None
        raise AssertionError("unreachable")

    def _insert_sale(self, cur, cart, payment_method, customer_id, discount_pct, tax_rate, when) -> int:
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
            "subtotal, discount, tax, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
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
                columns = list(rows[0])
                cur.executemany(
                    f"INSERT INTO {table}({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                    ([r[c] for c in columns] for r in rows),
                )
        self.db.after_reload(cur, tables)

    REQUIRED_TABLES = set(ALL_TABLES)

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
                )
