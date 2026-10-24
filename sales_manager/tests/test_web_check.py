"""The website check (ops/web_check.py): what it calls a problem, with DNS, certificates and pages simulated."""

import http.client
import http.server
import ssl
import sys
import threading
import urllib.error
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("failed_url", [
    "http://nirkana.es/", "https://www.nirkana.es/", "https://nirkana.es/",
    "https://nirkana.es/privacidad.html", "https://nirkana.es/sitemap.xml",
])
@pytest.mark.parametrize("failure", [
    pytest.param(lambda: TimeoutError("timed out"), id="timeout"),
    pytest.param(lambda: urllib.error.URLError("DNS unavailable"), id="dns"),
    pytest.param(lambda: http.client.IncompleteRead(b"", 12), id="incomplete-response"),
    pytest.param(lambda: http.client.BadStatusLine("invalid response"), id="invalid-response"),
])
def test_connection_failures_are_reported_without_skipping_other_pages(monkeypatch, failed_url, failure):
    paths = ["/", "/privacidad.html", "/sitemap.xml"]
    monkeypatch.setattr(web_check, "pages", lambda: paths)
    visited = []

    def published(url, follow=True):
        visited.append(url)
        if url == failed_url:
            raise failure()
        if url == "http://nirkana.es/":
            assert follow is False
            return 301, "https://nirkana.es/", ""
        return 200, "https://nirkana.es/" if "www." in url else url, "NirKanA"

    problems = web_check.http_problems("nirkana.es", published)
    assert len(problems) == 1
    assert failed_url in problems[0] and "no responde" in problems[0]
    assert visited == ["http://nirkana.es/", "https://www.nirkana.es/"] + [f"https://nirkana.es{p}" for p in paths]


def test_connection_failures_do_not_hide_other_http_or_content_errors(monkeypatch):
    monkeypatch.setattr(web_check, "pages", lambda: ["/", "/privacidad.html", "/sitemap.xml"])

    def broken(url, follow=True):
        if url.startswith("http:"):
            raise TimeoutError("timed out")
        if url.endswith("/privacidad.html"):
            return 404, url, ""
        return 200, "https://nirkana.es/" if "www." in url else url, "Site not found"

    problems = web_check.http_problems("nirkana.es", broken)
    assert len(problems) == 3
    assert "http://nirkana.es/" in problems[0] and "no responde" in problems[0]
    assert "Web: https://nirkana.es/ no es la web de NirKanA" in problems
    assert "Web: https://nirkana.es/privacidad.html responde 404" in problems


def test_programming_errors_are_not_silenced_as_network_failures():
    def broken(url, follow=True):
        raise ValueError("programming error")

    with pytest.raises(ValueError, match="programming error"):
        web_check.http_problems("nirkana.es", broken)


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


def test_the_home_offers_the_trial_in_the_header_and_on_the_first_screen():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    url = web_check.trial_url()
    assert url == "https://nirkana-prueba.onrender.com"
    assert web_check.home_trial_problems(html, url) == []
    assert web_check.home_trial_problems("<html></html>", "") == []  # trial switched off: nothing to offer

    # The way the redesign lost it: the button is not in the header, or not in the first screen's buttons.
    header_button = '<a class="btn small magnet only-trial" data-trial href="#contacto">Probar gratis</a>'
    hero_button = '<a class="btn magnet only-trial" data-trial href="#contacto">Probar gratis 24 horas'
    assert header_button in html and hero_button in html
    assert web_check.home_trial_problems(html.replace(header_button, ""), url) == [
        "Web: la cabecera no ofrece el botón de la prueba de 24 horas (a[data-trial])"]
    assert web_check.home_trial_problems(html.replace(hero_button, hero_button.replace(" data-trial", "")), url) == [
        "Web: la portada no ofrece el botón de la prueba de 24 horas (a[data-trial])"]
    assert len(web_check.home_trial_problems("<html><body>NirKanA</body></html>", url)) == 2


class _Trial:
    """A trial that answers what `answers` says, one after another, on a clock that only moves when the check sleeps."""

    def __init__(self, *answers):
        self.answers, self.now, self.asked = list(answers), 0.0, 0

    def get(self, url, follow=True):
        assert url == "https://prueba.example/api/health"
        self.asked += 1
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def check(self, wait=60):
        return web_check.trial_problems("https://prueba.example", self.get, wait, self.sleep, lambda: self.now)

    def sleep(self, seconds):
        self.now += seconds


OK = (200, "u", '{"ok": true, "mode": "prueba"}')


def test_a_sleeping_trial_is_given_time_to_wake_up():
    trial = _Trial((502, "u", ""), OSError("connection reset"), (200, "u", "<h1>Starting…</h1>"), OK)
    assert trial.check() == [] and trial.asked == 4
    assert _Trial(OK).check() == []
    assert web_check.trial_problems("", lambda url: 1 / 0) == []  # trial switched off: nothing is asked


def test_an_incomplete_http_response_is_retried_while_the_trial_wakes_up():
    trial = _Trial(http.client.IncompleteRead(b"", 12), OK)
    assert trial.check() == [] and trial.asked == 2
    down = _Trial(http.client.BadStatusLine("invalid response")).check(wait=12)
    assert len(down) == 1 and "sin respuesta" in down[0]


def test_a_trial_that_never_wakes_up_or_is_not_the_trial_is_reported():
    never = _Trial((502, "u", ""))
    assert never.check(wait=30) == ["Prueba: https://prueba.example no responde tras 30 s (HTTP 502): revisa el servicio en Render"]
    assert never.asked == 6  # every web_check.TRIAL_RETRY seconds until the wait is over
    down = _Trial(OSError("timed out")).check(wait=12)
    assert "sin respuesta (timed out)" in down[0]
    other = _Trial((200, "u", '{"ok": true, "mode": "produccion"}')).check()
    assert other == ['Prueba: https://prueba.example/api/health responde, pero no es la prueba de 24 horas '
                     "('{\"ok\": true, \"mode\": \"produccion\"}')"]
    broken = _Trial((200, "u", '{"ok": false, "mode": "prueba"}')).check()
    assert "no es la prueba" in broken[0]


def test_main_reports_and_fails(monkeypatch, capsys):
    monkeypatch.setattr(web_check, "dns_problems", lambda name: ["DNS: x"])
    monkeypatch.setattr(web_check, "certificate_problems", lambda name: [])
    monkeypatch.setattr(web_check, "http_problems", lambda name: [])
    monkeypatch.setattr(web_check, "fetch", lambda url, follow=True: (200, url, "<html></html>"))
    monkeypatch.setattr(web_check, "trial_url", lambda: "")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert web_check.main() == 1 and "::error::DNS: x" in capsys.readouterr().out
    monkeypatch.setattr(web_check, "dns_problems", lambda name: [])
    assert web_check.main() == 0 and "OK nirkana.es" in capsys.readouterr().out


def test_main_also_reports_a_home_without_the_trial_and_a_trial_that_is_down(monkeypatch, capsys):
    monkeypatch.setattr(web_check, "dns_problems", lambda name: [])
    monkeypatch.setattr(web_check, "certificate_problems", lambda name: [])
    monkeypatch.setattr(web_check, "http_problems", lambda name: [])
    monkeypatch.setattr(web_check, "fetch", lambda url, follow=True: (200, url, "<html><body>NirKanA</body></html>"))
    monkeypatch.setattr(web_check, "trial_url", lambda: "https://prueba.example")
    monkeypatch.setattr(web_check, "trial_problems", lambda url: ["Prueba: caída"])
    assert web_check.main() == 1
    printed = capsys.readouterr().out
    assert "la cabecera no ofrece" in printed and "la portada no ofrece" in printed and "Prueba: caída" in printed
    monkeypatch.setattr(web_check, "fetch", lambda url, follow=True: (200, url, (ROOT / "docs" / "index.html").read_text("utf-8")))
    monkeypatch.setattr(web_check, "trial_problems", lambda url: [])
    assert web_check.main() == 0 and "la prueba de 24 horas, ofrecida y respondiendo" in capsys.readouterr().out


def test_main_still_reports_dns_and_trial_when_every_http_request_fails(monkeypatch, capsys):
    def down(url, follow=True):
        raise http.client.IncompleteRead(b"", 12)

    original_http_problems = web_check.http_problems
    monkeypatch.setattr(web_check, "pages", lambda: ["/", "/sitemap.xml"])
    monkeypatch.setattr(web_check, "dns_problems", lambda name: ["DNS: no se resuelve"])
    monkeypatch.setattr(web_check, "certificate_problems", lambda name: [])
    monkeypatch.setattr(web_check, "http_problems", lambda name: original_http_problems(name, get=down))
    monkeypatch.setattr(web_check, "fetch", down)
    monkeypatch.setattr(web_check, "trial_url", lambda: "https://prueba.example")
    monkeypatch.setattr(web_check, "trial_problems", lambda url: ["Prueba: caída"])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert web_check.main() == 1
    printed = capsys.readouterr().out
    assert "::error::DNS: no se resuelve" in printed and "::error::Prueba: caída" in printed
    assert "https://nirkana.es/sitemap.xml no responde" in printed
    assert "OK nirkana.es" not in printed
