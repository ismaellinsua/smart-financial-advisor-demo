"""Visual identity: global CSS and small presentational helpers."""

from html import escape

import plotly.graph_objects as go
import streamlit as st


def inject_css(accent: str) -> None:
    accent = escape(accent)
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

button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
    background: var(--accent) !important; border-color: var(--accent) !important; color: #fff !important; }}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {{ filter: brightness(1.12); }}

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

/* Insight list */
.sm-insight {{ display: flex; gap: .7rem; align-items: flex-start; padding: .7rem .9rem; border-radius: 10px;
               margin-bottom: .5rem; background: var(--secondary-background-color, #F5F7FA); font-size: .93rem; }}
.sm-insight .tag {{ font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
                    padding: .15rem .45rem; border-radius: 6px; white-space: nowrap; margin-top: .1rem; }}
.sm-insight.good .tag {{ background: #D1FADF; color: #05603A; }}
.sm-insight.warning .tag {{ background: #FEF0C7; color: #93370D; }}
.sm-insight.info .tag {{ background: #D1E9FF; color: #194185; }}

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
