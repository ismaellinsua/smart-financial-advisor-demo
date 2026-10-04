"""Tables, open orders (comandas) and the kitchen queue."""


import pandas as pd

from .security import clean_text
from . import clock

KITCHEN_FLOW = ["pendiente", "preparando", "listo", "servido"]


class OrdersMixin:
    """Mixed into `Store`. Several waiters can add to the same order; charging turns its items into a sale."""

    # ------------------------------------------------------------------ tables
    def dining_tables(self, include_inactive: bool = False) -> pd.DataFrame:
        """Tables with the open order on each, if any (id, guests, opened time, items and amount so far)."""
        df = self._frame(
            "SELECT t.id, t.name, t.zone, t.seats, t.active, o.id AS order_id, o.guests, o.opened_at, o.opened_by "
            "FROM dining_tables t LEFT JOIN orders o ON o.table_id = t.id AND o.status = 'abierta' "
            + ("" if include_inactive else "WHERE t.active = 1 ") + "ORDER BY t.zone, t.id"
        )
        amounts = self._frame(
            "SELECT i.order_id, SUM(i.quantity) AS items, SUM(i.quantity * p.price) AS amount, "
            "SUM(CASE WHEN i.kitchen IN ('pendiente', 'preparando') THEN 1 ELSE 0 END) AS cooking, "
            "SUM(CASE WHEN i.kitchen = 'listo' THEN 1 ELSE 0 END) AS ready "
            "FROM order_items i JOIN products p ON p.id = i.product_id JOIN orders o ON o.id = i.order_id "
            "WHERE o.status = 'abierta' AND i.sale_id IS NULL GROUP BY i.order_id"
        )
        df = df.merge(amounts, on="order_id", how="left")
        for col in ("items", "amount", "cooking", "ready"):
            df[col] = df[col].fillna(0).astype(float)
        df["opened_at"] = pd.to_datetime(df["opened_at"])
        return df

    def save_table(self, name: str, zone: str = "Sala", seats: int = 4, table_id: int | None = None) -> int:
        name = clean_text(name, "Nombre", "short", required=True)
        zone = clean_text(zone or "Sala", "Zona", "short")
        seats = int(seats)
        if not 1 <= seats <= 50:
            raise ValueError("Las plazas deben estar entre 1 y 50.")
        with self.db.tx() as cur:
            if table_id is None:
                return cur.execute("INSERT INTO dining_tables(name, zone, seats) VALUES (?, ?, ?) RETURNING id",
                                   (name, zone, seats)).fetchone()["id"]
            cur.execute("UPDATE dining_tables SET name = ?, zone = ?, seats = ? WHERE id = ?",
                        (name, zone, seats, int(table_id)))
            return int(table_id)

    def set_table_active(self, table_id: int, active: bool) -> None:
        with self.db.tx() as cur:
            busy = cur.execute("SELECT id FROM orders WHERE table_id = ? AND status = 'abierta'",
                               (int(table_id),)).fetchone()
            if busy and not active:
                raise ValueError("No se puede retirar una mesa con una comanda abierta.")
            cur.execute("UPDATE dining_tables SET active = ? WHERE id = ?", (int(active), int(table_id)))

    # ------------------------------------------------------------------ orders
    def open_order(self, table_id: int | None, guests: int = 0, opened_by: str = "", label: str = "") -> int:
        """Open an order on a table (or a counter/takeaway order without table). Re-opening a busy table returns
        its current order, so two waiters never create two tickets for the same table."""
        label = clean_text(label, "Nombre", "short")
        if table_id is None and not label:
            raise ValueError("Pon un nombre a la comanda (p. ej. «Barra» o «Para llevar · Ana»).")
        for _ in range(2):
            try:
                with self.db.tx() as cur:
                    if table_id is not None:
                        table = cur.execute("SELECT active FROM dining_tables WHERE id = ?", (int(table_id),)).fetchone()
                        if table is None or not table["active"]:
                            raise ValueError("Mesa no disponible.")
                        current = cur.execute("SELECT id FROM orders WHERE table_id = ? AND status = 'abierta'",
                                              (int(table_id),)).fetchone()
                        if current:
                            return current["id"]
                    return cur.execute(
                        "INSERT INTO orders(table_id, label, opened_at, opened_by, guests) VALUES (?, ?, ?, ?, ?) "
                        "RETURNING id",
                        (None if table_id is None else int(table_id), label,
                         clock.now().isoformat(timespec="seconds"), opened_by, max(0, int(guests))),
                    ).fetchone()["id"]
            except self.db.integrity_errors:
                continue  # another waiter opened it at the same instant: take theirs
        raise ValueError("No se pudo abrir la comanda. Inténtalo de nuevo.")

    def open_orders(self) -> pd.DataFrame:
        return self._frame(
            "SELECT o.id, o.label, o.opened_at, o.guests, t.name AS table_name FROM orders o "
            "LEFT JOIN dining_tables t ON t.id = o.table_id WHERE o.status = 'abierta' ORDER BY o.opened_at"
        )

    def order(self, order_id: int) -> dict:
        with self.db.tx() as cur:
            row = cur.execute(
                "SELECT o.*, t.name AS table_name FROM orders o LEFT JOIN dining_tables t ON t.id = o.table_id "
                "WHERE o.id = ?", (int(order_id),)).fetchone()
            if row is None:
                raise ValueError("Comanda no encontrada.")
            items = cur.execute(
                "SELECT i.*, p.price, p.category FROM order_items i JOIN products p ON p.id = i.product_id "
                "WHERE i.order_id = ? ORDER BY i.id", (int(order_id),)).fetchall()
        unpaid = [i for i in items if i["sale_id"] is None]
        return {**row, "items": items, "unpaid": unpaid,
                "amount": round(sum(i["quantity"] * i["price"] for i in unpaid), 2),
                "title": row["table_name"] or row["label"]}

    def _open_order_row(self, cur, order_id: int) -> dict:
        row = cur.execute("SELECT status FROM orders WHERE id = ?", (int(order_id),)).fetchone()
        if row is None or row["status"] != "abierta":
            raise ValueError("La comanda ya no está abierta.")
        return row

    def add_order_item(self, order_id: int, product_id: int, quantity: int = 1, notes: str = "",
                       added_by: str = "") -> int:
        quantity = int(quantity)
        if not 1 <= quantity <= 999:
            raise ValueError("Cantidad no válida.")
        notes = clean_text(notes, "Nota", "notes")
        with self.db.tx() as cur:
            self._open_order_row(cur, order_id)
            p = cur.execute("SELECT name FROM products WHERE id = ? AND active = 1", (int(product_id),)).fetchone()
            if p is None:
                raise ValueError("Producto no disponible.")
            # Same product, no note and not yet in the kitchen: add to that line instead of a new one.
            same = None if notes else cur.execute(
                "SELECT id FROM order_items WHERE order_id = ? AND product_id = ? AND notes = '' "
                "AND kitchen = 'pendiente' AND sale_id IS NULL", (int(order_id), int(product_id))).fetchone()
            if same:
                cur.execute("UPDATE order_items SET quantity = quantity + ? WHERE id = ?", (quantity, same["id"]))
                return same["id"]
            return cur.execute(
                "INSERT INTO order_items(order_id, product_id, name, quantity, notes, added_by, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (int(order_id), int(product_id), p["name"], quantity, notes, added_by,
                 clock.now().isoformat(timespec="seconds")),
            ).fetchone()["id"]

    def change_order_item(self, item_id: int, delta: int, force: bool = False) -> None:
        """Change a line's quantity; at zero it is removed. Lines already in the kitchen need `force`
        (a manager), so food that is being cooked does not silently disappear from the bill."""
        with self.db.tx() as cur:
            item = cur.execute("SELECT * FROM order_items WHERE id = ?", (int(item_id),)).fetchone()
            if item is None or item["sale_id"] is not None:
                raise ValueError("Esa línea ya no se puede cambiar.")
            self._open_order_row(cur, item["order_id"])
            if delta < 0 and item["kitchen"] != "pendiente" and not force:
                raise ValueError("Ya está en cocina: solo un encargado puede quitarlo.")
            new = item["quantity"] + int(delta)
            if new <= 0:
                cur.execute("DELETE FROM order_items WHERE id = ?", (int(item_id),))
            else:
                cur.execute("UPDATE order_items SET quantity = ? WHERE id = ?", (new, int(item_id)))

    def set_kitchen_status(self, item_id: int, status: str) -> None:
        if status not in KITCHEN_FLOW:
            raise ValueError("Estado de cocina no válido.")
        with self.db.tx() as cur:
            cur.execute("UPDATE order_items SET kitchen = ? WHERE id = ?", (status, int(item_id)))

    def advance_kitchen(self, item_id: int) -> None:
        with self.db.tx() as cur:
            item = cur.execute("SELECT kitchen FROM order_items WHERE id = ?", (int(item_id),)).fetchone()
            if item is None:
                return
            step = KITCHEN_FLOW.index(item["kitchen"]) if item["kitchen"] in KITCHEN_FLOW else 0
            nxt = KITCHEN_FLOW[min(step + 1, len(KITCHEN_FLOW) - 1)]
            cur.execute("UPDATE order_items SET kitchen = ? WHERE id = ?", (nxt, int(item_id)))

    def kitchen_queue(self, categories: list[str] | None = None) -> pd.DataFrame:
        df = self._frame(
            "SELECT i.id, i.order_id, i.name, i.quantity, i.notes, i.kitchen, i.added_at, i.added_by, p.category, "
            "COALESCE(t.name, o.label) AS place FROM order_items i JOIN orders o ON o.id = i.order_id "
            "JOIN products p ON p.id = i.product_id LEFT JOIN dining_tables t ON t.id = o.table_id "
            "WHERE o.status = 'abierta' AND i.kitchen IN ('pendiente', 'preparando', 'listo') ORDER BY i.added_at, i.id"
        )
        df["added_at"] = pd.to_datetime(df["added_at"])
        if categories:
            df = df[df["category"].isin(categories)]
        return df

    def set_order_guests(self, order_id: int, guests: int) -> None:
        with self.db.tx() as cur:
            cur.execute("UPDATE orders SET guests = ? WHERE id = ?", (max(0, min(99, int(guests))), int(order_id)))

    def move_order(self, order_id: int, table_id: int) -> None:
        with self.db.tx() as cur:
            self._open_order_row(cur, order_id)
            if cur.execute("SELECT id FROM orders WHERE table_id = ? AND status = 'abierta'",
                           (int(table_id),)).fetchone():
                raise ValueError("Esa mesa ya está ocupada.")
            cur.execute("UPDATE orders SET table_id = ? WHERE id = ?", (int(table_id), int(order_id)))

    def cancel_order(self, order_id: int) -> None:
        with self.db.tx() as cur:
            self._open_order_row(cur, order_id)
            if cur.execute("SELECT id FROM order_items WHERE order_id = ? AND sale_id IS NOT NULL",
                           (int(order_id),)).fetchone():
                raise ValueError("Parte de la comanda ya está cobrada: cobra el resto.")
            cur.execute("DELETE FROM order_items WHERE order_id = ?", (int(order_id),))
            cur.execute("UPDATE orders SET status = 'cancelada', closed_at = ? WHERE id = ?",
                        (clock.now().isoformat(timespec="seconds"), int(order_id)))

    def order_cart(self, order_id: int, selection: dict | None = None) -> list[dict]:
        """Cart for charging: all unpaid items, or `selection` {item_id: units} to split the bill by products."""
        order = self.order(order_id)
        cart: dict[int, int] = {}
        for item in order["unpaid"]:
            units = item["quantity"] if selection is None else min(int(selection.get(item["id"], 0)), item["quantity"])
            if units > 0:
                cart[item["product_id"]] = cart.get(item["product_id"], 0) + units
        return [{"product_id": pid, "quantity": q} for pid, q in cart.items()]

    def charge_order(self, order_id: int, selection: dict | None = None, **checkout) -> dict:
        """Charge an order (or the selected units): one sale; the order closes when nothing is left to pay."""
        cart = self.order_cart(order_id, selection)
        if not cart:
            raise self.SaleError("No hay nada seleccionado para cobrar.")
        when = checkout.pop("when", None) or clock.now()
        for attempt in range(3):
            try:
                with self.db.tx() as cur:
                    self._open_order_row(cur, order_id)
                    sale_id = self._insert_sale(
                        cur, cart, checkout.get("payment_method", "Tarjeta"), checkout.get("customer_id"),
                        float(checkout.get("discount_pct") or 0), None, when, checkout.get("user_name", ""),
                        payments=checkout.get("payments"), redeem_points=int(checkout.get("redeem_points") or 0),
                        max_discount=checkout.get("max_discount"),
                        discount_approved_by=checkout.get("discount_approved_by", ""),
                    )
                    self._mark_paid(cur, order_id, selection, sale_id)
                    left = cur.execute("SELECT COUNT(*) AS n FROM order_items WHERE order_id = ? AND sale_id IS NULL",
                                       (int(order_id),)).fetchone()["n"]
                    if not left:
                        cur.execute("UPDATE orders SET status = 'cobrada', closed_at = ? WHERE id = ?",
                                    (when.isoformat(timespec="seconds"), int(order_id)))
                return self.sale(sale_id)
            except self.db.integrity_errors:
                if attempt == 2:
                    raise self.SaleError("No se pudo cobrar la comanda. Inténtalo de nuevo.") from None
        raise AssertionError("unreachable")

    def _mark_paid(self, cur, order_id: int, selection: dict | None, sale_id: int) -> None:
        items = cur.execute("SELECT * FROM order_items WHERE order_id = ? AND sale_id IS NULL ORDER BY id",
                            (int(order_id),)).fetchall()
        for item in items:
            units = item["quantity"] if selection is None else min(int(selection.get(item["id"], 0)), item["quantity"])
            if units <= 0:
                continue
            if units == item["quantity"]:
                cur.execute("UPDATE order_items SET sale_id = ? WHERE id = ?", (sale_id, item["id"]))
            else:  # pay part of a line: split it in a paid and an unpaid line
                cur.execute("UPDATE order_items SET quantity = ? WHERE id = ?", (item["quantity"] - units, item["id"]))
                cur.execute(
                    "INSERT INTO order_items(order_id, product_id, name, quantity, notes, added_by, added_at, kitchen, "
                    "sale_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (item["order_id"], item["product_id"], item["name"], units, item["notes"], item["added_by"],
                     item["added_at"], item["kitchen"], sale_id),
                )
