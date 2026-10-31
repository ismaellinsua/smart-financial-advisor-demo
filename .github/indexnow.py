"""Avisa a IndexNow de las páginas de nirkana.es que cambian en el último commit (o de todas, con TODAS=true).

Solo envía direcciones que están en docs/sitemap.xml: lo que no se indexa (demo, TikTok, privacidad, 404) nunca se anuncia.
La clave es el nombre del único archivo docs/<32 hex>.txt, cuyo contenido es la propia clave (así lo pide IndexNow).
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE = "https://nirkana.es"
DOCS = Path("docs")


def key() -> str:
    found = [p for p in DOCS.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", p.stem) and p.read_text().strip() == p.stem]
    if len(found) != 1:
        sys.exit(f"Tiene que haber exactamente un archivo de clave docs/<clave>.txt; hay {len(found)}.")
    return found[0].stem


def sitemap_urls() -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", (DOCS / "sitemap.xml").read_text(encoding="utf-8"))


def changed_urls() -> list[str]:
    diff = subprocess.run(["git", "diff", "--name-only", "HEAD^", "HEAD", "--", "docs"], capture_output=True, text=True, check=False)
    urls = set()
    for name in diff.stdout.split():
        path = Path(name)
        if path.name == "index.html":
            rel = path.parent.relative_to(DOCS).as_posix()
            urls.add(f"{SITE}/" if rel == "." else f"{SITE}/{rel}/")
    return sorted(urls)


def main() -> None:
    k = key()
    public = sitemap_urls()
    wanted = public if os.environ.get("TODAS") == "true" else [u for u in changed_urls() if u in public]
    if not wanted:
        print("Ninguna página del mapa del sitio ha cambiado: no hay nada que avisar.")
        return
    body = json.dumps({"host": "nirkana.es", "key": k, "keyLocation": f"{SITE}/{k}.txt", "urlList": wanted}).encode()
    request = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https host
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    print(f"IndexNow respondió {status} para {len(wanted)} páginas:")
    for url in wanted:
        print(f"  {url}")
    # 200 y 202: recibido. 422: la clave aún no se ve en la web (primera publicación); se reintenta en el siguiente cambio.
    if status not in (200, 202):
        print(f"::warning::IndexNow no aceptó el aviso (código {status}).")


if __name__ == "__main__":
    main()
