"""VERI*FACTU billing records: the fields and chained SHA-256 fingerprint (huella) required by the Spanish tax
agency (Real Decreto 1007/2023 and Orden HAC/1177/2024).

Pure functions: storage, locking and immutability live in `store_billing.py`. Sending the records to the AEAT and the
QR code are later steps; until they exist this is not yet a complete VERI*FACTU system.
"""

import hashlib
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode

# Invoice types (TipoFactura) used by the app.
INVOICE_TYPES = {
    "F1": "Factura completa",
    "F2": "Factura simplificada (ticket)",
    "F3": "Factura completa que sustituye a una simplificada",
    "R1": "Rectificativa (art. 80 Uno, Dos y Seis LIVA)",
    "R5": "Rectificativa de factura simplificada",
}


# AEAT services that check the QR printed on invoices. Records are not sent to the AEAT yet, so the app works as a
# «no VERI*FACTU» system: its QR goes to the NoVerifactu address and invoices must not carry the «VERI*FACTU» legend.
SENDS_TO_AEAT = False
QR_HOSTS = {"produccion": "https://www2.agenciatributaria.gob.es", "pruebas": "https://prewww2.aeat.es"}
QR_PATHS = {True: "/wlpl/TIKE-CONT/ValidarQR", False: "/wlpl/TIKE-CONT/ValidarQRNoVerifactu"}
QR_SIZE_MM = 35  # the specification asks for 30 to 40 mm


def amount(value) -> str:
    """Amounts with two decimals and a point, as in the records: 12.35, -3.00."""
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def issue_date(when: datetime) -> str:
    return when.strftime("%d-%m-%Y")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def alta_hash(nif: str, number: str, issued_on: str, invoice_type: str, tax_total: str, amount_total: str,
              previous: str, generated_at: str) -> str:
    """Fingerprint of an issue record (registro de alta), chained to the previous record's fingerprint."""
    fields = [("IDEmisorFactura", nif), ("NumSerieFactura", number), ("FechaExpedicionFactura", issued_on),
              ("TipoFactura", invoice_type), ("CuotaTotal", tax_total), ("ImporteTotal", amount_total),
              ("Huella", previous), ("FechaHoraHusoGenRegistro", generated_at)]
    return _sha256("&".join(f"{k}={str(v).strip()}" for k, v in fields))


def anulacion_hash(nif: str, number: str, issued_on: str, previous: str, generated_at: str) -> str:
    """Fingerprint of a cancellation record (registro de anulación)."""
    fields = [("IDEmisorFacturaAnulada", nif), ("NumSerieFacturaAnulada", number),
              ("FechaExpedicionFacturaAnulada", issued_on), ("Huella", previous),
              ("FechaHoraHusoGenRegistro", generated_at)]
    return _sha256("&".join(f"{k}={str(v).strip()}" for k, v in fields))


def record_hash(row: dict, previous: str) -> str:
    """Recompute a stored record's fingerprint from its own fields and the previous one's."""
    if row["kind"] == "anulacion":
        return anulacion_hash(row["issuer_tax_id"], row["number"], row["issued_on"], previous, row["generated_at"])
    return alta_hash(row["issuer_tax_id"], row["number"], row["issued_on"], row["invoice_type"], row["tax_total"],
                     row["amount_total"], previous, row["generated_at"])


def verify_chain(rows: list[dict]) -> dict:
    """Walk the records in order: each must point to the previous fingerprint and match its own contents."""
    previous = ""
    for i, row in enumerate(rows):
        if row["previous_hash"] != previous:
            return {"ok": False, "checked": i, "broken_at": row["id"], "reason": "la cadena está rota"}
        if record_hash(row, previous) != row["hash"]:
            return {"ok": False, "checked": i, "broken_at": row["id"], "reason": "un registro ha sido alterado"}
        previous = row["hash"]
    return {"ok": True, "checked": len(rows), "broken_at": None, "reason": ""}


def qr_url(record: dict, environment: str = "produccion") -> str:
    """Address encoded in an invoice's tax QR code: issuer, number, date and total of its billing record."""
    query = urlencode({"nif": record["issuer_tax_id"], "numserie": record["number"], "fecha": record["issued_on"],
                       "importe": record["amount_total"]})
    return f"{QR_HOSTS[environment]}{QR_PATHS[SENDS_TO_AEAT]}?{query}"


def qr_code(url: str):
    import segno

    return segno.make_qr(url, error="m")  # ISO/IEC 18004, error correction level M as required


def qr_svg_data_uri(url: str) -> str:
    return qr_code(url).svg_data_uri(scale=4, border=2)


def qr_png(url: str) -> bytes:
    import io

    out = io.BytesIO()
    qr_code(url).save(out, kind="png", scale=8, border=2)
    return out.getvalue()
