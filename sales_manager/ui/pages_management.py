"""Purchasing (suppliers and purchase orders) and expenses with net profit."""

from datetime import date, timedelta
from functools import partial

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.pdfs import purchase_order_pdf
from core.presets import PAYMENT_METHODS
from core.security import csv_safe
from core.store_purchases import EXPENSE_CATEGORIES, PURCHASE_STATUSES, PURCHASES_CATEGORY
from ui.context import ctx, logged_download
from ui.styles import page_header, style_figure
from core import clock

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]


def _guard(c) -> bool:
    if c.can("encargado"):
        return True
    st.error("No tienes permiso para ver esta sección.", icon=":material/lock:")
    return False


def _flash(key: str) -> None:
    if key in st.session_state:
        st.success(st.session_state.pop(key))


# ------------------------------------------------------------------ purchases
def purchases_page() -> None:
    c = ctx()
    if not _guard(c):
        return
    page_header("Compras y proveedores", "Pide a tus proveedores, recibe la mercancía y el stock y los costes se "
                "actualizan solos.", eyebrow="Gestión")
    _flash("purchase_flash")
    orders_tab, new_tab, suppliers_tab = st.tabs(["Pedidos", "Nuevo pedido", "Proveedores"])
    with orders_tab:
        _orders(c)
    with new_tab:
        _new_order(c)
    with suppliers_tab:
        _suppliers(c)


def _orders(c) -> None:
    df = c.store.purchases()
    if df.empty:
        st.info("No hay pedidos. Crea uno en «Nuevo pedido» o desde Automatizaciones → Reposición inteligente.")
        return
    pending = df[df["status"].isin(["borrador", "enviado"])]
    m1, m2 = st.columns(2)
    m1.metric("Pedidos abiertos", len(pending))
    m2.metric("Importe pendiente de recibir", c.money_short(pending["total"].sum()))
    event = st.dataframe(
        df.assign(status=df["status"].map(PURCHASE_STATUSES)), hide_index=True, width="stretch",
        on_select="rerun", selection_mode="single-row", key="po_table",
        column_order=["number", "created_at", "supplier", "status", "total", "created_by"],
        column_config={"number": "Pedido", "created_at": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY"),
                       "supplier": "Proveedor", "status": "Estado",
                       "total": st.column_config.NumberColumn("Importe", format=f"%.2f {c.symbol}"),
                       "created_by": "Creado por"})
    if not event.selection.rows:
        st.caption("Selecciona un pedido para enviarlo, recibirlo o descargarlo.")
        return
    po = c.store.purchase(int(df.iloc[event.selection.rows[0]]["id"]))
    with st.container(border=True):
        st.markdown(f"#### {po['number']} · {po['supplier_name'] or 'Sin proveedor'} · "
                    f"{PURCHASE_STATUSES[po['status']]}")
        logged_download(st, "Descargar pedido (PDF)", partial(purchase_order_pdf, po, c.settings), f"{po['number']}.pdf",
                        "application/pdf", icon=":material/picture_as_pdf:")
        if po["status"] not in ("borrador", "enviado"):
            st.dataframe(pd.DataFrame(po["items"])[["name", "quantity", "received", "unit_cost"]], hide_index=True,
                         width="stretch", column_config={
                             "name": "Producto", "quantity": "Pedido", "received": "Recibido",
                             "unit_cost": st.column_config.NumberColumn("Coste", format=f"%.2f {c.symbol}")})
            return
        st.markdown("**Recibir mercancía**")
        received = {}
        for item in po["items"]:
            received[item["id"]] = st.number_input(
                f"{item['name']} · pedido {item['quantity']} a {c.money(item['unit_cost'])}", 0,
                item["quantity"] * 10, item["quantity"], key=f"rcv_{po['id']}_{item['id']}")
        a, b = st.columns(2)
        expense = a.toggle("Apuntarlo como gasto", value=True, key=f"rcv_exp_{po['id']}")
        method = b.selectbox("Pagado por", PAYMENT_METHODS, index=PAYMENT_METHODS.index("Transferencia"),
                             key=f"rcv_m_{po['id']}")
        x, y, z = st.columns(3)
        if x.button("Recibir y actualizar stock", type="primary", icon=":material/inventory:",
                    key=f"rcv_btn_{po['id']}", width="stretch"):
            try:
                c.store.receive_purchase(po["id"], received, received_by=c.who, register_expense=expense,
                                         method=method)
            except ValueError as exc:
                st.error(str(exc))
            else:
                c.store.audit(c.username, "pedido_recibido", po["number"])
                st.session_state["purchase_flash"] = f"{po['number']} recibido: stock y costes actualizados."
                st.rerun()
        if po["status"] == "borrador" and y.button("Marcar como enviado", key=f"po_sent_{po['id']}",
                                                   width="stretch"):
            c.store.set_purchase_status(po["id"], "enviado")
            st.rerun()
        if z.button("Cancelar pedido", key=f"po_cancel_{po['id']}", width="stretch"):
            c.store.set_purchase_status(po["id"], "cancelado")
            c.store.audit(c.username, "pedido_cancelado", po["number"])
            st.rerun()


def _new_order(c) -> None:
    suppliers = c.store.suppliers()
    options = {0: "Sin proveedor", **dict(zip(suppliers["id"].astype(int), suppliers["name"]))}
    supplier = st.selectbox("Proveedor", list(options), format_func=options.get, key="po_supplier")
    products = c.store.products()
    if supplier:
        own = products[products["supplier_id"] == supplier]
        products = own if not own.empty else products
    lines = pd.DataFrame({"producto": products["name"], "cantidad": 0, "coste": products["cost"].astype(float),
                          "stock": products["stock"], "product_id": products["id"]})
    edited = st.data_editor(
        lines, hide_index=True, width="stretch", key=f"po_lines_{supplier}",
        disabled=["producto", "stock", "product_id"], column_order=["producto", "stock", "cantidad", "coste"],
        column_config={"producto": "Producto", "stock": "Stock actual",
                       "cantidad": st.column_config.NumberColumn("Pedir", min_value=0, step=1),
                       "coste": st.column_config.NumberColumn("Coste unit.", min_value=0, format=f"%.2f {c.symbol}")})
    chosen = edited[edited["cantidad"] > 0]
    total = float((chosen["cantidad"] * chosen["coste"]).sum())
    notes = st.text_input("Notas para el proveedor", max_chars=500, key="po_notes")
    if st.button(f"Crear pedido · {c.money(total)}", type="primary", disabled=chosen.empty,
                 icon=":material/shopping_cart_checkout:"):
        try:
            po = c.store.create_purchase(supplier or None, [
                {"product_id": int(r["product_id"]), "quantity": int(r["cantidad"]), "unit_cost": float(r["coste"])}
                for _, r in chosen.iterrows()], notes, created_by=c.who, location_id=c.location_id)
        except ValueError as exc:
            st.error(str(exc))
        else:
            number = c.store.purchase(po)["number"]
            c.store.audit(c.username, "pedido_creado", number)
            st.session_state["purchase_flash"] = f"Pedido {number} creado. Descárgalo en «Pedidos» para enviarlo."
            st.rerun()


def _suppliers(c) -> None:
    left, right = st.columns([3, 2], gap="large")
    with left:
        suppliers = c.store.suppliers()
        if suppliers.empty:
            st.info("Sin proveedores todavía.")
        else:
            st.dataframe(suppliers, hide_index=True, width="stretch",
                         column_order=["name", "tax_id", "email", "phone", "notes"],
                         column_config={"name": "Proveedor", "tax_id": "NIF/CIF", "email": "Email",
                                        "phone": "Teléfono", "notes": "Notas"})
            st.markdown("**Proveedor habitual de cada producto**")
            products = c.store.products()
            names = {0: "—", **dict(zip(suppliers["id"].astype(int), suppliers["name"]))}
            table = pd.DataFrame({"id": products["id"], "producto": products["name"],
                                  "proveedor": products["supplier_id"].fillna(0).astype(int).map(names)})
            edited = st.data_editor(table, hide_index=True, width="stretch", key="product_suppliers",
                                    disabled=["id", "producto"], column_order=["producto", "proveedor"],
                                    column_config={"producto": "Producto", "proveedor": st.column_config.SelectboxColumn(
                                        "Proveedor", options=list(names.values()), required=True)})
            if st.button("Guardar proveedores habituales", icon=":material/save:"):
                by_name = {v: k for k, v in names.items()}
                for (_, before), (_, after) in zip(table.iterrows(), edited.iterrows()):
                    if before["proveedor"] != after["proveedor"]:
                        c.store.set_product_supplier(int(after["id"]), by_name.get(after["proveedor"]) or None)
                st.session_state["purchase_flash"] = "Proveedores habituales guardados."
                st.rerun()
    with right, st.container(border=True):
        st.markdown("**Nuevo proveedor**")
        with st.form("new_supplier", clear_on_submit=True, border=False):
            data = {"name": st.text_input("Nombre", max_chars=120), "tax_id": st.text_input("NIF/CIF", max_chars=60),
                    "email": st.text_input("Email", max_chars=254), "phone": st.text_input("Teléfono", max_chars=60),
                    "notes": st.text_area("Notas", max_chars=500, height=70)}
            if st.form_submit_button("Guardar proveedor", type="primary"):
                try:
                    c.store.save_supplier(data)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["purchase_flash"] = f"Proveedor «{data['name']}» guardado."
                    st.rerun()


# -------------------------------------------------------------------- expenses
def _month_bounds(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    return start, (start + timedelta(days=32)).replace(day=1)


def expenses_page() -> None:
    c = ctx()
    if not _guard(c):
        return
    page_header("Gastos y beneficio", "Lo que de verdad ganas: ventas netas, menos lo que te cuesta lo vendido, "
                "menos los gastos del negocio.", eyebrow="Gestión")
    created = c.store.apply_recurring(since=clock.today() - timedelta(days=62))
    if created:
        st.toast(f"Se han apuntado {created} gastos fijos del mes.", icon=":material/autorenew:")
    _flash("expense_flash")

    today = clock.today()
    months = [date(today.year + (today.month - 1 - i) // 12, (today.month - 1 - i) % 12 + 1, 1) for i in range(12)]
    month = st.selectbox("Mes", months, format_func=lambda d: f"{MONTHS[d.month - 1].capitalize()} {d.year}",
                         key="exp_month")
    start, end = _month_bounds(month)
    p = c.store.profit(start, end)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ventas netas", c.money_short(p["net_sales"]), help="Sin impuestos y descontadas las devoluciones.")
    m2.metric("Margen bruto", c.money_short(p["gross"]), help="Ventas netas menos el coste de lo vendido.")
    m3.metric("Gastos", c.money_short(p["opex"]), help="Gastos del negocio. Las compras de mercancía no se cuentan "
                                                       "aquí: ya están dentro del coste de lo vendido.")
    m4.metric("Beneficio neto", c.money_short(p["net"]), f"{p['margin_pct']:.1f} % de las ventas".replace(".", ","),
              delta_color="normal")

    left, right = st.columns([3, 2], gap="large")
    with left, st.container(border=True):
        st.markdown("**Beneficio neto de los últimos 6 meses**")
        series = []
        for m in reversed(months[:6]):
            s, e = _month_bounds(m)
            series.append((f"{MONTHS[m.month - 1][:3]} {str(m.year)[2:]}", c.store.profit(s, e)["net"]))
        accent = c.settings["accent_color"]
        fig = go.Figure(go.Bar(
            x=[x for x, _ in series], y=[y for _, y in series],
            marker_color=[accent if y >= 0 else "#D92D20" for _, y in series],
            text=[c.money_short(y) for _, y in series], textposition="outside",
            hovertemplate="%{x}<br><b>%{y:,.2f} " + c.symbol + "</b><extra></extra>"))
        st.plotly_chart(style_figure(fig, 300), width="stretch", config={"displayModeBar": False})
    with right, st.container(border=True):
        st.markdown("**Gastos del mes por categoría**")
        if p["by_category"].empty:
            st.caption("Sin gastos este mes.")
        for category, amount in p["by_category"].items():
            share = amount / p["opex"] * 100 if p["opex"] else 0
            st.markdown(f"{category} · **{c.money(amount)}**")
            st.progress(min(1.0, share / 100))
        if p["purchases"]:
            st.caption(f"Compras de mercancía este mes: {c.money(p['purchases'])} (no restan dos veces).")

    list_tab, add_tab, fixed_tab = st.tabs(["Gastos del mes", "Apuntar gasto", "Gastos fijos"])
    with list_tab:
        df = c.store.expenses(start, end)
        if df.empty:
            st.caption("No hay gastos este mes.")
        else:
            event = st.dataframe(df, hide_index=True, width="stretch", on_select="rerun",
                                 selection_mode="single-row", key="exp_table",
                                 column_order=["day", "category", "description", "supplier", "method", "amount",
                                               "created_by"],
                                 column_config={"day": st.column_config.DateColumn("Día", format="DD/MM/YYYY"),
                                                "category": "Categoría", "description": "Concepto",
                                                "supplier": "Proveedor", "method": "Pago",
                                                "amount": st.column_config.NumberColumn("Importe", format=f"%.2f {c.symbol}"),
                                                "created_by": "Apuntado por"})
            logged_download(st, "Exportar a CSV", csv_safe(df.drop(columns=["id"])).to_csv(
                index=False, sep=";", decimal=",").encode("utf-8-sig"), "gastos.csv", "text/csv",
                icon=":material/download:")
            if event.selection.rows and st.button("Eliminar el gasto seleccionado", icon=":material/delete:"):
                row = df.iloc[event.selection.rows[0]]
                c.store.delete_expense(int(row["id"]))
                c.store.audit(c.username, "gasto_eliminado", f"{row['description']} · {row['amount']:.2f}")
                st.rerun()
    with add_tab, st.form("new_expense", clear_on_submit=True, border=False):
        a, b = st.columns(2)
        day = a.date_input("Día", clock.today(), format="DD/MM/YYYY")
        category = b.selectbox("Categoría", [x for x in EXPENSE_CATEGORIES if x != PURCHASES_CATEGORY] +
                               [PURCHASES_CATEGORY])
        description = st.text_input("Concepto", max_chars=120, placeholder="Ej.: Factura de la luz de septiembre")
        a, b = st.columns(2)
        amount = a.number_input(f"Importe ({c.symbol})", 0.0, 10_000_000.0, 0.0, step=10.0)
        method = b.selectbox("Pagado por", PAYMENT_METHODS, index=PAYMENT_METHODS.index("Transferencia"))
        with st.expander("Factura del proveedor (para deducir el IVA)", icon=":material/receipt:"):
            st.caption("Con estos datos el gasto entra en el libro de facturas recibidas del Excel para la gestoría.")
            a, b = st.columns(2)
            issuer = a.text_input("Proveedor", max_chars=120)
            issuer_tax_id = b.text_input("NIF del proveedor", max_chars=20)
            invoice_number = a.text_input("Nº de factura", max_chars=40)
            rates = [None, 21.0, 10.0, 5.0, 4.0, 0.0]
            tax_rate = b.selectbox("IVA de la factura", rates, format_func=lambda r: "Sin factura" if r is None
                                   else f"{r:g} %", help="El importe de arriba es el total de la factura, con IVA.")
        if st.form_submit_button("Apuntar gasto", type="primary", icon=":material/add:"):
            try:
                c.store.add_expense(day, category, description, amount, method, created_by=c.who,
                                    invoice_number=invoice_number, issuer_tax_id=issuer_tax_id, issuer_name=issuer,
                                    tax_rate=tax_rate)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["expense_flash"] = "Gasto apuntado."
                st.rerun()
    with fixed_tab:
        st.caption("Se apuntan solos cada mes el día indicado (si el mes es más corto, el último día).")
        fixed = c.store.recurring_expenses()
        for _, r in fixed.iterrows():
            a, b = st.columns([5, 1], vertical_alignment="center")
            a.markdown(f"**{r['description']}** · {r['category']} · {c.money(r['amount'])} el día {int(r['day_of_month'])}")
            on = b.toggle("Activo", value=bool(r["active"]), key=f"fixed_{r['id']}")
            if on != bool(r["active"]):
                c.store.set_recurring_active(int(r["id"]), on)
                st.rerun()
        with st.form("new_fixed", clear_on_submit=True, border=False):
            a, b, d = st.columns([2, 2, 1])
            category = a.selectbox("Categoría", [x for x in EXPENSE_CATEGORIES if x != PURCHASES_CATEGORY])
            description = b.text_input("Concepto", max_chars=120, placeholder="Ej.: Alquiler del local")
            day_of_month = d.number_input("Día", 1, 31, 1)
            amount = st.number_input(f"Importe mensual ({c.symbol})", 0.0, 1_000_000.0, 0.0, step=10.0)
            if st.form_submit_button("Añadir gasto fijo", type="primary"):
                try:
                    c.store.save_recurring(category, description, amount, day_of_month)
                    c.store.apply_recurring()
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["expense_flash"] = "Gasto fijo añadido."
                    st.rerun()


# ------------------------------------------------------------------ gestoría
def accounting_page() -> None:
    from core.accounting import quarter

    c = ctx()
    if not c.can("encargado"):
        st.error("No tienes permiso para ver esta sección.", icon=":material/lock:")
        return
    page_header("Gestoría", "Todo lo que pide tu gestoría cada trimestre: libro de facturas emitidas, resumen de IVA "
                "por tipo, retenciones y gastos, en un Excel.", eyebrow="Gestión")
    first, _ = quarter(clock.today())
    quarters = []
    for _ in range(8):  # this quarter and the seven before
        start, end = quarter(first)
        quarters.append((start, end))
        first = (start - timedelta(days=1)).replace(day=1)
    labels = {q: f"{(q[0].month - 1) // 3 + 1}T {q[0].year}" for q in quarters}
    a, b = st.columns([1, 2])
    today = clock.today()
    filing = (today.month - 1) % 3 == 0 and today.day <= 20  # first 20 days: the previous quarter is being filed
    chosen = a.selectbox("Trimestre", quarters, format_func=labels.get, index=1 if filing else 0,
                         help="El IVA trimestral (modelo 303) se presenta del 1 al 20 del mes siguiente al trimestre.")
    start, end = chosen
    b.caption(f"Del {start:%d/%m/%Y} al {end - timedelta(days=1):%d/%m/%Y}.")
    book, voided = c.store.issued_book(start, end)
    summary = c.store.vat_summary(book)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Facturación", c.money(book["Total"].sum() if not book.empty else 0))
    m2.metric("Base imponible", c.money(book["Base imponible"].sum() if not book.empty else 0))
    m3.metric("IVA repercutido", c.money(book["Cuota IVA"].sum() if not book.empty else 0))
    m4.metric("IRPF retenido", c.money(book["Retención IRPF"].sum() if not book.empty else 0),
              help="Lo que te retuvieron tus clientes en facturas con IRPF (para el modelo 130 si eres autónomo).")
    st.markdown("##### IVA por tipo")
    if summary.empty:
        st.info("No hay ventas en este trimestre.")
    else:
        st.dataframe(summary, hide_index=True, width="stretch", column_config={
            "Tipo IVA %": st.column_config.NumberColumn(format="%.0f %%"),
            **{col: st.column_config.NumberColumn(format=f"%.2f {c.symbol}")
               for col in ("Base imponible", "Cuota IVA", "Total")}})
    received = c.store.received_book(start, end)
    deductible = float(received["Cuota IVA"].sum()) if not received.empty else 0.0
    charged = float(book["Cuota IVA"].sum()) if not book.empty else 0.0
    st.caption(f"IVA soportado en facturas recibidas: **{c.money(deductible)}** ({len(received)} facturas) · "
               f"diferencia orientativa a ingresar: **{c.money(charged - deductible)}**. Es una orientación: "
               "tu gestoría revisa qué IVA es deducible.")
    with st.expander(f"Libro de facturas emitidas ({len(book)} líneas)", icon=":material/menu_book:"):
        st.caption("Los tickets van en un apunte por día y tipo de IVA (con su primer y último número); los de más de "
                   "3.000 € van uno a uno. Un ticket que se cambió por factura se cuenta solo en la factura. Las "
                   "devoluciones y rectificativas restan.")
        st.dataframe(book, hide_index=True, width="stretch")
    if not voided.empty:
        st.caption(f"{len(voided)} ticket(s) anulados en el trimestre: van en una hoja aparte del Excel para que la "
                   "numeración cuadre.")
    name = f"gestoria-{labels[chosen].replace(' ', '-')}.xlsx"
    logged_download(st, "Descargar Excel para la gestoría", lambda: c.store.gestoria_workbook(start, end), name,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary",
                    icon=":material/download:")
    st.caption("Incluye: resumen, libro de facturas emitidas, libro de facturas recibidas (los gastos apuntados con la "
               "factura del proveedor), tickets anulados y todos los gastos.")
