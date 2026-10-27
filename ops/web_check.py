"""Is the public website (nirkana.es) served as it should be? DNS, HTTPS certificate, redirects and every page.

    python ops/web_check.py

Checks, from outside, what GitHub Pages and the DNS provider do and nobody else watches:
  - the domain and www point to GitHub Pages and nowhere else,
  - the certificate is valid for the domain and has at least CERT_MIN_DAYS left (GitHub renews it by itself; if the
    DNS changes, renewal fails silently and the site breaks the day it expires),
  - http:// and www. send visitors to https://domain/ (Enforce HTTPS),
  - every page in docs/ answers 200 (the published site is the one in the repository),
  - connection and HTTP protocol errors are reported per address without skipping the remaining checks,
  - with the 24-hour trial switched on (TRIAL_URL in docs/assets/site.js), the published home page offers it in the header
    and on the first screen, and the trial itself answers «ok» (it sleeps when nobody visits it: it is given up to
    TRIAL_WAIT seconds to wake up).
Environment: WEB_DOMAIN (defaults to docs/CNAME). Exit code 1 when something is wrong, so the scheduled run turns red
and GitHub emails the repository owner.
"""

import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from http.client import HTTPException
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
# GitHub Pages' addresses (docs.github.com → «Managing a custom domain for your GitHub Pages site»).
PAGES_IPS = {"185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153",
             "2606:50c0:8000::153", "2606:50c0:8001::153", "2606:50c0:8002::153", "2606:50c0:8003::153"}
CERT_MIN_DAYS = 14
TIMEOUT = 20
TRIAL_WAIT = 180   # seconds: a sleeping free instance answers 502 and takes from half a minute to a few minutes to wake up
TRIAL_RETRY = 6


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

    def checked_get(url: str, follow: bool = True) -> tuple[int, str, str] | None:
        try:
            return get(url, follow=follow)
        except (OSError, HTTPException) as exc:
            problems.append(f"Web: {url} no responde ({exc})")
            return None

    response = checked_get(f"http://{name}/", follow=False)
    if response is not None:
        status, where, _ = response
        if status not in (301, 308) or not where.startswith(home):
            problems.append(f"HTTPS: http://{name}/ no redirige a {home} (respuesta {status}): activa «Enforce HTTPS»")
    response = checked_get(f"https://www.{name}/")
    if response is not None:
        status, where, _ = response
        if status != 200 or not where.startswith(home):
            problems.append(f"Web: https://www.{name}/ no lleva a {home} (termina en {where}, {status})")
    for path in pages():
        response = checked_get(f"https://{name}{path}")
        if response is None:
            continue
        status, _, body = response
        if status != 200:
            problems.append(f"Web: https://{name}{path} responde {status}")
        elif path == "/" and "NirKanA" not in body:
            problems.append(f"Web: https://{name}/ no es la web de NirKanA")
    return problems


def trial_url() -> str:
    """The address of the 24-hour trial set in docs/assets/site.js («» when the trial is switched off)."""
    found = re.search(r'const TRIAL_URL = "([^"]*)";', (DOCS / "assets" / "site.js").read_text(encoding="utf-8"))
    return found.group(1).rstrip("/") if found else ""


def _block(html: str, start: str) -> str:
    """The piece of `html` from the first `start` to the next closing </div> («» when `start` is not there)."""
    begin = html.find(start)
    return html[begin: html.find("</div>", begin)] if begin >= 0 else ""


def home_trial_problems(html: str, url: str) -> list[str]:
    """With the trial switched on, what a visitor sees first (the header and the first screen) must offer it. The
    redesign once left it only further down the page and nobody found it."""
    if not url:
        return []
    hero = html[html.find('<section class="hero"'):] if '<section class="hero"' in html else ""
    places = {"la cabecera": _block(html, '<div class="bar-end">'), "la portada": _block(hero, '<div class="cta">')}
    return [f"Web: {place} no ofrece el botón de la prueba de 24 horas (a[data-trial])"
            for place, block in places.items() if "data-trial" not in block]


def trial_problems(url: str, get=fetch, wait: float = TRIAL_WAIT, sleep=time.sleep, clock=time.monotonic) -> list[str]:
    """The trial answers «ok» and says it is the trial. A free instance sleeps when nobody visits it, so it is asked until
    it wakes up (502, a waiting page or a reset are «not yet») and only reported after `wait` seconds."""
    if not url:
        return []
    deadline = clock() + wait
    while True:
        try:
            status, _, body = get(f"{url}/api/health")
        except (OSError, HTTPException) as exc:  # timeouts, resets and incomplete responses while the instance starts
            last = f"sin respuesta ({exc})"
        else:
            last = f"HTTP {status}"
            if status == 200:
                try:
                    health = json.loads(body)
                except ValueError:
                    health = None
                if isinstance(health, dict):
                    if health.get("ok") is True and health.get("mode") == "prueba":
                        return []
                    return [f"Prueba: {url}/api/health responde, pero no es la prueba de 24 horas ({body[:80]!r})"]
                last = "HTTP 200 sin datos (¿página de espera?)"
        if clock() >= deadline:
            return [f"Prueba: {url} no responde tras {int(wait)} s ({last}): revisa el servicio en Render"]
        sleep(TRIAL_RETRY)


def formspree_diagnostic() -> None:
    """TEMPORARY: print what Formspree answers for the contact form's id and for an id that does not exist, to a GET and
    to an EMPTY message (Formspree refuses empty messages: nothing is stored or emailed). Never fails the check."""
    found = re.search(r'formspreeId: "([^"]*)"', (DOCS / "assets" / "site.js").read_text(encoding="utf-8"))
    site = f"https://{domain()}"
    for label, form in (("formulario de la web", found.group(1) if found else ""), ("id inexistente", "nirkanacheck0")):
        url = f"https://formspree.io/f/{form}"
        for method in ("GET", "POST"):
            headers = {"User-Agent": "NirKanA web check", "Accept": "application/json"}
            data = None
            if method == "POST":
                headers.update({"Content-Type": "application/json", "Origin": site, "Referer": f"{site}/"})
                data = b"{}"
            request = urllib.request.Request(url, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                    status, where, body = response.status, response.geturl(), response.read(600)
            except urllib.error.HTTPError as exc:
                status, where, body = exc.code, url, exc.read(600)
            except (OSError, HTTPException) as exc:
                print(f"::notice::Formspree {method} {label}: sin respuesta ({exc!r})")
                continue
            print(f"::notice::Formspree {method} {label}: HTTP {status} {where} {body.decode('utf-8', 'replace')!r}")


def main() -> int:
    name = domain()
    url = trial_url()
    try:
        status, _, home = fetch(f"https://{name}/")
    except (OSError, HTTPException):  # the per-address checks below report unavailable or incomplete responses
        status, home = 0, ""
    problems = (dns_problems(name) + certificate_problems(name) + http_problems(name)
                + (home_trial_problems(home, url) if status == 200 else []) + trial_problems(url))
    for problem in problems:
        print(f"::error::{problem}" if os.environ.get("GITHUB_ACTIONS") else problem)
    if not problems:
        trial = " y la prueba de 24 horas, ofrecida y respondiendo" if url else ""
        print(f"OK {name}: DNS en GitHub Pages, certificado válido, redirecciones y {len(pages())} páginas{trial}.")
    if os.environ.get("GITHUB_WORKFLOW") == "Web":  # TEMPORARY: only in the Web workflow, never in tests
        formspree_diagnostic()
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
