"""Genera el contenido de la web que sale de textos: docs/guias/ (índice y una página por guía), docs/herramientas/ (índice y una
página por calculadora gratuita) y docs/sitemap.xml.

    python ops/guias.py            # escribe las páginas y el mapa del sitio
    python ops/guias.py --check    # no escribe nada: sale con error si lo publicado no es lo que saldría de los textos

Los textos están en ops/guias_texto.py (guías) y ops/herramientas_texto.py (herramientas; las cuentas las hace
docs/assets/herramientas.js). La cabecera, el pie y los iconos se copian de una página de sector
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
import herramientas_texto as TT  # noqa: E402

ROOT = HERE.parent
DOCS = ROOT / "docs"
SITE = "https://nirkana.es"
DATE = "2026-10-30"       # fecha de la última modificación de las páginas que genera o que toca este cambio
PUBLISHED = "2026-10-21"  # cuándo salieron las primeras guías; cada guía puede traer su propio `published` y `updated`
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
REFERENCE = "tpv-tiendas/index.html"
CORE = ["", "tpv-restaurantes/", "programa-peluquerias-estetica/", "tpv-tiendas/", "programa-facturacion-autonomos/", "tpv-tienda-online/",
        "programa-gestion-pequenas-empresas/"]
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


def date_text(iso: str) -> str:
    year, month, day = (int(part) for part in iso.split("-"))
    return f"{day} de {MONTHS[month - 1]} de {year}"


def dates(guide: dict) -> tuple[str, str]:
    """(publicada, actualizada) de una guía: las primeras salieron el 21/10/2026 y solo cambia `updated` si se toca el texto."""
    published = guide.get("published", PUBLISHED)
    return published, guide.get("updated", published)


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


def chrome(demo: str, here: bool = True) -> tuple[str, str, str]:
    """Sprite, header and footer of the reference sector page; on the guides the «Guías» link is marked as the current one."""
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
    return sprite, (header.replace(link, '<a class="here" href="/guias/" aria-current="page">Guías</a>') if here else header), footer


def head(*, title: str, description: str, path: str, blocks: list[dict], article: bool = False, alt: str = "Resumen de ventas de NirKanA",
         published: str = DATE, updated: str = DATE, scripts: tuple[str, ...] = (), index: bool = True) -> str:
    url = f"{SITE}/{path}"
    image = f"{SITE}/assets/img/og.jpg"
    lines = [
        '<!doctype html>', '<html lang="es" class="js has-trial">', '<head>',
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        '  <meta http-equiv="Content-Security-Policy"', f'        content="{CSP}">',
        '  <meta name="referrer" content="strict-origin-when-cross-origin">',
        f'  <title>{esc(title)}</title>',
        f'  <meta name="description" content="{esc(description)}">',
        '  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">' if index else '  <meta name="robots" content="noindex, follow">',
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
        lines += [f'  <meta property="article:published_time" content="{published}">', f'  <meta property="article:modified_time" content="{updated}">',
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
        '  <link rel="preload" href="/assets/fonts/sora-latin-800.woff2" as="font" type="font/woff2" crossorigin>',
        '  <link rel="stylesheet" href="/assets/site.css">',
        '  <noscript><link rel="stylesheet" href="/assets/sin-js.css"></noscript>',
        '  <script src="/assets/site.js" defer></script>',
        *[f'  <script src="{src}" defer></script>' for src in scripts],
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
    published, updated = dates(g)
    sections = g["sections"]
    words = len(plain(g["lead"] + " ".join(body for _, _, body in sections) + g["nirkana"]).split())
    minutes = max(3, round(words / 200))
    crumbs = [("NirKanA", "/"), ("Guías", "/guias/"), (card_title(g["title"]), f"/{path}")]
    blocks = [
        breadcrumbs(crumbs),
        {"@context": "https://schema.org", "@type": "Article", "headline": g["h1"], "description": g["description"], "inLanguage": "es",
         "datePublished": published, "dateModified": updated, "mainEntityOfPage": {"@type": "WebPage", "@id": f"{SITE}/{path}"},
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
          <p class="guide-meta">Por el equipo de NirKanA · {"Publicada" if published == updated else "Actualizada"} el <time datetime="{updated}">{date_text(updated)}</time> · {minutes} min de lectura</p>
        </div>
      </header>
      <div class="wrap narrow guide-body">
{note}        <nav class="toc" aria-label="En esta guía"><b>En esta guía</b><ol>{toc}</ol></nav>
{tool_box(g)}{body}
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
    return page(head(title=g["title"], description=g["description"], path=path, blocks=blocks, article=True, alt=shot_alt, published=published, updated=updated),
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

{sections}{tools_section()}    <section>
      <div class="wrap faq">
        <div class="faq-side">
          <p class="eyebrow">Preguntas</p>
          <h2>Preguntas frecuentes</h2>
          <p class="sub">Por sectores: <a href="/tpv-restaurantes/">Restaurantes</a> · <a href="/programa-peluquerias-estetica/">Peluquerías</a> · <a href="/tpv-tiendas/">Tiendas</a> · <a href="/programa-facturacion-autonomos/">Autónomos</a> · <a href="/tpv-tienda-online/">Tiendas online</a> · <a href="/programa-gestion-pequenas-empresas/">Pequeñas empresas</a>.</p>
        </div>
{faq_html(h["faq"])}      </div>
    </section>

{final_band(h["demo"], "Consulta desde las guías de NirKanA")}"""
    return page(head(title=h["title"], description=h["description"], path="guias/", blocks=blocks), sprite, header, main, footer)



def tool_box(g: dict) -> str:
    """A pointer to the free calculators that go with a guide, under its table of contents."""
    slugs = g.get("tools", [])
    if not slugs:
        return ""
    items = "".join(f'<li><a href="/herramientas/{s}/">{esc(TT.TOOLS[s]["app_name"])}</a> — {esc(TT.TOOLS[s]["summary"])}</li>' for s in slugs)
    return f'        <aside class="tool-link" aria-label="Herramienta gratis"><p class="tool-link-title">Herramienta gratis</p><ul>{items}</ul></aside>\n'


def tool_cards(slugs: list[str], indent: str = "          ") -> str:
    return "".join(
        f'{indent}<article class="feat"><span class="ico"><svg class="ic"><use href="#{TT.TOOLS[s]["icon"]}"/></svg></span>\n'
        f'{indent}  <h3><a href="/herramientas/{s}/">{esc(TT.TOOLS[s]["app_name"])}</a></h3><p>{esc(TT.TOOLS[s]["summary"])}</p></article>\n' for s in slugs)


def tools_section() -> str:
    return f"""    <section class="guide-group">
      <div class="wrap">
        <div class="head">
          <h2>Herramientas gratis</h2>
        </div>
        <div class="feats tools-feats">
{tool_cards(list(TT.TOOLS))}        </div>
        <p class="guides-all"><a class="btn ghost" href="/herramientas/">Ver todas las herramientas</a></p>
      </div>
    </section>

"""


# ------------------------------------------------------------------------------------------------ free tools
DENOMINATIONS = [(50000, "Billete", "500 €"), (20000, "Billete", "200 €"), (10000, "Billete", "100 €"), (5000, "Billete", "50 €"),
                 (2000, "Billete", "20 €"), (1000, "Billete", "10 €"), (500, "Billete", "5 €"),
                 (200, "Moneda", "2 €"), (100, "Moneda", "1 €"), (50, "Moneda", "0,50 €"), (20, "Moneda", "0,20 €"),
                 (10, "Moneda", "0,10 €"), (5, "Moneda", "0,05 €"), (2, "Moneda", "0,02 €"), (1, "Moneda", "0,01 €")]
NO_JS = ('<noscript><p class="callout"><strong>Esta calculadora necesita JavaScript.</strong> Si no puedes activarlo, usa la plantilla '
         'de Excel del arqueo de caja o haz las cuentas a mano con las fórmulas de más abajo.</p></noscript>')


def field(ident: str, name: str, label: str, unit: str, placeholder: str, *, mode: str = "decimal") -> str:
    return (f'<div class="tc-field"><label for="{ident}">{esc(label)} <span class="unit">({esc(unit)})</span></label>'
            f'<input id="{ident}" type="text" inputmode="{mode}" autocomplete="off" placeholder="{placeholder}" data-in="{name}"></div>')


def widget_arqueo() -> str:
    def den(value: int, kind: str, name: str) -> str:
        return (f'<div class="den"><label for="den-{value}"><span class="sr-only">{kind} de </span>{esc(name)}</label>'
                f'<input id="den-{value}" type="text" inputmode="numeric" autocomplete="off" placeholder="0" data-valor="{value}">'
                f'<span class="sub" data-sub="{value}">0,00 €</span></div>')
    bills = "".join(den(v, k, n) for v, k, n in DENOMINATIONS if v >= 500)
    coins = "".join(den(v, k, n) for v, k, n in DENOMINATIONS if v < 500)
    return f"""      <section class="tool" aria-label="Calculadora de arqueo de caja">
        {NO_JS}
        <form class="tc" data-calc="arqueo" autocomplete="off" novalidate>
          <div class="tc-grid">
            <fieldset class="tc-block">
              <legend>1. Efectivo contado</legend>
              <p class="tc-hint">Cuántos billetes y monedas hay de cada tipo. En blanco cuenta como cero.</p>
              <div class="den-cols">
                <div role="group" aria-labelledby="den-billetes"><p class="den-title" id="den-billetes">Billetes</p>{bills}</div>
                <div role="group" aria-labelledby="den-monedas"><p class="den-title" id="den-monedas">Monedas</p>{coins}</div>
              </div>
              <p class="tc-total"><span>Total contado</span> <strong data-out="contado">0,00 €</strong></p>
            </fieldset>
            <div class="tc-side">
              <fieldset class="tc-block">
                <legend>2. Lo que debería haber</legend>
                {field("c-fondo", "fondo", "Fondo de caja con el que empezaste", "€", "0,00")}
                {field("c-ventas", "ventas", "Ventas cobradas en efectivo", "€", "0,00")}
                {field("c-entradas", "entradas", "Otras entradas de efectivo", "€", "0,00")}
                {field("c-salidas", "salidas", "Salidas de efectivo: proveedores, retiradas, devoluciones", "€", "0,00")}
                <p class="tc-total"><span>Efectivo esperado</span> <strong data-out="esperado">0,00 €</strong></p>
              </fieldset>
              <div class="tc-estado" role="status" aria-live="polite" data-out="estado" data-estado="vacio">
                <p class="tc-estado-titulo" data-out="estado-titulo">Escribe lo que has contado y lo que debería haber.</p>
                <p class="tc-estado-detalle" data-out="estado-detalle"></p>
              </div>
              <fieldset class="tc-block">
                <legend>3. Fondo para mañana (opcional)</legend>
                {field("c-dejar", "dejar", "Fondo que dejas en la caja", "€", "0,00")}
                <p class="tc-retirar" data-out="retirar" hidden></p>
              </fieldset>
            </div>
          </div>
          <div class="tc-actions">
            <button type="reset" class="btn ghost small">Poner a cero</button>
            <button type="button" class="btn ghost small" data-imprimir>Imprimir o guardar en PDF</button>
            <a class="btn ghost small" href="/descargas/plantilla-arqueo-de-caja.xlsx" download data-evento="plantilla-arqueo" data-evento-titulo="Descarga la plantilla de arqueo de caja"><svg class="ic"><use href="#i-download"/></svg> Plantilla de Excel</a>
          </div>
        </form>
      </section>
"""


def widget_margen() -> str:
    return f"""      <section class="tool" aria-label="Calculadora de margen y precio de venta">
        {NO_JS}
        <form class="tc" data-calc="margen" data-modo="margen" autocomplete="off" novalidate>
          <div class="tc-grid">
            <fieldset class="tc-block">
              <legend>1. Tus datos</legend>
              <div class="seg" role="radiogroup" aria-label="Qué quieres calcular">
                <input type="radio" id="modo-margen" name="modo" value="margen" checked><label for="modo-margen">Quiero un margen</label>
                <input type="radio" id="modo-precio" name="modo" value="precio"><label for="modo-precio">Tengo el precio</label>
              </div>
              {field("m-coste", "coste", "Coste de cada unidad, sin IVA", "€", "10,00")}
              <div data-solo="margen">{field("m-margen", "margen", "Margen que quieres ganar", "%", "40")}</div>
              <div data-solo="precio" hidden>
                {field("m-precio", "precio", "Precio de venta", "€", "24,99")}
                <div class="tc-field"><label for="m-incluido">Ese precio</label>
                  <select id="m-incluido" data-in="iva-incluido"><option value="si" selected>Lleva el IVA incluido</option><option value="no">Es sin IVA</option></select></div>
              </div>
              <div class="tc-field"><label for="m-iva">IVA del producto</label>
                <select id="m-iva" data-in="iva"><option value="21" selected>21 % (general)</option><option value="10">10 % (reducido)</option><option value="4">4 % (superreducido)</option><option value="0">0 % (exento)</option></select></div>
              {field("m-descuento", "descuento", "Descuento que quieres probar, opcional", "%", "0")}
              <div class="tc-actions"><button type="reset" class="btn ghost small">Poner a cero</button></div>
            </fieldset>
            <div class="tc-block tc-results">
              <p class="sr-only" role="status" data-out="resumen"></p>
              <p class="tc-hint" data-out="aviso">Escribe el coste y el margen que quieres (o el precio de venta) y aquí verás el resultado.</p>
              <div data-out="resultados" hidden>
                <dl class="result-cards">
                  <div class="rc main"><dt>Precio al público, con IVA</dt><dd data-out="pvp"></dd></div>
                  <div class="rc"><dt>Precio sin IVA</dt><dd data-out="neto"></dd></div>
                  <div class="rc"><dt>IVA</dt><dd data-out="iva"></dd></div>
                  <div class="rc"><dt>Beneficio por unidad</dt><dd data-out="beneficio"></dd></div>
                  <div class="rc"><dt>Margen sobre el precio</dt><dd data-out="margen"></dd></div>
                  <div class="rc"><dt>Recargo sobre el coste</dt><dd data-out="recargo"></dd></div>
                </dl>
                <div class="tc-descuento" data-out="descuento" hidden>
                  <p class="tc-sub">Con el descuento</p>
                  <dl class="result-cards small">
                    <div class="rc"><dt>Precio al público</dt><dd data-out="d-pvp"></dd></div>
                    <div class="rc"><dt>Beneficio por unidad</dt><dd data-out="d-beneficio"></dd></div>
                    <div class="rc"><dt>Margen</dt><dd data-out="d-margen"></dd></div>
                  </dl>
                  <p class="tc-aviso" data-out="d-texto"></p>
                </div>
              </div>
            </div>
          </div>
        </form>
      </section>
"""


def render_tool(slug: str) -> str:
    t = TT.TOOLS[slug]
    path = f"herramientas/{slug}/"
    sprite, header, footer = chrome(t["demo"], here=False)
    crumbs = [("NirKanA", "/"), ("Herramientas", "/herramientas/"), (t["app_name"], f"/{path}")]
    blocks = [
        breadcrumbs(crumbs),
        {"@context": "https://schema.org", "@type": "WebApplication", "name": t["app_name"], "url": f"{SITE}/{path}", "description": t["description"],
         "applicationCategory": "BusinessApplication", "operatingSystem": "Cualquiera, en el navegador", "inLanguage": "es", "isAccessibleForFree": True,
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
         "publisher": {"@type": "Organization", "name": "NirKanA", "url": f"{SITE}/"}},
        faq_block(t["faq"]),
    ]
    widget = widget_arqueo() if t["widget"] == "arqueo" else widget_margen()
    body = "\n".join(f'        <section class="guide-sec" id="{sid}">\n          <h2>{esc(h2)}</h2>{text.rstrip()}\n        </section>\n' for sid, h2, text in t["sections"])
    shot_id, shot_alt, shot_caption = t["shot"]
    sector_links = " · ".join(f'<a href="{T.SECTOR[x][0]}">{esc(T.SECTOR[x][1])}</a>' for x in t["sectors"])
    related = "".join(f'<li><a href="/guias/{r}/">{esc(card_title(T.GUIDES[r]["title"]))}</a> — {esc(T.GUIDES[r]["summary"])}</li>' for r in t["related"])
    others = "".join(f'<li><a href="/herramientas/{o}/">{esc(TT.TOOLS[o]["app_name"])}</a> — {esc(TT.TOOLS[o]["summary"])}</li>' for o in TT.TOOLS if o != slug)
    main = f"""    <article class="guide tool-page">
      <header class="guide-head">
        <div class="wrap narrow">
          <nav class="crumbs" aria-label="Estás en"><a href="/">NirKanA</a> <span aria-hidden="true">›</span> <a href="/herramientas/">Herramientas</a> <span aria-hidden="true">›</span> {esc(t["app_name"])}</nav>
          <p class="eyebrow">Herramienta gratis</p>
          <h1>{esc(t["h1"])}</h1>
          <p class="lead">{esc(t["lead"])}</p>
          <p class="guide-meta">Gratis · Sin registro · No se envía ni se guarda nada</p>
        </div>
      </header>
      <div class="wrap tool-wrap">
{widget}      </div>
      <div class="wrap narrow guide-body">
{body}
        <aside class="guide-cta" aria-label="Probar NirKanA">
          <p class="cta-title">Que estas cuentas las haga el programa</p>
          <p class="only-trial">Abre NirKanA 24 horas gratis, sin tarjeta, con un negocio de ejemplo y compruébalo tú. Si te encaja, te lo dejamos listo con tus productos o tus servicios.</p>
          <p class="no-trial">Cuéntanos tu negocio y te lo dejamos listo con tus productos o tus servicios. Sin compromiso.</p>
          {cta_buttons().format(demo=t["demo"])}
          {mail_line(t["subject"])}
        </aside>

        <section class="guide-sec nk" id="nirkana">
          <h2>Cómo lo hace NirKanA</h2>
          <div class="nk-box">{t["nirkana"].rstrip()}
            <figure class="shot guide-shot">
              <img src="/assets/img/shots/{shot_id}.webp" width="1200" height="750" alt="{esc(shot_alt)}" loading="lazy">
              <figcaption>{esc(shot_caption)}</figcaption>
            </figure>
            <p class="nk-more">Más sobre esto: {sector_links}.</p>
          </div>
        </section>

        <section class="guide-sec" id="preguntas">
          <h2>Preguntas frecuentes</h2>
{faq_html(t["faq"])}        </section>

        <section class="guide-sec" id="relacionadas">
          <h2>Sigue leyendo</h2>
          <ul class="related">{related}{others}</ul>
        </section>
      </div>
    </article>

{final_band(t["demo"], t["subject"])}"""
    return page(head(title=t["title"], description=t["description"], path=path, blocks=blocks, alt=shot_alt, scripts=("/assets/herramientas.js",)),
                sprite, header, main, footer)


def render_tools_hub() -> str:
    h = TT.HUB
    sprite, header, footer = chrome(h["demo"], here=False)
    items = [{"@type": "ListItem", "position": i, "url": f"{SITE}/herramientas/{slug}/", "name": t["app_name"]} for i, (slug, t) in enumerate(TT.TOOLS.items(), 1)]
    blocks = [
        breadcrumbs([("NirKanA", "/"), ("Herramientas", "/herramientas/")]),
        {"@context": "https://schema.org", "@type": "CollectionPage", "name": h["h1"], "description": h["description"], "inLanguage": "es",
         "url": f"{SITE}/herramientas/", "isPartOf": {"@type": "WebSite", "name": "NirKanA", "url": f"{SITE}/"},
         "mainEntity": {"@type": "ItemList", "itemListElement": items}},
        faq_block(h["faq"]),
    ]
    main = f"""    <section class="sub-hero">
      <div class="wrap">
        <nav class="crumbs" aria-label="Estás en"><a href="/">NirKanA</a> <span aria-hidden="true">›</span> Herramientas</nav>
        <h1>{esc(h["h1"])}</h1>
        <p class="sub">{esc(h["lead"])}</p>
        {cta_buttons().format(demo=h["demo"])}
      </div>
    </section>

    <section class="guide-group">
      <div class="wrap">
        <div class="head">
          <h2>Calculadoras</h2>
        </div>
        <div class="feats tools-feats">
{tool_cards(list(TT.TOOLS))}        </div>
      </div>
    </section>

    <section class="guide-group">
      <div class="wrap narrow">
        <h2>Para qué sirven</h2>
        <p>Cuadrar la caja y poner precios son dos cuentas que un negocio hace todas las semanas y en las que un error pequeño cuesta dinero. Estas herramientas las hacen contigo, con las fórmulas a la vista, para que entiendas el resultado y no solo lo copies.</p>
        <p>Si prefieres leer antes de calcular, cada una tiene su guía: el <a href="/guias/arqueo-y-cierre-de-caja/">arqueo y cierre de caja</a> paso a paso y cómo <a href="/guias/calcular-el-margen-de-un-producto/">calcular el margen de un producto y fijar el precio</a>.</p>
        <p>Y cuando quieras que las ventas, el stock y la caja se calculen solos mientras trabajas, puedes probar <a href="/">NirKanA</a> 24 horas gratis, sin tarjeta.</p>
      </div>
    </section>

    <section>
      <div class="wrap faq">
        <div class="faq-side">
          <p class="eyebrow">Preguntas</p>
          <h2>Preguntas frecuentes</h2>
          <p class="sub">También en <a href="/guias/">las guías</a>.</p>
        </div>
{faq_html(h["faq"])}      </div>
    </section>

{final_band(h["demo"], "Consulta desde las herramientas de NirKanA")}"""
    return page(head(title=h["title"], description=h["description"], path="herramientas/", blocks=blocks), sprite, header, main, footer)


# ------------------------------------------------------------------------------------------------ TikTok landing
def render_tiktok() -> str:
    """The page behind the profile link of TikTok: noindex, no cookies and no query strings; the visits are counted by path and the
    three buttons by event (see site.js, data-evento), so the effect of the videos can be read in GoatCounter."""
    t = T.TIKTOK
    sprite, header, footer = chrome(t["demo"], here=False)
    shot_id, shot_alt, shot_name = t["shot"]
    buttons = (cta_buttons().format(demo=t["demo"])
               .replace("data-trial href", 'data-trial data-evento="tiktok-prueba" data-evento-titulo="TikTok: clic en Probar gratis" href')
               .replace('data-demo="' + t["demo"] + '" href', 'data-demo="' + t["demo"] + '" data-evento="tiktok-demo" data-evento-titulo="TikTok: clic en Ver la demo" href'))
    mail = mail_line(t["subject"]).replace("<a data-email ", '<a data-email data-evento="tiktok-correo" data-evento-titulo="TikTok: clic en el correo" ')
    guides_title, guides_summary, guides_icon = t["guides"]
    free = tool_cards(list(TT.TOOLS), indent="          ") + (
        f'          <article class="feat"><span class="ico"><svg class="ic"><use href="#{guides_icon}"/></svg></span>\n'
        f'            <h3><a href="/guias/">{esc(guides_title)}</a></h3><p>{esc(guides_summary)}</p></article>\n')
    sectors = "".join(
        f'          <article class="feat"><span class="ico"><svg class="ic"><use href="#{icon}"/></svg></span>\n'
        f'            <h3><a href="{T.SECTOR[key][0]}">{esc(T.SECTOR[key][1])}</a></h3><p>{esc(summary)}</p></article>\n' for key, icon, summary in t["sectors"])
    main = f"""    <section class="sub-hero">
      <div class="wrap sub-hero-grid">
        <div class="sub-hero-copy">
          <p class="eyebrow">{esc(t["eyebrow"])}</p>
          <h1>{esc(t["h1"])}</h1>
          <p class="sub">{esc(t["lead"])}</p>
          {buttons}
          {mail}
        </div>
        <figure class="screen sub-hero-shot">
          <div class="chrome"><i></i><i></i><i></i><span>nirkana · {esc(shot_name)}</span></div>
          <img src="/assets/img/shots/{shot_id}.webp" width="1200" height="750" alt="{esc(shot_alt)}" fetchpriority="high">
        </figure>
      </div>
    </section>

    <section>
      <div class="wrap">
        <div class="head">
          <h2>{esc(t["free_title"])}</h2>
          <p class="sub">{esc(t["free_lead"])}</p>
        </div>
        <div class="feats">
{free}        </div>
      </div>
    </section>

    <section class="band">
      <div class="wrap">
        <div class="head">
          <h2>{esc(t["sectors_title"])}</h2>
        </div>
        <div class="feats">
{sectors}        </div>
      </div>
    </section>

{final_band(t["demo"], t["subject"])}"""
    return page(head(title=t["title"], description=t["description"], path="tiktok/", blocks=[], index=False, alt=shot_alt), sprite, header, main, footer)


# ------------------------------------------------------------------------------------------------ files
def sitemap() -> str:
    paths = [(p, DATE if p == "programa-peluquerias-estetica/" else "2026-10-27") for p in CORE] + [("guias/", DATE), ("herramientas/", "2026-10-27")] + [(f"guias/{slug}/", dates(g)[1]) for slug, g in T.GUIDES.items()] \
        + [(f"herramientas/{slug}/", t.get("updated", "2026-10-27")) for slug, t in TT.TOOLS.items()]
    urls = "".join(f"  <url>\n    <loc>{SITE}/{p}</loc>\n    <lastmod>{day}</lastmod>\n  </url>\n" for p, day in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


def outputs() -> dict[Path, str]:
    files = {DOCS / "guias" / "index.html": render_hub(), DOCS / "herramientas" / "index.html": render_tools_hub(), DOCS / "tiktok" / "index.html": render_tiktok(),
             DOCS / "sitemap.xml": sitemap()}
    for slug in T.GUIDES:
        files[DOCS / "guias" / slug / "index.html"] = render_guide(slug)
    for slug in TT.TOOLS:
        files[DOCS / "herramientas" / slug / "index.html"] = render_tool(slug)
    return files


def validate() -> None:
    """The same limits tests/web-claims.test.mjs applies, so a mistake fails here with a clearer message."""
    seen: set[str] = set()
    for slug, g in list(T.GUIDES.items()) + [("hub", T.HUB), ("tiktok", T.TIKTOK)] + [(f"herramienta {k}", v) for k, v in TT.TOOLS.items()] + [("herramientas", TT.HUB)]:
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
        for tool_slug in g.get("tools", []):
            if tool_slug not in TT.TOOLS:
                raise GuideError(f"{slug}: herramienta «{tool_slug}» no válida")
        published, updated = dates(g)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published) or not published <= updated <= DATE:
            raise GuideError(f"{slug}: fechas no válidas ({published} → {updated}); la última no puede pasar de {DATE}")
        if not (DOCS / "assets" / "img" / "shots" / f"{g['shot'][0]}.webp").exists():
            raise GuideError(f"{slug}: no existe la captura {g['shot'][0]}.webp")
    for key, _, _ in T.TIKTOK["sectors"]:
        if key not in T.SECTOR:
            raise GuideError(f"tiktok: sector «{key}» no válido")
    if not (DOCS / "assets" / "img" / "shots" / f"{T.TIKTOK['shot'][0]}.webp").exists():
        raise GuideError(f"tiktok: no existe la captura {T.TIKTOK['shot'][0]}.webp")
    for slug, t in TT.TOOLS.items():
        for other in t["related"]:
            if other not in T.GUIDES:
                raise GuideError(f"herramienta {slug}: guía relacionada «{other}» no válida")
        for s in t["sectors"]:
            if s not in T.SECTOR:
                raise GuideError(f"herramienta {slug}: sector «{s}» no válido")
        if t["widget"] not in ("arqueo", "margen"):
            raise GuideError(f"herramienta {slug}: widget «{t['widget']}» desconocido")
        if not (DOCS / "assets" / "img" / "shots" / f"{t['shot'][0]}.webp").exists():
            raise GuideError(f"herramienta {slug}: no existe la captura {t['shot'][0]}.webp")


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
    print(f"{len(files)} archivos escritos ({len(stale)} cambiados): {len(T.GUIDES)} guías, {len(TT.TOOLS)} herramientas, sus índices, la entrada de TikTok y el mapa del sitio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
