"""Genera los anuncios de NirKanA en PNG.  Uso:  python marketing/anuncios/generar.py"""
import os
from html import escape
from pathlib import Path

from playwright.sync_api import sync_playwright

# Cuando quieras publicar, rellena esto y vuelve a ejecutar los scripts. Vacío = no aparece.
CONTACTO = ""  # texto que se ve en los anuncios, p. ej. "WhatsApp 600 111 222 · nirkana.es"
LLAMADA = "Pide tu demo gratuita"

# A dónde llegan las solicitudes del formulario de los anuncios interactivos (los mismos datos que en la web).
WHATSAPP = ""      # número con prefijo y solo cifras, p. ej. "34600111222"
FORMSPREE_ID = "mbgdrbyg"  # el código de tu formulario de Formspree (lo que va después de formspree.io/f/)
WEB = "https://nirkana.es/"  # tu web; el aviso de privacidad está en WEB + "privacidad.html"

AQUI = Path(__file__).resolve().parent
CAPTURAS = AQUI.parents[1] / "docs" / "screenshots"
SALIDA = AQUI / "img"

FORMATOS = {  # nombre: (ancho, alto, uso)
    "feed": (1080, 1350, "Instagram y Facebook (publicación)"),
    "historia": (1080, 1920, "Historias de Instagram/Facebook y estados de WhatsApp"),
    "horizontal": (1200, 628, "Facebook, LinkedIn y anuncios de enlace"),
}

# Cada anuncio: captura y recorte (x, y, ancho, alto) en píxeles de la captura original.
ANUNCIOS = {
    "general": {
        "etiqueta": "Gestor de ventas para tu negocio",
        "titulo": "Vende más.", "titulo2": "Controla todo.",
        "texto": "Cobros, stock, caja y clientes en una sola app. Y avisos antes de que algo vaya mal.",
        "puntos": ["Desde el móvil, sin instalar nada", "Para restaurantes, tiendas y autónomos", "Informe del negocio cada lunes"],
        "captura": "02-panel.png", "recorte": (360, 70, 1020, 700), "movil": "11-movil-panel.png",
    },
    "restaurante": {
        "etiqueta": "Para restaurantes y cafeterías",
        "titulo": "Tu sala, tu cocina", "titulo2": "y tu caja, en el móvil.",
        "texto": "Los camareros piden desde el móvil y la cocina lo ve al momento.",
        "puntos": ["Mesas y comandas compartidas", "Pantalla de cocina en tiempo real", "Cuenta dividida y pago mixto"],
        "captura": "23-mesas.png", "recorte": (360, 80, 1020, 720),
    },
    "tienda": {
        "etiqueta": "Para tiendas y comercios",
        "titulo": "Que no se te agote", "titulo2": "lo que más vendes.",
        "texto": "La app vigila tu stock y te avisa antes de que falte un producto.",
        "puntos": ["Venta rápida con control de stock", "Pedidos a proveedores en un clic", "Puntos para clientes fieles"],
        "captura": "29-alertas.png", "recorte": (360, 70, 1020, 720),
    },
    "autonomo": {
        "etiqueta": "Para autónomos y servicios",
        "titulo": "Tu agenda y tus facturas,", "titulo2": "sin papeles.",
        "texto": "Organiza tus citas, cobra con un toque y envía la factura en PDF.",
        "puntos": ["Agenda de citas sin solapes", "Cobro de la cita con un toque", "Facturas en PDF al instante"],
        "captura": "18-agenda.png", "recorte": (360, 70, 1020, 600),
    },
    "online": {
        "etiqueta": "Para tiendas online",
        "titulo": "Descubre qué producto", "titulo2": "te da dinero de verdad.",
        "texto": "Márgenes, canales y clientes que dejan de comprar, en un solo panel.",
        "puntos": ["Ventas por canal y forma de pago", "Márgenes y precios por producto", "Aviso de clientes que se van"],
        "captura": "30-analisis-abc.png", "recorte": (360, 70, 1020, 720),
    },
    "cobro": {
        "etiqueta": "Cobra rápido y sin errores",
        "titulo": "Cobra en segundos,", "titulo2": "sin líos con el cambio.",
        "texto": "Toca los productos, elige la forma de pago y listo. La app calcula el cambio por ti.",
        "puntos": ["Tarjeta, efectivo, Bizum o pago mixto", "Cuenta dividida entre varios", "Ticket y factura en PDF"],
        "captura": "03-punto-de-venta.png", "recorte": (360, 40, 1020, 720), "movil": "12-movil-vender.png",
    },
    "cocina": {
        "etiqueta": "Para restaurantes y bares",
        "titulo": "Pedidos a cocina", "titulo2": "sin papelitos ni gritos.",
        "texto": "Cada comanda aparece en la pantalla de cocina en el orden en que llega.",
        "puntos": ["Pedidos en orden de llegada", "Notas: «poco hecho», «para compartir»", "La sala ve qué platos están listos"],
        "captura": "24-cocina.png", "recorte": (360, 80, 1020, 720),
    },
    "caja": {
        "etiqueta": "Cierre de caja",
        "titulo": "Cierra la caja", "titulo2": "en un minuto.",
        "texto": "La app sabe cuánto efectivo debería haber en el cajón. Tú solo lo cuentas.",
        "puntos": ["Ventas por forma de pago", "Aviso si la caja no cuadra", "Informe del cierre guardado y firmado"],
        "captura": "19-cierre-de-caja.png", "recorte": (360, 80, 1020, 820),
    },
    "equipo": {
        "etiqueta": "Tu equipo, bajo control",
        "titulo": "Un PIN por empleado.", "titulo2": "Cada venta, firmada.",
        "texto": "Cada persona entra con su PIN y solo ve lo que le toca.",
        "puntos": ["Roles: administrador, encargado y empleado", "Registro de quién hace cada cosa", "Ventas por persona en el panel"],
        "captura": "22-equipo-y-seguridad.png", "recorte": (360, 80, 1020, 700), "movil": "21-acceso-equipo.png",
    },
    "promociones": {
        "etiqueta": "Promociones y puntos",
        "titulo": "Happy hour y 2x1", "titulo2": "que se aplican solos.",
        "texto": "Crea la promoción una vez y la app la aplica sola al cobrar, el día y a la hora que digas.",
        "puntos": ["Descuentos por día y por horario", "Ofertas «lleva 2, paga 1»", "Puntos para tus clientes fieles"],
        "captura": "26-promociones.png", "recorte": (360, 80, 1020, 720),
    },
    "informe": {
        "etiqueta": "Inteligencia para tu negocio",
        "titulo": "Cada lunes,", "titulo2": "cómo va tu negocio.",
        "texto": "Cuánto has vendido, qué ha funcionado y qué deberías cambiar, explicado en claro.",
        "puntos": ["Ventas y beneficio de la semana", "Tu mejor y tu peor día", "Recomendaciones concretas"],
        "captura": "32-informe-semanal.png", "recorte": (360, 85, 1020, 780),
    },
}

CSS = """
@font-face { font-family: Jakarta; src: url("%(fuente)s") format("woff2"); font-weight: 200 800; }
* { box-sizing: border-box; margin: 0; }
body { width: %(w)dpx; height: %(h)dpx; overflow: hidden; font-family: Jakarta, sans-serif; color: #fff;
  background: radial-gradient(120%% 80%% at 85%% 0%%, #2A3F8F 0%%, transparent 55%%),
              radial-gradient(90%% 60%% at 0%% 100%%, rgba(20,184,166,.28) 0%%, transparent 60%%),
              linear-gradient(160deg, #0B1B33, #13265A); position: relative; }
body::before { content: ""; position: absolute; inset: 0; opacity: .5;
  background-image: radial-gradient(rgba(142,162,255,.22) 1.4px, transparent 1.4px); background-size: 34px 34px;
  -webkit-mask-image: linear-gradient(180deg, #000, transparent 70%%); }
.lienzo { position: relative; height: 100%%; display: flex; flex-direction: column; }
.marca { display: flex; align-items: center; gap: 18px; font-weight: 800; letter-spacing: -.02em; }
.logo { display: grid; place-items: center; border-radius: 26%%; color: #fff;
  background: linear-gradient(135deg, #3B5BFD, #6D4BFF 55%%, #14B8A6); box-shadow: 0 10px 30px -8px rgba(59,91,253,.9); }
.etiqueta { display: inline-flex; align-items: center; gap: 12px; align-self: flex-start; font-weight: 600;
  color: #CFE0FF; border: 1.5px solid rgba(142,162,255,.45); background: rgba(59,91,253,.16); border-radius: 999px; }
.etiqueta i { width: 12px; height: 12px; border-radius: 50%%; background: #14B8A6; box-shadow: 0 0 0 6px rgba(20,184,166,.25); }
h1 { font-weight: 800; letter-spacing: -.025em; word-spacing: .04em; line-height: 1.04; }
h1, h1 span { font-kerning: normal; text-rendering: geometricPrecision; }
h1 span { display: block; background: linear-gradient(90deg, #8EA2FF, #5EEAD4); -webkit-background-clip: text; color: transparent; }
.texto { color: #B9C4DD; font-weight: 500; line-height: 1.35; }
ul { list-style: none; padding: 0; display: grid; }
li { display: flex; align-items: center; gap: 16px; font-weight: 600; color: #E8ECF5; }
li b { flex: none; display: grid; place-items: center; border-radius: 50%%; background: rgba(20,184,166,.18); color: #5EEAD4; }
.escena { position: relative; perspective: 2200px; }
.pantalla { position: relative; border-radius: 22px; overflow: hidden; background: #fff;
  box-shadow: 0 50px 90px -30px rgba(0,0,0,.75), 0 0 0 1.5px rgba(255,255,255,.12);
  transform: rotateY(-9deg) rotateX(5deg); transform-origin: left center; }
.barra { height: 38px; background: #EEF1F7; display: flex; align-items: center; gap: 9px; padding: 0 18px; }
.barra i { width: 12px; height: 12px; border-radius: 50%%; background: #D3D9E6; }
.barra i:first-child { background: #FF6B6B; } .barra i:nth-child(2) { background: #FFC24B; } .barra i:nth-child(3) { background: #3DD68C; }
.recorte { position: relative; overflow: hidden; }
.recorte img { position: absolute; max-width: none; }
.movil { position: absolute; border-radius: 34px; overflow: hidden; border: 9px solid #0A1222; background: #fff;
  box-shadow: 0 40px 70px -20px rgba(0,0,0,.8); }
.movil img { width: 100%%; display: block; }
.pie { display: flex; align-items: center; gap: 24px; margin-top: auto; }
.boton { white-space: nowrap; flex: none; display: inline-flex; align-items: center; gap: 14px; font-weight: 800; color: #fff; border-radius: 999px;
  background: linear-gradient(135deg, #3B5BFD, #6D4BFF 55%%, #14B8A6); box-shadow: 0 18px 40px -14px rgba(59,91,253,.95); }
.nota { color: #9AA6BD; font-weight: 500; }
"""

# Tamaños por formato: (márgenes, logo, nombre, etiqueta, h1, texto, punto, botón, nota)
MEDIDAS = {
    "feed": dict(pad=72, logo=64, nombre=40, eti=26, h1=80, txt=31, li=29, btn=32, nota=24, ancho_pantalla=1000),
    "historia": dict(pad=84, logo=72, nombre=44, eti=30, h1=82, txt=36, li=33, btn=38, nota=28, ancho_pantalla=980),
    "horizontal": dict(pad=48, logo=44, nombre=28, eti=17, h1=46, txt=19, li=18, btn=20, nota=15, ancho_pantalla=600),
}


def captura(nombre, recorte, ancho):
    x, y, w, h = recorte
    escala = ancho / w
    src = (CAPTURAS / nombre).as_uri()
    return (f'<div class="recorte" style="width:{ancho}px;height:{round(h * escala)}px">'
            f'<img src="{src}" style="width:{round(1440 * escala)}px;left:{round(-x * escala)}px;top:{round(-y * escala)}px" alt=""></div>')


def pagina(ad, formato):
    w, h, _ = FORMATOS[formato]
    m = MEDIDAS[formato]
    pad = m["pad"]
    css = CSS % {"w": w, "h": h, "fuente": (AQUI / "fuentes" / "PlusJakartaSans.woff2").as_uri()}
    marca = (f'<div class="marca" style="font-size:{m["nombre"]}px"><span class="logo" '
             f'style="width:{m["logo"]}px;height:{m["logo"]}px;font-size:{m["logo"] * .55:.0f}px">N</span>NirKanA</div>')
    etiqueta = (f'<p class="etiqueta" style="font-size:{m["eti"]}px;padding:{m["eti"] * .5:.0f}px {m["eti"] * .9:.0f}px">'
                f'<i></i>{escape(ad["etiqueta"])}</p>')
    titulo = (f'<h1 style="font-size:{m["h1"]}px">{escape(ad["titulo"])}<span>{escape(ad["titulo2"])}</span></h1>')
    texto = f'<p class="texto" style="font-size:{m["txt"]}px">{escape(ad["texto"])}</p>'
    puntos = "".join(f'<li style="font-size:{m["li"]}px"><b style="width:{m["li"] * 1.4:.0f}px;height:{m["li"] * 1.4:.0f}px;'
                     f'font-size:{m["li"] * .8:.0f}px">✓</b>{escape(p)}</li>' for p in ad["puntos"])
    lista = f'<ul style="gap:{m["li"] * .55:.0f}px">{puntos}</ul>'
    nota = escape(CONTACTO) if CONTACTO else "Demo de 20 minutos, sin compromiso"
    pie = (f'<div class="pie"><span class="boton" style="font-size:{m["btn"]}px;padding:{m["btn"] * .7:.0f}px {m["btn"] * 1.3:.0f}px">'
           f'{escape(LLAMADA)} →</span><span class="nota" style="font-size:{m["nota"]}px">{nota}</span></div>')

    aw = m["ancho_pantalla"]
    movil = ""
    if ad.get("movil"):
        mw = round(aw * .27)
        movil = (f'<div class="movil" style="width:{mw}px;right:{-pad * .2:.0f}px;bottom:{-mw * .35:.0f}px">'
                 f'<img src="{(CAPTURAS / ad["movil"]).as_uri()}" alt=""></div>')
    escena = (f'<div class="escena"><div class="pantalla" style="width:{aw}px"><div class="barra"><i></i><i></i><i></i></div>'
              f'{captura(ad["captura"], ad["recorte"], aw)}</div>{movil}</div>')

    if formato == "horizontal":
        cuerpo = (f'<div class="lienzo" style="padding:{pad}px;flex-direction:row;gap:36px">'
                  f'<div style="flex:0 0 520px;display:flex;flex-direction:column;gap:18px">{marca}{etiqueta}{titulo}{lista}{pie}</div>'
                  f'<div style="flex:1;display:flex;align-items:center;margin-right:-{pad + 160}px">{escena}</div></div>')
    else:
        gap = 34 if formato == "feed" else 50
        bloque_pantalla = (f'<div style="margin:0 -{pad}px 0 0;padding:{gap * .4:.0f}px 0 0;flex:1;min-height:0;display:flex;'
                           f'overflow:hidden;-webkit-mask-image:linear-gradient(180deg,#000 82%,transparent);align-items:{"flex-start" if formato == "feed" else "center"}">{escena}</div>')
        cuerpo = (f'<div class="lienzo" style="padding:{pad}px;gap:{gap}px">{marca}'
                  f'<div style="display:flex;flex-direction:column;gap:{gap * .7:.0f}px">{etiqueta}{titulo}{texto if formato == "historia" else ""}</div>'
                  f'{bloque_pantalla if formato == "historia" else ""}{lista}'
                  f'{bloque_pantalla if formato == "feed" else ""}{pie}</div>')
    return f'<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{css}</style></head><body>{cuerpo}</body></html>'


def main():
    SALIDA.mkdir(exist_ok=True)
    tmp = SALIDA / "_tmp.html"
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        for formato, (w, h, _) in FORMATOS.items():
            pag = nav.new_page(viewport={"width": w, "height": h})
            for clave, ad in ANUNCIOS.items():
                tmp.write_text(pagina(ad, formato), encoding="utf-8")
                pag.goto(tmp.as_uri())
                pag.wait_for_load_state("networkidle")
                pag.evaluate("document.fonts.ready")
                destino = SALIDA / f"{clave}-{formato}.png"
                pag.screenshot(path=str(destino))
                print("✓", destino.relative_to(AQUI))
            pag.close()
        nav.close()
    tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
