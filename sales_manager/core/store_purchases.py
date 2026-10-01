"""Suppliers, purchase orders, expenses and net profit."""

import calendar
from datetime import date, datetime, timedelta

import pandas as pd

from .presets import PAYMENT_METHODS
from .security import clean_text

EXPENSE_CATEGORIES = [
    "Alquiler", "Nóminas", "Suministros", "Compras a proveedores", "Marketing", "Seguros",
    "Impuestos y tasas", "Mantenimiento", "Software y servicios", "Transporte", "Otros",
]
# Stock bought is already counted as cost of goods sold when it is sold: not an operating expense.
PURCHASES_CATEGORY = "Compras a proveedores"
PURCHASE_STATUSES = {"borrador": "Borrador", "enviado": "Enviado", "recibido": "Recibido", "cancelado": "Cancelado"}


class PurchasesMixin:
    """Mixed into `Store`."""

    # ---------------------------------------------------------------- suppliers
    def suppliers(self, include_inactive: bool = False) -> pd.DataFrame:
        return self._frame("SELECT * FROM suppliers" + ("" if include_inactive else " WHERE active = 1")
                           + " ORDER BY name")

    def save_supplier(self, data: dict, supplier_id: int | None = None) -> int:
        values = (clean_text(data.get("name"), "Nombre", required=True),
                  clean_text(data.get("tax_id"), "NIF/CIF", "short"), clean_text(data.get("email"), "Email", "email"),
                  clean_text(data.get("phone"), "Teléfono", "short"), clean_text(data.get("notes"), "Notas", "notes"),
                  int(bool(data.get("active", 1))))
        fields = "name, tax_id, email, phone, notes, active"
        with self.db.tx() as cur:
            if supplier_id is None:
                return cur.execute(f"INSERT INTO suppliers({fields}) VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
                                   values).fetchone()["id"]
            cur.execute(f"UPDATE suppliers SET {', '.join(f + ' = ?' for f in fields.split(', '))} WHERE id = ?",
                        (*values, int(supplier_id)))
            return int(supplier_id)

    def set_product_supplier(self, product_id: int, supplier_id: int | None) -> None:
        with self.db.tx() as cur:
            cur.execute("UPDATE products SET supplier_id = ? WHERE id = ?",
                        (None if not supplier_id else int(supplier_id), int(product_id)))

    # ----------------------------------------------------------------- purchases
    def _next_purchase_number(self, cur, when: datetime) -> str:
        stem = f"PED-{when.year}-"
        row = cur.execute("SELECT number FROM purchase_orders WHERE number LIKE ? ORDER BY number DESC LIMIT 1",
                          (stem + "%",)).fetchone()
        return f"{stem}{(int(row['number'].rsplit('-', 1)[1]) + 1 if row else 1):04d}"

    def create_purchase(self, supplier_id: int | None, items: list[dict], notes: str = "", created_by: str = "",
                        when: datetime | None = None) -> int:
        lines = [(int(i["product_id"]), int(i["quantity"]), float(i["unit_cost"])) for i in items
                 if int(i.get("quantity") or 0) > 0]
        if not lines:
            raise ValueError("Añade al menos un producto con cantidad.")
        if any(cost < 0 for _, _, cost in lines):
            raise ValueError("El coste no puede ser negativo.")
        notes = clean_text(notes, "Notas", "notes")
        when = when or datetime.now()
        for attempt in range(3):
            try:
                with self.db.tx() as cur:
                    po_id = cur.execute(
                        "INSERT INTO purchase_orders(number, supplier_id, created_at, created_by, notes, total) "
                        "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
                        (self._next_purchase_number(cur, when), None if not supplier_id else int(supplier_id),
                         when.isoformat(timespec="seconds"), created_by, notes,
                         round(sum(q * c for _, q, c in lines), 2)),
                    ).fetchone()["id"]
                    for pid, qty, cost in lines:
                        p = cur.execute("SELECT name FROM products WHERE id = ?", (pid,)).fetchone()
                        if p is None:
                            raise ValueError("Producto no encontrado.")
                        cur.execute("INSERT INTO purchase_items(po_id, product_id, name, quantity, unit_cost) "
                                    "VALUES (?, ?, ?, ?, ?)", (po_id, pid, p["name"], qty, cost))
                    return po_id
            except self.db.integrity_errors:
                if attempt == 2:
                    raise ValueError("No se pudo crear el pedido. Inténtalo de nuevo.") from None
        raise AssertionError("unreachable")

    def purchases(self) -> pd.DataFrame:
        df = self._frame(
            "SELECT o.id, o.number, o.status, o.created_at, o.created_by, o.received_at, o.total, "
            "COALESCE(s.name, 'Sin proveedor') AS supplier FROM purchase_orders o "
            "LEFT JOIN suppliers s ON s.id = o.supplier_id ORDER BY o.created_at DESC, o.id DESC")
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["total"] = df["total"].astype(float)
        return df

    def purchase(self, po_id: int) -> dict:
        with self.db.tx() as cur:
            row = cur.execute("SELECT o.*, s.name AS supplier_name, s.email AS supplier_email, s.tax_id AS supplier_tax_id "
                              "FROM purchase_orders o LEFT JOIN suppliers s ON s.id = o.supplier_id WHERE o.id = ?",
                              (int(po_id),)).fetchone()
            if row is None:
                raise ValueError("Pedido no encontrado.")
            items = cur.execute("SELECT * FROM purchase_items WHERE po_id = ? ORDER BY id", (int(po_id),)).fetchall()
        return {**row, "items": items}

    def set_purchase_status(self, po_id: int, status: str) -> None:
        if status not in ("enviado", "cancelado"):
            raise ValueError("Cambio de estado no válido.")
        with self.db.tx() as cur:
            row = cur.execute("SELECT status FROM purchase_orders WHERE id = ?", (int(po_id),)).fetchone()
            if row is None or row["status"] in ("recibido", "cancelado"):
                raise ValueError("Ese pedido ya está cerrado.")
            cur.execute("UPDATE purchase_orders SET status = ? WHERE id = ?", (status, int(po_id)))

    def receive_purchase(self, po_id: int, received: dict | None = None, received_by: str = "",
                         register_expense: bool = True, method: str = "Transferencia",
                         when: datetime | None = None) -> dict:
        """Receive goods: stock goes up and the product cost becomes the weighted average of old and new units.
        Optionally records the purchase as an expense. `received` maps item id to units (default: all)."""
        when = when or datetime.now()
        if method not in PAYMENT_METHODS:
            raise ValueError("Forma de pago no válida.")
        with self.db.tx() as cur:
            po = cur.execute("SELECT * FROM purchase_orders WHERE id = ?", (int(po_id),)).fetchone()
            if po is None or po["status"] not in ("borrador", "enviado"):
                raise ValueError("Ese pedido no se puede recibir.")
            total = 0.0
            for item in cur.execute("SELECT * FROM purchase_items WHERE po_id = ?", (int(po_id),)).fetchall():
                units = item["quantity"] if received is None else int(received.get(item["id"], 0))
                if not 0 <= units <= item["quantity"] * 10:
                    raise ValueError(f"Cantidad recibida no válida para «{item['name']}».")
                cur.execute("UPDATE purchase_items SET received = ? WHERE id = ?", (units, item["id"]))
                if units == 0:
                    continue
                p = cur.execute("SELECT stock, cost, track_stock FROM products WHERE id = ?",
                                (item["product_id"],)).fetchone()
                old = max(int(p["stock"]), 0) if p["track_stock"] else 0
                new_cost = (old * float(p["cost"]) + units * float(item["unit_cost"])) / (old + units)
                cur.execute("UPDATE products SET cost = ?, stock = stock + CASE WHEN track_stock = 1 THEN ? ELSE 0 END "
                            "WHERE id = ?", (round(new_cost, 4), units, item["product_id"]))
                total += units * float(item["unit_cost"])
            cur.execute("UPDATE purchase_orders SET status = 'recibido', received_at = ?, received_by = ?, total = ? "
                        "WHERE id = ?", (when.isoformat(timespec="seconds"), received_by, round(total, 2), int(po_id)))
            if register_expense and total > 0:
                cur.execute(
                    "INSERT INTO expenses(day, category, description, amount, method, supplier_id, purchase_id, "
                    "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (when.date().isoformat(), PURCHASES_CATEGORY, f"Pedido {po['number']}", round(total, 2), method,
                     po["supplier_id"], int(po_id), received_by, when.isoformat(timespec="seconds")),
                )
        return self.purchase(po_id)

    def draft_purchases(self, suggestions: pd.DataFrame, created_by: str = "") -> list[str]:
        """One draft order per supplier from reorder suggestions (sku, suggested_qty)."""
        products = self.products().set_index("sku")
        groups: dict = {}
        for _, row in suggestions.iterrows():
            if row["sku"] not in products.index or int(row["suggested_qty"]) <= 0:
                continue
            p = products.loc[row["sku"]]
            supplier = None if pd.isna(p.get("supplier_id")) else int(p["supplier_id"])
            groups.setdefault(supplier, []).append(
                {"product_id": int(p["id"]), "quantity": int(row["suggested_qty"]), "unit_cost": float(p["cost"])})
        numbers = []
        for supplier, items in groups.items():
            po_id = self.create_purchase(supplier, items, "Generado desde la reposición inteligente", created_by)
            numbers.append(self.purchase(po_id)["number"])
        return numbers

    # ------------------------------------------------------------------ expenses
    def add_expense(self, day: date, category: str, description: str, amount: float, method: str = "Transferencia",
                    supplier_id: int | None = None, created_by: str = "", recurring_id: int | None = None) -> int:
        if category not in EXPENSE_CATEGORIES:
            raise ValueError("Categoría de gasto no válida.")
        if method not in PAYMENT_METHODS:
            raise ValueError("Forma de pago no válida.")
        amount = round(float(amount), 2)
        if not 0 < amount <= 10_000_000:
            raise ValueError("El importe debe ser mayor que cero.")
        description = clean_text(description, "Descripción", "name", required=True)
        with self.db.tx() as cur:
            return cur.execute(
                "INSERT INTO expenses(day, category, description, amount, method, supplier_id, recurring_id, "
                "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (day.isoformat(), category, description, amount, method, None if not supplier_id else int(supplier_id),
                 recurring_id, created_by, datetime.now().isoformat(timespec="seconds")),
            ).fetchone()["id"]

    def delete_expense(self, expense_id: int) -> None:
        with self.db.tx() as cur:
            cur.execute("DELETE FROM expenses WHERE id = ?", (int(expense_id),))

    def expenses(self, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        sql, params = ("SELECT e.*, COALESCE(s.name, '') AS supplier FROM expenses e "
                       "LEFT JOIN suppliers s ON s.id = e.supplier_id WHERE 1 = 1"), []
        if start:
            sql += " AND e.day >= ?"
            params.append(start.isoformat())
        if end:
            sql += " AND e.day < ?"
            params.append(end.isoformat())
        df = self._frame(sql + " ORDER BY e.day DESC, e.id DESC", params)
        df["day"] = pd.to_datetime(df["day"])
        df["amount"] = df["amount"].astype(float)
        return df

    def recurring_expenses(self) -> pd.DataFrame:
        return self._frame("SELECT * FROM recurring_expenses ORDER BY active DESC, category, description")

    def save_recurring(self, category: str, description: str, amount: float, day_of_month: int,
                       method: str = "Transferencia") -> int:
        if category not in EXPENSE_CATEGORIES or method not in PAYMENT_METHODS:
            raise ValueError("Categoría o forma de pago no válida.")
        if not 1 <= int(day_of_month) <= 31:
            raise ValueError("El día del mes debe estar entre 1 y 31.")
        if not float(amount) > 0:
            raise ValueError("El importe debe ser mayor que cero.")
        description = clean_text(description, "Descripción", "name", required=True)
        with self.db.tx() as cur:
            return cur.execute(
                "INSERT INTO recurring_expenses(category, description, amount, day_of_month, method) "
                "VALUES (?, ?, ?, ?, ?) RETURNING id",
                (category, description, round(float(amount), 2), int(day_of_month), method)).fetchone()["id"]

    def set_recurring_active(self, recurring_id: int, active: bool) -> None:
        with self.db.tx() as cur:
            cur.execute("UPDATE recurring_expenses SET active = ? WHERE id = ?", (int(active), int(recurring_id)))

    def apply_recurring(self, until: date | None = None, since: date | None = None) -> int:
        """Create the monthly fixed expenses that are due and not yet recorded. Safe to call any time."""
        until = until or date.today()
        since = since or until.replace(day=1)
        created = 0
        month = since.replace(day=1)
        recurring = self.recurring_expenses()
        recurring = recurring[recurring["active"] == 1]
        while month <= until:
            last = calendar.monthrange(month.year, month.month)[1]
            nxt = (month + timedelta(days=last)).replace(day=1)
            for _, r in recurring.iterrows():
                due = month.replace(day=min(int(r["day_of_month"]), last))
                if not since <= due <= until:
                    continue
                with self.db.tx() as cur:
                    exists = cur.execute("SELECT id FROM expenses WHERE recurring_id = ? AND day >= ? AND day < ?",
                                         (int(r["id"]), month.isoformat(), nxt.isoformat())).fetchone()
                if not exists:
                    self.add_expense(due, r["category"], r["description"], r["amount"], r["method"],
                                     created_by="Automático", recurring_id=int(r["id"]))
                    created += 1
            month = nxt
        return created

    # -------------------------------------------------------------------- profit
    def profit(self, start: date, end: date) -> dict:
        """Net sales − cost of goods sold − operating expenses for [start, end). Purchases of stock are shown
        apart: they become cost when the goods are sold, so counting them again would double count."""
        lines = self.sale_lines(datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.min.time()))
        exp = self.expenses(start, end)
        net_sales, cogs = float(lines["revenue"].sum()), float(lines["cost"].sum())
        operating = exp[exp["category"] != PURCHASES_CATEGORY]
        by_category = operating.groupby("category")["amount"].sum().sort_values(ascending=False)
        opex = float(operating["amount"].sum())
        return {
            "net_sales": net_sales, "cogs": cogs, "gross": net_sales - cogs, "opex": opex,
            "purchases": float(exp[exp["category"] == PURCHASES_CATEGORY]["amount"].sum()),
            "net": net_sales - cogs - opex, "by_category": by_category,
            "margin_pct": (net_sales - cogs - opex) / net_sales * 100 if net_sales else 0.0,
        }
