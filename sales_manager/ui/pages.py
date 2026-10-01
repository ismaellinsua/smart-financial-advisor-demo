"""Application pages."""

from datetime import date, datetime, time, timedelta
from html import escape
from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import automation
from core.db import SaleError
from core.presets import CURRENCIES, PAYMENT_METHODS, PRESETS
from core.pricing import compute_totals
from core.receipts import receipt_html
from ui.context import PAGES, ctx, get_store
from ui.styles import insight, page_header, style_figure

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _today_label() -> str:
    d = date.today()
    return f"{automation.WEEKDAYS[d.weekday()].capitalize()}, {d.day} de {MONTHS[d.month - 1]} de {d.year}"


def _pct(value: float, signed: bool = False) -> str:
    return (f"{value:+.1f}" if signed else f"{value:.1f}").replace(".", ",") + " %"


def _delta(value) -> str | None:
    return None if value is None else _pct(value, signed=True)


def _csv(df: pd.DataFrame) -> bytes:
    # UTF-8 with BOM and semicolons so it opens cleanly in Spanish-locale Excel.
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


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
            demo = st.toggle("Cargar datos de ejemplo (60 días de ventas)", value=True,
                             help="Ideal para explorar el panel y las automatizaciones. Puedes borrarlos luego.")
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
    demo = st.toggle("Cargar datos de ejemplo para probar", value=True, key="switch_demo")
    st.warning("Se reemplazarán el catálogo, los clientes y las ventas actuales por los del nuevo negocio.",
               icon=":material/warning:")
    st.download_button(
        "Antes, descargar una copia de mis datos", c.store.backup_bytes(), f"ventas-{date.today():%Y-%m-%d}.db",
        "application/octet-stream", icon=":material/download:", use_container_width=True,
    )
    if st.button(f"Cambiar a «{PRESETS[business_type]['label']}»", type="primary", use_container_width=True,
                 icon=":material/swap_horiz:"):
        c.store.save_settings({"business_name": name.strip() or c.settings["business_name"]})
        with st.spinner("Preparando el nuevo negocio…"):
            c.store.load_preset(business_type, with_demo_sales=demo)
        st.session_state.pop("cart", None)
        st.rerun()


# ----------------------------------------------------------------- dashboard
def dashboard() -> None:
    c = ctx()
    page_header("Panel de ventas", f"Así va {c.settings['business_name']}", eyebrow=_today_label())

    period = st.segmented_control(
        "Periodo", [7, 30, 90], default=30, format_func=lambda d: f"Últimos {d} días",
        label_visibility="collapsed", key="dash_period",
    ) or 30
    start, end, prev_start = automation.period_bounds(period)
    sales = c.store.sales(start=prev_start)
    lines = c.store.sale_lines(start=prev_start)
    k = automation.kpis(sales, lines, start, end, prev_start)

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
        days = pd.date_range(start.date(), date.today(), freq="D")
        daily = cur_sales.groupby(cur_sales["created_at"].dt.normalize())["total"].sum().reindex(days, fill_value=0)
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
        st.markdown("**Alertas automáticas**")
        products = c.store.products()
        low = automation.low_stock(products)
        inactive = automation.inactive_customers(
            c.store.customers(), c.store.sales(), int(c.settings["inactive_days"])
        )
        st.metric("Bajo stock mínimo", len(low))
        st.metric("Clientes a reactivar", len(inactive))
        if "automations" in PAGES:
            st.page_link(PAGES["automations"], label="Ver automatizaciones", icon=":material/arrow_forward:")

    st.markdown("#### Recomendaciones")
    for level, message in automation.insights(products, cur_lines, c.preset["item_label"]):
        insight(level, message)


# ---------------------------------------------------------------- point of sale
def _cart() -> dict:
    return st.session_state.setdefault("cart", {})


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


@st.dialog("Venta registrada")
def _sale_dialog(sale_id: int) -> None:
    c = ctx()
    sale = c.store.sale(sale_id)
    st.success(f"Ticket **{sale['number']}** · {c.money(sale['total'])} · {sale['payment_method']}")
    st.caption("El stock se ha actualizado automáticamente.")
    st.download_button(
        "Descargar ticket (HTML imprimible)", receipt_html(sale, c.settings), file_name=f"{sale['number']}.html",
        mime="text/html", icon=":material/receipt_long:", use_container_width=True, type="primary",
    )
    if st.button("Nueva venta", use_container_width=True):
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
    by_id = products.set_index("id")

    catalog, ticket = st.columns([3, 2], gap="large")
    with catalog:
        f1, f2 = st.columns([2, 3])
        query = f1.text_input("Buscar", placeholder="Nombre o código…", label_visibility="collapsed")
        categories = sorted(products["category"].unique())
        selected = f2.pills("Categoría", categories, selection_mode="multi", label_visibility="collapsed")
        view = products
        if query:
            q = query.lower()
            view = view[view["name"].str.lower().str.contains(q, regex=False)
                        | view["sku"].str.lower().str.contains(q, regex=False)]
        if selected:
            view = view[view["category"].isin(selected)]
        if view.empty:
            st.info("No hay resultados con esos filtros.")
        cols = st.columns(3)
        for i, (_, p) in enumerate(view.iterrows()):
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

    with ticket, st.container(border=True):
        st.markdown("#### Ticket actual")
        if not cart:
            st.caption("El ticket está vacío. Añade artículos desde el catálogo.")
        lines = []
        for pid, qty in list(cart.items()):
            p = by_id.loc[pid]
            lines.append({"product_id": pid, "quantity": qty, "unit_price": p["price"]})
            n, minus, q, plus = st.columns([6, 1, 1, 1], vertical_alignment="center")
            n.markdown(f"**{escape(p['name'])}**  \n<span style='opacity:.65'>{c.money(p['price'])} × {qty} = "
                       f"{c.money(p['price'] * qty)}</span>", unsafe_allow_html=True)
            minus.button("", key=f"dec_{pid}", on_click=_change_qty, args=(pid, -1), icon=":material/remove:",
                         type="tertiary", help="Quitar una unidad")
            q.markdown(f"<div style='text-align:center;font-weight:700'>{qty}</div>", unsafe_allow_html=True)
            plus.button("", key=f"inc_{pid}", on_click=_change_qty, args=(pid, 1), icon=":material/add:",
                        type="tertiary", help="Añadir una unidad",
                        disabled=bool(p["track_stock"]) and qty >= p["stock"])

        st.divider()
        customers = c.store.customers()
        names = {int(i): n for i, n in zip(customers["id"], customers["name"])}
        # 0 stands for the walk-in customer (ids start at 1).
        if st.session_state.get("pos_customer") not in names:
            st.session_state["pos_customer"] = 0
        cust_col, new_col = st.columns([4, 1], vertical_alignment="bottom")
        customer_id = cust_col.selectbox(
            "Cliente", [0, *names], key="pos_customer",
            format_func=lambda i: names.get(i, "Cliente general"),
        ) or None
        with new_col.popover("Nuevo", icon=":material/person_add:", help="Nuevo cliente"):
            with st.form("pos_new_customer", clear_on_submit=True, border=False):
                st.text_input("Nombre", key="pos_new_name")
                st.text_input("Email", key="pos_new_email")
                st.text_input("Teléfono", key="pos_new_phone")
                st.form_submit_button("Crear cliente", on_click=_create_customer_from_pos, type="primary")

        payment = st.segmented_control("Forma de pago", PAYMENT_METHODS, default=PAYMENT_METHODS[0],
                                       key="pos_payment") or PAYMENT_METHODS[0]
        discount = st.number_input("Descuento (%)", 0.0, 100.0, 0.0, step=5.0, key="pos_discount")

        totals = compute_totals(lines, discount, c.tax_rate)
        discount_row = (f"<tr><td>Descuento</td><td>−{c.money(totals['discount'])}</td></tr>"
                        if totals["discount"] else "")
        st.markdown(
            f"<table class='sm-totals'><tr><td>Subtotal</td><td>{c.money(totals['subtotal'])}</td></tr>"
            f"{discount_row}<tr><td>Impuestos ({c.tax_rate:g} %)</td><td>{c.money(totals['tax'])}</td></tr>"
            f"<tr class='grand'><td>Total</td><td>{c.money(totals['total'])}</td></tr></table>",
            unsafe_allow_html=True,
        )
        st.write("")
        pay_col, clear_col = st.columns([3, 1])
        if pay_col.button(f"Cobrar {c.money(totals['total'])}", type="primary", use_container_width=True,
                          disabled=not cart, icon=":material/payments:"):
            try:
                sale = c.store.create_sale(
                    [{"product_id": pid, "quantity": q} for pid, q in cart.items()],
                    payment_method=payment, customer_id=customer_id, discount_pct=discount,
                )
            except SaleError as exc:
                st.error(str(exc))
            else:
                cart.clear()
                st.session_state["last_sale"] = sale["id"]
                st.rerun()
        if clear_col.button("Vaciar", use_container_width=True, disabled=not cart):
            cart.clear()
            st.rerun()


# ------------------------------------------------------------------- history
@st.dialog("Anular venta")
def _confirm_cancel(sale_id: int, number: str) -> None:
    st.write(f"¿Seguro que quieres anular **{number}**? Las unidades volverán al stock. "
             "La venta se conserva en el historial marcada como anulada.")
    if st.button("Sí, anular", type="primary", use_container_width=True):
        try:
            get_store().cancel_sale(sale_id)
        except SaleError as exc:
            st.error(str(exc))
        else:
            st.rerun()


def history() -> None:
    c = ctx()
    page_header("Historial de ventas", "Consulta, reimprime tickets o anula ventas.", eyebrow="Ventas")
    f1, f2, f3 = st.columns([2, 1, 2])
    rng = f1.date_input("Fechas", (date.today() - timedelta(days=30), date.today()), format="DD/MM/YYYY")
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

    view = df[["id", "number", "created_at", "customer_name", "payment_method", "total", "status"]]
    event = st.dataframe(
        view, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
        column_order=["number", "created_at", "customer_name", "payment_method", "total", "status"],
        column_config={
            "number": "Ticket",
            "created_at": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
            "customer_name": "Cliente",
            "payment_method": "Pago",
            "total": st.column_config.NumberColumn("Total", format=f"%.2f {c.symbol}"),
            "status": "Estado",
        },
    )
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
        a, b = st.columns(2)
        a.download_button("Descargar ticket", receipt_html(sale, c.settings), f"{sale['number']}.html",
                          "text/html", icon=":material/receipt_long:", use_container_width=True)
        if b.button("Anular venta", disabled=sale["status"] == "anulada", use_container_width=True,
                    icon=":material/block:"):
            _confirm_cancel(sale["id"], sale["number"])


# ------------------------------------------------------------------ products
def _editor_key(name: str) -> str:
    return f"{name}_{st.session_state.get(name + '_v', 0)}"


def _bump(name: str) -> None:
    st.session_state[name + "_v"] = st.session_state.get(name + "_v", 0) + 1


def products_page() -> None:
    c = ctx()
    label, plural = c.preset["item_label"], c.preset["item_label_plural"]
    page_header(plural, "Edita directamente en la tabla y guarda. Desactiva en lugar de borrar para "
                "conservar el historial.", eyebrow="Gestión")
    if "products_flash" in st.session_state:
        st.success(st.session_state.pop("products_flash"))

    df = c.store.products(include_inactive=True)
    categories = sorted(set(c.preset["categories"]) | set(df["category"]))
    tab_list, tab_new = st.tabs([f"Catálogo ({len(df)})", f"Nuevo {label.lower()}"])

    with tab_list:
        df = df.assign(
            track_stock=df["track_stock"].astype(bool), active=df["active"].astype(bool),
            margin=((df["price"] - df["cost"]) / df["price"].where(df["price"] > 0) * 100).round(1),
            state=[("—" if not t else "Bajo mínimo" if s <= m else "Correcto")
                   for t, s, m in zip(df["track_stock"], df["stock"], df["min_stock"])],
        )
        edited = st.data_editor(
            df, key=_editor_key("products_editor"), hide_index=True, use_container_width=True,
            disabled=["id", "margin", "state"],
            column_order=["sku", "name", "category", "price", "cost", "margin", "stock", "min_stock", "state",
                          "track_stock", "active"],
            column_config={
                "sku": "Código", "name": "Nombre",
                "category": st.column_config.SelectboxColumn("Categoría", options=categories, required=True),
                "price": st.column_config.NumberColumn("Precio", min_value=0, format=f"%.2f {c.symbol}"),
                "cost": st.column_config.NumberColumn("Coste", min_value=0, format=f"%.2f {c.symbol}"),
                "margin": st.column_config.NumberColumn("Margen", format="%.1f %%"),
                "stock": st.column_config.NumberColumn("Stock", step=1),
                "min_stock": st.column_config.NumberColumn("Mínimo", min_value=0, step=1),
                "state": "Estado",
                "track_stock": st.column_config.CheckboxColumn("Controlar stock"),
                "active": st.column_config.CheckboxColumn("Activo"),
            },
        )
        if st.button("Guardar cambios", type="primary", icon=":material/save:"):
            fields = ["sku", "name", "category", "price", "cost", "stock", "min_stock", "track_stock", "active"]
            changed = 0
            try:
                for (_, before), (_, after) in zip(df.iterrows(), edited.iterrows()):
                    if any(before[f] != after[f] for f in fields):
                        data = {f: after[f] for f in fields}
                        data.update(track_stock=int(after["track_stock"]), active=int(after["active"]),
                                    stock=int(after["stock"]), min_stock=int(after["min_stock"]))
                        c.store.upsert_product(data, int(after["id"]))
                        changed += 1
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
            else:
                st.session_state["products_flash"] = f"{changed} cambio(s) guardado(s)."
                _bump("products_editor")
                st.rerun()

    with tab_new:
        with st.form("new_product", clear_on_submit=True):
            a, b = st.columns(2)
            sku = a.text_input("Código / SKU")
            name = b.text_input("Nombre")
            category = a.selectbox("Categoría", categories)
            new_category = b.text_input("…o nueva categoría")
            p1, p2, p3, p4 = st.columns(4)
            price = p1.number_input(f"Precio ({c.symbol}, sin impuestos)", 0.0, step=1.0)
            cost = p2.number_input(f"Coste ({c.symbol})", 0.0, step=1.0)
            stock = p3.number_input("Stock inicial", 0, step=1)
            min_stock = p4.number_input("Stock mínimo", 0, step=1)
            track = st.toggle("Controlar stock", value=bool(c.preset["track_stock"]))
            if st.form_submit_button(f"Crear {label.lower()}", type="primary"):
                try:
                    c.store.upsert_product({
                        "sku": sku.strip(), "name": name.strip(), "category": new_category.strip() or category,
                        "price": price, "cost": cost, "stock": stock if track else 0,
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
    page_header("Clientes", "Tu cartera, ordenada por valor. Edita en la tabla y guarda.", eyebrow="Gestión")
    if "customers_flash" in st.session_state:
        st.success(st.session_state.pop("customers_flash"))

    ranking = automation.customer_ranking(c.store.customers(), c.store.sales())
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
                "notes": st.text_area("Notas", height=80),
            }
            if st.form_submit_button("Guardar cliente", type="primary"):
                try:
                    c.store.upsert_customer(data)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["customers_flash"] = f"Cliente «{data['name']}» guardado."
                    _bump("customers_editor")
                    st.rerun()

    fields = ["name", "email", "phone", "tax_id", "notes"]
    edited = st.data_editor(
        ranking, key=_editor_key("customers_editor"), hide_index=True, use_container_width=True,
        disabled=["id", "purchases", "lifetime_value", "last_purchase", "created_at"],
        column_order=["name", "email", "phone", "tax_id", "purchases", "lifetime_value", "last_purchase", "notes"],
        column_config={
            "name": "Nombre", "email": "Email", "phone": "Teléfono", "tax_id": "Identificación fiscal",
            "purchases": st.column_config.NumberColumn("Compras"),
            "lifetime_value": st.column_config.ProgressColumn(
                "Valor acumulado", format=f"%.2f {c.symbol}", min_value=0,
                max_value=float(max(ranking["lifetime_value"].max(), 1)) if len(ranking) else 1.0,
            ),
            "last_purchase": st.column_config.DatetimeColumn("Última compra", format="DD/MM/YYYY"),
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


# --------------------------------------------------------------- automations
def automations_page() -> None:
    c = ctx()
    page_header(
        "Automatizaciones",
        "Se recalculan solas con cada venta: reposición, alertas, seguimiento de clientes e informes.",
        eyebrow="Inteligencia",
    )
    products = c.store.products()
    lines = c.store.sale_lines(start=datetime.now() - timedelta(days=120))
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
            st.download_button("Generar orden de compra (CSV)", _csv(sug), "orden_de_compra.csv", "text/csv",
                               type="primary", icon=":material/shopping_cart_checkout:")

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
        inactive = automation.inactive_customers(c.store.customers(), sales, days)
        if inactive.empty:
            st.success("Ningún cliente habitual lleva tanto tiempo sin comprar.")
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
        rng = st.date_input("Periodo del informe", (date.today().replace(day=1), date.today()), format="DD/MM/YYYY")
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
def settings_page() -> None:
    c = ctx()
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
        values["tax_rate"] = b.number_input("Impuesto por defecto (%)", 0.0, 100.0, float(s["tax_rate"]), step=0.5)
        values["invoice_prefix"] = d.text_input("Prefijo de tickets", s["invoice_prefix"], max_chars=8)
        values["receipt_footer"] = st.text_input("Pie del ticket", s["receipt_footer"])
        st.markdown("##### Automatizaciones")
        a, b = st.columns(2)
        values["inactive_days"] = a.number_input("Días para considerar un cliente inactivo", 7, 365,
                                                 int(s["inactive_days"]))
        values["reorder_lead_days"] = b.number_input("Días de cobertura al reponer", 1, 120,
                                                     int(s["reorder_lead_days"]))
        if st.form_submit_button("Guardar configuración", type="primary"):
            values["invoice_prefix"] = values["invoice_prefix"].strip().upper().replace("-", "") or "VTA"
            c.store.save_settings(values)
            st.session_state["settings_flash"] = "Configuración guardada."
            st.rerun()

    st.markdown("##### Tipo de negocio y plantillas")
    with st.container(border=True):
        types = list(PRESETS)
        business_type = st.selectbox("Tipo de negocio", types, types.index(s["business_type"]),
                                     format_func=lambda k: PRESETS[k]["label"])
        st.caption("Cambiar solo el tipo adapta el vocabulario de la aplicación. Cargar la plantilla reemplaza "
                   "catálogo, clientes y ventas por los de ejemplo.")
        demo = st.toggle("Incluir 60 días de ventas de ejemplo", value=True)
        confirm = st.checkbox("Entiendo que se borrarán los datos actuales")
        if not confirm:
            st.caption("Marca la casilla de arriba para activar «Cargar plantilla» y «Empezar desde cero».")
        a, b, d = st.columns(3)
        if a.button("Cambiar solo el tipo", use_container_width=True):
            c.store.save_settings({"business_type": business_type})
            st.session_state["settings_flash"] = f"Tipo cambiado a «{PRESETS[business_type]['label']}»."
            st.rerun()
        if b.button("Cargar plantilla", type="primary", disabled=not confirm, use_container_width=True):
            with st.spinner("Cargando plantilla…"):
                c.store.load_preset(business_type, with_demo_sales=demo)
            st.session_state.pop("cart", None)
            st.session_state["settings_flash"] = "Plantilla cargada."
            st.rerun()
        if d.button("Empezar desde cero", disabled=not confirm, use_container_width=True):
            c.store.reset()
            st.session_state.pop("cart", None)
            st.rerun()

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
            "Descargar copia de seguridad", c.store.backup_bytes(), f"ventas-{date.today():%Y-%m-%d}.db",
            "application/octet-stream", icon=":material/download:", type="primary",
        )
        upload = st.file_uploader("Restaurar desde una copia", type=["db"])
        confirm_restore = st.checkbox("Entiendo que se reemplazarán los datos actuales por los de la copia")
        if st.button("Restaurar copia", disabled=not (upload and confirm_restore), icon=":material/restore:"):
            try:
                c.store.restore(upload.getvalue())
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("cart", None)
                st.session_state["settings_flash"] = "Copia restaurada correctamente."
                st.rerun()
