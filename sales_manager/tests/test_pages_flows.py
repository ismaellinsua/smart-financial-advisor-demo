"""What people do on Historial, Equipo y seguridad and Cierre de caja, click by click: not only that each page renders
(test_app.py), but that its buttons, forms and dialogs change the business as they should and respect each role."""

import json
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import clock
from core.db import Store
from core.security import new_totp_secret, totp_code

ROOT = str(Path(__file__).resolve().parent.parent)

# Runs `code` with a signed-in person. `pick` makes every selectable table answer that its first row is selected, which
# AppTest cannot click; `upload` is what the file picker returns (AppTest cannot upload files either).
SCRIPT = """
import sys, types
sys.path.insert(0, {root!r})
import streamlit as st
import ui.context
from core.db import Store
store = Store({db!r})
ui.context.get_store = lambda: store
st.session_state["user"] = {{"id": {user_id}, "username": {username!r}, "name": {name!r}, "role": {role!r}}}
if {readonly}:
    st.session_state["billing_access"] = types.SimpleNamespace(level="readonly")
if {pick}:
    shown = st.dataframe
    def picked(*args, **kwargs):
        table = shown(*args, **kwargs)
        if kwargs.get("on_select") == "rerun":
            return types.SimpleNamespace(selection=types.SimpleNamespace(rows=[0]))
        return table
    st.dataframe = picked
upload = {upload!r}
if upload is not None:
    st.file_uploader = lambda *a, **k: types.SimpleNamespace(getvalue=lambda: upload)
{code}
"""


def app(target, code, role="admin", user_id=0, username="test", name="Tester", pick=False, upload=None,
        readonly=False):
    script = SCRIPT.format(root=ROOT, db=target, code=code, role=role, user_id=user_id, username=username, name=name,
                           pick=pick, upload=upload, readonly=readonly)
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception, at.exception
    return at


def labelled(widgets, label):
    return next(w for w in widgets if w.label == label)


def texts(at) -> str:
    return " ".join(str(e.value) for kind in ("success", "error", "warning", "info", "caption", "markdown")
                    for e in getattr(at, kind))


@pytest.fixture
def shop(module_targets):
    """A shop with one sale of two T-shirts (CAM-001) made today by Tester."""
    target = module_targets.new()
    store = Store(target)
    store.load_preset("retail", with_demo_sales=False)
    store.save_settings({"demo_mode": "no", "tax_id": "B12345678", "address": "Calle Mayor 1, 28001 Madrid"})
    df = store.products()
    pid = int(df.loc[df["sku"] == "CAM-001", "id"].iloc[0])
    sale = store.create_sale([{"product_id": pid, "quantity": 2}], "Efectivo", user_name="Tester")
    yield target, store, sale
    store.close()


# ------------------------------------------------------------------ Historial
HISTORY = "import ui.pages_history as h\nh.history()"


def test_history_shows_the_selected_sale_and_what_can_be_done_with_it(shop):
    target, store, sale = shop
    at = app(target, HISTORY, role="encargado", pick=True)
    assert f"{sale['number']} ·" in texts(at)
    labels = [b.label for b in at.button]
    assert {"Emitir factura", "Devolver productos", "Anular la venta completa"} <= set(labels)
    assert not labelled(at.button, "Emitir factura").disabled
    at = labelled(at.button, "Anular la venta completa").click().run()
    assert "Sí, anular" in [b.label for b in at.button]  # asks before cancelling


def test_history_filters_by_status_and_search(shop):
    target, store, sale = shop
    at = app(target, HISTORY, role="encargado")
    assert sale["number"] in set(at.dataframe[0].value["number"])
    at = labelled(at.selectbox, "Estado").select("Anuladas").run()
    assert at.dataframe[0].value.empty
    at = labelled(at.selectbox, "Estado").select("Todas").run()
    at = labelled(at.text_input, "Buscar").input("no-existe").run()
    assert at.dataframe[0].value.empty
    at = labelled(at.text_input, "Buscar").input(sale["number"][-4:]).run()
    assert sale["number"] in set(at.dataframe[0].value["number"])


def test_cancelling_a_sale_returns_the_stock_and_is_logged(shop):
    target, store, sale = shop
    before = store.products().set_index("sku").loc["CAM-001", "stock"]
    at = app(target, f"import ui.pages_history as h\nh._confirm_cancel({sale['id']}, {sale['number']!r})",
             role="encargado")
    labelled(at.button, "Sí, anular").click().run()
    assert store.sale(sale["id"])["status"] == "anulada"
    assert store.products().set_index("sku").loc["CAM-001", "stock"] == before + 2
    assert "venta_anulada" in set(store.audit_log()["action"])


def test_staff_cannot_cancel_even_from_the_dialog(shop):
    target, store, sale = shop
    at = app(target, f"import ui.pages_history as h\nh._confirm_cancel({sale['id']}, {sale['number']!r})",
             role="empleado")
    at = labelled(at.button, "Sí, anular").click().run()
    assert "Solo un encargado" in texts(at)
    assert store.sale(sale["id"])["status"] == "completada"


def test_issuing_an_invoice_from_a_sale(shop):
    target, store, sale = shop
    at = app(target, f"import ui.pages_history as h\nh._invoice_dialog({sale['id']})", role="encargado")
    at = labelled(at.button, "Emitir factura").click().run()
    assert "Nombre" in texts(at) or at.error  # the customer's data are required
    assert store.invoice_for_sale(sale["id"]) is None
    labelled(at.text_input, "Nombre o razón social *").input("Cliente Uno SL")
    at = labelled(at.text_input, "NIF / CIF *").input("B87654321").run()
    at = labelled(at.button, "Emitir factura").click().run()
    invoice = store.invoice_for_sale(sale["id"])
    assert invoice is not None and f"Factura **{invoice['number']}** emitida." in texts(at)
    assert "factura_emitida" in set(store.audit_log()["action"])
    # Now the invoice shows in its tab, ready to download.
    at = app(target, HISTORY, role="encargado", pick=True)
    assert f"Facturada con el número **{invoice['number']}**." in texts(at)
    assert f"Descargar {invoice['number']} (PDF)" in [d.label for d in at.get("download_button")]


def test_staff_cannot_issue_invoices(shop):
    target, store, sale = shop
    at = app(target, f"import ui.pages_history as h\nh._invoice_dialog({sale['id']})", role="empleado")
    labelled(at.text_input, "Nombre o razón social *").input("Cliente Uno SL")
    labelled(at.text_input, "NIF / CIF *").input("B87654321")
    at = labelled(at.button, "Emitir factura").click().run()
    assert "Solo un encargado" in texts(at) and store.invoice_for_sale(sale["id"]) is None


def test_refunding_part_of_a_sale(shop):
    target, store, sale = shop
    at = app(target, f"import ui.pages_history as h\nh._refund_dialog({sale['id']})", role="encargado")
    assert labelled(at.button, "Registrar devolución").disabled  # nothing chosen yet
    at = at.number_input[0].set_value(1).run()
    labelled(at.text_input, "Motivo").input("Talla equivocada")
    at = labelled(at.button, "Registrar devolución").click().run()
    refunds = store.sale_refunds(sale["id"])
    assert len(refunds) == 1 and refunds[0]["total"] == pytest.approx(sale["total"] / 2, abs=0.01)
    assert "registrada" in texts(at) and "Justificante de devolución" in [d.label for d in at.get("download_button")]
    # It is listed in the refunds tab, and the sale can no longer be cancelled outright.
    at = app(target, HISTORY, role="encargado", pick=True)
    assert "Justificante" in [d.label for d in at.get("download_button")]
    assert "Anular la venta completa" not in [b.label for b in at.button]
    assert "Devoluciones:" in texts(at)


def test_staff_cannot_refund(shop):
    target, store, sale = shop
    at = app(target, f"import ui.pages_history as h\nh._refund_dialog({sale['id']})", role="empleado")
    assert "Solo un encargado" in texts(at) and not [b for b in at.button if b.label == "Registrar devolución"]


def test_a_business_that_stopped_paying_can_look_but_not_change_sales(shop):
    target, store, sale = shop
    at = app(target, HISTORY, role="admin", pick=True, readonly=True)
    assert labelled(at.button, "Emitir factura").disabled and labelled(at.button, "Devolver productos").disabled
    assert "Anular la venta completa" not in [b.label for b in at.button]


def test_empty_invoice_and_refund_tabs_explain_how_to_fill_them(shop):
    target, store, sale = shop
    at = app(target, HISTORY, role="admin")
    assert "Aún no has emitido facturas" in texts(at) and "Sin devoluciones" in texts(at)


# ------------------------------------------------------------------ Equipo y seguridad
TEAM = "import ui.pages_team as t\nt.team_page()"


@pytest.fixture
def team(shop):
    target, store, _ = shop
    admin = store.create_user("Ana Admin", "ana", "admin", "Clave-segura-1")
    return target, store, admin


def team_app(target, admin, **kwargs):
    return app(target, TEAM, role="admin", user_id=admin, username="ana", name="Ana Admin", **kwargs)


def test_adding_a_person(team):
    target, store, admin = team
    at = team_app(target, admin)
    labelled(at.text_input, "Nombre").input("Lucía")
    labelled(at.text_input, "Usuario").input("Lucia")
    labelled(at.text_input, "PIN o contraseña").input("482916")
    at = at.button(key="FormSubmitter:new_user-Añadir").click().run()
    users = store.users().set_index("username")
    assert users.loc["lucia", "role"] == "empleado" and "lucia" in texts(at)


def test_a_weak_pin_is_refused(team):
    target, store, admin = team
    at = team_app(target, admin)
    labelled(at.text_input, "Nombre").input("Lucía")
    labelled(at.text_input, "Usuario").input("lucia")
    labelled(at.text_input, "PIN o contraseña").input("123456")
    at = at.button(key="FormSubmitter:new_user-Añadir").click().run()
    assert at.error and "lucia" not in set(store.users()["username"])


def test_changing_someones_role_access_and_pin(team):
    target, store, admin = team
    staff = store.create_user("Luis", "luis", "empleado", "482916")
    at = team_app(target, admin)
    at.selectbox(key="team_user").select(staff).run()
    at.selectbox(key=f"team_role_{staff}").select("encargado")
    at.toggle(key=f"team_active_{staff}").set_value(False)
    at.text_input(key=f"team_secret_{staff}").input("739204")
    at = at.button(key=f"team_save_{staff}").click().run()
    luis = store.user(staff)
    assert luis["role"] == "encargado" and not luis["active"] and "Cambios guardados para Luis." in texts(at)


def test_another_administrators_password_needs_your_own(team):
    target, store, admin = team
    other = store.create_user("Otro Admin", "otro", "admin", "Clave-segura-2")
    at = team_app(target, admin)
    at.selectbox(key="team_user").select(other).run()
    at = at.text_input(key=f"team_secret_{other}").input("Clave-nueva-3").run()
    at.text_input(key=f"team_mine_{other}").input("no-es-la-mia")
    at = at.button(key=f"team_save_{other}").click().run()
    assert "Tu contraseña no es correcta" in texts(at)
    at.text_input(key=f"team_mine_{other}").input("Clave-segura-1")
    at = at.button(key=f"team_save_{other}").click().run()
    assert "Cambios guardados para Otro Admin." in texts(at)
    assert store.confirm_secret(other, "Clave-nueva-3")


def test_removing_someones_two_step_verification(team):
    target, store, admin = team
    staff = store.create_user("Luis", "luis", "encargado", "482916")
    secret = new_totp_secret()
    store.enable_two_factor(staff, secret, totp_code(secret))
    at = team_app(target, admin)
    at = at.selectbox(key="team_user").select(staff).run()
    at = at.button(key=f"team_2fa_{staff}").click().run()
    assert not store.user(staff)["two_factor"] and "quitada a Luis" in texts(at)


def test_recovery_codes_are_shown_once(team):
    target, store, admin = team
    at = team_app(target, admin)
    at = at.button(key="new_codes").click().run()
    shown = max((c.value for c in at.code), key=lambda v: v.count("\n")).split("\n")
    assert store.recovery_codes_left(admin) == len(shown) > 1
    at = at.button(key="codes_saved").click().run()
    assert "codes_saved" not in [b.key for b in at.button]


def test_turning_two_step_verification_on_and_off(team):
    target, store, admin = team
    at = team_app(target, admin)
    secret = at.session_state["totp_pending"]
    labelled(at.text_input, "2. Escribe el código de 6 cifras que muestra la app").input("000000")
    at = at.button(key="FormSubmitter:totp_on-Activar").click().run()
    assert at.error and not store.user(admin)["two_factor"]
    labelled(at.text_input, "2. Escribe el código de 6 cifras que muestra la app").input(totp_code(secret))
    at = at.button(key="FormSubmitter:totp_on-Activar").click().run()
    assert store.user(admin)["two_factor"]
    labelled(at.text_input, "Código actual de la app para desactivarla").input(totp_code(secret))
    at.button(key="FormSubmitter:totp_off-Desactivar").click().run()
    assert not store.user(admin)["two_factor"]


def test_activity_log_views_and_app_errors(team):
    target, store, admin = team
    store.audit("intruso", "acceso_fallido", "")
    try:
        raise RuntimeError("fallo de prueba")
    except RuntimeError as exc:
        ref = store.record_error(exc, page="Vender", username="ana")
    at = team_app(target, admin)
    log = at.dataframe[1].value
    assert {"acceso_fallido", "usuario_creado"} <= set(log["action"])
    at = at.segmented_control(key="audit_view").set_value("Accesos fallidos").run()
    assert set(at.dataframe[1].value["action"]) == {"acceso_fallido"}
    assert "Errores de la app en 7 días: 1" in [e.label for e in at.expander]
    assert ref in set(at.dataframe[-1].value["ref"])


def test_only_the_administrator_opens_the_team_page(team):
    target, store, admin = team
    at = app(target, TEAM, role="encargado")
    assert "Añadir persona" not in texts(at) and not at.text_input


# ------------------------------------------------------------------ Cierre de caja
CASH = "import ui.pages_cash as c\nc.cash_page()"


def test_closing_the_till_reports_the_difference_and_saves_it(shop):
    target, store, sale = shop
    at = app(target, CASH, role="encargado")
    day = clock.today()
    assert labelled(at.button, "Cerrar caja").disabled  # count the drawer first
    at.number_input(key=f"cash_open_{day}").set_value(50.0)
    expected = 50.0 + sale["total"]
    at = at.number_input(key=f"cash_count_{day}").set_value(expected).run()
    assert "La caja cuadra." in texts(at)
    at = at.number_input(key=f"cash_count_{day}").set_value(expected + 5).run()
    assert "Sobran" in texts(at)
    at = at.number_input(key=f"cash_count_{day}").set_value(expected - 5).run()
    assert "Faltan" in texts(at)
    at.text_area(key=f"cash_notes_{day}").input("Retirada para el banco")
    at = labelled(at.button, "Cerrar caja").click().run()
    closing = store.cash_closing(day, None)
    assert closing["difference"] == pytest.approx(-5) and closing["closed_by"] == "Tester"
    assert "cerrada" in texts(at) and "Descargar informe (PDF)" in [d.label for d in at.get("download_button")]
    assert "caja_cerrada" in set(store.audit_log()["action"])


def test_a_sale_after_closing_asks_to_reopen_and_reopening_keeps_the_old_count(shop):
    target, store, sale = shop
    day = clock.today()
    store.close_cash(day, 0, sale["total"], closed_by="Tester")
    df = store.products()
    store.create_sale([{"product_id": int(df.iloc[0]["id"]), "quantity": 1}], "Efectivo", user_name="Tester")
    at = app(target, CASH, role="encargado")
    assert "Ha habido ventas o anulaciones después del cierre" in texts(at)
    at = labelled(at.button, "Reabrir caja").click().run()
    assert store.cash_closing(day, None) is None
    assert "Cierres reabiertos (1)" in [e.label for e in at.expander]
    assert "caja_reabierta" in set(store.audit_log()["action"])


def test_a_day_without_sales(shop):
    target, store, sale = shop
    at = app(target, CASH, role="encargado")
    at = at.date_input(key="cash_day").set_value(clock.today() - timedelta(days=3)).run()
    assert "No hay ventas este día." in texts(at) and "Todavía no has cerrado ninguna caja." in texts(at)


def test_staff_cannot_open_the_cash_page(shop):
    target, store, sale = shop
    at = app(target, CASH, role="empleado")
    assert not [b for b in at.button if b.label == "Cerrar caja"]


def _offline_sales(store) -> bytes:
    pkg = json.loads(store.offline_package(1))
    product = pkg["products"][0]
    when = (clock.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    one = {"id": str(uuid.uuid4()), "number": f"{pkg['series']}000001", "created_at": when, "payment_method": "Efectivo",
           "total": product["price"], "items": [{"product_id": product["id"], "name": product["name"], "quantity": 1,
                                                 "unit_price": product["price"], "tax_rate": product["vat"]}]}
    return json.dumps({"kind": "nirkana-ventas", "version": 1, "key": pkg["key"], "device": pkg["device"],
                       "sales": [one]}).encode()


def test_importing_the_offline_till_sales(shop):
    target, store, sale = shop
    at = app(target, CASH, role="encargado", upload=_offline_sales(store))
    at = labelled(at.button, "Importar").click().run()
    assert "1 ventas importadas" in texts(at)
    at = labelled(at.button, "Importar").click().run()  # the same file again: nothing twice
    assert "0 ventas importadas" in texts(at) and "1 ya estaban" in texts(at)


def test_a_file_that_is_not_from_the_offline_till_is_refused(shop):
    target, store, sale = shop
    at = app(target, CASH, role="encargado", upload=b"no es un archivo de ventas")
    at = labelled(at.button, "Importar").click().run()
    assert at.error
