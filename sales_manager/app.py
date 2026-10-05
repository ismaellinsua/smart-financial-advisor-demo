"""Gestor de Ventas — punto de venta, inventario, clientes y automatizaciones para cualquier negocio.

Ejecutar desde la raíz del repositorio:  streamlit run sales_manager/app.py

Copyright (c) 2025-2026 NirKanA. Todos los derechos reservados. Software propietario: ver LICENSE.
"""

import traceback
from datetime import timedelta
from pathlib import Path

import streamlit as st

from core.presets import PRESETS
from core.security import ROLES
from ui import booking, pages, pages_billing, pages_intel, pages_management, pages_promos, pages_tables, tenancy
from ui.auth import logout_button, require_user
from ui.context import PAGES, ctx, stripe_client
from ui.styles import inject_css, installable, sidebar_brand, sidebar_copyright, topbar
from core import clock

# A local icon: a «:material/…:» one is fetched from Google's servers by every visitor's browser.
st.set_page_config(page_title="Gestor de Ventas", page_icon=str(Path(__file__).parent / "static" / "icon-192.png"),
                   layout="wide")

installable()

# Several businesses in one app: decide which one this visit is for (or show the operator panel).
if not tenancy.gate():
    st.stop()

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

# Customers booking online (…/?reservar): a public page, no sign-in.
if booking.wanted():
    booking.public_page(c.store, c.settings)
    st.stop()

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
    help=st.Page(pages.help_page, title="Ayuda", icon=":material/help:", url_path="ayuda"),
    accounting=st.Page(pages_management.accounting_page, title="Gestoría", icon=":material/request_page:",
                       url_path="gestoria"),
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
    billing=st.Page(pages_billing.billing_page, title="Suscripción", icon=":material/workspace_premium:",
                    url_path="suscripcion"),
)
billing_access = st.session_state.get("billing_access")
charged = stripe_client() is not None

# Each role only gets the pages it may use; a hidden page cannot be opened by typing its address.
P = PAGES
sections = {"Operación": [*([P["dashboard"]] if c.can("encargado") else []),
                          *([P["tables"], P["kitchen"]] if show_tables else []), P["pos"],
                          *([P["agenda"]] if show_agenda else []),
                          *([P["cash"]] if c.can("encargado") else []), P["history"]]}
if c.can("encargado"):
    sections["Gestión"] = [P["products"], P["customers"], P["promos"], P["purchases"], P["expenses"],
                           P["accounting"]]
    sections["Inteligencia"] = [P["intelligence"], P["automations"]]
if c.can("admin"):
    sections["Ajustes"] = [P["settings"], P["team"], *([P["billing"]] if charged else []), P["help"]]
else:
    sections["Ayuda"] = [P["help"]]
if billing_access is not None and billing_access.level == "readonly":
    # Not paid: look up and download only. Pages left out of the navigation cannot be opened by address either.
    sections = {"Tu cuenta": [P["billing"], P["history"], P["help"]]}

sidebar_brand(c.settings["business_name"], PRESETS[c.settings["business_type"]]["label"])
if c.multi_location:
    # Where this session sells, counts cash and moves stock. People pinned to a location can't change it.
    ids = [loc["id"] for loc in c.locations]
    if c.fixed_location or st.session_state.get("location") not in ids:
        st.session_state["location"] = c.fixed_location or ids[0]
    st.sidebar.selectbox("Local", ids, format_func={loc["id"]: loc["name"] for loc in c.locations}.get,
                         key="location", disabled=bool(c.fixed_location),
                         help="Las ventas, la caja, las mesas y el stock de esta sesión son de este local.")
if c.can("admin") and c.store.can_replace_data() and st.sidebar.button(
        "Cambiar de negocio", icon=":material/swap_horiz:", width="stretch"):
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
today = c.store.sales(start=now.replace(hour=0, minute=0, second=0, microsecond=0), include_cancelled=False,
                      location_id=c.location_id if c.multi_location else None)
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
topbar(c.settings["business_name"] + (f" · {c.location_name}" if c.multi_location else ""), c.money_short(today["total"].sum()), len(today), next_up,
       person=f"{c.who} · {ROLES[c.role]}", own=not c.can("encargado"),
       alerts=pages_intel.alert_counts(c) if c.can("encargado") else None)
if c.settings.get("demo_mode") == "si":
    pages.demo_banner(c)
if flash := st.session_state.pop("billing_flash", None):
    st.info(flash, icon=":material/workspace_premium:")
if billing_access is not None and billing_access.level == "warn" and c.can("encargado"):
    st.warning(billing_access.message, icon=":material/credit_card:")
try:
    nav.run()
except Exception as exc:  # noqa: BLE001 - st.rerun/st.stop are BaseException and pass through untouched
    traceback.print_exc()  # the full detail stays in the server log («Manage app → Logs»)
    try:
        ref = c.store.record_error(exc, nav.title, c.username)
    except Exception:  # noqa: BLE001 - the database itself may be what failed
        ref = "sin registrar"
    st.error(f"Algo ha fallado en esta pantalla. Queda registrado con la referencia **{ref}**: si se repite, "
             "escríbenos a nirkana.oficial@gmail.com con ella. Tus datos no se han perdido.", icon=":material/error:")
