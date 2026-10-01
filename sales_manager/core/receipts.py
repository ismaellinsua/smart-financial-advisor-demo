"""Printable HTML receipts."""

import re
from datetime import datetime
from html import escape

from .presets import CURRENCIES
from .pricing import format_money


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


def payment_lines(sale: dict) -> list[str]:
    """Plain-text description of how a sale was paid, with the change given in cash."""
    out = []
    for pay in sale.get("payments") or []:
        text = f"{pay['method']}: {pay['amount']:.2f}"
        if pay.get("tendered") and pay["tendered"] > pay["amount"]:
            text += f" (entregado {pay['tendered']:.2f}, cambio {pay['tendered'] - pay['amount']:.2f})"
        out.append(text.replace(".", ","))
    return out


def receipt_html(sale: dict, settings: dict) -> str:
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
    customer = escape(sale.get("customer_name") or "Cliente general")
    if sale.get("customer_tax_id"):
        customer += f"<br><span class='muted'>{escape(sale['customer_tax_id'])}</span>"
    discount_row = "".join(
        f"<tr><td>{escape(label)}</td><td class='n'>−{money(amount)}</td></tr>" for label, amount in sale_adjustments(sale)
    )
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
  @media print {{ body {{ background: #fff; }} .sheet {{ box-shadow: none; margin: 0; }} }}
</style></head>
<body><div class="sheet">{void}
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
  <tr><td>Impuestos ({sale['tax_rate']:g} %)</td><td class="n">{money(sale['tax'])}</td></tr>
  <tr class="grand"><td>Total</td><td class="n">{money(sale['total'])}</td></tr>
</table>
<div class="pay muted">{paid}{points}</div>
<footer class="muted">{escape(settings.get('receipt_footer', ''))}</footer>
</div></body></html>"""
