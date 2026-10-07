"""Publish the legal texts (aviso legal, condiciones del servicio, contrato de encargado) on the website.

    python ops/legal.py              # legal/datos.json → docs/aviso-legal.html, condiciones.html, encargado.html
    python ops/legal.py --check      # only say what is missing

The texts live in legal/ with gaps ({{nif}}, {{domicilio}}…); the owner's data goes in legal/datos.json (start from
legal/datos.example.json). Nothing is written while a gap or a «PENDIENTE» remains: a legal page with a placeholder
is worse than none. The pages get links in the website's footers; the app asks each business to accept the
conditions once TERMS_URL points at the website.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sales_manager"))

from core.legal import TERMS_VERSION  # noqa: E402

PAGES = ("aviso-legal", "condiciones", "encargado")
VERSIONED = {"condiciones", "encargado"}  # what each business accepts, with its version
FOOTER_LINKS = (("aviso-legal", "Aviso legal"), ("condiciones", "Condiciones del servicio"))
GAP = re.compile(r"\{\{([a-z_]+)\}\}")
TITLE = re.compile(r"^<!-- titulo: (.+?) -->\n")


class LegalError(Exception):
    """The texts cannot be published yet; the message says what is missing."""


def _table(rows: list[dict]) -> str:
    cells = "\n".join(f"          <tr><td>{html.escape(r['nombre'])}</td><td>{html.escape(r['finalidad'])}</td>"
                      f"<td>{html.escape(r['ubicacion'])}</td></tr>" for r in rows)
    return ("      <table>\n        <thead><tr><th>Proveedor</th><th>Para qué</th><th>Dónde están los datos</th></tr>"
            f"</thead>\n        <tbody>\n{cells}\n        </tbody>\n      </table>")


def render(data: dict, legal_dir: Path = ROOT / "legal") -> dict[str, str]:
    """Every page, filled in. Raises LegalError listing what is still missing."""
    missing = sorted({k for k, v in data.items() if isinstance(v, str) and ("PENDIENTE" in v or not v.strip())})
    rows = data.get("subencargados") or []
    missing += [f"subencargados: {r.get('nombre', '?')}" for r in rows
                if any("PENDIENTE" in str(v) or not str(v).strip() for v in r.values())]
    if not rows:
        missing.append("subencargados")
    values = {k: html.escape(str(v)) for k, v in data.items() if isinstance(v, str)}
    values["tabla_subencargados"] = _table(rows) if rows else ""
    shell = (legal_dir / "_plantilla.html").read_text()
    pages = {}
    for page in PAGES:
        body = (legal_dir / f"{page}.html").read_text()
        title = TITLE.match(body)
        if not title:
            raise LegalError(f"legal/{page}.html no empieza por <!-- titulo: … -->")
        content = GAP.sub(lambda m: values.get(m.group(1), m.group(0)), body[title.end():].rstrip("\n"))
        version = f" Versión {TERMS_VERSION}." if page in VERSIONED else ""
        filled = shell.replace("{{contenido}}", content).replace("{{titulo}}", html.escape(title.group(1)))
        filled = filled.replace("{{pagina}}", page).replace("{{version_texto}}", version)
        filled = GAP.sub(lambda m: values.get(m.group(1), m.group(0)), filled)
        missing += [f"{{{{{gap}}}}} en legal/{page}.html" for gap in GAP.findall(filled)]
        pages[page] = filled
    if missing:
        raise LegalError("Falta por rellenar en legal/datos.json: " + ", ".join(dict.fromkeys(missing)))
    return pages


def link_footers(docs: Path) -> list[Path]:
    """Add the legal pages next to «Aviso de privacidad» in every footer that does not have them yet."""
    changed = []
    for path in sorted(docs.rglob("*.html")):
        text = path.read_text()
        if "aviso-legal.html" in text:
            continue
        found = re.search(r'(\n(\s*)<a href="(/?)privacidad\.html">Aviso de privacidad</a>)', text)
        if not found:
            continue
        indent, root = found.group(2), found.group(3)
        extra = "".join(f'\n{indent}<a href="{root}{page}.html">{title}</a>' for page, title in FOOTER_LINKS)
        path.write_text(text[:found.end()] + extra + text[found.end():])
        changed.append(path)
    return changed


def publish(data_file: Path, docs: Path, legal_dir: Path = ROOT / "legal") -> list[Path]:
    if not data_file.exists():
        raise LegalError(f"No existe {data_file}: cópialo de legal/datos.example.json y rellénalo.")
    pages = render(json.loads(data_file.read_text()), legal_dir)
    written = []
    for page, text in pages.items():
        (docs / f"{page}.html").write_text(text)
        written.append(docs / f"{page}.html")
    return written + link_footers(docs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="solo comprobar qué falta")
    parser.add_argument("--data", type=Path, default=ROOT / "legal" / "datos.json")
    args = parser.parse_args()
    try:
        if args.check:
            if not args.data.exists():
                raise LegalError(f"No existe {args.data}: cópialo de legal/datos.example.json y rellénalo.")
            render(json.loads(args.data.read_text()))
            print("Todo listo para publicar.")
        else:
            for path in publish(args.data, ROOT / "docs"):
                print(f"Escrito {path.relative_to(ROOT)}")
            print(f"Versión de las condiciones: {TERMS_VERSION}. Para que cada negocio las acepte, define "
                  "TERMS_URL (p. ej. https://nirkana.es) en el servidor.")
    except LegalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
