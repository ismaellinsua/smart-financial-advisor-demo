"""Anuncios 3D de NirKanA: página interactiva, imágenes PNG y vídeos MP4.

Uso:  python marketing/anuncios/tresd.py            (todos)
      python marketing/anuncios/tresd.py general    (solo uno)

La escena 3D está en 3d/fuente/escena.js. Si la cambias, vuelve a compilarla con:
  npm i three@0.186.1 esbuild && npx esbuild 3d/fuente/escena.js --bundle --minify --format=iife --outfile=3d/nirkana3d.js
"""
import base64
import io
import json
import os
import subprocess
import sys
from html import escape
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from generar import CONTACTO, LLAMADA

AQUI = Path(__file__).resolve().parent
CAPTURAS = AQUI.parents[1] / "docs" / "screenshots"
DIR = AQUI / "3d"
FPS, DURACION, MOMENTO_FOTO = 30, 12.0, 7.0

IMAGENES = {"feed": (1080, 1350), "historia": (1080, 1920), "horizontal": (1200, 628)}
VIDEOS = {"reel": (1080, 1920), "feed": (1080, 1350)}

ANUNCIOS = {
    "general": dict(etiqueta="Gestor de ventas para tu negocio", titulo="Vende más.", titulo2="Controla todo.",
                    pantalla="02-panel.png", movil="11-movil-panel.png",
                    tarjetas=[["Mesa 4 cobrada · 86,40 €", "verde"], ["Solomillo se agota en 1 día", "rojo"],
                              ["La caja cuadra", "turquesa"], ["Informe del lunes listo", "azul"]]),
    "restaurante": dict(etiqueta="Para restaurantes y cafeterías", titulo="Tu sala y tu cocina,", titulo2="en el móvil.",
                        pantalla="23-mesas.png", movil="12-movil-vender.png",
                        tarjetas=[["Mesa 2 · platos listos", "verde"], ["Nueva comanda en cocina", "azul"],
                                  ["Happy hour activa", "turquesa"], ["Terraza 3 · 81,07 €", "verde"]]),
    "tienda": dict(etiqueta="Para tiendas y comercios", titulo="Que no se te agote", titulo2="lo que más vendes.",
                   pantalla="29-alertas.png", movil="12-movil-vender.png",
                   tarjetas=[["Stock bajo en 3 productos", "rojo"], ["Pedido al proveedor enviado", "azul"],
                             ["Stock actualizado", "verde"], ["+40 puntos para Lucía", "turquesa"]]),
    "autonomo": dict(etiqueta="Para autónomos y servicios", titulo="Tu agenda y tus facturas,", titulo2="sin papeles.",
                     pantalla="18-agenda.png", movil="11-movil-panel.png",
                     tarjetas=[["Cita de las 10:00 confirmada", "azul"], ["Factura FAC-0001 emitida", "verde"],
                               ["Cobrado: 240,79 €", "verde"], ["Mañana tienes 3 citas", "turquesa"]]),
}

CSS = """
@font-face { font-family: Jakarta; src: url("data:font/woff2;base64,{FUENTE}") format("woff2"); font-weight: 200 800; }
* { box-sizing: border-box; margin: 0; }
html, body { height: 100%; overflow: hidden; }
body { font-family: Jakarta, system-ui, sans-serif; color: #fff; background: #0B1B33; position: relative;
  --u: min(calc(100vw / 1080), calc(100vh / 1150)); }
.fondo { position: fixed; inset: 0;
  background: radial-gradient(120% 70% at 85% 0%, #2A3F8F 0%, transparent 60%),
              radial-gradient(90% 60% at 0% 100%, rgba(20,184,166,.3) 0%, transparent 60%),
              linear-gradient(160deg, #0B1B33, #13265A); }
#lienzo { position: fixed; inset: 0; width: 100%; height: 100%; display: block; touch-action: none; }
.capa { position: fixed; inset: 0; display: flex; flex-direction: column; justify-content: space-between;
  padding: calc(84 * var(--u)) calc(76 * var(--u)) calc(90 * var(--u)); pointer-events: none; }
.arriba { display: flex; flex-direction: column; gap: calc(28 * var(--u)); }
.marca { display: flex; align-items: center; gap: calc(18 * var(--u)); font-size: calc(42 * var(--u)); font-weight: 800; }
.logo { display: grid; place-items: center; width: calc(66 * var(--u)); height: calc(66 * var(--u)); border-radius: 26%;
  font-size: calc(36 * var(--u)); background: linear-gradient(135deg, #3B5BFD, #6D4BFF 55%, #14B8A6);
  box-shadow: 0 10px 30px -8px rgba(59,91,253,.9); }
.etiqueta { align-self: flex-start; display: flex; align-items: center; gap: calc(12 * var(--u)); font-weight: 600;
  font-size: calc(28 * var(--u)); color: #CFE0FF; border: 1.5px solid rgba(142,162,255,.45); background: rgba(59,91,253,.16);
  border-radius: 999px; padding: calc(12 * var(--u)) calc(24 * var(--u)); }
.etiqueta i { width: calc(12 * var(--u)); height: calc(12 * var(--u)); border-radius: 50%; background: #14B8A6;
  box-shadow: 0 0 0 calc(6 * var(--u)) rgba(20,184,166,.25); }
h1 { font-size: calc(92 * var(--u)); font-weight: 800; letter-spacing: -.03em; line-height: 1.04; }
h1 span { display: block; background: linear-gradient(90deg, #8EA2FF, #5EEAD4); -webkit-background-clip: text; color: transparent; }
.abajo { display: flex; align-items: center; gap: calc(26 * var(--u)); flex-wrap: wrap; }
.boton { pointer-events: auto; white-space: nowrap; font-size: calc(36 * var(--u)); font-weight: 800; color: #fff; text-decoration: none;
  border-radius: 999px; padding: calc(26 * var(--u)) calc(48 * var(--u));
  background: linear-gradient(135deg, #3B5BFD, #6D4BFF 55%, #14B8A6); box-shadow: 0 18px 44px -14px rgba(59,91,253,1); }
.nota { font-size: calc(28 * var(--u)); color: #B9C4DD; font-weight: 500; }
.ap { animation: sube .8s cubic-bezier(.2,.8,.2,1) var(--d, 0s) both; }
@keyframes sube { from { opacity: 0; transform: translateY(40px); } to { opacity: 1; transform: none; } }
.late { animation: sube .8s cubic-bezier(.2,.8,.2,1) 3.6s both, late 1.4s ease-in-out 4.6s infinite; }
@keyframes late { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
.pista { position: fixed; right: 14px; top: 14px; font-size: 14px; color: #CFE0FF;
  background: rgba(11,27,51,.6); border: 1px solid rgba(142,162,255,.35); border-radius: 999px; padding: 8px 16px;
  pointer-events: none; transition: opacity .4s; animation: sube .6s 4s both; }
body.captura .pista { display: none; }
body.tocado .pista { animation: none; opacity: 0; }
@media (min-aspect-ratio: 13/10) {
  body { --u: calc(100vh / 760); }
  .capa { right: auto; width: 48%; padding: calc(64 * var(--u)); }
  h1 { font-size: calc(78 * var(--u)); }
}
"""

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NirKanA · {etiqueta}</title>
<style>{css}</style></head>
<body>
<div class="fondo"></div>
<canvas id="lienzo" aria-label="Portátil y móvil con la app NirKanA en 3D. Arrástralo para girarlo."></canvas>
<div class="capa">
  <div class="arriba">
    <div class="marca ap" style="--d:.1s"><span class="logo">N</span>NirKanA</div>
    <p class="etiqueta ap" style="--d:.3s"><i></i>{etiqueta}</p>
    <h1 class="ap" style="--d:.5s">{titulo}<span>{titulo2}</span></h1>
  </div>
  <div class="abajo">
    <span class="boton late">{llamada} →</span>
    <span class="nota ap" style="--d:4s">{nota}</span>
  </div>
</div>
<p class="pista">↻ Arrastra para girar</p>
<script>
if (location.search.includes("captura")) document.body.classList.add("captura");
window.NIRKANA = {cfg};
</script>
<script>{js}</script>
</body></html>
"""


def jpg(imagen):
    buf = io.BytesIO()
    imagen.save(buf, "JPEG", quality=86)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def pagina(ad):
    """Un solo HTML con todo dentro (imágenes, fuente y código): funciona sin internet y se envía como un archivo."""
    pantalla = jpg(Image.open(CAPTURAS / ad["pantalla"]).convert("RGB").crop((0, 0, 1440, 900)))
    movil = jpg(Image.open(CAPTURAS / ad["movil"]).convert("RGB"))
    cfg = json.dumps({"pantalla": pantalla, "movil": movil, "tarjetas": ad["tarjetas"]}, ensure_ascii=False)
    fuente = base64.b64encode((AQUI / "fuentes" / "PlusJakartaSans.woff2").read_bytes()).decode()
    js = (DIR / "nirkana3d.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    nota = CONTACTO or "Demo de 20 minutos, sin compromiso"
    return PAGINA.format(css=CSS.replace("{FUENTE}", fuente), etiqueta=escape(ad["etiqueta"]), titulo=escape(ad["titulo"]),
                         titulo2=escape(ad["titulo2"]), llamada=escape(LLAMADA), nota=escape(nota), cfg=cfg, js=js)


def abrir(nav, html, w, h):
    pag = nav.new_page(viewport={"width": w, "height": h})
    pag.goto(html.as_uri() + "?captura")
    pag.wait_for_function("window.listo !== undefined")
    pag.evaluate("window.listo")
    pag.evaluate("document.fonts.ready")
    pag.evaluate("document.getAnimations().forEach((a) => a.pause())")
    return pag


def fotograma(pag, t):
    pag.evaluate("(t) => { document.getAnimations().forEach((a) => { a.currentTime = t * 1000; }); window.dibujar(t); }", t)


def main():
    elegidos = sys.argv[1:] or list(ANUNCIOS)
    (DIR / "imagenes").mkdir(parents=True, exist_ok=True)
    (DIR / "video").mkdir(exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None,
                                args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for clave in elegidos:
            html = DIR / f"{clave}.html"
            html.write_text(pagina(ANUNCIOS[clave]), encoding="utf-8")
            print(f"✓ 3d/{html.name}  (interactivo)")
            for formato, (w, h) in IMAGENES.items():
                pag = abrir(nav, html, w, h)
                fotograma(pag, MOMENTO_FOTO)
                pag.screenshot(path=str(DIR / "imagenes" / f"{clave}-{formato}.png"))
                pag.close()
                print(f"✓ 3d/imagenes/{clave}-{formato}.png")
            for formato, (w, h) in VIDEOS.items():
                pag = abrir(nav, html, w, h)
                mp4 = DIR / "video" / f"{clave}-{formato}.mp4"
                ff = subprocess.Popen(
                    ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
                     "-movflags", "+faststart", str(mp4)], stdin=subprocess.PIPE)
                for f in range(round(DURACION * FPS)):
                    fotograma(pag, f / FPS)
                    ff.stdin.write(pag.screenshot(type="jpeg", quality=92))
                ff.stdin.close()
                if ff.wait() != 0:
                    raise RuntimeError(f"ffmpeg falló con {mp4.name}")
                pag.close()
                print(f"✓ 3d/video/{mp4.name}")
        nav.close()


if __name__ == "__main__":
    main()
