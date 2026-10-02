"""Crea los anuncios en vídeo de NirKanA (MP4) y su versión animada en HTML.

Uso:  python marketing/anuncios/video.py            (todos)
      python marketing/anuncios/video.py general    (solo uno)
Necesita Playwright con Chromium y ffmpeg.
"""
import os
import subprocess
import sys
from html import escape
from pathlib import Path

from playwright.sync_api import sync_playwright

from generar import CONTACTO, LLAMADA

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "video"
FPS = 30

FORMATOS = {  # nombre: (ancho, alto, escala del texto, ancho máx. y alto máx. de la captura)
    "reel": (1080, 1920, 1.0, 940, 1000),
    "feed": (1080, 1350, .8, 900, 600),
}

VIDEOS = {
    "general": {
        "gancho": ["¿Llevas tu negocio", "con libreta, Excel", "y calculadora?"],
        "lema": "Tu negocio entero, en una sola app.",
        "escenas": [
            ("Cobra en segundos", "Tarjeta, efectivo, Bizum o pago mixto.", "03-punto-de-venta.png", (360, 40, 1020, 720)),
            ("Cierra la caja en un minuto", "La app sabe cuánto efectivo debería haber.", "19-cierre-de-caja.png", (360, 80, 1020, 820)),
            ("Te avisa antes de que algo falle", "Stock que se agota, cajas que no cuadran…", "29-alertas.png", (360, 70, 1020, 720)),
        ],
    },
    "restaurante": {
        "gancho": ["¿Comandas en papel", "y gritos a cocina?"],
        "lema": "Sala, cocina y caja, conectadas.",
        "escenas": [
            ("Toda la sala de un vistazo", "Varios camareros en la misma mesa.", "23-mesas.png", (360, 80, 1020, 720)),
            ("La cocina lo ve al momento", "Pedidos en orden de llegada, con sus notas.", "24-cocina.png", (360, 80, 1020, 720)),
            ("Happy hour que se aplica solo", "Y 2x1 los días que tú digas.", "26-promociones.png", (360, 80, 1020, 720)),
        ],
    },
    "autonomo": {
        "gancho": ["¿Citas por WhatsApp", "y facturas a mano?"],
        "lema": "Tu agenda y tus cobros, en el móvil.",
        "escenas": [
            ("Tu agenda, sin solapes", "Cada cita con su servicio y su precio.", "18-agenda.png", (360, 70, 1020, 600)),
            ("Factura en PDF al momento", "Con los datos fiscales de tu cliente.", "20-emitir-factura.png", (440, 40, 560, 680)),
            ("Sabes lo que has cobrado", "Por día y por forma de pago.", "19-cierre-de-caja.png", (360, 80, 1020, 820)),
        ],
    },
    "tienda": {
        "gancho": ["¿Te enteras de que algo", "se ha agotado", "cuando ya es tarde?"],
        "lema": "Tu tienda, siempre bajo control.",
        "escenas": [
            ("Vende con el stock al día", "Cada venta descuenta del almacén.", "03-punto-de-venta.png", (360, 40, 1020, 720)),
            ("Te avisa antes de que se agote", "Y te dice qué pedir según lo que vendes.", "29-alertas.png", (360, 70, 1020, 720)),
            ("Pide al proveedor en un clic", "El stock se actualiza solo al recibirlo.", "27-compras.png", (360, 80, 1020, 700)),
        ],
    },
}

# Momentos de cada parte (segundos)
GANCHO, LOGO, ESCENA, FINAL = 3.2, 2.4, 2.8, 3.4

CSS = """
@font-face { font-family: Jakarta; src: url("../fuentes/PlusJakartaSans.woff2") format("woff2"); font-weight: 200 800; }
* { box-sizing: border-box; margin: 0; }
html, body { width: {W}px; height: {H}px; overflow: hidden; }
body { font-family: Jakarta, sans-serif; color: #fff; background: #0B1B33; position: relative; --k: {K}; }
.fondo { position: absolute; inset: -20%;
  background: radial-gradient(40% 30% at 80% 10%, #2A3F8F, transparent 70%),
              radial-gradient(40% 30% at 10% 90%, rgba(20,184,166,.35), transparent 70%),
              linear-gradient(160deg, #0B1B33, #13265A);
  animation: deriva {T}s linear both; }
@keyframes deriva { to { transform: translate(-6%, 4%) rotate(6deg); } }
.puntos { position: absolute; inset: 0; opacity: .45;
  background-image: radial-gradient(rgba(142,162,255,.22) 1.4px, transparent 1.4px); background-size: 34px 34px; }
.progreso { position: absolute; top: 0; left: 0; height: 8px; width: 100%; transform-origin: left;
  background: linear-gradient(90deg, #3B5BFD, #6D4BFF, #14B8A6); animation: prog {T}s linear both; }
@keyframes prog { from { transform: scaleX(0); } to { transform: scaleX(1); } }

.esc { position: absolute; inset: 0; display: flex; flex-direction: column; opacity: 0;
  padding: calc(120px * var(--k)) calc(80px * var(--k)); animation: escena var(--dur) linear var(--ini) both; }
.esc.ultima { animation-name: escena-final; }
@keyframes escena { 0% { opacity: 0; } 8% { opacity: 1; } 90% { opacity: 1; } 100% { opacity: 0; } }
@keyframes escena-final { 0% { opacity: 0; } 10%, 100% { opacity: 1; } }
.ap { opacity: 0; animation: sube .7s cubic-bezier(.2,.8,.2,1) calc(var(--ini) + var(--d, 0s)) both; }
@keyframes sube { from { opacity: 0; transform: translateY(50px); } to { opacity: 1; transform: none; } }
.grad { background: linear-gradient(90deg, #8EA2FF, #5EEAD4); -webkit-background-clip: text; color: transparent; }

.gancho { justify-content: center; }
.gancho h1 { font-size: calc(104px * var(--k)); font-weight: 800; letter-spacing: -.03em; line-height: 1.08; }
.gancho h1 span { display: block; }

.logo-esc { justify-content: center; align-items: center; text-align: center; gap: calc(40px * var(--k)); }
.logo { display: grid; place-items: center; color: #fff; font-weight: 800; border-radius: 26%;
  background: linear-gradient(135deg, #3B5BFD, #6D4BFF 55%, #14B8A6); box-shadow: 0 20px 60px -10px rgba(59,91,253,.9); }
.logo-esc .logo { width: calc(200px * var(--k)); height: calc(200px * var(--k)); font-size: calc(120px * var(--k));
  animation: aparece 1s cubic-bezier(.2,1.4,.3,1) calc(var(--ini) + .1s) both; }
@keyframes aparece { from { opacity: 0; transform: scale(.4) rotate(-20deg); } to { opacity: 1; transform: none; } }
.logo-esc .nombre { font-size: calc(110px * var(--k)); font-weight: 800; letter-spacing: -.03em; }
.logo-esc .lema { font-size: calc(48px * var(--k)); font-weight: 600; color: #B9C4DD; max-width: 18em; line-height: 1.25; }
.anillo { position: absolute; width: calc(560px * var(--k)); height: calc(560px * var(--k)); border-radius: 50%;
  border: 2px solid rgba(142,162,255,.3); left: 50%; top: 50%; margin: calc(-280px * var(--k)) 0 0 calc(-280px * var(--k));
  animation: onda 2.4s ease-out var(--ini) both; }
@keyframes onda { from { transform: scale(.3); opacity: 1; } to { transform: scale(1.8); opacity: 0; } }

.marca { display: flex; align-items: center; gap: 16px; font-size: calc(40px * var(--k)); font-weight: 800; }
.marca .logo { width: calc(60px * var(--k)); height: calc(60px * var(--k)); font-size: calc(34px * var(--k)); }
.num { margin-top: calc(70px * var(--k)); font-size: calc(30px * var(--k)); font-weight: 700; color: #5EEAD4; letter-spacing: .12em; }
.funcion h2 { margin-top: calc(18px * var(--k)); font-size: calc(80px * var(--k)); font-weight: 800; letter-spacing: -.03em; line-height: 1.05; }
.funcion p.sub { margin-top: calc(22px * var(--k)); font-size: calc(40px * var(--k)); font-weight: 500; color: #B9C4DD; line-height: 1.3; }
.zona { flex: 1; display: flex; align-items: center; justify-content: center; perspective: 2200px; }
.disp { border-radius: 22px; overflow: hidden; background: #fff;
  box-shadow: 0 60px 100px -30px rgba(0,0,0,.8), 0 0 0 1.5px rgba(255,255,255,.12);
  animation: entra var(--dur) cubic-bezier(.2,.8,.2,1) var(--ini) both; }
@keyframes entra { 0% { opacity: 0; transform: translateY(160px) rotateX(24deg) scale(.88); }
  30% { opacity: 1; transform: rotateX(4deg) scale(.98); } 100% { opacity: 1; transform: rotateX(0) scale(1.04); } }
.barra { height: 36px; background: #EEF1F7; display: flex; align-items: center; gap: 9px; padding: 0 18px; }
.barra i { width: 12px; height: 12px; border-radius: 50%; background: #FF6B6B; }
.barra i + i { background: #FFC24B; } .barra i + i + i { background: #3DD68C; }
.recorte { position: relative; overflow: hidden; }
.recorte img { position: absolute; max-width: none; }

.final { justify-content: center; align-items: center; text-align: center; gap: calc(44px * var(--k)); }
.final .logo { width: calc(130px * var(--k)); height: calc(130px * var(--k)); font-size: calc(78px * var(--k)); }
.final h2 { font-size: calc(96px * var(--k)); font-weight: 800; letter-spacing: -.03em; line-height: 1.05; }
.boton { display: inline-block; font-size: calc(46px * var(--k)); font-weight: 800; color: #fff; border-radius: 999px;
  padding: calc(34px * var(--k)) calc(64px * var(--k)); background: linear-gradient(135deg, #3B5BFD, #6D4BFF 55%, #14B8A6);
  box-shadow: 0 24px 60px -16px rgba(59,91,253,1); }
.late { animation: late 1.2s ease-in-out calc(var(--ini) + 1s) infinite; }
@keyframes late { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.06); } }
.nota { font-size: calc(36px * var(--k)); color: #9AA6BD; font-weight: 500; }

#otra { position: absolute; right: 24px; bottom: 24px; font: 600 22px Jakarta, sans-serif; color: #fff; cursor: pointer;
  background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.25); border-radius: 999px; padding: 12px 22px; display: none; }
body.vivo #otra { display: block; }
"""

REPETIR = """<script>
// Al abrir el archivo en el navegador, el anuncio se reproduce solo y se puede repetir.
if (!navigator.webdriver) {
  document.body.classList.add("vivo");
  document.getElementById("otra").onclick = () =>
    document.getAnimations().forEach((a) => { a.currentTime = 0; a.play(); });
}
</script>"""


def captura(nombre, recorte, max_w, max_h):
    x, y, w, h = recorte
    escala = min(max_w / w, max_h / h)
    src = f"../../../docs/screenshots/{nombre}"
    return (f'<div class="recorte" style="width:{round(w * escala)}px;height:{round(h * escala)}px">'
            f'<img src="{src}" style="width:{round(1440 * escala)}px;left:{round(-x * escala)}px;top:{round(-y * escala)}px" alt=""></div>')


def pagina(v, formato):
    w, h, k, max_w, max_h = FORMATOS[formato]
    total = GANCHO + LOGO + ESCENA * len(v["escenas"]) + FINAL
    partes, t = [], 0.0

    lineas = "".join(f'<span class="ap{" grad" if i == len(v["gancho"]) - 1 else ""}" style="--d:{.15 + i * .45:.2f}s">'
                     f'{escape(l)}</span>' for i, l in enumerate(v["gancho"]))
    partes.append(f'<section class="esc gancho" style="--ini:{t}s;--dur:{GANCHO}s"><h1>{lineas}</h1></section>')
    t += GANCHO

    partes.append(f'<section class="esc logo-esc" style="--ini:{t}s;--dur:{LOGO}s"><div class="anillo"></div>'
                  f'<div class="logo">N</div><div class="nombre ap" style="--d:.35s">NirKanA</div>'
                  f'<div class="lema ap" style="--d:.7s">{escape(v["lema"])}</div></section>')
    t += LOGO

    n = len(v["escenas"])
    for i, (titulo, sub, img, recorte) in enumerate(v["escenas"], 1):
        partes.append(
            f'<section class="esc funcion" style="--ini:{t:.1f}s;--dur:{ESCENA}s">'
            f'<div class="marca"><span class="logo">N</span>NirKanA</div>'
            f'<div class="num ap" style="--d:.05s">{i:02d} / {n:02d}</div>'
            f'<h2 class="ap" style="--d:.15s">{escape(titulo)}</h2><p class="sub ap" style="--d:.3s">{escape(sub)}</p>'
            f'<div class="zona"><div class="disp"><div class="barra"><i></i><i></i><i></i></div>'
            f'{captura(img, recorte, max_w, max_h)}</div></div></section>')
        t += ESCENA

    nota = escape(CONTACTO) if CONTACTO else "Demo de 20 minutos, sin compromiso"
    partes.append(f'<section class="esc final ultima" style="--ini:{t:.1f}s;--dur:{FINAL}s">'
                  f'<div class="logo ap" style="--d:.05s">N</div>'
                  f'<h2 class="ap" style="--d:.2s">{escape(v["lema"])}</h2>'
                  f'<div class="ap" style="--d:.45s"><span class="boton late">{escape(LLAMADA)} →</span></div>'
                  f'<p class="nota ap" style="--d:.7s">{nota}</p></section>')

    css = CSS.replace("{W}", str(w)).replace("{H}", str(h)).replace("{K}", str(k)).replace("{T}", f"{total:.1f}")
    cuerpo = "".join(partes)
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>NirKanA · anuncio</title>'
            f'<style>{css}</style></head><body><div class="fondo"></div><div class="puntos"></div>{cuerpo}'
            f'<div class="progreso"></div><button id="otra">↻ Ver otra vez</button>{REPETIR}</body></html>'), total


def grabar(nav, html_path, mp4_path, w, h, total):
    pag = nav.new_page(viewport={"width": w, "height": h})
    pag.goto(html_path.as_uri())
    pag.wait_for_load_state("networkidle")
    pag.evaluate("document.fonts.ready")
    pag.evaluate("document.getAnimations().forEach((a) => a.pause())")
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", "-movflags", "+faststart",
         str(mp4_path)], stdin=subprocess.PIPE)
    for f in range(round(total * FPS)):
        pag.evaluate("(t) => document.getAnimations().forEach((a) => { a.currentTime = t; })", f * 1000 / FPS)
        ff.stdin.write(pag.screenshot(type="jpeg", quality=92))
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError(f"ffmpeg falló con {mp4_path.name}")
    pag.close()


def main():
    SALIDA.mkdir(exist_ok=True)
    elegidos = sys.argv[1:] or list(VIDEOS)
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        for clave in elegidos:
            for formato, (w, h, *_ ) in FORMATOS.items():
                html, total = pagina(VIDEOS[clave], formato)
                html_path = SALIDA / f"{clave}-{formato}.html"
                html_path.write_text(html, encoding="utf-8")
                mp4 = SALIDA / f"{clave}-{formato}.mp4"
                grabar(nav, html_path, mp4, w, h, total)
                print(f"✓ video/{mp4.name}  ({total:.1f} s)")
        nav.close()


if __name__ == "__main__":
    main()
