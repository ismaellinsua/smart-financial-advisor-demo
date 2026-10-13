"""Builds a copy of the website that opens by double-click from a folder (no server needed).

    python ops/vista_local.py SALIDA/        # then open SALIDA/index.html

The site is written for https://nirkana.es/ (paths such as /assets/site.css and /tpv-tiendas/), which a browser cannot
follow from a folder on disk. This copy rewrites those paths to relative ones, points «Ver la demo» at the demo file
and drops the page-security meta tag (the browser treats files on disk as separate origins, which that tag would
block). The published site is never touched: this is only for looking at it. Do NOT publish the copy.
"""

import re
import shutil
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
SKIP_REWRITE = {"demo/index.html"}  # a self-contained page of its own


def relative(match: re.Match, prefix: str) -> str:
    attribute, path = match.group(1), match.group(2)
    anchor = ""
    for mark in ("#", "?"):
        if mark in path:
            path, rest = path.split(mark, 1)
            anchor = mark + rest
            break
    if path in ("", "/"):
        target = "index.html"
    elif path.endswith("/"):
        target = path.lstrip("/") + "index.html"
    else:
        target = path.lstrip("/")
    return f'{attribute}="{prefix}{target}{anchor}"'


def build(out: Path) -> int:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(DOCS, out, ignore=shutil.ignore_patterns("CNAME", "*.md", "robots.txt", "sitemap.xml"))
    pages = 0
    for page in out.rglob("*.html"):
        name = page.relative_to(out).as_posix()
        if name in SKIP_REWRITE:
            continue
        prefix = "../" * name.count("/")
        text = page.read_text(encoding="utf-8")
        text = re.sub(r'\b(href|src)="(/(?:[^"/][^"]*)?)"', lambda m, prefix=prefix: relative(m, prefix), text)
        text = re.sub(r'\s*<meta http-equiv="Content-Security-Policy"[^>]*>', "", text, flags=re.S)
        page.write_text(text, encoding="utf-8")
        pages += 1
    site = out / "assets" / "site.js"
    js = site.read_text(encoding="utf-8")
    js = js.replace('const DEMO_URL = "/demo/";',
                    'const DEMO_URL = new URL("../demo/index.html", document.currentScript.src).href;')
    js = re.sub(r"const demoOn = [^\n]+;", "const demoOn = true;", js)  # a file: address is not a /path nor https
    site.write_text(js, encoding="utf-8")
    assert "const demoOn = true;" in js and "document.currentScript" in js, "site.js changed: update ops/vista_local.py"
    (out / "LEEME.txt").write_text(
        "Copia de la web de NirKanA para verla en tu ordenador.\n\nAbre index.html con doble clic.\n"
        "«Ver la demo» abre la demo (demo/index.html). El formulario de contacto no envía nada desde aquí.\n"
        "Es solo para mirar: la web real es la carpeta docs/ del repositorio y se publica en nirkana.es.\n",
        encoding="utf-8")
    return pages


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(f"{build(Path(sys.argv[1]))} páginas listas en {sys.argv[1]}")
