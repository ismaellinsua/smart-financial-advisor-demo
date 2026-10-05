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
from ui.context import PAGES, ctx, get_store, logged_download
from ui.styles import insight, page_header, pos_mobile_css, style_figure
from core import clock
from core.fiscal_id import normalize as normalize_tax_id, tax_id_problem

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
ONBOARDING_STEPS = ["Tu negocio", "Datos fiscales", "Empezar"]


def onboarding() -> None:
    """First run: a three-step setup that leaves the business ready to sell and invoice, with real data."""
    store = get_store()
    data = st.session_state.setdefault("onboarding", {"step": 0})
    step = data["step"]
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header("Bienvenido a NirKanA", "Deja tu negocio listo para vender en tres pasos. Todo se puede cambiar "
                    "después en Configuración.", eyebrow=f"Paso {step + 1} de 3 · {ONBOARDING_STEPS[step]}")
        st.progress((step + 1) / 3)
        if step == 0:
            _onboarding_business(data)
        elif step == 1:
            _onboarding_fiscal(data)
        else:
            _onboarding_start(store, data)


def _onboarding_business(data: dict) -> None:
    with st.form("onboarding_business"):
        name = st.text_input("Nombre del negocio *", data.get("business_name", ""), placeholder="Ej.: Café Aurora",
                             help="Sale en tickets, facturas y en la cabecera de la app.")
        types = list(PRESETS)
        business_type = st.radio("Tipo de negocio", types, index=types.index(data.get("business_type", types[0])),
                                 format_func=lambda k: PRESETS[k]["label"],
                                 captions=[PRESETS[k]["description"] for k in types])
        zones = list(clock.TIMEZONES)
        zone = st.selectbox("Zona horaria", zones, zones.index(data.get("timezone", clock.DEFAULT_TIMEZONE)),
                            format_func=lambda z: clock.TIMEZONES[z],
                            help="La hora de tus tickets, facturas y cierres de caja.")
        if st.form_submit_button("Siguiente", type="primary", width="stretch", icon=":material/arrow_forward:"):
            if not name.strip():
                st.error("Escribe el nombre del negocio.")
                return
            data.update(business_name=name.strip(), business_type=business_type, timezone=zone, step=1)
            st.rerun()


def _onboarding_fiscal(data: dict) -> None:
    preset = PRESETS[data["business_type"]]
    st.caption("Son obligatorios en toda factura. Si ahora no los tienes a mano, puedes seguir y completarlos "
               "después: hasta entonces la app no emitirá facturas.")
    with st.form("onboarding_fiscal"):
        a, b = st.columns(2)
        tax_id = a.text_input("NIF / CIF", data.get("tax_id", ""), placeholder="B12345674")
        phone = b.text_input("Teléfono", data.get("phone", ""))
        address = st.text_input("Dirección fiscal", data.get("address", ""),
                                placeholder="Calle, número, código postal y ciudad")
        email = st.text_input("Email de contacto", data.get("email", ""))
        rates = [21.0, 10.0, 5.0, 4.0, 0.0]
        default_rate = float(data.get("tax_rate", preset["tax_rate"]))
        rate = st.selectbox("IVA habitual de lo que vendes", rates, rates.index(default_rate) if default_rate in rates
                            else 0, format_func=lambda r: f"{r:g} %",
                            help="21 % general, 10 % hostelería y alimentación, 4 % pan, leche, libros… Cada producto "
                                 "puede tener el suyo. Los precios se escriben con el IVA incluido, como en la carta.")
        back, forward = st.columns(2)
        go_back = back.form_submit_button("Atrás", width="stretch", icon=":material/arrow_back:")
        go_on = forward.form_submit_button("Siguiente", type="primary", width="stretch", icon=":material/arrow_forward:")
    if go_back:
        data["step"] = 0
        st.rerun()
    if go_on:
        problem = tax_id_problem(tax_id) if tax_id.strip() else None
        data.update(tax_id=normalize_tax_id(tax_id) if tax_id.strip() else "", address=address.strip(),
                    email=email.strip(), phone=phone.strip(), tax_rate=rate, tax_id_warning=problem, step=2)
        st.rerun()


def _onboarding_start(store, data: dict) -> None:
    preset = PRESETS[data["business_type"]]
    with st.container(border=True):
        st.markdown(f"**{escape(data['business_name'])}** · {preset['label']}")
        fiscal = " · ".join(escape(v) for v in (data.get("tax_id"), data.get("address")) if v)
        st.caption(fiscal or "Sin datos fiscales todavía: complétalos en Configuración antes de facturar.")
        st.caption(f"IVA habitual {data['tax_rate']:g} % · precios con IVA incluido · {clock.TIMEZONES[data['timezone']]}")
    if data.get("tax_id_warning"):
        st.warning(f"{data['tax_id_warning']} Revísalo si es un NIF español: saldrá en todas tus facturas.",
                   icon=":material/warning:")
    st.markdown("Para no partir de cero empezarás con un catálogo de ejemplo de tu tipo de negocio: cambia nombres "
                "y precios (con IVA incluido) antes de vender.")
    demo = st.toggle("Solo quiero probar la app con ventas de ejemplo", value=False,
                     help="Añade 60 días de ventas inventadas. Se borran al empezar de verdad.")
    back, create = st.columns(2)
    if back.button("Atrás", width="stretch", icon=":material/arrow_back:"):
        data["step"] = 1
        st.rerun()
    if create.button("Crear mi negocio", type="primary", width="stretch", icon=":material/rocket_launch:"):
        with st.spinner("Preparando tu negocio…"):
            store.load_preset(data["business_type"], with_demo_sales=demo)
            store.save_settings({k: data[k] for k in ("business_name", "timezone", "tax_id", "address", "email",
                                                      "phone", "tax_rate")})
        clock.set_timezone(data["timezone"])
        st.session_state.pop("onboarding", None)
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
    logged_download(
        st, "Antes, descargar una copia de mis datos", c.store.backup_bytes, f"ventas-{clock.today():%Y-%m-%d}.db",
        "application/octet-stream", icon=":material/download:", width="stretch",
    )
    confirmed = _identity_confirmed(c, "switch_secret")
    if st.button(f"Cambiar a «{PRESETS[business_type]['label']}»", type="primary", width="stretch",
                 icon=":material/swap_horiz:", disabled=not confirmed):
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


def _identity_confirmed(c, key: str) -> bool:
    """Ask again for the PIN or password before replacing data: a device left signed in is not enough."""
    secret = st.text_input("Tu PIN o contraseña, para confirmar", type="password", max_chars=128, key=key)
    if not secret:
        return False
    if c.user and c.store.confirm_secret(c.user["id"], secret):
        return True
    st.error("El PIN o contraseña no es correcto.")
    return False


def demo_banner(c) -> None:
    """Demonstration data is disposable: say so on every page and let the administrator start for real."""
    text, action = st.columns([5, 2], vertical_alignment="center")
    text.warning("**Modo demostración.** Los datos son de ejemplo y todo lo que vendas aquí se borrará al empezar "
                 "de verdad.", icon=":material/science:")
    if c.can("admin") and action.button("Empezar a vender de verdad", type="primary", width="stretch",
                                        icon=":material/rocket_launch:"):
        _start_for_real_dialog()


@st.dialog("Empezar a vender de verdad")
def _start_for_real_dialog() -> None:
    st.write("Se borrarán los datos de ejemplo (productos, clientes, ventas, facturas y cierres) y configurarás tu "
             "negocio desde cero. A partir de ahí, las ventas y facturas reales **no se podrán borrar**: la ley obliga "
             "a conservarlas.")
    c = ctx()
    if st.checkbox("Entiendo que se borrarán los datos de ejemplo", key="start_real_confirm") and \
            _identity_confirmed(c, "start_real_secret") and st.button(
            "Borrar ejemplos y empezar", type="primary", width="stretch"):
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
    if c.multi_location:
        places = {loc["id"]: loc["name"] for loc in c.store.locations(include_inactive=True)}
        per = (cur_sales.assign(place=cur_sales["location_id"].map(places).fillna("—"))
               .groupby("place")["total"].agg(["sum", "count"]).reset_index().sort_values("sum", ascending=False))
        per["ticket"] = per["sum"] / per["count"]
        st.markdown("**Por local**")
        st.dataframe(per, hide_index=True, width="stretch", column_config={
            "place": "Local", "sum": st.column_config.NumberColumn("Facturación", format=f"%.2f {c.symbol}"),
            "count": "Ventas", "ticket": st.column_config.NumberColumn("Ticket medio", format=f"%.2f {c.symbol}")})
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
        st.plotly_chart(style_figure(fig), width="stretch", config={"displayModeBar": False})
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
            st.plotly_chart(style_figure(fig), width="stretch", config={"displayModeBar": False})

    left, mid, right = st.columns([1, 1, 1], gap="large")
    with left, st.container(border=True):
        st.markdown("**Formas de pago**")
        pay = cur_sales.groupby("payment_method")["total"].sum().sort_values()
        if not pay.empty:
            fig = go.Figure(go.Bar(
                x=pay.values, y=pay.index, orientation="h", marker_color=accent,
                hovertemplate="%{y}<br><b>%{x:,.2f} " + c.symbol + "</b><extra></extra>",
            ))
            st.plotly_chart(style_figure(fig, 240), width="stretch", config={"displayModeBar": False})
    with mid, st.container(border=True):
        st.markdown("**Por categoría**")
        cat = cur_lines.groupby("category")["revenue"].sum().sort_values()
        if not cat.empty:
            fig = go.Figure(go.Bar(
                x=cat.values, y=cat.index, orientation="h", marker_color=accent,
                hovertemplate="%{y}<br><b>%{x:,.2f} " + c.symbol + "</b> netos<extra></extra>",
            ))
            st.plotly_chart(style_figure(fig, 240), width="stretch", config={"displayModeBar": False})
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
            st.plotly_chart(style_figure(fig, 60 + 40 * len(by_user)), width="stretch",
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


def _scan(skus: dict) -> None:
    """A barcode scanner types the code and Enter: an exact code goes straight to the ticket and the box clears."""
    code = str(st.session_state.get("pos_query", "")).strip().lower()
    if code in skus:
        _add_to_cart(skus[code])
        st.session_state["pos_query"] = ""
        st.session_state["pos_flash"] = ("toast", f"Añadido: {code.upper()}")


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
    components.html(with_print_button(receipt_html(sale, c.ticket_settings(sale.get("location_id")))), height=preview_height, scrolling=True)
    text = receipt_text(sale, c.settings)
    a, b, d = st.columns(3)
    number = whatsapp_number(sale.get("customer_phone") or "")
    a.link_button("WhatsApp", f"https://wa.me/{number}?text={quote(text)}", icon=":material/chat:",
                  width="stretch", help="Abre WhatsApp con el ticket escrito, listo para enviar.")
    email = sale.get("customer_email") or ""
    subject = f"Ticket {sale['number']} · {c.settings.get('business_name', '')}"
    b.link_button("Email", f"mailto:{quote(email)}?subject={quote(subject)}&body={quote(text)}",
                  icon=":material/mail:", width="stretch", help="Abre tu correo con el ticket escrito.")
    d.download_button("Archivo", receipt_html(sale, c.ticket_settings(sale.get("location_id"))), file_name=f"{sale['number']}.html",
                      mime="text/html", icon=":material/download:", width="stretch",
                      help="Descarga el ticket para guardarlo o imprimirlo más tarde.")


@st.dialog("Venta registrada")
def _sale_dialog(sale_id: int) -> None:
    c = ctx()
    sale = c.store.sale(sale_id)
    st.success(f"Ticket **{sale['number']}** · {c.money(sale['total'])} · {sale['payment_method']}")
    _ticket_actions(c, sale, preview_height=360)
    if st.button("Nueva venta", type="primary", width="stretch"):
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

    products = c.products_here()
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
                      type="primary", width="stretch", icon=":material/shopping_cart:", disabled=not units,
                      on_click=st.session_state.__setitem__, args=("pos_view", "ticket"))
        else:
            st.button("Seguir añadiendo", key="pos_to_catalog", width="stretch", icon=":material/arrow_back:",
                      on_click=st.session_state.__setitem__, args=("pos_view", "catalogo"))

    catalog_col, ticket_col = st.columns([3, 2], gap="large")
    with catalog_col, st.container(key="pos_catalog"):
        f1, f2 = st.columns([2, 3])
        query = f1.text_input("Buscar", placeholder="Nombre, código o escanea…", label_visibility="collapsed",
                              key="pos_query", on_change=_scan, args=(dict(zip(products["sku"].str.lower(),
                                                                              products["id"].astype(int))),))
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
                    width="stretch", disabled=bool(p["track_stock"]) and available <= 0,
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
        if cart and st.button("Vaciar ticket", width="stretch", icon=":material/delete:"):
            cart.clear()
            _persist_cart(c, cart)
            st.rerun()


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
        logged_download(st, "Exportar a CSV", _csv(df.drop(columns=["id", "place"])), "ventas.csv", "text/csv",
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
            _ticket_actions(c, sale)
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
    logged_download(st, "Exportar devoluciones a CSV", _csv(df.drop(columns=["id"])), "devoluciones.csv", "text/csv",
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
    logged_download(st, "Exportar facturas a CSV", _csv(df.drop(columns=["id"])), "facturas.csv", "text/csv",
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
OFFLINE_TILL_URL = "https://nirkana.es/caja/"


def _offline_till_panel(c) -> None:
    """The till that works without internet: its catalogue file goes out from here and its sales come back."""
    from core.store_offline import DEVICES, OfflineImportError

    with st.expander("Caja sin conexión", icon=":material/wifi_off:"):
        st.markdown(
            "Si se cae internet, sigue cobrando con la **caja sin conexión**: se instala en el móvil o la tablet y "
            "funciona sin red. Guarda las ventas en el dispositivo y aquí las importas cuando vuelva la conexión.")
        a, b = st.columns([1, 2], vertical_alignment="bottom")
        device = a.selectbox("Número de caja", list(DEVICES),
                             help="Uno distinto por dispositivo: cada caja numera sus tickets en su propia serie.")
        logged_download(b, "Descargar archivo de catálogo", c.store.offline_package(device, c.location_id),
                        f"catalogo-caja{device}.json", mime="application/json", icon=":material/download:")
        st.link_button("Abrir la caja sin conexión", OFFLINE_TILL_URL, icon=":material/open_in_new:")
        st.caption("1) Abre la caja en el dispositivo e **instálala** (menú del navegador → Instalar o Añadir a pantalla "
                   "de inicio). 2) Carga el archivo de catálogo. 3) Vuelve a descargarlo y cargarlo cuando cambies "
                   "precios o productos. La caja sin conexión no aplica promociones, puntos ni clientes.")
        st.markdown("**Importar ventas**")
        upload = st.file_uploader("Archivo de ventas de la caja sin conexión", type=["json"], key="offline_upload")
        if upload is not None and st.button("Importar", type="primary", icon=":material/upload:"):
            try:
                result = c.store.import_offline_sales(upload.getvalue(), c.who)
            except OfflineImportError as exc:
                st.error(str(exc))
            else:
                text = (f"{result['imported']} ventas importadas ({c.money(result['total'])})"
                        + (f", {result['repeated']} ya estaban" if result["repeated"] else "")
                        + (f", {result['rejected']} sin importar" if result["rejected"] else "") + ".")
                (st.warning if result["rejected"] else st.success)(
                    text + ("" if result["rejected"] else " Ya puedes borrarlas de la caja sin conexión."))
                for note in result["notes"]:
                    st.caption(note)


def cash_page() -> None:
    c = ctx()
    if not _require(c, "encargado"):
        return
    page_header("Cierre de caja" + (f" · {c.location_name}" if c.multi_location else ""),
                "Cuadra el efectivo al final del día y guarda el informe firmado.", eyebrow="Caja")
    if "cash_flash" in st.session_state:
        st.success(st.session_state.pop("cash_flash"))
    _offline_till_panel(c)
    day = st.date_input("Día", clock.today(), max_value=clock.today(), format="DD/MM/YYYY", key="cash_day")
    summary = c.store.day_summary(day, c.location_id)
    closing = c.store.cash_closing(day, c.location_id)

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
            st.dataframe(df, hide_index=True, width="stretch",
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
    history = c.store.cash_closings(c.location_id if c.multi_location else None)
    if history.empty:
        st.caption("Todavía no has cerrado ninguna caja.")
    else:
        st.dataframe(history.drop(columns=["closed_at"]), hide_index=True, width="stretch",
                     column_config={
                         "day": st.column_config.DateColumn("Día", format="DD/MM/YYYY"),
                         "total_sales": st.column_config.NumberColumn("Vendido", format=f"%.2f {c.symbol}"),
                         "sales_count": "Ventas",
                         "expected_cash": st.column_config.NumberColumn("Esperado", format=f"%.2f {c.symbol}"),
                         "counted_cash": st.column_config.NumberColumn("Contado", format=f"%.2f {c.symbol}"),
                         "difference": st.column_config.NumberColumn("Diferencia", format=f"%+.2f {c.symbol}"),
                     })
        logged_download(st, "Exportar cierres a CSV", _csv(history), "cierres_de_caja.csv", "text/csv",
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
    if st.button("Cerrar caja", type="primary", width="stretch", disabled=counted is None,
                 icon=":material/lock:"):
        try:
            closing = c.store.close_cash(day, opening, counted, notes, closed_by=c.who, location_id=c.location_id)
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
    st.download_button("Descargar informe (PDF)", cash_closing_pdf(closing, c.ticket_settings(closing.get("location_id"))),
                       f"cierre-{day:%Y-%m-%d}.pdf", "application/pdf", type="primary",
                       width="stretch", icon=":material/picture_as_pdf:")
    if st.button("Reabrir caja", width="stretch", icon=":material/lock_open:"):
        c.store.reopen_cash(day, c.location_id)
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
              width="stretch")
    day = b2.date_input("Día", key="agenda_day", format="DD/MM/YYYY", label_visibility="collapsed")
    b3.button("", icon=":material/chevron_right:", on_click=_shift_agenda_day, args=(1,), help="Día siguiente",
              width="stretch")
    b4.button("Hoy", on_click=_shift_agenda_day, args=(None,), width="stretch")

    start = datetime.combine(day, time.min)
    df = c.store.appointments(start, start + timedelta(days=1))
    pending = df[df["status"] == "pendiente"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Citas del día" if cfg["single"] else "Reservas del día", len(df[df["status"] != "cancelada"]))
    m2.metric("Pendientes", len(pending))
    expected = pending["price"].fillna(0).astype(float).sum()
    m3.metric("Ingresos previstos", c.money_short(expected), help="Servicios pendientes, impuestos incluidos.")

    if c.can("encargado"):
        _online_booking_panel(c, cfg)

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
    people = int(a.get("people") or 0)
    phone = a["customer_phone"] if isinstance(a.get("customer_phone"), str) else ""
    detail = " · ".join(x for x in [
        "Online" if a.get("source") == "online" else "",
        f"{people} pers." if people else "",
        a["service"] if isinstance(a["service"], str) else "",
        c.money(float(a["price"])) if pd.notna(a["price"]) else "",
        phone,
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
            with x.popover("Cobrar", icon=":material/payments:", width="stretch"):
                method = st.segmented_control("Forma de pago", PAYMENT_METHODS, default=PAYMENT_METHODS[0],
                                              key=f"appt_pay_{aid}") or PAYMENT_METHODS[0]
                if st.button("Cobrar ahora", type="primary", key=f"appt_charge_{aid}", width="stretch"):
                    try:
                        sale = c.store.charge_appointment(aid, method, user_name=c.who, location_id=c.location_id)
                    except SaleError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["last_sale"] = sale["id"]
                        st.rerun()
        else:
            x.button("Hecha", key=f"appt_done_{aid}", on_click=_set_appointment_status, args=(aid, "completada"),
                     icon=":material/check:", width="stretch")
        y.button("No vino", key=f"appt_noshow_{aid}", on_click=_set_appointment_status,
                 args=(aid, "no_presentado"), width="stretch")
        z.button("Cancelar", key=f"appt_cancel_{aid}", on_click=_set_appointment_status, args=(aid, "cancelada"),
                 width="stretch")
        if phone and a["starts_at"] >= clock.now():
            business = c.settings.get("business_name", "")
            text = (f"Hola, {a['who']}: te recordamos tu reserva en {business} el {a['starts_at']:%d/%m} a las "
                    f"{a['starts_at']:%H:%M}. Si no puedes venir, avísanos respondiendo a este mensaje. ¡Gracias!")
            st.link_button("Recordar por WhatsApp", f"https://wa.me/{whatsapp_number(phone)}?text={quote(text)}",
                           icon=":material/chat:", width="stretch",
                           help="Abre WhatsApp con el recordatorio escrito, listo para enviar.")


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
        phone = st.text_input("Teléfono (para recordarle la cita)", max_chars=20)
        people = 0 if cfg["single"] else st.number_input("Personas", min_value=1, max_value=200, value=2, step=1)
        product_id = st.selectbox(c.preset["item_label"], [0, *services],
                                  format_func=lambda i: services.get(i, "Sin servicio"),
                                  index=1 if cfg["single"] and services else 0)
        notes = st.text_input("Notas", placeholder="Ej.: mesa para 4, alergia a frutos secos…")
        if st.form_submit_button("Guardar", type="primary", width="stretch", icon=":material/event:"):
            try:
                c.store.create_appointment(
                    datetime.combine(when_day, when_time), duration,
                    product_id=product_id or None, customer_id=customer_id or None,
                    customer_name=walk_in, notes=notes, allow_overlap=not cfg["single"], created_by=c.who,
                    people=people, phone=phone,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["agenda_flash"] = ("success", f"Guardada para el {when_day:%d/%m} a las {when_time:%H:%M}.")
                st.session_state["agenda_goto"] = when_day  # applied before the date picker is drawn
                st.rerun()


def _online_booking_panel(c, cfg: dict) -> None:
    """Opening hours and rules for the public booking page, its link and a QR to print for the counter."""
    from core.store_bookings import WEEKDAYS as DAY_NAMES
    from ui.booking import booking_url

    rules = c.store.booking_rules(c.settings)
    state = "abiertas" if rules["enabled"] else "cerradas"
    with st.expander(f"Reservas online · {state}", icon=":material/language:"):
        if rules["enabled"]:
            url = booking_url()
            st.markdown("Comparte este enlace (web, Instagram, Google, WhatsApp) o imprime el código QR:")
            st.code(url, language=None)
            import io

            import segno

            png = io.BytesIO()
            segno.make_qr(url, error="m").save(png, kind="png", scale=8, border=2)
            q1, q2 = st.columns([1, 3], vertical_alignment="center")
            q1.image(png.getvalue(), width=140)
            q2.download_button("Descargar QR", png.getvalue(), file_name="qr-reservas.png", mime="image/png",
                               icon=":material/qr_code_2:")
        with st.form("booking_rules"):
            enabled = st.toggle("Aceptar reservas online", value=rules["enabled"])
            st.markdown("**Horario** (vacío = cerrado). Ejemplo: `09:00-14:00, 16:00-20:00`")
            hours = {}
            cols = st.columns(2)
            for day, label in enumerate(DAY_NAMES):
                current = ", ".join(f"{a:%H:%M}-{b:%H:%M}" for a, b in rules["hours"].get(day, []))
                hours[day] = cols[day % 2].text_input(label, current, max_chars=80, key=f"booking_h_{day}")
            closed = st.text_input("Días cerrados (festivos, vacaciones)", c.settings.get("booking_closed", ""),
                                   placeholder="24/12/2026, 25/12/2026", max_chars=1000)
            a, b = st.columns(2)
            values = {"enabled": enabled, "hours": hours, "closed": closed}
            if cfg["single"]:
                products = c.store.products()
                names = {int(i): n for i, n in zip(products["id"], products["name"])}
                values["services"] = st.multiselect(
                    "Servicios que se pueden reservar", list(names), [i for i in rules["services"] if i in names],
                    format_func=names.get, help="Si no eliges ninguno, la persona reserva una cita sin elegir servicio.")
                values["duration"] = a.number_input("Duración de cada cita (min)", 5, 600, rules["duration"], 5)
            else:
                values["services"] = []
                values["duration"] = a.number_input("Tiempo de mesa (min)", 5, 600, rules["duration"], 5)
                values["capacity"] = b.number_input("Comensales a la vez", 1, 1000, rules["capacity"], 1,
                                                    help="Suma de personas que caben al mismo tiempo.")
                values["max_party"] = a.number_input("Máximo de personas por reserva", 1, 100, rules["max_party"], 1)
            values["step"] = b.number_input("Una hora de inicio cada (min)", 5, 240, rules["step"], 5)
            values["days"] = a.number_input("Se puede reservar con hasta (días)", 1, 365, rules["days_ahead"], 1)
            values["notice_hours"] = b.number_input("Antelación mínima (horas)", 0, 168, rules["notice_hours"], 1)
            st.caption("Si el envío de emails está configurado, la persona recibe la confirmación y un recordatorio "
                       "el día antes, y tú un aviso de cada reserva nueva en el email del negocio.")
            if st.form_submit_button("Guardar", type="primary"):
                try:
                    c.store.save_booking_rules(values)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    c.store.audit(c.username, "reservas_online", "abiertas" if enabled else "cerradas")
                    st.session_state["agenda_flash"] = ("success", "Reservas online guardadas.")
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
    m3.metric("Cierre de sesión por inactividad", f"{int(c.settings.get('session_minutes') or 480) // 60} h")

    roles_help = ("**Administrador:** todo, incluida la configuración y el equipo. "
                  "**Encargado:** panel, caja, catálogo, clientes, facturas y anulaciones. "
                  "**Empleado:** vender, agenda y consultar tickets.")
    st.caption(roles_help)
    places = {loc["id"]: loc["name"] for loc in c.locations}
    st.dataframe(
        users.assign(role=users["role"].map(ROLES), active=users["active"].astype(bool),
                     two_factor=users["two_factor"].astype(bool),
                     last_login=pd.to_datetime(users["last_login"].replace("", None)),
                     place=users["location_id"].map(places).fillna("Cualquiera")),
        hide_index=True, width="stretch",
        column_order=["name", "username", "role", *(["place"] if c.multi_location else []), "active", "two_factor",
                      "last_login"],
        column_config={"name": "Nombre", "username": "Usuario", "role": "Rol", "place": "Local",
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
    st.caption("Accesos, intentos fallidos, anulaciones, facturas, cierres de caja, cambios de configuración y "
               "cada descarga de datos (exportaciones, copias y datos de clientes).")
    log = c.store.audit_log()
    views = {"Todo": None, "Accesos fallidos": {"acceso_fallido"},
             "Descargas de datos": {"exportacion", "datos_exportados"},
             "Clientes (RGPD)": {"datos_exportados", "cliente_suprimido", "consentimiento_publicidad"}}
    shown = st.segmented_control("Mostrar", list(views), default="Todo", key="audit_view") or "Todo"
    if views[shown]:
        log = log[log["action"].isin(views[shown])]
    st.dataframe(log, hide_index=True, width="stretch", column_config={
        "happened_at": st.column_config.DatetimeColumn("Cuándo", format="DD/MM/YYYY HH:mm:ss"),
        "username": "Usuario", "action": "Acción", "detail": "Detalle",
    })
    logged_download(st, "Exportar registro a CSV", _csv(log), "registro_actividad.csv", "text/csv",
                       icon=":material/download:")
    errors = c.store.recent_errors(7)
    with st.expander(f"Errores de la app en 7 días: {len(errors)}", icon=":material/bug_report:"):
        if errors.empty:
            st.caption("Ninguno. Si alguna pantalla falla, aparecerá aquí con su referencia.")
        else:
            st.dataframe(errors, hide_index=True, width="stretch", column_config={
                "happened_at": st.column_config.DatetimeColumn("Cuándo", format="DD/MM/YYYY HH:mm"),
                "ref": "Referencia", "page": "Pantalla", "username": "Usuario", "kind": "Tipo", "where_": "Dónde"})


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
    location = target.get("location_id")
    if c.multi_location:
        places = {0: "Cualquier local", **{loc["id"]: loc["name"] for loc in c.locations}}
        current = int(location) if pd.notna(location) and int(location) in places else 0
        location = st.selectbox("Local", list(places), index=list(places).index(current), format_func=places.get,
                                key=f"team_location_{uid}",
                                help="Fijado a un local, solo vende, cobra y ve la caja de ese local.") or None
    new_secret = st.text_input("Nuevo PIN o contraseña (opcional)", type="password", max_chars=128,
                               key=f"team_secret_{uid}")
    if st.button("Guardar cambios", type="primary", key=f"team_save_{uid}", icon=":material/save:"):
        try:
            c.store.update_user(uid, role=new_role, active=active, by=c.username)
            if c.multi_location:
                c.store.set_user_location(uid, location)
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


SHOP_TEMPLATE = ("pedido;fecha;sku;cantidad;precio;descuento;envio;total;estado\n"
                 "1001;05/10/2026 10:30;CAM-001;2;39,90;0;4,90;84,70;pagado\n")


def _online_shop_panel(c) -> None:
    """Shopify, WooCommerce or any shop, by files: catalogue out, orders in."""
    from core.store_ecommerce import ShopImportError

    with st.expander("Tienda online (Shopify, WooCommerce…)", icon=":material/shopping_cart:"):
        st.markdown("**1. Sube tu catálogo a la tienda** (productos, precios con IVA y stock"
                    + (f" de {c.location_name}" if c.multi_location else "") + ")")
        a, b = st.columns(2)
        logged_download(a, "Catálogo para Shopify", c.store.shop_catalog_csv("shopify", c.location_id),
                        "catalogo-shopify.csv", mime="text/csv", icon=":material/download:", width="stretch")
        logged_download(b, "Catálogo para WooCommerce", c.store.shop_catalog_csv("woocommerce", c.location_id),
                        "catalogo-woocommerce.csv", mime="text/csv", icon=":material/download:", width="stretch")
        st.caption("En Shopify: Productos → Importar (marca «Sobrescribir productos» para actualizar precios y stock). "
                   "En WooCommerce: Productos → Importar (marca «Actualizar productos existentes»). Los productos se "
                   "relacionan por su código (SKU).")
        st.markdown("**2. Trae los pedidos de la tienda** (se registran como ventas y descuentan stock)")
        upload = st.file_uploader("Exportación de pedidos (CSV)", type=["csv"], key="shop_orders",
                                  help="Shopify: Pedidos → Exportar → CSV para Excel. Otras tiendas: la plantilla.")
        products = c.store.products()
        no_stock = products[products["track_stock"] == 0]
        options = {0: "No incluir el envío", **dict(zip(no_stock["id"].astype(int), no_stock["name"]))}
        guess = next((pid for pid, name in options.items() if pid and "env" in name.lower()), 0)
        x, y = st.columns(2)
        method = x.selectbox("Cobrados con", PAYMENT_METHODS, key="shop_method")
        shipping = y.selectbox("Producto para los envíos", list(options), index=list(options).index(guess),
                               format_func=options.get, key="shop_shipping",
                               help="Un producto sin control de stock (p. ej. «Envío»). Créalo en «Nuevo» si no lo tienes.")
        if upload is not None and st.button("Importar pedidos", type="primary", icon=":material/upload:"):
            try:
                result = c.store.import_shop_orders(upload.getvalue(), method, c.location_id, shipping or None, c.who)
            except (ShopImportError, ValueError) as exc:
                st.error(str(exc))
            else:
                text = (f"{result['imported']} pedidos importados ({c.money(result['total'])})"
                        + (f", {result['repeated']} ya estaban" if result["repeated"] else "")
                        + (f", {result['skipped']} sin cobrar" if result["skipped"] else "")
                        + (f", {result['rejected']} con problemas" if result["rejected"] else "") + ".")
                (st.warning if result["rejected"] else st.success)(text)
                for note in result["notes"][:50]:
                    st.caption(note)
        st.download_button("Plantilla para otras tiendas (CSV)", SHOP_TEMPLATE.encode("utf-8-sig"),
                           "plantilla-pedidos.csv", "text/csv", icon=":material/description:")
        st.caption("Solo se leen el número de pedido, la fecha, los productos, el descuento, el envío y el total: "
                   "los datos personales de tus clientes en el archivo no se importan. Importar dos veces el mismo "
                   "archivo no duplica pedidos.")


def _stock_by_location(c) -> None:
    with st.expander("Stock por local y traspasos", icon=":material/swap_horiz:"):
        table = c.store.stock_by_location()
        names = [loc["name"] for loc in c.store.locations(include_inactive=True)]
        st.dataframe(table, hide_index=True, width="stretch", column_order=["sku", "name", *names, "Total"],
                     column_config={"sku": "Código", "name": "Artículo"})
        products = dict(zip(table["id"].astype(int), table["name"]))
        places = {loc["id"]: loc["name"] for loc in c.locations}
        with st.form("transfer_stock", clear_on_submit=True):
            st.markdown("**Traspasar stock**")
            product = st.selectbox("Artículo", list(products), format_func=products.get)
            a, b, d = st.columns(3)
            origin = a.selectbox("Desde", list(places), format_func=places.get)
            target = b.selectbox("Hasta", list(places), index=min(1, len(places) - 1), format_func=places.get)
            quantity = d.number_input("Unidades", min_value=1, value=1, step=1)
            if st.form_submit_button("Traspasar", type="primary", icon=":material/swap_horiz:"):
                try:
                    c.store.transfer_stock(product, quantity, origin, target, c.who)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    c.store.audit(c.username, "traspaso_stock",
                                  f"{quantity} × {products[product]}: {places[origin]} → {places[target]}")
                    st.session_state["products_flash"] = (f"Traspasadas {quantity} unidades de «{products[product]}» "
                                                          f"de {places[origin]} a {places[target]}.")
                    _bump("products_editor")
                    st.rerun()


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
    if c.multi_location:  # the table shows (and adjusts) the stock at the location chosen in the menu
        here = c.store.stock_at(c.location_id)
        df["stock"] = df["id"].map(here).fillna(0).astype(int)
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
            df, key=_editor_key("products_editor"), hide_index=True, width="stretch",
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
                "stock": st.column_config.NumberColumn(f"Stock en {c.location_name}" if c.multi_location else "Stock",
                                                       step=1),
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
                        c.store.adjust_stock(pid, delta, "Ajuste en el catálogo", user_name=c.who, location_id=c.location_id)
                    changed += bool(changes or delta)
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
            else:
                st.session_state["products_flash"] = f"{changed} cambio(s) guardado(s)."
                _bump("products_editor")
                st.rerun()

        if c.multi_location:
            _stock_by_location(c)
        _online_shop_panel(c)
        with st.expander("Ajustes de stock", icon=":material/history:"):
            moves = c.store.stock_moves()
            if moves.empty:
                st.caption("Todavía no hay ajustes manuales de stock.")
            else:
                st.dataframe(moves, hide_index=True, width="stretch", column_config={
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

    ranking = automation.customer_ranking(c.store.customers(), c.store.customer_totals())
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
        ranking, key=_editor_key("customers_editor"), hide_index=True, width="stretch",
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

    _customer_card(c, ranking)
    _privacy_section(c, c.store.customers())


def _customer_card(c, ranking) -> None:
    """Everything about one customer at a glance, e.g. before calling them or at the counter."""
    if ranking.empty:
        return
    with st.expander("Ficha del cliente", icon=":material/badge:"):
        names = dict(zip(ranking["id"].astype(int), ranking["name"]))
        cid = st.selectbox("Cliente", list(names), format_func=names.get, key="customer_card")
        card = c.store.customer_history(cid)
        done = card["sales"][card["sales"]["status"] == "completada"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Compras", len(done))
        m2.metric("Gastado", c.money_short(done["total"].sum()))
        m3.metric("Ticket medio", c.money_short(done["total"].mean() if len(done) else 0))
        m4.metric("Puntos", card["points"])
        row = ranking.set_index("id").loc[cid]
        contact = " · ".join(str(row[k]) for k in ("phone", "email") if isinstance(row[k], str) and row[k])
        if contact:
            st.caption(contact)
        if isinstance(row["notes"], str) and row["notes"]:
            st.info(row["notes"], icon=":material/sticky_note_2:")
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.markdown("**Últimas compras**")
            if card["sales"].empty:
                st.caption("Todavía no ha comprado.")
            else:
                st.dataframe(card["sales"], hide_index=True, width="stretch",
                             column_order=["number", "created_at", "payment_method", "total", "status"],
                             column_config={"number": "Ticket", "payment_method": "Pago", "status": "Estado",
                                            "created_at": st.column_config.DatetimeColumn("Fecha",
                                                                                          format="DD/MM/YYYY HH:mm"),
                                            "total": st.column_config.NumberColumn("Total",
                                                                                   format=f"%.2f {c.symbol}")})
        with right:
            st.markdown("**Lo que más compra**")
            if card["favourites"].empty:
                st.caption("—")
            for f in card["favourites"].itertuples():
                st.markdown(f"- {f.name} · {int(f.units)} ud.")
            if not card["upcoming"].empty:
                st.markdown("**Próximas citas**")
                for a in card["upcoming"].itertuples():
                    st.markdown(f"- {a.starts_at:%d/%m %H:%M}" + (f" · {a.notes}" if a.notes else ""))


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
                              icon=":material/download:", width="stretch", type="primary")
        else:
            b.button("Preparar sus datos", key=f"prepare_{cid}", width="stretch", icon=":material/folder_zip:",
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
    totals = c.store.customer_totals()
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
                sug, hide_index=True, width="stretch",
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
                        width="stretch"):
                numbers = c.store.draft_purchases(sug, created_by=c.who)
                c.store.audit(c.username, "pedidos_generados", ", ".join(numbers))
                st.success(f"Pedidos en borrador: {', '.join(numbers)}. Revísalos y envíalos en Gestión → Compras.")
            logged_download(b, "Descargar sugerencias (CSV)", _csv(sug), "orden_de_compra.csv", "text/csv",
                              icon=":material/download:", width="stretch")

    with t2:
        low = automation.low_stock(products)
        if low.empty:
            st.success("Todos los artículos están por encima de su stock mínimo.")
        else:
            st.warning(f"{len(low)} artículo(s) en o por debajo del mínimo.")
            st.dataframe(
                low[["sku", "name", "category", "stock", "min_stock"]], hide_index=True, width="stretch",
                column_config={"sku": "Código", "name": "Artículo", "category": "Categoría",
                               "stock": "Stock", "min_stock": "Mínimo"},
            )

    with t3:
        days = st.slider("Considerar inactivo tras (días)", 15, 180, int(c.settings["inactive_days"]))
        customers = c.store.customers()
        allowed = customers[customers["marketing_consent"] == 1]
        inactive = automation.inactive_customers(allowed, totals, days)
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
            st.dataframe(summary, hide_index=True, width="stretch")
            a, b = st.columns(2)
            logged_download(a, "Resumen por artículo (CSV)", _csv(summary), "resumen_articulos.csv", "text/csv",
                              icon=":material/download:", width="stretch")
            logged_download(b, "Detalle de ventas (CSV)", lambda: _csv(c.store.sales(start, end)), "ventas_detalle.csv",
                              "text/csv", icon=":material/download:", width="stretch")


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
        if a.button("Comprobar la cadena", width="stretch", icon=":material/fact_check:"):
            check = c.store.verify_billing_chain()
            if check["ok"]:
                st.success(f"Cadena correcta: {check['checked']} registros comprobados.")
            else:
                st.error(f"Problema en el registro nº {check['broken_at']}: {check['reason']}.")
        logged_download(b, "Descargar registros (CSV)", _csv(records), f"registro-facturacion-{clock.today():%Y-%m-%d}.csv",
                          "text/csv", width="stretch", icon=":material/download:", disabled=records.empty)


def _locations_settings(c) -> None:
    """Shops or premises of the business. With one place there's nothing to set up; the second one adds a
    location picker to the menu and splits sales, cash, tables and stock by location."""
    st.markdown("##### Locales")
    every = c.store.locations(include_inactive=True)
    with st.container(border=True):
        if not every:
            st.caption("Tu negocio tiene un solo local. Si abres otro, añádelo aquí: el actual pasará a llamarse "
                       "«Principal» y conservará todo su stock, ventas y cierres.")
        else:
            st.caption("Cada local vende de su propio stock, cierra su caja y tiene sus mesas. Las personas fijadas "
                       "a un local (en Equipo y seguridad) solo trabajan en él.")
            main = every[0]["id"]
            for loc in every:
                with st.expander(f"{loc['name']}{'' if loc['active'] else ' · cerrado'}", icon=":material/storefront:"):
                    with st.form(f"location_{loc['id']}"):
                        name = st.text_input("Nombre", loc["name"], max_chars=60)
                        address = st.text_input("Dirección (sale en sus tickets)", loc["address"], max_chars=250)
                        phone = st.text_input("Teléfono", loc["phone"], max_chars=60)
                        active = st.checkbox("Abierto", bool(loc["active"]), disabled=loc["id"] == main)
                        if st.form_submit_button("Guardar"):
                            try:
                                c.store.update_location(loc["id"], name, address, phone, active)
                            except ValueError as exc:
                                st.error(str(exc))
                            else:
                                c.store.audit(c.username, "local_guardado", name)
                                st.session_state["settings_flash"] = f"Local «{name}» guardado."
                                st.rerun()
        with st.form("new_location", clear_on_submit=True):
            st.markdown("**Añadir un local**")
            a, b = st.columns(2)
            name = a.text_input("Nombre del local", max_chars=60, placeholder="Ej.: Centro, Playa, Calle Mayor")
            phone = b.text_input("Teléfono del local", max_chars=60)
            address = st.text_input("Dirección del local", max_chars=250)
            if st.form_submit_button("Añadir local", icon=":material/add_business:"):
                try:
                    c.store.add_location(name, address, phone)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    c.store.audit(c.username, "local_creado", name)
                    st.session_state["settings_flash"] = (f"Local «{name}» creado. Elige en el menú en qué local "
                                                          "trabajas y pásale stock desde el catálogo.")
                    st.rerun()


def settings_page() -> None:
    c = ctx()
    if not _require(c, "admin"):
        return
    s = c.settings
    page_header("Configuración", "Identidad del negocio, impuestos, numeración y tipo de negocio.", eyebrow="Ajustes")
    if "settings_flash" in st.session_state:
        st.success(st.session_state.pop("settings_flash"))
    if "settings_warning" in st.session_state:
        st.warning(st.session_state.pop("settings_warning"), icon=":material/warning:")

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
        st.markdown("##### Avisos por email")
        st.caption("Llegan al email del negocio (arriba). El envío lo activa quien gestiona la app: hasta entonces "
                   "estas opciones no envían nada.")
        a, b = st.columns(2)
        values["email_weekly"] = "si" if a.toggle("Informe semanal cada lunes (PDF)",
                                                  value=s.get("email_weekly") == "si") else "no"
        values["email_alerts"] = "si" if b.toggle("Avisos importantes del día",
                                                  value=s.get("email_alerts") == "si",
                                                  help="Solo cuando aparecen avisos nuevos de nivel alto: caída de "
                                                       "ventas, productos agotados, pérdidas…") else "no"
        st.markdown("##### Seguridad")
        values["max_discount_staff"] = st.number_input(
            "Descuento máximo de los empleados sin autorización (%)", 0.0, 100.0,
            float(s.get("max_discount_staff") or 10), step=5.0,
            help="Por encima, un encargado o el administrador lo autoriza con su usuario y PIN, y queda registrado.")
        values["session_minutes"] = st.number_input(
            "Cerrar la sesión tras estos minutos sin uso", 5, 1440, int(s.get("session_minutes") or 480), step=15,
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
                if values.get("tax_id", "").strip() and (problem := tax_id_problem(values["tax_id"])):
                    st.session_state["settings_warning"] = f"{problem} Revísalo: saldrá en todas tus facturas."
                st.rerun()

    _locations_settings(c)

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
        if replaceable and confirm:
            confirm = _identity_confirmed(c, "template_secret")
        a, b, d = st.columns(3)
        if a.button("Cambiar solo el tipo", width="stretch"):
            c.store.save_settings({"business_type": business_type})
            c.store.audit(c.username, "tipo_negocio_cambiado", PRESETS[business_type]["label"])
            st.session_state["settings_flash"] = f"Tipo cambiado a «{PRESETS[business_type]['label']}»."
            st.rerun()
        if replaceable and b.button("Cargar plantilla", type="primary", disabled=not confirm,
                                    width="stretch"):
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
        if replaceable and d.button("Empezar desde cero", disabled=not confirm, width="stretch"):
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
        logged_download(
            st, "Descargar copia de seguridad", c.store.backup_bytes, f"ventas-{clock.today():%Y-%m-%d}.db",
            "application/octet-stream", icon=":material/download:", type="primary",
        )
        if not replaceable:
            st.caption("Restaurar una copia solo es posible en un negocio sin ventas (por ejemplo, al pasar a una base "
                       "de datos nueva): sobre datos reales borraría todo lo emitido después de la copia.")
            return
        upload = st.file_uploader("Restaurar desde una copia", type=["db"])
        confirm_restore = st.checkbox("Entiendo que se reemplazarán los datos actuales por los de la copia")
        if upload and confirm_restore:
            confirm_restore = _identity_confirmed(c, "restore_secret")
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


# -------------------------------------------------------------------- help
HELP = [
    # (who can do it, title, steps)
    ("empleado", "Cobrar una venta", [
        "Abre **Vender** y toca los productos (o búscalos por nombre o código).",
        "En el móvil, toca **Ver ticket y cobrar**; en el ordenador el ticket está a la derecha.",
        "Elige la forma de pago (con efectivo, escribe lo entregado y verás el cambio) y toca **Cobrar**.",
        "Desde la ventana de la venta puedes **imprimir** el ticket o enviarlo por **WhatsApp** o **email**.",
    ]),
    ("empleado", "Si recargas o se cierra la pestaña", [
        "No pierdes nada: sigues dentro y el ticket que estabas haciendo sigue ahí.",
        "La sesión se cierra sola tras el tiempo sin uso que fije el administrador.",
    ]),
    ("empleado", "Buscar o reimprimir un ticket", [
        "Abre **Historial**, busca por número o cliente y selecciona la venta.",
        "En «Imprimir o enviar el ticket» tienes de nuevo impresión, WhatsApp y email.",
    ]),
    ("empleado", "Descuentos", [
        "Puedes aplicar hasta el máximo que fije el negocio. Por encima, un encargado lo autoriza con su usuario y PIN "
        "en tu misma caja.",
    ]),
    ("encargado", "Devolver productos o anular una venta", [
        "En **Historial**, selecciona la venta y toca **Devolver productos**: elige las unidades y el motivo.",
        "Si la venta estaba facturada, la factura rectificativa se emite sola.",
        "**Anular** solo es posible si la venta no tiene factura ni devoluciones.",
    ]),
    ("encargado", "Facturar a un cliente", [
        "En **Historial**, selecciona la venta y toca **Emitir factura**. Hacen falta el nombre y el NIF del cliente.",
        "Para facturar, el negocio debe tener su NIF y su dirección en **Configuración**.",
    ]),
    ("encargado", "Cerrar la caja", [
        "Al final del día abre **Caja**, cuenta el efectivo y escribe lo contado: verás si hay descuadre.",
        "Descarga el cierre en PDF si lo necesitas para tu gestoría.",
    ]),
    ("admin", "Varios locales", [
        "En **Configuración → Locales** añade tu segundo local: el actual pasa a llamarse «Principal» y conserva "
        "todo su stock, ventas y cierres.",
        "Elige en el menú lateral en qué local trabajas: ventas, caja, mesas y ajustes de stock son de ese local. "
        "En **Equipo y seguridad** puedes fijar a cada persona en su local.",
        "Pasa mercancía entre locales en **Catálogo → Stock por local y traspasos**. El Panel muestra la "
        "facturación por local, y el Historial se filtra por local.",
    ]),
    ("empleado", "Instalar la app en el móvil o el ordenador", [
        "Android o Chrome: menú del navegador → **Instalar aplicación** (o «Añadir a pantalla de inicio»).",
        "iPhone o iPad (Safari): botón Compartir → **Añadir a pantalla de inicio**.",
        "Se abre con su icono y en su propia ventana, sin la barra del navegador.",
    ]),
    ("encargado", "Tienda online (Shopify, WooCommerce…)", [
        "En **Catálogo → Tienda online** descarga tu catálogo en el formato de Shopify o de WooCommerce y súbelo "
        "a tu tienda: productos, precios con IVA y stock, relacionados por su código (SKU).",
        "Para registrar las ventas de la web, exporta los pedidos de la tienda (en Shopify: Pedidos → Exportar) e "
        "impórtalos ahí mismo: cada pedido cobrado se convierte en una venta y descuenta stock. Para otras tiendas, "
        "usa la plantilla.",
    ]),
    ("encargado", "Si se cae internet", [
        "Prepáralo antes: en **Caja → Caja sin conexión** descarga el archivo de catálogo, abre la caja sin conexión "
        "en el móvil o la tablet, instálala y carga el archivo.",
        "Sin internet, cobra desde esa caja: guarda las ventas en el dispositivo con su propia numeración.",
        "Con internet otra vez: en la caja, «Guardar archivo de ventas»; en la app, **Caja → Importar ventas**; y "
        "después bórralas de la caja. Importar dos veces el mismo archivo no duplica nada.",
    ]),
    ("encargado", "Reservas online", [
        "En **Agenda → Reservas online**, pon tu horario y los días cerrados, y activa «Aceptar reservas online».",
        "Comparte el enlace o imprime el QR: tus clientes eligen hora libre sin llamarte y reciben un enlace para "
        "cancelar. Las reservas aparecen en la Agenda marcadas como «Online», con su teléfono.",
        "La víspera, cada cita con email recibe un recordatorio; las demás, envíalo con «Recordar por WhatsApp».",
    ]),
    ("encargado", "Papeles para la gestoría", [
        "Abre **Gestoría**, elige el trimestre y descarga el Excel: libro de facturas emitidas, IVA por tipo, "
        "retenciones, tickets anulados y gastos.",
        "Envíaselo a tu gestoría antes del día 20 del mes siguiente al trimestre (plazo del IVA trimestral).",
    ]),
    ("encargado", "Stock y precios", [
        "En el catálogo, cambia precios (con IVA incluido) y el IVA de cada producto.",
        "Para el stock usa **ajustes** (+ o −) con su motivo: nunca se pisan las ventas hechas mientras tanto.",
    ]),
    ("encargado", "Datos de un cliente (RGPD)", [
        "En **Clientes → Protección de datos** puedes descargar todos sus datos, marcar si acepta ofertas o borrar "
        "sus datos personales cuando lo pida (las facturas se conservan, como obliga la ley).",
    ]),
    ("admin", "Equipo y seguridad", [
        "En **Equipo y seguridad** das de alta a cada persona con su rol: empleado, encargado o administrador.",
        "Genera tus **códigos de recuperación** y guárdalos: sirven si olvidas tu contraseña.",
        "El registro de actividad muestra accesos, anulaciones, facturas, cierres y cada descarga de datos.",
    ]),
    ("admin", "Copias de seguridad", [
        "En **Configuración → Copia de seguridad** descargas una copia completa cuando quieras.",
        "Con las copias automáticas configuradas (ver README), cada noche se guarda una copia cifrada y se comprueba "
        "que se puede restaurar.",
    ]),
]


def help_page() -> None:
    c = ctx()
    page_header("Ayuda", "Lo esencial para trabajar con NirKanA, según lo que puedes hacer en este negocio.",
                eyebrow="Guía rápida")
    for role, title, steps in HELP:
        if not c.can(role):
            continue
        with st.expander(title):
            st.markdown("\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1)))
    st.caption("¿Algo no funciona como esperas? Escribe a nirkana.oficial@gmail.com.")
