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


# ------------------------------------------------------------------ one database role per business
def _database_owned_by(owner: str, createrole: bool):
    """A database owned by a non-superuser, like Neon's owner role: the real production situation."""
    import uuid
    from urllib.parse import urlsplit, urlunsplit

    import psycopg

    name = f"nk_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        if not admin.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (owner,)).fetchone():
            admin.execute(f'CREATE ROLE "{owner}" LOGIN PASSWORD \'dueno-de-prueba\'')
        admin.execute(f'ALTER ROLE "{owner}" {"CREATEROLE" if createrole else "NOCREATEROLE"}')
        admin.execute(f'CREATE DATABASE "{name}" OWNER "{owner}"')
    parts = urlsplit(PG_URL)
    return name, urlunsplit(parts._replace(netloc=f"{owner}:dueno-de-prueba@{parts.hostname}:{parts.port or 5432}",
                                           path=f"/{name}"))


def _drop(name: str, roles=()):
    import psycopg

    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        for role in roles:
            if admin.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone():
                admin.execute(f'DROP ROLE "{role}"')


@pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set")
def test_a_business_cannot_reach_another_even_naming_its_schema():
    import psycopg

    from core.engines import tenant_role_name
    from core.tenants import Directory

    name, url = _database_owned_by("nk_dueno_neon", createrole=True)
    roles = []
    try:
        directory = Directory(url)
        directory.create("cafe", "Café")
        directory.create("bar", "Bar")
        cafe, bar = directory.get("cafe"), directory.get("bar")
        roles = [cafe["db_role"], bar["db_role"]]
        mark = tenant_role_name("", name)
        assert cafe["db_role"] == f"{mark}n_cafe" and bar["db_role"] == f"{mark}n_bar"
        assert directory.role_isolation() == (2, 0)

        store = directory.store("cafe")
        store.load_preset("retail")  # everything the app does works as the business's role
        assert len(store.sales()) > 0
        for other in ('SELECT COUNT(*) FROM "n_bar".sales', "SELECT COUNT(*) FROM nirkana_operador.tenants",
                      'UPDATE "n_bar".settings SET value = \'x\''):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with store.db.tx() as cur:
                    cur.execute(other)
        with store.db.tx() as cur:
            assert cur.execute("SELECT current_user AS u").fetchone()["u"] == cafe["db_role"]
        store.close()
        directory.close()
    finally:
        _drop(name, roles)


@pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set")
def test_two_databases_on_one_server_never_share_a_business_role():
    from core.tenants import Directory

    made, roles = [], []
    try:
        for _ in range(2):
            name, url = _database_owned_by("nk_dueno_neon", createrole=True)
            made.append(name)
            directory = Directory(url)
            directory.create("cafe", "Café")  # the same business code in production and in a test copy
            roles.append(directory.get("cafe")["db_role"])
            directory.close()
        assert roles[0] and roles[1] and roles[0] != roles[1]
    finally:
        for name, role in zip(made, roles + [""] * 2):
            _drop(name, [role] if role else [])


@pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set")
def test_businesses_from_before_get_their_role_and_without_permission_nothing_breaks():
    import psycopg

    from core.engines import tenant_role_name
    from core.tenants import Directory

    name, url = _database_owned_by("nk_dueno_sin_roles", createrole=False)
    try:
        directory = Directory(url)
        directory.create("cafe", "Café")  # this user may not create roles: the business works as before
        assert directory.get("cafe")["db_role"] == "" and directory.role_isolation() == (0, 1)
        store = directory.store("cafe")
        store.load_preset("retail")
        store.close()
        directory.close()
        with psycopg.connect(PG_URL, autocommit=True) as admin:  # the owner is later allowed to create roles
            admin.execute('ALTER ROLE "nk_dueno_sin_roles" CREATEROLE')
        directory = Directory(url)  # every start gives a role to businesses that have none
        assert directory.get("cafe")["db_role"] == tenant_role_name("n_cafe", name)
        assert directory.role_isolation() == (1, 0)
        store = directory.store("cafe")
        assert len(store.sales()) > 0  # existing tables were granted to the new role
        store.close()
        directory.close()
    finally:
        _drop(name, [tenant_role_name("n_cafe", name)])
