"""Addresses outside a person's menu: a notice in Spanish, never the page itself nor Streamlit's English message."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.db import Store

ROOT = str(Path(__file__).resolve().parent.parent)

# The navigation of app.py reduced to its essence, with the address asked for set as Streamlit would.
SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx
from ui import routes

def page(name):
    def run():
        st.write("PAGE " + name)
    return run

PAGES = {{key: st.Page(page(key), title=key.title(), url_path=path, default=(key == "pos"))
         for key, path in [("pos", "vender"), ("agenda", "agenda"), ("settings", "ajustes"), ("team", "equipo")]}}
sections = {{"Operación": [PAGES["pos"], *([PAGES["agenda"]] if {agenda!r} else [])]}}
if not st.session_state.get("opened"):  # the first visit comes from the address; later runs from the app
    st.session_state["opened"] = True
    get_script_run_ctx().pages_manager.set_script_intent("", {path!r})
nav = st.navigation(routes.with_fallbacks(sections, PAGES, routes.requested_path(), notice={notice!r}))
nav.run()
"""


def _run(path: str, agenda: bool = True, notice: str = ""):
    return AppTest.from_string(SCRIPT.format(root=ROOT, path=path, agenda=agenda, notice=notice),
                               default_timeout=30).run()


def _texts(at) -> str:
    return " ".join([m.value for m in at.markdown] + [w.value for w in at.warning])


def test_allowed_page_opens():
    at = _run("agenda")
    assert not at.exception and "PAGE agenda" in _texts(at) and not at.warning


def test_page_of_another_role_explains_instead_of_opening():
    at = _run("ajustes")
    assert not at.exception
    assert "PAGE settings" not in _texts(at)
    assert "no está disponible con tu usuario" in at.warning[0].value


def test_unpaid_business_is_told_why():
    at = _run("ajustes", notice="Tu suscripción no está activa.")
    assert not at.exception and at.warning[0].value == "Tu suscripción no está activa."


def test_unknown_address_says_it_does_not_exist_in_spanish():
    at = _run("no-existe")
    assert not at.exception and "Esa página no existe" in at.warning[0].value


def test_alias_leads_to_the_real_page_only_when_allowed():
    at = _run("reservas")
    assert not at.exception and "PAGE agenda" in _texts(at)
    at = _run("reservas", agenda=False)
    assert not at.exception and "PAGE agenda" not in _texts(at)
    assert "no está disponible" in at.warning[0].value


@pytest.mark.parametrize("path", ["", "vender"])
def test_start_page_opens_at_root_and_at_its_own_address(path):
    at = _run(path)
    assert not at.exception and "PAGE pos" in _texts(at) and not at.warning


def test_odd_addresses_are_left_to_streamlit():
    at = _run("a.b")
    assert not at.exception and "PAGE pos" in _texts(at)


def test_new_customer_form_keeps_what_was_typed_when_it_fails(module_targets):
    target = module_targets.new()
    store = Store(target)
    store.load_preset("retail")
    store.close()
    script = f"""
import sys
sys.path.insert(0, {ROOT!r})
import streamlit as st
import ui.context, ui.pages_pos
from core.db import Store
store = Store({target!r})
ui.context.get_store = lambda: store
st.session_state["user"] = {{"id": 0, "username": "test", "name": "Tester", "role": "empleado"}}
ui.pages_pos.point_of_sale()
"""
    at = AppTest.from_string(script, default_timeout=30).run()
    at.button(key="add_" + str(int(Store(target).products().iloc[0]["id"]))).click().run()
    at.session_state["pos_view"] = "ticket"
    at.run()
    at.text_input(key="pos_new_email").input("ana@example.com")
    form = [b for b in at.button if b.label == "Crear cliente"][0]
    form.click().run()  # no name: refused
    assert at.text_input(key="pos_new_email").value == "ana@example.com"
    at.text_input(key="pos_new_name").input("Ana")
    [b for b in at.button if b.label == "Crear cliente"][0].click().run()
    assert not at.exception
    assert at.text_input(key="pos_new_name").value == "" and at.text_input(key="pos_new_email").value == ""
