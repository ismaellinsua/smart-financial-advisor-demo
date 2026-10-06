"""One business never sees another's data through anything shared by the server (caches, stores)."""

from types import SimpleNamespace

import pytest
import streamlit as st

import ui.pages_intel as intel
from conftest import PG_URL
from core.db import Store


class FakeStore:
    def __init__(self, key, name):
        self.cache_key, self.name = key, name

    def data_version(self):
        return (0, 0, 0, 0, 0, 0, 0)  # a business just created: the same for every new business

    def alerts(self):
        return [{"title": f"Stock bajo en {self.name}", "level": "alta", "page": "products"}]

    def weekly_report(self, start, alerts=None):
        return {"business": self.name}


def test_shared_alerts_and_reports_never_cross_businesses(monkeypatch):
    st.cache_data.clear()
    # Python reuses the memory address of a store that was dropped (more businesses than the server keeps open):
    # the cache must not tell two businesses apart by it.
    monkeypatch.setattr(intel, "id", lambda _obj: 140_000_000, raising=False)
    a = SimpleNamespace(store=FakeStore("n_cafe_aurora", "Café Aurora"))
    b = SimpleNamespace(store=FakeStore("n_bar_sol", "Bar Sol"))
    assert intel.cached_alerts(a)[0]["title"] == "Stock bajo en Café Aurora"
    assert intel.cached_alerts(b)[0]["title"] == "Stock bajo en Bar Sol"
    assert intel.cached_report(a, "2026-10-05")["business"] == "Café Aurora"
    assert intel.cached_report(b, "2026-10-05")["business"] == "Bar Sol"


@pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set")
def test_each_business_store_has_its_own_cache_key(tmp_path):
    import psycopg

    with psycopg.connect(PG_URL, autocommit=True) as conn:
        for schema in ("n_iso_a", "n_iso_b"):
            conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            conn.execute(f'CREATE SCHEMA "{schema}"')
    stores = [Store(PG_URL, schema="n_iso_a"), Store(PG_URL, schema="n_iso_a"), Store(PG_URL, schema="n_iso_b")]
    try:
        a1, a2, b = (s.cache_key for s in stores)
        assert a1 == a2 != b  # shared by every session of one business, never with another
        assert "tests" not in a1  # the database password never ends up in a cache key
        assert Store(str(tmp_path / "x.db")).cache_key != Store(str(tmp_path / "y.db")).cache_key
    finally:
        for s in stores:
            s.close()
        with psycopg.connect(PG_URL, autocommit=True) as conn:
            for schema in ("n_iso_a", "n_iso_b"):
                conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
