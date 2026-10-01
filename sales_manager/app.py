"""Gestor de Ventas — punto de venta, inventario, clientes y automatizaciones para cualquier negocio.

Ejecutar desde la raíz del repositorio:  streamlit run sales_manager/app.py
"""

import streamlit as st

from core.presets import PRESETS
from ui import pages
from ui.context import PAGES, ctx
from ui.styles import inject_css, sidebar_brand

st.set_page_config(page_title="Gestor de Ventas", page_icon=":material/storefront:", layout="wide")

c = ctx()
inject_css(c.settings["accent_color"])

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
nav.run()
