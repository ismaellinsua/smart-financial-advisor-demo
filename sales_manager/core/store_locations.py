"""Several shops or premises of one business (locales): each sells, counts its cash and keeps its own stock.

A business with one place never sees any of this. When the second one is added, the first becomes «Principal»
and keeps all the current stock; from then on every stock change says where it happened. `products.stock` stays
the total of all locations, so alerts, reorder suggestions and reports keep working on the whole business, and
`location_stock` holds how much of it is in each place. Sales, cash closings, tables and staff carry the location.
"""

import pandas as pd

from . import clock
from .security import clean_text

MAIN_NAME = "Principal"


class LocationsMixin:
    # ------------------------------------------------------------------ lookup
    @staticmethod
    def _main_location(cur) -> int | None:
        row = cur.execute("SELECT MIN(id) AS id FROM locations").fetchone()
        return row["id"] if row else None

    @staticmethod
    def _multi(cur) -> bool:
        return cur.execute("SELECT COUNT(*) AS n FROM locations").fetchone()["n"] >= 2

    def _location_or_main(self, cur, location_id) -> int | None:
        main = self._main_location(cur)
        if main is None:
            return None
        if location_id is None:
            return main
        if not cur.execute("SELECT 1 FROM locations WHERE id = ?", (int(location_id),)).fetchone():
            raise ValueError("Ese local no existe.")
        return int(location_id)

    def locations(self, include_inactive: bool = False) -> list[dict]:
        def load():
            with self.db.tx() as cur:
                return cur.execute("SELECT * FROM locations " + ("" if include_inactive else "WHERE active = 1 ")
                                   + "ORDER BY id").fetchall()
        return [dict(r) for r in self.db.reads.get(("locations", include_inactive), load)]

    def multi_location(self) -> bool:
        with self.db.tx() as cur:
            return self._multi(cur)

    def location(self, location_id: int | None) -> dict | None:
        if location_id is None:
            return None
        with self.db.tx() as cur:
            row = cur.execute("SELECT * FROM locations WHERE id = ?", (int(location_id),)).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------ manage
    def add_location(self, name: str, address: str = "", phone: str = "") -> int:
        """Add a shop. The first one added turns the existing business into «Principal», which keeps all the stock,
        sales, closings and tables it already had."""
        name = clean_text(name, "Nombre", "short", required=True)
        address, phone = clean_text(address, "Dirección", "address"), clean_text(phone, "Teléfono", "short")
        now = clock.now().isoformat(timespec="seconds")
        with self.db.tx() as cur:
            if cur.execute("SELECT 1 FROM locations WHERE lower(name) = lower(?)", (name,)).fetchone():
                raise ValueError("Ya hay un local con ese nombre.")
            if self._main_location(cur) is None:
                if name.lower() == MAIN_NAME.lower():
                    raise ValueError(f"«{MAIN_NAME}» es el nombre de tu local actual. Elige otro para el nuevo.")
                settings = self._settings(cur)
                main = cur.execute(
                    "INSERT INTO locations(name, address, phone, created_at) VALUES (?, ?, ?, ?) RETURNING id",
                    (MAIN_NAME, settings.get("address", ""), settings.get("phone", ""), now),
                ).fetchone()["id"]
                cur.execute("INSERT INTO location_stock(location_id, product_id, stock) "
                            "SELECT ?, id, stock FROM products WHERE track_stock = 1", (main,))
                for table in ("sales", "cash_closings", "dining_tables", "stock_moves", "purchase_orders"):
                    cur.execute(f"UPDATE {table} SET location_id = ? WHERE location_id IS NULL", (main,))
            return cur.execute(
                "INSERT INTO locations(name, address, phone, created_at) VALUES (?, ?, ?, ?) RETURNING id",
                (name, address, phone, now),
            ).fetchone()["id"]

    def update_location(self, location_id: int, name: str, address: str = "", phone: str = "",
                        active: bool = True) -> None:
        name = clean_text(name, "Nombre", "short", required=True)
        address, phone = clean_text(address, "Dirección", "address"), clean_text(phone, "Teléfono", "short")
        with self.db.tx() as cur:
            if cur.execute("SELECT 1 FROM locations WHERE lower(name) = lower(?) AND id <> ?",
                           (name, int(location_id))).fetchone():
                raise ValueError("Ya hay un local con ese nombre.")
            if not active:
                if int(location_id) == self._main_location(cur):
                    raise ValueError("El local principal no se puede cerrar.")
                left = cur.execute("SELECT COALESCE(SUM(stock), 0) AS n FROM location_stock WHERE location_id = ?",
                                   (int(location_id),)).fetchone()["n"]
                if left:
                    raise ValueError(f"Aún quedan {left} unidades en este local: traspásalas antes de cerrarlo.")
            cur.execute("UPDATE locations SET name = ?, address = ?, phone = ?, active = ? WHERE id = ?",
                        (name, address, phone, int(bool(active)), int(location_id)))

    # ------------------------------------------------------------------ stock
    def _move_stock(self, cur, product_id: int, delta: int, location_id=None, guard: bool = False) -> int | None:
        """Change a product's stock where it happened. Returns the stock left at that location (the total with a
        single location), or None when `guard` is on and it would go below zero (nothing is changed then)."""
        product_id, delta = int(product_id), int(delta)
        if not self._multi(cur):
            row = cur.execute("UPDATE products SET stock = stock + ? WHERE id = ?"
                              + (" AND stock + ? >= 0" if guard else "") + " RETURNING stock",
                              (delta, product_id, *((delta,) if guard else ()))).fetchone()
            return None if row is None else int(row["stock"])
        location_id = self._location_or_main(cur, location_id)
        cur.execute("INSERT INTO location_stock(location_id, product_id, stock) VALUES (?, ?, 0) "
                    "ON CONFLICT(location_id, product_id) DO NOTHING", (location_id, product_id))
        row = cur.execute("UPDATE location_stock SET stock = stock + ? WHERE location_id = ? AND product_id = ?"
                          + (" AND stock + ? >= 0" if guard else "") + " RETURNING stock",
                          (delta, location_id, product_id, *((delta,) if guard else ()))).fetchone()
        if row is None:
            return None
        cur.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (delta, product_id))
        return int(row["stock"])

    def _stock_at(self, cur, product_id: int, location_id=None) -> int:
        if not self._multi(cur):
            row = cur.execute("SELECT stock FROM products WHERE id = ?", (int(product_id),)).fetchone()
        else:
            row = cur.execute("SELECT stock FROM location_stock WHERE location_id = ? AND product_id = ?",
                              (self._location_or_main(cur, location_id), int(product_id))).fetchone()
        return int(row["stock"]) if row else 0

    def stock_at(self, location_id: int | None) -> dict[int, int]:
        """Units of each product at a location ({} with a single location: use the catalogue's stock)."""
        with self.db.tx() as cur:
            if not self._multi(cur):
                return {}
            rows = cur.execute("SELECT product_id, stock FROM location_stock WHERE location_id = ?",
                               (self._location_or_main(cur, location_id),)).fetchall()
        return {r["product_id"]: int(r["stock"]) for r in rows}

    def stock_by_location(self) -> pd.DataFrame:
        """One row per stocked product and one column per location, for the catalogue."""
        locations = self.locations(include_inactive=True)
        products = self._frame("SELECT id, sku, name, stock FROM products WHERE track_stock = 1 AND active = 1 "
                               "ORDER BY category, name")
        rows = self._frame("SELECT location_id, product_id, stock FROM location_stock")
        for loc in locations:
            per = rows[rows["location_id"] == loc["id"]].set_index("product_id")["stock"]
            products[loc["name"]] = products["id"].map(per).fillna(0).astype(int)
        return products.rename(columns={"stock": "Total"})

    def transfer_stock(self, product_id: int, quantity: int, from_location: int, to_location: int,
                       user_name: str = "") -> None:
        """Move units between locations: the total doesn't change, and both moves are recorded."""
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError("La cantidad debe ser mayor que cero.")
        if int(from_location) == int(to_location):
            raise ValueError("Elige dos locales distintos.")
        now = clock.now().isoformat(timespec="seconds")
        with self.db.tx() as cur:
            if not self._multi(cur):
                raise ValueError("Los traspasos necesitan al menos dos locales.")
            names = {r["id"]: r["name"] for r in cur.execute("SELECT id, name FROM locations").fetchall()}
            if int(from_location) not in names or int(to_location) not in names:
                raise ValueError("Ese local no existe.")
            product = cur.execute("SELECT name, track_stock FROM products WHERE id = ?", (int(product_id),)).fetchone()
            if product is None or not product["track_stock"]:
                raise ValueError("Ese producto no lleva control de stock.")
            left = self._move_stock(cur, product_id, -quantity, from_location, guard=True)
            if left is None:
                have = self._stock_at(cur, product_id, from_location)
                raise ValueError(f"En {names[int(from_location)]} solo hay {have} de «{product['name']}».")
            arrived = self._move_stock(cur, product_id, quantity, to_location)
            for loc, delta, after, other in ((from_location, -quantity, left, to_location),
                                             (to_location, quantity, arrived, from_location)):
                cur.execute(
                    "INSERT INTO stock_moves(product_id, delta, stock_after, reason, user_name, created_at, location_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (int(product_id), delta, after,
                     f"Traspaso {'a' if delta < 0 else 'desde'} {names[int(other)]}", str(user_name)[:120], now,
                     int(loc)),
                )
