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

from generar import CONTACTO, FORMSPREE_ID, LLAMADA, WEB, WHATSAPP

AQUI = Path(__file__).resolve().parent
CAPTURAS = AQUI.parents[1] / "docs" / "screenshots"
DIR = AQUI / "3d"
FPS, DURACION, MOMENTO_FOTO = 30, 12.0, 7.0

IMAGENES = {"feed": (1080, 1350), "historia": (1080, 1920), "horizontal": (1200, 628)}
VIDEOS = {"reel": (1080, 1920), "feed": (1080, 1350)}

ANUNCIOS = {
    "general": dict(
        etiqueta="Gestor de ventas para tu negocio", titulo="Vende más.", titulo2="Controla todo.",
        texto="Cobros, stock, caja y clientes en una sola app.", tipo="",
        pantalla="02-panel.png", movil="11-movil-panel.png",
        tarjetas=[["Mesa 4 cobrada", "86,40 € · tarjeta", "verde", "€"],
                  ["Solomillo se agota", "Quedan 6 · conviene pedir hoy", "rojo", "!"],
                  ["La caja cuadra", "Cierre de hoy guardado", "turquesa", "✓"],
                  ["Informe semanal listo", "Lunes · en PDF", "azul", "↗"]]),
    "restaurante": dict(
        etiqueta="Para restaurantes y cafeterías", titulo="Tu sala y tu cocina,", titulo2="en el móvil.",
        texto="Los camareros piden desde el móvil y la cocina lo ve al momento.", tipo="Restaurante / cafetería",
        pantalla="23-mesas.png", movil="12-movil-vender.png",
        tarjetas=[["Mesa 2 · platos listos", "Croquetas y ensalada", "verde", "✓"],
                  ["Nueva comanda en cocina", "Terraza 3 · 4 platos", "azul", "+"],
                  ["Happy hour activa", "Bebidas −30 % hasta las 20:00", "turquesa", "%"],
                  ["Terraza 3 cobrada", "81,07 € · pago mixto", "verde", "€"]]),
    "tienda": dict(
        etiqueta="Para tiendas y comercios", titulo="Que no se te agote", titulo2="lo que más vendes.",
        texto="La app vigila tu stock y te avisa antes de que falte un producto.", tipo="Tienda / comercio",
        pantalla="29-alertas.png", movil="12-movil-vender.png",
        tarjetas=[["Stock bajo", "3 productos se agotan pronto", "rojo", "!"],
                  ["Pedido enviado", "Bodegas del Valle · 42,25 €", "azul", "↗"],
                  ["Mercancía recibida", "Stock y costes al día", "verde", "✓"],
                  ["+40 puntos", "Lucía ya tiene 320", "turquesa", "★"]]),
    "autonomo": dict(
        etiqueta="Para autónomos y servicios", titulo="Tu agenda y tus facturas,", titulo2="sin papeles.",
        texto="Organiza tus citas, cobra con un toque y envía la factura en PDF.", tipo="Autónomo / servicios",
        pantalla="18-agenda.png", movil="11-movil-panel.png",
        tarjetas=[["Cita confirmada", "Mañana a las 10:00", "azul", "+"],
                  ["Factura emitida", "FAC-2026-0001 · PDF", "verde", "✓"],
                  ["Cita cobrada", "240,79 € · Bizum", "verde", "€"],
                  ["Agenda de mañana", "3 citas, sin solapes", "turquesa", "≡"]]),
}

CSS = """
@font-face { font-family: Jakarta; src: url("data:font/woff2;base64,{FUENTE}") format("woff2"); font-weight: 200 800; }
* { box-sizing: border-box; margin: 0; }
html, body { height: 100%; overflow: hidden; }
body { font-family: Jakarta, system-ui, sans-serif; color: #fff; background: #0A1628; position: relative;
  --u: min(calc(100vw / 1080), calc(100vh / 1150)); -webkit-font-smoothing: antialiased; }
.fondo { position: fixed; inset: 0;
  background: radial-gradient(110% 60% at 80% 0%, #24398A 0%, transparent 62%),
              radial-gradient(80% 50% at 0% 100%, rgba(20,184,166,.22) 0%, transparent 62%),
              linear-gradient(165deg, #0A1628 0%, #0F2150 100%); }
.fondo::after { content: ""; position: absolute; inset: 0; opacity: .35;
  background: linear-gradient(rgba(142,162,255,.07) 1px, transparent 1px) 0 0 / 100% calc(64 * var(--u)),
              linear-gradient(90deg, rgba(142,162,255,.07) 1px, transparent 1px) 0 0 / calc(64 * var(--u)) 100%;
  -webkit-mask-image: radial-gradient(70% 60% at 50% 40%, #000, transparent); }
#lienzo { position: fixed; inset: 0; width: 100%; height: 100%; display: block; touch-action: none; }
.capa { position: fixed; inset: 0; display: flex; flex-direction: column; justify-content: space-between;
  padding: calc(80 * var(--u)) calc(76 * var(--u)) calc(76 * var(--u)); pointer-events: none; }
.arriba { display: flex; flex-direction: column; gap: calc(24 * var(--u)); }
.marca { display: flex; align-items: center; gap: calc(16 * var(--u)); font-size: calc(38 * var(--u)); font-weight: 800; letter-spacing: -.02em; }
.logo { display: grid; place-items: center; width: calc(60 * var(--u)); height: calc(60 * var(--u)); border-radius: 28%;
  font-size: calc(33 * var(--u)); background: linear-gradient(135deg, #3B5BFD, #6D4BFF 55%, #14B8A6);
  box-shadow: 0 8px 24px -8px rgba(59,91,253,.9), inset 0 1px 0 rgba(255,255,255,.35); }
.etiqueta { align-self: flex-start; font-weight: 700; font-size: calc(22 * var(--u)); letter-spacing: .14em; text-transform: uppercase;
  color: #5EEAD4; margin-top: calc(18 * var(--u)); }
h1 { font-size: calc(86 * var(--u)); font-weight: 800; letter-spacing: -.035em; line-height: 1.03; }
h1 span { display: block; background: linear-gradient(90deg, #A5B4FF, #5EEAD4); -webkit-background-clip: text; color: transparent; }
.texto { font-size: calc(32 * var(--u)); color: #B9C4DD; font-weight: 500; line-height: 1.35; max-width: 26em; }
.abajo { display: flex; flex-direction: column; align-items: flex-start; gap: calc(26 * var(--u)); }
.boton { pointer-events: auto; cursor: pointer; border: 0; font-family: inherit; white-space: nowrap; font-size: calc(34 * var(--u));
  font-weight: 800; color: #fff; border-radius: 999px; padding: calc(26 * var(--u)) calc(50 * var(--u));
  background: linear-gradient(135deg, #3B5BFD, #6D4BFF 55%, #14B8A6);
  box-shadow: 0 18px 44px -14px rgba(59,91,253,1), inset 0 1px 0 rgba(255,255,255,.3); }
.boton:focus-visible { outline: 3px solid #5EEAD4; outline-offset: 4px; }
.confianza { display: flex; flex-wrap: wrap; gap: calc(10 * var(--u)) calc(28 * var(--u)); font-size: calc(24 * var(--u));
  color: #B9C4DD; font-weight: 600; }
.confianza span::before { content: "✓"; color: #5EEAD4; margin-right: .45em; font-weight: 800; }
.ap { animation: sube .8s cubic-bezier(.2,.8,.2,1) var(--d, 0s) both; }
@keyframes sube { from { opacity: 0; transform: translateY(36px); } to { opacity: 1; transform: none; } }
.late { animation: sube .8s cubic-bezier(.2,.8,.2,1) 3.4s both, late 1.6s ease-in-out 4.4s infinite; }
@keyframes late { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.04); } }
.pista { position: fixed; right: 14px; top: 14px; font-size: 13px; color: #CFE0FF; background: rgba(10,22,40,.6);
  border: 1px solid rgba(142,162,255,.35); border-radius: 999px; padding: 7px 14px; pointer-events: none; animation: sube .6s 4s both; }
body.captura .pista { display: none; }
body.tocado .pista { animation: none; opacity: 0; transition: opacity .4s; }
@media (min-aspect-ratio: 3/4) and (max-aspect-ratio: 13/10) { .texto { display: none; } }
@media (min-aspect-ratio: 13/10) {
  body { --u: calc(100vh / 760); }
  .capa { right: auto; width: 50%; padding: calc(60 * var(--u)); }
  h1 { font-size: calc(72 * var(--u)); }
  .texto { font-size: calc(26 * var(--u)); }
}

/* Formulario de contacto */
dialog { width: min(520px, 100% - 24px); max-height: calc(100% - 24px); border: 0; border-radius: 22px; padding: 0;
  color: #0E1726; background: #fff; box-shadow: 0 40px 80px -20px rgba(0,0,0,.6); }
dialog::backdrop { background: rgba(5,12,28,.65); backdrop-filter: blur(4px); }
dialog form { display: grid; gap: 14px; padding: 28px 26px 24px; font-size: 15px; }
dialog h2 { font-size: 24px; letter-spacing: -.02em; padding-right: 30px; }
dialog .intro { color: #5B6578; font-size: 15px; line-height: 1.45; margin-top: -6px; }
dialog label { display: grid; gap: 6px; font-weight: 600; font-size: 14px; }
dialog .opt { color: #5B6578; font-weight: 500; }
dialog input, dialog select, dialog textarea { font: inherit; font-weight: 500; color: #0E1726; width: 100%; padding: 11px 13px;
  border: 1.5px solid #E3E7EF; border-radius: 12px; background: #F7F8FC; }
dialog input:focus, dialog select:focus, dialog textarea:focus { outline: none; border-color: #3B5BFD; background: #fff;
  box-shadow: 0 0 0 4px rgba(59,91,253,.15); }
dialog textarea { resize: vertical; min-height: 76px; }
dialog .fila { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 480px) { dialog .fila { grid-template-columns: 1fr; } }
dialog .casilla { display: flex; align-items: flex-start; gap: 10px; font-weight: 500; font-size: 13px; color: #5B6578; line-height: 1.4; }
dialog .casilla input { width: 18px; height: 18px; margin-top: 1px; flex: none; accent-color: #3B5BFD; }
dialog .casilla a { color: #3B5BFD; }
dialog .trampa { position: absolute; left: -9999px; }
dialog .enviar { font: inherit; font-weight: 800; font-size: 16px; color: #fff; border: 0; border-radius: 999px; padding: 14px; cursor: pointer;
  background: linear-gradient(135deg, #3B5BFD, #6D4BFF 55%, #14B8A6); }
dialog .enviar:disabled { opacity: .6; cursor: wait; }
dialog .cerrar { position: absolute; top: 14px; right: 14px; width: 36px; height: 36px; border: 0; border-radius: 50%;
  background: #F1F3F8; color: #0E1726; font-size: 22px; line-height: 1; cursor: pointer; }
dialog .estado { min-height: 20px; font-size: 14px; font-weight: 600; }
dialog .estado.ok { color: #15803D; } dialog .estado.mal { color: #B91C1C; }
dialog .estado a { color: inherit; }
"""

TIPOS = ["Restaurante / cafetería", "Tienda / comercio", "Autónomo / servicios", "Tienda online", "Otro"]

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NirKanA · {etiqueta}</title>
<meta name="description" content="{texto}">
<style>{css}</style></head>
<body>
<div class="fondo"></div>
<canvas id="lienzo" aria-label="Portátil y móvil con la app NirKanA en 3D. Arrástralo para girarlo."></canvas>
<div class="capa">
  <div class="arriba">
    <div class="marca ap" style="--d:.1s"><span class="logo">N</span>NirKanA</div>
    <p class="etiqueta ap" style="--d:.3s">{etiqueta}</p>
    <h1 class="ap" style="--d:.45s">{titulo}<span>{titulo2}</span></h1>
    <p class="texto ap" style="--d:.65s">{texto}</p>
  </div>
  <div class="abajo">
    <button class="boton late" id="pedir" type="button">{llamada} →</button>
    <p class="confianza ap" style="--d:3.8s">{confianza}</p>
  </div>
</div>
<p class="pista">↻ Arrastra para girar</p>

<dialog id="formulario" aria-labelledby="titulo-form">
  <form id="form" novalidate>
    <button class="cerrar" type="button" aria-label="Cerrar">×</button>
    <h2 id="titulo-form">Pide tu demo gratuita</h2>
    <p class="intro">Te enseño NirKanA con productos como los tuyos en 20 minutos. Sin compromiso.</p>
    <div class="fila">
      <label>Nombre<input name="nombre" required maxlength="80" autocomplete="name"></label>
      <label>Negocio<input name="negocio" required maxlength="100" autocomplete="organization"></label>
    </div>
    <label>Tipo de negocio<select name="tipo" required>{opciones}</select></label>
    <div class="fila">
      <label>Email<input name="email" type="email" required maxlength="120" autocomplete="email"></label>
      <label><span>Teléfono <span class="opt">(opcional)</span></span><input name="telefono" type="tel" maxlength="20" autocomplete="tel" pattern="[0-9+ ()\\-]{{6,20}}"></label>
    </div>
    <label><span>¿Qué necesitas? <span class="opt">(opcional)</span></span><textarea name="mensaje" maxlength="1500" rows="3"></textarea></label>
    <label class="trampa" aria-hidden="true">No rellenar<input name="_gotcha" tabindex="-1" autocomplete="off"></label>
    <label class="casilla"><input type="checkbox" name="consentimiento" required>
      <span>Acepto que se usen estos datos solo para responder a mi solicitud, según el
      <a href="{privacidad}" target="_blank" rel="noopener noreferrer">aviso de privacidad</a>.</span></label>
    <button class="enviar" type="submit">Enviar solicitud</button>
    <p class="estado" role="status" aria-live="polite"></p>
  </form>
</dialog>

<script>
const CAPTURA = location.search.includes("captura");
if (CAPTURA) document.body.classList.add("captura");
window.NIRKANA = {cfg};
const CONTACTO = {contacto};
(() => {{
  const dlg = document.getElementById("formulario"), form = document.getElementById("form");
  const estado = form.querySelector(".estado"), boton = form.querySelector(".enviar");
  const decir = (html, tipo) => {{ estado.innerHTML = html; estado.className = "estado " + (tipo || ""); }};
  const limpio = (v, n) => String(v || "").replace(/[\\u0000-\\u0008\\u000B-\\u001F\\u007F]/g, "").trim().slice(0, n);
  const tel = String(CONTACTO.whatsapp).replace(/\\D/g, "");
  document.getElementById("pedir").addEventListener("click", () => {{ if (!CAPTURA) dlg.showModal(); }});
  form.querySelector(".cerrar").addEventListener("click", () => dlg.close());
  dlg.addEventListener("click", (e) => {{ if (e.target === dlg) dlg.close(); }});
  let enviado = 0;
  form.addEventListener("submit", async (e) => {{
    e.preventDefault();
    const d = new FormData(form);
    if (d.get("_gotcha")) return;
    if (!form.checkValidity()) {{ form.reportValidity(); decir("Revisa los campos marcados.", "mal"); return; }}
    if (Date.now() - enviado < 30000) {{ decir("Ya hemos recibido tu solicitud. ¡Gracias!", "ok"); return; }}
    const f = {{ nombre: limpio(d.get("nombre"), 80), negocio: limpio(d.get("negocio"), 100), tipo: limpio(d.get("tipo"), 40),
      email: limpio(d.get("email"), 120), telefono: limpio(d.get("telefono"), 20), mensaje: limpio(d.get("mensaje"), 1500) }};
    if (CONTACTO.formspree) {{
      boton.disabled = true; decir("Enviando…");
      try {{
        const r = await fetch("https://formspree.io/f/" + encodeURIComponent(CONTACTO.formspree), {{
          method: "POST", headers: {{ "Content-Type": "application/json", Accept: "application/json" }},
          body: JSON.stringify({{ ...f, _subject: "Demo de NirKanA · " + f.negocio, origen: "anuncio 3D" }}), credentials: "omit" }});
        if (!r.ok) throw new Error(r.status);
        form.reset(); enviado = Date.now();
        decir("¡Gracias! Te escribiré en menos de 24 horas laborables.", "ok");
      }} catch {{ decir("No se pudo enviar. Inténtalo de nuevo en unos minutos.", "mal"); }}
      finally {{ boton.disabled = false; }}
    }} else if (tel.length >= 8) {{
      const texto = "Hola, me interesa NirKanA. ¿Podemos ver una demo?\\n\\nNombre: " + f.nombre + "\\nNegocio: " + f.negocio +
        " (" + f.tipo + ")\\nEmail: " + f.email + "\\nTeléfono: " + (f.telefono || "-") + (f.mensaje ? "\\n\\n" + f.mensaje : "");
      window.open("https://wa.me/" + tel + "?text=" + encodeURIComponent(texto), "_blank", "noopener,noreferrer");
      enviado = Date.now(); decir("Se ha abierto WhatsApp con tu solicitud. Solo tienes que enviarla.", "ok");
    }} else {{
      decir('El formulario aún no está activo. Puedes pedir la demo desde <a href="' + CONTACTO.web + '#contacto" target="_blank" rel="noopener">nuestra web</a>.', "mal");
    }}
  }});
}})();
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
    contacto = json.dumps({"whatsapp": WHATSAPP, "formspree": FORMSPREE_ID, "web": WEB}, ensure_ascii=False)
    fuente = base64.b64encode((AQUI / "fuentes" / "PlusJakartaSans.woff2").read_bytes()).decode()
    js = (DIR / "nirkana3d.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    opciones = '<option value="">Elige una opción</option>' + "".join(
        f'<option{" selected" if t == ad["tipo"] else ""}>{escape(t)}</option>' for t in TIPOS)
    confianza = "".join(f"<span>{escape(x)}</span>" for x in (
        [CONTACTO] if CONTACTO else ["Demo sin compromiso", "Sin instalar nada", "Datos cifrados"]))
    return PAGINA.format(css=CSS.replace("{FUENTE}", fuente), etiqueta=escape(ad["etiqueta"]), titulo=escape(ad["titulo"]),
                         titulo2=escape(ad["titulo2"]), texto=escape(ad["texto"]), llamada=escape(LLAMADA),
                         confianza=confianza, opciones=opciones, privacidad=escape(WEB + "privacidad.html"),
                         cfg=cfg, contacto=contacto, js=js)


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
