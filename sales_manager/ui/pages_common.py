"""Helpers shared by the application pages."""

import pandas as pd
import streamlit as st

from core import automation, clock
from core.security import csv_safe

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _today_label() -> str:
    d = clock.today()
    return f"{automation.WEEKDAYS[d.weekday()].capitalize()}, {d.day} de {MONTHS[d.month - 1]} de {d.year}"


def _pct(value: float, signed: bool = False) -> str:
    return (f"{value:+.1f}" if signed else f"{value:.1f}").replace(".", ",") + " %"


def _delta(value) -> str | None:
    return None if value is None else _pct(value, signed=True)


def _require(c, role: str) -> bool:
    """Second line of defence: pages also check the role, not only the menu."""
    if c.can(role):
        return True
    st.error("No tienes permiso para ver esta sección.", icon=":material/lock:")
    return False


def _csv(df: pd.DataFrame) -> bytes:
    # UTF-8 with BOM and semicolons so it opens cleanly in Spanish-locale Excel.
    return csv_safe(df).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
