"""Intelligence: smart alerts, ABC analysis, price suggestions and the weekly report."""

import time
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import intelligence
from core.pdfs import weekly_report_pdf
from core.security import csv_safe
from core.store_intel import week_start
from ui.context import PAGES, ctx
from ui.styles import alert_card, page_header, style_figure
from core import clock

ABC_COLORS = {"A": "#12B76A", "B": "#F79009", "C": "#98A2B3"}
ALERTS_TTL = 90  # seconds a computed alert list is reused within one session


def cached_alerts(c, refresh: bool = False) -> list[dict]:
    """Alerts for the top bar and the Panel, recomputed at most every ALERTS_TTL seconds per session."""
    cached = st.session_state.get("_alerts")
    if refresh or not cached or time.monotonic() - cached[0] > ALERTS_TTL:
        cached = (time.monotonic(), c.store.alerts())
        st.session_state["_alerts"] = cached
    return cached[1]


def alert_counts(c) -> tuple[int, int]:
    alerts = cached_alerts(c)
    return len(alerts), sum(a["level"] == "alta" for a in alerts)


def show_alerts(alerts: list[dict], limit: int | None = None, links: bool = True) -> None:
    if not alerts:
        st.success("Todo en orden: no hay nada que requiera tu atención.", icon=":material/verified:")
        return
    for alert in alerts[:limit]:
        alert_card(alert)
        page = PAGES.get(alert["page"]) if links else None
        if page is not None and limit is None:
            st.page_link(page, label=f"Ir a {page.title}", icon=":material/arrow_forward:")


def _week_label(start: datetime) -> str:
    end = start + timedelta(days=6)
    return f"Semana del {start:%d/%m} al {end:%d/%m/%Y}"


def report_card(c) -> None:
    """Panel card: last week's report, ready every Monday."""
    start = week_start(clock.today()) - timedelta(days=7)
    monday = clock.today().weekday() == 0
    with st.container(border=True):
        a, b = st.columns([3, 2], vertical_alignment="center")
        a.markdown(f"**Informe semanal {'· nuevo' if monday else 'listo'}**  \n"
                   f"<span style='opacity:.7'>{_week_label(start)}: ventas, márgenes, equipo, alertas y "
                   "recomendaciones.</span>", unsafe_allow_html=True)
        store, settings = c.store, c.settings
        b.download_button("Descargar informe (PDF)", lambda: weekly_report_pdf(store.weekly_report(start), settings),
                          f"informe_semanal_{start:%Y-%m-%d}.pdf", "application/pdf", icon=":material/summarize:",
                          use_container_width=True, type="primary" if monday else "secondary", key="dash_report")


def intelligence_page() -> None:
    c = ctx()
    if not c.can("encargado"):
        st.error("No tienes permiso para ver esta sección.", icon=":material/lock:")
        return
    page_header("Inteligencia", "Alertas que se vigilan solas, qué productos sostienen tu negocio, a qué precio "
                "venderlos y un informe cada semana.", eyebrow="Inteligencia")
    t_alerts, t_abc, t_prices, t_report = st.tabs(["Alertas", "Análisis ABC", "Precios", "Informe semanal"])
    with t_alerts:
        _alerts_tab(c)
    products = c.store.products()
    with t_abc:
        abc = _abc_tab(c, products)
    with t_prices:
        _prices_tab(c, products, abc)
    with t_report:
        _report_tab(c)


def _alerts_tab(c) -> None:
    a, b = st.columns([4, 1], vertical_alignment="bottom")
    a.caption("Se revisan solas: ventas, caja, stock, clientes, mesas, equipo, gastos y márgenes.")
    refresh = b.button("Actualizar", icon=":material/refresh:", use_container_width=True)
    alerts = cached_alerts(c, refresh=refresh)
    counts = {lvl: sum(x["level"] == lvl for x in alerts) for lvl in intelligence.LEVELS}
    m1, m2, m3 = st.columns(3)
    m1.metric("Urgentes", counts["alta"])
    m2.metric("Atención", counts["media"])
    m3.metric("Ideas", counts["baja"])
    show_alerts(alerts)


def _abc_tab(c, products: pd.DataFrame) -> pd.DataFrame:
    days = st.segmented_control("Periodo analizado", [30, 90, 180], default=30, key="abc_days",
                                format_func=lambda d: f"Últimos {d} días") or 30
    lines = c.store.sale_lines(start=clock.now() - timedelta(days=days))
    abc = intelligence.abc_analysis(products, lines)
    if abc.empty or lines.empty:
        st.info("Aún no hay ventas suficientes en este periodo para el análisis.")
        return abc
    summary = intelligence.abc_summary(abc)
    cols = st.columns(3)
    for col, (k, text) in zip(cols, [("A", "Imprescindibles"), ("B", "Complementarios"), ("C", "Poco peso")]):
        count = summary[k]["count"]
        col.metric(f"Clase {k} · {text}", f"{count} producto{'' if count == 1 else 's'}",
                   f"{summary[k]['margin_share']:.0f} % del margen", delta_color="off", delta_arrow="off")
    st.caption("Ordenados por lo que aportan al margen bruto. **A**: los pocos que dan el 80 % del margen, nunca "
               "deben faltar. **B**: el siguiente 15 %. **C**: el resto; revisa si merece la pena mantenerlos.")

    top = abc.head(20)
    fig = go.Figure()
    fig.add_bar(x=top["name"], y=top["margin"], marker_color=[ABC_COLORS[k] for k in top["abc"]],
                hovertemplate="%{x}<br>Margen <b>%{y:,.2f} " + c.symbol + "</b><extra></extra>")
    fig.add_scatter(x=top["name"], y=top["cum_share"], yaxis="y2", mode="lines+markers",
                    line=dict(color=c.settings["accent_color"], width=2),
                    hovertemplate="%{y:.0f} % acumulado<extra></extra>")
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 105], tickvals=[0, 25, 50, 80, 95],
                                  ticktext=["0 %", "25 %", "50 %", "80 %", "95 %"], showgrid=False))
    with st.container(border=True):
        st.markdown("**Margen por producto y acumulado**")
        st.plotly_chart(style_figure(fig, 320), use_container_width=True, config={"displayModeBar": False})

    view = abc[["abc", "name", "category", "units", "revenue", "margin", "margin_pct", "share"]]
    st.dataframe(view, hide_index=True, use_container_width=True, column_config={
        "abc": st.column_config.TextColumn("Clase", width="small"), "name": "Producto", "category": "Categoría",
        "units": st.column_config.NumberColumn("Unidades", format="%d"),
        "revenue": st.column_config.NumberColumn("Ventas netas", format=f"%.2f {c.symbol}"),
        "margin": st.column_config.NumberColumn("Margen", format=f"%.2f {c.symbol}"),
        "margin_pct": st.column_config.NumberColumn("Margen %", format="%.1f %%"),
        "share": st.column_config.ProgressColumn("Peso en el margen", format="%.1f %%", min_value=0, max_value=100),
    })
    st.download_button("Descargar análisis (CSV)",
                       csv_safe(abc).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       "analisis_abc.csv", "text/csv", icon=":material/download:")
    return abc


def _prices_tab(c, products: pd.DataFrame, abc: pd.DataFrame) -> None:
    default = int(c.preset.get("target_margin", 50))
    target = st.slider("Margen objetivo sobre el precio (sin impuestos)", 10, 90, default, step=5, format="%d %%",
                       key="price_target",
                       help="Margen = (precio − coste) / precio. Lo habitual en tu sector ronda el "
                            f"{default} %.")
    sug = intelligence.price_suggestions(products, target, abc)
    if sug.empty:
        st.success(f"Todos tus productos con coste conocido alcanzan ya un margen del {target} %.",
                   icon=":material/verified:")
        return
    st.caption(f"{len(sug)} producto(s) por debajo del objetivo. El precio propuesto se redondea a un importe "
               "cómodo; puedes cambiarlo antes de aplicarlo. Primero los de clase A, que son los que más pesan.")
    editor = sug.assign(apply=False)[["apply", "abc", "name", "cost", "price", "unit_margin_pct", "suggested",
                                      "new_margin_pct", "increase_pct", "id"]]
    edited = st.data_editor(
        editor, hide_index=True, use_container_width=True, key=f"price_editor_{target}",
        disabled=["abc", "name", "cost", "price", "unit_margin_pct", "new_margin_pct", "increase_pct", "id"],
        column_order=["apply", "abc", "name", "cost", "price", "unit_margin_pct", "suggested", "new_margin_pct",
                      "increase_pct"],
        column_config={
            "apply": st.column_config.CheckboxColumn("Aplicar", width="small"),
            "abc": st.column_config.TextColumn("Clase", width="small"), "name": "Producto",
            "cost": st.column_config.NumberColumn("Coste", format=f"%.2f {c.symbol}"),
            "price": st.column_config.NumberColumn("Precio actual", format=f"%.2f {c.symbol}"),
            "unit_margin_pct": st.column_config.NumberColumn("Margen actual", format="%.1f %%"),
            "suggested": st.column_config.NumberColumn("Precio nuevo", format=f"%.2f {c.symbol}", min_value=0.01,
                                                       step=0.05),
            "new_margin_pct": st.column_config.NumberColumn("Margen nuevo", format="%.1f %%"),
            "increase_pct": st.column_config.NumberColumn("Subida", format="%+.1f %%"),
        },
    )
    if (sug["increase_pct"] > 15).any():
        st.caption("Las subidas de más del 15 % conviene hacerlas poco a poco, o revisar antes el coste con el "
                   "proveedor.")
    chosen = edited[edited["apply"]]
    if st.button(f"Aplicar {len(chosen)} precio(s)", type="primary", icon=":material/price_change:",
                 disabled=chosen.empty):
        try:
            n = c.store.set_prices(dict(zip(chosen["id"], chosen["suggested"])))
        except ValueError as exc:
            st.error(str(exc))
        else:
            c.store.audit(c.username, "precios_actualizados",
                          ", ".join(f"{name}: {price:.2f}" for name, price in zip(chosen["name"], chosen["suggested"])))
            st.session_state.pop("_alerts", None)
            st.toast(f"{n} precio(s) actualizado(s).", icon=":material/check_circle:")
            st.rerun()


def _report_tab(c) -> None:
    this_week = week_start(clock.today())
    weeks = [this_week - timedelta(days=7 * i) for i in range(1, 13)] + [this_week]
    start = st.selectbox("Semana", weeks, format_func=lambda w: _week_label(w) + (" (en curso)" if w == this_week
                                                                                  else ""), key="report_week")
    st.caption("Cada lunes el informe de la semana anterior aparece listo en el Panel para descargar.")
    report = c.store.weekly_report(start)
    n = report["numbers"]
    pct = lambda v: None if v is None else f"{v:+.1f} %".replace(".", ",")  # noqa: E731
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Facturación", c.money_short(n["cur"]["revenue"]), pct(n["delta"]["revenue"]))
    m2.metric("Ventas", n["cur"]["count"], pct(n["delta"]["count"]))
    m3.metric("Ticket medio", c.money_short(n["cur"]["ticket"]), pct(n["delta"]["ticket"]))
    m4.metric("Beneficio estimado", c.money_short(report["profit"]["net"]),
              help="Margen bruto de la semana menos su parte de los gastos fijos y los gastos puntuales.")
    left, right = st.columns([3, 2], gap="large")
    with left, st.container(border=True):
        st.markdown("**Ventas por día**")
        fig = go.Figure(go.Bar(x=[f"{name[:3]} {d:%d}" for name, d, _, _ in n["by_day"]],
                               y=[total for *_, total in n["by_day"]], marker_color=c.settings["accent_color"],
                               hovertemplate="%{x}<br><b>%{y:,.2f} " + c.symbol + "</b><extra></extra>"))
        st.plotly_chart(style_figure(fig, 260), use_container_width=True, config={"displayModeBar": False})
    with right, st.container(border=True):
        st.markdown("**Recomendaciones**")
        for i, rec in enumerate(report["recommendations"], 1):
            st.markdown(f"{i}. {rec}")
    st.download_button("Descargar informe completo (PDF)", weekly_report_pdf(report, c.settings),
                       f"informe_semanal_{start:%Y-%m-%d}.pdf", "application/pdf", type="primary",
                       icon=":material/summarize:")
