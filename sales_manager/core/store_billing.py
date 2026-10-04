"""VERI*FACTU billing records (registros de facturación): one per ticket, invoice, corrective invoice or cancellation,
chained by fingerprint and impossible to change or delete once written. Mixed into `Store`.

Records are written only when the administrator turns the register on (setting `verifactu` = "si"), outside demo
mode and with the business's tax id set. Sending them to the AEAT is a later step.
"""

import json

import pandas as pd

from . import clock
from .verifactu import alta_hash, amount, anulacion_hash, issue_date, verify_chain

CHAIN_LOCK = "__verifactu__"  # counters row locked while a record is chained, so records never fork


class BillingMixin:
    def _billing_issuer(self, cur) -> str | None:
        """The business tax id when the register is on and the data is real; otherwise None (nothing recorded)."""
        settings = self._settings(cur)
        nif = (settings.get("tax_id") or "").strip().upper()
        if settings.get("verifactu") != "si" or settings.get("demo_mode") == "si" or not nif:
            return None
        return nif

    def _chain_previous(self, cur) -> str:
        cur.execute("INSERT INTO counters(series, value) VALUES (?, 1) "
                    "ON CONFLICT(series) DO UPDATE SET value = counters.value + 1", (CHAIN_LOCK,))
        row = cur.execute("SELECT hash FROM billing_records ORDER BY id DESC LIMIT 1").fetchone()
        return row["hash"] if row else ""

    def _register_issue(self, cur, invoice_type: str, number: str, when, tax_total, amount_total, breakdown,
                        source: str, source_id: int) -> None:
        nif = self._billing_issuer(cur)
        if nif is None:
            return
        previous = self._chain_previous(cur)
        generated = clock.now_aware().isoformat()
        issued_on, tax_s, total_s = issue_date(when), amount(tax_total), amount(amount_total)
        fingerprint = alta_hash(nif, number, issued_on, invoice_type, tax_s, total_s, previous, generated)
        cur.execute(
            "INSERT INTO billing_records(kind, invoice_type, number, issued_on, issuer_tax_id, tax_total, amount_total, "
            "breakdown, previous_hash, generated_at, hash, source, source_id) "
            "VALUES ('alta', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (invoice_type, number, issued_on, nif, tax_s, total_s, json.dumps(breakdown, ensure_ascii=False),
             previous, generated, fingerprint, source, int(source_id)))

    def _register_cancellation(self, cur, source: str, source_id: int) -> None:
        nif = self._billing_issuer(cur)
        if nif is None:
            return
        original = cur.execute("SELECT number, issued_on, issuer_tax_id FROM billing_records WHERE kind = 'alta' "
                               "AND source = ? AND source_id = ? ORDER BY id LIMIT 1", (source, int(source_id))).fetchone()
        if original is None:  # issued before the register was turned on
            return
        previous = self._chain_previous(cur)
        generated = clock.now_aware().isoformat()
        fingerprint = anulacion_hash(original["issuer_tax_id"], original["number"], original["issued_on"],
                                     previous, generated)
        cur.execute(
            "INSERT INTO billing_records(kind, invoice_type, number, issued_on, issuer_tax_id, tax_total, amount_total, "
            "breakdown, previous_hash, generated_at, hash, source, source_id) "
            "VALUES ('anulacion', '', ?, ?, ?, '', '', '[]', ?, ?, ?, ?, ?)",
            (original["number"], original["issued_on"], original["issuer_tax_id"], previous, generated, fingerprint,
             source, int(source_id)))

    @staticmethod
    def _sale_breakdown(cur, sale_id: int) -> list[dict]:
        """VAT per rate of a sale, from its lines (older sales without per-line VAT use the sale's totals)."""
        rows = cur.execute("SELECT tax_rate, SUM(net_amount) AS base, SUM(tax_amount) AS tax FROM sale_items "
                           "WHERE sale_id = ? AND tax_amount IS NOT NULL GROUP BY tax_rate ORDER BY tax_rate",
                           (int(sale_id),)).fetchall()
        if not rows:
            sale = cur.execute("SELECT tax_rate, tax, total FROM sales WHERE id = ?", (int(sale_id),)).fetchone()
            return [{"rate": float(sale["tax_rate"]), "base": round(float(sale["total"]) - float(sale["tax"]), 2),
                     "tax": float(sale["tax"])}]
        return [{"rate": float(r["tax_rate"]), "base": round(float(r["base"]), 2), "tax": round(float(r["tax"]), 2)}
                for r in rows]

    # ------------------------------------------------------------------ public
    def enable_billing_register(self, by: str = "") -> None:
        settings = self.settings()
        if settings.get("demo_mode") == "si":
            raise ValueError("Primero pasa a vender de verdad: con datos de ejemplo no se registran facturas.")
        if not (settings.get("tax_id") or "").strip():
            raise ValueError("Pon el NIF del negocio en Configuración antes de activar el registro.")
        self.save_settings({"verifactu": "si"})
        self.audit(by, "registro_facturacion", "activado")

    def billing_records(self) -> pd.DataFrame:
        df = self._frame("SELECT id, kind, invoice_type, number, issued_on, issuer_tax_id, tax_total, amount_total, "
                         "previous_hash, generated_at, hash, source, source_id FROM billing_records ORDER BY id")
        return df

    def verify_billing_chain(self) -> dict:
        with self.db.tx() as cur:
            rows = cur.execute("SELECT * FROM billing_records ORDER BY id").fetchall()
        return verify_chain(rows)
