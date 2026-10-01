"""Shared per-run context for pages."""

from dataclasses import dataclass

import streamlit as st

from core.db import Store
from core.presets import CURRENCIES, PRESETS
from core.pricing import format_money

# Filled by app.py so pages can link to each other.
PAGES: dict = {}


@st.cache_resource
def get_store() -> Store:
    return Store()


@dataclass
class Ctx:
    store: Store
    settings: dict
    preset: dict
    symbol: str

    def money(self, value: float) -> str:
        return format_money(float(value), self.symbol)

    @property
    def tax_rate(self) -> float:
        return float(self.settings.get("tax_rate") or 0)


def ctx() -> Ctx:
    store = get_store()
    settings = store.settings()
    return Ctx(
        store=store,
        settings=settings,
        preset=PRESETS.get(settings["business_type"], PRESETS["retail"]),
        symbol=CURRENCIES.get(settings["currency"], "€"),
    )
