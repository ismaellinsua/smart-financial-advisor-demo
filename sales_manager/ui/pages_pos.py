"""Point of sale: cart, checkout and the ticket."""

from html import escape
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from core.receipts import (
    receipt_html,
    receipt_text,
    whatsapp_number,
    with_print_button,
)
from ui import context
from ui.checkout import checkout_panel
from ui.context import ctx
from ui.styles import page_header, pos_mobile_css


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
    try:
        cid = context.get_store().upsert_customer({
            "name": name,
            "email": st.session_state.get("pos_new_email", ""),
            "phone": st.session_state.get("pos_new_phone", ""),
        })
    except ValueError as exc:
        st.session_state["pos_flash"] = ("error", str(exc))
        return
    st.session_state["pos_customer"] = cid
    st.session_state["pos_flash"] = ("success", f"Cliente «{name}» creado y seleccionado.")


def ticket_actions(c, sale: dict, preview_height: int = 420) -> None:
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
def sale_dialog(sale_id: int) -> None:
    c = ctx()
    sale = c.store.sale(sale_id)
    st.success(f"Ticket **{sale['number']}** · {c.money(sale['total'])} · {sale['payment_method']}")
    ticket_actions(c, sale, preview_height=360)
    if st.button("Nueva venta", type="primary", width="stretch"):
        st.rerun()


def point_of_sale() -> None:
    c = ctx()
    page_header("Punto de venta", "Selecciona lo que vendes, elige la forma de pago y cobra en segundos.",
                eyebrow="Vender")
    if "last_sale" in st.session_state:
        sale_dialog(st.session_state.pop("last_sale"))
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
