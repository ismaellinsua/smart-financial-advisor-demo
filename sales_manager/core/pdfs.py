"""PDF documents: invoices and end-of-day cash reports."""

import re
from datetime import date, datetime
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .presets import CURRENCIES
from .pricing import format_money
from .receipts import payment_lines, sale_adjustments

INK = colors.HexColor("#1B2430")
MUTED = colors.HexColor("#667085")
LINE = colors.HexColor("#E4E7EC")
SOFT = colors.HexColor("#F5F7FA")


def _accent(settings: dict) -> colors.Color:
    value = settings.get("accent_color", "")
    return colors.HexColor(value) if re.fullmatch(r"#[0-9A-Fa-f]{6}", value or "") else colors.HexColor("#1F4E79")


def _styles(accent):
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
    return {
        "base": base,
        "muted": ParagraphStyle("muted", parent=base, fontSize=8.5, leading=12, textColor=MUTED),
        "brand": ParagraphStyle("brand", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=22,
                                textColor=accent),
        "doc": ParagraphStyle("doc", parent=base, fontName="Helvetica-Bold", fontSize=15, leading=19,
                              alignment=TA_RIGHT),
        "right": ParagraphStyle("right", parent=base, alignment=TA_RIGHT),
        "label": ParagraphStyle("label", parent=base, fontName="Helvetica-Bold", fontSize=8, leading=11,
                                textColor=MUTED),
        "label_r": ParagraphStyle("label_r", parent=base, fontName="Helvetica-Bold", fontSize=8, leading=11,
                                  textColor=MUTED, alignment=TA_RIGHT),
    }


def _p(text, style) -> Paragraph:
    """Paragraph with user text escaped (reportlab parses a small HTML-like markup)."""
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def _business_block(settings: dict, st) -> list:
    lines = [settings.get(k, "") for k in ("tax_id", "address", "phone", "email") if settings.get(k)]
    return [_p(settings.get("business_name", ""), st["brand"]), *[_p(line, st["muted"]) for line in lines]]


def _header(settings: dict, st, title: str, meta: list[str], accent) -> Table:
    right = [_p(title, st["doc"]), *[_p(m, st["right"]) for m in meta]]
    table = Table([[_business_block(settings, st), right]], colWidths=[105 * mm, 65 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 2, accent),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def _build(story: list, title: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm, title=title)
    doc.build(story)
    return buffer.getvalue()


def invoice_pdf(invoice: dict, settings: dict) -> bytes:
    sale = invoice["sale"]
    accent = _accent(settings)
    st = _styles(accent)
    money = lambda v: format_money(v, CURRENCIES.get(settings.get("currency", "EUR"), "€"))  # noqa: E731
    issued = datetime.fromisoformat(invoice["issued_at"])
    operation = datetime.fromisoformat(sale["created_at"])

    meta = [f"Nº {invoice['number']}", f"Fecha: {issued:%d/%m/%Y}"]
    if operation.date() != issued.date():
        meta.append(f"Fecha de la operación: {operation:%d/%m/%Y}")
    story = [_header(settings, st, "FACTURA", meta, accent), Spacer(1, 8 * mm)]

    customer = [_p("FACTURAR A", st["label"]), _p(invoice["customer_name"], st["base"]),
                _p(f"NIF/CIF: {invoice['customer_tax_id']}", st["base"])]
    for key in ("customer_address", "customer_email"):
        if invoice.get(key):
            customer.append(_p(invoice[key], st["muted"]))
    box = Table([[customer]], colWidths=[170 * mm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [box, Spacer(1, 8 * mm)]

    rows = [[_p("Concepto", st["label"]), _p("Cant.", st["label_r"]), _p("Precio", st["label_r"]),
             _p("Importe", st["label_r"])]]
    for item in sale["items"]:
        rows.append([_p(item["name"], st["base"]), _p(item["quantity"], st["right"]),
                     _p(money(item["unit_price"]), st["right"]),
                     _p(money(item["quantity"] * item["unit_price"]), st["right"])])
        if item.get("line_discount"):
            rows.append([_p(f"   {item.get('promo_name') or 'Promoción'}", st["muted"]), "", "",
                         _p(f"−{money(item['line_discount'])}", st["right"])])
    lines = Table(rows, colWidths=[95 * mm, 20 * mm, 27 * mm, 28 * mm], repeatRows=1)
    lines.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [lines, Spacer(1, 6 * mm)]

    base = sale["subtotal"] - sale["discount"]
    totals = [["Suma de conceptos", money(sale["subtotal"])]]
    totals += [[label, f"−{money(amount)}"] for label, amount in sale_adjustments(sale)]
    totals += [["Base imponible", money(base)], [f"IVA ({sale['tax_rate']:g} %)", money(sale["tax"])]]
    total_rows = [[_p(a, st["base"]), _p(b, st["right"])] for a, b in totals]
    total_rows.append([_p("TOTAL", st["doc"]), _p(money(sale["total"]), st["doc"])])
    table = Table(total_rows, colWidths=[45 * mm, 35 * mm], hAlign="RIGHT")
    table.setStyle(TableStyle([
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [table, Spacer(1, 10 * mm)]

    paid = "; ".join(payment_lines(sale)) or sale["payment_method"]
    story.append(_p(f"Forma de pago: {paid} · Ticket de venta {sale['number']}", st["muted"]))
    if settings.get("receipt_footer"):
        story.append(_p(settings["receipt_footer"], st["muted"]))
    return _build(story, f"Factura {invoice['number']}")


def cash_closing_pdf(closing: dict, settings: dict) -> bytes:
    accent = _accent(settings)
    st = _styles(accent)
    money = lambda v: format_money(v, CURRENCIES.get(settings.get("currency", "EUR"), "€"))  # noqa: E731
    day = date.fromisoformat(closing["day"])
    closed = datetime.fromisoformat(closing["closed_at"])
    story = [_header(settings, st, "CIERRE DE CAJA",
                     [f"Día: {day:%d/%m/%Y}", f"Cerrada: {closed:%d/%m/%Y %H:%M}"], accent),
             Spacer(1, 8 * mm), _p("VENTAS POR FORMA DE PAGO", st["label"]), Spacer(1, 2 * mm)]

    rows = [[_p("Forma de pago", st["label"]), _p("Ventas", st["label_r"]), _p("Importe", st["label_r"])]]
    for method, entry in sorted(closing["breakdown"].items()):
        rows.append([_p(method, st["base"]), _p(entry["count"], st["right"]), _p(money(entry["total"]), st["right"])])
    rows.append([_p("Total", st["label"]), _p(closing["sales_count"], st["right"]),
                 _p(money(closing["total_sales"]), st["right"])])
    refunded = sum(e.get("refunded", 0) for e in closing["breakdown"].values())
    table = Table(rows, colWidths=[90 * mm, 30 * mm, 50 * mm])
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, INK), ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINE),
        ("LINEABOVE", (0, -1), (-1, -1), 1, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(table)
    if refunded:
        story += [Spacer(1, 2 * mm), _p(f"Importes netos: incluyen devoluciones por {money(refunded)}.", st["muted"])]
    story += [Spacer(1, 8 * mm), _p("ARQUEO DE EFECTIVO", st["label"]), Spacer(1, 2 * mm)]

    diff = closing["difference"]
    diff_text = "Cuadra" if abs(diff) < 0.005 else (f"Sobran {money(diff)}" if diff > 0 else f"Faltan {money(-diff)}")
    cash = Table([[_p(a, st["base"]), _p(b, st["right"])] for a, b in [
        ("Fondo inicial", money(closing["opening_float"])),
        ("Ventas en efectivo", money(closing["cash_sales"])),
        ("Efectivo esperado", money(closing["expected_cash"])),
        ("Efectivo contado", money(closing["counted_cash"])),
        ("Diferencia", diff_text),
    ]], colWidths=[90 * mm, 80 * mm])
    cash.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE), ("LINEABOVE", (0, -1), (-1, -1), 1.5, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [cash, Spacer(1, 8 * mm)]
    if closing.get("notes"):
        story += [_p("NOTAS", st["label"]), _p(closing["notes"], st["base"]), Spacer(1, 8 * mm)]
    story += [Spacer(1, 14 * mm), _p("Firma del responsable: ______________________________", st["muted"])]
    return _build(story, f"Cierre de caja {day:%d/%m/%Y}")


def credit_note_pdf(note: dict, settings: dict) -> bytes:
    """Corrective invoice: negative amounts that cancel all or part of an invoice, with the reason."""
    refund, invoice = note["refund"], note["invoice"]
    accent = _accent(settings)
    st = _styles(accent)
    money = lambda v: format_money(v, CURRENCIES.get(settings.get("currency", "EUR"), "€"))  # noqa: E731
    issued = datetime.fromisoformat(note["issued_at"])
    original = datetime.fromisoformat(invoice["issued_at"])
    story = [_header(settings, st, "FACTURA RECTIFICATIVA",
                     [f"Nº {note['number']}", f"Fecha: {issued:%d/%m/%Y}"], accent), Spacer(1, 6 * mm),
             _p(f"Rectifica la factura {invoice['number']} de {original:%d/%m/%Y}. Motivo: {refund['reason']}",
                st["base"]), Spacer(1, 6 * mm)]

    customer = [_p("CLIENTE", st["label"]), _p(invoice["customer_name"], st["base"]),
                _p(f"NIF/CIF: {invoice['customer_tax_id']}", st["base"])]
    if invoice.get("customer_address"):
        customer.append(_p(invoice["customer_address"], st["muted"]))
    box = Table([[customer]], colWidths=[170 * mm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [box, Spacer(1, 8 * mm)]

    rows = [[_p("Concepto devuelto", st["label"]), _p("Cant.", st["label_r"]), _p("Base", st["label_r"])]]
    for item in refund["items"]:
        rows.append([_p(item["name"], st["base"]), _p(f"−{item['quantity']}", st["right"]),
                     _p(f"−{money(item['net_amount'])}", st["right"])])
    lines = Table(rows, colWidths=[110 * mm, 25 * mm, 35 * mm], repeatRows=1)
    lines.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [lines, Spacer(1, 6 * mm)]
    total_rows = [[_p("Base imponible", st["base"]), _p(f"−{money(refund['base'])}", st["right"])],
                  [_p(f"IVA ({refund['tax_rate']:g} %)", st["base"]), _p(f"−{money(refund['tax'])}", st["right"])],
                  [_p("TOTAL", st["doc"]), _p(f"−{money(refund['total'])}", st["doc"])]]
    table = Table(total_rows, colWidths=[45 * mm, 40 * mm], hAlign="RIGHT")
    table.setStyle(TableStyle([
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [table, Spacer(1, 10 * mm),
              _p(f"Devolución {refund['number']} · Ticket original {refund['sale_number']} · "
                 f"Importe devuelto por {refund['method']}", st["muted"])]
    return _build(story, f"Factura rectificativa {note['number']}")


def purchase_order_pdf(po: dict, settings: dict) -> bytes:
    """Order to send to a supplier: products, units and agreed cost."""
    accent = _accent(settings)
    st = _styles(accent)
    money = lambda v: format_money(v, CURRENCIES.get(settings.get("currency", "EUR"), "€"))  # noqa: E731
    created = datetime.fromisoformat(po["created_at"])
    story = [_header(settings, st, "PEDIDO DE COMPRA", [f"Nº {po['number']}", f"Fecha: {created:%d/%m/%Y}"], accent),
             Spacer(1, 8 * mm)]
    supplier = [_p("PROVEEDOR", st["label"]), _p(po.get("supplier_name") or "—", st["base"])]
    for key in ("supplier_tax_id", "supplier_email"):
        if po.get(key):
            supplier.append(_p(po[key], st["muted"]))
    box = Table([[supplier]], colWidths=[170 * mm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [box, Spacer(1, 8 * mm)]
    rows = [[_p("Producto", st["label"]), _p("Unidades", st["label_r"]), _p("Coste unit.", st["label_r"]),
             _p("Importe", st["label_r"])]]
    for item in po["items"]:
        rows.append([_p(item["name"], st["base"]), _p(item["quantity"], st["right"]),
                     _p(money(item["unit_cost"]), st["right"]), _p(money(item["quantity"] * item["unit_cost"]), st["right"])])
    rows.append([_p("Total (sin impuestos)", st["label"]), "", "",
                 _p(money(sum(i["quantity"] * i["unit_cost"] for i in po["items"])), st["right"])])
    table = Table(rows, colWidths=[95 * mm, 22 * mm, 25 * mm, 28 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, INK), ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINE),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [table, Spacer(1, 8 * mm)]
    if po.get("notes"):
        story.append(_p(f"Notas: {po['notes']}", st["muted"]))
    return _build(story, f"Pedido {po['number']}")
