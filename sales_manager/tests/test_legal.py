"""Legal texts: published only when complete, and accepted by each business with its version."""

import json
import shutil
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from streamlit.testing.v1 import AppTest

from conftest import PG_URL
from core.legal import TERMS_VERSION

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))
import legal  # noqa: E402

EXAMPLE = json.loads((ROOT / "legal" / "datos.example.json").read_text())


def complete(**changes):
    data = json.loads(json.dumps(EXAMPLE))
    data["subencargados"][-1].update(nombre="Correo Ejemplo SL", ubicacion="Unión Europea (España)")
    data.update(titular="Ana Prueba <b>", nif="12345678Z", domicilio="Calle Mayor 1, 28001 Madrid",
                fecha="7 de octubre de 2026", **changes)
    return data


def test_nothing_is_published_while_a_gap_remains():
    with pytest.raises(legal.LegalError) as missing:
        legal.render(EXAMPLE)
    for field in ("nif", "domicilio", "fecha", "titular", "subencargados"):
        assert field in str(missing.value)
    with pytest.raises(legal.LegalError, match="subencargados"):
        legal.render(complete(subencargados=[]))


def test_published_pages_are_complete_escaped_and_linked(tmp_path):
    docs = tmp_path / "docs"
    shutil.copytree(ROOT / "docs", docs)
    data = tmp_path / "datos.json"
    data.write_text(json.dumps(complete()))
    written = legal.publish(data, docs)
    assert {p.name for p in written} >= {"aviso-legal.html", "condiciones.html", "encargado.html", "index.html"}
    for page in ("aviso-legal", "condiciones", "encargado"):
        text = (docs / f"{page}.html").read_text()
        assert "{{" not in text and "PENDIENTE" not in text
        assert "12345678Z" in text and "Ana Prueba &lt;b&gt;" in text and "<b>" not in text
        assert (f"Versión {TERMS_VERSION}" in text) == (page != "aviso-legal")  # what businesses accept is versioned
    assert "<td>Correo Ejemplo SL</td>" in (docs / "encargado.html").read_text()
    for page in [docs / "index.html", docs / "tpv-tiendas" / "index.html"]:
        footer = page.read_text()
        assert footer.count("aviso-legal.html") == 1 and footer.count("condiciones.html\">Condiciones") == 1
    assert legal.link_footers(docs) == []  # running it again changes nothing


def test_the_live_website_never_shows_a_gap():
    for page in (ROOT / "docs").rglob("*.html"):
        text = page.read_text()
        assert "{{" not in text and "PENDIENTE" not in text, page


def test_every_gap_in_the_texts_has_a_value_in_the_example():
    gaps = set()
    for page in (ROOT / "legal").glob("*.html"):
        gaps |= set(legal.GAP.findall(page.read_text()))
    computed = {"contenido", "titulo", "pagina", "version_texto", "tabla_subencargados"}
    assert gaps - computed <= set(EXAMPLE), gaps - computed - set(EXAMPLE)


# ------------------------------------------------------------------ each business accepts them
needs_pg = pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def directory_url():
    import psycopg

    name = f"nk_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    yield urlunsplit(urlsplit(PG_URL)._replace(path=f"/{name}"))
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
import ui.auth, ui.context, ui.tenancy
from core.tenants import Directory

directory = Directory({url!r})
store = directory.store("cafe")
def info(code):
    return directory.get(code)
info.clear = lambda: None
ui.context.multi_tenant = lambda: True
ui.context.get_directory = lambda: directory
ui.context.get_store = lambda: store
ui.tenancy.tenant_info = info
original = ui.auth.setting
ui.auth.setting = lambda name: {terms!r} if name == "terms_url" else original(name)
st.session_state["tenant"] = "cafe"
st.session_state["signed_in_as"] = (ui.auth.require_user(store, store.settings()) or {{}}).get("username", "")
"""


def _app(url, terms="https://nirkana.es", user=None):
    at = AppTest.from_string(SCRIPT.format(root=str(ROOT / "sales_manager"), url=url, terms=terms),
                             default_timeout=60)
    if user:
        at.session_state["user"] = user
        at.session_state["last_seen"] = time.time()
    return at.run()


@needs_pg
def test_the_administrator_accepts_the_terms_when_creating_the_business(directory_url):
    from core.tenants import Directory

    directory = Directory(directory_url)
    setup = directory.create("cafe", "Café")
    at = _app(directory_url)
    label = at.checkbox[0].label
    assert "Condiciones del servicio" in label and "https://nirkana.es/encargado.html" in label and TERMS_VERSION in label
    at.text_input[0].input(setup)
    at.text_input[1].input("Ana")
    at.text_input[2].input("ana")
    at.text_input[3].input("Segura-2026!")
    at.text_input[4].input("Segura-2026!")
    at.button[0].click().run()
    assert any("aceptar las condiciones" in e.value for e in at.error)
    assert not directory.store("cafe").has_users()  # nothing is created without the acceptance

    at.checkbox[0].check()
    at.button[0].click().run()
    tenant = directory.get("cafe")
    assert (tenant["terms_version"], tenant["terms_accepted_by"]) == (TERMS_VERSION, "ana")
    assert any(r["action"] == "condiciones_aceptadas" for r in directory.log())


@needs_pg
def test_a_new_version_stops_only_the_administrator_until_accepted(directory_url):
    from core.tenants import Directory

    directory = Directory(directory_url)
    directory.create("cafe", "Café")
    store = directory.store("cafe")
    store.create_user("Ana", "ana", "admin", "Segura-2026!")
    store.create_user("Luis", "luis", "empleado", "48213579")
    users = {u["username"]: {k: u[k] for k in ("id", "username", "name", "role")} | {"location_id": None}
             for u in store.users().to_dict("records")}
    directory.accept_terms("cafe", "2020-01-01", "ana")  # an older version

    staff = _app(directory_url, user=users["luis"])
    assert staff.session_state["signed_in_as"] == "luis"  # the team keeps working

    at = _app(directory_url, user=users["ana"])
    assert at.session_state["signed_in_as"] == ""  # stopped at the new terms
    assert TERMS_VERSION in at.checkbox[0].label
    at.button[0].click().run()
    assert any("Marca la casilla" in e.value for e in at.error)
    at.checkbox[0].check()
    at.button[0].click().run()
    assert directory.get("cafe")["terms_version"] == TERMS_VERSION
    assert at.session_state["signed_in_as"] == "ana"


@needs_pg
def test_without_published_terms_nobody_is_asked(directory_url):
    from core.tenants import Directory

    directory = Directory(directory_url)
    directory.create("cafe", "Café")
    assert not _app(directory_url, terms="").checkbox  # bootstrap without the acceptance box
