"""Floor plan with tables, shared orders (comandas) and the kitchen screen."""

from html import escape

import pandas as pd
import streamlit as st

from ui.checkout import checkout_panel
from ui.context import ctx, get_store
from ui.styles import page_header
from core import clock

KITCHEN_LABELS = {"pendiente": "En cola", "preparando": "Preparando", "listo": "Listo", "servido": "Servido"}


def tables_enabled(settings: dict, preset: dict) -> bool:
    choice = settings.get("tables_enabled", "auto")
    return bool(preset.get("tables")) if choice == "auto" else choice == "si"


def _minutes(since) -> int:
    return max(0, int((clock.now() - since.to_pydatetime()).total_seconds() // 60))


def _open_table(table_id: int, who: str) -> None:
    try:
        st.session_state["table_order"] = get_store().open_order(table_id, opened_by=who)
    except ValueError as exc:
        st.session_state["tables_flash"] = ("error", str(exc))


def _close_view() -> None:
    st.session_state.pop("table_order", None)
    st.session_state.pop("charging", None)


# ---------------------------------------------------------------- floor plan
def tables_page() -> None:
    c = ctx()
    if "last_sale" in st.session_state:
        from ui.pages_pos import sale_dialog
        sale_dialog(st.session_state.pop("last_sale"))
    if "tables_flash" in st.session_state:
        kind, msg = st.session_state.pop("tables_flash")
        getattr(st, kind)(msg)
    order_id = st.session_state.get("table_order")
    if order_id:
        try:
            order = c.store.order(order_id)
        except ValueError:
            order = None
        if order and order["status"] == "abierta":
            _order_view(c, order)
            return
        _close_view()

    page_header("Mesas", "Toca una mesa para abrirla o ver su comanda. Varios camareros pueden pedir en la misma "
                "mesa a la vez.", eyebrow="Sala")
    floor = c.store.dining_tables(location_id=c.location_id)
    busy = floor[floor["order_id"].notna()]
    with st.container(key="floor_stats"):
        m1, m2, m3 = st.columns(3)
        m1.metric("Mesas ocupadas", f"{len(busy)} de {len(floor)}")
        m2.metric("Comensales", int(busy["guests"].fillna(0).sum()))
        m3.metric("Pendiente de cobro", c.money_short(busy["amount"].sum()))
    if floor.empty:
        st.info("No hay mesas. Créalas en «Configurar mesas», más abajo.")

    with st.container(key="floor"):
        for zone, tables in floor.groupby("zone", sort=False):
            st.markdown(f"##### {escape(str(zone))}")
            rows = [tables.iloc[i:i + 4] for i in range(0, len(tables), 4)]  # row by row: phones show them in order
            for row in rows:
                _table_row(c, row)

    _counter_and_setup(c)


def _table_row(c, row: pd.DataFrame) -> None:
    cols = st.columns(4)
    for i, (_, t) in enumerate(row.iterrows()):
        with cols[i], st.container(border=True):
            if pd.notna(t["order_id"]):  # occupied
                ready = f"<span class='sm-ready'>{int(t['ready'])} listo</span>" if t["ready"] else ""
                st.markdown(
                    f"<div class='sm-table busy'><b>{escape(t['name'])}</b>{ready}"
                    f"<div>{f'{int(t.guests)} pers · ' if t['guests'] else ''}{_minutes(t['opened_at'])} min</div>"
                    f"<div class='amt'>{escape(c.money(t['amount']))}</div></div>",
                    unsafe_allow_html=True)
                st.button("Ver comanda", key=f"tbl_{t['id']}", width="stretch",
                          on_click=st.session_state.__setitem__, args=("table_order", int(t["order_id"])))
            else:
                st.markdown(f"<div class='sm-table'><b>{escape(t['name'])}</b><div>Libre · {int(t['seats'])} "
                            f"plazas</div><div class='amt'>&nbsp;</div></div>", unsafe_allow_html=True)
                st.button("Abrir", key=f"tbl_{t['id']}", width="stretch", type="primary",
                          on_click=_open_table, args=(int(t["id"]), c.who))


def _counter_and_setup(c) -> None:
    others = c.store.open_orders()
    others = others[others["table_name"].isna()]
    st.markdown("##### Barra y para llevar")
    a, b = st.columns([3, 1], vertical_alignment="bottom")
    label = a.text_input("Nueva comanda sin mesa", placeholder="Ej.: Barra · Juan, Para llevar · 21:15",
                         max_chars=60, key="counter_label")
    if b.button("Abrir comanda", width="stretch"):
        try:
            st.session_state["table_order"] = c.store.open_order(None, opened_by=c.who, label=label)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    for _, o in others.iterrows():
        st.button(f"{o['label']} · abierta {o['opened_at'][11:16]}", key=f"ord_{o['id']}",
                  on_click=st.session_state.__setitem__, args=("table_order", int(o["id"])))

    if c.can("encargado"):
        with st.expander("Configurar mesas", icon=":material/table_restaurant:"):
            with st.form("new_table", clear_on_submit=True, border=False):
                x, y, z = st.columns(3)
                name = x.text_input("Nombre", max_chars=60, placeholder="Mesa 9")
                zone = y.text_input("Zona", "Sala", max_chars=60)
                seats = z.number_input("Plazas", 1, 50, 4)
                if st.form_submit_button("Añadir mesa", type="primary"):
                    try:
                        c.store.save_table(name, zone, seats, location_id=c.location_id)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            for _, t in c.store.dining_tables(include_inactive=True, location_id=c.location_id).iterrows():
                if st.toggle(f"{t['name']} ({t['zone']})", value=bool(t["active"]), key=f"tbl_on_{t['id']}") \
                        != bool(t["active"]):
                    try:
                        c.store.set_table_active(int(t["id"]), not bool(t["active"]))
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.rerun()


# --------------------------------------------------------------- order view
def _add(order_id: int, product_id: int, who: str) -> None:
    note = st.session_state.get("order_note", "")
    st.session_state["order_note"] = ""  # the note belongs to this product only
    try:
        get_store().add_order_item(order_id, product_id, 1, note, added_by=who)
    except ValueError as exc:
        st.session_state["tables_flash"] = ("error", str(exc))


def _change(item_id: int, delta: int, force: bool) -> None:
    try:
        get_store().change_order_item(item_id, delta, force=force)
    except ValueError as exc:
        st.session_state["tables_flash"] = ("error", str(exc))


def _order_view(c, order: dict) -> None:
    oid = order["id"]
    top, back = st.columns([5, 1], vertical_alignment="bottom")
    with top:
        page_header(order["title"], f"Abierta por {order['opened_by'] or '—'} a las {order['opened_at'][11:16]}",
                    eyebrow="Comanda")
    back.button("← Mesas", on_click=_close_view, width="stretch")
    guests = st.number_input("Comensales", 0, 99, int(order["guests"] or 0), key=f"guests_{oid}")
    if guests != int(order["guests"] or 0):
        c.store.set_order_guests(oid, guests)

    menu, ticket = st.columns([3, 2], gap="large")
    with menu:
        products = c.products_here()
        cats = sorted(products["category"].unique())
        chosen = st.pills("Categoría", cats, key=f"order_cat_{oid}", label_visibility="collapsed")
        if chosen:
            products = products[products["category"] == chosen]
        st.text_input("Nota para el próximo producto", key="order_note", max_chars=200,
                      placeholder="Ej.: sin cebolla, poco hecho…")
        cols = st.columns(2)
        for i, (_, p) in enumerate(products.iterrows()):
            out = bool(p["track_stock"]) and p["stock"] <= 0
            cols[i % 2].button(f"{p['name']} · {c.money(p['price'])}", key=f"oadd_{oid}_{p['id']}",
                               on_click=_add, args=(oid, int(p["id"]), c.who), width="stretch",
                               disabled=out)

    with ticket, st.container(border=True):
        st.markdown("#### Comanda")
        if not order["items"]:
            st.caption("Vacía. Toca los productos para añadirlos.")
        for item in order["items"]:
            paid = item["sale_id"] is not None
            chip = "Cobrado" if paid else KITCHEN_LABELS.get(item["kitchen"], item["kitchen"])
            note = f"<div class='note'>{escape(item['notes'])}</div>" if item["notes"] else ""
            n, minus, plus = st.columns([6, 1, 1], vertical_alignment="center")
            n.markdown(
                f"<div class='sm-oline {'paid' if paid else escape(str(item['kitchen']))}'><b>{int(item['quantity'])} × "
                f"{escape(item['name'])}</b> <span class='chip'>{escape(chip)}</span>{note}"
                f"<div class='by'>{escape(item['added_by'])}</div></div>", unsafe_allow_html=True)
            if not paid:
                locked = item["kitchen"] != "pendiente" and not c.can("encargado")
                minus.button("", icon=":material/remove:", key=f"odec_{item['id']}", type="tertiary",
                             on_click=_change, args=(item["id"], -1, c.can("encargado")), disabled=locked,
                             help="Ya en cocina: solo un encargado puede quitarlo." if locked else "Quitar uno")
                plus.button("", icon=":material/add:", key=f"oinc_{item['id']}", type="tertiary",
                            on_click=_change, args=(item["id"], 1, False))
        st.markdown(f"**Por cobrar: {c.money(order['amount'])}**")

        a, b = st.columns(2)
        charging = st.session_state.get("charging") == oid
        if a.button("Cerrar cobro" if charging else "Cobrar", type="primary", width="stretch",
                    disabled=not order["unpaid"], icon=":material/payments:", key=f"charge_toggle_{oid}"):
            st.session_state["charging"] = None if charging else oid
            st.rerun()
        with b.popover("Más", width="stretch"):
            free = c.store.dining_tables(location_id=c.location_id)
            free = free[free["order_id"].isna()]
            options = dict(zip(free["id"].astype(int), free["name"]))
            target = st.selectbox("Mover a", list(options), format_func=options.get, key=f"move_{oid}")
            if st.button("Mover", disabled=target is None, key=f"move_btn_{oid}"):
                try:
                    c.store.move_order(oid, target)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if c.can("encargado") and st.button("Cancelar comanda", key=f"cancel_{oid}"):
                try:
                    c.store.cancel_order(oid)
                    c.store.audit(c.username, "comanda_cancelada", order["title"])
                    _close_view()
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

        if charging and order["unpaid"]:
            st.divider()
            how = st.radio("Qué se cobra", ["Toda la cuenta", "Por productos"], horizontal=True, key=f"how_{oid}")
            selection = None
            if how == "Por productos":
                selection = {}
                for item in order["unpaid"]:
                    selection[item["id"]] = st.number_input(f"{item['name']} (de {item['quantity']})", 0,
                                                            item["quantity"], 0, key=f"sel_{oid}_{item['id']}")
            cart = c.store.order_cart(oid, selection)

            def charge(_cart, **checkout):
                return c.store.charge_order(oid, selection, **checkout)

            sale = checkout_panel(c, cart, f"order_{oid}", charge_fn=charge)
            if sale:
                st.session_state["last_sale"] = sale["id"]
                st.session_state["charging"] = None
                if c.store.order(oid)["status"] != "abierta":
                    _close_view()
                st.rerun()


# -------------------------------------------------------------------- kitchen
def kitchen_page() -> None:
    c = ctx()
    page_header("Cocina", "Pedidos de todas las mesas en orden de llegada. Se actualiza solo cada 10 segundos.",
                eyebrow="Sala")
    categories = sorted(c.store.products()["category"].unique())
    default = [cat for cat in categories if cat.lower() != "bebidas"] or categories
    shown = st.multiselect("Qué ve esta pantalla", categories, default=default, key="kitchen_cats")
    _kitchen_board(shown, c.location_id)


@st.fragment(run_every="10s")
def _kitchen_board(categories: list[str], location_id: int | None = None) -> None:
    queue = get_store().kitchen_queue(categories or None, location_id)
    if queue.empty:
        st.success("No hay nada pendiente. ¡Cocina al día!", icon=":material/check_circle:")
        return
    columns = st.columns(3)
    for col, status, action in zip(columns, ["pendiente", "preparando", "listo"],
                                   ["Empezar", "Listo", "Servido"]):
        items = queue[queue["kitchen"] == status]
        col.markdown(f"**{KITCHEN_LABELS[status]}** · {len(items)}")
        for _, it in items.iterrows():
            wait = _minutes(it["added_at"])
            late = " late" if wait >= 15 and status != "listo" else ""
            note = f"<div class='note'>{escape(it['notes'])}</div>" if it["notes"] else ""
            with col.container(border=True):
                st.markdown(f"<div class='sm-kds{late}'><div class='place'>{escape(str(it['place']))} · "
                            f"{wait} min</div><b>{int(it['quantity'])} × {escape(it['name'])}</b>{note}</div>",
                            unsafe_allow_html=True)
                if st.button(action, key=f"kds_{it['id']}", width="stretch",
                             type="primary" if status == "listo" else "secondary"):
                    get_store().advance_kitchen(int(it["id"]))
                    st.rerun(scope="fragment")
