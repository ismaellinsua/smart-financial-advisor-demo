"""End to end in a real browser at phone size: sign in, sell from the till, reload. Runs the real app server.

Needs PostgreSQL (TEST_DATABASE_URL) and Playwright with Chromium; skipped otherwise. Set E2E_CHROMIUM to use a
browser binary that is already installed instead of Playwright's own.
"""

import os
import socket
import subprocess
import sys
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
