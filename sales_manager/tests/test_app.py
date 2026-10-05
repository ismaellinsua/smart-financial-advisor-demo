"""Smoke tests: every page renders without exceptions against a demo database."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.db import Store

APP = str(Path(__file__).resolve().parent.parent / "app.py")
ROOT = str(Path(APP).parent)
PAGES = ["dashboard", "intelligence_page", "point_of_sale", "history", "products_page", "customers_page", "automations_page",
         "settings_page", "cash_page", "agenda_page", "team_page", "promotions_page", "tables_page",
         "kitchen_page", "purchases_page", "expenses_page", "help_page",
         "accounting_page"]

# Renders a single page function against a given database file.
SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import ui.context, ui.pages, ui.pages_promos, ui.pages_tables
ui.pages.promotions_page = ui.pages_promos.promotions_page
ui.pages.tables_page = ui.pages_tables.tables_page
ui.pages.kitchen_page = ui.pages_tables.kitchen_page
ui.pages_tables.get_store = lambda: store
import ui.pages_management
ui.pages.purchases_page = ui.pages_management.purchases_page
ui.pages.expenses_page = ui.pages_management.expenses_page
ui.pages.accounting_page = ui.pages_management.accounting_page
import ui.pages_intel
ui.pages.intelligence_page = ui.pages_intel.intelligence_page
from core.db import Store
import streamlit as st
store = Store({db!r})
ui.context.get_store = lambda: store
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


@pytest.fixture(scope="module")
def two_locations_db(module_targets):
    """The demo restaurant with a second location that has some stock, tables and a sale of its own."""
    target = module_targets.new()
    store = Store(target)
    store.load_preset("restaurant")
    playa = store.add_location("Playa", "Paseo Marítimo 3", "910 000 001")
    main = store.locations()[0]["id"]
    product = store.products()
    product = product[product["track_stock"] == 1].iloc[0]
    store.transfer_stock(int(product["id"]), 3, main, playa, "Ana")
    store.save_table("Terraza P1", "Terraza", 4, location_id=playa)
    store.create_sale([{"product_id": int(product["id"]), "quantity": 1}], location_id=playa)
    store.close()
    return target


@pytest.mark.parametrize("fn", PAGES)
def test_page_renders_with_two_locations(two_locations_db, fn):
    script = SCRIPT.format(root=ROOT, db=two_locations_db, fn=fn, role="admin").replace(
        "ui.pages.{fn}()".format(fn=fn), f"st.session_state['location'] = store.locations()[1]['id']\nui.pages.{fn}()")
    at = AppTest.from_string(script, default_timeout=30).run()
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


def test_point_of_sale_split_bill(demo_db):
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=demo_db, fn="point_of_sale", role="empleado"),
                             default_timeout=30).run()
    check = Store(demo_db)
    add = [b.key for b in at.button if b.key and b.key.startswith("add_")]
    at.button(key=add[0]).click().run()
    at.button(key=add[1]).click().run()
    at.session_state["pos_mode"] = "Dividir cuenta"
    at.run()
    assert at.number_input(key="pos_people").value == 2
    at.button(key="pos_charge").click().run()
    assert not at.exception, at.exception
    sale = check.sale(int(check.sales().iloc[0]["id"]))
    assert sale["payment_method"] in ("Mixto", "Tarjeta") and len(sale["payments"]) == 2
    assert sum(p["amount"] for p in sale["payments"]) == pytest.approx(sale["total"])
    check.close()


def test_table_order_flow(demo_db):
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=demo_db, fn="tables_page", role="empleado"),
                             default_timeout=30).run()
    assert not at.exception, at.exception
    check = Store(demo_db)
    before = len(check.sales())
    free = next(b for b in at.button if b.label == "Abrir")
    free.click().run()
    oid = at.session_state["table_order"]
    adds = [b.key for b in at.button if b.key and b.key.startswith(f"oadd_{oid}_")]
    at.button(key=adds[0]).click().run()
    at.button(key=adds[1]).click().run()
    assert len(check.order(oid)["items"]) == 2
    at.button(key=f"charge_toggle_{oid}").click().run()
    at.button(key=f"order_{oid}_charge").click().run()
    assert not at.exception, at.exception
    assert len(check.sales()) == before + 1
    assert check.order(oid)["status"] == "cobrada"
    check.close()


def _app(store, monkeypatch, secrets=None, user=None):
    import time

    import ui.context

    monkeypatch.setattr(ui.context, "get_store", lambda: store)
    at = AppTest.from_file(APP, default_timeout=60)
    for key, value in (secrets or {}).items():
        at.secrets[key] = value
    if user:
        at.session_state["user"] = user
        at.session_state["last_seen"] = time.time()
    return at.run()


def test_first_run_creates_admin_then_business(tmp_path, monkeypatch):
    import ui.auth

    store = Store(tmp_path / "empty.db")
    at = _app(store, monkeypatch)
    assert not at.exception
    fields = at.text_input
    fields[0].input("NO-ES-EL-CODIGO")
    fields[1].input("Elena")
    fields[2].input("elena")
    fields[3].input("Segura2026")
    fields[4].input("Segura2026")
    at.button[0].click().run()
    assert at.error and not store.has_users()  # without the code from the server log, no admin
    at.text_input[0].input(ui.auth.setup_code())
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert store.has_users() and store.users().iloc[0]["role"] == "admin"
    codes = at.code[0].value.split("\n")  # recovery codes are shown once, before anything else
    assert len(codes) == 8 and store.recovery_codes_left(int(store.users().iloc[0]["id"])) == 8
    next(b for b in at.button if b.label == "Ya los he guardado").click().run()
    # The three-step setup follows: business, fiscal data, start.
    at.text_input[0].input("Café Aurora")
    at.radio[0].set_value("restaurant")
    next(b for b in at.button if b.label == "Siguiente").click().run()
    assert not at.exception, at.exception
    fiscal = {t.label: t for t in at.text_input}
    fiscal["NIF / CIF"].input("b-1234567-4")
    fiscal["Dirección fiscal"].input("Calle Mayor 1, 28001 Madrid")
    next(b for b in at.button if b.label == "Siguiente").click().run()
    assert not at.exception, at.exception
    assert not at.warning  # a valid CIF raises no warning
    assert all(not t.value for t in at.toggle)  # no example sales unless asked
    next(b for b in at.button if b.label == "Crear mi negocio").click().run()
    assert not at.exception, at.exception
    settings = store.settings()
    assert (settings["business_name"], settings["business_type"]) == ("Café Aurora", "restaurant")
    assert (settings["tax_id"], settings["address"]) == ("B12345674", "Calle Mayor 1, 28001 Madrid")
    assert float(settings["tax_rate"]) == 10.0 and settings["demo_mode"] == "no"
    assert not store.is_empty() and store.sales().empty


def test_first_admin_requires_setup_password(tmp_path, monkeypatch):
    store = Store(tmp_path / "setup.db")
    at = _app(store, monkeypatch, secrets={"app_password": "clave-de-instalacion"})
    fields = at.text_input
    fields[0].input("mala")
    fields[1].input("Elena")
    fields[2].input("elena")
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
    store.create_user("Elena", "elena", "admin", "Segura2026")
    store.create_user("Lucía Pérez", "lucia", "empleado", "482619")
    at = _app(store, monkeypatch)
    page = " ".join(str(e.value) for e in at.markdown) + " ".join(str(s.label) for s in at.selectbox)
    assert "Lucía" not in page and "Elena" not in page and not at.selectbox  # no public list of the team
    at.text_input[0].input("lucia")
    at.text_input[1].input("000000")
    at.button[0].click().run()
    assert at.error and "incorrectos" in at.error[0].value
    at.text_input[1].input("482619")
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["user"]["username"] == "lucia"
    labels = " ".join(str(b.label) for b in at.sidebar.button)
    assert "Cambiar de negocio" not in labels and "Cerrar sesión · Lucía Pérez" in labels and "Cambiar mi PIN" in labels

    # A staff member who opens an admin page directly gets a permission error, not the page.
    script = SCRIPT.format(root=ROOT, db=str(tmp_path / "team.db"), fn="settings_page", role="empleado")
    page = AppTest.from_string(script, default_timeout=30).run()
    assert page.error and "permiso" in page.error[0].value
    assert not page.text_input  # no settings form rendered


def test_deactivated_user_is_signed_out(tmp_path, monkeypatch):
    store = Store(tmp_path / "out.db")
    store.load_preset("retail", with_demo_sales=False)
    store.create_user("Elena", "elena", "admin", "Segura2026")
    uid = store.create_user("Diego", "diego", "empleado", "739104")
    at = _app(store, monkeypatch, user={"id": uid, "username": "diego", "name": "Diego", "role": "empleado"})
    assert at.session_state["user"]["username"] == "diego"
    store.update_user(uid, active=False)
    at.run()
    assert "user" not in at.session_state


def test_switch_business_button_opens_dialog(tmp_path, monkeypatch):
    # AppTest reruns the whole script, which closes dialogs, so the switch itself is checked in a real browser.
    store = Store(tmp_path / "switch.db")
    store.load_preset("restaurant", with_demo_sales=False)
    uid = store.create_user("Elena", "elena", "admin", "Segura2026")
    at = _app(store, monkeypatch, user={"id": uid, "username": "elena", "name": "Elena", "role": "admin"})
    next(b for b in at.sidebar.button if b.label == "Cambiar de negocio").click().run()
    assert not at.exception, at.exception
    radio = at.radio(key="switch_type")
    assert radio.value == "restaurant"
    assert list(radio.options) == ["Pequeño comercio / Tienda", "Restaurante / Cafetería",
                                   "Autónomo / Servicios profesionales", "Tienda online / E-commerce"]
    assert at.text_input(key="switch_name_restaurant").value == store.settings()["business_name"]


def test_settings_hide_destructive_actions_once_there_are_real_sales(module_targets):
    target = module_targets.new()
    store = Store(target)
    store.load_preset("retail", with_demo_sales=False)
    pid = int(store.products()["id"].iloc[0])
    store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")
    store.close()
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=target, fn="settings_page", role="admin"),
                             default_timeout=30).run()
    assert not at.exception, at.exception
    labels = {b.label for b in at.button}
    assert "Cambiar solo el tipo" in labels
    assert not labels & {"Cargar plantilla", "Empezar desde cero", "Restaurar copia"}


def test_settings_turn_on_the_billing_register_and_check_it(module_targets):
    target = module_targets.new()
    store = Store(target)
    store.load_preset("retail", with_demo_sales=False)
    store.save_settings({"tax_id": "B12345678"})
    store.close()
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=target, fn="settings_page", role="admin"),
                             default_timeout=30).run()
    assert not at.exception, at.exception
    enable = next(b for b in at.button if b.label == "Activar el registro de facturación")
    assert enable.disabled
    next(c for c in at.checkbox if "no se puede desactivar" in c.label).check().run()
    next(b for b in at.button if b.label == "Activar el registro de facturación").click().run()
    assert not at.exception, at.exception
    store = Store(target)
    df = store.products()
    store.create_sale([{"product_id": int(df.loc[df["sku"] == "CAM-001", "id"].iloc[0]), "quantity": 1}], "Tarjeta")
    store.close()
    at.run()
    next(b for b in at.button if b.label == "Comprobar la cadena").click().run()
    assert not at.exception, at.exception
    assert any("Cadena correcta: 1 registros" in str(m.value) for m in at.success)


def test_settings_offer_templates_in_demo_mode(demo_db):
    assert Store(demo_db).is_demo()
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=demo_db, fn="settings_page", role="admin"),
                             default_timeout=30).run()
    assert not at.exception, at.exception
    assert {"Cargar plantilla", "Empezar desde cero", "Restaurar copia"} <= {b.label for b in at.button}


def test_weak_pin_from_before_must_be_changed_at_login(tmp_path, monkeypatch):
    from core.security import hash_secret

    store = Store(tmp_path / "weak.db")
    store.load_preset("retail", with_demo_sales=False)
    store.create_user("Elena", "elena", "admin", "Segura2026")
    uid = store.create_user("Ana", "ana", "empleado", "582913")
    with store.db.tx() as cur:  # a 4-digit PIN set under the old rules
        cur.execute("UPDATE users SET secret_hash = ? WHERE id = ?", (hash_secret("4826"), uid))
    at = _app(store, monkeypatch)
    at.text_input[0].input("ana")
    at.text_input[1].input("4826")
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert "más seguro" in " ".join(str(m.value) for m in at.markdown)
    at.text_input[0].input("4826")
    at.text_input[1].input("771930")
    at.text_input[2].input("771930")
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert "must_change_secret" not in at.session_state
    assert store.authenticate("ana", "771930")["name"] == "Ana"


def test_staff_discount_above_the_limit_blocks_the_charge(demo_db):
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=demo_db, fn="point_of_sale", role="empleado"),
                             default_timeout=30).run()
    at.button(key=next(b.key for b in at.button if b.key and b.key.startswith("add_"))).click().run()
    at.number_input(key="pos_discount").set_value(50.0).run()
    assert not at.exception, at.exception
    charge = next(b for b in at.button if b.label.startswith("Cobrar"))
    assert charge.disabled
    assert any("autorización" in w.value for w in at.warning)
    assert "Usuario del encargado" in [t.label for t in at.text_input]
    at.number_input(key="pos_discount").set_value(10.0).run()
    assert not next(b for b in at.button if b.label.startswith("Cobrar")).disabled


def test_staff_history_shows_only_their_own_recent_sales(module_targets):
    from datetime import timedelta

    from core import clock

    target = module_targets.new()
    store = Store(target)
    store.load_preset("retail", with_demo_sales=False)
    df = store.products()
    pid = int(df.loc[df["sku"] == "CAM-001", "id"].iloc[0])
    mine = store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta", user_name="Tester")
    theirs = store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta", user_name="Otra persona")
    old = store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta", user_name="Tester",
                            when=clock.now() - timedelta(days=20))
    store.close()
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=target, fn="history", role="empleado"),
                             default_timeout=30).run()
    assert not at.exception, at.exception
    shown = set(at.dataframe[0].value["number"])
    assert mine["number"] in shown and theirs["number"] not in shown and old["number"] not in shown
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=target, fn="history", role="encargado"),
                             default_timeout=30).run()
    assert {mine["number"], theirs["number"]} <= set(at.dataframe[0].value["number"])


# Who may open each page. The menu hides the rest, and each page checks again on its own (an address typed by hand
# must not open it either).
PAGE_ROLES = {
    "point_of_sale": "empleado", "history": "empleado", "agenda_page": "empleado", "tables_page": "empleado",
    "kitchen_page": "empleado", "help_page": "empleado",
    "dashboard": "encargado", "cash_page": "encargado", "products_page": "encargado", "customers_page": "encargado",
    "automations_page": "encargado", "intelligence_page": "encargado", "promotions_page": "encargado",
    "purchases_page": "encargado", "expenses_page": "encargado", "accounting_page": "encargado",
    "team_page": "admin", "settings_page": "admin",
}
RANK = {"empleado": 0, "encargado": 1, "admin": 2}


def test_every_page_is_listed_in_the_role_matrix():
    assert set(PAGE_ROLES) == set(PAGES)


@pytest.mark.parametrize("role", list(RANK))
@pytest.mark.parametrize("fn", list(PAGE_ROLES))
def test_each_page_checks_the_role_itself(demo_db, fn, role):
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=demo_db, fn=fn, role=role), default_timeout=30).run()
    assert not at.exception, at.exception
    refused = any("No tienes permiso" in str(e.value) for e in at.error)
    assert refused == (RANK[role] < RANK[PAGE_ROLES[fn]]), f"{fn} as {role}"


def test_help_shows_each_role_only_what_it_can_do(demo_db):
    titles = {}
    for role in ("empleado", "admin"):
        at = AppTest.from_string(SCRIPT.format(root=ROOT, db=demo_db, fn="help_page", role=role),
                                 default_timeout=30).run()
        assert not at.exception, at.exception
        titles[role] = {e.label for e in at.expander}
    assert "Cobrar una venta" in titles["empleado"] and "Equipo y seguridad" not in titles["empleado"]
    assert {"Cobrar una venta", "Equipo y seguridad", "Cerrar la caja"} <= titles["admin"]


def test_a_failing_page_shows_a_reference_and_is_logged(tmp_path, monkeypatch):
    import ui.pages

    store = Store(tmp_path / "errors.db")
    store.load_preset("retail", with_demo_sales=False)
    uid = store.create_user("Ana", "ana", "admin", "Segura2026!")

    def broken():
        {}["customer@example.com"]  # the message would contain personal data: it must not be stored

    monkeypatch.setattr(ui.pages, "dashboard", broken)
    at = _app(store, monkeypatch, user={"id": uid, "username": "ana", "name": "Ana", "role": "admin"})
    assert not at.exception, at.exception  # the person sees a message, not a crash
    message = at.error[0].value
    errors = store.recent_errors()
    assert len(errors) == 1 and errors.iloc[0]["ref"] in message
    row = errors.iloc[0]
    assert (row["kind"], row["page"], row["username"]) == ("KeyError", "Panel", "ana")
    assert "broken" in row["where_"] and "example.com" not in " ".join(map(str, row.values))


def test_expense_with_supplier_invoice_reaches_the_gestoria_page(module_targets):
    from core import clock
    from core.accounting import quarter

    target = module_targets.new()
    store = Store(target)
    store.load_preset("retail", with_demo_sales=False)
    store.close()
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=target, fn="expenses_page", role="admin"),
                             default_timeout=30).run()
    def first(label):  # the page also has a «Gastos fijos» form with its own «Concepto»
        return next(t for t in at.text_input if t.label == label)

    first("Concepto").input("Luz de septiembre")
    next(n for n in at.number_input if n.label.startswith("Importe")).set_value(121.0)
    first("Proveedor").input("Eléctrica S.A.")
    first("NIF del proveedor").input("A81948077")
    first("Nº de factura").input("F-2026-881")
    next(s for s in at.selectbox if s.label == "IVA de la factura").set_value(21.0)
    next(b for b in at.button if b.label == "Apuntar gasto").click().run()
    assert not at.exception, at.exception

    store = Store(target)
    received = store.received_book(*quarter(clock.today()))
    assert list(received["Cuota IVA"]) == [21.0] and received.iloc[0]["Nº factura"] == "F-2026-881"
    store.close()
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=target, fn="accounting_page", role="admin"),
                             default_timeout=30).run()
    at.selectbox[0].set_value(quarter(clock.today())).run()
    assert not at.exception, at.exception
    assert any("IVA soportado en facturas recibidas: **21,00 €** (1 facturas)" in str(c.value) for c in at.caption)


def test_setup_password_from_the_environment(monkeypatch):
    """In a container there is no secrets file: APP_PASSWORD from the environment protects the first run."""
    from ui.auth import configured_password

    monkeypatch.delenv("APP_PASSWORD", raising=False)
    assert configured_password() is None
    monkeypatch.setenv("APP_PASSWORD", "clave-de-instalacion")
    assert configured_password() == "clave-de-instalacion"


def test_container_refuses_to_keep_data_on_its_own_disk(monkeypatch):
    """In the container the disk is wiped on every deploy: without DATABASE_URL the app must stop, not use SQLite."""
    from ui import context

    opened = []
    monkeypatch.setenv("REQUIRE_DATABASE", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(context, "Store", lambda *args, **kwargs: opened.append(args))
    monkeypatch.setattr(context, "get_store", lambda: context._single_store())  # other tests replace it for good
    context._single_store.clear()
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert at.error and "DATABASE_URL" in at.error[0].value
    assert opened == []  # no local file was opened
    context._single_store.clear()
