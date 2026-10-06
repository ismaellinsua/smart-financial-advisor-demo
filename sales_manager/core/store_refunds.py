"""Partial returns and corrective invoices (facturas rectificativas)."""

from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from .presets import PAYMENT_METHODS
from .security import clean_text
from . import clock
from .pricing import tax_breakdown

CENT = Decimal("0.01")


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


class RefundsMixin:
    """Returns of some or all units of a completed sale, with stock, points and invoices kept consistent.

    Mixed into `Store`; uses its transaction helpers and raises `Store.SaleError`.
    """

    def _next_refund_number(self, cur, when: datetime) -> str:
        prefix = (self._settings(cur).get("refund_prefix") or "DEV").strip() or "DEV"
        return self._take_number(cur, "refunds", f"{prefix}-{when.year}-", 5)

    def _next_credit_note_number(self, cur, when: datetime) -> str:
        series = ((self._settings(cur).get("invoice_series") or "FAC").strip() or "FAC") + "R"
        return self._take_number(cur, "credit_notes", f"{series}-{when.year}-", 4)

    @staticmethod
    def _line_net(item: dict, sale: dict) -> Decimal:
        if item.get("net_amount") is not None:
            return _d(item["net_amount"])
        return _d(Decimal(str(item["quantity"])) * _d(item["unit_price"]) * (1 - Decimal(str(sale["discount_pct"])) / 100))

    def returnable(self, sale_id: int) -> list[dict]:
        """Items of a sale with how many units can still be returned."""
        with self.db.tx() as cur:
            items = cur.execute("SELECT * FROM sale_items WHERE sale_id = ? ORDER BY id", (int(sale_id),)).fetchall()
            done = {r["sale_item_id"]: r["n"] for r in cur.execute(
                "SELECT ri.sale_item_id, SUM(ri.quantity) AS n FROM refund_items ri JOIN refunds r ON r.id = ri.refund_id "
                "WHERE r.sale_id = ? GROUP BY ri.sale_item_id", (int(sale_id),)).fetchall()}
        return [{**i, "returned": int(done.get(i["id"], 0)), "remaining": i["quantity"] - int(done.get(i["id"], 0))}
                for i in items]

    def create_refund(self, sale_id: int, quantities: dict, method: str, reason: str, user_name: str = "",
                      when: datetime | None = None, as_role: str | None = None) -> dict:
        """Return units of a sale. `quantities` maps sale_item_id to units. Invoiced sales get a corrective
        invoice automatically. Stock goes back for tracked products and the points earned are reduced."""
        self._require(as_role, "encargado")
        reason = clean_text(reason, "Motivo", "notes")
        if len(reason) < 3:
            raise ValueError("Indica el motivo de la devolución.")
        if method not in PAYMENT_METHODS:
            raise ValueError("Forma de devolución no válida.")
        wanted = {int(k): int(v) for k, v in quantities.items() if int(v or 0) > 0}
        if not wanted:
            raise ValueError("Elige al menos una unidad para devolver.")
        when = when or clock.now()
        sale_id = int(sale_id)
        for attempt in range(3):
            try:
                with self.db.tx() as cur:
                    refund_id = self._insert_refund(cur, sale_id, wanted, method, reason, user_name, when)
                return self.refund(refund_id)
            except self.db.integrity_errors:
                if attempt == 2:
                    raise self.SaleError("No se pudo registrar la devolución. Inténtalo de nuevo.") from None
        raise AssertionError("unreachable")

    def _insert_refund(self, cur, sale_id, wanted, method, reason, user_name, when) -> int:
        # Locked first: two returns of the same ticket at once would both see «nothing returned yet».
        sale = cur.execute("SELECT * FROM sales WHERE id = ?" + self.db.for_update, (sale_id,)).fetchone()
        if sale is None or sale["status"] != "completada":
            raise self.SaleError("Solo se pueden devolver ventas completadas.")
        items = {i["id"]: i for i in cur.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall()}
        done_rows = cur.execute(
            "SELECT ri.sale_item_id, SUM(ri.quantity) AS n, SUM(ri.net_amount) AS net, "
            "SUM(COALESCE(ri.tax_amount, 0)) AS vat FROM refund_items ri "
            "JOIN refunds r ON r.id = ri.refund_id WHERE r.sale_id = ? GROUP BY ri.sale_item_id", (sale_id,)
        ).fetchall()
        done = {r["sale_item_id"]: (int(r["n"]), _d(r["net"]), _d(r["vat"])) for r in done_rows}
        # Sales from before per-product VAT have no per-line VAT: they keep the single-rate calculation.
        legacy = any(i["tax_amount"] is None for i in items.values())

        lines, base, vat_total = [], Decimal("0"), Decimal("0")
        for item_id, qty in wanted.items():
            item = items.get(item_id)
            if item is None:
                raise self.SaleError("Ese producto no pertenece a la venta.")
            returned, returned_net, returned_vat = done.get(item_id, (0, Decimal("0"), Decimal("0")))
            remaining = item["quantity"] - returned
            if qty > remaining:
                raise self.SaleError(f"De «{item['name']}» solo quedan {remaining} unidades por devolver.")
            line_net = self._line_net(item, sale)
            # Returning the last units takes exactly what is left, so several partial returns add up to the line.
            net = line_net - returned_net if qty == remaining else _d(line_net * qty / item["quantity"])
            vat = None
            if not legacy:
                line_vat = _d(item["tax_amount"])
                vat = line_vat - returned_vat if qty == remaining else _d(line_vat * qty / item["quantity"])
                vat_total += vat
            lines.append((item, qty, net, vat))
            base += net

        prior = cur.execute("SELECT COALESCE(SUM(base), 0) AS b, COALESCE(SUM(tax), 0) AS t, "
                            "COALESCE(SUM(total), 0) AS s FROM refunds WHERE sale_id = ?", (sale_id,)).fetchone()
        everything_back = all(
            (done.get(i, (0, 0))[0] + wanted.get(i, 0)) == it["quantity"] for i, it in items.items()
        )
        if not legacy:  # each line carries its own base and VAT: the sum is exact at any rate mix
            tax = vat_total
        elif everything_back:  # the last return closes the sale exactly, whatever the rounding before
            base = _d(Decimal(str(sale["total"])) - Decimal(str(sale["tax"]))) - _d(prior["b"])
            tax = _d(sale["tax"]) - _d(prior["t"])
        else:
            tax = _d(base * Decimal(str(sale["tax_rate"])) / 100)
        total = base + tax

        stamp = when.isoformat(timespec="seconds")
        refund_id = cur.execute(
            "INSERT INTO refunds(number, sale_id, created_at, user_name, reason, method, base, tax, total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (self._next_refund_number(cur, when), sale_id, stamp, user_name, reason, method,
             float(base), float(tax), float(total)),
        ).fetchone()["id"]
        for item, qty, net, vat in lines:
            cur.execute(
                "INSERT INTO refund_items(refund_id, sale_item_id, product_id, name, quantity, net_amount, unit_cost, "
                "tax_rate, tax_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (refund_id, item["id"], item["product_id"], item["name"], qty, float(net), item["unit_cost"],
                 item["tax_rate"] if item["tax_rate"] is not None else sale["tax_rate"],
                 None if vat is None else float(vat)),
            )
            if cur.execute("SELECT track_stock FROM products WHERE id = ?", (item["product_id"],)).fetchone()["track_stock"]:
                self._move_stock(cur, item["product_id"], qty, sale.get("location_id"))  # back where it was sold

        if sale["customer_id"] is not None and sale["points_earned"] and float(sale["total"]):
            give_back = int(round(sale["points_earned"] * float(total) / float(sale["total"])))
            balance = self._points(cur, sale["customer_id"])
            take = min(give_back, max(balance, 0))
            if take:
                cur.execute("INSERT INTO loyalty_moves(customer_id, sale_id, points, reason, created_at) "
                            "VALUES (?, ?, ?, 'devolución', ?)", (sale["customer_id"], sale_id, -take, stamp))

        rates: dict[float, list] = {}
        for item, _qty, net, vat in lines:
            rate = float(item["tax_rate"] if item["tax_rate"] is not None else sale["tax_rate"])
            share = rates.setdefault(rate, [Decimal("0"), Decimal("0")])
            share[0] += net
            share[1] += vat if vat is not None else _d(net * Decimal(str(rate)) / 100)
        breakdown = [{"rate": r, "base": -float(b), "tax": -float(v)} for r, (b, v) in sorted(rates.items())]

        invoice = cur.execute("SELECT id FROM invoices WHERE sale_id = ?", (sale_id,)).fetchone()
        if invoice:
            note_number = self._next_credit_note_number(cur, when)
            note_id = cur.execute(
                "INSERT INTO credit_notes(number, invoice_id, refund_id, issued_at, issued_by) "
                "VALUES (?, ?, ?, ?, ?) RETURNING id",
                (note_number, invoice["id"], refund_id, stamp, user_name),
            ).fetchone()["id"]
            # Corrective invoice of a full invoice (R1), by differences: negative amounts.
            self._register_issue(cur, "R1", note_number, when, -tax, -total, breakdown, "credit_note", note_id)
        else:
            # A return of a ticket corrects a simplified invoice (R5).
            refund_number = cur.execute("SELECT number FROM refunds WHERE id = ?", (refund_id,)).fetchone()["number"]
            self._register_issue(cur, "R5", refund_number, when, -tax, -total, breakdown, "refund", refund_id)
        return refund_id

    def refund(self, refund_id: int) -> dict:
        with self.db.tx() as cur:
            row = cur.execute("SELECT * FROM refunds WHERE id = ?", (int(refund_id),)).fetchone()
            if row is None:
                raise self.SaleError("Devolución no encontrada.")
            items = cur.execute("SELECT * FROM refund_items WHERE refund_id = ? ORDER BY id", (int(refund_id),)).fetchall()
            note = cur.execute("SELECT * FROM credit_notes WHERE refund_id = ?", (int(refund_id),)).fetchone()
            sale = cur.execute("SELECT number, tax_rate, customer_id FROM sales WHERE id = ?", (row["sale_id"],)).fetchone()
            billing = self._billing_record(cur, "refund", refund_id)
            if note:
                note = {**note, "billing": self._billing_record(cur, "credit_note", note["id"])}
        return {**row, "items": items, "credit_note": note, "sale_number": sale["number"],
                "tax_rate": sale["tax_rate"], "taxes": tax_breakdown(items, sale["tax_rate"]), "billing": billing}

    def refunds(self, start: datetime | None = None, end: datetime | None = None) -> pd.DataFrame:
        sql = ("SELECT r.id, r.number, r.created_at, r.user_name, r.reason, r.method, r.base, r.tax, r.total, "
               "s.number AS sale_number, c.number AS credit_note FROM refunds r JOIN sales s ON s.id = r.sale_id "
               "LEFT JOIN credit_notes c ON c.refund_id = r.id WHERE 1 = 1")
        params: list = []
        if start:
            sql += " AND r.created_at >= ?"
            params.append(start.isoformat(timespec="seconds"))
        if end:
            sql += " AND r.created_at < ?"
            params.append(end.isoformat(timespec="seconds"))
        df = self._frame(sql + " ORDER BY r.created_at DESC", params)
        df["created_at"] = pd.to_datetime(df["created_at"])
        for col in ("base", "tax", "total"):
            df[col] = df[col].astype(float)
        return df

    def sale_refunds(self, sale_id: int) -> list[dict]:
        with self.db.tx() as cur:
            ids = [r["id"] for r in cur.execute("SELECT id FROM refunds WHERE sale_id = ? ORDER BY id",
                                                (int(sale_id),)).fetchall()]
        return [self.refund(i) for i in ids]

    def credit_note(self, refund_id: int) -> dict | None:
        """Everything a corrective invoice PDF needs: the note, the refund and the invoice it corrects."""
        refund = self.refund(refund_id)
        if not refund["credit_note"]:
            return None
        with self.db.tx() as cur:
            invoice = cur.execute("SELECT * FROM invoices WHERE id = ?", (refund["credit_note"]["invoice_id"],)).fetchone()
        return {**refund["credit_note"], "refund": refund, "invoice": invoice}

    def refunds_by_method(self, day: date, location_id: int | None = None) -> dict[str, float]:
        """Money handed back on a day, per method; with `location_id`, only refunds of that location's sales."""
        start = datetime.combine(day, time.min)
        where = " AND s.location_id = ?" if location_id is not None else ""
        with self.db.tx() as cur:
            rows = cur.execute(
                "SELECT r.method, SUM(r.total) AS t FROM refunds r JOIN sales s ON s.id = r.sale_id "
                "WHERE r.created_at >= ? AND r.created_at < ?" + where + " GROUP BY r.method",
                (start.isoformat(timespec="seconds"), (start + timedelta(days=1)).isoformat(timespec="seconds"),
                 *(() if location_id is None else (int(location_id),))),
            ).fetchall()
        return {r["method"]: round(float(r["t"]), 2) for r in rows}
