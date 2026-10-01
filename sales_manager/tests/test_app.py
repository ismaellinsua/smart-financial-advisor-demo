"""Smoke tests: every page renders without exceptions against a demo database."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.db import Store

APP = str(Path(__file__).resolve().parent.parent / "app.py")
ROOT = str(Path(APP).parent)
PAGES = ["dashboard", "point_of_sale", "history", "products_page", "customers_page", "automations_page",
         "settings_page"]

# Renders a single page function against a given database file.
SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import ui.context, ui.pages
from core.db import Store
store = Store({db!r})
ui.context.get_store = lambda: store
ui.pages.get_store = lambda: store
ui.pages.{fn}()
"""


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "demo.db"
    Store(path).load_preset("restaurant")
    return str(path)


@pytest.fixture(scope="module")
def empty_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "empty.db"
    Store(path).load_preset("services", with_demo_sales=False)
    return str(path)


@pytest.mark.parametrize("fn", PAGES)
def test_page_renders_without_sales(empty_db, fn):
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=empty_db, fn=fn), default_timeout=30).run()
    assert not at.exception, at.exception


@pytest.mark.parametrize("fn", PAGES)
def test_page_renders(demo_db, fn):
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=demo_db, fn=fn), default_timeout=30).run()
    assert not at.exception, at.exception


def test_point_of_sale_checkout(demo_db):
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=demo_db, fn="point_of_sale"), default_timeout=30).run()
    before = len(Store(demo_db).sales())
    at.button(key=next(b.key for b in at.button if b.key and b.key.startswith("add_"))).click().run()
    charge = next(b for b in at.button if b.label.startswith("Cobrar"))
    charge.click().run()
    assert not at.exception, at.exception
    assert len(Store(demo_db).sales()) == before + 1


def test_onboarding_creates_workspace(tmp_path, monkeypatch):
    store = Store(tmp_path / "empty.db")
    import ui.context

    monkeypatch.setattr(ui.context, "get_store", lambda: store)
    monkeypatch.setattr("ui.pages.get_store", lambda: store)
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    at.text_input[0].input("Café Aurora")
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert store.settings()["business_name"] == "Café Aurora"
    assert not store.is_empty()


def test_password_gate(tmp_path, monkeypatch):
    store = Store(tmp_path / "gate.db")
    store.load_preset("retail", with_demo_sales=False)
    import ui.context

    monkeypatch.setattr(ui.context, "get_store", lambda: store)
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["app_password"] = "secreta"
    at.run()
    assert not at.exception
    assert any("Contraseña" == t.label for t in at.text_input)
    at.text_input[0].input("mala")
    at.button[0].click().run()
    assert at.error and "incorrecta" in at.error[0].value
    at.text_input[0].input("secreta")
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["authenticated"]
