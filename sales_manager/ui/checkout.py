"""Checkout panel shared by the till and table orders: customer, discounts, points and payments."""

import time as _time
from html import escape

import streamlit as st

from core.db import AuthError, SaleError
from core.presets import PAYMENT_METHODS
from core.pricing import split_evenly

MODES = ["Un pago", "Pago mixto", "Dividir cuenta"]


def _totals_table(c, totals: dict) -> None:
    rows = [("Subtotal", c.money(totals["subtotal"]))]
    if totals["promo_discount"]:
        rows.append(("Promociones", f"−{c.money(totals['promo_discount'])}"))
    if totals["manual_discount"]:
        rows.append(("Descuento", f"−{c.money(totals['manual_discount'])}"))
    if totals["loyalty_discount"]:
        rows.append(("Puntos canjeados", f"−{c.money(totals['loyalty_discount'])}"))
    body = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in rows)
    st.markdown(f"<table class='sm-totals'>{body}<tr class='grand'><td>Total</td>"
                f"<td>{escape(c.money(totals['total']))}</td></tr></table>", unsafe_allow_html=True)
    if totals.get("taxes"):
        st.caption("IVA incluido: " + " · ".join(f"{t['rate']:g} % {c.money(t['tax'])}" for t in totals["taxes"]))


def _payments(c, total: float, prefix: str) -> tuple[list[dict] | None, str | None]:
    """Payment widgets. Returns (payments, problem); `problem` explains why the charge button is disabled."""
    mode = st.segmented_control("Cómo paga", MODES, default=MODES[0], key=f"{prefix}_mode") or MODES[0]
    if mode == "Un pago":
        method = st.segmented_control("Forma de pago", PAYMENT_METHODS, default=PAYMENT_METHODS[0],
                                      key=f"{prefix}_payment") or PAYMENT_METHODS[0]
        tendered = 0.0
        if method == "Efectivo":
            given = st.number_input(f"Entregado ({c.symbol})", min_value=0.0, step=5.0, value=None,
                                    placeholder="Opcional: para calcular el cambio", key=f"{prefix}_tendered")
            if given:
                if given + 0.005 < total:
                    return None, f"Faltan {c.money(total - given)} por entregar."
                st.markdown(f"<div class='sm-change'>Cambio: <b>{escape(c.money(given - total))}</b></div>",
                            unsafe_allow_html=True)
                tendered = given
        return [{"method": method, "amount": total, "tendered": tendered}], None

    if mode == "Pago mixto":
        payments, cols = [], st.columns(2)
        for i, method in enumerate(PAYMENT_METHODS):
            amount = cols[i % 2].number_input(f"{method} ({c.symbol})", min_value=0.0, step=1.0, value=0.0,
                                              key=f"{prefix}_mix_{method}")
            if amount:
                payments.append({"method": method, "amount": round(amount, 2), "tendered": 0.0})
        paid = round(sum(p["amount"] for p in payments), 2)
        pending = round(total - paid, 2)
        if abs(pending) >= 0.005:
            text = f"Faltan {c.money(pending)}" if pending > 0 else f"Sobran {c.money(-pending)}"
            return None, f"{text} para cuadrar el total."
        return payments, None

    people = st.number_input("Número de personas", min_value=2, max_value=30, value=2, step=1,
                             key=f"{prefix}_people")
    parts = split_evenly(total, int(people))
    st.caption(f"Cada persona paga {c.money(parts[0])}" + (
        f" (la última {c.money(parts[-1])} por el redondeo)." if parts[-1] != parts[0] else "."))
    payments, cols = [], st.columns(2)
    for i, amount in enumerate(parts):
        method = cols[i % 2].selectbox(f"Persona {i + 1} · {c.money(amount)}", PAYMENT_METHODS,
                                       key=f"{prefix}_split_{i}")
        payments.append({"method": method, "amount": amount, "tendered": 0.0})
    return payments, None


def checkout_panel(c, cart: list[dict], prefix: str, *, customer_widget=None, button_label: str = "Cobrar",
                   charge_fn=None):
    """Draw customer, discount, points, totals and payment for `cart`; return the sale once charged.

    `customer_widget(customers_by_id) -> id | None` lets the caller draw its own customer picker (the till adds
    a «new customer» button); by default a plain selectbox is shown. `charge_fn(cart, **checkout)` replaces the
    default `create_sale`, e.g. to charge a table order.
    """
    customers = c.store.customers()
    names = {int(i): n for i, n in zip(customers["id"], customers["name"])}
    if customer_widget:
        customer_id = customer_widget(names)
    else:
        key = f"{prefix}_customer"
        if st.session_state.get(key) not in names:
            st.session_state[key] = 0
        customer_id = st.selectbox("Cliente", [0, *names], key=key,
                                   format_func=lambda i: names.get(i, "Cliente general")) or None

    loyalty = c.store.loyalty_settings(c.settings)
    redeem = 0
    if customer_id and loyalty["enabled"]:
        balance = c.store.customer_points(customer_id)
        worth = c.money(balance * loyalty["value"])
        if balance >= loyalty["min_redeem"]:
            redeem = int(st.number_input(f"Canjear puntos (tiene {balance}, valen {worth})", min_value=0,
                                         max_value=balance, step=max(1, loyalty["min_redeem"]), value=0,
                                         key=f"{prefix}_redeem_{customer_id}"))
        else:
            st.caption(f"Puntos del cliente: {balance} ({worth}). Se canjean a partir de {loyalty['min_redeem']}.")
    discount = st.number_input("Descuento manual (%)", 0.0, 100.0, 0.0, step=5.0, key=f"{prefix}_discount")
    limit = discount_limit(c)
    approver = _discount_approval(c, prefix, discount, limit)

    if not cart:
        _totals_table(c, {"subtotal": 0, "promo_discount": 0, "manual_discount": 0, "loyalty_discount": 0,
                          "tax": 0, "total": 0})
        st.button(f"{button_label} {c.money(0)}", type="primary", width="stretch", disabled=True,
                  icon=":material/payments:", key=f"{prefix}_charge")
        return None
    try:
        quote = c.store.quote(cart, customer_id=customer_id, discount_pct=discount, redeem_points=redeem)
    except SaleError as exc:
        st.error(str(exc))
        return None

    applied = [ln for ln in quote["lines"] if ln["line_discount"]]
    for ln in applied:
        st.markdown(f"<div class='sm-promo'>✓ {escape(ln['promo_name'])} · {escape(ln['name'])} "
                    f"<b>−{escape(c.money(ln['line_discount']))}</b></div>", unsafe_allow_html=True)
    totals = quote["totals"]
    _totals_table(c, totals)
    if quote["points_earned"]:
        st.caption(f"Con esta compra el cliente gana {quote['points_earned']} puntos.")

    payments, problem = _payments(c, totals["total"], prefix)
    if discount > limit and not approver:
        payments, problem = None, f"Un descuento de más del {limit:g} % necesita la autorización de un encargado."
    if problem:
        st.warning(problem, icon=":material/info:")
    if st.button(f"{button_label} {c.money(totals['total'])}", type="primary", width="stretch",
                 disabled=payments is None, icon=":material/payments:", key=f"{prefix}_charge"):
        try:
            sale = (charge_fn or c.store.create_sale)(
                cart, customer_id=customer_id, discount_pct=discount, user_name=c.who, payments=payments,
                redeem_points=redeem, max_discount=limit, discount_approved_by=approver, location_id=c.location_id)
            st.session_state.pop(f"{prefix}_approval", None)
            return sale
        except SaleError as exc:
            st.error(str(exc))
    return None


def discount_limit(c) -> float:
    """Managers and the administrator give any discount; staff up to the limit set in Configuración."""
    if c.can("encargado"):
        return 100.0
    try:
        return max(0.0, min(100.0, float(c.settings.get("max_discount_staff") or 0)))
    except ValueError:
        return 0.0


def _discount_approval(c, prefix: str, discount: float, limit: float) -> str:
    """Above the staff limit a manager authorises that exact discount with their user and PIN. Returns who did."""
    key = f"{prefix}_approval"
    approval = st.session_state.get(key)
    if discount <= limit:
        st.session_state.pop(key, None)
        return ""
    if approval and approval[1] == discount:
        st.caption(f"Descuento del {discount:g} % autorizado por {approval[0]}.")
        return approval[0]
    with st.container(border=True):
        st.markdown(f"**Autorización de un encargado** · más del {limit:g} %")
        with st.form(f"{prefix}_approve", clear_on_submit=True, border=False):
            a, b = st.columns(2)
            username = a.text_input("Usuario del encargado", max_chars=30)
            secret = b.text_input("Su PIN o contraseña", type="password", max_chars=128)
            otp = st.text_input("Código de verificación (si lo tiene activado)", max_chars=6)
            if st.form_submit_button("Autorizar descuento"):
                try:
                    who = c.store.authorize(username, secret, otp=otp,
                                            purpose=f"descuento del {discount:g} % en la caja de {c.who}")
                except AuthError as exc:
                    _time.sleep(0.8)  # slows down scripted guessing
                    st.error(str(exc))
                else:
                    st.session_state[key] = (who["name"], discount)
                    st.rerun()
    return ""
