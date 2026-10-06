"""Dashboard: today's figures, trends and recommendations."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import automation, clock
from ui import pages_intel
from ui.context import PAGES, ctx
from ui.pages_common import _delta, _pct, _require, _today_label
from ui.styles import insight, page_header, style_figure


# ----------------------------------------------------------------- dashboard
def dashboard() -> None:
    c = ctx()
    if not _require(c, "encargado"):
        return
    page_header("Panel de ventas", f"Así va {c.settings['business_name']}", eyebrow=_today_label())

    pages_intel.report_card(c)
    period = st.segmented_control(
        "Periodo", [7, 30, 90], default=30, format_func=lambda d: f"Últimos {d} días",
        label_visibility="collapsed", key="dash_period",
    ) or 30
    start, end, prev_start = automation.period_bounds(period)
    sales = c.store.sales(start=prev_start)
    lines = c.store.sale_lines(start=prev_start)
    refunds = c.store.refunds(start=prev_start)
    k = automation.kpis(sales, lines, start, end, prev_start, refunds)

    m1, m2, m3, m4 = st.columns(4)
    vs = f"Variación frente a los {period} días anteriores."
    m1.metric("Facturación", c.money_short(k["revenue"]), _delta(k["revenue_delta"]), help=f"Impuestos incluidos. {vs}")
    m2.metric("Ventas", f"{k['count']}", _delta(k["count_delta"]), help=vs)
    m3.metric("Ticket medio", c.money_short(k["ticket"]), _delta(k["ticket_delta"]), help=vs)
    m4.metric("Margen bruto", _pct(k["margin_pct"]), help="Sobre ventas netas, sin impuestos.")

    cur_sales = sales[(sales["status"] == "completada") & (sales["created_at"] >= start)]
    if c.multi_location:
        places = {loc["id"]: loc["name"] for loc in c.store.locations(include_inactive=True)}
        per = (cur_sales.assign(place=cur_sales["location_id"].map(places).fillna("—"))
               .groupby("place")["total"].agg(["sum", "count"]).reset_index().sort_values("sum", ascending=False))
        per["ticket"] = per["sum"] / per["count"]
        st.markdown("**Por local**")
        st.dataframe(per, hide_index=True, width="stretch", column_config={
            "place": "Local", "sum": st.column_config.NumberColumn("Facturación", format=f"%.2f {c.symbol}"),
            "count": "Ventas", "ticket": st.column_config.NumberColumn("Ticket medio", format=f"%.2f {c.symbol}")})
    cur_lines = lines[lines["created_at"] >= start]
    accent = c.settings["accent_color"]

    left, right = st.columns([3, 2], gap="large")
    with left, st.container(border=True):
        st.markdown("**Facturación diaria**")
        days = pd.date_range(start.date(), clock.today(), freq="D")
        daily = cur_sales.groupby(cur_sales["created_at"].dt.normalize())["total"].sum().reindex(days, fill_value=0)
        if not refunds.empty:  # returns lower the day they were made
            back = refunds.groupby(refunds["created_at"].dt.normalize())["total"].sum()
            daily = daily.sub(back.reindex(days, fill_value=0), fill_value=0)
        fig = go.Figure(go.Bar(
            x=daily.index, y=daily.values, marker_color=accent,
            hovertemplate="%{x|%d/%m/%Y}<br><b>%{y:,.2f} " + c.symbol + "</b><extra></extra>",
        ))
        fig.update_xaxes(tickformat="%d/%m")
        st.plotly_chart(style_figure(fig), width="stretch", config={"displayModeBar": False})
    with right, st.container(border=True):
        st.markdown("**Lo más vendido** · ventas netas")
        top = cur_lines.groupby("name")["revenue"].sum().nlargest(6).sort_values()
        if top.empty:
            st.caption("Sin ventas en el periodo.")
        else:
            fig = go.Figure(go.Bar(
                x=top.values, y=top.index, orientation="h", marker_color=accent,
                text=[c.money(v) for v in top.values], textposition="auto",
                hovertemplate="%{y}<br><b>%{x:,.2f} " + c.symbol + "</b> netos<extra></extra>",
            ))
            st.plotly_chart(style_figure(fig), width="stretch", config={"displayModeBar": False})

    left, mid, right = st.columns([1, 1, 1], gap="large")
    with left, st.container(border=True):
        st.markdown("**Formas de pago**")
        pay = cur_sales.groupby("payment_method")["total"].sum().sort_values()
        if not pay.empty:
            fig = go.Figure(go.Bar(
                x=pay.values, y=pay.index, orientation="h", marker_color=accent,
                hovertemplate="%{y}<br><b>%{x:,.2f} " + c.symbol + "</b><extra></extra>",
            ))
            st.plotly_chart(style_figure(fig, 240), width="stretch", config={"displayModeBar": False})
    with mid, st.container(border=True):
        st.markdown("**Por categoría**")
        cat = cur_lines.groupby("category")["revenue"].sum().sort_values()
        if not cat.empty:
            fig = go.Figure(go.Bar(
                x=cat.values, y=cat.index, orientation="h", marker_color=accent,
                hovertemplate="%{y}<br><b>%{x:,.2f} " + c.symbol + "</b> netos<extra></extra>",
            ))
            st.plotly_chart(style_figure(fig, 240), width="stretch", config={"displayModeBar": False})
    with right, st.container(border=True):
        st.markdown("**Alertas inteligentes**")
        alerts = pages_intel.cached_alerts(c)
        pages_intel.show_alerts(alerts, limit=3)
        if len(alerts) > 3:
            st.caption(f"Y {len(alerts) - 3} más.")
        if "intelligence" in PAGES:
            st.page_link(PAGES["intelligence"], label="Ver todas y el análisis", icon=":material/arrow_forward:")

    by_user = cur_sales[cur_sales["user_name"] != ""].groupby("user_name")["total"].agg(["sum", "count"])
    if not by_user.empty:
        with st.container(border=True):
            st.markdown("**Ventas por persona del equipo**")
            by_user = by_user.sort_values("sum")
            fig = go.Figure(go.Bar(
                x=by_user["sum"], y=by_user.index, orientation="h", marker_color=accent,
                text=[f"{c.money(v)} · {n} ventas" for v, n in zip(by_user["sum"], by_user["count"])],
                textposition="auto",
                hovertemplate="%{y}<br><b>%{x:,.2f} " + c.symbol + "</b><extra></extra>",
            ))
            st.plotly_chart(style_figure(fig, 60 + 40 * len(by_user)), width="stretch",
                            config={"displayModeBar": False})

    st.markdown("#### Recomendaciones")
    for level, message in automation.insights(c.store.products(), cur_lines, c.preset["item_label"]):
        insight(level, message)
