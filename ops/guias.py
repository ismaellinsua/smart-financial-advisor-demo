"""Genera las guías de la web: docs/guias/ (índice y una página por guía) y docs/sitemap.xml.

    python ops/guias.py            # escribe las páginas y el mapa del sitio
    python ops/guias.py --check    # no escribe nada: sale con error si lo publicado no es lo que saldría de los textos

Los textos están en ops/guias_texto.py. La cabecera, el pie y los iconos se copian de una página de sector
(docs/tpv-tiendas/), así que las guías siempre llevan lo mismo que el resto de la web, incluido el «Aviso legal» que añada
ops/legal.py. Cada guía sale con título y descripción propios, migas de pan, datos estructurados (BreadcrumbList, Article y
FAQPage con las mismas preguntas que se ven), la prueba de 24 horas y el correo visibles, y enlaces a su sector y a otras guías.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guias_texto as T  # noqa: E402

ROOT = HERE.parent
DOCS = ROOT / "docs"
SITE = "https://nirkana.es"
DATE = "2026-10-21"
DATE_TEXT = "21 de octubre de 2026"
REFERENCE = "tpv-tiendas/index.html"
CORE = ["", "tpv-restaurantes/", "programa-peluquerias-estetica/", "tpv-tiendas/", "programa-facturacion-autonomos/", "tpv-tienda-online/"]
CSP = ("default-src 'self'; img-src 'self' data: https://*.goatcounter.com https://nirkana-prueba.onrender.com; "
       "frame-src https://nirkana-prueba.onrender.com; style-src 'self'; script-src 'self'; connect-src 'self' https://formspree.io; "
       "form-action https://formspree.io; base-uri 'none'; object-src 'none'; upgrade-insecure-requests")


class GuideError(Exception):
    pass


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def card_title(title: str) -> str:
    return title.removesuffix(" · NirKanA")


def ld(data: dict) -> str:
    return '  <script type="application/ld+json">\n  ' + json.dumps(data, ensure_ascii=False) + "\n  </script>\n"


# ------------------------------------------------------------------------------------------------ shared pieces
def sprite_sheet() -> str:
    """Every icon the site's pages define (each page only carries the ones it uses), so the guides can use any of them."""
    symbols: dict[str, str] = {}
    for path in [DOCS / "index.html"] + [DOCS / p / "index.html" for p in CORE[1:]]:
        for match in re.finditer(r'    <symbol id="([a-z-]+)".*?</symbol>\n', path.read_text(encoding="utf-8"), re.S):
            symbols.setdefault(match.group(1), match.group(0))
    return '  <svg class="sprite" aria-hidden="true" focusable="false">\n' + "".join(symbols.values()) + "  </svg>\n"


def chrome(demo: str) -> tuple[str, str, str]:
    """Sprite, header and footer of the reference sector page, with the «Guías» link marked as the current one."""
    ref = (DOCS / REFERENCE).read_text(encoding="utf-8")
    parts = []
    for pattern in (r'  <header class="top">.*?</header>\n', r'  <footer class="foot">.*?</footer>\n'):
        match = re.search(pattern, ref, re.S)
        if not match:
            raise GuideError(f"{REFERENCE}: no encuentro {pattern}")
        parts.append(re.sub(r'data-demo="[a-z]+"', f'data-demo="{demo}"', match.group(0)))
    header, footer = parts
    sprite = sprite_sheet()
    link = '<a href="/guias/">Guías</a>'
    if link not in header:
        raise GuideError(f"{REFERENCE}: la cabecera no tiene el enlace «Guías»")
    return sprite, header.replace(link, '<a class="here" href="/guias/" aria-current="page">Guías</a>'), footer


def head(*, title: str, description: str, path: str, blocks: list[dict], article: bool = False, alt: str = "Resumen de ventas de NirKanA") -> str:
    url = f"{SITE}/{path}"
    image = f"{SITE}/assets/img/og.jpg"
    lines = [
        '<!doctype html>', '<html lang="es" class="js has-demo has-trial">', '<head>',
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        '  <meta http-equiv="Content-Security-Policy"', f'        content="{CSP}">',
        '  <meta name="referrer" content="strict-origin-when-cross-origin">',
        f'  <title>{esc(title)}</title>',
        f'  <meta name="description" content="{esc(description)}">',
        '  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">',
        f'  <meta property="og:title" content="{esc(title)}">',
        f'  <meta property="og:description" content="{esc(description)}">',
        f'  <meta property="og:type" content="{"article" if article else "website"}">',
        f'  <meta property="og:image" content="{image}">',
        '  <meta property="og:image:width" content="1200">',
        '  <meta property="og:image:height" content="630">',
        f'  <meta property="og:image:alt" content="{esc(alt)}">',
        '  <meta property="og:locale" content="es_ES">',
        '  <meta property="og:site_name" content="NirKanA">',
        f'  <meta property="og:url" content="{url}">',
    ]
    if article:
        lines += [f'  <meta property="article:published_time" content="{DATE}">', f'  <meta property="article:modified_time" content="{DATE}">',
                  '  <meta property="article:author" content="NirKanA">']
    lines += [
        '  <meta name="twitter:card" content="summary_large_image">',
        f'  <meta name="twitter:title" content="{esc(title)}">',
        f'  <meta name="twitter:description" content="{esc(description)}">',
        f'  <meta name="twitter:image" content="{image}">',
        f'  <meta name="twitter:image:alt" content="{esc(alt)}">',
        '  <meta name="theme-color" content="#0B1B33">',
        '  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">',
        '  <link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">',
        '  <link rel="stylesheet" href="/assets/site.css">',
        '  <noscript><link rel="stylesheet" href="/assets/sin-js.css"></noscript>',
        '  <script src="/assets/site.js" defer></script>',
        f'  <link rel="canonical" href="{url}">',
    ]
    return "\n".join(lines) + "\n" + "".join(ld(block) for block in blocks) + "</head>\n"


def breadcrumbs(items: list[tuple[str, str]]) -> dict:
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i, "name": name, "item": f"{SITE}{path}"} for i, (name, path) in enumerate(items, 1)]}


def faq_block(faq: list[tuple[str, str]]) -> dict:
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}


def faq_html(faq: list[tuple[str, str]]) -> str:
    items = "".join(f"          <details>\n            <summary>{esc(q)}</summary>\n            <p>{esc(a)}</p>\n          </details>\n" for q, a in faq)
    return f'        <div class="faq-list">\n{items}        </div>\n'


def cta_buttons() -> str:
    return ('<div class="cta-row">\n'
            '            <a class="btn magnet only-trial" data-trial href="/#contacto">Probar NirKanA gratis <svg class="ic"><use href="#i-arrow"/></svg></a>\n'
            '            <a class="btn ghost only-trial" href="/#contacto">Quiero NirKanA</a>\n'
            '            <a class="btn magnet no-trial" href="/#contacto">Quiero NirKanA <svg class="ic"><use href="#i-arrow"/></svg></a>\n'
            '            <a class="btn ghost no-trial only-demo" data-demo="{demo}" href="/demo/">Ver la demo</a>\n'
            '          </div>')


def mail_line(subject: str) -> str:
    return f'<p class="mail-line" data-email-wrap hidden><span>O escríbenos a <a data-email data-subject="{esc(subject)}"></a></span></p>'


def final_band(demo: str, subject: str) -> str:
    return f"""    <section class="band">
      <div class="wrap center-cta">
        <h2>¿Lo vemos con tu negocio?</h2>
        <p class="sub only-trial">Pruébala gratis 24 horas con un negocio de ejemplo, sin tarjeta. Si te encaja, te la
          dejamos lista con tus productos o tus servicios.</p>
        <p class="sub no-trial">Cuéntanos tu negocio y te la dejamos lista con tus productos, tus servicios y tu forma de trabajar.
          Sin compromiso.</p>
        {cta_buttons().format(demo=demo)}
        {mail_line(subject)}
      </div>
    </section>
"""


def page(head_html: str, sprite: str, header: str, main: str, footer: str) -> str:
    return (f'{head_html}<body class="subpage">\n{sprite}\n  <a class="skip" href="#contenido">Saltar al contenido</a>\n\n{header}\n'
            f'  <main id="contenido">\n{main}  </main>\n\n{footer}</body>\n</html>\n')


# ------------------------------------------------------------------------------------------------ guide page
def render_guide(slug: str) -> str:
    g = T.GUIDES[slug]
    path = f"guias/{slug}/"
    sprite, header, footer = chrome(g["demo"])
    sections = g["sections"]
    words = len(plain(g["lead"] + " ".join(body for _, _, body in sections) + g["nirkana"]).split())
    minutes = max(3, round(words / 200))
    crumbs = [("NirKanA", "/"), ("Guías", "/guias/"), (card_title(g["title"]), f"/{path}")]
    blocks = [
        breadcrumbs(crumbs),
        {"@context": "https://schema.org", "@type": "Article", "headline": g["h1"], "description": g["description"], "inLanguage": "es",
         "datePublished": DATE, "dateModified": DATE, "mainEntityOfPage": {"@type": "WebPage", "@id": f"{SITE}/{path}"},
         "image": [f"{SITE}/assets/img/og.jpg"],
         "author": {"@type": "Organization", "name": "NirKanA", "url": f"{SITE}/"},
         "publisher": {"@type": "Organization", "name": "NirKanA", "url": f"{SITE}/",
                       "logo": {"@type": "ImageObject", "url": f"{SITE}/assets/apple-touch-icon.png"}}},
        faq_block(g["faq"]),
    ]
    toc_items = [(sid, h2) for sid, h2, _ in sections] + [("nirkana", "Cómo lo hace NirKanA"), ("preguntas", "Preguntas frecuentes")]
    toc = "".join(f'<li><a href="#{sid}">{esc(h2)}</a></li>' for sid, h2 in toc_items)
    body = "\n".join(f'        <section class="guide-sec" id="{sid}">\n          <h2>{esc(h2)}</h2>{text.rstrip()}\n        </section>\n' for sid, h2, text in sections)
    shot_id, shot_alt, shot_caption = g["shot"]
    sector_links = " · ".join(f'<a href="{T.SECTOR[s][0]}">{esc(T.SECTOR[s][1])}</a>' for s in g["sectors"])
    related = "".join(f'<li><a href="/guias/{r}/">{esc(card_title(T.GUIDES[r]["title"]))}</a> — {esc(T.GUIDES[r]["summary"])}</li>' for r in g["related"])
    note = f'        <div class="callout"><p><strong>Importante:</strong> {esc(g["disclaimer"])}</p></div>\n' if g.get("disclaimer") else ""
    main = f"""    <article class="guide">
      <header class="guide-head">
        <div class="wrap narrow">
          <nav class="crumbs" aria-label="Estás en"><a href="/">NirKanA</a> <span aria-hidden="true">›</span> <a href="/guias/">Guías</a> <span aria-hidden="true">›</span> {esc(card_title(g["title"]))}</nav>
          <p class="eyebrow">Guía</p>
          <h1>{esc(g["h1"])}</h1>
          <p class="lead">{esc(g["lead"])}</p>
          <p class="guide-meta">Por el equipo de NirKanA · Actualizada el <time datetime="{DATE}">{DATE_TEXT}</time> · {minutes} min de lectura</p>
        </div>
      </header>
      <div class="wrap narrow guide-body">
{note}        <nav class="toc" aria-label="En esta guía"><b>En esta guía</b><ol>{toc}</ol></nav>
{body}
        <aside class="guide-cta" aria-label="Probar NirKanA">
          <p class="cta-title">Pruébalo con un negocio de ejemplo</p>
          <p class="only-trial">Abre NirKanA 24 horas gratis, sin tarjeta, y compruébalo tú. Si te encaja, te lo dejamos listo con tus productos o tus servicios.</p>
          <p class="no-trial">Cuéntanos tu negocio y te lo dejamos listo con tus productos o tus servicios. Sin compromiso.</p>
          {cta_buttons().format(demo=g["demo"])}
          {mail_line(g["subject"])}
        </aside>

        <section class="guide-sec nk" id="nirkana">
          <h2>Cómo lo hace NirKanA</h2>
          <div class="nk-box">{g["nirkana"].rstrip()}
            <figure class="shot guide-shot">
              <img src="/assets/img/shots/{shot_id}.webp" width="1200" height="750" alt="{esc(shot_alt)}" loading="lazy">
              <figcaption>{esc(shot_caption)}</figcaption>
            </figure>
            <p class="nk-more">Más sobre esto: {sector_links}.</p>
          </div>
        </section>

        <section class="guide-sec" id="preguntas">
          <h2>Preguntas frecuentes</h2>
{faq_html(g["faq"])}        </section>

        <section class="guide-sec" id="relacionadas">
          <h2>Sigue leyendo</h2>
          <ul class="related">{related}</ul>
        </section>
      </div>
    </article>

{final_band(g["demo"], g["subject"])}"""
    return page(head(title=g["title"], description=g["description"], path=path, blocks=blocks, article=True, alt=shot_alt),
                sprite, header, main, footer)


# ------------------------------------------------------------------------------------------------ hub page
def render_hub() -> str:
    h = T.HUB
    sprite, header, footer = chrome(h["demo"])
    items = [{"@type": "ListItem", "position": i, "url": f"{SITE}/guias/{slug}/", "name": card_title(g["title"])} for i, (slug, g) in enumerate(T.GUIDES.items(), 1)]
    blocks = [
        breadcrumbs([("NirKanA", "/"), ("Guías", "/guias/")]),
        {"@context": "https://schema.org", "@type": "CollectionPage", "name": h["h1"], "description": h["description"], "inLanguage": "es",
         "url": f"{SITE}/guias/", "isPartOf": {"@type": "WebSite", "name": "NirKanA", "url": f"{SITE}/"},
         "mainEntity": {"@type": "ItemList", "itemListElement": items}},
        faq_block(h["faq"]),
    ]
    groups: dict[str, list[str]] = {}
    for slug, g in T.GUIDES.items():
        groups.setdefault(g["group"], []).append(slug)
    sections = ""
    for name, slugs in groups.items():
        cards = "".join(
            f'          <article class="feat"><span class="ico"><svg class="ic"><use href="#{T.GUIDES[s]["icon"]}"/></svg></span>\n'
            f'            <h3><a href="/guias/{s}/">{esc(card_title(T.GUIDES[s]["title"]))}</a></h3><p>{esc(T.GUIDES[s]["summary"])}</p></article>\n' for s in slugs)
        sections += f"""    <section class="guide-group">
      <div class="wrap">
        <div class="head">
          <h2>{esc(name)}</h2>
        </div>
        <div class="feats">
{cards}        </div>
      </div>
    </section>

"""
    main = f"""    <section class="sub-hero">
      <div class="wrap">
        <nav class="crumbs" aria-label="Estás en"><a href="/">NirKanA</a> <span aria-hidden="true">›</span> Guías</nav>
        <h1>{esc(h["h1"])}</h1>
        <p class="sub">{esc(h["lead"])}</p>
        {cta_buttons().format(demo=h["demo"])}
      </div>
    </section>

{sections}    <section>
      <div class="wrap faq">
        <div class="faq-side">
          <p class="eyebrow">Preguntas</p>
          <h2>Preguntas frecuentes</h2>
          <p class="sub">Por sectores: <a href="/tpv-restaurantes/">Restaurantes</a> · <a href="/programa-peluquerias-estetica/">Peluquerías</a> · <a href="/tpv-tiendas/">Tiendas</a> · <a href="/programa-facturacion-autonomos/">Autónomos</a> · <a href="/tpv-tienda-online/">Tiendas online</a>.</p>
        </div>
{faq_html(h["faq"])}      </div>
    </section>

{final_band(h["demo"], "Consulta desde las guías de NirKanA")}"""
    return page(head(title=h["title"], description=h["description"], path="guias/", blocks=blocks), sprite, header, main, footer)


# ------------------------------------------------------------------------------------------------ files
def sitemap() -> str:
    paths = CORE + ["guias/"] + [f"guias/{slug}/" for slug in T.GUIDES]
    urls = "".join(f"  <url>\n    <loc>{SITE}/{p}</loc>\n    <lastmod>{DATE}</lastmod>\n  </url>\n" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


def outputs() -> dict[Path, str]:
    files = {DOCS / "guias" / "index.html": render_hub(), DOCS / "sitemap.xml": sitemap()}
    for slug in T.GUIDES:
        files[DOCS / "guias" / slug / "index.html"] = render_guide(slug)
    return files


def validate() -> None:
    """The same limits tests/web-claims.test.mjs applies, so a mistake fails here with a clearer message."""
    seen: set[str] = set()
    for slug, g in list(T.GUIDES.items()) + [("hub", T.HUB)]:
        if len(g["title"]) > 70:
            raise GuideError(f"{slug}: el título tiene {len(g['title'])} caracteres (máximo 70)")
        if not 50 <= len(g["description"]) <= 200:
            raise GuideError(f"{slug}: la descripción tiene {len(g['description'])} caracteres (de 50 a 200)")
        if g["title"] in seen or g["description"] in seen:
            raise GuideError(f"{slug}: título o descripción repetidos")
        seen.update((g["title"], g["description"]))
    for slug, g in T.GUIDES.items():
        for other in g["related"]:
            if other not in T.GUIDES or other == slug:
                raise GuideError(f"{slug}: guía relacionada «{other}» no válida")
        for s in g["sectors"]:
            if s not in T.SECTOR:
                raise GuideError(f"{slug}: sector «{s}» no válido")
        if not (DOCS / "assets" / "img" / "shots" / f"{g['shot'][0]}.webp").exists():
            raise GuideError(f"{slug}: no existe la captura {g['shot'][0]}.webp")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="no escribe: falla si lo publicado no coincide")
    args = parser.parse_args(argv)
    try:
        validate()
        files = outputs()
    except GuideError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    stale = [path for path, text in files.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
    if args.check:
        for path in stale:
            print(f"desactualizado: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1 if stale else 0
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"{len(files)} archivos escritos ({len(stale)} cambiados): {len(T.GUIDES)} guías, el índice y el mapa del sitio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
