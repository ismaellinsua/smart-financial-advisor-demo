"""Application pages."""

from datetime import date, datetime, time, timedelta
from html import escape
from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from core import automation
from core.db import FISCAL_DATA_MESSAGE, FiscalDataError, SaleError
from core.presets import CURRENCIES, PAYMENT_METHODS, PRESETS
from core.security import ROLES, csv_safe, new_totp_secret, totp_uri
from core.pdfs import cash_closing_pdf, credit_note_pdf, invoice_pdf
from core.receipts import (RECEIPT_PAPERS, receipt_html, receipt_text, refund_receipt_html, whatsapp_number,
                           with_print_button)
from ui import pages_intel
from ui.checkout import checkout_panel
from ui.context import PAGES, ctx, get_store
from ui.styles import insight, page_header, pos_mobile_css, style_figure
from core import clock

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _today_label() -> str:
    d = clock.today()
    return f"{automation.WEEKDAYS[d.weekday()].capitalize()}, {d.day} de {MONTHS[d.month - 1]} de {d.year}"


def _pct(value: float, signed: bool = False) -> str:
    return (f"{value:+.1f}" if signed else f"{value:.1f}").replace(".", ",") + " %"


def _delta(value) -> str | None:
    return None if value is None else _pct(value, signed=True)


def _require(c, role: str) -> bool:
    """Second line of defence: pages also check the role, not only the menu."""
    if c.can(role):
        return True
    st.error("No tienes permiso para ver esta sección.", icon=":material/lock:")
    return False


def _csv(df: pd.DataFrame) -> bytes:
    # UTF-8 with BOM and semicolons so it opens cleanly in Spanish-locale Excel.
    return csv_safe(df).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


# ---------------------------------------------------------------- onboarding
def onboarding() -> None:
    store = get_store()
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header(
            "Bienvenido a tu Gestor de Ventas",
            "Configura tu negocio en un minuto. Podrás cambiar todo después en Configuración.",
            eyebrow="Primeros pasos",
        )
        with st.form("onboarding"):
            name = st.text_input("Nombre del negocio", placeholder="Ej.: Café Aurora")
            business_type = st.selectbox(
                "Tipo de negocio", list(PRESETS), format_func=lambda k: PRESETS[k]["label"]
            )
            currency = st.selectbox("Moneda", list(CURRENCIES))
            demo = st.toggle("Cargar datos de ejemplo (solo para probar)", value=False,
                             help="60 días de ventas inventadas para explorar la app. Déjalo apagado si vas a "
                                  "vender de verdad: los datos de ejemplo se borran al empezar.")
            if st.form_submit_button("Crear mi espacio", type="primary", use_container_width=True):
                store.save_settings({"business_name": name.strip() or "Mi Negocio", "currency": currency})
                with st.spinner("Preparando tu catálogo…"):
                    store.load_preset(business_type, with_demo_sales=demo)
                st.rerun()


@st.dialog("Cambiar de negocio")
def switch_business_dialog() -> None:
    c = ctx()
    types = list(PRESETS)
    business_type = st.radio(
        "¿Qué tipo de negocio quieres?", types, index=types.index(c.settings["business_type"]),
        format_func=lambda k: PRESETS[k]["label"],
        captions=[PRESETS[k]["description"] for k in types], key="switch_type",
    )
    # Keep the current name for the current type; other types suggest a ready-made demo name.
    default_name = (c.settings["business_name"] if business_type == c.settings["business_type"]
                    else PRESETS[business_type]["demo_name"])
    name = st.text_input("Nombre del negocio", default_name, key=f"switch_name_{business_type}")
    demo = st.toggle("Cargar datos de ejemplo para probar", value=c.store.is_demo(), key="switch_demo")
    st.warning("Se reemplazarán el catálogo, los clientes y las ventas actuales por los del nuevo negocio.",
               icon=":material/warning:")
    st.download_button(
        "Antes, descargar una copia de mis datos", c.store.backup_bytes(), f"ventas-{clock.today():%Y-%m-%d}.db",
        "application/octet-stream", icon=":material/download:", use_container_width=True,
    )
    if st.button(f"Cambiar a «{PRESETS[business_type]['label']}»", type="primary", use_container_width=True,
                 icon=":material/swap_horiz:"):
        if not c.can("admin"):
            st.error("Solo el administrador puede cambiar de negocio.")
            return
        try:
            with st.spinner("Preparando el nuevo negocio…"):
                c.store.load_preset(business_type, with_demo_sales=demo)
        except FiscalDataError as exc:
            st.error(str(exc))
            return
        c.store.save_settings({"business_name": name.strip() or c.settings["business_name"]})
        c.store.audit(c.username, "negocio_cambiado", f"{PRESETS[business_type]['label']} · {name}")
        st.session_state.pop("cart", None)
        st.rerun()


def demo_banner(c) -> None:
    """Demonstration data is disposable: say so on every page and let the administrator start for real."""
    text, action = st.columns([5, 2], vertical_alignment="center")
    text.warning("**Modo demostración.** Los datos son de ejemplo y todo lo que vendas aquí se borrará al empezar "
                 "de verdad.", icon=":material/science:")
    if c.can("admin") and action.button("Empezar a vender de verdad", type="primary", use_container_width=True,
                                        icon=":material/rocket_launch:"):
        _start_for_real_dialog()


@st.dialog("Empezar a vender de verdad")
def _start_for_real_dialog() -> None:
    st.write("Se borrarán los datos de ejemplo (productos, clientes, ventas, facturas y cierres) y configurarás tu "
             "negocio desde cero. A partir de ahí, las ventas y facturas reales **no se podrán borrar**: la ley obliga "
             "a conservarlas.")
    if st.checkbox("Entiendo que se borrarán los datos de ejemplo", key="start_real_confirm") and st.button(
            "Borrar ejemplos y empezar", type="primary", use_container_width=True):
        c = ctx()
        if not c.can("admin"):
            st.error("Solo el administrador puede hacerlo.")
            return
        c.store.reset()
        c.store.audit(c.username, "datos_de_ejemplo_borrados")
        st.session_state.pop("cart", None)
        st.rerun()


# ----------------------------------------------------------------- dashboard
def dashboard() -> None:
    c = ctx()
    if not _require(c, "encargado"):
        return
    page_header("Panel de ventas", f"Así va {c.settings['business_name']}", eyebrow=_today_label())

    pages_intel.report_card(c)
    period = st.segmented_control(
        "Periodo", [7, 30, 90], default=30, format_func=lambda d: f"Últimos {d} días",
        label_visibility="collapsed", key="dash_period",
    ) or 30
    start, end, prev_start = automation.period_bounds(period)
    sales = c.store.sales(start=prev_start)
    lines = c.store.sale_lines(start=prev_start)
    refunds = c.store.refunds(start=prev_start)
    k = automation.kpis(sales, lines, start, end, prev_start, refunds)

    m1, m2, m3, m4 = st.columns(4)
    vs = f"Variación frente a los {period} días anteriores."
    m1.metric("Facturación", c.money_short(k["revenue"]), _delta(k["revenue_delta"]), help=f"Impuestos incluidos. {vs}")
    m2.metric("Ventas", f"{k['count']}", _delta(k["count_delta"]), help=vs)
    m3.metric("Ticket medio", c.money_short(k["ticket"]), _delta(k["ticket_delta"]), help=vs)
    m4.metric("Margen bruto", _pct(k["margin_pct"]), help="Sobre ventas netas, sin impuestos.")

    cur_sales = sales[(sales["status"] == "completada") & (sales["created_at"] >= start)]
    cur_lines = lines[lines["created_at"] >= start]
    accent = c.settings["accent_color"]

    left, right = st.columns([3, 2], gap="large")
    with left, st.container(border=True):
        st.markdown("**Facturación diaria**")
        days = pd.date_range(start.date(), clock.today(), freq="D")
        daily = cur_sales.groupby(cur_sales["created_at"].dt.normalize())["total"].sum().reindex(days, fill_value=0)
        if not refunds.empty:  # returns lower the day they were made
            back = refunds.groupby(refunds["created_at"].dt.normalize())["total"].sum()
            daily = daily.sub(back.reindex(days, fill_value=0), fill_value=0)
        fig = go.Figure(go.Bar(
            x=daily.index, y=daily.values, marker_color=accent,
            hovertemplate="%{x|%d/%m/%Y}<br><b>%{y:,.2f} " + c.symbol + "</b><extra></extra>",
        ))
        fig.update_xaxes(tickformat="%d/%m")
        st.plotly_chart(style_figure(fig), use_container_width=True, config={"displayModeBar": False})
    with right, st.container(border=True):
        st.markdown("**Lo más vendido** · ventas netas")
        top = cur_lines.groupby("name")["revenue"].sum().nlargest(6).sort_values()
        if top.empty:
            st.caption("Sin ventas en el periodo.")
        else:
            fig = go.Figure(go.Bar(
                x=top.values, y=top.index, orientation="h", marker_color=accent,
                text=[c.money(v) for v in top.values], textposition="auto",
                hovertemplate="%{y}<br><b>%{x:,.2f} " + c.symbol + "</b> netos<extra></extra>",
            ))
            st.plotly_chart(style_figure(fig), use_container_width=True, config={"displayModeBar": False})

    left, mid, right = st.columns([1, 1, 1], gap="large")
    with left, st.container(border=True):
        st.markdown("**Formas de pago**")
        pay = cur_sales.groupby("payment_method")["total"].sum().sort_values()
        if not pay.empty:
            fig = go.Figure(go.Bar(
                x=pay.values, y=pay.index, orientation="h", marker_color=accent,
                hovertemplate="%{y}<br><b>%{x:,.2f} " + c.symbol + "</b><extra></extra>",
            ))
            st.plotly_chart(style_figure(fig, 240), use_container_width=True, config={"displayModeBar": False})
    with mid, st.container(border=True):
        st.markdown("**Por categoría**")
        cat = cur_lines.groupby("category")["revenue"].sum().sort_values()
        if not cat.empty:
            fig = go.Figure(go.Bar(
                x=cat.values, y=cat.index, orientation="h", marker_color=accent,
                hovertemplate="%{y}<br><b>%{x:,.2f} " + c.symbol + "</b> netos<extra></extra>",
            ))
            st.plotly_chart(style_figure(fig, 240), use_container_width=True, config={"displayModeBar": False})
    with right, st.container(border=True):
        st.markdown("**Alertas inteligentes**")
        alerts = pages_intel.cached_alerts(c)
        pages_intel.show_alerts(alerts, limit=3)
        if len(alerts) > 3:
            st.caption(f"Y {len(alerts) - 3} más.")
        if "intelligence" in PAGES:
            st.page_link(PAGES["intelligence"], label="Ver todas y el análisis", icon=":material/arrow_forward:")

    by_user = cur_sales[cur_sales["user_name"] != ""].groupby("user_name")["total"].agg(["sum", "count"])
    if not by_user.empty:
        with st.container(border=True):
            st.markdown("**Ventas por persona del equipo**")
            by_user = by_user.sort_values("sum")
            fig = go.Figure(go.Bar(
                x=by_user["sum"], y=by_user.index, orientation="h", marker_color=accent,
                text=[f"{c.money(v)} · {n} ventas" for v, n in zip(by_user["sum"], by_user["count"])],
                textposition="auto",
                hovertemplate="%{y}<br><b>%{x:,.2f} " + c.symbol + "</b><extra></extra>",
            ))
            st.plotly_chart(style_figure(fig, 60 + 40 * len(by_user)), use_container_width=True,
                            config={"displayModeBar": False})

    st.markdown("#### Recomendaciones")
    for level, message in automation.insights(c.store.products(), cur_lines, c.preset["item_label"]):
        insight(level, message)


# ---------------------------------------------------------------- point of sale
def _cart() -> dict:
    """The ticket being rung up. It is also kept in the database, so a reload or a lost tab does not lose it."""
    if "cart" not in st.session_state:
        c = ctx()
        saved = c.store.saved_cart(c.user["id"]) if c.user else {}
        st.session_state["cart"], st.session_state["cart_saved"] = saved, dict(saved)
    return st.session_state["cart"]


def _persist_cart(c, cart: dict) -> None:
    if c.user and st.session_state.get("cart_saved") != cart:
        c.store.save_cart(c.user["id"], cart)
        st.session_state["cart_saved"] = dict(cart)


def _add_to_cart(pid: int) -> None:
    cart = _cart()
    cart[pid] = cart.get(pid, 0) + 1


def _change_qty(pid: int, delta: int) -> None:
    cart = _cart()
    cart[pid] = cart.get(pid, 0) + delta
    if cart[pid] <= 0:
        cart.pop(pid)


def _create_customer_from_pos() -> None:
    name = st.session_state.get("pos_new_name", "").strip()
    if not name:
        st.session_state["pos_flash"] = ("error", "Indica al menos el nombre del cliente.")
        return
    cid = get_store().upsert_customer({
        "name": name,
        "email": st.session_state.get("pos_new_email", ""),
        "phone": st.session_state.get("pos_new_phone", ""),
    })
    st.session_state["pos_customer"] = cid
    st.session_state["pos_flash"] = ("success", f"Cliente «{name}» creado y seleccionado.")


def _ticket_actions(c, sale: dict, preview_height: int = 420) -> None:
    """Print the ticket from the browser (A4 or thermal roll, as set in Configuración) or send it to the customer."""
    components.html(with_print_button(receipt_html(sale, c.settings)), height=preview_height, scrolling=True)
    text = receipt_text(sale, c.settings)
    a, b, d = st.columns(3)
    number = whatsapp_number(sale.get("customer_phone") or "")
    a.link_button("WhatsApp", f"https://wa.me/{number}?text={quote(text)}", icon=":material/chat:",
                  use_container_width=True, help="Abre WhatsApp con el ticket escrito, listo para enviar.")
    email = sale.get("customer_email") or ""
    subject = f"Ticket {sale['number']} · {c.settings.get('business_name', '')}"
    b.link_button("Email", f"mailto:{quote(email)}?subject={quote(subject)}&body={quote(text)}",
                  icon=":material/mail:", use_container_width=True, help="Abre tu correo con el ticket escrito.")
    d.download_button("Archivo", receipt_html(sale, c.settings), file_name=f"{sale['number']}.html",
                      mime="text/html", icon=":material/download:", use_container_width=True,
                      help="Descarga el ticket para guardarlo o imprimirlo más tarde.")


@st.dialog("Venta registrada")
def _sale_dialog(sale_id: int) -> None:
    c = ctx()
    sale = c.store.sale(sale_id)
    st.success(f"Ticket **{sale['number']}** · {c.money(sale['total'])} · {sale['payment_method']}")
    _ticket_actions(c, sale, preview_height=360)
    if st.button("Nueva venta", type="primary", use_container_width=True):
        st.rerun()


def point_of_sale() -> None:
    c = ctx()
    page_header("Punto de venta", "Selecciona lo que vendes, elige la forma de pago y cobra en segundos.",
                eyebrow="Vender")
    if "last_sale" in st.session_state:
        _sale_dialog(st.session_state.pop("last_sale"))
    if "pos_flash" in st.session_state:
        kind, msg = st.session_state.pop("pos_flash")
        getattr(st, kind)(msg)

    products = c.store.products()
    cart = _cart()
    # Drop items that were deactivated since they were added.
    for pid in [p for p in cart if p not in set(products["id"])]:
        cart.pop(pid)
    _persist_cart(c, cart)
    by_id = products.set_index("id")

    view = st.session_state.setdefault("pos_view", "catalogo")
    if view == "ticket" and not cart:
        view = st.session_state["pos_view"] = "catalogo"
    pos_mobile_css(view)
    with st.container(key="pos_bar"):
        units = sum(cart.values())
        if view == "catalogo":
            st.button(f"Ver ticket y cobrar ({units})" if units else "Añade productos al ticket", key="pos_to_ticket",
                      type="primary", use_container_width=True, icon=":material/shopping_cart:", disabled=not units,
                      on_click=st.session_state.__setitem__, args=("pos_view", "ticket"))
        else:
            st.button("Seguir añadiendo", key="pos_to_catalog", use_container_width=True, icon=":material/arrow_back:",
                      on_click=st.session_state.__setitem__, args=("pos_view", "catalogo"))

    catalog_col, ticket_col = st.columns([3, 2], gap="large")
    with catalog_col, st.container(key="pos_catalog"):
        f1, f2 = st.columns([2, 3])
        query = f1.text_input("Buscar", placeholder="Nombre o código…", label_visibility="collapsed")
        categories = sorted(products["category"].unique())
        selected = f2.pills("Categoría", categories, selection_mode="multi", label_visibility="collapsed")
        shown = products
        if query:
            q = query.lower()
            shown = shown[shown["name"].str.lower().str.contains(q, regex=False)
                          | shown["sku"].str.lower().str.contains(q, regex=False)]
        if selected:
            shown = shown[shown["category"].isin(selected)]
        if shown.empty:
            st.info("No hay resultados con esos filtros.")
        grid = st.container(key="pos_grid")
        cols = grid.columns(3)
        for i, (_, p) in enumerate(shown.iterrows()):
            pid = int(p["id"])
            available = p["stock"] - cart.get(pid, 0)
            with cols[i % 3], st.container(border=True):
                if p["track_stock"]:
                    low = "low" if p["stock"] <= p["min_stock"] else ""
                    stock = f"<div class='sm-tile-stock {low}'>{int(p['stock'])} en stock</div>"
                else:
                    stock = "<div class='sm-tile-stock'>Sin control de stock</div>"
                st.markdown(
                    f"<div class='sm-tile-cat'>{escape(p['category'])}</div><div class='sm-tile-name'>{escape(p['name'])}</div>"
                    f"<div class='sm-tile-price'>{c.money(p['price'])}</div>{stock}",
                    unsafe_allow_html=True,
                )
                st.button(
                    "Añadir", key=f"add_{pid}", on_click=_add_to_cart, args=(pid,), icon=":material/add:",
                    use_container_width=True, disabled=bool(p["track_stock"]) and available <= 0,
                )

    with ticket_col, st.container(key="pos_ticket"), st.container(border=True):
        st.markdown("#### Ticket actual")
        if not cart:
            st.caption("El ticket está vacío. Añade artículos desde el catálogo.")
        lines = st.container(key="pos_lines")
        for pid, qty in list(cart.items()):
            p = by_id.loc[pid]
            n, minus, q, plus = lines.columns([6, 1, 1, 1], vertical_alignment="center")
            n.markdown(f"**{escape(p['name'])}**  \n<span style='opacity:.65'>{c.money(p['price'])} × {qty} = "
                       f"{c.money(p['price'] * qty)}</span>", unsafe_allow_html=True)
            minus.button("", key=f"dec_{pid}", on_click=_change_qty, args=(pid, -1), icon=":material/remove:",
                         type="tertiary", help="Quitar una unidad")
            q.markdown(f"<div style='text-align:center;font-weight:700'>{qty}</div>", unsafe_allow_html=True)
            plus.button("", key=f"inc_{pid}", on_click=_change_qty, args=(pid, 1), icon=":material/add:",
                        type="tertiary", help="Añadir una unidad",
                        disabled=bool(p["track_stock"]) and qty >= p["stock"])

        st.divider()

        def customer_picker(names: dict):
            # 0 stands for the walk-in customer (ids start at 1).
            if st.session_state.get("pos_customer") not in names:
                st.session_state["pos_customer"] = 0
            cust_col, new_col = st.columns([4, 1], vertical_alignment="bottom")
            chosen = cust_col.selectbox("Cliente", [0, *names], key="pos_customer",
                                        format_func=lambda i: names.get(i, "Cliente general")) or None
            with new_col.popover("Nuevo", icon=":material/person_add:", help="Nuevo cliente"):
                with st.form("pos_new_customer", clear_on_submit=True, border=False):
                    st.text_input("Nombre", key="pos_new_name")
                    st.text_input("Email", key="pos_new_email")
                    st.text_input("Teléfono", key="pos_new_phone")
                    st.form_submit_button("Crear cliente", on_click=_create_customer_from_pos, type="primary")
            return chosen

        sale = checkout_panel(c, [{"product_id": pid, "quantity": q} for pid, q in cart.items()], "pos",
                              customer_widget=customer_picker)
        if sale:
            cart.clear()
            _persist_cart(c, cart)
            st.session_state["last_sale"] = sale["id"]
            st.session_state["pos_view"] = "catalogo"
            st.rerun()
        if cart and st.button("Vaciar ticket", use_container_width=True, icon=":material/delete:"):
            cart.clear()
            _persist_cart(c, cart)
            st.rerun()


# ------------------------------------------------------------------- history
@st.dialog("Anular venta")
def _confirm_cancel(sale_id: int, number: str) -> None:
    st.write(f"¿Seguro que quieres anular **{number}**? Las unidades volverán al stock. "
             "La venta se conserva en el historial marcada como anulada.")
    if st.button("Sí, anular", type="primary", use_container_width=True):
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
    address = st.text_input("Dirección fiscal", customer.get("address", ""), key=f"inv_addr_{sale_id}")
    email = st.text_input("Email", customer.get("email", ""), key=f"inv_mail_{sale_id}")
    irpf = st.selectbox("Retención de IRPF", c.store.IRPF_RATES, format_func=lambda r: "Sin retención" if not r
                        else f"{r:g} %", key=f"inv_irpf_{sale_id}",
                        help="Solo si eres profesional y facturas a una empresa o a otro profesional: 15 % en general, "
                             "7 % los primeros años de actividad. El cliente te paga el total menos la retención.")
    invoice = c.store.invoice_for_sale(sale_id)
    slot = st.empty()  # the issue button disappears as soon as the invoice exists
    if invoice is None and slot.button("Emitir factura", type="primary", use_container_width=True,
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
                           "application/pdf", type="primary", use_container_width=True,
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


def _history_sales(c) -> None:
    f1, f2, f3 = st.columns([2, 1, 2])
    rng = f1.date_input("Fechas", (clock.today() - timedelta(days=30), clock.today()), format="DD/MM/YYYY")
    status = f2.selectbox("Estado", ["Todas", "Completadas", "Anuladas"])
    query = f3.text_input("Buscar", placeholder="Nº de ticket o cliente…")
    if not isinstance(rng, tuple) or len(rng) != 2:
        st.info("Selecciona una fecha de inicio y otra de fin.")
        return
    start = datetime.combine(rng[0], time.min)
    end = datetime.combine(rng[1] + timedelta(days=1), time.min)
    df = c.store.sales(start, end)
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

    view = df[["id", "number", "created_at", "customer_name", "payment_method", "total", "status", "user_name"]]
    event = st.dataframe(
        view, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
        column_order=["number", "created_at", "customer_name", "payment_method", "total", "user_name", "status"],
        column_config={
            "number": "Ticket",
            "created_at": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
            "customer_name": "Cliente",
            "payment_method": "Pago",
            "total": st.column_config.NumberColumn("Total", format=f"%.2f {c.symbol}"),
            "user_name": "Atendió",
            "status": "Estado",
        },
    )
    if c.can("encargado"):
        st.download_button("Exportar a CSV", _csv(df.drop(columns=["id"])), "ventas.csv", "text/csv",
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
            items[["name", "quantity", "unit_price", "importe"]], hide_index=True, use_container_width=True,
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
            _ticket_actions(c, sale)
        a, b, d = st.columns(3)
        a.download_button("Descargar ticket", receipt_html(sale, c.settings), f"{sale['number']}.html",
                          "text/html", icon=":material/receipt_long:", use_container_width=True)
        if invoice:
            full = c.store.invoice(invoice["id"])
            b.download_button("Descargar factura", invoice_pdf(full, c.settings), f"{full['number']}.pdf",
                              "application/pdf", icon=":material/request_quote:", use_container_width=True)
        elif b.button("Emitir factura", disabled=sale["status"] != "completada" or not c.can("encargado"),
                      use_container_width=True, icon=":material/request_quote:"):
            _invoice_dialog(sale["id"])
        past_refunds = c.store.sale_refunds(sale["id"])
        if past_refunds:
            st.caption("Devoluciones: " + " · ".join(
                f"{r['number']} ({c.money(r['total'])})" + (f", rectificativa {r['credit_note']['number']}"
                                                          if r["credit_note"] else "") for r in past_refunds))
        if d.button("Devolver productos", disabled=sale["status"] != "completada" or not c.can("encargado"),
                    use_container_width=True, icon=":material/undo:"):
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
    if slot.button("Registrar devolución", type="primary", use_container_width=True, icon=":material/undo:",
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
                           use_container_width=True)
        if refund["credit_note"]:
            note = c.store.credit_note(refund["id"])
            st.download_button(f"Factura rectificativa {note['number']} (PDF)", credit_note_pdf(note, c.settings),
                               f"{note['number']}.pdf", "application/pdf", type="primary",
                               icon=":material/request_quote:", use_container_width=True)


def _history_refunds(c) -> None:
    df = c.store.refunds()
    if df.empty:
        st.info("Sin devoluciones. Se registran desde una venta del Historial con «Devolver productos».")
        return
    event = st.dataframe(
        df, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
        key="refunds_table",
        column_order=["number", "created_at", "sale_number", "reason", "method", "total", "credit_note", "user_name"],
        column_config={
            "number": "Devolución", "created_at": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
            "sale_number": "Ticket", "reason": "Motivo", "method": "Devuelto por",
            "total": st.column_config.NumberColumn("Importe", format=f"%.2f {c.symbol}"),
            "credit_note": "Rectificativa", "user_name": "Registró",
        },
    )
    st.download_button("Exportar devoluciones a CSV", _csv(df.drop(columns=["id"])), "devoluciones.csv", "text/csv",
                       icon=":material/download:")
    if event.selection.rows:
        refund = c.store.refund(int(df.iloc[event.selection.rows[0]]["id"]))
        a, b = st.columns(2)
        a.download_button("Justificante", refund_receipt_html(refund, c.settings), f"{refund['number']}.html",
                          "text/html", icon=":material/receipt_long:", use_container_width=True)
        if refund["credit_note"]:
            note = c.store.credit_note(refund["id"])
            b.download_button(f"Rectificativa {note['number']}", credit_note_pdf(note, c.settings),
                              f"{note['number']}.pdf", "application/pdf", icon=":material/request_quote:",
                              use_container_width=True)


def _history_invoices(c) -> None:
    df = c.store.invoices()
    if df.empty:
        st.info("Aún no has emitido facturas. Selecciona una venta en la pestaña «Ventas» y pulsa «Emitir factura».")
        return
    event = st.dataframe(
        df, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
        key="invoices_table",
        column_order=["number", "issued_at", "customer_name", "customer_tax_id", "sale_number", "total"],
        column_config={
            "number": "Factura",
            "issued_at": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY"),
            "customer_name": "Cliente", "customer_tax_id": "NIF/CIF", "sale_number": "Ticket",
            "total": st.column_config.NumberColumn("Total", format=f"%.2f {c.symbol}"),
        },
    )
    st.download_button("Exportar facturas a CSV", _csv(df.drop(columns=["id"])), "facturas.csv", "text/csv",
                       icon=":material/download:")
    rows = event.selection.rows
    if rows:
        full = c.store.invoice(int(df.iloc[rows[0]]["id"]))
        st.download_button(f"Descargar {full['number']} (PDF)", invoice_pdf(full, c.settings),
                           f"{full['number']}.pdf", "application/pdf", type="primary",
                           icon=":material/request_quote:")
    else:
        st.caption("Selecciona una factura para descargarla.")


# ---------------------------------------------------------------------- cash
def cash_page() -> None:
    c = ctx()
    if not _require(c, "encargado"):
        return
    page_header("Cierre de caja", "Cuadra el efectivo al final del día y guarda el informe firmado.",
                eyebrow="Caja")
    if "cash_flash" in st.session_state:
        st.success(st.session_state.pop("cash_flash"))
    day = st.date_input("Día", clock.today(), max_value=clock.today(), format="DD/MM/YYYY", key="cash_day")
    summary = c.store.day_summary(day)
    closing = c.store.cash_closing(day)

    m1, m2, m3 = st.columns(3)
    m1.metric("Vendido", c.money_short(summary["total"]))
    m2.metric("Ventas", summary["count"])
    m3.metric("Cobrado en efectivo", c.money_short(summary["cash"]))

    left, right = st.columns([3, 2], gap="large")
    with left, st.container(border=True):
        st.markdown("**Por forma de pago**")
        if summary["breakdown"]:
            df = pd.DataFrame(
                [{"method": m, "count": e["count"], "refunded": e.get("refunded", 0.0), "total": e["total"]}
                 for m, e in summary["breakdown"].items()]
            ).sort_values("total", ascending=False)
            st.dataframe(df, hide_index=True, use_container_width=True,
                         column_order=["method", "count", *(["refunded"] if summary["refunded"] else []), "total"],
                         column_config={
                             "method": "Forma de pago", "count": "Cobros",
                             "refunded": st.column_config.NumberColumn("Devuelto", format=f"%.2f {c.symbol}"),
                             "total": st.column_config.NumberColumn("Neto", format=f"%.2f {c.symbol}"),
                         })
        else:
            st.caption("No hay ventas este día.")
        if summary["cancelled"]:
            st.caption(f"{summary['cancelled']} venta(s) anulada(s) no se cuentan.")

    with right, st.container(border=True):
        if closing:
            _closed_cash_panel(c, day, closing, summary)
        else:
            _open_cash_panel(c, day, summary)

    st.markdown("#### Cierres anteriores")
    history = c.store.cash_closings()
    if history.empty:
        st.caption("Todavía no has cerrado ninguna caja.")
    else:
        st.dataframe(history.drop(columns=["closed_at"]), hide_index=True, use_container_width=True,
                     column_config={
                         "day": st.column_config.DateColumn("Día", format="DD/MM/YYYY"),
                         "total_sales": st.column_config.NumberColumn("Vendido", format=f"%.2f {c.symbol}"),
                         "sales_count": "Ventas",
                         "expected_cash": st.column_config.NumberColumn("Esperado", format=f"%.2f {c.symbol}"),
                         "counted_cash": st.column_config.NumberColumn("Contado", format=f"%.2f {c.symbol}"),
                         "difference": st.column_config.NumberColumn("Diferencia", format=f"%+.2f {c.symbol}"),
                     })
        st.download_button("Exportar cierres a CSV", _csv(history), "cierres_de_caja.csv", "text/csv",
                           icon=":material/download:")


def _difference_message(c, difference: float):
    if abs(difference) < 0.005:
        st.success("La caja cuadra.", icon=":material/check_circle:")
    elif difference > 0:
        st.warning(f"Sobran {c.money(difference)}.", icon=":material/info:")
    else:
        st.error(f"Faltan {c.money(-difference)}.", icon=":material/error:")


def _open_cash_panel(c, day: date, summary: dict) -> None:
    st.markdown("**Arqueo de efectivo**")
    opening = st.number_input(f"Fondo inicial ({c.symbol})", min_value=0.0, step=10.0,
                              value=float(c.settings.get("opening_float") or 0), key=f"cash_open_{day}")
    expected = round(opening + summary["cash"], 2)
    st.markdown(f"Efectivo esperado en el cajón: **{c.money(expected)}**")
    counted = st.number_input(f"Efectivo contado ({c.symbol})", min_value=0.0, step=1.0, value=None,
                              placeholder="Cuenta el cajón y escribe el total", key=f"cash_count_{day}")
    if counted is not None:
        _difference_message(c, round(counted - expected, 2))
    notes = st.text_area("Notas", placeholder="Ej.: retirada de 200 € para el banco", key=f"cash_notes_{day}",
                         height=70)
    if st.button("Cerrar caja", type="primary", use_container_width=True, disabled=counted is None,
                 icon=":material/lock:"):
        try:
            closing = c.store.close_cash(day, opening, counted, notes, closed_by=c.who)
            c.store.audit(c.username, "caja_cerrada", f"{day:%d/%m/%Y} · diferencia {closing['difference']:+.2f}")
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["cash_flash"] = f"Caja del {day:%d/%m/%Y} cerrada."
            st.rerun()


def _closed_cash_panel(c, day: date, closing: dict, summary: dict) -> None:
    closed_at = datetime.fromisoformat(closing["closed_at"])
    st.markdown(f"**Caja cerrada** · {closed_at:%d/%m/%Y %H:%M}")
    st.markdown(f"Esperado **{c.money(closing['expected_cash'])}** · Contado **{c.money(closing['counted_cash'])}**")
    _difference_message(c, closing["difference"])
    if summary["count"] != closing["sales_count"] or abs(summary["total"] - closing["total_sales"]) >= 0.005:
        st.warning("Ha habido ventas o anulaciones después del cierre. Reabre la caja y ciérrala de nuevo "
                   "para incluirlas.", icon=":material/warning:")
    st.download_button("Descargar informe (PDF)", cash_closing_pdf(closing, c.settings),
                       f"cierre-{day:%Y-%m-%d}.pdf", "application/pdf", type="primary",
                       use_container_width=True, icon=":material/picture_as_pdf:")
    if st.button("Reabrir caja", use_container_width=True, icon=":material/lock_open:"):
        c.store.reopen_cash(day)
        c.store.audit(c.username, "caja_reabierta", f"{day:%d/%m/%Y}")
        st.rerun()


# -------------------------------------------------------------------- agenda
STATUS_LABELS = {"pendiente": "Pendiente", "completada": "Hecha", "cancelada": "Cancelada",
                 "no_presentado": "No vino"}


def agenda_enabled(settings: dict, preset: dict) -> bool:
    choice = settings.get("agenda_enabled", "auto")
    return bool(preset.get("agenda")) if choice == "auto" else choice == "si"


def agenda_config(preset: dict) -> dict:
    return preset.get("agenda") or {"title": "Agenda", "single": True, "duration": 60}


def _shift_agenda_day(days: int | None) -> None:
    current = st.session_state.get("agenda_day", clock.today())
    st.session_state["agenda_day"] = clock.today() if days is None else current + timedelta(days=days)


def _set_appointment_status(appointment_id: int, status: str) -> None:
    try:
        get_store().set_appointment_status(appointment_id, status)
    except ValueError as exc:
        st.session_state["agenda_flash"] = ("error", str(exc))


def agenda_page() -> None:
    c = ctx()
    cfg = agenda_config(c.preset)
    page_header(cfg["title"], "Organiza el día, evita solapes y cobra cada cita con un toque.", eyebrow="Agenda")
    if "last_sale" in st.session_state:
        _sale_dialog(st.session_state.pop("last_sale"))
    if "agenda_flash" in st.session_state:
        kind, msg = st.session_state.pop("agenda_flash")
        getattr(st, kind)(msg)

    if "agenda_goto" in st.session_state:
        st.session_state["agenda_day"] = st.session_state.pop("agenda_goto")
    st.session_state.setdefault("agenda_day", clock.today())
    b1, b2, b3, b4 = st.columns([1, 4, 1, 1.4], vertical_alignment="bottom")
    b1.button("", icon=":material/chevron_left:", on_click=_shift_agenda_day, args=(-1,), help="Día anterior",
              use_container_width=True)
    day = b2.date_input("Día", key="agenda_day", format="DD/MM/YYYY", label_visibility="collapsed")
    b3.button("", icon=":material/chevron_right:", on_click=_shift_agenda_day, args=(1,), help="Día siguiente",
              use_container_width=True)
    b4.button("Hoy", on_click=_shift_agenda_day, args=(None,), use_container_width=True)

    start = datetime.combine(day, time.min)
    df = c.store.appointments(start, start + timedelta(days=1))
    pending = df[df["status"] == "pendiente"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Citas del día" if cfg["single"] else "Reservas del día", len(df[df["status"] != "cancelada"]))
    m2.metric("Pendientes", len(pending))
    expected = pending["price"].fillna(0).astype(float).sum()
    m3.metric("Ingresos previstos", c.money_short(expected), help="Servicios pendientes, impuestos incluidos.")

    left, right = st.columns([3, 2], gap="large")
    with left:
        if df.empty:
            st.info(f"No hay {'citas' if cfg['single'] else 'reservas'} este día. Crea una con el formulario.")
        for _, a in df.iterrows():
            _appointment_card(c, a)
    with right, st.container(border=True):
        _new_appointment_form(c, cfg, day)


def _appointment_card(c, a) -> None:
    end = a["starts_at"] + timedelta(minutes=int(a["duration_min"]))
    status = a["status"]
    detail = " · ".join(x for x in [
        a["service"] if isinstance(a["service"], str) else "",
        c.money(float(a["price"])) if pd.notna(a["price"]) else "",
        a["notes"],
    ] if x)
    with st.container(border=True):
        st.markdown(
            f"<div class='sm-appt {escape(status)}'><div class='when'>{a['starts_at']:%H:%M}<span>–{end:%H:%M}</span></div>"
            f"<div class='who'>{escape(str(a['who']))}<div class='what'>{escape(detail)}</div></div>"
            f"<span class='chip'>{escape(STATUS_LABELS.get(status, status))}</span></div>",
            unsafe_allow_html=True,
        )
        if status != "pendiente":
            return
        aid = int(a["id"])
        x, y, z = st.columns(3)
        if pd.notna(a["product_id"]):
            with x.popover("Cobrar", icon=":material/payments:", use_container_width=True):
                method = st.segmented_control("Forma de pago", PAYMENT_METHODS, default=PAYMENT_METHODS[0],
                                              key=f"appt_pay_{aid}") or PAYMENT_METHODS[0]
                if st.button("Cobrar ahora", type="primary", key=f"appt_charge_{aid}", use_container_width=True):
                    try:
                        sale = c.store.charge_appointment(aid, method, user_name=c.who)
                    except SaleError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["last_sale"] = sale["id"]
                        st.rerun()
        else:
            x.button("Hecha", key=f"appt_done_{aid}", on_click=_set_appointment_status, args=(aid, "completada"),
                     icon=":material/check:", use_container_width=True)
        y.button("No vino", key=f"appt_noshow_{aid}", on_click=_set_appointment_status,
                 args=(aid, "no_presentado"), use_container_width=True)
        z.button("Cancelar", key=f"appt_cancel_{aid}", on_click=_set_appointment_status, args=(aid, "cancelada"),
                 use_container_width=True)


def _new_appointment_form(c, cfg: dict, day: date) -> None:
    st.markdown("**Nueva cita**" if cfg["single"] else "**Nueva reserva**")
    customers = c.store.customers()
    names = {int(i): n for i, n in zip(customers["id"], customers["name"])}
    products = c.store.products()
    services = {int(i): n for i, n in zip(products["id"], products["name"])}
    with st.form("new_appointment", clear_on_submit=True, border=False):
        a, b = st.columns(2)
        when_day = a.date_input("Fecha", day, format="DD/MM/YYYY")
        when_time = b.time_input("Hora", time(10, 0), step=timedelta(minutes=15))
        duration = st.number_input("Duración (minutos)", min_value=15, max_value=600, step=15,
                                   value=int(cfg.get("duration", 60)))
        customer_id = st.selectbox("Cliente", [0, *names], format_func=lambda i: names.get(i, "Sin ficha (escribir nombre)"))
        walk_in = st.text_input("Nombre (si no tiene ficha)")
        product_id = st.selectbox(c.preset["item_label"], [0, *services],
                                  format_func=lambda i: services.get(i, "Sin servicio"),
                                  index=1 if cfg["single"] and services else 0)
        notes = st.text_input("Notas", placeholder="Ej.: mesa para 4, alergia a frutos secos…")
        if st.form_submit_button("Guardar", type="primary", use_container_width=True, icon=":material/event:"):
            try:
                c.store.create_appointment(
                    datetime.combine(when_day, when_time), duration,
                    product_id=product_id or None, customer_id=customer_id or None,
                    customer_name=walk_in, notes=notes, allow_overlap=not cfg["single"], created_by=c.who,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["agenda_flash"] = ("success", f"Guardada para el {when_day:%d/%m} a las {when_time:%H:%M}.")
                st.session_state["agenda_goto"] = when_day  # applied before the date picker is drawn
                st.rerun()


# ---------------------------------------------------------------------- team
def team_page() -> None:
    c = ctx()
    if not _require(c, "admin"):
        return
    page_header("Equipo y seguridad", "Da de alta a tu equipo: cada persona entra con su nombre y su PIN, y todo "
                "lo que hace queda firmado.", eyebrow="Ajustes")
    if "team_flash" in st.session_state:
        st.success(st.session_state.pop("team_flash"))

    users = c.store.users()
    m1, m2, m3 = st.columns(3)
    m1.metric("Personas activas", int(users["active"].sum()))
    m2.metric("Administradores", int(((users["role"] == "admin") & (users["active"] == 1)).sum()))
    m3.metric("Cierre de sesión por inactividad", f"{int(c.settings.get('session_minutes') or 720) // 60} h")

    roles_help = ("**Administrador:** todo, incluida la configuración y el equipo. "
                  "**Encargado:** panel, caja, catálogo, clientes, facturas y anulaciones. "
                  "**Empleado:** vender, agenda y consultar tickets.")
    st.caption(roles_help)
    st.dataframe(
        users.assign(role=users["role"].map(ROLES), active=users["active"].astype(bool),
                     two_factor=users["two_factor"].astype(bool),
                     last_login=pd.to_datetime(users["last_login"].replace("", None))),
        hide_index=True, use_container_width=True,
        column_order=["name", "username", "role", "active", "two_factor", "last_login"],
        column_config={"name": "Nombre", "username": "Usuario", "role": "Rol",
                       "active": st.column_config.CheckboxColumn("Activo"),
                       "two_factor": st.column_config.CheckboxColumn("Dos pasos"),
                       "last_login": st.column_config.DatetimeColumn("Último acceso", format="DD/MM/YYYY HH:mm")},
    )

    add, manage = st.columns(2, gap="large")
    with add, st.container(border=True):
        st.markdown("**Añadir persona**")
        with st.form("new_user", clear_on_submit=True, border=False):
            name = st.text_input("Nombre", max_chars=120, placeholder="Ej.: Lucía")
            username = st.text_input("Usuario", max_chars=30, placeholder="Ej.: lucia")
            role = st.selectbox("Rol", list(ROLES), index=2, format_func=ROLES.get)
            secret = st.text_input("PIN o contraseña", type="password", max_chars=128,
                                   help="Empleados y encargados: mínimo 6 cifras o caracteres, sin series fáciles "
                                        "(123456, 111111). Administradores: mínimo 8, con letras y números.")
            if st.form_submit_button("Añadir", type="primary", icon=":material/person_add:"):
                try:
                    c.store.create_user(name, username, role, secret, by=c.username)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["team_flash"] = f"{name} ya puede entrar con su usuario «{username.lower()}»."
                    st.rerun()

    with manage, st.container(border=True):
        st.markdown("**Modificar persona**")
        if users.empty:
            st.caption("Todavía no hay nadie en el equipo.")
        else:
            options = dict(zip(users["id"].astype(int), users["name"] + " (" + users["username"] + ")"))
            uid = st.selectbox("Persona", list(options), format_func=options.get, key="team_user")
            _manage_user(c, users.set_index("id").loc[uid], uid)

    _own_account_security(c)

    st.markdown("#### Registro de actividad")
    st.caption("Accesos, intentos fallidos, anulaciones, facturas, cierres de caja y cambios de configuración.")
    log = c.store.audit_log()
    only_failed = st.toggle("Ver solo accesos fallidos", key="audit_failed")
    if only_failed:
        log = log[log["action"] == "acceso_fallido"]
    st.dataframe(log, hide_index=True, use_container_width=True, column_config={
        "happened_at": st.column_config.DatetimeColumn("Cuándo", format="DD/MM/YYYY HH:mm:ss"),
        "username": "Usuario", "action": "Acción", "detail": "Detalle",
    })
    st.download_button("Exportar registro a CSV", _csv(log), "registro_actividad.csv", "text/csv",
                       icon=":material/download:")


def _own_account_security(c) -> None:
    """Recovery codes and two-step verification for the administrator who is signed in."""
    st.markdown("#### Seguridad de tu cuenta")
    codes_col, totp_col = st.columns(2, gap="large")
    if c.user is None or c.user["role"] != "admin":
        return
    with codes_col, st.container(border=True):
        left = c.store.recovery_codes_left(c.user["id"])
        st.markdown("**Códigos de recuperación**")
        st.caption(f"Te quedan **{left}**. Sirven para volver a entrar si olvidas la contraseña, pierdes el móvil "
                   "o alguien bloquea tu cuenta." + (" **Genera unos nuevos.**" if left <= 2 else ""))
        if st.button("Generar códigos nuevos", key="new_codes", icon=":material/key:",
                     help="Los anteriores que no hayas usado dejarán de funcionar."):
            st.session_state["team_codes"] = c.store.create_recovery_codes(c.user["id"], by=c.username)
        if st.session_state.get("team_codes"):
            st.warning("Guárdalos ahora fuera de este dispositivo: no se volverán a mostrar.", icon=":material/key:")
            st.code("\n".join(st.session_state["team_codes"]), language=None)
            if st.button("Ya los he guardado", key="codes_saved"):
                st.session_state.pop("team_codes", None)
                st.rerun()
    with totp_col, st.container(border=True):
        st.markdown("**Verificación en dos pasos**")
        me = c.store.user(c.user["id"])
        if me is None:
            return
        enabled = bool(me["two_factor"])
        if enabled:
            st.success("Activada: al entrar se pide también el código de tu app de autenticación.",
                       icon=":material/verified_user:")
            with st.form("totp_off", clear_on_submit=True, border=False):
                code = st.text_input("Código actual de la app para desactivarla", max_chars=6)
                if st.form_submit_button("Desactivar"):
                    try:
                        c.store.disable_two_factor(c.user["id"], code)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.rerun()
            return
        st.caption("Recomendado para el administrador: aunque alguien adivine tu contraseña, sin tu móvil no entra. "
                   "Usa Google Authenticator, Microsoft Authenticator o similar.")
        secret = st.session_state.setdefault("totp_pending", new_totp_secret())
        st.markdown("1. En la app, añade una cuenta con **«Introducir clave de configuración»** y escribe esta clave "
                    "(tipo: basada en tiempo):")
        st.code(" ".join(secret[i:i + 4] for i in range(0, len(secret), 4)), language=None)
        st.caption(f"Cuenta: {c.username} · NirKanA. En el móvil también puedes abrir este enlace: "
                   f"[añadir a la app]({totp_uri(secret, c.username)}).")
        with st.form("totp_on", clear_on_submit=True, border=False):
            code = st.text_input("2. Escribe el código de 6 cifras que muestra la app", max_chars=6)
            if st.form_submit_button("Activar", type="primary"):
                try:
                    c.store.enable_two_factor(c.user["id"], secret, code)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.pop("totp_pending", None)
                    st.rerun()


def _manage_user(c, target, uid: int) -> None:
    new_role = st.selectbox("Rol", list(ROLES), index=list(ROLES).index(target["role"]), format_func=ROLES.get,
                            key=f"team_role_{uid}")
    active = st.toggle("Puede entrar", value=bool(target["active"]), key=f"team_active_{uid}")
    new_secret = st.text_input("Nuevo PIN o contraseña (opcional)", type="password", max_chars=128,
                               key=f"team_secret_{uid}")
    if st.button("Guardar cambios", type="primary", key=f"team_save_{uid}", icon=":material/save:"):
        try:
            c.store.update_user(uid, role=new_role, active=active, by=c.username)
            if new_secret:
                c.store.set_user_secret(uid, new_secret, by=c.username)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["team_flash"] = f"Cambios guardados para {target['name']}."
            st.rerun()


# ------------------------------------------------------------------ products
def _editor_key(name: str) -> str:
    return f"{name}_{st.session_state.get(name + '_v', 0)}"


def _bump(name: str) -> None:
    st.session_state[name + "_v"] = st.session_state.get(name + "_v", 0) + 1


def _same(a, b) -> bool:
    """Equal cells of the table editor, counting two empty cells as equal."""
    return (pd.isna(a) and pd.isna(b)) if (pd.isna(a) or pd.isna(b)) else a == b


def products_page() -> None:
    c = ctx()
    if not _require(c, "encargado"):
        return
    label, plural = c.preset["item_label"], c.preset["item_label_plural"]
    page_header(plural, "Edita directamente en la tabla y guarda. Desactiva en lugar de borrar para "
                "conservar el historial.", eyebrow="Gestión")
    if "products_flash" in st.session_state:
        st.success(st.session_state.pop("products_flash"))

    df = c.store.products(include_inactive=True)
    vat_labels = {None: f"Por defecto ({c.tax_rate:g} %)", **{r: f"{r:g} %" for r in (21.0, 10.0, 5.0, 4.0, 0.0)}}
    vat_rates = {label: rate for rate, label in vat_labels.items()}
    categories = sorted(set(c.preset["categories"]) | set(df["category"]))
    tab_list, tab_new = st.tabs([f"Catálogo ({len(df)})", f"Nuevo {label.lower()}"])

    with tab_list:
        df = df.assign(
            track_stock=df["track_stock"].astype(bool), active=df["active"].astype(bool),
            margin=((df["net_price"] - df["cost"]) / df["net_price"].where(df["net_price"] > 0) * 100).round(1),
            iva=[vat_labels[None] if pd.isna(r) else vat_labels.get(float(r), f"{float(r):g} %") for r in df["tax_rate"]],
            state=[("—" if not t else "Bajo mínimo" if s <= m else "Correcto")
                   for t, s, m in zip(df["track_stock"], df["stock"], df["min_stock"])],
        )
        edited = st.data_editor(
            df, key=_editor_key("products_editor"), hide_index=True, use_container_width=True,
            disabled=["id", "margin", "state"],
            column_order=["sku", "name", "category", "price", "iva", "cost", "margin", "stock", "min_stock", "state",
                          "track_stock", "active"],
            column_config={
                "sku": "Código", "name": "Nombre",
                "category": st.column_config.SelectboxColumn("Categoría", options=categories, required=True),
                "price": st.column_config.NumberColumn("Precio (IVA incl.)", min_value=0, format=f"%.2f {c.symbol}",
                                                       help="El precio final, como en la carta o la etiqueta."),
                "iva": st.column_config.SelectboxColumn(
                    "IVA", options=list(vat_rates), required=True,
                    help="El del producto, o el IVA por defecto del negocio (se cambia en Configuración)."),
                "cost": st.column_config.NumberColumn("Coste (sin IVA)", min_value=0, format=f"%.2f {c.symbol}"),
                "margin": st.column_config.NumberColumn("Margen", format="%.1f %%",
                                                        help="Sobre el precio sin IVA, que es lo que te queda."),
                "stock": st.column_config.NumberColumn("Stock", step=1),
                "min_stock": st.column_config.NumberColumn("Mínimo", min_value=0, step=1),
                "state": "Estado",
                "track_stock": st.column_config.CheckboxColumn("Controlar stock"),
                "active": st.column_config.CheckboxColumn("Activo"),
            },
        )
        st.caption("Si cambias el stock, la diferencia se suma o resta a las existencias reales de ese momento "
                   "(aunque se haya vendido mientras editabas) y queda en «Ajustes de stock».")
        if st.button("Guardar cambios", type="primary", icon=":material/save:"):
            changed = 0
            try:
                for (_, before), (_, after) in zip(df.iterrows(), edited.iterrows()):
                    pid = int(after["id"])
                    changes = {f: after[f] for f in c.store.PRODUCT_EDITABLE
                               if f != "tax_rate" and not _same(before[f], after[f])}
                    if before["iva"] != after["iva"]:
                        changes["tax_rate"] = vat_rates.get(after["iva"])
                    delta = int(after["stock"]) - int(before["stock"])
                    if changes:
                        c.store.update_product(pid, changes)
                        c.store.audit(c.username, "producto_modificado", f"{after['sku']} · " + ", ".join(
                            f"{k}: {before[k]} → {after[k]}" for k in changes))
                    if delta:
                        c.store.adjust_stock(pid, delta, "Ajuste en el catálogo", user_name=c.who)
                    changed += bool(changes or delta)
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
            else:
                st.session_state["products_flash"] = f"{changed} cambio(s) guardado(s)."
                _bump("products_editor")
                st.rerun()

        with st.expander("Ajustes de stock", icon=":material/history:"):
            moves = c.store.stock_moves()
            if moves.empty:
                st.caption("Todavía no hay ajustes manuales de stock.")
            else:
                st.dataframe(moves, hide_index=True, use_container_width=True, column_config={
                    "created_at": st.column_config.DatetimeColumn("Cuándo", format="DD/MM/YYYY HH:mm"),
                    "sku": "Código", "name": "Artículo", "delta": "Cambio", "stock_after": "Queda",
                    "reason": "Motivo", "user_name": "Quién"})

    with tab_new:
        with st.form("new_product", clear_on_submit=True):
            a, b = st.columns(2)
            sku = a.text_input("Código / SKU")
            name = b.text_input("Nombre")
            category = a.selectbox("Categoría", categories)
            new_category = b.text_input("…o nueva categoría")
            p1, p2, p3, p4 = st.columns(4)
            price = p1.number_input(f"Precio de venta ({c.symbol}, IVA incluido)", 0.0, step=0.5)
            cost = p2.number_input(f"Coste ({c.symbol})", 0.0, step=1.0)
            stock = p3.number_input("Stock inicial", 0, step=1)
            min_stock = p4.number_input("Stock mínimo", 0, step=1)
            vat_options = [None, 21.0, 10.0, 5.0, 4.0, 0.0]
            vat = st.selectbox("IVA", vat_options, format_func=lambda r: f"Por defecto ({c.tax_rate:g} %)"
                               if r is None else f"{r:g} %")
            track = st.toggle("Controlar stock", value=bool(c.preset["track_stock"]))
            if st.form_submit_button(f"Crear {label.lower()}", type="primary"):
                try:
                    c.store.upsert_product({
                        "sku": sku.strip(), "name": name.strip(), "category": new_category.strip() or category,
                        "price": price, "cost": cost, "tax_rate": vat, "stock": stock if track else 0,
                        "min_stock": min_stock if track else 0, "track_stock": int(track), "active": 1,
                    })
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["products_flash"] = f"«{name}» añadido al catálogo."
                    _bump("products_editor")
                    st.rerun()


# ----------------------------------------------------------------- customers
def customers_page() -> None:
    c = ctx()
    if not _require(c, "encargado"):
        return
    page_header("Clientes", "Tu cartera, ordenada por valor. Edita en la tabla y guarda.", eyebrow="Gestión")
    if "customers_flash" in st.session_state:
        st.success(st.session_state.pop("customers_flash"))

    ranking = automation.customer_ranking(c.store.customers(), c.store.sales())
    points = c.store.points_by_customer()
    ranking = ranking.merge(points, left_on="id", right_on="customer_id", how="left").drop(columns=["customer_id"])
    ranking["points"] = ranking["points"].fillna(0).astype(int)
    buyers = ranking[ranking["purchases"] > 0]
    m1, m2, m3 = st.columns(3)
    m1.metric("Clientes", len(ranking))
    m2.metric("Con compras", len(buyers))
    m3.metric("Valor medio por cliente", c.money_short(buyers["lifetime_value"].mean() if len(buyers) else 0))

    with st.expander("Añadir cliente", icon=":material/person_add:"):
        with st.form("new_customer", clear_on_submit=True, border=False):
            a, b = st.columns(2)
            data = {
                "name": a.text_input("Nombre o razón social"),
                "tax_id": b.text_input("NIF / RFC / CUIT"),
                "email": a.text_input("Email"),
                "phone": b.text_input("Teléfono"),
                "address": st.text_input("Dirección fiscal", placeholder="Calle, número, código postal y ciudad"),
                "notes": st.text_area("Notas", height=80),
            }
            consent = st.checkbox("Acepta recibir ofertas y novedades",
                                  help="Solo con su permiso expreso (RGPD). Puede retirarlo cuando quiera.")
            if st.form_submit_button("Guardar cliente", type="primary"):
                try:
                    new_id = c.store.upsert_customer(data)
                    if consent:
                        c.store.set_marketing_consent(new_id, True, by=c.username)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["customers_flash"] = f"Cliente «{data['name']}» guardado."
                    _bump("customers_editor")
                    st.rerun()

    fields = ["name", "email", "phone", "tax_id", "address", "notes"]
    edited = st.data_editor(
        ranking, key=_editor_key("customers_editor"), hide_index=True, use_container_width=True,
        disabled=["id", "purchases", "lifetime_value", "last_purchase", "created_at", "points"],
        column_order=["name", "email", "phone", "tax_id", "address", "purchases", "lifetime_value", "points",
                      "last_purchase", "notes"],
        column_config={
            "name": "Nombre", "email": "Email", "phone": "Teléfono", "tax_id": "Identificación fiscal", "address": "Dirección",
            "purchases": st.column_config.NumberColumn("Compras"),
            "lifetime_value": st.column_config.ProgressColumn(
                "Valor acumulado", format=f"%.2f {c.symbol}", min_value=0,
                max_value=float(max(ranking["lifetime_value"].max(), 1)) if len(ranking) else 1.0,
            ),
            "last_purchase": st.column_config.DatetimeColumn("Última compra", format="DD/MM/YYYY"),
            "points": st.column_config.NumberColumn("Puntos"),
            "notes": "Notas",
        },
    )
    if st.button("Guardar cambios", type="primary", icon=":material/save:"):
        changed = 0
        try:
            for (_, before), (_, after) in zip(ranking.iterrows(), edited.iterrows()):
                if any(str(before[f]) != str(after[f]) for f in fields):
                    c.store.upsert_customer({f: after[f] for f in fields}, int(after["id"]))
                    changed += 1
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["customers_flash"] = f"{changed} cambio(s) guardado(s)."
            _bump("customers_editor")
            st.rerun()

    _privacy_section(c, c.store.customers())


def _prepare_export(cid: int) -> None:
    c = ctx()
    st.session_state[f"export_{cid}"] = c.store.customer_data_export(cid, by=c.username)


def _privacy_section(c, customers: pd.DataFrame) -> None:
    """A customer's rights (RGPD): see and take their data, stop marketing, have their data erased."""
    st.markdown("##### Protección de datos (RGPD)")
    with st.container(border=True):
        people = customers[customers["anonymized_at"] == ""]
        if people.empty:
            st.caption("Aún no hay clientes.")
            return
        names = dict(zip(people["id"].astype(int), people["name"] + people["email"].map(lambda e: f" · {e}" if e else "")))
        cid = st.selectbox("Cliente", list(names), format_func=names.get, key="privacy_customer",
                           help="Cuando un cliente pide ver, llevarse o borrar sus datos, o dejar de recibir ofertas.")
        person = people.set_index("id").loc[cid]
        consent = bool(person["marketing_consent"])
        a, b = st.columns(2)
        with a:
            wants = st.toggle("Acepta recibir ofertas", value=consent, key=f"consent_{cid}")
            if wants != consent:
                c.store.set_marketing_consent(cid, wants, by=c.username)
                st.session_state["customers_flash"] = ("Consentimiento registrado." if wants
                                                       else "Ya no recibirá ofertas.")
                st.rerun()
            if person["consent_at"]:
                st.caption(f"Última decisión: {datetime.fromisoformat(person['consent_at']):%d/%m/%Y %H:%M}")
        export = st.session_state.get(f"export_{cid}")
        if export:
            b.download_button("Descargar sus datos (JSON)", export, f"datos-cliente-{cid}.json", "application/json",
                              icon=":material/download:", use_container_width=True, type="primary")
        else:
            b.button("Preparar sus datos", key=f"prepare_{cid}", use_container_width=True, icon=":material/folder_zip:",
                     on_click=_prepare_export, args=(cid,),
                     help="Derecho de acceso y portabilidad: todo lo que guardas de esta persona (queda registrado).")
        with st.expander("Borrar sus datos personales (derecho de supresión)", icon=":material/person_remove:"):
            st.caption("Se borran nombre, email, teléfono, NIF, dirección y notas. Sus compras siguen en las cifras "
                       "sin identificarle y **las facturas se conservan tal cual**, porque la ley obliga a guardarlas.")
            sure = st.checkbox("Confirmo que el cliente lo ha pedido", key=f"forget_ok_{cid}")
            if st.button("Borrar datos personales", disabled=not sure, key=f"forget_{cid}", icon=":material/delete:"):
                c.store.forget_customer(cid, by=c.username)
                st.session_state["customers_flash"] = "Datos personales borrados. Las facturas se conservan."
                _bump("customers_editor")
                st.rerun()


# --------------------------------------------------------------- automations
def automations_page() -> None:
    c = ctx()
    if not _require(c, "encargado"):
        return
    page_header(
        "Automatizaciones",
        "Se recalculan solas con cada venta: reposición, alertas, seguimiento de clientes e informes.",
        eyebrow="Inteligencia",
    )
    products = c.store.products()
    lines = c.store.sale_lines(start=clock.now() - timedelta(days=120))
    sales = c.store.sales()
    t1, t2, t3, t4 = st.tabs(["Reposición inteligente", "Alertas de stock", "Seguimiento de clientes", "Informes"])

    with t1:
        lead = st.slider("Días a cubrir hasta la próxima entrega", 3, 60, int(c.settings["reorder_lead_days"]),
                         help="Se compara con la demanda media diaria de los últimos 30 días.")
        sug = automation.reorder_suggestions(products, lines, lead_days=lead)
        a, b = st.columns(2)
        a.metric("Artículos a reponer", len(sug))
        b.metric("Inversión estimada", c.money(sug["estimated_cost"].sum()))
        if sug.empty:
            st.success("Tu stock cubre la demanda prevista. No hace falta comprar nada.")
        else:
            st.dataframe(
                sug, hide_index=True, use_container_width=True,
                column_config={
                    "sku": "Código", "name": "Artículo", "stock": "Stock actual",
                    "daily_demand": st.column_config.NumberColumn("Demanda/día", format="%.2f"),
                    "days_of_cover": st.column_config.NumberColumn("Días de cobertura", format="%.1f"),
                    "suggested_qty": "Pedir",
                    "estimated_cost": st.column_config.NumberColumn("Coste estimado", format=f"%.2f {c.symbol}"),
                },
            )
            a, b = st.columns(2)
            if a.button("Crear pedidos a proveedores", type="primary", icon=":material/shopping_cart_checkout:",
                        use_container_width=True):
                numbers = c.store.draft_purchases(sug, created_by=c.who)
                c.store.audit(c.username, "pedidos_generados", ", ".join(numbers))
                st.success(f"Pedidos en borrador: {', '.join(numbers)}. Revísalos y envíalos en Gestión → Compras.")
            b.download_button("Descargar sugerencias (CSV)", _csv(sug), "orden_de_compra.csv", "text/csv",
                              icon=":material/download:", use_container_width=True)

    with t2:
        low = automation.low_stock(products)
        if low.empty:
            st.success("Todos los artículos están por encima de su stock mínimo.")
        else:
            st.warning(f"{len(low)} artículo(s) en o por debajo del mínimo.")
            st.dataframe(
                low[["sku", "name", "category", "stock", "min_stock"]], hide_index=True, use_container_width=True,
                column_config={"sku": "Código", "name": "Artículo", "category": "Categoría",
                               "stock": "Stock", "min_stock": "Mínimo"},
            )

    with t3:
        days = st.slider("Considerar inactivo tras (días)", 15, 180, int(c.settings["inactive_days"]))
        customers = c.store.customers()
        allowed = customers[customers["marketing_consent"] == 1]
        inactive = automation.inactive_customers(allowed, sales, days)
        st.caption(f"Solo aparecen los clientes que aceptan recibir ofertas ({len(allowed)} de {len(customers)}). "
                   "El consentimiento se marca en Clientes → Protección de datos.")
        if inactive.empty:
            st.success("Ningún cliente con permiso para ofertas lleva tanto tiempo sin comprar.")
        for _, row in inactive.iterrows():
            with st.expander(f"{row['name']} · {row['days_inactive']} días sin comprar · "
                             f"{c.money(row['lifetime_value'])} acumulados"):
                message = st.text_area("Mensaje", automation.followup_message(row["name"], c.settings["business_name"]),
                                       height=170, key=f"msg_{row['id']}")
                subject = f"Te echamos de menos en {c.settings['business_name']}"
                if row["email"]:
                    st.link_button("Enviar por email", f"mailto:{row['email']}?subject={quote(subject)}"
                                   f"&body={quote(message)}", icon=":material/mail:")
                else:
                    st.caption("Este cliente no tiene email registrado.")

    with t4:
        rng = st.date_input("Periodo del informe", (clock.today().replace(day=1), clock.today()), format="DD/MM/YYYY")
        if isinstance(rng, tuple) and len(rng) == 2:
            start = datetime.combine(rng[0], time.min)
            end = datetime.combine(rng[1] + timedelta(days=1), time.min)
            period_lines = c.store.sale_lines(start, end)
            summary = (
                period_lines.groupby(["category", "name"])
                .agg(unidades=("quantity", "sum"), ventas_netas=("revenue", "sum"), margen=("margin", "sum"))
                .round(2).reset_index().sort_values("ventas_netas", ascending=False)
            )
            st.dataframe(summary, hide_index=True, use_container_width=True)
            a, b = st.columns(2)
            a.download_button("Resumen por artículo (CSV)", _csv(summary), "resumen_articulos.csv", "text/csv",
                              icon=":material/download:", use_container_width=True)
            b.download_button("Detalle de ventas (CSV)", _csv(c.store.sales(start, end)), "ventas_detalle.csv",
                              "text/csv", icon=":material/download:", use_container_width=True)


# ------------------------------------------------------------------ settings
def _billing_register_section(c, s: dict) -> None:
    st.markdown("##### Registro de facturación (VERI*FACTU, en preparación)")
    with st.container(border=True):
        st.caption("Cada ticket, factura, rectificativa y anulación queda en un registro encadenado con la huella "
                   "SHA-256 que exige la AEAT: no se puede modificar ni borrar, y tickets y facturas llevan el código QR "
                   "tributario. **Todavía no se envía a Hacienda**: esa parte llega en una próxima versión, así que "
                   "NirKanA aún no es un sistema VERI*FACTU completo y no imprime esa leyenda.")
        if s.get("verifactu") != "si":
            ready = s.get("demo_mode") != "si" and bool((s.get("tax_id") or "").strip())
            if not ready:
                st.info("Para activarlo hace falta vender de verdad (sin datos de ejemplo) y tener el NIF del "
                        "negocio en «Datos del negocio».", icon=":material/info:")
            confirm = st.checkbox("Entiendo que, una vez activado, el registro no se puede desactivar",
                                  disabled=not ready)
            if st.button("Activar el registro de facturación", disabled=not (ready and confirm),
                         icon=":material/verified:"):
                try:
                    c.store.enable_billing_register(c.username)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["settings_flash"] = "Registro de facturación activado."
                    st.rerun()
            return
        records = c.store.billing_records()
        st.success(f"Registro activo: {len(records)} registros encadenados.", icon=":material/link:")
        a, b = st.columns(2)
        if a.button("Comprobar la cadena", use_container_width=True, icon=":material/fact_check:"):
            check = c.store.verify_billing_chain()
            if check["ok"]:
                st.success(f"Cadena correcta: {check['checked']} registros comprobados.")
            else:
                st.error(f"Problema en el registro nº {check['broken_at']}: {check['reason']}.")
        b.download_button("Descargar registros (CSV)", _csv(records), f"registro-facturacion-{clock.today():%Y-%m-%d}.csv",
                          "text/csv", use_container_width=True, icon=":material/download:", disabled=records.empty)


def settings_page() -> None:
    c = ctx()
    if not _require(c, "admin"):
        return
    s = c.settings
    page_header("Configuración", "Identidad del negocio, impuestos, numeración y tipo de negocio.", eyebrow="Ajustes")
    if "settings_flash" in st.session_state:
        st.success(st.session_state.pop("settings_flash"))

    with st.form("settings"):
        st.markdown("##### Datos del negocio")
        a, b = st.columns(2)
        values = {
            "business_name": a.text_input("Nombre comercial", s["business_name"]),
            "tax_id": b.text_input("Identificación fiscal", s["tax_id"]),
            "address": a.text_input("Dirección", s["address"]),
            "phone": b.text_input("Teléfono", s["phone"]),
            "email": a.text_input("Email", s["email"]),
            "accent_color": b.color_picker("Color de marca", s["accent_color"]),
        }
        st.markdown("##### Ventas e impuestos")
        a, b, d = st.columns(3)
        currencies = list(CURRENCIES)
        values["currency"] = a.selectbox("Moneda", currencies, currencies.index(s["currency"]))
        zones = list(clock.TIMEZONES)
        current_zone = s.get("timezone") if s.get("timezone") in zones else clock.DEFAULT_TIMEZONE
        values["timezone"] = st.selectbox(
            "Zona horaria", zones, zones.index(current_zone), format_func=lambda z: f"{clock.TIMEZONES[z]} ({z})",
            help="Hora de tickets, facturas, caja, agenda y promociones por franja horaria.")
        values["tax_rate"] = b.number_input("IVA por defecto (%)", 0.0, 100.0, float(s["tax_rate"]), step=0.5,
                                            help="El de los productos que no tengan un IVA propio.")
        values["invoice_prefix"] = d.text_input("Prefijo de tickets", s["invoice_prefix"], max_chars=8)
        f, g = st.columns([3, 2])
        values["receipt_footer"] = f.text_input("Pie del ticket", s["receipt_footer"])
        papers = list(RECEIPT_PAPERS)
        values["receipt_paper"] = g.selectbox(
            "Papel del ticket", papers, papers.index(s.get("receipt_paper", "a4")) if s.get("receipt_paper") in papers
            else 0, format_func=RECEIPT_PAPERS.get,
            help="Térmico: impresoras de tickets de 80 o 58 mm (conectadas por USB, red o Bluetooth al equipo).")
        a, b = st.columns(2)
        values["invoice_series"] = a.text_input("Serie de facturas", s["invoice_series"], max_chars=8,
                                                help="Las facturas se numeran aparte: SERIE-AÑO-0001.")
        values["opening_float"] = b.number_input(f"Fondo de caja habitual ({c.symbol})", 0.0, 100000.0,
                                                 float(s["opening_float"] or 0), step=10.0)
        agenda_options = {"auto": "Automática según el tipo de negocio", "si": "Sí", "no": "No"}
        a, b = st.columns(2)
        values["agenda_enabled"] = a.selectbox(
            "Mostrar agenda de citas y reservas", list(agenda_options), list(agenda_options).index(
                s["agenda_enabled"] if s["agenda_enabled"] in agenda_options else "auto"),
            format_func=agenda_options.get)
        values["tables_enabled"] = b.selectbox(
            "Mostrar mesas, comandas y cocina", list(agenda_options), list(agenda_options).index(
                s.get("tables_enabled") if s.get("tables_enabled") in agenda_options else "auto"),
            format_func=agenda_options.get)
        st.markdown("##### Automatizaciones")
        a, b = st.columns(2)
        values["inactive_days"] = a.number_input("Días para considerar un cliente inactivo", 7, 365,
                                                 int(s["inactive_days"]))
        values["reorder_lead_days"] = b.number_input("Días de cobertura al reponer", 1, 120,
                                                     int(s["reorder_lead_days"]))
        st.markdown("##### Seguridad")
        values["max_discount_staff"] = st.number_input(
            "Descuento máximo de los empleados sin autorización (%)", 0.0, 100.0,
            float(s.get("max_discount_staff") or 10), step=5.0,
            help="Por encima, un encargado o el administrador lo autoriza con su usuario y PIN, y queda registrado.")
        values["session_minutes"] = st.number_input(
            "Cerrar la sesión tras estos minutos sin uso", 5, 1440, int(s.get("session_minutes") or 720), step=15,
            help="En tablets o móviles compartidos conviene un valor bajo, por ejemplo 15.")
        if st.form_submit_button("Guardar configuración", type="primary"):
            values["invoice_prefix"] = values["invoice_prefix"].strip().upper().replace("-", "") or "VTA"
            values["invoice_series"] = values["invoice_series"].strip().upper().replace("-", "") or "FAC"
            if values["invoice_series"] == values["invoice_prefix"]:
                st.error("La serie de facturas debe ser distinta del prefijo de tickets.")
            else:
                c.store.save_settings(values)
                c.store.audit(c.username, "configuracion_guardada")
                st.session_state["settings_flash"] = "Configuración guardada."
                st.rerun()

    replaceable = c.store.can_replace_data()
    st.markdown("##### Tipo de negocio y plantillas")
    with st.container(border=True):
        types = list(PRESETS)
        business_type = st.selectbox("Tipo de negocio", types, types.index(s["business_type"]),
                                     format_func=lambda k: PRESETS[k]["label"])
        if replaceable:
            st.caption("Cambiar solo el tipo adapta el vocabulario de la aplicación. Cargar la plantilla reemplaza "
                       "catálogo, clientes y ventas por los de ejemplo.")
            demo = st.toggle("Incluir 60 días de ventas de ejemplo", value=c.store.is_demo())
            confirm = st.checkbox("Entiendo que se borrarán los datos actuales")
            if not confirm:
                st.caption("Marca la casilla de arriba para activar «Cargar plantilla» y «Empezar desde cero».")
        else:
            st.caption("Cambiar el tipo adapta el vocabulario de la aplicación. " + FISCAL_DATA_MESSAGE)
            demo = confirm = False
        a, b, d = st.columns(3)
        if a.button("Cambiar solo el tipo", use_container_width=True):
            c.store.save_settings({"business_type": business_type})
            c.store.audit(c.username, "tipo_negocio_cambiado", PRESETS[business_type]["label"])
            st.session_state["settings_flash"] = f"Tipo cambiado a «{PRESETS[business_type]['label']}»."
            st.rerun()
        if replaceable and b.button("Cargar plantilla", type="primary", disabled=not confirm,
                                    use_container_width=True):
            try:
                with st.spinner("Cargando plantilla…"):
                    c.store.load_preset(business_type, with_demo_sales=demo)
            except FiscalDataError as exc:
                st.error(str(exc))
                return
            c.store.audit(c.username, "plantilla_cargada", PRESETS[business_type]["label"])
            st.session_state.pop("cart", None)
            st.session_state["settings_flash"] = "Plantilla cargada."
            st.rerun()
        if replaceable and d.button("Empezar desde cero", disabled=not confirm, use_container_width=True):
            try:
                c.store.reset()
            except FiscalDataError as exc:
                st.error(str(exc))
                return
            c.store.audit(c.username, "datos_borrados")
            st.session_state.pop("cart", None)
            st.rerun()

    _billing_register_section(c, s)

    st.markdown("##### Copia de seguridad")
    with st.container(border=True):
        if c.store.persistent_in_cloud:
            st.success(f"Tus datos se guardan en **{c.store.backend_label}** y no se pierden aunque la app se "
                       "reinicie.", icon=":material/cloud_done:")
            st.caption("Aun así, descarga una copia de vez en cuando. También sirve para pasar a esta base de datos "
                       "los datos que tenías antes: descarga la copia en la app antigua y restáurala aquí.")
        else:
            st.warning(f"Tus datos se guardan en un **{c.store.backend_label}**. En Streamlit Community "
                       "Cloud se pierden cuando la app se reinicia o se actualiza: descarga copias a menudo o "
                       "conecta una base de datos gratuita (ver README).", icon=":material/warning:")
        st.download_button(
            "Descargar copia de seguridad", c.store.backup_bytes(), f"ventas-{clock.today():%Y-%m-%d}.db",
            "application/octet-stream", icon=":material/download:", type="primary",
        )
        if not replaceable:
            st.caption("Restaurar una copia solo es posible en un negocio sin ventas (por ejemplo, al pasar a una base "
                       "de datos nueva): sobre datos reales borraría todo lo emitido después de la copia.")
            return
        upload = st.file_uploader("Restaurar desde una copia", type=["db"])
        confirm_restore = st.checkbox("Entiendo que se reemplazarán los datos actuales por los de la copia")
        if st.button("Restaurar copia", disabled=not (upload and confirm_restore), icon=":material/restore:"):
            try:
                c.store.restore(upload.getvalue())
                c.store.audit(c.username, "copia_restaurada", upload.name[:80])
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("cart", None)
                st.session_state["settings_flash"] = "Copia restaurada correctamente."
                st.rerun()
