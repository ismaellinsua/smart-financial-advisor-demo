"""Publish the legal texts (aviso legal, condiciones del servicio, contrato de encargado) on the website.

    python ops/legal.py              # legal/datos.json → docs/aviso-legal.html, linked from every footer
    python ops/legal.py --check      # only say what is missing
    python ops/legal.py --todas      # also condiciones.html and encargado.html (see below)
    python ops/legal.py --docs ../nirkana-web   # publish into the website's own repository instead of docs/

The texts live in legal/ with gaps ({{nif}}, {{domicilio}}…); the owner's data goes in legal/datos.json (start from
legal/datos.example.json). Nothing is written while a gap or a «PENDIENTE» remains: a legal page with a placeholder
is worse than none. The page gets links in the website's footers, and the owner's identity (name, NIF, address) is
also written into the «Responsable» paragraph of privacidad.html, so that both pages say the same.

By default only the aviso legal (the website's own obligation, LSSI art. 10) is published. The conditions and the data
processing contract that a business accepts are the ones of the NirKanA app (nirkana-app, app/static/legal/, served at
https://app.nirkana.es/legal/): a second, different copy on the website would contradict them. legal/condiciones.html and
legal/encargado.html belong to the earlier Streamlit app (one payment method, a trial «of the length we tell you», daily
backups promised); --todas still publishes them, for that app only.
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
DEFAULT_PAGES = ("aviso-legal",)
VERSIONED = {"condiciones", "encargado"}  # what each business accepts, with its version
FOOTER_LINKS = (("aviso-legal", "Aviso legal"), ("condiciones", "Condiciones del servicio"))
GAP = re.compile(r"\{\{([a-z_]+)\}\}")
TITLE = re.compile(r"^<!-- titulo: (.+?) -->\n")
HOLDER = re.compile(r"(<!-- titular -->\n).*?(\n\s*<!-- /titular -->)", re.DOTALL)
UPDATED = re.compile(r"<p>Última actualización: [^<]*</p>")


class LegalError(Exception):
    """The texts cannot be published yet; the message says what is missing."""


def _table(rows: list[dict]) -> str:
    cells = "\n".join(f"          <tr><td>{html.escape(r['nombre'])}</td><td>{html.escape(r['finalidad'])}</td>"
                      f"<td>{html.escape(r['ubicacion'])}</td></tr>" for r in rows)
    return ("      <table>\n        <thead><tr><th>Proveedor</th><th>Para qué</th><th>Dónde están los datos</th></tr>"
            f"</thead>\n        <tbody>\n{cells}\n        </tbody>\n      </table>")


def render(data: dict, legal_dir: Path = ROOT / "legal", pages: tuple = PAGES) -> dict[str, str]:
    """The chosen pages, filled in. Raises LegalError listing what is still missing."""
    shell = (legal_dir / "_plantilla.html").read_text()
    bodies = {page: (legal_dir / f"{page}.html").read_text() for page in pages}
    used = set(GAP.findall(shell))
    for body in bodies.values():
        used |= set(GAP.findall(body))
    # Only what the chosen pages use has to be filled in: the aviso legal does not need the sub-processors' list.
    missing = sorted(k for k in used if isinstance(data.get(k), str) and ("PENDIENTE" in data[k] or not data[k].strip()))
    rows = data.get("subencargados") or []
    if "tabla_subencargados" in used:
        missing += [f"subencargados: {r.get('nombre', '?')}" for r in rows
                    if any("PENDIENTE" in str(v) or not str(v).strip() for v in r.values())]
        if not rows:
            missing.append("subencargados")
    values = {k: html.escape(str(v)) for k, v in data.items() if isinstance(v, str)}
    values["tabla_subencargados"] = _table(rows) if rows else ""
    rendered = {}
    for page, body in bodies.items():
        title = TITLE.match(body)
        if not title:
            raise LegalError(f"legal/{page}.html no empieza por <!-- titulo: … -->")
        content = GAP.sub(lambda m: values.get(m.group(1), m.group(0)), body[title.end():].rstrip("\n"))
        version = f" Versión {TERMS_VERSION}." if page in VERSIONED else ""
        filled = shell.replace("{{contenido}}", content).replace("{{titulo}}", html.escape(title.group(1)))
        filled = filled.replace("{{pagina}}", page).replace("{{version_texto}}", version)
        filled = GAP.sub(lambda m: values.get(m.group(1), m.group(0)), filled)
        missing += [f"{{{{{gap}}}}} en legal/{page}.html" for gap in GAP.findall(filled)]
        rendered[page] = filled
    if missing:
        raise LegalError("Falta por rellenar en legal/datos.json: " + ", ".join(dict.fromkeys(missing)))
    return rendered


def link_footers(docs: Path, pages: tuple = DEFAULT_PAGES) -> list[Path]:
    """Add the chosen legal pages next to «Aviso de privacidad» in every footer that does not have them yet."""
    changed = []
    for path in sorted(docs.rglob("*.html")):
        text = path.read_text()
        found = re.search(r'(\n(\s*)<a href="(/?)privacidad\.html">Aviso de privacidad</a>)', text)
        if not found:
            continue
        indent, root = found.group(2), found.group(3)
        extra = "".join(f'\n{indent}<a href="{root}{page}.html">{title}</a>' for page, title in FOOTER_LINKS
                        if page in pages and f'href="{root}{page}.html"' not in text)
        if extra:
            path.write_text(text[:found.end()] + extra + text[found.end():])
            changed.append(path)
    return changed


def fill_holder(docs: Path, data: dict) -> list[Path]:
    """The «Responsable» paragraph of the privacy notice gets the same identity as the aviso legal."""
    path = docs / "privacidad.html"
    if not path.exists():
        return []
    text = path.read_text()
    found = HOLDER.search(text)
    if not found:
        return []
    esc = {k: html.escape(str(data[k]), quote=True) for k in ("titular", "nif", "domicilio", "email", "fecha")}
    paragraph = (f"      <p>{esc['titular']}, titular de NirKanA (NIF {esc['nif']}; domicilio: {esc['domicilio']}). "
                 f'Contacto: <a href="mailto:{esc["email"]}">{esc["email"]}</a>.</p>')
    filled = text[:found.start()] + found.group(1) + paragraph + found.group(2) + text[found.end():]
    filled = UPDATED.sub(f"<p>Última actualización: {esc['fecha']}.</p>", filled, count=1)
    if filled == text:
        return []
    path.write_text(filled)
    return [path]


def publish(data_file: Path, docs: Path, legal_dir: Path = ROOT / "legal", pages: tuple = DEFAULT_PAGES) -> list[Path]:
    if not data_file.exists():
        raise LegalError(f"No existe {data_file}: cópialo de legal/datos.example.json y rellénalo.")
    data = json.loads(data_file.read_text())
    rendered = render(data, legal_dir, pages)
    holder = {k for k in ("titular", "nif", "domicilio", "email", "fecha") if not str(data.get(k, "")).strip()}
    if holder:
        raise LegalError("Falta por rellenar en legal/datos.json: " + ", ".join(sorted(holder)))
    written = []
    for page, text in rendered.items():
        (docs / f"{page}.html").write_text(text)
        written.append(docs / f"{page}.html")
    return written + link_footers(docs, pages) + fill_holder(docs, data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="solo comprobar qué falta")
    parser.add_argument("--data", type=Path, default=ROOT / "legal" / "datos.json")
    parser.add_argument("--todas", action="store_true",
                        help="publicar también condiciones y encargado (textos de la app anterior; ver arriba)")
    parser.add_argument("--docs", type=Path, default=ROOT / "docs",
                        help="carpeta de la web (por defecto docs/; tras separar la web, la del repositorio nirkana-web)")
    args = parser.parse_args()
    pages = PAGES if args.todas else DEFAULT_PAGES
    try:
        if args.check:
            if not args.data.exists():
                raise LegalError(f"No existe {args.data}: cópialo de legal/datos.example.json y rellénalo.")
            render(json.loads(args.data.read_text()), pages=pages)
            print("Todo listo para publicar.")
        else:
            if not (args.docs / "index.html").exists():
                raise LegalError(f"{args.docs} no parece la web (no tiene index.html).")
            for path in publish(args.data, args.docs, pages=pages):
                print(f"Escrito {path}")
            if args.todas:
                print(f"Versión de las condiciones: {TERMS_VERSION}. Para que cada negocio las acepte, define "
                      "TERMS_URL (p. ej. https://nirkana.es) en el servidor.")
            else:
                print("Solo el aviso legal. Las condiciones y el contrato de encargado son los de la app "
                      "(app.nirkana.es/legal/): rellénalos allí con ops/legal/rellenar.py de nirkana-app.")
    except LegalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
