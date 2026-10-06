"""Customers, loyalty and privacy requests."""

from datetime import datetime

import pandas as pd
import streamlit as st

from core import automation
from ui.context import ctx, logged_download
from ui.pages_common import require_role
from ui.pages_products import bump_editor, editor_key
from ui.styles import page_header


# ----------------------------------------------------------------- customers
def customers_page() -> None:
    c = ctx()
    if not require_role(c, "encargado"):
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
                    bump_editor("customers_editor")
                    st.rerun()

    fields = ["name", "email", "phone", "tax_id", "address", "notes"]
    edited = st.data_editor(
        ranking, key=editor_key("customers_editor"), hide_index=True, width="stretch",
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
            bump_editor("customers_editor")
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
    st.session_state[f"export_{cid}"] = c.store.customer_data_export(cid, by=c.username, as_role=c.role)


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
            logged_download(b, "Descargar sus datos (JSON)", export, f"datos-cliente-{cid}.json", "application/json",
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
                c.store.forget_customer(cid, by=c.username, as_role=c.role)
                st.session_state["customers_flash"] = "Datos personales borrados. Las facturas se conservan."
                bump_editor("customers_editor")
                st.rerun()
