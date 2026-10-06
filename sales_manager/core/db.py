"""Storage for the sales manager: a local SQLite file or a PostgreSQL server (e.g. a free Neon database).

`Store(path_or_url)` picks the engine: a `postgresql://` URL uses PostgreSQL, anything else is a SQLite path.
Every public method runs in its own transaction, so the app behaves the same on both engines.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from .presets import DEFAULT_SETTINGS, PAYMENT_METHODS
from .pricing import apply_promotions, compute_totals, tax_breakdown
from .engines import LOCAL_HOSTS, Cursor, PostgresEngine, SQLiteEngine, is_postgres, load_numbers, secure_url
from .errors import AuthError, FiscalDataError, SaleError
from .schema import (
    ADDED_FOREIGN_KEYS, CHECKS,
    APPEND_ONLY_MESSAGE, DATA_TABLES, FISCAL_DATA_MESSAGE, FISCAL_TABLES, MIGRATIONS,
    VERSIONED_MIGRATIONS,
)
from .store_users import LOCKOUT_MINUTES, MAX_FAILED_LOGINS, UsersMixin
from .store_demo import DemoMixin
from .store_catalog import CatalogMixin
from .store_invoices import InvoicesMixin
from .store_appointments import AppointmentsMixin
from .store_cash import CashMixin
from .store_backup import BackupMixin
from .throttle import ThrottleMixin
from .store_orders import OrdersMixin
from .store_purchases import PurchasesMixin
from .store_intel import IntelligenceMixin
from .store_refunds import RefundsMixin
from .store_billing import BillingMixin
from .store_sessions import SessionsMixin
from .store_privacy import PrivacyMixin
from .store_errors import ErrorsMixin
from .accounting import AccountingMixin
from .store_bookings import BookingMixin
from .store_offline import OfflineMixin
from .store_locations import LocationsMixin
from .store_ecommerce import EcommerceMixin
from .security import is_safe_identifier
from . import clock

# Changes whenever the schema, the engines, this file or the default settings change, so a new version of the code
# sets the database up once and later starts skip it.
# Re-exported so the UI, the tenants directory and the tests keep importing from one place.
__all__ = [
    "Store", "DEFAULT_DB_PATH", "SCHEMA_FINGERPRINT", "SaleError", "AuthError", "FiscalDataError",
    "FISCAL_DATA_MESSAGE", "APPEND_ONLY_MESSAGE", "DATA_TABLES", "FISCAL_TABLES", "VERSIONED_MIGRATIONS",
    "LOCKOUT_MINUTES", "MAX_FAILED_LOGINS", "LOCAL_HOSTS", "Cursor", "load_numbers", "secure_url",
]

_HERE = Path(__file__).resolve().parent
SCHEMA_FINGERPRINT = hashlib.sha256(
    b"".join((_HERE / name).read_bytes() for name in ("db.py", "schema.py", "engines.py"))
    + json.dumps(DEFAULT_SETTINGS, sort_keys=True).encode()
).hexdigest()[:32]

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ventas.db"


# ----------------------------------------------------------------------------- store
class Store(UsersMixin, ThrottleMixin, DemoMixin, CatalogMixin, InvoicesMixin, AppointmentsMixin, CashMixin, BackupMixin,
            RefundsMixin, OrdersMixin, PurchasesMixin, IntelligenceMixin, BillingMixin, SessionsMixin,
            PrivacyMixin, ErrorsMixin, AccountingMixin, BookingMixin, OfflineMixin, LocationsMixin,
            EcommerceMixin):
    SaleError = SaleError
    def __init__(self, path=DEFAULT_DB_PATH, schema: str | None = None):
        """`schema`: on PostgreSQL, the business's own schema when one database serves several businesses."""
        self.db = PostgresEngine(str(path), schema) if is_postgres(path) else SQLiteEngine(str(path))
        if self._schema_is_current():
            return  # one query instead of ~110: with a remote database each one is a round trip
        with self.db.tx() as cur:
            for statement in filter(str.strip, self.db.schema().split(";")):
                cur.execute(statement)
            # Same as the indexes their UNIQUE constraints already create: only extra work on every write.
            for redundant in ("idx_invoices_sale", "idx_credit_notes_refund"):
                cur.execute(f"DROP INDEX IF EXISTS {redundant}")
            for table, column, ddl in MIGRATIONS:
                if column not in self.db.columns(cur, table):
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl.format(real=self.db.real)}")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS sales_offline_id ON sales(offline_id) WHERE offline_id <> ''")
            # Looked up on every visit to a public cancel link, and on every online booking (hourly limit).
            cur.execute("CREATE INDEX IF NOT EXISTS idx_appointments_cancel ON appointments(cancel_hash) "
                        "WHERE cancel_hash <> ''")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_appointments_source ON appointments(source, created_at)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS sales_external_ref ON sales(external_ref) "
                        "WHERE external_ref <> ''")
            # Each fixed expense once a month, even if two devices post them at the same moment. Databases that
            # already have a duplicate keep working (and keep the check in `apply_recurring`).
            if not cur.execute("SELECT 1 FROM expenses WHERE recurring_id IS NOT NULL GROUP BY recurring_id, "
                               "substr(day, 1, 7) HAVING COUNT(*) > 1 LIMIT 1").fetchone():
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS expenses_recurring_month "
                            "ON expenses(recurring_id, substr(day, 1, 7)) WHERE recurring_id IS NOT NULL")
            # One customer per tax number and one location per name (ignoring case). Databases that already have
            # duplicates keep working, and the app refuses new ones anyway (upsert_customer, save_location).
            if not cur.execute("SELECT 1 FROM customers WHERE tax_id <> '' GROUP BY tax_id HAVING COUNT(*) > 1 "
                               "LIMIT 1").fetchone():
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS customers_tax_id ON customers(tax_id) "
                            "WHERE tax_id <> ''")
            if not cur.execute("SELECT 1 FROM locations GROUP BY lower(name) HAVING COUNT(*) > 1 LIMIT 1").fetchone():
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS locations_name ON locations(lower(name))")
            # One cash closing per day and location (it used to be one per day).
            self.db.drop_day_unique(cur)
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS cash_closings_day_location "
                        "ON cash_closings(day, COALESCE(location_id, 0))")
            self.db.make_append_only(cur, "billing_records")
            self._run_versioned_migrations(cur)
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
            cur.execute("INSERT INTO schema_state(key, value) VALUES ('fingerprint', ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (SCHEMA_FINGERPRINT,))

    def _schema_is_current(self) -> bool:
        """True when this database was already set up by this exact version of the code."""
        try:
            with self.db.tx() as cur:
                row = cur.execute("SELECT (SELECT value FROM schema_state WHERE key = 'fingerprint') AS f, "
                                  "(SELECT MAX(version) FROM schema_migrations) AS v").fetchone()
        except Exception:  # noqa: BLE001 - a new or older database without these tables: set it up
            return False
        return row["f"] == SCHEMA_FINGERPRINT and row["v"] == VERSIONED_MIGRATIONS[-1][0]

    def _run_versioned_migrations(self, cur: Cursor) -> None:
        self.db.lock_migrations(cur)
        done = {r["version"] for r in cur.execute("SELECT version FROM schema_migrations").fetchall()}
        for version, name, method in VERSIONED_MIGRATIONS:
            if version in done:
                continue
            getattr(self, method)(cur)
            cur.execute("INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                        (version, name, clock.now_aware().isoformat(timespec="seconds")))

    def schema_version(self) -> int:
        with self.db.tx() as cur:
            row = cur.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
        return int(row["v"] or 0)

    def _money_to_numeric(self, cur: Cursor) -> None:
        """PostgreSQL databases created before stored amounts as binary floating point: make them exact."""
        for table, column in self.db.float_columns(cur):
            if is_safe_identifier(table) and is_safe_identifier(column):
                cur.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {self.db.real} "
                            f"USING round({column}::numeric, 4)")

    def _add_foreign_keys(self, cur: Cursor) -> None:
        """PostgreSQL databases created before these columns had foreign keys: add them. They are enforced for every
        new or changed row at once (NOT VALID) and checked against existing rows only when those are all consistent,
        so an old inconsistency never stops the app from starting. SQLite cannot add them to existing tables."""
        if not self.db.for_update:
            return
        for table, column, parent, on_delete in ADDED_FOREIGN_KEYS:
            name = f"fk_{table}_{column}"
            if cur.execute("SELECT 1 FROM pg_constraint WHERE conrelid = to_regclass(?) AND contype = 'f' "
                           "AND conkey = ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid = to_regclass(?) "
                           "AND attname = ?)]::int2[]", (table, table, column)).fetchone():
                continue  # created with the column (newer databases)
            cur.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({column}) "
                        f"REFERENCES {parent}(id) {on_delete} NOT VALID")
            orphans = cur.execute(f"SELECT 1 FROM {table} t WHERE t.{column} IS NOT NULL AND NOT EXISTS "
                                  f"(SELECT 1 FROM {parent} p WHERE p.id = t.{column}) LIMIT 1").fetchone()
            if not orphans:
                cur.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}")

    def _add_checks(self, cur: Cursor) -> None:
        """PostgreSQL databases from before only accept known values in status and role columns from now on (NOT
        VALID); existing rows are checked too when they all comply. SQLite cannot add them to existing tables."""
        if not self.db.for_update:
            return
        for name, (table, condition) in CHECKS.items():
            if cur.execute("SELECT 1 FROM pg_constraint WHERE conname = ? AND conrelid = to_regclass(?)",
                           (name, table)).fetchone():
                continue
            cur.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({condition}) NOT VALID")
            if not cur.execute(f"SELECT 1 FROM {table} WHERE NOT ({condition}) LIMIT 1").fetchone():
                cur.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}")

    @staticmethod
    def _migrate_prices(cur: Cursor) -> None:
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
            rows, columns = cur.query_rows(sql, params)
        return pd.DataFrame.from_records(rows, columns=columns)

    # ------------------------------------------------------------------ settings
    @staticmethod
    def _insert_default_settings(cur: Cursor) -> None:
        cur.executemany(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
            DEFAULT_SETTINGS.items(),
        )

    @staticmethod
    def _settings(cur: Cursor) -> dict:
        return {r["key"]: r["value"] for r in cur.execute("SELECT key, value FROM settings").fetchall()}

    @staticmethod
    def _save_settings(cur: Cursor, values: dict) -> None:
        cur.executemany(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(k, str(v)) for k, v in values.items()],
        )

    def settings(self) -> dict:
        def load():
            with self.db.tx() as cur:
                return self._settings(cur)
        return dict(self.db.reads.get("settings", load))

    def save_settings(self, values: dict) -> None:
        if "timezone" in values:
            clock.zone(values["timezone"])  # rejects unknown zones
        with self.db.tx() as cur:
            self._save_settings(cur, values)

    # --------------------------------------------------------------------- sales
    @staticmethod
    def _take_number(cur: Cursor, table: str, stem: str, width: int) -> str:
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

    def _next_number(self, cur: Cursor, when: datetime) -> str:
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
        location_id: int | None = None,
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
                        max_discount=max_discount, discount_approved_by=discount_approved_by, location_id=location_id,
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

    def loyalty_settings(self, settings: dict) -> dict:
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

        loyalty = self.loyalty_settings(settings)
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
                     discount_approved_by="", location_id=None) -> int:
        if max_discount is not None and discount_pct > max_discount + 1e-9 and not discount_approved_by:
            raise SaleError(f"Un descuento de más del {max_discount:g} % necesita la autorización de un encargado.")
        if redeem_points and customer_id is not None:
            # One redemption per customer at a time: two tills can't spend the same points twice.
            cur.execute("INSERT INTO counters(series, value) VALUES (?, 1) "
                        "ON CONFLICT(series) DO UPDATE SET value = counters.value + 1", (f"__puntos_{int(customer_id)}__",))
        q = self._quote(cur, cart, discount_pct, tax_rate, customer_id, redeem_points, when, apply_promos)
        t = q["totals"]
        pays = self._normalize_payments(payments, payment_method, t["total"])
        methods = {p["method"] for p in pays}
        label = methods.pop() if len(methods) == 1 else ("Mixto" if pays else payment_method)
        number = self._next_number(cur, when)
        location_id = self._location_or_main(cur, location_id)
        row = cur.execute(
            "INSERT INTO sales(number, created_at, customer_id, payment_method, discount_pct, tax_rate, "
            "subtotal, discount, tax, total, user_name, promo_discount, loyalty_discount, points_redeemed, "
            "points_earned, discount_approved_by, location_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                number, when.isoformat(timespec="seconds"), customer_id, label,
                discount_pct, float(q["tax_rate"]), t["subtotal"], t["discount"], t["tax"], t["total"], user_name,
                t["promo_discount"], t["loyalty_discount"], q["points_redeemed"], q["points_earned"],
                str(discount_approved_by)[:120], location_id,
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
                # Guarded decrement (at this location): protects against concurrent sales of the last units.
                if self._move_stock(cur, p["id"], -line["quantity"], location_id, guard=True) is None:
                    raise SaleError(f"Stock insuficiente de «{p['name']}»"
                                    + (" en este local." if self._multi(cur) else "."))
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

    def cancel_sale(self, sale_id: int, by: str = "", when: datetime | None = None, as_role: str | None = None) -> None:
        """Void a sale and return its units to stock. Sales are never deleted, to keep numbering intact."""
        self._require(as_role, "encargado")
        sale_id = int(sale_id)
        stamp = (when or clock.now()).isoformat(timespec="seconds")
        with self.db.tx() as cur:
            # Locked first: two voids (or a void and a return) of the same sale at once must not both go ahead.
            sale = cur.execute("SELECT status FROM sales WHERE id = ?" + self.db.for_update, (sale_id,)).fetchone()
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
            items = cur.execute("SELECT i.product_id, i.quantity, s.location_id FROM sale_items i "
                                "JOIN sales s ON s.id = i.sale_id JOIN products p ON p.id = i.product_id "
                                "WHERE i.sale_id = ? AND p.track_stock = 1", (sale_id,)).fetchall()
            for item in items:  # back to the location that sold them
                self._move_stock(cur, item["product_id"], item["quantity"], item["location_id"])
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

    def sales(self, start: datetime | None = None, end: datetime | None = None, include_cancelled=True,
              location_id: int | None = None) -> pd.DataFrame:
        """`location_id`: only that location's sales (with several locations); None for the whole business."""
        sql = (
            "SELECT s.*, COALESCE(c.name, 'Cliente general') AS customer_name "
            "FROM sales s LEFT JOIN customers c ON c.id = s.customer_id WHERE 1 = 1"
        )
        params: list = []
        if location_id is not None:
            sql += " AND s.location_id = ?"
            params.append(int(location_id))
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

    def customer_totals(self, start: datetime | None = None) -> pd.DataFrame:
        """Completed purchases per customer, summed by the database: a few thousand rows instead of every ticket."""
        sql = ("SELECT customer_id, COUNT(*) AS purchases, SUM(total) AS lifetime_value, "
               "MIN(created_at) AS first_purchase, MAX(created_at) AS last_purchase FROM sales "
               "WHERE status = 'completada' AND customer_id IS NOT NULL")
        params = []
        if start:
            sql += " AND created_at >= ?"
            params.append(start.isoformat(timespec="seconds"))
        df = self._frame(sql + " GROUP BY customer_id", params)
        df["purchases"] = df["purchases"].astype(int)
        df["lifetime_value"] = df["lifetime_value"].astype(float)
        for col in ("first_purchase", "last_purchase"):
            df[col] = pd.to_datetime(df[col])
        return df

    def sale_lines(self, start: datetime | None = None, end: datetime | None = None) -> pd.DataFrame:
        """Line-level data of completed sales, with margin, for analytics. Returns appear as negative lines on
        the day they happened, so revenue, margins and demand are always net of returns."""
        sql, params = self._lines_sql(start, end)
        df = self._frame(sql, params)
        df["created_at"] = pd.to_datetime(df["created_at"])
        # An empty result comes back with object columns; keep numeric types so analytics work with no sales.
        numeric = ["quantity", "unit_price", "unit_cost", "discount_pct", "revenue", "cost"]
        df[numeric] = df[numeric].astype(float)
        df["margin"] = df["revenue"] - df["cost"]
        return df

    def product_summary(self, start: datetime | None = None, end: datetime | None = None) -> pd.DataFrame:
        """Units, net sales and margin per product for a period, added up by the database: one row per product
        instead of one per line sold, whatever the length of the period."""
        sql, params = self._lines_sql(start, end)
        df = self._frame("SELECT category, name, SUM(quantity) AS unidades, SUM(revenue) AS ventas_netas, "
                         f"SUM(revenue - cost) AS margen FROM ({sql}) lines GROUP BY category, name", params)
        for column in ("unidades", "ventas_netas", "margen"):
            df[column] = df[column].astype(float)
        return df.round(2).sort_values("ventas_netas", ascending=False).reset_index(drop=True)

    def _lines_sql(self, start: datetime | None, end: datetime | None) -> tuple[str, list]:
        """Completed sales lines and returns (as negative lines) in a period, as one query; see sale_lines."""
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
        return sql, [*sold_params, *back_params]

