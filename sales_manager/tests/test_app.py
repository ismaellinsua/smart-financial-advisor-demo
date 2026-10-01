"""Smoke tests: every page renders without exceptions against a demo database."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.db import Store

APP = str(Path(__file__).resolve().parent.parent / "app.py")
ROOT = str(Path(APP).parent)
PAGES = ["dashboard", "point_of_sale", "history", "products_page", "customers_page", "automations_page",
         "settings_page", "cash_page", "agenda_page", "team_page"]

# Renders a single page function against a given database file.
SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import ui.context, ui.pages
from core.db import Store
import streamlit as st
store = Store({db!r})
ui.context.get_store = lambda: store
ui.pages.get_store = lambda: store
st.session_state["user"] = {{"id": 0, "username": "test", "name": "Tester", "role": {role!r}}}
ui.pages.{fn}()
"""


@pytest.fixture(scope="module")
def demo_db(module_targets):
    target = module_targets.new()
    store = Store(target)
    store.load_preset("restaurant")
    store.close()
    return target


@pytest.fixture(scope="module")
def empty_db(module_targets):
    target = module_targets.new()
    store = Store(target)
    store.load_preset("services", with_demo_sales=False)
    store.close()
    return target


@pytest.mark.parametrize("fn", PAGES)
def test_page_renders_without_sales(empty_db, fn):
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=empty_db, fn=fn, role="admin"), default_timeout=30).run()
    assert not at.exception, at.exception


@pytest.mark.parametrize("fn", PAGES)
def test_page_renders(demo_db, fn):
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=demo_db, fn=fn, role="admin"), default_timeout=30).run()
    assert not at.exception, at.exception


def test_point_of_sale_checkout(demo_db):
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=demo_db, fn="point_of_sale", role="empleado"), default_timeout=30).run()
    check = Store(demo_db)
    before = len(check.sales())
    at.button(key=next(b.key for b in at.button if b.key and b.key.startswith("add_"))).click().run()
    charge = next(b for b in at.button if b.label.startswith("Cobrar"))
    charge.click().run()
    assert not at.exception, at.exception
    assert len(check.sales()) == before + 1
    check.close()


def _app(store, monkeypatch, secrets=None, user=None):
    import time

    import ui.context

    monkeypatch.setattr(ui.context, "get_store", lambda: store)
    monkeypatch.setattr("ui.pages.get_store", lambda: store)
    at = AppTest.from_file(APP, default_timeout=60)
    for key, value in (secrets or {}).items():
        at.secrets[key] = value
    if user:
        at.session_state["user"] = user
        at.session_state["last_seen"] = time.time()
    return at.run()


def test_first_run_creates_admin_then_business(tmp_path, monkeypatch):
    store = Store(tmp_path / "empty.db")
    at = _app(store, monkeypatch)
    assert not at.exception
    at.text_input[0].input("Ismael")
    at.text_input[1].input("ismael")
    at.text_input[2].input("Segura2026")
    at.text_input[3].input("Segura2026")
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert store.has_users() and store.users().iloc[0]["role"] == "admin"
    at.text_input[0].input("Café Aurora")  # onboarding form follows
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert store.settings()["business_name"] == "Café Aurora"
    assert not store.is_empty()


def test_first_admin_requires_setup_password(tmp_path, monkeypatch):
    store = Store(tmp_path / "setup.db")
    at = _app(store, monkeypatch, secrets={"app_password": "clave-de-instalacion"})
    fields = at.text_input
    fields[0].input("mala")
    fields[1].input("Ismael")
    fields[2].input("ismael")
    fields[3].input("Segura2026")
    fields[4].input("Segura2026")
    at.button[0].click().run()
    assert at.error and "instalación" in at.error[0].value
    assert not store.has_users()
    at.text_input[0].input("clave-de-instalacion")
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert store.has_users()


def test_staff_login_and_permissions(tmp_path, monkeypatch):
    store = Store(tmp_path / "team.db")
    store.load_preset("restaurant", with_demo_sales=False)
    store.create_user("Ismael", "ismael", "admin", "Segura2026")
    store.create_user("Lucía", "lucia", "empleado", "4826")
    at = _app(store, monkeypatch)
    at.selectbox[0].set_value("lucia")
    at.text_input[0].input("0000")
    at.button[0].click().run()
    assert at.error and "incorrectos" in at.error[0].value
    at.text_input[0].input("4826")
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["user"]["username"] == "lucia"
    labels = " ".join(str(b.label) for b in at.sidebar.button)
    assert "Cambiar de negocio" not in labels and "Cerrar sesión · Lucía" in labels

    # A staff member who opens an admin page directly gets a permission error, not the page.
    script = SCRIPT.format(root=ROOT, db=str(tmp_path / "team.db"), fn="settings_page", role="empleado")
    page = AppTest.from_string(script, default_timeout=30).run()
    assert page.error and "permiso" in page.error[0].value
    assert not page.text_input  # no settings form rendered


def test_deactivated_user_is_signed_out(tmp_path, monkeypatch):
    store = Store(tmp_path / "out.db")
    store.load_preset("retail", with_demo_sales=False)
    store.create_user("Ismael", "ismael", "admin", "Segura2026")
    uid = store.create_user("Diego", "diego", "empleado", "7391")
    at = _app(store, monkeypatch, user={"id": uid, "username": "diego", "name": "Diego", "role": "empleado"})
    assert at.session_state["user"]["username"] == "diego"
    store.update_user(uid, active=False)
    at.run()
    assert "user" not in at.session_state


def test_switch_business_button_opens_dialog(tmp_path, monkeypatch):
    # AppTest reruns the whole script, which closes dialogs, so the switch itself is checked in a real browser.
    store = Store(tmp_path / "switch.db")
    store.load_preset("restaurant", with_demo_sales=False)
    uid = store.create_user("Ismael", "ismael", "admin", "Segura2026")
    at = _app(store, monkeypatch, user={"id": uid, "username": "ismael", "name": "Ismael", "role": "admin"})
    next(b for b in at.sidebar.button if b.label == "Cambiar de negocio").click().run()
    assert not at.exception, at.exception
    radio = at.radio(key="switch_type")
    assert radio.value == "restaurant"
    assert list(radio.options) == ["Pequeño comercio / Tienda", "Restaurante / Cafetería",
                                   "Autónomo / Servicios profesionales", "Tienda online / E-commerce"]
    assert at.text_input(key="switch_name_restaurant").value == store.settings()["business_name"]
