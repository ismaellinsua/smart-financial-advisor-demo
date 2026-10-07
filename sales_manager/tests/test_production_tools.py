"""The two scripts for going live: the generator of production secrets and the check of a deployed app."""

import http.server
import re
import stat
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

import comprobar_produccion as check  # noqa: E402
import preparar_produccion as prepare  # noqa: E402

from core.security import totp_code, verify_totp  # noqa: E402


# ------------------------------------------------------------------ preparar_produccion
def test_secrets_are_generated_once_kept_private_and_never_overwritten(tmp_path, capsys):
    out = tmp_path / ".env.produccion"
    assert prepare.main([], out=out) == 0
    assert stat.S_IMODE(out.stat().st_mode) == 0o600  # only the owner can read it
    values = prepare.read(out)
    generated = [values[k] for k in ("DATA_KEY", "BACKUP_PASSPHRASE", "OPERATOR_PASSWORD", "APP_PASSWORD")]
    assert len(set(generated)) == 4 and min(map(len, generated)) >= 32
    secret = values["OPERATOR_TOTP_SECRET"]
    assert verify_totp(secret, totp_code(secret))  # a real two-step key the app accepts
    assert values["MULTI_TENANT"] == "true" and values["REQUIRE_DATABASE"] == "1" and values["DATABASE_URL"] == ""
    shown = capsys.readouterr().out
    assert secret in shown and "NO SUBAS ESTE ARCHIVO" in shown

    before = out.read_text()
    assert prepare.main([], out=out) == 1  # DATA_KEY must never change once in use
    assert out.read_text() == before and "no se sobrescribe" in capsys.readouterr().out
    assert prepare.main(["--qr"], out=out) == 0 and secret in capsys.readouterr().out
    assert prepare.main(["--qr"], out=tmp_path / "otro") == 1


def test_every_value_production_reads_is_in_the_file():
    """Nothing the server or the scheduled jobs need is left out of the list (core/config.py is the reference)."""
    from core.config import SETTINGS

    text = prepare.content(prepare.generated())
    listed = set(re.findall(r"^([A-Z0-9_]+)=", text, re.M))
    needed = {"DATABASE_URL", "MULTI_TENANT", "REQUIRE_DATABASE", "DATA_KEY", "OPERATOR_PASSWORD",
              "OPERATOR_TOTP_SECRET", "OPERATOR_EMAIL", "APP_URL", "TERMS_URL", "STRIPE_SECRET_KEY", "STRIPE_PRICE_ID",
              "STRIPE_WEBHOOK_SECRET", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "BACKUP_DATABASES",
              "BACKUP_PASSPHRASE", "BACKUP_S3_BUCKET", "PRODUCTION"}
    assert needed <= listed
    assert {n.upper() for n in SETTINGS} >= listed - {"PRODUCTION", "BACKUP_S3_ENDPOINT", "BACKUP_S3_ACCESS_KEY_ID",
                                                     "BACKUP_S3_SECRET_ACCESS_KEY"}


def test_the_render_blueprint_asks_for_everything_the_app_needs():
    blueprint = (ROOT / "render.yaml").read_text()
    for key in ("DATABASE_URL", "DATA_KEY", "OPERATOR_PASSWORD", "OPERATOR_TOTP_SECRET", "OPERATOR_EMAIL", "APP_URL",
                "TERMS_URL", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "MULTI_TENANT"):
        assert f"key: {key}\n" in blueprint, key


# ------------------------------------------------------------------ comprobar_produccion
CADDY_CSP = re.search(r'Content-Security-Policy "([^"]+)"',
                      (ROOT / "ops" / "deploy" / "Caddyfile").read_text()).group(1)
GOOD_HEADERS = {"Strict-Transport-Security": "max-age=31536000", "X-Frame-Options": "SAMEORIGIN",
                "X-Content-Type-Options": "nosniff", "Referrer-Policy": "strict-origin-when-cross-origin",
                "Permissions-Policy": "camera=(self)", "Content-Security-Policy": CADDY_CSP}


def deployed(headers=None, health=(200, "ok"), webhook=400, cookie=403, http_redirect=True):
    """A fake of the live container, answering as check_app's requests expect."""
    headers = GOOD_HEADERS if headers is None else headers

    def get(url, method="GET", body=None, headers_=None, follow=True, **kwargs):
        if url.startswith("http://"):
            return (301, {"Location": "https://app.example/"}, "") if http_redirect else (200, {}, "")
        if url.endswith("/_nk/salud"):
            return health[0], {}, health[1]
        if url.endswith("/_nk/sesion"):
            return cookie, {}, ""
        if url.endswith("/stripe/webhook"):
            return webhook, {}, ""
        return 200, headers, "<html>"
    return get


def test_the_real_container_configuration_passes_every_check():
    results = check.check_app("https://app.example", get=deployed())
    assert all(ok for ok, _ in results), [text for ok, text in results if not ok]
    assert len(results) >= 12


def test_each_production_mistake_is_named():
    def failures(**kwargs):
        return [text for ok, text in check.check_app("https://app.example", get=deployed(**kwargs)) if not ok]

    loose = {**GOOD_HEADERS, "Content-Security-Policy": CADDY_CSP.replace("script-src 'self'",
                                                                          "script-src 'self' 'unsafe-inline'")}
    assert failures(headers=loose) == ["La CSP solo ejecuta los scripts de la app (sin 'unsafe-inline')"]
    assert "base de datos no funcionan" in failures(health=(503, "no"))[0]
    assert "falta STRIPE_WEBHOOK_SECRET" in failures(webhook=502)[0]
    assert "Otra web no puede fijar la sesión" in failures(cookie=204)[0]
    assert "http:// lleva a https://" in failures(http_redirect=False)[0]
    bare = failures(headers={"Server": "uvicorn"})  # Streamlit straight to the internet, without the container
    assert len(bare) >= 7 and any("Server" in t for t in bare)
    assert not check.check_app("http://app.example", get=deployed())[0][0]  # plain HTTP is a failure in itself


def test_legal_pages_must_be_published_and_complete():
    def web(url, **kwargs):
        if url.endswith("encargado.html"):
            return 404, {}, ""
        if url.endswith("aviso-legal.html"):
            return 200, {}, "NIF: PENDIENTE"
        return 200, {}, "Condiciones"

    results = check.check_web("https://nirkana.es", get=web)
    assert [ok for ok, _ in results] == [True, False, False]
    assert "responde 404" in results[1][1] and "huecos sin rellenar" in results[2][1]


def test_request_reports_status_headers_and_connection_failures():
    class Server(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/redir":
                self.send_response(308)
                self.send_header("Location", "https://example.org/")
                self.end_headers()
                return
            self.send_response(404 if self.path == "/no" else 200)
            self.send_header("X-Prueba", "1")
            self.end_headers()
            self.wfile.write(b"ok")

        def do_POST(self):  # noqa: N802
            self.send_response(403)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, headers, body = check.request(f"{base}/")
        assert (status, headers.get("X-Prueba"), body) == (200, "1", "ok")
        assert check.request(f"{base}/no")[0] == 404
        assert check.request(f"{base}/", method="POST", body=b"{}")[0] == 403
        status, headers, _ = check.request(f"{base}/redir", follow=False)
        assert status == 308 and headers.get("Location") == "https://example.org/"
    finally:
        server.shutdown()
    assert check.request("http://127.0.0.1:9/")[0] == 0  # nothing listening


def test_main_prints_a_verdict(monkeypatch, capsys):
    monkeypatch.setattr(check, "request", deployed())
    assert check.main(["https://app.example"]) == 0
    assert "Producción lista" in capsys.readouterr().out
    monkeypatch.setattr(check, "request", deployed(health=(503, "no")))
    assert check.main(["https://app.example"]) == 1 and "FALLO" in capsys.readouterr().out


# ------------------------------------------------------------------ GitHub ruleset for main
def test_the_main_ruleset_requires_the_ci_and_forbids_rewriting_history():
    import json

    ruleset = json.loads((ROOT / "ops" / "github" / "ruleset-main.json").read_text())
    rules = {rule["type"]: rule.get("parameters", {}) for rule in ruleset["rules"]}
    assert ruleset["enforcement"] == "active" and ruleset["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    assert {"deletion", "non_fast_forward", "pull_request", "required_status_checks"} <= set(rules)
    required = {c["context"] for c in rules["required_status_checks"]["required_status_checks"]}
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    jobs = set(re.findall(r"^  ([a-z_-]+):\n", workflow.split("\njobs:\n", 1)[1], re.M))
    assert required == {"tests"} and required <= jobs  # the check name is the CI job's: a typo would block every PR
