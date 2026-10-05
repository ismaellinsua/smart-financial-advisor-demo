"""Customers' data protection rights (RGPD): access and portability, erasure, and consent to marketing.
Mixed into `Store`.

Erasure anonymises the customer instead of deleting the row: sales stay in the figures and invoices keep the
customer's fiscal data they were issued with, because the law requires keeping invoices (4 years for tax,
6 under the Commercial Code). Every export and erasure is written to the activity log.
"""

import json

import pandas as pd

from . import clock

ANONYMOUS = "Cliente eliminado"


class PrivacyMixin:
    def set_marketing_consent(self, customer_id: int, consent: bool, by: str = "") -> None:
        stamp = clock.now().isoformat(timespec="seconds")
        with self.db.tx() as cur:
            row = cur.execute("SELECT name, anonymized_at FROM customers WHERE id = ?", (int(customer_id),)).fetchone()
            if row is None:
                raise ValueError("Cliente no encontrado.")
            if consent and row["anonymized_at"]:
                raise ValueError("Este cliente ejerció su derecho de supresión: no se le pueden enviar ofertas.")
            cur.execute("UPDATE customers SET marketing_consent = ?, consent_at = ? WHERE id = ?",
                        (int(bool(consent)), stamp, int(customer_id)))
            self._audit(cur, by, "consentimiento_publicidad",
                        f"cliente {int(customer_id)}: {'acepta' if consent else 'retirado'}")

    def customer_data_export(self, customer_id: int, by: str = "") -> bytes:
        """Everything the business holds about one person, as JSON (right of access and portability)."""
        cid = int(customer_id)
        with self.db.tx() as cur:
            customer = cur.execute("SELECT * FROM customers WHERE id = ?", (cid,)).fetchone()
            if customer is None:
                raise ValueError("Cliente no encontrado.")
            sales = cur.execute("SELECT id, number, created_at, status, payment_method, total FROM sales "
                                "WHERE customer_id = ? ORDER BY id", (cid,)).fetchall()
            for sale in sales:
                sale["items"] = cur.execute("SELECT name, quantity, unit_price FROM sale_items WHERE sale_id = ? "
                                            "ORDER BY id", (sale["id"],)).fetchall()
            invoices = cur.execute(
                "SELECT i.number, i.issued_at, i.customer_name, i.customer_tax_id, i.customer_address, "
                "i.customer_email FROM invoices i JOIN sales s ON s.id = i.sale_id WHERE s.customer_id = ? "
                "ORDER BY i.id", (cid,)).fetchall()
            points = cur.execute("SELECT points, reason, created_at FROM loyalty_moves WHERE customer_id = ? "
                                 "ORDER BY id", (cid,)).fetchall()
            appointments = cur.execute("SELECT starts_at, duration_min, status, notes FROM appointments "
                                       "WHERE customer_id = ? ORDER BY id", (cid,)).fetchall()
            business = self._settings(cur)
            self._audit(cur, by, "datos_exportados", f"cliente {cid}")
        data = {
            "responsable": {"nombre": business.get("business_name", ""), "nif": business.get("tax_id", ""),
                            "email": business.get("email", "")},
            "generado": clock.now().isoformat(timespec="seconds"),
            "cliente": customer, "compras": sales, "facturas": invoices, "puntos": points, "citas": appointments,
        }
        return json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")

    def forget_customer(self, customer_id: int, by: str = "") -> None:
        """Right to erasure: remove the person's contact data, keep the figures and the invoices the law requires."""
        cid = int(customer_id)
        stamp = clock.now().isoformat(timespec="seconds")
        with self.db.tx() as cur:
            row = cur.execute("SELECT anonymized_at FROM customers WHERE id = ?", (cid,)).fetchone()
            if row is None:
                raise ValueError("Cliente no encontrado.")
            if row["anonymized_at"]:
                raise ValueError("Los datos de este cliente ya se borraron.")
            cur.execute("UPDATE customers SET name = ?, email = '', phone = '', tax_id = '', address = '', notes = '', "
                        "marketing_consent = 0, consent_at = ?, anonymized_at = ? WHERE id = ?",
                        (f"{ANONYMOUS} #{cid}", stamp, stamp, cid))
            cur.execute("UPDATE appointments SET customer_name = ?, notes = '' WHERE customer_id = ?",
                        (f"{ANONYMOUS} #{cid}", cid))
            self._audit(cur, by, "cliente_suprimido", f"cliente {cid} (facturas conservadas por obligación legal)")

    def customer_history(self, customer_id: int, limit: int = 50) -> dict:
        """A customer's card: their latest purchases, what they buy most, points and upcoming appointments."""
        cid = int(customer_id)
        sales = self._frame("SELECT id, number, created_at, payment_method, total, status FROM sales "
                            "WHERE customer_id = ? ORDER BY created_at DESC LIMIT ?", (cid, int(limit)))
        favourites = self._frame(
            "SELECT i.name, SUM(i.quantity) AS units, SUM(i.gross_amount) AS spent FROM sale_items i "
            "JOIN sales s ON s.id = i.sale_id WHERE s.customer_id = ? AND s.status = 'completada' "
            "GROUP BY i.name ORDER BY units DESC LIMIT 5", (cid,))
        upcoming = self._frame("SELECT starts_at, notes FROM appointments WHERE customer_id = ? AND status = "
                               "'pendiente' AND starts_at >= ? ORDER BY starts_at LIMIT 5",
                               (cid, clock.now().isoformat(timespec="seconds")))
        for df, col in ((sales, "created_at"), (upcoming, "starts_at")):
            df[col] = pd.to_datetime(df[col])
        sales["total"] = sales["total"].astype(float)
        return {"sales": sales, "favourites": favourites, "upcoming": upcoming,
                "points": self.customer_points(cid)}

