"""Promotions and loyalty: rules applied automatically at the till."""

from datetime import time

import streamlit as st

from core.pricing import PROMO_KINDS, PROMO_SCOPES
from ui.context import ctx
from ui.styles import page_header

DAY_NAMES = ["L", "M", "X", "J", "V", "S", "D"]


def _describe(p, products: dict) -> str:
    what = f"{p['value']:g} %" if p["kind"] == "porcentaje" else f"{int(p['buy'])}x{int(p['pay'])}"
    where = {"todo": "todo", "categoria": p["target"], "producto": products.get(str(p["target"]), "producto")}[p["scope"]]
    days = "todos los días" if p["days"] == "0123456" else "".join(DAY_NAMES[int(d)] for d in p["days"])
    hours = f" · {p['start_time']}–{p['end_time']}" if p["start_time"] else ""
    return f"{what} · {where} · {days}{hours}"


def promotions_page() -> None:
    c = ctx()
    if not c.can("encargado"):
        st.error("No tienes permiso para ver esta sección.", icon=":material/lock:")
        return
    page_header("Promociones y fidelización", "Reglas que se aplican solas al cobrar, y puntos que fidelizan a "
                "tus clientes.", eyebrow="Gestión")
    if "promo_flash" in st.session_state:
        st.success(st.session_state.pop("promo_flash"))
    tab_promos, tab_loyalty = st.tabs(["Promociones", "Fidelización"])
    with tab_promos:
        _promotions(c)
    with tab_loyalty:
        _loyalty(c)


def _promotions(c) -> None:
    products_df = c.store.products()
    products = {str(int(i)): n for i, n in zip(products_df["id"], products_df["name"])}
    categories = sorted(set(products_df["category"]))
    promos = c.store.promotions()
    left, right = st.columns([3, 2], gap="large")
    with left:
        if promos.empty:
            st.info("Aún no hay promociones. Crea la primera con el formulario.")
        for _, p in promos.iterrows():
            pid = int(p["id"])
            with st.container(border=True):
                a, b, d = st.columns([6, 2, 1], vertical_alignment="center")
                a.markdown(f"**{p['name']}**")
                a.caption(_describe(p, products))
                active = b.toggle("Activa", value=bool(p["active"]), key=f"promo_active_{pid}")
                if active != bool(p["active"]):
                    c.store.set_promotion_active(pid, active)
                    c.store.audit(c.username, "promocion_" + ("activada" if active else "pausada"), p["name"])
                    st.rerun()
                if d.button("", icon=":material/delete:", key=f"promo_del_{pid}", help="Eliminar"):
                    c.store.delete_promotion(pid)
                    c.store.audit(c.username, "promocion_eliminada", p["name"])
                    st.rerun()
    with right, st.container(border=True):
        st.markdown("**Nueva promoción**")
        kind = st.radio("Tipo", list(PROMO_KINDS), format_func=PROMO_KINDS.get, horizontal=True, key="promo_kind")
        scope = st.radio("Se aplica a", list(PROMO_SCOPES), format_func=PROMO_SCOPES.get, horizontal=True,
                         key="promo_scope")
        with st.form("new_promo", clear_on_submit=True, border=False):
            name = st.text_input("Nombre", max_chars=120, placeholder="Ej.: Happy hour cervezas")
            value = buy = pay = 0
            if kind == "porcentaje":
                value = st.number_input("Descuento (%)", 1.0, 100.0, 20.0, step=5.0)
            else:
                a, b = st.columns(2)
                buy = a.number_input("Lleva", 2, 20, 2)
                pay = b.number_input("Paga", 0, 19, 1)
            target = ""
            if scope == "categoria":
                target = st.selectbox("Categoría", categories)
            elif scope == "producto":
                target = st.selectbox("Producto", list(products), format_func=products.get)
            days = st.multiselect("Días", list(range(7)), default=list(range(7)), format_func=lambda d: DAY_NAMES[d])
            timed = st.toggle("Solo en un horario (happy hour)")
            a, b = st.columns(2)
            start = a.time_input("Desde", time(18, 0), step=900)
            end = b.time_input("Hasta", time(20, 0), step=900)
            if st.form_submit_button("Crear promoción", type="primary", icon=":material/sell:"):
                try:
                    c.store.save_promotion({
                        "name": name, "kind": kind, "value": value, "buy": buy, "pay": pay, "scope": scope,
                        "target": target or "", "days": "".join(str(d) for d in days),
                        "start_time": f"{start:%H:%M}" if timed else "", "end_time": f"{end:%H:%M}" if timed else "",
                    })
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    c.store.audit(c.username, "promocion_creada", name)
                    st.session_state["promo_flash"] = f"Promoción «{name}» creada. Se aplicará sola al cobrar."
                    st.rerun()
        st.caption("Si a un producto le valen varias promociones, se aplica la que más ahorra. No se acumulan.")


def _loyalty(c) -> None:
    s = c.settings
    loyalty = c.store._loyalty_settings(s)
    left, right = st.columns([2, 3], gap="large")
    with left, st.container(border=True):
        st.markdown("**Reglas de los puntos**")
        if not c.can("admin"):
            st.caption("Solo el administrador puede cambiar las reglas.")
        with st.form("loyalty_rules", border=False):
            enabled = st.toggle("Fidelización activa", value=loyalty["enabled"], disabled=not c.can("admin"))
            per_euro = st.number_input("Puntos por cada euro gastado", 0.0, 100.0, loyalty["per_euro"], step=0.5,
                                       disabled=not c.can("admin"))
            per_100 = st.number_input(f"Valor de 100 puntos ({c.symbol})", 0.0, 1000.0,
                                      round(loyalty["value"] * 100, 2), step=0.5, disabled=not c.can("admin"))
            minimum = st.number_input("Mínimo de puntos para canjear", 1, 100000, loyalty["min_redeem"], step=50,
                                      disabled=not c.can("admin"))
            if st.form_submit_button("Guardar reglas", type="primary", disabled=not c.can("admin")):
                c.store.save_settings({"loyalty_enabled": "si" if enabled else "no", "points_per_euro": per_euro,
                                       "point_value": round(per_100 / 100, 4), "min_redeem_points": minimum})
                c.store.audit(c.username, "fidelizacion_configurada",
                              f"{per_euro:g} pt/€, 100 pt = {per_100:g}, mínimo {minimum}")
                st.session_state["promo_flash"] = "Reglas de fidelización guardadas."
                st.rerun()
        back = per_euro_return(loyalty)
        if back:
            st.caption(f"Con estas reglas, cada {c.money(100)} gastados devuelven {c.money(back)} en puntos "
                       f"({back:.1f} %).")
    with right:
        st.markdown("**Clientes con más puntos**")
        points = c.store.points_by_customer()
        customers = c.store.customers()[["id", "name", "email"]]
        if points.empty:
            st.caption("Todavía nadie tiene puntos: se ganan al comprar eligiendo el cliente en el ticket.")
            return
        table = customers.merge(points, left_on="id", right_on="customer_id").sort_values("points", ascending=False)
        table["value"] = table["points"] * loyalty["value"]
        st.dataframe(table[["name", "email", "points", "value"]], hide_index=True, use_container_width=True,
                     column_config={"name": "Cliente", "email": "Email", "points": "Puntos",
                                    "value": st.column_config.NumberColumn("Valen", format=f"%.2f {c.symbol}")})


def per_euro_return(loyalty: dict) -> float:
    """Percentage of spending returned as points value."""
    return round(loyalty["per_euro"] * loyalty["value"] * 100, 2) if loyalty["enabled"] else 0.0
