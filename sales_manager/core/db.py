"""SQLite storage for the sales manager."""

import random
import sqlite3
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'General',
    price REAL NOT NULL CHECK (price >= 0),
    cost REAL NOT NULL DEFAULT 0 CHECK (cost >= 0),
    stock INTEGER NOT NULL DEFAULT 0,
    min_stock INTEGER NOT NULL DEFAULT 0,
    track_stock INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    tax_id TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    payment_method TEXT NOT NULL,
    discount_pct REAL NOT NULL DEFAULT 0,
    tax_rate REAL NOT NULL DEFAULT 0,
    subtotal REAL NOT NULL,
    discount REAL NOT NULL,
    tax REAL NOT NULL,
    total REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'completada'
);
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL,
    unit_cost REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_items_sale ON sale_items(sale_id);
"""

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ventas.db"


class SaleError(Exception):
    """Raised when a sale cannot be completed (e.g. insufficient stock)."""


class Store:
    def __init__(self, path=DEFAULT_DB_PATH):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        for key, value in DEFAULT_SETTINGS.items():
            self.conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    # ------------------------------------------------------------------ settings
    def settings(self) -> dict:
        return {r["key"]: r["value"] for r in self.conn.execute("SELECT key, value FROM settings")}

    def save_settings(self, values: dict) -> None:
        with self.conn:
            self.conn.executemany(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                [(k, str(v)) for k, v in values.items()],
            )

    # ------------------------------------------------------------------ products
    def products(self, include_inactive: bool = False) -> pd.DataFrame:
        sql = "SELECT * FROM products"
        if not include_inactive:
            sql += " WHERE active = 1"
        return pd.read_sql_query(sql + " ORDER BY category, name", self.conn)

    def upsert_product(self, data: dict, product_id: int | None = None) -> int:
        fields = ["sku", "name", "category", "price", "cost", "stock", "min_stock", "track_stock", "active"]
        values = [data.get(f) for f in fields]
        if not data.get("sku") or not data.get("name"):
            raise ValueError("Código y nombre son obligatorios.")
        try:
            with self.conn:
                if product_id is None:
                    cur = self.conn.execute(
                        f"INSERT INTO products({', '.join(fields)}) VALUES ({', '.join('?' * len(fields))})",
                        values,
                    )
                    return cur.lastrowid
                self.conn.execute(
                    f"UPDATE products SET {', '.join(f + ' = ?' for f in fields)} WHERE id = ?",
                    [*values, product_id],
                )
                return product_id
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"No se pudo guardar: el código '{data['sku']}' ya existe o hay valores inválidos.") from exc

    def adjust_stock(self, product_id: int, delta: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (delta, product_id))

    # ----------------------------------------------------------------- customers
    def customers(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM customers ORDER BY name", self.conn)

    def upsert_customer(self, data: dict, customer_id: int | None = None) -> int:
        if not data.get("name", "").strip():
            raise ValueError("El nombre del cliente es obligatorio.")
        fields = ["name", "email", "phone", "tax_id", "notes"]
        values = [str(data.get(f) or "").strip() for f in fields]
        with self.conn:
            if customer_id is None:
                cur = self.conn.execute(
                    "INSERT INTO customers(name, email, phone, tax_id, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    [*values, datetime.now().isoformat(timespec="seconds")],
                )
                return cur.lastrowid
            self.conn.execute(
                f"UPDATE customers SET {', '.join(f + ' = ?' for f in fields)} WHERE id = ?",
                [*values, customer_id],
            )
            return customer_id

    # --------------------------------------------------------------------- sales
    def _next_number(self, when: datetime) -> str:
        prefix = self.settings().get("invoice_prefix", "VTA").strip() or "VTA"
        stem = f"{prefix}-{when.year}-"
        row = self.conn.execute(
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
        if tax_rate is None:
            tax_rate = float(self.settings().get("tax_rate", 0))

        lines = []
        for item in cart:
            qty = int(item["quantity"])
            if qty <= 0:
                raise SaleError("Las cantidades deben ser mayores que cero.")
            p = self.conn.execute(
                "SELECT * FROM products WHERE id = ? AND active = 1", (item["product_id"],)
            ).fetchone()
            if p is None:
                raise SaleError("Uno de los productos ya no está disponible.")
            if p["track_stock"] and p["stock"] < qty:
                raise SaleError(f"Stock insuficiente de «{p['name']}»: quedan {p['stock']}.")
            lines.append({"product": p, "quantity": qty, "unit_price": p["price"]})

        totals = compute_totals(lines, discount_pct, tax_rate)
        with self.conn:
            number = self._next_number(when)
            cur = self.conn.execute(
                "INSERT INTO sales(number, created_at, customer_id, payment_method, discount_pct, tax_rate, "
                "subtotal, discount, tax, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    number,
                    when.isoformat(timespec="seconds"),
                    customer_id,
                    payment_method,
                    discount_pct,
                    tax_rate,
                    totals["subtotal"],
                    totals["discount"],
                    totals["tax"],
                    totals["total"],
                ),
            )
            sale_id = cur.lastrowid
            for line in lines:
                p = line["product"]
                self.conn.execute(
                    "INSERT INTO sale_items(sale_id, product_id, name, quantity, unit_price, unit_cost) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (sale_id, p["id"], p["name"], line["quantity"], p["price"], p["cost"]),
                )
                if p["track_stock"]:
                    # Guarded decrement: protects against concurrent sales of the last units.
                    updated = self.conn.execute(
                        "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                        (line["quantity"], p["id"], line["quantity"]),
                    ).rowcount
                    if not updated:
                        raise SaleError(f"Stock insuficiente de «{p['name']}».")
        return self.sale(sale_id)

    def cancel_sale(self, sale_id: int) -> None:
        """Void a sale and return its units to stock. Sales are never deleted, to keep numbering intact."""
        with self.conn:
            sale = self.conn.execute("SELECT status FROM sales WHERE id = ?", (sale_id,)).fetchone()
            if sale is None or sale["status"] == "anulada":
                raise SaleError("La venta no existe o ya está anulada.")
            items = self.conn.execute("SELECT product_id, quantity FROM sale_items WHERE sale_id = ?", (sale_id,))
            for item in items.fetchall():
                self.conn.execute(
                    "UPDATE products SET stock = stock + ? WHERE id = ? AND track_stock = 1",
                    (item["quantity"], item["product_id"]),
                )
            self.conn.execute("UPDATE sales SET status = 'anulada' WHERE id = ?", (sale_id,))

    def sale(self, sale_id: int) -> dict:
        row = self.conn.execute(
            "SELECT s.*, c.name AS customer_name, c.email AS customer_email, c.tax_id AS customer_tax_id "
            "FROM sales s LEFT JOIN customers c ON c.id = s.customer_id WHERE s.id = ?",
            (sale_id,),
        ).fetchone()
        if row is None:
            raise SaleError("Venta no encontrada.")
        items = self.conn.execute("SELECT * FROM sale_items WHERE sale_id = ? ORDER BY id", (sale_id,)).fetchall()
        return {**dict(row), "items": [dict(i) for i in items]}

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
        df = pd.read_sql_query(sql + " ORDER BY s.created_at DESC", self.conn, params=params)
        df["created_at"] = pd.to_datetime(df["created_at"])
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
        df = pd.read_sql_query(sql, self.conn, params=params)
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["margin"] = df["revenue"] - df["cost"]
        return df

    # ---------------------------------------------------------------- demo setup
    def is_empty(self) -> bool:
        return self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0

    def reset(self) -> None:
        with self.conn:
            for table in ("sale_items", "sales", "customers", "products"):
                self.conn.execute(f"DELETE FROM {table}")
            self.conn.execute("DELETE FROM sqlite_sequence")

    def load_preset(self, business_type: str, with_demo_sales: bool = True, seed: int = 7) -> None:
        """Replace all data with a preset catalog and, optionally, ~60 days of realistic demo activity."""
        preset = PRESETS[business_type]
        self.reset()
        self.save_settings({"business_type": business_type, "tax_rate": preset["tax_rate"]})
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
            self._generate_demo_sales(seed)
        finally:
            with self.conn:
                self.conn.executemany("UPDATE products SET stock = ? WHERE id = ?", [(v, k) for k, v in targets.items()])

    def _generate_demo_sales(self, seed: int) -> None:
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
            for _ in range(int(rng.randint(1, 5) * weekend_boost)):
                when = day.replace(hour=rng.randint(9, 20), minute=rng.randint(0, 59))
                if when > now:
                    continue
                picks = products.sample(n=rng.randint(1, min(3, len(products))), random_state=rng.randint(0, 10**6))
                cart = [{"product_id": int(pid), "quantity": rng.randint(1, 3)} for pid in picks["id"]]
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
