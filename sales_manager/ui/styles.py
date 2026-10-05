"""Visual identity: global CSS and small presentational helpers."""

import re
from html import escape

import plotly.graph_objects as go
import streamlit as st


def inject_css(accent: str) -> None:
    # Only a plain hex colour may reach the stylesheet.
    accent = accent if re.fullmatch(r"#[0-9A-Fa-f]{6}", accent or "") else "#1F4E79"
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {{ --accent: {accent}; }}
html, body, [class*="css"], .stMarkdown, .stButton button, input, textarea {{
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 2rem; max-width: 1280px; }}
@media (max-width: 640px) {{ .block-container, [data-testid="stMainBlockContainer"] {{ padding-top: 4.5rem !important; }} }}
h1, h2, h3 {{ letter-spacing: -0.02em; font-weight: 700; }}

/* Page header */
.sm-header {{ display: flex; align-items: flex-end; justify-content: space-between;
              border-bottom: 1px solid rgba(128,128,128,.18); padding-bottom: .9rem; margin-bottom: 1.4rem; }}
.sm-header h1 {{ margin: 0; padding: 0; font-size: 1.9rem; }}
.sm-header p {{ margin: .25rem 0 0; opacity: .65; font-size: .95rem; }}
.sm-eyebrow {{ text-transform: uppercase; letter-spacing: .12em; font-size: .72rem; font-weight: 600;
               color: var(--accent); }}

/* Metric cards */
[data-testid="stMetric"] {{ background: var(--secondary-background-color, #F5F7FA); border-radius: 14px;
    padding: 1rem 1.2rem; border: 1px solid rgba(128,128,128,.12); }}
[data-testid="stMetricLabel"] p {{ font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; opacity: .7; }}
[data-testid="stMetricValue"] {{ font-weight: 700; font-variant-numeric: tabular-nums; font-size: 1.65rem; }}

/* Bordered containers as cards */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 14px; }}

/* Buttons */
.stButton button, .stDownloadButton button, .stFormSubmitButton button {{ border-radius: 10px; font-weight: 600; }}

button[kind="primary"], button[kind="primaryFormSubmit"], button[data-testid^="stBaseButton-primary"] {{
    background: var(--accent) !important; border-color: var(--accent) !important; color: #fff !important; }}
button[kind="primary"]:hover, button[data-testid^="stBaseButton-primary"]:hover {{ filter: brightness(1.12); }}
button[kind="primary"]:disabled, button[data-testid^="stBaseButton-primary"]:disabled {{ opacity: .4; cursor: not-allowed; }}

/* Product tiles in the point of sale */
.sm-tile-cat {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .08em; opacity: .55; }}
.sm-tile-name {{ font-weight: 600; font-size: .98rem; line-height: 1.25; min-height: 2.5em; }}
.sm-tile-price {{ font-weight: 700; font-size: 1.15rem; color: var(--accent); font-variant-numeric: tabular-nums; }}
.sm-tile-stock {{ font-size: .78rem; opacity: .65; }}
.sm-tile-stock.low {{ color: #B42318; opacity: 1; font-weight: 600; }}

/* Totals box */
.sm-totals {{ width: 100%; font-variant-numeric: tabular-nums; }}
.sm-totals td {{ padding: .2rem 0; border: 0; }}
.sm-totals td:last-child {{ text-align: right; }}
.sm-totals .grand td {{ font-size: 1.35rem; font-weight: 700; color: var(--accent);
                        border-top: 2px solid var(--accent); padding-top: .5rem; }}

/* Tables, orders and kitchen */
.sm-table {{ line-height: 1.5; font-size: .88rem; }}
.sm-table b {{ font-size: 1rem; }}
.sm-table .amt {{ font-weight: 700; color: var(--accent); font-variant-numeric: tabular-nums; }}
.sm-table.busy {{ border-left: 3px solid var(--accent); padding-left: .55rem; }}
.sm-ready {{ margin-left: .4rem; font-size: .68rem; font-weight: 700; padding: .05rem .4rem; border-radius: 6px;
             background: #D1FADF; color: #05603A; }}
.sm-oline {{ font-size: .9rem; line-height: 1.35; }}
.sm-oline .chip {{ font-size: .66rem; font-weight: 700; text-transform: uppercase; padding: .05rem .4rem;
                   border-radius: 6px; background: #F2F4F7; color: #475467; margin-left: .3rem; }}
.sm-oline.preparando .chip {{ background: #FEF0C7; color: #93370D; }}
.sm-oline.listo .chip {{ background: #D1FADF; color: #05603A; }}
.sm-oline.paid {{ opacity: .45; }}
.sm-oline .note, .sm-kds .note {{ font-style: italic; color: #B54708; font-size: .85rem; }}
.sm-oline .by {{ font-size: .72rem; opacity: .55; }}
.sm-kds {{ font-size: 1rem; line-height: 1.4; }}
.sm-kds .place {{ font-size: .78rem; opacity: .7; }}
.sm-kds.late .place {{ color: #B42318; opacity: 1; font-weight: 700; }}

/* Checkout */
.sm-promo {{ font-size: .85rem; color: #067647; padding: .1rem 0; }}
.sm-change {{ font-size: 1.05rem; padding: .3rem 0 .6rem; }}
.sm-change b {{ color: var(--accent); font-size: 1.3rem; }}

/* Smart alerts */
.sm-alert {{ display: flex; gap: .7rem; align-items: flex-start; padding: .65rem .85rem; border-radius: 10px;
             margin-bottom: .45rem; border-left: 3px solid #98A2B3;
             background: var(--secondary-background-color, #F5F7FA); font-size: .9rem; }}
.sm-alert.alta {{ border-left-color: #D92D20; }}
.sm-alert.media {{ border-left-color: #F79009; }}
.sm-alert .lvl {{ font-size: .66rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
                  padding: .12rem .42rem; border-radius: 6px; white-space: nowrap; margin-top: .12rem;
                  background: #EAECF0; color: #344054; }}
.sm-alert.alta .lvl {{ background: #FEE4E2; color: #B42318; }}
.sm-alert.media .lvl {{ background: #FEF0C7; color: #93370D; }}
.sm-alert b {{ display: block; }}
.sm-alert span.d {{ opacity: .75; font-size: .84rem; }}
.sm-abc {{ display: inline-block; min-width: 1.6rem; text-align: center; font-weight: 700; border-radius: 6px;
           padding: .05rem .4rem; color: #fff; }}

/* Insight list */
.sm-insight {{ display: flex; gap: .7rem; align-items: flex-start; padding: .7rem .9rem; border-radius: 10px;
               margin-bottom: .5rem; background: var(--secondary-background-color, #F5F7FA); font-size: .93rem; }}
.sm-insight .tag {{ font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
                    padding: .15rem .45rem; border-radius: 6px; white-space: nowrap; margin-top: .1rem; }}
.sm-insight.good .tag {{ background: #D1FADF; color: #05603A; }}
.sm-insight.warning .tag {{ background: #FEF0C7; color: #93370D; }}
.sm-insight.info .tag {{ background: #D1E9FF; color: #194185; }}

/* Top bar: one quiet line with today's pulse */
.sm-topbar {{ display: flex; align-items: center; gap: .75rem; padding: .45rem .9rem; margin: -1rem 0 1.2rem;
             border: 1px solid rgba(128,128,128,.16); border-radius: 999px; font-size: .84rem;
             background: linear-gradient(90deg, color-mix(in srgb, var(--accent) 7%, transparent), transparent 70%); }}
.sm-topbar .dot {{ width: .5rem; height: .5rem; border-radius: 50%; background: var(--accent); flex: none;
                  box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 45%, transparent); }}
@media (prefers-reduced-motion: no-preference) {{
  .sm-topbar .dot {{ animation: sm-pulse 2.4s ease-out infinite; }}
}}
@keyframes sm-pulse {{ 0% {{ box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 45%, transparent); }}
                      70%, 100% {{ box-shadow: 0 0 0 .45rem transparent; }} }}
.sm-topbar .biz {{ font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }}
.sm-topbar .sep {{ opacity: .3; }}
.sm-topbar .stat {{ margin-left: auto; white-space: nowrap; font-variant-numeric: tabular-nums; opacity: .85; }}
.sm-topbar .stat b {{ color: var(--accent); }}
.sm-topbar .next {{ white-space: nowrap; opacity: .65; }}
.sm-topbar .who {{ white-space: nowrap; font-size: .76rem; padding: .1rem .55rem; border-radius: 999px;
                  background: color-mix(in srgb, var(--accent) 12%, transparent); }}
.sm-topbar .alerts {{ white-space: nowrap; font-size: .76rem; font-weight: 600; padding: .1rem .55rem;
                     border-radius: 999px; background: #FEE4E2; color: #B42318; }}
.sm-topbar .alerts.calm {{ background: #FEF0C7; color: #93370D; }}
@media (max-width: 640px) {{ .sm-topbar .next, .sm-topbar .sep.n, .sm-topbar .biz {{ display: none; }} }}

/* Agenda cards */
.sm-appt {{ display: flex; align-items: center; gap: .9rem; }}
.sm-appt .when {{ font-weight: 700; font-size: 1.05rem; font-variant-numeric: tabular-nums; min-width: 3.4rem; }}
.sm-appt .when span {{ display: block; font-weight: 400; font-size: .78rem; opacity: .55; }}
.sm-appt .who {{ flex: 1; font-weight: 600; min-width: 0; }}
.sm-appt .what {{ font-weight: 400; font-size: .85rem; opacity: .7; }}
.sm-appt .chip {{ font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
                 padding: .15rem .5rem; border-radius: 6px; background: #D1E9FF; color: #194185; }}
.sm-appt.completada .chip {{ background: #D1FADF; color: #05603A; }}
.sm-appt.cancelada .chip, .sm-appt.no_presentado .chip {{ background: #F2F4F7; color: #475467; }}
.sm-appt.cancelada .who, .sm-appt.no_presentado .who {{ text-decoration: line-through; opacity: .6; }}

/* Sidebar brand */
.sm-brand {{ display: flex; align-items: center; gap: .7rem; padding: .2rem 0 1rem; }}
.sm-brand .logo {{ width: 40px; height: 40px; border-radius: 11px; background: var(--accent); color: #fff;
                   display: grid; place-items: center; font-weight: 700; font-size: 1.05rem; }}
.sm-brand .name {{ font-weight: 700; line-height: 1.15; }}
.sm-brand .type {{ font-size: .75rem; opacity: .6; }}
</style>
""",
        unsafe_allow_html=True,
    )


# Phones: the till shows either the catalogue or the ticket, switched from a bar fixed at the bottom, so «Cobrar» is
# always two taps away; tiles stay three per row and every control is at least 44 px (WCAG 2.5.5).
POS_MOBILE_CSS = """
<style>
.st-key-pos_bar {{ display: none; }}
@media (max-width: 640px) {{
  .st-key-pos_{hidden} {{ display: none !important; }}
  .st-key-pos_bar {{ display: block; }}
  .st-key-{fixed} {{ position: fixed; left: 0; right: 0; bottom: 0; z-index: 999990;
                     padding: .6rem 1rem calc(.6rem + env(safe-area-inset-bottom)); background: var(--background-color, #fff);
                     box-shadow: 0 -4px 16px rgba(16,24,40,.12); }}
  .st-key-pos_grid .stButton button [data-testid="stIconMaterial"] {{ display: none; }}
  [data-testid="stButtonGroup"] button, [data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"],
  [data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] button {{
      min-height: 44px; min-width: 44px; }}
  [data-testid="stMainBlockContainer"] {{ padding-bottom: 6rem !important; }}
  .st-key-pos_grid [data-testid="stHorizontalBlock"], .st-key-pos_lines [data-testid="stHorizontalBlock"] {{
      flex-wrap: nowrap !important; gap: .4rem !important; }}
  .st-key-pos_grid [data-testid="stColumn"], .st-key-pos_lines [data-testid="stColumn"] {{
      min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }}
  .st-key-pos_lines [data-testid="stColumn"]:first-child {{ flex: 5 1 0 !important; }}
  .st-key-pos_grid .sm-tile-name {{ font-size: .85rem; min-height: 3.6em; }}
  .st-key-pos_grid .sm-tile-cat, .st-key-pos_grid .sm-tile-stock {{ font-size: .68rem; }}
  .st-key-pos_grid [data-testid="stVerticalBlockBorderWrapper"] {{ padding: .55rem !important; }}
  .st-key-pos_grid .stButton button {{ padding: 0 .3rem; justify-content: center; }}
  .st-key-pos_grid .stButton button * {{ gap: 0 !important; margin: 0 !important; justify-content: center; }}
  .st-key-pos_grid .stButton button p {{ font-size: .85rem; white-space: nowrap; }}
  .stButton button, .stDownloadButton button, [data-testid="stPopover"] button {{ min-height: 44px; }}
  .st-key-pos_lines .stButton button {{ min-width: 44px; }}
}}
</style>
"""


def pos_mobile_css(view: str) -> None:
    # Catalogue: the «see ticket» bar is fixed at the bottom. Ticket: «Cobrar» itself is, and «back» sits on top.
    hidden, fixed = ("ticket", "pos_bar") if view == "catalogo" else ("catalog", "pos_charge")
    st.markdown(POS_MOBILE_CSS.format(hidden=hidden, fixed=fixed), unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    st.markdown(
        f"<div class='sm-header'><div>"
        f"{f'<div class=sm-eyebrow>{escape(eyebrow)}</div>' if eyebrow else ''}"
        f"<h1>{escape(title)}</h1>{f'<p>{escape(subtitle)}</p>' if subtitle else ''}</div></div>",
        unsafe_allow_html=True,
    )


def sidebar_brand(name: str, business_type_label: str) -> None:
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "MN"
    st.sidebar.markdown(
        f"<div class='sm-brand'><div class='logo'>{escape(initials)}</div>"
        f"<div><div class='name'>{escape(name)}</div><div class='type'>{escape(business_type_label)}</div></div></div>",
        unsafe_allow_html=True,
    )


def topbar(business: str, today_total: str, today_count: int, next_up: str = "", person: str = "",
           own: bool = False, alerts: tuple[int, int] | None = None) -> None:
    """`alerts` is (total, urgent); shown only to people who can act on them."""
    sales = f"{today_count} venta" + ("" if today_count == 1 else "s")
    nxt = f"<span class='sep n'>·</span><span class='next'>{escape(next_up)}</span>" if next_up else ""
    who = f"<span class='who'>{escape(person)}</span>" if person else ""
    label = "Tus ventas hoy" if own else "Hoy"
    if alerts and alerts[0]:
        total, urgent = alerts
        text = f"{total} aviso" + ("" if total == 1 else "s")
        who = f"<span class='alerts{'' if urgent else ' calm'}' title='Alertas inteligentes'>{text}</span>" + who
    st.markdown(
        f"<div class='sm-topbar' role='status'><span class='dot'></span>"
        f"<span class='biz'>{escape(business)}</span>{nxt}"
        f"<span class='stat'>{label} <b>{escape(today_total)}</b> · {sales}</span>{who}</div>",
        unsafe_allow_html=True,
    )


def sidebar_copyright() -> None:
    st.sidebar.caption("© 2026 Ismael Linsua · Todos los derechos reservados")


INSIGHT_TAGS = {"good": "Fortaleza", "warning": "Atención", "info": "Idea"}


def insight(level: str, message: str) -> None:
    st.markdown(
        f"<div class='sm-insight {level}'><span class='tag'>{INSIGHT_TAGS.get(level, 'Nota')}</span>"
        f"<span>{escape(message)}</span></div>",
        unsafe_allow_html=True,
    )


def style_figure(fig: go.Figure, height: int = 320) -> go.Figure:
    """Quiet, consistent chart chrome: recessive grid, no x grid, thin rounded bars, compact margins."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        font=dict(family="Inter, system-ui, sans-serif", size=12),
        showlegend=False,
        bargap=0.25,
        hoverlabel=dict(font_family="Inter, system-ui, sans-serif"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False, zeroline=False, title=None)
    fig.update_yaxes(gridcolor="rgba(128,128,128,.15)", zeroline=False, title=None)
    fig.update_traces(selector=dict(type="bar"), marker_cornerradius=4)
    return fig


ALERT_LEVELS = {"alta": "Urgente", "media": "Atención", "baja": "Idea"}


def alert_card(alert: dict) -> None:
    st.markdown(
        f"<div class='sm-alert {escape(alert['level'])}'><span class='lvl'>{ALERT_LEVELS[alert['level']]}</span>"
        f"<div><b>{escape(alert['title'])}</b><span class='d'>{escape(alert['detail'])}</span></div></div>",
        unsafe_allow_html=True,
    )


def installable() -> None:
    """Declare the web app manifest and icons, so phones and computers offer to install NirKanA as an app (its
    own icon and window, no browser bar). Streamlit has no way to add them to the page head, so a script does."""
    st.html("""<script>
(() => {
  if (document.querySelector('link[rel="manifest"]')) return;
  const add = (tag, attrs) => document.head.appendChild(Object.assign(document.createElement(tag), attrs));
  add("link", { rel: "manifest", href: "/app/static/manifest.json" });
  add("link", { rel: "apple-touch-icon", href: "/app/static/apple-touch-icon.png" });
  add("meta", { name: "theme-color", content: "#3B5BFD" });
  add("meta", { name: "mobile-web-app-capable", content: "yes" });
  add("meta", { name: "apple-mobile-web-app-capable", content: "yes" });
  add("meta", { name: "apple-mobile-web-app-title", content: "NirKanA" });
})();
</script>""", unsafe_allow_javascript=True)
