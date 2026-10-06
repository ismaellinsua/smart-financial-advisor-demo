"""Restocking, inactive customers and reports."""

from datetime import datetime, time, timedelta
from urllib.parse import quote

import streamlit as st

from core import automation, clock
from ui.context import ctx, logged_download
from ui.pages_common import csv_bytes, require_role
from ui.styles import page_header


# --------------------------------------------------------------- automations
def automations_page() -> None:
    c = ctx()
    if not require_role(c, "encargado"):
        return
    page_header(
        "Automatizaciones",
        "Se recalculan solas con cada venta: reposición, alertas, seguimiento de clientes e informes.",
        eyebrow="Inteligencia",
    )
    products = c.store.products()
    lines = c.store.sale_lines(start=clock.now() - timedelta(days=120))
    totals = c.store.customer_totals()
    t1, t2, t3, t4 = st.tabs(["Reposición inteligente", "Alertas de stock", "Seguimiento de clientes", "Informes"])

    with t1:
        lead = st.slider("Días a cubrir hasta la próxima entrega", 3, 60, int(c.settings["reorder_lead_days"]),
                         help="Se compara con la demanda media diaria de los últimos 30 días.")
        sug = automation.reorder_suggestions(products, lines, lead_days=lead)
        a, b = st.columns(2)
        a.metric("Artículos a reponer", len(sug))
        b.metric("Inversión estimada", c.money(sug["estimated_cost"].sum()))
        if sug.empty:
            st.success("Tu stock cubre la demanda prevista. No hace falta comprar nada.")
        else:
            st.dataframe(
                sug, hide_index=True, width="stretch",
                column_config={
                    "sku": "Código", "name": "Artículo", "stock": "Stock actual",
                    "daily_demand": st.column_config.NumberColumn("Demanda/día", format="%.2f"),
                    "days_of_cover": st.column_config.NumberColumn("Días de cobertura", format="%.1f"),
                    "suggested_qty": "Pedir",
                    "estimated_cost": st.column_config.NumberColumn("Coste estimado", format=f"%.2f {c.symbol}"),
                },
            )
            a, b = st.columns(2)
            if a.button("Crear pedidos a proveedores", type="primary", icon=":material/shopping_cart_checkout:",
                        width="stretch"):
                numbers = c.store.draft_purchases(sug, created_by=c.who)
                c.store.audit(c.username, "pedidos_generados", ", ".join(numbers))
                st.success(f"Pedidos en borrador: {', '.join(numbers)}. Revísalos y envíalos en Gestión → Compras.")
            logged_download(b, "Descargar sugerencias (CSV)", csv_bytes(sug), "orden_de_compra.csv", "text/csv",
                              icon=":material/download:", width="stretch")

    with t2:
        low = automation.low_stock(products)
        if low.empty:
            st.success("Todos los artículos están por encima de su stock mínimo.")
        else:
            st.warning(f"{len(low)} artículo(s) en o por debajo del mínimo.")
            st.dataframe(
                low[["sku", "name", "category", "stock", "min_stock"]], hide_index=True, width="stretch",
                column_config={"sku": "Código", "name": "Artículo", "category": "Categoría",
                               "stock": "Stock", "min_stock": "Mínimo"},
            )

    with t3:
        days = st.slider("Considerar inactivo tras (días)", 15, 180, int(c.settings["inactive_days"]))
        customers = c.store.customers()
        allowed = customers[customers["marketing_consent"] == 1]
        inactive = automation.inactive_customers(allowed, totals, days)
        st.caption(f"Solo aparecen los clientes que aceptan recibir ofertas ({len(allowed)} de {len(customers)}). "
                   "El consentimiento se marca en Clientes → Protección de datos.")
        if inactive.empty:
            st.success("Ningún cliente con permiso para ofertas lleva tanto tiempo sin comprar.")
        for _, row in inactive.iterrows():
            with st.expander(f"{row['name']} · {row['days_inactive']} días sin comprar · "
                             f"{c.money(row['lifetime_value'])} acumulados"):
                message = st.text_area("Mensaje", automation.followup_message(row["name"], c.settings["business_name"]),
                                       height=170, key=f"msg_{row['id']}")
                subject = f"Te echamos de menos en {c.settings['business_name']}"
                if row["email"]:
                    st.link_button("Enviar por email", f"mailto:{row['email']}?subject={quote(subject)}"
                                   f"&body={quote(message)}", icon=":material/mail:")
                else:
                    st.caption("Este cliente no tiene email registrado.")

    with t4:
        rng = st.date_input("Periodo del informe", (clock.today().replace(day=1), clock.today()), format="DD/MM/YYYY")
        if isinstance(rng, tuple) and len(rng) == 2:
            start = datetime.combine(rng[0], time.min)
            end = datetime.combine(rng[1] + timedelta(days=1), time.min)
            period_lines = c.store.sale_lines(start, end)
            summary = (
                period_lines.groupby(["category", "name"])
                .agg(unidades=("quantity", "sum"), ventas_netas=("revenue", "sum"), margen=("margin", "sum"))
                .round(2).reset_index().sort_values("ventas_netas", ascending=False)
            )
            st.dataframe(summary, hide_index=True, width="stretch")
            a, b = st.columns(2)
            logged_download(a, "Resumen por artículo (CSV)", csv_bytes(summary), "resumen_articulos.csv", "text/csv",
                              icon=":material/download:", width="stretch")
            logged_download(b, "Detalle de ventas (CSV)", lambda: csv_bytes(c.store.sales(start, end)), "ventas_detalle.csv",
                              "text/csv", icon=":material/download:", width="stretch")
