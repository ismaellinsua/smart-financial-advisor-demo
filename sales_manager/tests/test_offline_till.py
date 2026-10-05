"""The offline till in a real browser at phone size: load the catalogue, sell, lose the connection, reload, keep
selling, and import the exported sales into the app with the same totals. Needs Playwright with Chromium."""

import functools
import http.server
import json
import os
import threading
from pathlib import Path

import pytest

from core.db import Store

playwright = pytest.importorskip("playwright.sync_api")
DOCS = Path(__file__).resolve().parent.parent.parent / "docs"


@pytest.fixture(scope="module")
def site():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(DOCS))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://localhost:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def browser_page():
    with playwright.sync_playwright() as p:
        executable = os.environ.get("E2E_CHROMIUM")
        try:
            browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        except Exception as exc:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"Chromium not available: {exc}")
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                                      accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(15_000)
        yield context, page
        browser.close()


def test_sell_offline_and_import_into_the_app(site, browser_page, tmp_path):
    context, page = browser_page
    store = Store(str(tmp_path / "shop.db"))
    store.load_preset("retail", with_demo_sales=False)
    store.save_settings({"business_name": "Tienda Sol", "tax_id": "B12345678", "demo_mode": "no"})
    package = store.offline_package(1)
    products = json.loads(package)["products"]

    page.goto(f"{site}/caja/", wait_until="networkidle")
    page.get_by_text("Cargar archivo de catálogo").wait_for()
    page.set_input_files("#package-file", files=[{"name": "catalogo-caja1.json", "mimeType": "application/json",
                                                  "buffer": package}])
    page.get_by_text("Tienda Sol").wait_for()
    page.wait_for_function("navigator.serviceWorker.controller !== null || navigator.serviceWorker.ready")
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")

    page.get_by_label(f"Añadir {products[0]['name']}").click()
    page.get_by_label(f"Añadir {products[0]['name']}").click()
    page.get_by_label(f"Añadir {products[1]['name']}").click()
    page.get_by_role("radio", name="Efectivo").click()
    page.locator("#charge").click()
    page.locator("#ticket").get_by_text("VTA-SC1-000001").wait_for()
    page.get_by_role("button", name="Nueva venta").click()

    # No connection: the installed till still opens and keeps the pending sale.
    context.set_offline(True)
    page.reload(wait_until="load")
    page.locator("#net.off").wait_for()
    page.get_by_text("1 por enviar").wait_for()
    page.get_by_label(f"Añadir {products[2]['name']}").click()
    page.get_by_role("radio", name="Tarjeta").click()
    box = page.locator("#charge").bounding_box()
    assert box["height"] >= 44
    page.locator("#charge").click()
    page.locator("#ticket").get_by_text("VTA-SC1-000002").wait_for()
    page.get_by_role("button", name="Nueva venta").click()

    page.get_by_role("button", name="2 por enviar").click()
    with page.expect_download() as download:
        page.get_by_role("button", name="Guardar archivo de ventas").click()
    exported = Path(download.value.path()).read_bytes()

    result = store.import_offline_sales(exported, "Marta")
    expected = round(products[0]["price"] * 2 + products[1]["price"] + products[2]["price"], 2)
    assert (result["imported"], result["rejected"]) == (2, 0) and result["total"] == pytest.approx(expected)

    page.once("dialog", lambda d: d.accept())
    page.get_by_role("button", name="Ya las importé").click()
    page.get_by_text("No hay ventas pendientes").wait_for()
    store.close()
