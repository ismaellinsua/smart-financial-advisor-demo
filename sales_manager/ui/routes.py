"""What an address outside the menu shows: a clear message in Spanish instead of Streamlit's English «Page not found».

Each role only gets the pages it may use (app.py). The others are still registered, hidden from the menu, so that
opening one by its address (an old bookmark, a link from a colleague with another role) explains why it is not
available instead of claiming it does not exist. Short aliases people type (/reservas) lead to the real page, and
the start page also opens at its own address (/panel), which Streamlit otherwise reports as missing.
"""

import re

import streamlit as st

# Addresses people expect, and the page (key in PAGES) they mean.
ALIASES = {"reservas": "agenda", "citas": "agenda", "tpv": "pos", "configuracion": "settings"}
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,40}")


def _path(page) -> str:
    """The page's own address. Streamlit reports "" for the start page, but it still has one (…/panel)."""
    return getattr(page, "_url_path", None) or page.url_path


def _unavailable(title: str, notice: str = ""):
    def page() -> None:
        st.warning(notice or f"«{title}» no está disponible con tu usuario en este negocio. Si la necesitas, pídesela "
                   "a un administrador.", icon=":material/lock:")
    return page


def _not_found() -> None:
    st.warning("Esa página no existe. Usa el menú de la izquierda para ir a donde querías.",
               icon=":material/search_off:")


def _alias_to(page):
    def go() -> None:
        st.switch_page(page)
    return go


def _pages_manager():
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    return get_script_run_ctx().pages_manager


def requested_path() -> str:
    """The page named in the address (…/ajustes → "ajustes"), "" for the main page or when it cannot be told."""
    try:
        return str(_pages_manager().intended_page_name or "").strip("/").lower()
    except Exception:  # an internal of Streamlit: without it, unknown addresses keep Streamlit's own message
        return ""


def _open_start_page(page) -> None:
    """Asked for by its own address: open it as the start page it is, without Streamlit's «not found»."""
    try:
        _pages_manager().set_script_intent(page._script_hash, "")
    except Exception:
        pass


def with_fallbacks(sections: dict, pages: dict, requested: str = "", notice: str = "") -> dict:
    """`sections` plus hidden pages for every other address: pages this user may not open, aliases and, when
    `requested` matches nothing, a «no existe» page at that address. `notice` replaces the usual explanation of
    why a page is not available (e.g. the subscription is not active)."""
    listed = [p for group in sections.values() for p in group]
    allowed = {_path(p) for p in listed}
    for page in listed:
        if page.url_path == "" and requested == _path(page):
            _open_start_page(page)
    extra = []
    for page in pages.values():
        if _path(page) not in allowed:
            extra.append(st.Page(_unavailable(page.title, notice), title=page.title, url_path=_path(page),
                                 visibility="hidden"))
    taken = {_path(p) for p in pages.values()} | allowed
    for alias, key in ALIASES.items():
        target = pages.get(key)
        if target is not None and alias not in taken:
            run = _alias_to(target) if _path(target) in allowed else _unavailable(target.title, notice)
            extra.append(st.Page(run, title=target.title, url_path=alias, visibility="hidden"))
            taken.add(alias)
    if requested and requested not in taken and SLUG_RE.fullmatch(requested):
        extra.append(st.Page(_not_found, title="Página no encontrada", url_path=requested, visibility="hidden"))
    if not extra:
        return sections
    last = list(sections)[-1]  # hidden pages never show, so any section will do
    return {**sections, last: [*sections[last], *extra]}
