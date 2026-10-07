"""Screenshots of the app for the README, the web and the ads, rebuilt from scratch with fictitious people.

    python ops/capturas.py postgresql://usuario:clave@localhost:5432/una_base_vacia

The database must be one you can throw away: each business is created in its own schema and dropped at the end.
Needs Playwright with Chromium (E2E_CHROMIUM may point at an installed browser). Writes capturas/*.png for the README
and the ads (outside docs/, so the web does not publish them) and the web versions in docs/assets/img (full .webp,
1200×750 «-c» preview, phone .webp, panel.webp and movil.webp).
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sales_manager"))

from core.db import Store  # noqa: E402

APP = ROOT / "sales_manager" / "app.py"
OUT = ROOT / "capturas"
WEB = ROOT / "docs" / "assets" / "img"
DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}
ADMIN = ("Marta", "marta", "Aurora2026!")
STAFF = ("Lucía", "lucia", "582901")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def business(base_url: str, preset: str, name: str, demo: bool, extra: dict | None = None, empty: bool = False):
    """A business in a schema of its own, served by its own app process. Yields (address, store)."""
    import psycopg

    schema = f"capturas_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(base_url, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    sep = "&" if "?" in base_url else "?"
    url = f"{base_url}{sep}options=-csearch_path%3D{schema}"
    store = Store(url)
    if not empty:
        store.load_preset(preset, with_demo_sales=True)
        store.save_settings({"business_name": name, "demo_mode": "si" if demo else "no", **(extra or {})})
    store.create_user(ADMIN[0], ADMIN[1], "admin", ADMIN[2])
    if not empty:
        store.create_user(STAFF[0], STAFF[1], "empleado", STAFF[2])
    port = _free_port()
    env = {**os.environ, "DATABASE_URL": url, "TZ": "Europe/Madrid"}
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(APP), "--server.port", str(port),
                             "--server.headless", "true", "--client.toolbarMode", "viewer",
                             "--browser.gatherUsageStats", "false"],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    address = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(f"{address}/_stcore/health", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    try:
        yield address, store
    finally:
        proc.terminate()
        proc.wait(timeout=15)
        store.close()
        with psycopg.connect(base_url, autocommit=True) as conn:
            conn.execute(f'DROP SCHEMA "{schema}" CASCADE')


class Camera:
    def __init__(self, playwright, address: str, phone: bool = False):
        executable = os.environ.get("E2E_CHROMIUM")
        self.browser = playwright.chromium.launch(**({"executable_path": executable} if executable else {}))
        viewport = PHONE if phone else DESKTOP
        self.context = self.browser.new_context(viewport=viewport, device_scale_factor=2 if phone else 1,
                                                is_mobile=phone, has_touch=phone, locale="es-ES",
                                                timezone_id="Europe/Madrid")
        self.page = self.context.new_page()
        self.page.set_default_timeout(30_000)
        self.address = address
        self.phone = phone

    def close(self):
        self.browser.close()

    def settle(self, ms: int = 1200):
        try:  # Streamlit keeps a socket open: «idle» may never come
            self.page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:  # noqa: BLE001
            pass
        self.page.wait_for_function("!document.querySelector('[data-testid=stStatusWidget]')", timeout=20_000)
        self.page.wait_for_timeout(ms)
        try:  # notices that fade by themselves («gastos fijos apuntados»…) would cover the picture
            self.page.wait_for_function("!document.querySelector('[data-testid=stToast]')", timeout=8_000)
        except Exception:  # noqa: BLE001
            pass

    def open(self):
        self.page.goto(self.address, wait_until="networkidle")
        self.settle()

    def login(self, who):
        self.open()
        self.page.get_by_role("textbox", name="Usuario").fill(who[1])
        self.page.get_by_role("textbox", name="PIN o contraseña").fill(who[2])
        self.page.get_by_role("button", name="Entrar").click()
        self.page.get_by_test_id("stSidebarNav").wait_for(state="attached")
        self.settle()

    def go(self, title: str):
        if self.phone:  # the menu is folded away on phones
            self.page.get_by_test_id("stExpandSidebarButton").click()
            self.page.wait_for_timeout(600)
        self.page.get_by_test_id("stSidebarNav").get_by_text(title, exact=True).click()
        self.settle(1800)

    def shot(self, name: str, full: bool = False):
        path = OUT / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=full)
        print("  ", path.name)


def _tab(page, name):
    page.get_by_role("tab", name=name).click()
    page.wait_for_timeout(1200)


def restaurant(playwright, address):
    cam = Camera(playwright, address)
    cam.login(ADMIN)
    cam.go("Panel")
    cam.shot("02-panel")
    cam.go("Vender")
    for i in (0, 0, 3, 6):  # two coffees and two dishes
        cam.page.get_by_role("button", name="Añadir").nth(i).click()
        cam.page.wait_for_timeout(700)
    cam.settle()
    cam.shot("03-punto-de-venta")
    cam.page.get_by_role("button", name="Cobrar").first.click()
    cam.page.get_by_text("Venta registrada").first.wait_for()
    cam.page.get_by_role("button", name="Nueva venta").wait_for()
    cam.settle()
    cam.shot("04-venta-registrada")
    cam.page.get_by_role("button", name="Nueva venta").click()
    cam.settle()
    cam.go("Historial")
    cam.shot("05-historial")
    cam.go("Carta")
    cam.shot("06-carta")
    cam.go("Clientes")
    cam.shot("07-clientes")
    cam.go("Automatizaciones")
    cam.shot("08-reposicion")
    _tab(cam.page, "Seguimiento de clientes")
    cam.shot("09-seguimiento-clientes")
    cam.go("Configuración")
    cam.shot("10-configuracion")
    backup = cam.page.get_by_text("Copia de seguridad", exact=True).first
    backup.scroll_into_view_if_needed()
    cam.page.mouse.wheel(0, 300)
    cam.settle()
    cam.shot("14-copia-de-seguridad")
    cam.shot("15-base-de-datos-nube")
    cam.go("Equipo y seguridad")
    cam.shot("22-equipo-y-seguridad")
    cam.go("Cocina")
    cam.shot("24-cocina", full=True)
    cam.go("Promociones")
    cam.shot("26-promociones", full=True)
    cam.go("Compras")
    cam.shot("27-compras", full=True)
    cam.go("Gastos y beneficio")
    cam.shot("28-gastos-y-beneficio", full=True)
    cam.go("Alertas y análisis")
    cam.shot("29-alertas", full=True)
    _tab(cam.page, "Análisis ABC")
    cam.shot("30-analisis-abc")
    _tab(cam.page, "Precios")
    cam.shot("31-precios")
    _tab(cam.page, "Informe semanal")
    cam.shot("32-informe-semanal", full=True)
    cam.close()

    cam = Camera(playwright, address)
    cam.login(STAFF)
    cam.go("Mesas")
    cam.shot("23-mesas", full=True)
    cam.page.get_by_role("button", name="Ver comanda").first.click()
    cam.settle()
    cam.page.get_by_role("button", name="Cobrar").first.click()
    cam.settle()
    cam.page.get_by_text("Por productos").click()
    cam.settle()
    cam.shot("25-cobro-comanda", full=True)
    cam.close()

    phone = Camera(playwright, address, phone=True)
    phone.open()
    phone.shot("13-movil-acceso")
    phone.shot("21-acceso-equipo")
    phone.login(ADMIN)
    phone.shot("11-movil-panel")
    phone.close()
    phone = Camera(playwright, address, phone=True)
    phone.login(STAFF)
    phone.go("Vender")
    phone.shot("12-movil-vender")
    phone.close()


def freelance_day(store):
    """Today's diary and till for the freelance business (the demo data covers the past)."""
    from core import clock

    services = store.products()
    today = clock.now().replace(minute=0, second=0, microsecond=0)
    customers = store.customers()
    plan = [(9, 0, "Lucía Fernández"), (11, 1, "Pablo Navarro"), (16, 2, "Distribuciones Norte S.L.")]
    for hour, i, who in plan:
        match = customers[customers["name"] == who]
        store.create_appointment(today.replace(hour=hour), 60, product_id=int(services.iloc[i % len(services)]["id"]),
                                 customer_id=int(match.iloc[0]["id"]) if len(match) else None,
                                 customer_name="" if len(match) else who, created_by=ADMIN[0])
    for i, method in ((0, "Tarjeta"), (1, "Transferencia")):
        store.create_sale([{"product_id": int(services.iloc[i]["id"]), "quantity": 1}], method,
                          when=today.replace(hour=10 + 2 * i), user_name=ADMIN[0])


def freelance(playwright, address):
    cam = Camera(playwright, address)
    cam.login(ADMIN)
    cam.go("Panel")
    cam.shot("17-demo-autonomo")
    cam.go("Agenda")
    cam.shot("18-agenda")
    cam.go("Caja")
    cam.shot("19-cierre-de-caja")
    cam.go("Historial")
    cam.page.locator("[data-testid=stDataFrame] .dvn-scroller").first.click(position={"x": 18, "y": 54})  # 1st row
    cam.settle()
    cam.page.get_by_role("button", name="Emitir factura").first.click()
    cam.page.get_by_role("dialog").wait_for()
    cam.settle()
    cam.shot("20-emitir-factura")
    cam.close()

    phone = Camera(playwright, address, phone=True)
    phone.login(ADMIN)
    phone.page.get_by_test_id("stExpandSidebarButton").click()
    phone.page.wait_for_timeout(600)
    phone.page.get_by_role("button", name="Cambiar de negocio").click()
    phone.page.get_by_role("dialog").wait_for()
    phone.settle()
    phone.shot("16-movil-cambiar-negocio")
    phone.close()


def welcome(playwright, address):
    cam = Camera(playwright, address)
    cam.open()  # a business with no catalogue yet: after signing in comes the set-up assistant, no menu
    cam.page.get_by_role("textbox", name="Usuario").fill(ADMIN[1])
    cam.page.get_by_role("textbox", name="PIN o contraseña").fill(ADMIN[2])
    cam.page.get_by_role("button", name="Entrar").click()
    cam.page.get_by_text("Paso 1 de 3").first.wait_for()
    cam.page.get_by_role("textbox", name="Nombre del negocio *").fill("Café Aurora")
    cam.page.get_by_text("Bienvenido a NirKanA").click()  # leave the field: no «Press Enter» hint in the picture
    cam.page.mouse.move(5, 5)
    cam.settle(600)
    cam.shot("01-bienvenida")
    cam.close()


def web_versions():
    """What docs/index.html shows: the same pictures, sized for the web."""
    from PIL import Image

    shots = WEB / "shots"
    for png in sorted(OUT.glob("*.png")):
        name = png.stem.split("-", 1)[1]
        image = Image.open(png).convert("RGB")
        if image.width == PHONE["width"] * 2:  # phone pictures: half size
            if (shots / f"{name}.webp").exists():
                image.resize((PHONE["width"], image.height // 2), Image.LANCZOS).save(shots / f"{name}.webp",
                                                                                       quality=82)
            continue
        if (shots / f"{name}.webp").exists():
            image.save(shots / f"{name}.webp", quality=82)
        if (shots / f"{name}-c.webp").exists():
            image.crop((0, 0, DESKTOP["width"], DESKTOP["height"])).resize((1200, 750), Image.LANCZOS).save(
                shots / f"{name}-c.webp", quality=80)
    panel = Image.open(OUT / "02-panel.png").convert("RGB")
    panel.crop((330, 20, 1430, 745)).save(WEB / "panel.webp", quality=82)
    share = Image.new("RGB", (1200, 630), (11, 27, 51))  # og:image for links shared in WhatsApp, Facebook…
    small = panel.crop((330, 20, 1430, 745))
    small.thumbnail((1120, 550))
    share.paste(small, ((1200 - small.width) // 2, (630 - small.height) // 2))
    share.save(WEB / "og.jpg", quality=85, optimize=True, progressive=True)
    phone = Image.open(OUT / "11-movil-panel.png").convert("RGB")
    phone.resize((360, round(phone.height * 360 / phone.width)), Image.LANCZOS).save(WEB / "movil.webp", quality=82)


def main():
    if len(sys.argv) != 2 or not sys.argv[1].startswith(("postgresql://", "postgres://")):
        sys.exit(__doc__)
    from playwright.sync_api import sync_playwright

    base_url = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    fiscal = {"tax_id": "B12345674", "address": "Calle Mayor 1, 28013 Madrid", "email": "hola@cafeaurora.es"}
    only = os.environ.get("CAPTURAS_SOLO", "")  # e.g. «autonomo» to redo one part
    with sync_playwright() as playwright:
        if only in ("", "restaurante"):
            print("Café Aurora (restaurante)")
            with business(base_url, "restaurant", "Café Aurora", demo=False, extra=fiscal) as (address, _):
                restaurant(playwright, address)
        if only in ("", "autonomo"):
            print("Ana García · Consultoría (autónomo, datos de ejemplo)")
            with business(base_url, "services", "Ana García · Consultoría", demo=True,
                          extra={"tax_id": "12345678Z", "email": "ana@consultoria.es"}) as (address, store):
                freelance_day(store)
                freelance(playwright, address)
        if only in ("", "bienvenida"):
            print("Primera configuración")
            with business(base_url, "retail", "", demo=False, empty=True) as (address, _):
                welcome(playwright, address)
    web_versions()
    print("Listo.")


if __name__ == "__main__":
    main()
