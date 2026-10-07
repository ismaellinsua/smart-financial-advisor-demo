"""Is the public website (nirkana.es) served as it should be? DNS, HTTPS certificate, redirects and every page.

    python ops/web_check.py

Checks, from outside, what GitHub Pages and the DNS provider do and nobody else watches:
  - the domain and www point to GitHub Pages and nowhere else,
  - the certificate is valid for the domain and has at least CERT_MIN_DAYS left (GitHub renews it by itself; if the
    DNS changes, renewal fails silently and the site breaks the day it expires),
  - http:// and www. send visitors to https://domain/ (Enforce HTTPS),
  - every page in docs/ answers 200 (the published site is the one in the repository).
Environment: WEB_DOMAIN (defaults to docs/CNAME). Exit code 1 when something is wrong, so the scheduled run turns red
and GitHub emails the repository owner.
"""

import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
# GitHub Pages' addresses (docs.github.com → «Managing a custom domain for your GitHub Pages site»).
PAGES_IPS = {"185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153",
             "2606:50c0:8000::153", "2606:50c0:8001::153", "2606:50c0:8002::153", "2606:50c0:8003::153"}
CERT_MIN_DAYS = 14
TIMEOUT = 20


def domain() -> str:
    return (os.environ.get("WEB_DOMAIN") or (DOCS / "CNAME").read_text()).strip().lower()


def pages() -> list[str]:
    """Every page of the site as published from docs/: «/», «/privacidad.html», «/tpv-tiendas/»…"""
    found = []
    for page in sorted(DOCS.rglob("*.html")):
        relative = page.relative_to(DOCS).as_posix()
        if relative == "404.html":
            continue
        found.append("/" + (relative[: -len("index.html")] if relative.endswith("index.html") else relative))
    return found + ["/robots.txt", "/sitemap.xml"]


def resolve(host: str) -> set[str]:
    return {info[4][0] for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)}


def dns_problems(name: str, lookup=resolve) -> list[str]:
    problems = []
    for host in (name, f"www.{name}"):
        try:
            addresses = lookup(host)
        except OSError as exc:
            problems.append(f"DNS: {host} no se resuelve ({exc})")
            continue
        if not addresses:
            problems.append(f"DNS: {host} no tiene direcciones")
        elif strangers := sorted(addresses - PAGES_IPS):
            problems.append(f"DNS: {host} apunta a {', '.join(strangers)}, que no es GitHub Pages")
    return problems


def certificate_days_left(name: str) -> int:
    """Days until the certificate served for `name` expires. Raises ssl.SSLError when it is not valid for it."""
    context = ssl.create_default_context()
    with socket.create_connection((name, 443), timeout=TIMEOUT) as raw, \
            context.wrap_socket(raw, server_hostname=name) as tls:
        expires = ssl.cert_time_to_seconds(tls.getpeercert()["notAfter"])
    return int((expires - time.time()) // 86400)


def certificate_problems(name: str, days_left=certificate_days_left) -> list[str]:
    try:
        left = days_left(name)
    except (ssl.SSLError, ssl.CertificateError) as exc:
        return [f"HTTPS: el certificado de {name} no es válido ({exc})"]
    except OSError as exc:
        return [f"HTTPS: {name} no responde en el puerto 443 ({exc})"]
    if left < CERT_MIN_DAYS:
        return [f"HTTPS: el certificado de {name} caduca en {left} días (GitHub no lo ha renovado: revisa el DNS "
                "y Settings → Pages)"]
    return []


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(url: str, follow: bool = True) -> tuple[int, str, str]:
    """(status, final address, body) of a GET."""
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "NirKanA web check"})
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            return response.status, response.geturl(), response.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Location") or url, ""


def http_problems(name: str, get=fetch) -> list[str]:
    home = f"https://{name}/"
    problems = []
    status, where, _ = get(f"http://{name}/", follow=False)
    if status not in (301, 308) or not where.startswith(home):
        problems.append(f"HTTPS: http://{name}/ no redirige a {home} (respuesta {status}): activa «Enforce HTTPS»")
    status, where, _ = get(f"https://www.{name}/")
    if status != 200 or not where.startswith(home):
        problems.append(f"Web: https://www.{name}/ no lleva a {home} (termina en {where}, {status})")
    for path in pages():
        status, _, body = get(f"https://{name}{path}")
        if status != 200:
            problems.append(f"Web: https://{name}{path} responde {status}")
        elif path == "/" and "NirKanA" not in body:
            problems.append(f"Web: https://{name}/ no es la web de NirKanA")
    return problems


def main() -> int:
    name = domain()
    problems = dns_problems(name) + certificate_problems(name) + http_problems(name)
    for problem in problems:
        print(f"::error::{problem}" if os.environ.get("GITHUB_ACTIONS") else problem)
    if not problems:
        print(f"OK {name}: DNS en GitHub Pages, certificado válido, redirecciones y {len(pages())} páginas.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
