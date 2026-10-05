"""End to end in a real browser at phone size: sign in, sell from the till, reload. Runs the real app server.

Needs PostgreSQL (TEST_DATABASE_URL) and Playwright with Chromium; skipped otherwise. Set E2E_CHROMIUM to use a
browser binary that is already installed instead of Playwright's own.
"""

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from conftest import PG_URL, Targets
from core.db import Store

playwright = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set")

APP = Path(__file__).resolve().parent.parent / "app.py"
PHONE = {"width": 390, "height": 844}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    targets = Targets("postgres", tmp_path_factory.mktemp("e2e"))
    url = targets.new()
    store = Store(url)
    store.load_preset("retail", with_demo_sales=False)
    store.save_settings({"business_name": "Tienda Prueba", "tax_id": "B12345678", "address": "Calle Mayor 1, Madrid"})
    store.create_user("Marta", "marta", "empleado", "583920")
    store.close()
    port = _free_port()
    env = {**os.environ, "DATABASE_URL": url, "TZ": "UTC"}
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(APP), "--server.port", str(port),
                             "--server.headless", "true", "--browser.gatherUsageStats", "false"],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{base}/_stcore/health", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("the app server did not start")
    yield base
    proc.terminate()
    proc.wait(timeout=10)
    targets.cleanup()


@pytest.fixture
def phone(server):
    with playwright.sync_playwright() as p:
        executable = os.environ.get("E2E_CHROMIUM")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        page = browser.new_context(viewport=PHONE, is_mobile=True, has_touch=True).new_page()
        page.set_default_timeout(20_000)
        yield page
        browser.close()


def _sign_in(page, base):
    page.goto(base, wait_until="networkidle")
    page.get_by_label("Usuario", exact=True).fill("marta")
    page.get_by_label("PIN o contraseña").fill("583920")
    page.get_by_role("button", name="Entrar").click()
    page.get_by_text("Punto de venta").first.wait_for()


def test_staff_sells_from_a_phone_and_a_reload_keeps_the_ticket(server, phone):
    _sign_in(phone, server)
    for i in (0, 0, 1):
        phone.get_by_role("button", name="Añadir").nth(i).click()
        phone.wait_for_timeout(700)
    to_ticket = phone.get_by_role("button", name="Ver ticket y cobrar (3)")
    to_ticket.wait_for()

    phone.reload(wait_until="networkidle")  # the session and the ticket survive a reload
    phone.get_by_role("button", name="Ver ticket y cobrar (3)").click()

    charge = phone.get_by_role("button", name="Cobrar").first
    charge.wait_for(state="visible")
    phone.wait_for_timeout(500)  # let the layout settle before measuring
    box = charge.bounding_box()
    assert box["y"] + box["height"] <= PHONE["height"], "Cobrar must be on screen without scrolling"
    assert box["height"] >= 44
    charge.click()
    phone.get_by_text("Venta registrada").wait_for()
    # The dialog fills in progressively (ticket preview first): wait for its last button instead of checking at once.
    phone.get_by_role("button", name="Nueva venta").wait_for(state="visible")


@pytest.fixture(scope="module")
def multi_server(tmp_path_factory):
    """The app in multi-business mode over a fresh database, as the operator would run it."""
    import uuid
    from urllib.parse import urlsplit, urlunsplit

    import psycopg

    name = f"nk_e2e_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    url = urlunsplit(urlsplit(PG_URL)._replace(path=f"/{name}"))
    port = _free_port()
    env = {**os.environ, "DATABASE_URL": url, "TZ": "UTC", "MULTI_TENANT": "true",
           "OPERATOR_PASSWORD": "operador-de-prueba-2026"}
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(APP), "--server.port", str(port),
                             "--server.headless", "true", "--browser.gatherUsageStats", "false"],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{base}/_stcore/health", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    yield base
    proc.terminate()
    proc.wait(timeout=10)
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def _operator(page, base):
    """Open the operator panel, signing in when needed (visiting a business in the same tab ends that session)."""
    page.goto(f"{base}/?operador", wait_until="networkidle")
    if page.get_by_role("textbox", name="Contraseña de operador").count():
        page.get_by_role("textbox", name="Contraseña de operador").fill("operador-de-prueba-2026")
        page.get_by_role("button", name="Entrar").click()
    page.get_by_text("Dar de alta un negocio").wait_for()


def _create_business(page, base, code, name):
    _operator(page, base)
    page.get_by_role("textbox", name="Código (va en la dirección)").fill(code)
    page.get_by_role("textbox", name="Nombre del negocio").fill(name)
    page.get_by_role("button", name="Crear negocio").click()
    page.get_by_text("Código de instalación:").wait_for()
    return page.locator("code", has_text="Código de instalación:").inner_text().split("Código de instalación:")[1].strip()


def _first_admin(page, base, code, setup, username):
    page.goto(f"{base}/?negocio={code}", wait_until="networkidle")
    page.get_by_text("Crea tu cuenta de administrador").wait_for()
    page.get_by_role("textbox", name="Código de instalación de tu negocio").fill(setup)
    page.get_by_role("textbox", name="Tu nombre").fill(username.title())
    page.get_by_role("textbox", name="Usuario").fill(username)
    page.get_by_role("textbox", name="Contraseña", exact=True).fill("Segura2026!")
    page.get_by_role("textbox", name="Repite la contraseña").fill("Segura2026!")
    page.get_by_role("button", name="Crear administrador").click()
    page.get_by_role("button", name="Ya los he guardado").click()
    page.get_by_text("Paso 1 de 3").wait_for()


def test_operator_creates_businesses_that_stay_apart(multi_server):
    with playwright.sync_playwright() as p:
        executable = os.environ.get("E2E_CHROMIUM")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        page.set_default_timeout(20_000)

        page.goto(multi_server, wait_until="networkidle")
        page.get_by_text("Entra en tu negocio").wait_for()  # no business is listed to visitors

        aurora = _create_business(page, multi_server, "cafe-aurora", "Café Aurora")
        sol = _create_business(page, multi_server, "tienda-sol", "Tienda Sol")
        _first_admin(page, multi_server, "cafe-aurora", aurora, "ana")

        # Same tab, other business: the Café Aurora session must not carry over.
        page.goto(f"{multi_server}/?negocio=tienda-sol", wait_until="networkidle")
        page.get_by_text("Crea tu cuenta de administrador").wait_for()
        page.get_by_role("textbox", name="Código de instalación de tu negocio").fill(aurora)  # the other's code
        page.get_by_role("textbox", name="Tu nombre").fill("Intruso")
        page.get_by_role("textbox", name="Usuario").fill("intruso")
        page.get_by_role("textbox", name="Contraseña", exact=True).fill("Segura2026!")
        page.get_by_role("textbox", name="Repite la contraseña").fill("Segura2026!")
        page.get_by_role("button", name="Crear administrador").click()
        page.get_by_text("no es correcto").wait_for()
        _first_admin(page, multi_server, "tienda-sol", sol, "luis")

        page.goto(f"{multi_server}/?negocio=no-existe", wait_until="networkidle")
        page.get_by_text("No encontramos ese negocio").wait_for()

        # The installed app opens at «/»: it goes back to the last business used on this device.
        page.goto(multi_server, wait_until="networkidle")
        page.wait_for_url("**negocio=tienda-sol**")
        page.get_by_text("Paso 1 de 3").wait_for()

        _operator(page, multi_server)
        page.get_by_role("button", name="Suspender acceso").click()  # the first business: Café Aurora
        page.wait_for_timeout(1500)
        page.goto(f"{multi_server}/?negocio=cafe-aurora", wait_until="networkidle")
        page.get_by_text("está suspendido").wait_for()
        browser.close()


# ------------------------------------------------------------------ charging for the service (fake Stripe)
class _FakeStripe:
    """Just enough of Stripe's API and hosted checkout to walk a subscription end to end."""

    def __init__(self):
        import json
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from urllib.parse import parse_qs, urlsplit

        sessions, fake = {}, self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, body):
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):  # noqa: N802
                form = {k: v[0] for k, v in parse_qs(self.rfile.read(int(self.headers["Content-Length"]))
                                                     .decode()).items()}
                if self.path == "/v1/checkout/sessions":
                    sid = f"cs_test_{len(sessions) + 1}"
                    sessions[sid] = form
                    return self._json({"id": sid, "url": f"{fake.base}/pay/{sid}"})
                if self.path == "/v1/billing_portal/sessions":
                    return self._json({"url": f"{fake.base}/portal"})
                self.send_error(404)

            def do_GET(self):  # noqa: N802
                path = urlsplit(self.path).path
                if path.startswith("/pay/"):  # the customer «pays» and Stripe sends them back
                    sid = path.rsplit("/", 1)[1]
                    self.send_response(303)
                    self.send_header("Location", sessions[sid]["success_url"].replace("{CHECKOUT_SESSION_ID}", sid))
                    return self.end_headers()
                if path.startswith("/v1/checkout/sessions/"):
                    sid = path.rsplit("/", 1)[1]
                    code = sessions[sid]["client_reference_id"]
                    return self._json({"id": sid, "client_reference_id": code, "subscription": fake.sub(code)})
                if path == "/v1/subscriptions":
                    return self._json({"data": [fake.sub("cafe-pago")]})
                self.send_error(404)

            def log_message(self, *args):
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.http.server_address[1]}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    @staticmethod
    def sub(code):
        return {"id": "sub_1", "customer": "cus_1", "status": "active", "cancel_at_period_end": False,
                "current_period_end": int(time.time()) + 30 * 86400, "metadata": {"tenant": code}}


@pytest.fixture(scope="module")
def billing_server():
    import uuid
    from urllib.parse import urlsplit, urlunsplit

    import psycopg

    stripe = _FakeStripe()
    name = f"nk_e2e_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    url = urlunsplit(urlsplit(PG_URL)._replace(path=f"/{name}"))
    port = _free_port()
    env = {**os.environ, "DATABASE_URL": url, "TZ": "UTC", "MULTI_TENANT": "true",
           "OPERATOR_PASSWORD": "operador-de-prueba-2026", "STRIPE_SECRET_KEY": "sk_test_e2e",
           "STRIPE_PRICE_ID": "price_e2e", "STRIPE_API_BASE": f"{stripe.base}/v1"}
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(APP), "--server.port", str(port),
                             "--server.headless", "true", "--browser.gatherUsageStats", "false"],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{base}/_stcore/health", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    yield base, url
    proc.terminate()
    proc.wait(timeout=10)
    stripe.http.shutdown()
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def test_unpaid_business_can_only_look_up_until_it_subscribes(billing_server):
    import psycopg

    from core.tenants import DIRECTORY_SCHEMA, Directory

    base, url = billing_server
    directory = Directory(url)
    setup = directory.create("cafe-pago", "Café Pago", trial_days=0)
    with psycopg.connect(url, autocommit=True) as conn:  # the trial ended three weeks ago, grace days included
        conn.execute(f"UPDATE {DIRECTORY_SCHEMA}.tenants SET trial_ends = '2020-01-01T00:00:00'")

    with playwright.sync_playwright() as p:
        executable = os.environ.get("E2E_CHROMIUM")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.set_default_timeout(20_000)
        _first_admin(page, base, "cafe-pago", setup, "ana")
        store = directory.store("cafe-pago")
        store.load_preset("retail", with_demo_sales=False)
        store.close()

        page.reload(wait_until="networkidle")
        page.get_by_text("puedes consultar y descargar tus datos").first.wait_for()
        nav = page.get_by_test_id("stSidebarNav")
        assert nav.get_by_text("Suscripción").count() and nav.get_by_text("Historial").count()
        assert not nav.get_by_text("Vender").count() and not nav.get_by_text("Configuración").count()
        page.goto(f"{base}/vender?negocio=cafe-pago", wait_until="networkidle")  # typing the address won't do
        page.get_by_text("puedes consultar y descargar tus datos").first.wait_for()
        assert not page.get_by_role("button", name="Cobrar").count()
        page.keyboard.press("Escape")  # Streamlit's «Page not found» notice

        page.get_by_test_id("stSidebarNav").get_by_text("Suscripción").click()
        page.get_by_role("button", name="Suscribirme").click()
        with context.expect_page() as paying:
            page.get_by_role("link", name="Ir al pago seguro de Stripe").click()
        back = paying.value
        back.wait_for_url("**negocio=cafe-pago**")
        back.get_by_text("Tu suscripción está activa").wait_for()
        assert "session_id" not in back.url  # the payment reference does not stay in the address

        tenant = directory.get("cafe-pago")
        assert (tenant["billing_status"], tenant["stripe_customer"]) == ("active", "cus_1")
        back.get_by_test_id("stSidebarNav").get_by_text("Vender").wait_for()
        browser.close()
