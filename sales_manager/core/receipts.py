"""Printable HTML receipts."""

import re
from datetime import datetime
from html import escape

from .presets import CURRENCIES
from .pricing import format_money

RECEIPT_PAPERS = {"a4": "Hoja A4 (cualquier impresora)", "80": "Ticket térmico de 80 mm", "58": "Ticket térmico de 58 mm"}


def _paper_css(paper: str) -> str:
    """Thermal rolls: one narrow column, no shadows or margins, printed at the roll's width."""
    if paper not in ("80", "58"):
        return ""
    width = int(paper) - 6  # printable width of the roll
    return f"""
  @page {{ size: {paper}mm auto; margin: 2mm 3mm; }}
  body {{ background: #fff; font-size: 12px; }}
  .sheet {{ width: {width}mm; max-width: {width}mm; margin: 0 auto; padding: 0; box-shadow: none; border-radius: 0; }}
  header {{ display: block; text-align: center; padding-bottom: 8px; border-bottom-width: 1px; }}
  header .doc {{ text-align: center; margin-top: 6px; }}
  h1 {{ font-size: 16px; }} .doc strong {{ font-size: 14px; }}
  .meta {{ display: block; margin: 10px 0; font-size: 12px; }} .meta > div {{ text-align: left !important; }}
  table {{ font-size: 11px; }} th, td {{ padding: 4px 0; }}
  .totals {{ width: 100%; }} .grand td {{ font-size: 15px; }}
  .qr {{ text-align: center; }} .qr img {{ margin: 0 auto; }}
  footer {{ margin-top: 14px; }}"""


def whatsapp_number(phone: str) -> str:
    """wa.me needs the number with its country code and digits only; Spanish numbers may come without it."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    return "34" + digits if len(digits) == 9 and digits[0] in "6789" else digits


def receipt_text(sale: dict, settings: dict) -> str:
    """Short plain-text ticket to send by WhatsApp or email."""
    symbol = CURRENCIES.get(settings.get("currency", "EUR"), "€")
    money = lambda v: format_money(v, symbol)  # noqa: E731
    when = datetime.fromisoformat(sale["created_at"]).strftime("%d/%m/%Y %H:%M")
    lines = [settings.get("business_name", ""), f"Ticket {sale['number']} · {when}", ""]
    lines += [f"{i['quantity']} x {i['name']}  {money(i['quantity'] * i['unit_price'])}" for i in sale["items"]]
    lines += ["", f"Total: {money(sale['total'])} ({sale['payment_method']})"]
    if settings.get("tax_id"):
        lines.append(f"NIF {settings['tax_id']}")
    if settings.get("receipt_footer"):
        lines += ["", settings["receipt_footer"]]
    return "\n".join(lines)


def with_print_button(html: str) -> str:
    """The ticket preview with a button that opens the browser's print dialog (hidden on paper)."""
    button = ("<div class='no-print' style='position:sticky;top:0;z-index:2;background:#f5f7fa;padding:8px;"
              "text-align:center'><button onclick='window.print()' style='font:600 15px Inter,Arial,sans-serif;"
              "padding:12px 28px;min-height:44px;border:0;border-radius:10px;background:#1F4E79;color:#fff;"
              "cursor:pointer'>Imprimir ticket</button></div>")
    return (html.replace("</style>", "@media print { .no-print { display: none !important; } }</style>", 1)
                .replace("<body>", "<body>" + button, 1))


def sale_adjustments(sale: dict) -> list[tuple[str, float]]:
    """Discount lines of a sale, in the order they were applied: promotions, manual discount, points."""
    promo = float(sale.get("promo_discount") or 0)
    loyalty = float(sale.get("loyalty_discount") or 0)
    manual = round(float(sale.get("discount") or 0) - promo - loyalty, 2)
    rows = []
    if promo:
        rows.append(("Promociones", promo))
    if manual > 0:
        rows.append((f"Descuento ({sale['discount_pct']:g} %)", manual))
    if loyalty:
        rows.append((f"Canje de {sale.get('points_redeemed', 0)} puntos", loyalty))
    return rows


def prices_include_vat(sale: dict) -> bool:
    """Sales since per-product VAT store each line's VAT; older ones priced without VAT and added it at the end."""
    return bool(sale.get("items")) and all(i.get("tax_amount") is not None for i in sale["items"])


def vat_rows(taxes: list[dict]) -> list[tuple[str, float, float]]:
    """(label, base, VAT) per rate, e.g. («IVA 10 %», 4.09, 0.41)."""
    return [(f"IVA {t['rate']:g} %", t["base"], t["tax"]) for t in taxes]


def payment_lines(sale: dict) -> list[str]:
    """Plain-text description of how a sale was paid, with the change given in cash."""
    out = []
    for pay in sale.get("payments") or []:
        text = f"{pay['method']}: {pay['amount']:.2f}"
        if pay.get("tendered") and pay["tendered"] > pay["amount"]:
            text += f" (entregado {pay['tendered']:.2f}, cambio {pay['tendered'] - pay['amount']:.2f})"
        out.append(text.replace(".", ","))
    return out


def qr_block(record: dict | None) -> str:
    """The tax QR code (Orden HAC/1177/2024), placed at the start of the document; empty without a billing record."""
    if not record:
        return ""
    from .verifactu import QR_SIZE_MM, qr_svg_data_uri, qr_url

    return (f"<div class='qr' style='margin-bottom:16px'><img src='{qr_svg_data_uri(qr_url(record))}' "
            f"alt='Código QR tributario' style='width:{QR_SIZE_MM}mm;height:{QR_SIZE_MM}mm;display:block'>"
            "<div style='font-size:11px;color:#667085'>QR tributario</div></div>")


def receipt_html(sale: dict, settings: dict, paper: str | None = None) -> str:
    paper = paper or settings.get("receipt_paper", "a4")
    symbol = CURRENCIES.get(settings.get("currency", "EUR"), "€")
    money = lambda v: format_money(v, symbol)  # noqa: E731
    accent = settings.get("accent_color", "")
    accent = accent if re.fullmatch(r"#[0-9A-Fa-f]{6}", accent or "") else "#1F4E79"
    when = datetime.fromisoformat(sale["created_at"]).strftime("%d/%m/%Y %H:%M")

    rows = "".join(
        f"<tr><td>{escape(i['name'])}</td><td class='n'>{i['quantity']}</td>"
        f"<td class='n'>{money(i['unit_price'])}</td><td class='n'>{money(i['quantity'] * i['unit_price'])}</td></tr>"
        + (f"<tr class='promo'><td colspan='3'>↳ {escape(i.get('promo_name') or 'Promoción')}</td>"
           f"<td class='n'>−{money(i['line_discount'])}</td></tr>" if i.get("line_discount") else "")
        for i in sale["items"]
    )
    business_lines = " · ".join(
        escape(settings[k]) for k in ("tax_id", "address", "phone", "email") if settings.get(k)
    )
    if settings.get("location_line"):  # a business with several locations: where it was sold
        business_lines += f"<br>Local: {escape(settings['location_line'])}"
    customer = escape(sale.get("customer_name") or "Cliente general")
    if sale.get("customer_tax_id"):
        customer += f"<br><span class='muted'>{escape(sale['customer_tax_id'])}</span>"
    discount_row = "".join(
        f"<tr><td>{escape(label)}</td><td class='n'>−{money(amount)}</td></tr>" for label, amount in sale_adjustments(sale)
    )
    if prices_include_vat(sale):
        tax_block = (f"<tr class='grand'><td>Total</td><td class='n'>{money(sale['total'])}</td></tr>"
                     + "".join(f"<tr class='muted'><td>{escape(label)} incluido (base {money(base)})</td>"
                               f"<td class='n'>{money(vat)}</td></tr>" for label, base, vat in vat_rows(sale["taxes"])))
    else:  # sales from before prices included VAT
        tax_block = (f"<tr><td>Impuestos ({sale['tax_rate']:g} %)</td><td class='n'>{money(sale['tax'])}</td></tr>"
                     f"<tr class='grand'><td>Total</td><td class='n'>{money(sale['total'])}</td></tr>")
    paid = "".join(f"<div>{escape(line)} {escape(symbol)}</div>" for line in payment_lines(sale))
    points = (f"<div>Puntos ganados con esta compra: <b>{sale['points_earned']}</b></div>"
              if sale.get("points_earned") else "")
    void = "<div class='void'>ANULADA</div>" if sale.get("status") == "anulada" else ""

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>{escape(sale['number'])} · {escape(settings.get('business_name', ''))}</title>
<style>
  body {{ font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif; color: #1b2430; margin: 0; background: #f5f7fa; }}
  .sheet {{ max-width: 720px; margin: 32px auto; background: #fff; padding: 48px; border-radius: 12px;
           box-shadow: 0 4px 24px rgba(16,24,40,.08); position: relative; }}
  header {{ display: flex; justify-content: space-between; align-items: flex-start;
            border-bottom: 3px solid {accent}; padding-bottom: 20px; }}
  h1 {{ margin: 0; font-size: 24px; color: {accent}; letter-spacing: -.02em; }}
  .muted {{ color: #667085; font-size: 13px; }}
  .doc {{ text-align: right; }} .doc strong {{ font-size: 18px; }}
  .meta {{ display: flex; justify-content: space-between; margin: 24px 0; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ text-align: left; color: #667085; font-weight: 600; border-bottom: 1px solid #e4e7ec; padding: 10px 0; }}
  td {{ padding: 10px 0; border-bottom: 1px solid #f2f4f7; }}
  .n {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .totals {{ width: 280px; margin-left: auto; margin-top: 16px; }}
  .totals td {{ border: 0; padding: 4px 0; }}
  .grand td {{ font-size: 18px; font-weight: 700; color: {accent}; border-top: 2px solid {accent}; padding-top: 10px; }}
  .promo td {{ color: #067647; font-size: 13px; border-bottom: 0; padding-top: 0; }}
  .pay {{ margin-top: 20px; font-size: 13px; line-height: 1.6; }}
  footer {{ margin-top: 40px; text-align: center; }}
  .void {{ position: absolute; top: 40%; left: 0; right: 0; text-align: center; font-size: 72px; font-weight: 800;
           color: rgba(217,45,32,.18); transform: rotate(-18deg); pointer-events: none; }}
  @media print {{ body {{ background: #fff; }} .sheet {{ box-shadow: none; margin: 0; }} }}{_paper_css(paper)}
</style></head>
<body><div class="sheet">{void}{qr_block(sale.get("billing"))}
<header>
  <div><h1>{escape(settings.get('business_name', ''))}</h1><div class="muted">{business_lines}</div></div>
  <div class="doc"><div class="muted">Ticket de venta</div><strong>{escape(sale['number'])}</strong>
  <div class="muted">{when}</div></div>
</header>
<div class="meta"><div><div class="muted">Cliente</div>{customer}</div>
<div style="text-align:right"><div class="muted">Forma de pago</div>{escape(sale['payment_method'])}</div></div>
<table><thead><tr><th>Concepto</th><th class="n">Cant.</th><th class="n">Precio</th><th class="n">Importe</th></tr></thead>
<tbody>{rows}</tbody></table>
<table class="totals">
  <tr><td>Subtotal</td><td class="n">{money(sale['subtotal'])}</td></tr>
  {discount_row}
  {tax_block}
</table>
<div class="pay muted">{paid}{points}</div>
<footer class="muted">{escape(settings.get('receipt_footer', ''))}</footer>
</div></body></html>"""


def refund_receipt_html(refund: dict, settings: dict) -> str:
    """Simple printable proof of a return for the customer."""
    symbol = CURRENCIES.get(settings.get("currency", "EUR"), "€")
    money = lambda v: format_money(v, symbol)  # noqa: E731
    when = datetime.fromisoformat(refund["created_at"]).strftime("%d/%m/%Y %H:%M")
    def amount(i):  # what the customer gets back for the line, VAT included
        rate = i["tax_rate"] if i.get("tax_rate") is not None else refund["tax_rate"]
        vat = i["tax_amount"] if i.get("tax_amount") is not None else round(i["net_amount"] * rate / 100, 2)
        return i["net_amount"] + vat
    rows = "".join(f"<tr><td>{escape(i['name'])}</td><td class='n'>{i['quantity']}</td>"
                   f"<td class='n'>−{money(amount(i))}</td></tr>" for i in refund["items"])
    vat_lines = " · ".join(f"{label}: −{money(vat)} (base −{money(base)})"
                           for label, base, vat in vat_rows(refund.get("taxes") or []))
    note = (f"<p>Factura rectificativa: <b>{escape(refund['credit_note']['number'])}</b></p>"
            if refund.get("credit_note") else "")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>{escape(refund['number'])}</title>
<style>body {{ font-family: Arial, sans-serif; max-width: 560px; margin: 32px auto; color: #1b2430; }}
table {{ width: 100%; border-collapse: collapse; }} td, th {{ padding: 6px 0; border-bottom: 1px solid #eee; }}
.n {{ text-align: right; }} .total {{ font-size: 20px; font-weight: 700; text-align: right; margin-top: 12px; }}
.muted {{ color: #667085; font-size: 13px; }}</style></head><body>{qr_block(refund.get("billing"))}
<h2>{escape(settings.get('business_name', ''))}</h2>
<p><b>Devolución {escape(refund['number'])}</b> · {when}<br>
<span class="muted">Ticket original {escape(refund['sale_number'])} · Motivo: {escape(refund['reason'])}</span></p>
<table><tr><th align="left">Concepto</th><th class="n">Cant.</th><th class="n">Importe</th></tr>{rows}</table>
<p class="muted">{vat_lines}</p>
<div class="total">Devuelto: {money(refund['total'])}</div>
<p class="muted">Forma de devolución: {escape(refund['method'])}</p>{note}
</body></html>"""
