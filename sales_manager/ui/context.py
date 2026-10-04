"""Shared per-run context for pages."""

import os
from dataclasses import dataclass

import streamlit as st

from core import clock
from core.db import Store
from core.presets import CURRENCIES, PRESETS
from core.pricing import format_money, format_money_short

# Filled by app.py so pages can link to each other.
PAGES: dict = {}


def database_url() -> str | None:
    """PostgreSQL URL from Streamlit secrets (`database_url`) or the DATABASE_URL environment variable."""
    try:
        url = st.secrets.get("database_url")
    except Exception:  # no secrets file
        url = None
    return url or os.environ.get("DATABASE_URL") or None


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name)
    except Exception:  # no secrets file
        value = None
    return str(value or os.environ.get(name.upper(), "") or "")


def multi_tenant() -> bool:
    """One app and one database for several businesses (secret `multi_tenant = true`), each chosen in the address
    with ?negocio=code. Off by default: a single-business deployment works as always."""
    return _secret("multi_tenant").lower() in ("1", "true", "si", "sí", "yes") and bool(database_url())


@st.cache_resource(show_spinner=False)
def get_directory():
    from core.tenants import Directory

    return Directory(database_url())


def tenant_code() -> str:
    """The business this session is serving (multi-business mode only)."""
    return st.session_state.get("tenant", "")


@st.cache_resource(show_spinner="Conectando con la base de datos…")
def _single_store() -> Store:
    url = database_url()
    return Store(url) if url else Store()


@st.cache_resource(show_spinner="Conectando con tu negocio…", max_entries=200)
def _tenant_store(code: str) -> Store:
    return get_directory().store(code)


def get_store() -> Store:
    if multi_tenant():
        code = tenant_code()
        if not code:
            raise RuntimeError("No hay ningún negocio elegido en esta sesión.")
        return _tenant_store(code)
    return _single_store()


@dataclass
class Ctx:
    store: Store
    settings: dict
    preset: dict
    symbol: str
    user: dict | None = None

    @property
    def role(self) -> str:
        # No signed-in user means the least privileged role, never the most.
        return self.user["role"] if self.user else "empleado"

    @property
    def who(self) -> str:
        """Name that signs sales, invoices and closings; also used in the audit log."""
        return self.user["name"] if self.user else ""

    @property
    def username(self) -> str:
        return self.user["username"] if self.user else ""

    def can(self, needed: str) -> bool:
        return Store.can(self.role, needed)

    def money(self, value: float) -> str:
        return format_money(float(value), self.symbol)

    def money_short(self, value: float) -> str:
        return format_money_short(float(value), self.symbol)

    @property
    def tax_rate(self) -> float:
        return float(self.settings.get("tax_rate") or 0)


def ctx() -> Ctx:
    store = get_store()
    settings = store.settings()
    clock.set_timezone(settings.get("timezone"))  # every date and time the app shows or saves
    return Ctx(
        store=store,
        settings=settings,
        preset=PRESETS.get(settings["business_type"], PRESETS["retail"]),
        symbol=CURRENCIES.get(settings["currency"], "€"),
        user=st.session_state.get("user"),
    )


def _log_export(file_name: str) -> None:
    c = ctx()
    c.store.audit(c.username, "exportacion", file_name)


def logged_download(where, label: str, data, file_name: str, *args, **kwargs):
    """A download of business data that leaves a line in the activity log (who took what, and when)."""
    return where.download_button(label, data, file_name, *args, on_click=_log_export, args=(file_name,), **kwargs)
