"""Products, customers and promotions. Mixed into `Store`."""

import re

import pandas as pd

from . import clock
from .pricing import PROMO_KINDS, PROMO_SCOPES
from .security import clean_text


def _vat(value) -> float | None:
    """A product's VAT rate, or None for «the business default»."""
    if value is None or value == "" or (isinstance(value, float) and value != value):  # NaN from the editor
        return None
    rate = float(value)
    if not 0 <= rate <= 100:
        raise ValueError("El IVA debe estar entre 0 y 100 %.")
    return rate


class CatalogMixin:
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
                multi = self._multi(cur)
                if product_id is None:
                    row = cur.execute(
                        f"INSERT INTO products({', '.join(fields)}) VALUES ({', '.join('?' * len(fields))}) "
                        "RETURNING id",
                        values,
                    ).fetchone()
                    if multi and data.get("track_stock", 1):  # a new product's stock starts at the main location
                        cur.execute("INSERT INTO location_stock(location_id, product_id, stock) VALUES (?, ?, ?)",
                                    (self._main_location(cur), row["id"], int(data.get("stock") or 0)))
                    return row["id"]
                if multi:  # with several locations, stock only changes through adjustments and transfers
                    fields, values = zip(*[(f, v) for f, v in zip(fields, values) if f != "stock"])
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

    def adjust_stock(self, product_id: int, delta: int, reason: str = "Ajuste manual", user_name: str = "",
                     location_id: int | None = None) -> int:
        """Add or remove units on top of the current stock (never a stale absolute value) and record who did it.
        With several locations, at `location_id` (the main one by default). Returns the stock left there."""
        delta = int(delta)
        reason = clean_text(reason, "Motivo", "short")
        with self.db.tx() as cur:
            after = self._move_stock(cur, product_id, delta, location_id, guard=True)
            if after is None:
                raise ValueError("El stock no puede quedar en negativo.")
            if delta:
                cur.execute("INSERT INTO stock_moves(product_id, delta, stock_after, reason, user_name, created_at, "
                            "location_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (int(product_id), delta, after, reason, str(user_name)[:120],
                             clock.now().isoformat(timespec="seconds"), self._location_or_main(cur, location_id)))
            return after

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
