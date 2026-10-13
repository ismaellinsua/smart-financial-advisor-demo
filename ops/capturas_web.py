"""Screenshots of the real NirKanA app for the website, taken from the public demo (docs/demo/index.html).

    python ops/capturas_web.py            # rewrites docs/assets/img/shots/*.webp, panel.webp, movil.webp and og.jpg

The demo is the real front-end of the app running on invented data, so nothing here can show a screen the product does not
have. Needs Playwright with Chromium (--chromium=RUTA to use another browser, default /opt/pw-browsers/chromium) and Pillow.
Every shot is taken at noon in Madrid on the same day, so a rerun gives the same pictures.
"""

import io
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEMO = (ROOT / "docs" / "demo" / "index.html").as_uri()
IMG = ROOT / "docs" / "assets" / "img"
SHOTS = IMG / "shots"
NOW = datetime.fromisoformat("2026-10-13T10:00:00+00:00")
HIDE_DEMO_BAR = ".demo-bar { display: none !important } :root { --demo-h: 0px !important } #toasts { display: none !important }"


def open_demo(browser, sector, width=1440, height=900, phone=False):
    ctx = browser.new_context(viewport={"width": width, "height": height}, locale="es-ES", timezone_id="Europe/Madrid",
                              device_scale_factor=1, is_mobile=phone, has_touch=phone)
    ctx.clock.set_fixed_time(NOW)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{DEMO}?negocio={sector}&rapido")
    pg.wait_for_selector(".brand", state="attached", timeout=20000)
    pg.add_style_tag(content=HIDE_DEMO_BAR)
    pg.wait_for_timeout(400)
    pg.errors = errors
    return pg


def go(pg, route):
    pg.evaluate(f"location.hash = '#/{route}'")
    pg.wait_for_timeout(900)
    pg.evaluate("window.scrollTo(0, 0)")


def tiles(pg, count):
    items = pg.locator(".tile:not([disabled])")
    expect(items.first).to_be_visible()
    for i in range(count):
        items.nth(i).click()
    pg.wait_for_timeout(500)


def modal_shot_ready(pg):
    pg.wait_for_selector(".modal", timeout=5000)
    pg.wait_for_timeout(400)


def save(png: bytes, name: str, size=(1440, 900), compact=(1200, 750), directory=SHOTS):
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if im.size != size:
        im = im.resize(size, Image.LANCZOS)
    directory.mkdir(parents=True, exist_ok=True)
    im.save(directory / f"{name}.webp", "WEBP", quality=82, method=6)
    if compact:
        im.resize(compact, Image.LANCZOS).save(directory / f"{name}-c.webp", "WEBP", quality=82, method=6)
    print(f"  {name}")


def desktop(browser):
    # ---- a shop
    pg = open_demo(browser, "tienda")
    go(pg, "vender")
    tiles(pg, 3)
    save(pg.screenshot(), "vender")
    go(pg, "resumen")
    save(pg.screenshot(), "resumen")
    pg.locator("h2:has-text('Reposición')").first.scroll_into_view_if_needed()
    pg.evaluate("window.scrollBy(0, -80)")
    pg.wait_for_timeout(300)
    save(pg.screenshot(), "reposicion")
    for route, name in (("compras", "compras"), ("caja", "caja"), ("ventas", "ventas"), ("resultados", "resultados"),
                        ("equipo", "equipo"), ("promociones", "promociones"), ("productos", "productos")):
        go(pg, route)
        save(pg.screenshot(), name)
    go(pg, "ventas")
    pg.locator(".list-item").first.click()
    modal_shot_ready(pg)
    pg.click(".modal button:has-text('Hacer factura')")
    pg.locator(".modal label.field", has_text="Nombre o razón social").first.locator("input").fill("Talleres Norte S.L.")
    pg.locator(".modal label.field", has_text="NIF/CIF").first.locator("input").fill("B00000000")
    pg.locator(".modal-foot").last.locator("button:has-text('Emitir factura')").last.click()
    expect(pg.locator(".modal").last).to_contain_text("F-")
    modal_shot_ready(pg)
    save(pg.screenshot(), "factura")
    assert not pg.errors, pg.errors
    pg.context.close()

    # ---- a restaurant
    pg = open_demo(browser, "hosteleria")
    go(pg, "mesas")
    save(pg.screenshot(), "mesas")
    go(pg, "cocina")
    save(pg.screenshot(), "cocina")
    go(pg, "mesas")
    pg.locator(".table-card.busy").first.click()
    pg.wait_for_selector(".pos.order")
    pg.wait_for_timeout(500)
    pg.click("button:has-text('Cobrar mesa')")
    modal_shot_ready(pg)
    save(pg.screenshot(), "cobro-mesa")
    pg.keyboard.press("Escape")
    assert not pg.errors, pg.errors
    pg.context.close()

    # ---- a service business
    pg = open_demo(browser, "servicios")
    go(pg, "agenda")
    save(pg.screenshot(), "agenda")
    go(pg, "clientes")
    save(pg.screenshot(), "clientes")
    go(pg, "clientes")
    pg.locator(".list-item").first.click()
    modal_shot_ready(pg)
    save(pg.screenshot(), "ficha-cliente")
    assert not pg.errors, pg.errors
    pg.context.close()

    # ---- the hero pictures
    pg = open_demo(browser, "hosteleria", 1100, 725)
    go(pg, "resumen")
    save(pg.screenshot(), "panel", size=(1100, 725), compact=None, directory=IMG)
    og = pg.screenshot(clip={"x": 0, "y": 0, "width": 1100, "height": 580})
    pg.context.close()
    # social card: the dashboard on the site's navy
    card = Image.new("RGB", (1200, 630), (11, 27, 51))
    shot = Image.open(io.BytesIO(og)).convert("RGB")
    shot = shot.resize((920, int(920 * shot.height / shot.width)), Image.LANCZOS)
    card.paste(shot, (140, 50))
    card.save(IMG / "og.jpg", "JPEG", quality=86, optimize=True)
    print("  og")


def phone(browser):
    pg = open_demo(browser, "tienda", 390, 844, phone=True)
    go(pg, "vender")
    tiles(pg, 2)
    save(pg.screenshot(), "movil-vender", size=(390, 844), compact=None)
    go(pg, "resumen")
    save(pg.screenshot(), "movil-resumen", size=(390, 844), compact=None)
    go(pg, "caja")
    save(pg.screenshot(), "movil-caja", size=(390, 844), compact=None)
    pg.context.close()
    pg = open_demo(browser, "tienda", 360, 779, phone=True)
    go(pg, "vender")
    tiles(pg, 2)
    save(pg.screenshot(), "movil", size=(360, 779), compact=None, directory=IMG)
    pg.context.close()


def main():
    chromium = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--chromium=")), "/opt/pw-browsers/chromium")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium or None)
        desktop(browser)
        phone(browser)
        browser.close()


if __name__ == "__main__":
    main()
