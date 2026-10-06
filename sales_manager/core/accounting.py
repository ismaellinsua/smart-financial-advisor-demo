"""What the gestoría needs each quarter: the register of invoices issued (libro registro de facturas expedidas), the
VAT summary for the quarterly return (modelo 303) and the income tax withheld by customers.

Rules followed (Reglamento de facturación, RD 1619/2012, and RIVA art. 63):
- Tickets (simplified invoices, F2) are entered as one summary line per day and VAT rate (asiento resumen), with
  their first and last number. Tickets over 3,000 € (VAT included) are entered one by one.
- A ticket replaced by a full invoice (F3) is counted once, in the invoice, never twice.
- Corrective invoices (R1, of full invoices) and returns of tickets (R5) go in with negative amounts.
- Voided tickets are listed apart, so the gestoría sees why the numbering has gaps.
"""

from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

import pandas as pd

SUMMARY_LIMIT = Decimal("3000")  # a ticket above this (VAT included) cannot go in a daily summary
BOOK_COLUMNS = ["Fecha expedición", "Fecha operación", "Tipo", "Número", "Nº tickets", "NIF destinatario",
                "Destinatario", "Base imponible", "Tipo IVA %", "Cuota IVA", "Total", "Retención IRPF",
                "Observaciones"]
TYPE_LABELS = {"F2": "F2 · Ticket", "F2R": "F2 · Resumen diario de tickets", "F3": "F3 · Factura (sustituye ticket)",
               "R1": "R1 · Rectificativa de factura", "R5": "R5 · Devolución de ticket"}


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quarter(day: date) -> tuple[date, date]:
    """First day of the quarter of `day` and first day of the next one."""
    first = date(day.year, 3 * ((day.month - 1) // 3) + 1, 1)
    nxt = date(first.year + (first.month == 10), (first.month + 2) % 12 + 1, 1)
    return first, nxt


def _by_rate(lines: pd.DataFrame, key: str) -> pd.DataFrame:
    """Base and VAT per document and rate. Older lines without their own VAT use the document's single rate."""
    if lines.empty:
        return pd.DataFrame(columns=[key, "rate", "base", "tax"])
    lines = lines.copy()
    lines["rate"] = lines["item_rate"].where(lines["item_rate"].notna(), lines["doc_rate"]).astype(float)
    lines["base"] = lines["net"].map(_d)
    lines["tax"] = [(_d(t) if t is not None and t == t else _d(b * Decimal(str(r)) / 100))
                    for t, b, r in zip(lines["vat"], lines["base"], lines["rate"])]
    grouped = lines.groupby([key, "rate"], as_index=False).agg(base=("base", "sum"), tax=("tax", "sum"))
    return grouped


class AccountingMixin:
    """Mixed into `Store`: the data, already split by VAT rate."""

    def _window(self, start: date, end: date) -> tuple[str, str]:
        return (datetime.combine(start, time.min).isoformat(timespec="seconds"),
                datetime.combine(end, time.min).isoformat(timespec="seconds"))

    def issued_book(self, start: date, end: date) -> tuple[pd.DataFrame, pd.DataFrame]:
        """(book, voided): the register of invoices issued from `start` to `end` (exclusive), and voided tickets."""
        lo, hi = self._window(start, end)
        rows: list[dict] = []

        # Tickets of the period that were not replaced by a full invoice.
        tickets = self._frame(
            "SELECT s.id, s.number, s.created_at, s.total, s.tax_rate AS doc_rate, i.tax_rate AS item_rate, "
            "COALESCE(i.net_amount, i.quantity * i.unit_price * (1 - s.discount_pct / 100.0)) AS net, "
            "i.tax_amount AS vat FROM sales s JOIN sale_items i ON i.sale_id = s.id "
            "WHERE s.status = 'completada' AND s.created_at >= ? AND s.created_at < ? "
            "AND NOT EXISTS (SELECT 1 FROM invoices f WHERE f.sale_id = s.id)", (lo, hi))
        if not tickets.empty:
            heads = tickets.drop_duplicates("id").set_index("id")[["number", "created_at", "total"]]
            parts = _by_rate(tickets, "id").join(heads, on="id")
            parts["day"] = parts["created_at"].str[:10]
            big = parts["total"].map(_d) > SUMMARY_LIMIT
            for r in parts[big].itertuples():
                rows.append(self._row(r.day, r.day, "F2", r.number, 1, "", "", r.base, r.rate, r.tax))
            for (day, rate), g in parts[~big].groupby(["day", "rate"]):
                numbers = sorted(g["number"])
                label = numbers[0] if len(numbers) == 1 else f"{numbers[0]} a {numbers[-1]}"
                rows.append(self._row(day, day, "F2R", label, len(numbers), "", "", g["base"].sum(), rate,
                                      g["tax"].sum()))

        # Full invoices issued in the period (they replace the ticket of their sale).
        invoices = self._frame(
            "SELECT f.id, f.number, f.issued_at, s.created_at, f.customer_tax_id, f.customer_name, f.irpf_amount, "
            "s.tax_rate AS doc_rate, i.tax_rate AS item_rate, "
            "COALESCE(i.net_amount, i.quantity * i.unit_price * (1 - s.discount_pct / 100.0)) AS net, "
            "i.tax_amount AS vat FROM invoices f JOIN sales s ON s.id = f.sale_id JOIN sale_items i ON i.sale_id = s.id "
            "WHERE f.issued_at >= ? AND f.issued_at < ?", (lo, hi))
        if not invoices.empty:
            heads = invoices.drop_duplicates("id").set_index("id")
            for inv_id, g in _by_rate(invoices, "id").groupby("id"):
                h = heads.loc[inv_id]
                for k, r in enumerate(g.sort_values("rate", ascending=False).itertuples()):
                    rows.append(self._row(h["issued_at"][:10], h["created_at"][:10], "F3", h["number"], 1,
                                          h["customer_tax_id"], h["customer_name"], r.base, r.rate, r.tax,
                                          irpf=_d(h["irpf_amount"]) if k == 0 else Decimal("0")))

        # Returns: corrective invoices (R1) when the sale was invoiced, ticket returns (R5) otherwise.
        returns = self._frame(
            "SELECT r.id, r.number, r.created_at, c.number AS note_number, c.issued_at AS note_issued, "
            "f.customer_tax_id, f.customer_name, f.number AS invoice_number, s.number AS ticket, "
            "s.tax_rate AS doc_rate, ri.tax_rate AS item_rate, ri.net_amount AS net, ri.tax_amount AS vat "
            "FROM refunds r JOIN refund_items ri ON ri.refund_id = r.id JOIN sales s ON s.id = r.sale_id "
            "LEFT JOIN credit_notes c ON c.refund_id = r.id LEFT JOIN invoices f ON f.id = c.invoice_id "
            "WHERE r.created_at >= ? AND r.created_at < ?", (lo, hi))
        if not returns.empty:
            heads = returns.drop_duplicates("id").set_index("id")
            for ref_id, g in _by_rate(returns, "id").groupby("id"):
                h = heads.loc[ref_id]
                for r in g.sort_values("rate", ascending=False).itertuples():
                    if pd.notna(h["note_number"]) and h["note_number"]:
                        rows.append(self._row(h["note_issued"][:10], h["created_at"][:10], "R1", h["note_number"], 1,
                                              h["customer_tax_id"], h["customer_name"], -r.base, r.rate, -r.tax,
                                              note=f"Rectifica la factura {h['invoice_number']}"))
                    else:
                        rows.append(self._row(h["created_at"][:10], h["created_at"][:10], "R5", h["number"], 1, "",
                                              "", -r.base, r.rate, -r.tax, note=f"Devolución del ticket {h['ticket']}"))

        book = pd.DataFrame(rows, columns=BOOK_COLUMNS)
        if not book.empty:
            book = book.sort_values(["Fecha expedición", "Número"], kind="stable").reset_index(drop=True)
        voided = self._frame("SELECT number AS \"Número\", created_at AS \"Fecha\", voided_at AS \"Anulado el\", "
                             "voided_by AS \"Anulado por\", total AS \"Importe\" FROM sales WHERE status = 'anulada' "
                             "AND created_at >= ? AND created_at < ? ORDER BY created_at", (lo, hi))
        return book, voided

    @staticmethod
    def _row(issued, operated, kind, number, count, tax_id, name, base, rate, tax, irpf=Decimal("0"), note=""):
        base, tax = _d(base), _d(tax)
        return {"Fecha expedición": issued, "Fecha operación": operated, "Tipo": TYPE_LABELS[kind], "Número": number,
                "Nº tickets": count, "NIF destinatario": tax_id or "", "Destinatario": name or "",
                "Base imponible": float(base), "Tipo IVA %": float(rate), "Cuota IVA": float(tax),
                "Total": float(base + tax), "Retención IRPF": float(_d(irpf)), "Observaciones": note}

    def received_book(self, start: date, end: date) -> pd.DataFrame:
        """Register of invoices received: expenses noted with the supplier's invoice and its VAT rate."""
        exp = self.expenses(start, end)
        rows = []
        if not exp.empty:
            exp = exp[exp["tax_rate"].notna()]
            for e in exp.itertuples():
                total, rate = _d(e.amount), Decimal(str(e.tax_rate))
                base = _d(total / (1 + rate / 100))
                rows.append({"Fecha": str(e.day)[:10], "Nº factura": e.invoice_number,
                             "NIF proveedor": e.issuer_tax_id or e.supplier_tax_id,
                             "Proveedor": e.issuer_name or e.supplier, "Concepto": e.description,
                             "Categoría": e.category, "Base imponible": float(base), "Tipo IVA %": float(rate),
                             "Cuota IVA": float(total - base), "Total": float(total)})
        return pd.DataFrame(rows, columns=["Fecha", "Nº factura", "NIF proveedor", "Proveedor", "Concepto", "Categoría",
                                           "Base imponible", "Tipo IVA %", "Cuota IVA", "Total"])

    def vat_summary(self, book: pd.DataFrame) -> pd.DataFrame:
        """VAT charged per rate in the period (what goes into the quarterly return, modelo 303)."""
        if book.empty:
            return pd.DataFrame(columns=["Tipo IVA %", "Base imponible", "Cuota IVA", "Total"])
        out = (book.groupby("Tipo IVA %", as_index=False)[["Base imponible", "Cuota IVA", "Total"]].sum()
               .sort_values("Tipo IVA %", ascending=False))
        return out.round(2).reset_index(drop=True)

    def gestoria_workbook(self, start: date, end: date) -> bytes:
        """One Excel file for the gestoría: summary, register of invoices issued, voided tickets, expenses."""
        book, voided = self.issued_book(start, end)
        summary = self.vat_summary(book)
        received = self.received_book(start, end)
        charged = float(book["Cuota IVA"].sum()) if not book.empty else 0.0
        deductible = float(received["Cuota IVA"].sum()) if not received.empty else 0.0
        expenses = self.expenses(start, end)  # end is exclusive, as here
        settings = self.settings()
        header = pd.DataFrame({
            "Dato": ["Negocio", "NIF", "Periodo", "Facturación (IVA incluido)", "Base imponible", "IVA repercutido",
                     "Retenciones de IRPF que te practicaron", "Gastos apuntados (IVA incluido)",
                     "IVA soportado en facturas recibidas", "Diferencia orientativa (repercutido − soportado)"],
            "Valor": [settings.get("business_name", ""), settings.get("tax_id", ""),
                      f"{start:%d/%m/%Y} a {end - timedelta(days=1):%d/%m/%Y}",
                      round(float(book["Total"].sum()) if not book.empty else 0.0, 2),
                      round(float(book["Base imponible"].sum()) if not book.empty else 0.0, 2),
                      round(float(book["Cuota IVA"].sum()) if not book.empty else 0.0, 2),
                      round(float(book["Retención IRPF"].sum()) if not book.empty else 0.0, 2),
                      round(float(expenses["amount"].astype(float).sum()) if not expenses.empty else 0.0, 2),
                      round(deductible, 2), round(charged - deductible, 2)]})
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as xls:
            header.to_excel(xls, sheet_name="Resumen", index=False)
            summary.to_excel(xls, sheet_name="Resumen", index=False, startrow=len(header) + 2)
            book.to_excel(xls, sheet_name="Facturas expedidas", index=False)
            received.to_excel(xls, sheet_name="Facturas recibidas", index=False)
            voided.to_excel(xls, sheet_name="Tickets anulados", index=False)
            exp = expenses.rename(columns={"day": "Fecha", "category": "Categoría", "description": "Concepto",
                                           "supplier": "Proveedor", "amount": "Importe (IVA incluido)",
                                           "method": "Forma de pago"})
            if "Fecha" in exp.columns:
                exp["Fecha"] = pd.to_datetime(exp["Fecha"]).dt.date
            keep = [c for c in ("Fecha", "Proveedor", "Categoría", "Concepto", "Importe (IVA incluido)",
                                "Forma de pago") if c in exp.columns]
            exp[keep].to_excel(xls, sheet_name="Gastos", index=False)
            for sheet in xls.sheets.values():
                # Text such as «=HYPERLINK(…)» typed as a customer or supplier name must stay text: openpyxl would
                # store it as a formula that runs when the accountant opens the file. This book has no formulas.
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.data_type == "f":
                            cell.data_type = "s"
                for column in sheet.columns:  # readable column widths
                    width = max(len(str(c.value or "")) for c in column)
                    sheet.column_dimensions[column[0].column_letter].width = min(max(10, width + 2), 48)
        return out.getvalue()
