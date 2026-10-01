"""Gestor de Ventas — punto de venta, inventario, clientes y automatizaciones para cualquier negocio.

Ejecutar desde la raíz del repositorio:  streamlit run sales_manager/app.py

Copyright (c) 2025-2026 Ismael Linsua. Todos los derechos reservados. Software propietario: ver LICENSE.
"""

import streamlit as st

from core.presets import PRESETS
from ui import pages
from ui.auth import logout_button, require_login
from ui.context import PAGES, ctx
from ui.styles import inject_css, sidebar_brand, sidebar_copyright

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

if not require_login():
    st.stop()

if c.store.is_empty():
    pages.onboarding()
    st.stop()

PAGES.update(
    dashboard=st.Page(pages.dashboard, title="Panel", icon=":material/space_dashboard:", url_path="panel",
                      default=True),
    pos=st.Page(pages.point_of_sale, title="Vender", icon=":material/point_of_sale:", url_path="vender"),
    history=st.Page(pages.history, title="Historial", icon=":material/receipt_long:", url_path="historial"),
    products=st.Page(pages.products_page, title=c.preset["item_label_plural"], icon=":material/inventory_2:",
                     url_path="catalogo"),
    customers=st.Page(pages.customers_page, title="Clientes", icon=":material/group:", url_path="clientes"),
    automations=st.Page(pages.automations_page, title="Automatizaciones", icon=":material/bolt:",
                        url_path="automatizaciones"),
    settings=st.Page(pages.settings_page, title="Configuración", icon=":material/settings:", url_path="ajustes"),
)

sidebar_brand(c.settings["business_name"], PRESETS[c.settings["business_type"]]["label"])
nav = st.navigation({
    "Operación": [PAGES["dashboard"], PAGES["pos"], PAGES["history"]],
    "Gestión": [PAGES["products"], PAGES["customers"]],
    "Inteligencia": [PAGES["automations"]],
    "Ajustes": [PAGES["settings"]],
})
logout_button()
sidebar_copyright()
nav.run()
