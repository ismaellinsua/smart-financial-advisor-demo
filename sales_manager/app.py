"""Gestor de Ventas — punto de venta, inventario, clientes y automatizaciones para cualquier negocio.

Ejecutar desde la raíz del repositorio:  streamlit run sales_manager/app.py

Copyright (c) 2025-2026 Ismael Linsua. Todos los derechos reservados. Software propietario: ver LICENSE.
"""

from datetime import datetime, timedelta

import streamlit as st

from core.presets import PRESETS
from core.security import ROLES
from ui import pages, pages_promos
from ui.auth import logout_button, require_user
from ui.context import PAGES, ctx
from ui.styles import inject_css, sidebar_brand, sidebar_copyright, topbar

st.set_page_config(page_title="Gestor de Ventas", page_icon=":material/storefront:", layout="wide")

try:
    c = ctx()
except Exception as exc:  # the database is unreachable or the URL is wrong; retried on the next visit
    st.error(
        "No se pudo conectar con la base de datos. Revisa que `database_url` en los *Secrets* de Streamlit "
        "sea la cadena de conexión completa de Neon (empieza por `postgresql://`)."
    )
    st.caption(f"Detalle técnico: {type(exc).__name__}")
    st.stop()
inject_css(c.settings["accent_color"])

user = require_user(c.store, c.settings)
if user is None:
    st.stop()
c = ctx()  # now with the signed-in user

if c.store.is_empty():
    if c.can("admin"):
        pages.onboarding()
    else:
        st.info("El negocio todavía no está configurado. Pide al administrador que lo prepare.")
    st.stop()

show_agenda = pages.agenda_enabled(c.settings, c.preset)
PAGES.update(
    dashboard=st.Page(pages.dashboard, title="Panel", icon=":material/space_dashboard:", url_path="panel",
                      default=c.can("encargado")),
    pos=st.Page(pages.point_of_sale, title="Vender", icon=":material/point_of_sale:", url_path="vender",
                default=not c.can("encargado")),
    history=st.Page(pages.history, title="Historial", icon=":material/receipt_long:", url_path="historial"),
    products=st.Page(pages.products_page, title=c.preset["item_label_plural"], icon=":material/inventory_2:",
                     url_path="catalogo"),
    customers=st.Page(pages.customers_page, title="Clientes", icon=":material/group:", url_path="clientes"),
    automations=st.Page(pages.automations_page, title="Automatizaciones", icon=":material/bolt:",
                        url_path="automatizaciones"),
    settings=st.Page(pages.settings_page, title="Configuración", icon=":material/settings:", url_path="ajustes"),
    promos=st.Page(pages_promos.promotions_page, title="Promociones", icon=":material/sell:",
                   url_path="promociones"),
    team=st.Page(pages.team_page, title="Equipo y seguridad", icon=":material/shield_person:", url_path="equipo"),
    cash=st.Page(pages.cash_page, title="Caja", icon=":material/account_balance_wallet:", url_path="caja"),
    agenda=st.Page(pages.agenda_page, title=pages.agenda_config(c.preset)["title"], icon=":material/event:",
                   url_path="agenda"),
)

# Each role only gets the pages it may use; a hidden page cannot be opened by typing its address.
P = PAGES
sections = {"Operación": [*([P["dashboard"]] if c.can("encargado") else []), P["pos"],
                          *([P["agenda"]] if show_agenda else []),
                          *([P["cash"]] if c.can("encargado") else []), P["history"]]}
if c.can("encargado"):
    sections["Gestión"] = [P["products"], P["customers"], P["promos"]]
    sections["Inteligencia"] = [P["automations"]]
if c.can("admin"):
    sections["Ajustes"] = [P["settings"], P["team"]]

sidebar_brand(c.settings["business_name"], PRESETS[c.settings["business_type"]]["label"])
if c.can("admin") and st.sidebar.button("Cambiar de negocio", icon=":material/swap_horiz:",
                                        use_container_width=True):
    pages.switch_business_dialog()
nav = st.navigation(sections)
logout_button(c.store, user)
sidebar_copyright()

now = datetime.now()
today = c.store.sales(start=now.replace(hour=0, minute=0, second=0, microsecond=0), include_cancelled=False)
if not c.can("encargado"):
    today = today[today["user_name"] == c.who]  # staff see their own figures
next_up = ""
if show_agenda:
    upcoming = c.store.appointments(now, now + timedelta(days=7))
    upcoming = upcoming[upcoming["status"] == "pendiente"]
    if not upcoming.empty:
        first = upcoming.iloc[0]
        when = (f"{first['starts_at']:%H:%M}" if first["starts_at"].date() == now.date()
                else f"{first['starts_at']:%d/%m %H:%M}")
        next_up = f"Próxima: {when} · {first['who']}"
topbar(c.settings["business_name"], c.money_short(today["total"].sum()), len(today), next_up,
       person=f"{c.who} · {ROLES[c.role]}", own=not c.can("encargado"))
nav.run()
