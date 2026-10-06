"""Sales history, refunds and invoices."""

from datetime import datetime, time, timedelta

import pandas as pd
import streamlit as st

from core import clock
from core.db import SaleError
from core.fiscal_id import tax_id_problem
from core.pdfs import credit_note_pdf, invoice_pdf
from core.presets import PAYMENT_METHODS
from core.receipts import receipt_html, refund_receipt_html
from ui.context import ctx, logged_download
from ui.pages_common import csv_bytes
from ui.pages_pos import ticket_actions
from ui.styles import page_header


# ------------------------------------------------------------------- history
@st.dialog("Anular venta")
def _confirm_cancel(sale_id: int, number: str) -> None:
    st.write(f"¿Seguro que quieres anular **{number}**? Las unidades volverán al stock. "
             "La venta se conserva en el historial marcada como anulada.")
    if st.button("Sí, anular", type="primary", width="stretch"):
        c = ctx()
        if not c.can("encargado"):
            st.error("Solo un encargado o el administrador puede anular ventas.")
            return
        try:
            c.store.cancel_sale(sale_id, by=c.who)
        except SaleError as exc:
            st.error(str(exc))
        else:
            c.store.audit(c.username, "venta_anulada", number)
            st.rerun()


@st.dialog("Emitir factura")
def _invoice_dialog(sale_id: int) -> None:
    c = ctx()
    sale = c.store.sale(sale_id)
    customer = {}
    if sale.get("customer_id") is not None:
        found = c.store.customers().query("id == @sale['customer_id']")
        if not found.empty:
            customer = found.iloc[0].to_dict()
    st.caption(f"Venta {sale['number']} · {c.money(sale['total'])}. Revisa los datos fiscales del cliente.")
    name = st.text_input("Nombre o razón social *", customer.get("name", ""), key=f"inv_name_{sale_id}")
    tax_id = st.text_input("NIF / CIF *", customer.get("tax_id", ""), key=f"inv_tax_{sale_id}")
    if tax_id.strip() and (problem := tax_id_problem(tax_id)):
        st.caption(f":orange[{problem}] Si el cliente es de fuera de España, puede ser correcto.")
    address = st.text_input("Dirección fiscal", customer.get("address", ""), key=f"inv_addr_{sale_id}")
    email = st.text_input("Email", customer.get("email", ""), key=f"inv_mail_{sale_id}")
    irpf = st.selectbox("Retención de IRPF", c.store.IRPF_RATES, format_func=lambda r: "Sin retención" if not r
                        else f"{r:g} %", key=f"inv_irpf_{sale_id}",
                        help="Solo si eres profesional y facturas a una empresa o a otro profesional: 15 % en general, "
                             "7 % los primeros años de actividad. El cliente te paga el total menos la retención.")
    invoice = c.store.invoice_for_sale(sale_id)
    slot = st.empty()  # the issue button disappears as soon as the invoice exists
    if invoice is None and slot.button("Emitir factura", type="primary", width="stretch",
                                       icon=":material/request_quote:"):
        try:
            if not c.can("encargado"):
                raise ValueError("Solo un encargado o el administrador puede emitir facturas.")
            customer = {"name": name, "tax_id": tax_id, "address": address, "email": email}
            issued = c.store.create_invoice(sale_id, customer, issued_by=c.who, irpf_rate=irpf)
            c.store.audit(c.username, "factura_emitida", f"{issued['number']} · {sale['number']}")
        except (ValueError, SaleError) as exc:
            st.error(str(exc))
        invoice = c.store.invoice_for_sale(sale_id)
        if invoice is not None:
            slot.empty()
    if invoice is not None:
        full = c.store.invoice(invoice["id"])
        st.success(f"Factura **{full['number']}** emitida.")
        st.download_button("Descargar factura (PDF)", invoice_pdf(full, c.settings), f"{full['number']}.pdf",
                           "application/pdf", type="primary", width="stretch",
                           icon=":material/download:")


def history() -> None:
    c = ctx()
    page_header("Historial de ventas", "Consulta ventas, reimprime tickets, emite facturas, devuelve productos "
                "o anula ventas.", eyebrow="Ventas")
    if not c.can("encargado"):
        _history_sales(c)  # staff: look up and reprint tickets only
        return
    sales_tab, invoices_tab, refunds_tab = st.tabs(["Ventas", "Facturas", "Devoluciones"])
    with sales_tab:
        _history_sales(c)
    with invoices_tab:
        _history_invoices(c)
    with refunds_tab:
        _history_refunds(c)


STAFF_HISTORY_DAYS = 7  # staff see their own tickets of the last week; the business's figures are for managers


def _history_sales(c) -> None:
    staff = not c.can("encargado")
    f1, f2, f3 = st.columns([2, 1, 2])
    earliest = clock.today() - timedelta(days=STAFF_HISTORY_DAYS - 1) if staff else None
    rng = f1.date_input("Fechas", (earliest or clock.today() - timedelta(days=30), clock.today()), format="DD/MM/YYYY",
                        min_value=earliest)
    status = f2.selectbox("Estado", ["Todas", "Completadas", "Anuladas"])
    query = f3.text_input("Buscar", placeholder="Nº de ticket o cliente…")
    if not isinstance(rng, tuple) or len(rng) != 2:
        st.info("Selecciona una fecha de inicio y otra de fin.")
        return
    start = datetime.combine(rng[0], time.min)
    end = datetime.combine(rng[1] + timedelta(days=1), time.min)
    places = {loc["id"]: loc["name"] for loc in c.store.locations(include_inactive=True)}
    where = None
    if c.multi_location and not staff:
        options = [0, *places]
        where = st.selectbox("Local", options, index=options.index(c.location_id) if c.location_id in options else 0,
                             format_func=lambda i: places.get(i, "Todos los locales"), key="history_location") or None
    df = c.store.sales(start, end, location_id=where)
    df["place"] = df["location_id"].map(places).fillna("")
    if staff:
        df = df[df["user_name"] == c.who]
        st.caption(f"Ves tus propias ventas de los últimos {STAFF_HISTORY_DAYS} días.")
    if status == "Completadas":
        df = df[df["status"] == "completada"]
    elif status == "Anuladas":
        df = df[df["status"] == "anulada"]
    if query:
        q = query.lower()
        df = df[df["number"].str.lower().str.contains(q, regex=False)
                | df["customer_name"].str.lower().str.contains(q, regex=False)]

    done = df[df["status"] == "completada"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Ventas", len(done))
    m2.metric("Total facturado", c.money_short(done["total"].sum()))
    m3.metric("Impuestos repercutidos", c.money_short(done["tax"].sum()))

    view = df[["id", "number", "created_at", "customer_name", "payment_method", "total", "status", "user_name",
               "place"]]
    event = st.dataframe(
        view, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        column_order=["number", "created_at", *(["place"] if c.multi_location else []), "customer_name",
                      "payment_method", "total", "user_name", "status"],
        column_config={
            "number": "Ticket", "place": "Local",
            "created_at": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
            "customer_name": "Cliente",
            "payment_method": "Pago",
            "total": st.column_config.NumberColumn("Total", format=f"%.2f {c.symbol}"),
            "user_name": "Atendió",
            "status": "Estado",
        },
    )
    if c.can("encargado"):
        logged_download(st, "Exportar a CSV", csv_bytes(df.drop(columns=["id", "place"])), "ventas.csv", "text/csv",
                           icon=":material/download:")

    rows = event.selection.rows
    if not rows:
        st.caption("Selecciona una venta para ver el detalle.")
        return
    sale = c.store.sale(int(view.iloc[rows[0]]["id"]))
    with st.container(border=True):
        st.markdown(f"#### {sale['number']} · {c.money(sale['total'])}")
        items = pd.DataFrame(sale["items"])
        items["importe"] = items["quantity"] * items["unit_price"]
        st.dataframe(
            items[["name", "quantity", "unit_price", "importe"]], hide_index=True, width="stretch",
            column_config={
                "name": "Concepto", "quantity": "Cant.",
                "unit_price": st.column_config.NumberColumn("Precio", format=f"%.2f {c.symbol}"),
                "importe": st.column_config.NumberColumn("Importe", format=f"%.2f {c.symbol}"),
            },
        )
        invoice = c.store.invoice_for_sale(sale["id"])
        if invoice:
            st.caption(f"Facturada con el número **{invoice['number']}**.")
        with st.expander("Imprimir o enviar el ticket", icon=":material/print:"):
            ticket_actions(c, sale)
        a, b, d = st.columns(3)
        a.download_button("Descargar ticket", receipt_html(sale, c.ticket_settings(sale.get("location_id"))), f"{sale['number']}.html",
                          "text/html", icon=":material/receipt_long:", width="stretch")
        if invoice:
            full = c.store.invoice(invoice["id"])
            b.download_button("Descargar factura", invoice_pdf(full, c.settings), f"{full['number']}.pdf",
                              "application/pdf", icon=":material/request_quote:", width="stretch")
        elif b.button("Emitir factura", disabled=sale["status"] != "completada" or not c.can("encargado"),
                      width="stretch", icon=":material/request_quote:"):
            _invoice_dialog(sale["id"])
        past_refunds = c.store.sale_refunds(sale["id"])
        if past_refunds:
            st.caption("Devoluciones: " + " · ".join(
                f"{r['number']} ({c.money(r['total'])})" + (f", rectificativa {r['credit_note']['number']}"
                                                          if r["credit_note"] else "") for r in past_refunds))
        if d.button("Devolver productos", disabled=sale["status"] != "completada" or not c.can("encargado"),
                    width="stretch", icon=":material/undo:"):
            _refund_dialog(sale["id"])
        if c.can("encargado") and sale["status"] == "completada" and not invoice and not past_refunds:
            if st.button("Anular la venta completa", icon=":material/block:", type="tertiary"):
                _confirm_cancel(sale["id"], sale["number"])




@st.dialog("Devolver productos")
def _refund_dialog(sale_id: int) -> None:
    c = ctx()
    if not c.can("encargado"):
        st.error("Solo un encargado o el administrador puede registrar devoluciones.")
        return
    sale = c.store.sale(sale_id)
    st.caption(f"Venta {sale['number']} · {c.money(sale['total'])}. Elige cuántas unidades devuelves de cada producto.")
    quantities = {}
    for item in c.store.returnable(sale_id):
        if item["remaining"] <= 0:
            st.caption(f"{item['name']}: ya devuelto por completo.")
            continue
        quantities[item["id"]] = st.number_input(
            f"{item['name']} (quedan {item['remaining']} de {item['quantity']})", 0, int(item["remaining"]), 0,
            key=f"refund_{sale_id}_{item['id']}")
    methods = [m for m in PAYMENT_METHODS]
    default = sale["payments"][0]["method"] if sale.get("payments") else sale["payment_method"]
    method = st.selectbox("Devolver el dinero por", methods,
                          index=methods.index(default) if default in methods else 0, key=f"refund_m_{sale_id}")
    reason = st.text_input("Motivo", max_chars=500, placeholder="Ej.: talla equivocada, producto defectuoso…",
                           key=f"refund_r_{sale_id}")
    if c.store.invoice_for_sale(sale_id):
        st.info("La venta está facturada: se emitirá una factura rectificativa automáticamente.",
                icon=":material/request_quote:")
    slot = st.empty()
    if slot.button("Registrar devolución", type="primary", width="stretch", icon=":material/undo:",
                   disabled=not any(quantities.values())):
        try:
            refund = c.store.create_refund(sale_id, quantities, method, reason, user_name=c.who)
        except (ValueError, SaleError) as exc:
            st.error(str(exc))
            return
        slot.empty()
        c.store.audit(c.username, "devolucion", f"{refund['number']} · {sale['number']} · {refund['total']:.2f}")
        st.success(f"Devolución **{refund['number']}** registrada: {c.money(refund['total'])} por {method}.")
        st.download_button("Justificante de devolución", refund_receipt_html(refund, c.settings),
                           f"{refund['number']}.html", "text/html", icon=":material/receipt_long:",
                           width="stretch")
        if refund["credit_note"]:
            note = c.store.credit_note(refund["id"])
            st.download_button(f"Factura rectificativa {note['number']} (PDF)", credit_note_pdf(note, c.settings),
                               f"{note['number']}.pdf", "application/pdf", type="primary",
                               icon=":material/request_quote:", width="stretch")


def _history_refunds(c) -> None:
    df = c.store.refunds()
    if df.empty:
        st.info("Sin devoluciones. Se registran desde una venta del Historial con «Devolver productos».")
        return
    event = st.dataframe(
        df, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        key="refunds_table",
        column_order=["number", "created_at", "sale_number", "reason", "method", "total", "credit_note", "user_name"],
        column_config={
            "number": "Devolución", "created_at": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
            "sale_number": "Ticket", "reason": "Motivo", "method": "Devuelto por",
            "total": st.column_config.NumberColumn("Importe", format=f"%.2f {c.symbol}"),
            "credit_note": "Rectificativa", "user_name": "Registró",
        },
    )
    logged_download(st, "Exportar devoluciones a CSV", csv_bytes(df.drop(columns=["id"])), "devoluciones.csv", "text/csv",
                       icon=":material/download:")
    if event.selection.rows:
        refund = c.store.refund(int(df.iloc[event.selection.rows[0]]["id"]))
        a, b = st.columns(2)
        a.download_button("Justificante", refund_receipt_html(refund, c.settings), f"{refund['number']}.html",
                          "text/html", icon=":material/receipt_long:", width="stretch")
        if refund["credit_note"]:
            note = c.store.credit_note(refund["id"])
            b.download_button(f"Rectificativa {note['number']}", credit_note_pdf(note, c.settings),
                              f"{note['number']}.pdf", "application/pdf", icon=":material/request_quote:",
                              width="stretch")


def _history_invoices(c) -> None:
    df = c.store.invoices()
    if df.empty:
        st.info("Aún no has emitido facturas. Selecciona una venta en la pestaña «Ventas» y pulsa «Emitir factura».")
        return
    event = st.dataframe(
        df, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        key="invoices_table",
        column_order=["number", "issued_at", "customer_name", "customer_tax_id", "sale_number", "total"],
        column_config={
            "number": "Factura",
            "issued_at": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY"),
            "customer_name": "Cliente", "customer_tax_id": "NIF/CIF", "sale_number": "Ticket",
            "total": st.column_config.NumberColumn("Total", format=f"%.2f {c.symbol}"),
        },
    )
    logged_download(st, "Exportar facturas a CSV", csv_bytes(df.drop(columns=["id"])), "facturas.csv", "text/csv",
                       icon=":material/download:")
    rows = event.selection.rows
    if rows:
        full = c.store.invoice(int(df.iloc[rows[0]]["id"]))
        st.download_button(f"Descargar {full['number']} (PDF)", invoice_pdf(full, c.settings),
                           f"{full['number']}.pdf", "application/pdf", type="primary",
                           icon=":material/request_quote:")
    else:
        st.caption("Selecciona una factura para descargarla.")
