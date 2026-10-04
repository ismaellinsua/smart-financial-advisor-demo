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


@st.cache_resource(show_spinner="Conectando con la base de datos…")
def get_store() -> Store:
    url = database_url()
    return Store(url) if url else Store()


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
