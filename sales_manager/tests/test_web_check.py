"""The website check (ops/web_check.py): what it calls a problem, with DNS, certificates and pages simulated."""

import http.server
import ssl
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

import web_check  # noqa: E402

GITHUB = {"185.199.108.153", "185.199.109.153"}


def test_every_page_of_the_site_is_checked():
    pages = web_check.pages()
    assert "/" in pages and "/privacidad.html" in pages and "/tpv-tiendas/" in pages
    assert "/404.html" not in pages and "/robots.txt" in pages
    assert web_check.domain() == "nirkana.es"


def test_dns_must_point_only_to_github_pages():
    assert web_check.dns_problems("nirkana.es", lambda host: GITHUB) == []
    moved = web_check.dns_problems("nirkana.es", lambda host: GITHUB | {"203.0.113.9"} if host.startswith("www")
                                   else GITHUB)
    assert moved == ["DNS: www.nirkana.es apunta a 203.0.113.9, que no es GitHub Pages"]

    def missing(host):
        raise OSError("Name or service not known")

    assert len(web_check.dns_problems("nirkana.es", missing)) == 2


def test_a_certificate_close_to_expiry_or_invalid_is_reported():
    assert web_check.certificate_problems("nirkana.es", lambda name: 80) == []
    assert "caduca en 3 días" in web_check.certificate_problems("nirkana.es", lambda name: 3)[0]

    def wrong_name(name):
        raise ssl.CertificateError("hostname 'nirkana.es' doesn't match 'example.com'")

    assert "no es válido" in web_check.certificate_problems("nirkana.es", wrong_name)[0]

    def closed(name):
        raise ConnectionRefusedError("refused")

    assert "no responde" in web_check.certificate_problems("nirkana.es", closed)[0]


def test_redirects_and_pages():
    def published(url, follow=True):
        if url == "http://nirkana.es/":
            return 301, "https://nirkana.es/", ""
        if url == "https://www.nirkana.es/":
            return 200, "https://nirkana.es/", "NirKanA"
        return 200, url, "NirKanA"

    assert web_check.http_problems("nirkana.es", published) == []

    def badly(url, follow=True):
        if url == "http://nirkana.es/":
            return 200, url, "NirKanA"  # Enforce HTTPS off
        if url.endswith("/privacidad.html"):
            return 404, url, ""
        if url == "https://nirkana.es/":
            return 200, url, "Site not found · GitHub Pages"
        return published(url, follow)

    problems = web_check.http_problems("nirkana.es", badly)
    assert any("Enforce HTTPS" in p for p in problems)
    assert "Web: https://nirkana.es/privacidad.html responde 404" in problems
    assert "Web: https://nirkana.es/ no es la web de NirKanA" in problems


def test_fetch_can_see_a_redirect_instead_of_following_it():
    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/":
                self.send_response(301)
                self.send_header("Location", "/destino")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"NirKanA")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert web_check.fetch(f"{base}/", follow=False)[:2] == (301, "/destino")
        assert web_check.fetch(f"{base}/") == (200, f"{base}/destino", "NirKanA")
    finally:
        server.shutdown()


def test_main_reports_and_fails(monkeypatch, capsys):
    monkeypatch.setattr(web_check, "dns_problems", lambda name: ["DNS: x"])
    monkeypatch.setattr(web_check, "certificate_problems", lambda name: [])
    monkeypatch.setattr(web_check, "http_problems", lambda name: [])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert web_check.main() == 1 and "::error::DNS: x" in capsys.readouterr().out
    monkeypatch.setattr(web_check, "dns_problems", lambda name: [])
    assert web_check.main() == 0 and "OK nirkana.es" in capsys.readouterr().out
