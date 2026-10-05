"""PDF documents: invoices and end-of-day cash reports."""

import re
from datetime import date, datetime, timedelta
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .presets import CURRENCIES
from .pricing import format_money
from .receipts import payment_lines, prices_include_vat, sale_adjustments

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


def _qr(record: dict | None, st) -> list:
    """The tax QR code at the start of an invoice (Orden HAC/1177/2024); nothing without a billing record."""
    if not record:
        return []
    from .verifactu import QR_SIZE_MM, qr_png, qr_url

    image = Image(BytesIO(qr_png(qr_url(record))), width=QR_SIZE_MM * mm, height=QR_SIZE_MM * mm)
    table = Table([[image], [_p("QR tributario", st["muted"])]], colWidths=[170 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return [table, Spacer(1, 4 * mm)]


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
    story = [*_qr(invoice.get("billing"), st), _header(settings, st, "FACTURA", meta, accent), Spacer(1, 8 * mm)]

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

    gross = prices_include_vat(sale)
    rows = [[_p("Concepto", st["label"]), _p("Cant.", st["label_r"]),
             _p("Precio (IVA incl.)" if gross else "Precio", st["label_r"]), _p("IVA", st["label_r"]),
             _p("Importe", st["label_r"])]]
    for item in sale["items"]:
        rate = item["tax_rate"] if item.get("tax_rate") is not None else sale["tax_rate"]
        rows.append([_p(item["name"], st["base"]), _p(item["quantity"], st["right"]),
                     _p(money(item["unit_price"]), st["right"]), _p(f"{rate:g} %", st["right"]),
                     _p(money(item["quantity"] * item["unit_price"]), st["right"])])
        if item.get("line_discount"):
            rows.append([_p(f"   {item.get('promo_name') or 'Promoción'}", st["muted"]), "", "", "",
                         _p(f"−{money(item['line_discount'])}", st["right"])])
    lines = Table(rows, colWidths=[80 * mm, 17 * mm, 30 * mm, 15 * mm, 28 * mm], repeatRows=1)
    lines.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [lines, Spacer(1, 6 * mm)]

    totals = [["Suma de conceptos", money(sale["subtotal"])]]
    totals += [[label, f"−{money(amount)}"] for label, amount in sale_adjustments(sale)]
    if gross:
        for t in sale["taxes"]:
            totals += [[f"Base imponible ({t['rate']:g} %)", money(t["base"])],
                       [f"Cuota IVA {t['rate']:g} %", money(t["tax"])]]
    else:  # invoices of sales from before prices included VAT
        totals += [["Base imponible", money(sale["subtotal"] - sale["discount"])],
                   [f"IVA ({sale['tax_rate']:g} %)", money(sale["tax"])]]
    total_rows = [[_p(a, st["base"]), _p(b, st["right"])] for a, b in totals]
    irpf = float(invoice.get("irpf_amount") or 0)
    if irpf:
        total_rows.append([_p("TOTAL FACTURA", st["base"]), _p(money(sale["total"]), st["right"])])
        total_rows.append([_p(f"Retención IRPF ({invoice['irpf_rate']:g} %)", st["base"]),
                           _p(f"−{money(irpf)}", st["right"])])
        total_rows.append([_p("TOTAL A PAGAR", st["doc"]), _p(money(sale["total"] - irpf), st["doc"])])
    else:
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
                     [f"Día: {day:%d/%m/%Y}", f"Cerrada: {closed:%d/%m/%Y %H:%M}",
                      *([f"Local: {settings['location_line']}"] if settings.get("location_line") else [])], accent),
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
    story = [*_qr(note.get("billing"), st), _header(settings, st, "FACTURA RECTIFICATIVA",
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
    total_rows = []
    for t in refund["taxes"]:
        total_rows += [[_p(f"Base imponible ({t['rate']:g} %)", st["base"]), _p(f"−{money(t['base'])}", st["right"])],
                       [_p(f"Cuota IVA {t['rate']:g} %", st["base"]), _p(f"−{money(t['tax'])}", st["right"])]]
    total_rows.append([_p("TOTAL", st["doc"]), _p(f"−{money(refund['total'])}", st["doc"])])
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


def _grid(rows: list, widths: list, accent, total: bool = False, extra: list | None = None) -> Table:
    table = Table(rows, colWidths=[w * mm for w in widths], repeatRows=1)
    style = [("LINEBELOW", (0, 0), (-1, 0), 1, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
             ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
             ("VALIGN", (0, 0), (-1, -1), "TOP")]
    if total:
        style.append(("LINEABOVE", (0, -1), (-1, -1), 1.5, accent))
    table.setStyle(TableStyle(style + (extra or [])))
    return table


def weekly_report_pdf(report: dict, settings: dict) -> bytes:
    """Monday report: how the week went against the one before, what sold, who sold, alerts and what to do."""
    accent = _accent(settings)
    st = _styles(accent)
    money = lambda v: format_money(v, CURRENCIES.get(settings.get("currency", "EUR"), "€"))  # noqa: E731
    minus = lambda v: f"−{money(v)}" if v >= 0.005 else money(0)  # noqa: E731
    pct = lambda v: "—" if v is None else f"{v:+.1f} %".replace(".", ",")  # noqa: E731
    n = report["numbers"]
    start, last = report["start"], report["end"] - timedelta(days=1)
    meta = [f"Del {start:%d/%m} al {last:%d/%m/%Y}"]
    if not report.get("complete", True):
        meta.append("Semana en curso (datos parciales)")
    story = [_header(settings, st, "INFORME SEMANAL", meta, accent), Spacer(1, 7 * mm)]

    def section(title: str) -> None:
        story.extend([Spacer(1, 6 * mm), _p(title, st["label"]), Spacer(1, 2 * mm)])

    section("RESUMEN FRENTE A LA SEMANA ANTERIOR")
    cur, prev, d = n["cur"], n["prev"], n["delta"]
    rows = [[_p("Indicador", st["label"]), _p("Esta semana", st["label_r"]), _p("Anterior", st["label_r"]),
             _p("Variación", st["label_r"])]]
    for label, key, fmt in [("Facturación (con impuestos, neta de devoluciones)", "revenue", money),
                            ("Ventas", "count", str), ("Ticket medio", "ticket", money),
                            ("Margen bruto", "margin", money)]:
        rows.append([_p(label, st["base"]), _p(fmt(cur[key]), st["right"]), _p(fmt(prev[key]), st["right"]),
                     _p(pct(d[key]), st["right"])])
    story.append(_grid(rows, [80, 30, 30, 30], accent))
    if cur["refunds"]:
        story += [Spacer(1, 1.5 * mm), _p(f"Devoluciones de la semana: {money(cur['refunds'])}.", st["muted"])]

    p = report["profit"]
    section("BENEFICIO ESTIMADO DE LA SEMANA")
    rows = [[_p(a, st["base"]), _p(b, st["right"])] for a, b in [
        ("Ventas netas (sin impuestos)", money(p["net_sales"])), ("Margen bruto", money(p["gross"])),
        ("Gastos fijos (parte semanal)", minus(p["fixed"])), ("Otros gastos de la semana", minus(p["variable"])), ("Beneficio neto estimado", money(p["net"]))]]
    story.append(_grid([[_p("Concepto", st["label"]), _p("Importe", st["label_r"])], *rows], [120, 50], accent,
                       total=True))

    section("VENTAS POR DÍA")
    rows = [[_p("Día", st["label"]), _p("Ventas", st["label_r"]), _p("Facturación", st["label_r"])]]
    for name, day, count, total in n["by_day"]:
        rows.append([_p(f"{name} {day:%d/%m}", st["base"]), _p(count, st["right"]), _p(money(total), st["right"])])
    story.append(_grid(rows, [90, 30, 50], accent))

    if not n["top"].empty:
        section("LO MÁS VENDIDO")
        rows = [[_p("Producto", st["label"]), _p("Uds.", st["label_r"]), _p("Ventas netas", st["label_r"]),
                 _p("Margen", st["label_r"])]]
        for name, r in n["top"].iterrows():
            rows.append([_p(name, st["base"]), _p(f"{r['units']:g}", st["right"]), _p(money(r["revenue"]), st["right"]),
                         _p(money(r["margin"]), st["right"])])
        story.append(_grid(rows, [90, 20, 30, 30], accent))

    if not n["team"].empty:
        section("VENTAS POR PERSONA")
        rows = [[_p("Persona", st["label"]), _p("Ventas", st["label_r"]), _p("Facturación", st["label_r"])]]
        for who, r in n["team"].iterrows():
            rows.append([_p(who, st["base"]), _p(int(r["count"]), st["right"]), _p(money(r["sum"]), st["right"])])
        story.append(_grid(rows, [90, 30, 50], accent))

    summary = report["abc_summary"]
    section("ANÁLISIS ABC · ÚLTIMOS 30 DÍAS")
    rows = [[_p("Clase", st["label"]), _p("Productos", st["label_r"]), _p("% del margen", st["label_r"]),
             _p("Productos clave", st["label"])]]
    for k, text in [("A", "Imprescindibles"), ("B", "Complementarios"), ("C", "Poco peso")]:
        names = ", ".join(report["abc"][report["abc"]["abc"] == k]["name"].head(4))
        rows.append([_p(f"{k} · {text}", st["base"]), _p(summary[k]["count"], st["right"]),
                     _p(f"{summary[k]['margin_share']:.0f} %", st["right"]), _p(names or "—", st["muted"])])
    story.append(_grid(rows, [38, 22, 25, 85], accent, extra=[("LEFTPADDING", (3, 0), (3, -1), 10)]))

    closings = report["closings"]
    if not closings.empty:
        section("CIERRES DE CAJA")
        rows = [[_p("Día", st["label"]), _p("Esperado", st["label_r"]), _p("Contado", st["label_r"]),
                 _p("Diferencia", st["label_r"])]]
        for _, r in closings.sort_values("day").iterrows():
            rows.append([_p(f"{date.fromisoformat(str(r['day'])[:10]):%d/%m}", st["base"]),
                         _p(money(r["expected_cash"]), st["right"]), _p(money(r["counted_cash"]), st["right"]),
                         _p(money(r["difference"]), st["right"])])
        story.append(_grid(rows, [70, 33, 33, 34], accent))

    if report["alerts"]:
        section("ALERTAS")
        for a in report["alerts"]:
            story += [_p(f"[{a['level'].upper()}] {a['title']}", st["base"]), _p(a["detail"], st["muted"]),
                      Spacer(1, 1.5 * mm)]

    if report["recommendations"]:
        section("RECOMENDACIONES PARA ESTA SEMANA")
        for i, rec in enumerate(report["recommendations"], 1):
            story += [_p(f"{i}. {rec}", st["base"]), Spacer(1, 1.2 * mm)]
    return _build(story, f"Informe semanal {start:%d-%m-%Y}")
