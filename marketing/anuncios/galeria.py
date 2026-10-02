"""Crea galeria.html: todos los anuncios en una página para verlos y descargarlos.  Uso: python marketing/anuncios/galeria.py"""
from html import escape
from pathlib import Path

AQUI = Path(__file__).resolve().parent

SECCIONES = [
    ("Anuncios 3D interactivos", "Ábrelos y arrastra para girar el portátil y el móvil. Cada uno es un solo archivo: se puede enviar por WhatsApp o email.", "3d", "*.html"),
    ("Vídeos 3D", "Para Reels, TikTok, historias y publicaciones.", "3d/video", "*.mp4"),
    ("Imágenes 3D", "Publicación, historia y horizontal.", "3d/imagenes", "*.png"),
    ("Vídeos animados", "17 segundos: gancho, logo, tres funciones y llamada a la acción.", "video", "*.mp4"),
    ("Imágenes", "Once campañas en tres formatos.", "img", "*.png"),
]

CSS = """
:root { --bg: #0B1B33; --tarjeta: #13254a; --texto: #E8ECF5; --suave: #9AA6BD; --linea: #22304A; color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--texto); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
header, section { width: min(1200px, 100% - 32px); margin: 0 auto; }
header { padding: 40px 0 8px; }
h1 { margin: 0 0 6px; font-size: 32px; } h2 { margin: 40px 0 4px; font-size: 22px; }
p { margin: 0 0 16px; color: var(--suave); }
.rejilla { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
figure { margin: 0; background: var(--tarjeta); border: 1px solid var(--linea); border-radius: 14px; overflow: hidden; display: flex; flex-direction: column; }
figure img, figure video { width: 100%; aspect-ratio: 4 / 5; object-fit: contain; background: #081226; display: block; }
figure iframe { width: 100%; aspect-ratio: 4 / 5; border: 0; display: block; background: #081226; }
figcaption { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 10px 12px; font-size: 14px; }
a { color: #8EA2FF; font-weight: 600; text-decoration: none; white-space: nowrap; }
"""


def tarjeta(ruta: Path):
    rel = ruta.relative_to(AQUI).as_posix()
    nombre = escape(ruta.stem)
    if ruta.suffix == ".png":
        medio = f'<img src="{rel}" alt="Anuncio {nombre}" loading="lazy">'
    elif ruta.suffix == ".mp4":
        medio = f'<video src="{rel}" controls muted loop playsinline preload="metadata"></video>'
    else:
        medio = f'<iframe src="{rel}" title="Anuncio 3D {nombre}" loading="lazy"></iframe>'
    abrir = f'<a href="{rel}" target="_blank" rel="noopener">Abrir</a> · ' if ruta.suffix == ".html" else ""
    return (f'<figure>{medio}<figcaption><span>{nombre}</span>'
            f'<span>{abrir}<a href="{rel}" download>Descargar</a></span></figcaption></figure>')


def main():
    partes = []
    for titulo, texto, carpeta, patron in SECCIONES:
        archivos = sorted((AQUI / carpeta).glob(patron))
        if archivos:
            partes.append(f'<section><h2>{escape(titulo)} ({len(archivos)})</h2><p>{escape(texto)}</p>'
                          f'<div class="rejilla">{"".join(tarjeta(a) for a in archivos)}</div></section>')
    html = (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>Anuncios de NirKanA</title>'
            f'<style>{CSS}</style></head><body><header><h1>Anuncios de NirKanA</h1>'
            f'<p>Todo listo para publicar. Los textos para acompañarlos están en TEXTOS.md.</p></header>'
            f'{"".join(partes)}<div style="height:60px"></div></body></html>')
    (AQUI / "galeria.html").write_text(html, encoding="utf-8")
    print("✓ galeria.html")


if __name__ == "__main__":
    main()
