"""Gestor de Ventas — punto de venta, inventario, clientes y automatizaciones para cualquier negocio.

Ejecutar desde la raíz del repositorio:  streamlit run sales_manager/app.py

Copyright (c) 2025-2026 Ismael Linsua. Todos los derechos reservados. Software propietario: ver LICENSE.
"""

from datetime import timedelta

import streamlit as st

from core.presets import PRESETS
from core.security import ROLES
from ui import pages, pages_intel, pages_management, pages_promos, pages_tables
from ui.auth import logout_button, require_user
from ui.context import PAGES, ctx
from ui.styles import inject_css, sidebar_brand, sidebar_copyright, topbar
from core import clock

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
show_tables = pages_tables.tables_enabled(c.settings, c.preset)
staff_home = "tables" if show_tables else "pos"  # where waiters land after signing in
PAGES.update(
    dashboard=st.Page(pages.dashboard, title="Panel", icon=":material/space_dashboard:", url_path="panel",
                      default=c.can("encargado")),
    pos=st.Page(pages.point_of_sale, title="Vender", icon=":material/point_of_sale:", url_path="vender",
                default=not c.can("encargado") and staff_home == "pos"),
    history=st.Page(pages.history, title="Historial", icon=":material/receipt_long:", url_path="historial"),
    products=st.Page(pages.products_page, title=c.preset["item_label_plural"], icon=":material/inventory_2:",
                     url_path="catalogo"),
    customers=st.Page(pages.customers_page, title="Clientes", icon=":material/group:", url_path="clientes"),
    automations=st.Page(pages.automations_page, title="Automatizaciones", icon=":material/bolt:",
                        url_path="automatizaciones"),
    intelligence=st.Page(pages_intel.intelligence_page, title="Alertas y análisis", icon=":material/insights:",
                         url_path="inteligencia"),
    settings=st.Page(pages.settings_page, title="Configuración", icon=":material/settings:", url_path="ajustes"),
    promos=st.Page(pages_promos.promotions_page, title="Promociones", icon=":material/sell:",
                   url_path="promociones"),
    tables=st.Page(pages_tables.tables_page, title="Mesas", icon=":material/table_restaurant:", url_path="mesas",
                   default=not c.can("encargado") and staff_home == "tables"),
    kitchen=st.Page(pages_tables.kitchen_page, title="Cocina", icon=":material/skillet:", url_path="cocina"),
    purchases=st.Page(pages_management.purchases_page, title="Compras", icon=":material/local_shipping:",
                      url_path="compras"),
    expenses=st.Page(pages_management.expenses_page, title="Gastos y beneficio", icon=":material/account_balance:",
                     url_path="gastos"),
    team=st.Page(pages.team_page, title="Equipo y seguridad", icon=":material/shield_person:", url_path="equipo"),
    cash=st.Page(pages.cash_page, title="Caja", icon=":material/account_balance_wallet:", url_path="caja"),
    agenda=st.Page(pages.agenda_page, title=pages.agenda_config(c.preset)["title"], icon=":material/event:",
                   url_path="agenda"),
)

# Each role only gets the pages it may use; a hidden page cannot be opened by typing its address.
P = PAGES
sections = {"Operación": [*([P["dashboard"]] if c.can("encargado") else []),
                          *([P["tables"], P["kitchen"]] if show_tables else []), P["pos"],
                          *([P["agenda"]] if show_agenda else []),
                          *([P["cash"]] if c.can("encargado") else []), P["history"]]}
if c.can("encargado"):
    sections["Gestión"] = [P["products"], P["customers"], P["promos"], P["purchases"], P["expenses"]]
    sections["Inteligencia"] = [P["intelligence"], P["automations"]]
if c.can("admin"):
    sections["Ajustes"] = [P["settings"], P["team"]]

sidebar_brand(c.settings["business_name"], PRESETS[c.settings["business_type"]]["label"])
if c.can("admin") and c.store.can_replace_data() and st.sidebar.button(
        "Cambiar de negocio", icon=":material/swap_horiz:", use_container_width=True):
    pages.switch_business_dialog()
nav = st.navigation(sections, expanded=True)
# On phones the menu covers the screen: close it as soon as a page is chosen (Streamlit leaves it open).
st.html("""<script>
(() => {
  if (window.__nkCloseMenu) return;
  window.__nkCloseMenu = true;
  document.addEventListener("click", (event) => {
    if (window.innerWidth > 768 || !event.target.closest('[data-testid="stSidebarNav"] a')) return;
    setTimeout(() => {
      const close = document.querySelector('[data-testid="stSidebarCollapseButton"] button');
      if (close) close.click();
    }, 150);
  }, true);
})();
</script>""", unsafe_allow_javascript=True)
logout_button(c.store, user)
sidebar_copyright()

now = clock.now()
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
       person=f"{c.who} · {ROLES[c.role]}", own=not c.can("encargado"),
       alerts=pages_intel.alert_counts(c) if c.can("encargado") else None)
if c.settings.get("demo_mode") == "si":
    pages.demo_banner(c)
nav.run()
