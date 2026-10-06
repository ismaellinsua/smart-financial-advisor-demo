"""Full invoices issued from sales. Mixed into `Store`."""

from datetime import datetime

import pandas as pd

from . import clock
from .engines import Cursor
from .errors import SaleError
from .security import clean_text


class InvoicesMixin:
    # ------------------------------------------------------------------ invoices
    def _next_invoice_number(self, cur: Cursor, when: datetime) -> str:
        series = (self._settings(cur).get("invoice_series") or "FAC").strip() or "FAC"
        return self._take_number(cur, "invoices", f"{series}-{when.year}-", 4)

    def invoice_for_sale(self, sale_id: int) -> dict | None:
        with self.db.tx() as cur:
            return cur.execute("SELECT * FROM invoices WHERE sale_id = ?", (int(sale_id),)).fetchone()

    IRPF_RATES = (0.0, 7.0, 15.0, 19.0)

    def create_invoice(self, sale_id: int, customer: dict, when: datetime | None = None, issued_by: str = "",
                       irpf_rate: float = 0.0, as_role: str | None = None) -> dict:
        """Issue a full invoice for a completed sale. Invoices have their own correlative series per year.

        `irpf_rate` is the income tax a company withholds from a professional's invoice (7 % or 15 % usually);
        it is applied to the taxable base and shown as «Retención IRPF», lowering what the customer pays."""
        self._require(as_role, "encargado")
        settings = self.settings()
        if not settings.get("tax_id", "").strip() or not settings.get("address", "").strip():
            raise ValueError("Para emitir facturas, completa primero tu NIF y tu dirección en Configuración: "
                             "son obligatorios en toda factura.")
        irpf_rate = float(irpf_rate or 0)
        if irpf_rate not in self.IRPF_RATES:
            raise ValueError("Retención de IRPF no válida.")
        name = clean_text(customer.get("name"), "Nombre", "name")
        tax_id = clean_text(customer.get("tax_id"), "NIF/CIF", "short")
        if not name or not tax_id:
            raise ValueError("Para emitir una factura hacen falta el nombre y el NIF/CIF del cliente.")
        address = clean_text(customer.get("address"), "Dirección", "address")
        email = clean_text(customer.get("email"), "Email", "email")
        when = when or clock.now()
        sale_id = int(sale_id)
        for attempt in range(3):
            try:
                with self.db.tx() as cur:
                    sale = cur.execute("SELECT status, customer_id, tax, total FROM sales WHERE id = ?",
                                       (sale_id,)).fetchone()
                    if sale is None or sale["status"] != "completada":
                        raise SaleError("Solo se pueden facturar ventas completadas.")
                    if cur.execute("SELECT id FROM invoices WHERE sale_id = ?", (sale_id,)).fetchone():
                        raise SaleError("Esta venta ya tiene factura.")
                    base = cur.execute("SELECT COALESCE(SUM(net_amount), 0) AS b FROM sale_items WHERE sale_id = ?",
                                       (sale_id,)).fetchone()["b"]
                    irpf_amount = round(float(base) * irpf_rate / 100 + 1e-9, 2)
                    number = self._next_invoice_number(cur, when)
                    row = cur.execute(
                        "INSERT INTO invoices(number, sale_id, issued_at, customer_name, customer_tax_id, "
                        "customer_address, customer_email, issued_by, irpf_rate, irpf_amount) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                        (number, sale_id, when.isoformat(timespec="seconds"),
                         name, tax_id, address, email, issued_by, irpf_rate, irpf_amount),
                    ).fetchone()
                    # The full invoice replaces the simplified one (ticket) the customer already had.
                    self._register_issue(cur, "F3", number, when, sale["tax"], sale["total"],
                                         self._sale_breakdown(cur, sale_id), "invoice", row["id"])
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
            billing = self._billing_record(cur, "invoice", invoice_id) if row else None
        if row is None:
            raise SaleError("Factura no encontrada.")
        return {**row, "sale": self.sale(row["sale_id"]), "billing": billing}

    def invoices(self) -> pd.DataFrame:
        df = self._frame(
            "SELECT i.id, i.number, i.issued_at, i.customer_name, i.customer_tax_id, s.number AS sale_number, "
            "s.total FROM invoices i JOIN sales s ON s.id = i.sale_id ORDER BY i.id DESC"
        )
        df["issued_at"] = pd.to_datetime(df["issued_at"])
        df["total"] = df["total"].astype(float)
        return df
