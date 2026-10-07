"""Scheduled emails: only what each business asked for, once, and never in demonstration mode."""

import os
from datetime import datetime

import pytest

from core.mailer import Mailer, mask_email, valid_email
from core.notifications import send_due

MONDAY, TUESDAY = datetime(2026, 10, 5, 8, 0), datetime(2026, 10, 6, 8, 0)


class FakeMailer(Mailer):
    def __init__(self):
        super().__init__("smtp.example.com", 587, "envios@example.com", "x")
        self.sent = []

    def send(self, to, subject, text, html="", attachments=(), reply_to=""):
        self.last = self.message(to, subject, text, html, attachments, reply_to)  # built exactly as for real
        self.sent.append((to, subject, [a[0] for a in attachments]))


@pytest.fixture
def store(make_store):
    s = make_store()
    s.load_preset("retail", with_demo_sales=False)
    s.save_settings({"business_name": "Tienda Sol", "email": "duena@example.com", "demo_mode": "no"})
    return s


def test_nothing_is_sent_unless_the_business_asked(store):
    mailer = FakeMailer()
    assert send_due(store, mailer, MONDAY) == [] and not mailer.sent
    store.save_settings({"email_weekly": "si", "email": "no-es-un-email"})
    assert send_due(store, mailer, MONDAY) == []
    store.save_settings({"email": "duena@example.com", "demo_mode": "si"})
    assert send_due(store, mailer, MONDAY) == []


def test_weekly_report_goes_on_mondays_once_with_the_pdf(store):
    store.save_settings({"email_weekly": "si"})
    mailer = FakeMailer()
    assert send_due(store, mailer, TUESDAY) == []
    assert send_due(store, mailer, MONDAY) == ["informe semanal"]
    to, subject, files = mailer.sent[0]
    assert to == "duena@example.com" and "Tienda Sol" in subject and files == ["informe-2026-09-28.pdf"]
    assert send_due(store, mailer, MONDAY) == []  # the job ran twice: no second email


def test_important_alerts_are_sent_when_they_are_new(store, monkeypatch):
    store.save_settings({"email_alerts": "si"})
    mailer = FakeMailer()
    alerts = [{"level": "alta", "area": "Stock", "title": "2 productos agotados", "detail": "Pide ya.", "page": ""},
              {"level": "media", "area": "Caja", "title": "Descuadre", "detail": "", "page": ""}]
    monkeypatch.setattr(type(store), "alerts", lambda self, now=None: alerts)
    assert send_due(store, mailer, TUESDAY) == ["1 aviso(s)"]
    assert send_due(store, mailer, TUESDAY) == []  # same alerts: not again
    alerts[0]["title"] = "3 productos agotados"
    assert send_due(store, mailer, TUESDAY) == ["1 aviso(s)"]
    assert len(mailer.sent) == 2


def test_message_and_configuration():
    assert Mailer.from_settings(lambda name: None) is None
    mailer = Mailer.from_settings({"smtp_host": "smtp.gmail.com", "smtp_user": "nirkana.oficial@gmail.com",
                                   "smtp_password": "app-pass"}.get)
    assert mailer.port == 587 and "nirkana.oficial@gmail.com" in mailer.sender
    msg = mailer.message("cliente@example.com", "Asunto\ninyectado", "Hola", attachments=[("a.pdf", b"%PDF", "application/pdf")])
    assert msg["Subject"] == "Asunto inyectado" and msg["To"] == "cliente@example.com"
    assert [p.get_filename() for p in msg.iter_attachments()] == ["a.pdf"]
    with pytest.raises(ValueError):
        mailer.message("a@b.com\nBcc: otro@example.com", "x", "y")
    assert valid_email("a@b.es") and not valid_email("a@b") and mask_email("nirkana@gmail.com") == "n***@gmail.com"


def test_uptime_check_reports_an_app_that_does_not_answer(tmp_path):
    import http.server
    import subprocess
    import sys
    import threading
    from pathlib import Path

    class Health(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            ok = self.path == "/_stcore/health"
            self.send_response(200 if ok else 404)
            self.end_headers()
            self.wfile.write(b"ok" if ok else b"no")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    up = f"http://127.0.0.1:{server.server_port}"
    script = Path(__file__).resolve().parents[2] / "ops" / "uptime.py"
    env = {"PATH": "/usr/bin:/bin", "UPTIME_URLS": up,
           **{k: v for k, v in os.environ.items() if k.startswith("COVERAGE_")}}  # measured in CI
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=env)
    assert result.returncode == 0 and "OK" in result.stdout
    env["UPTIME_URLS"] = f"{up}\nhttp://127.0.0.1:9"
    # The address that does not answer is retried without waiting, to keep the test fast.
    result = subprocess.run([sys.executable, "-c", "import sys; import importlib.util as u; "
                             f"spec = u.spec_from_file_location('uptime', {str(script)!r}); m = u.module_from_spec(spec); "
                             "spec.loader.exec_module(m); m.WAIT_SECONDS = 0; sys.exit(m.main())"],
                            capture_output=True, text=True, env=env)
    server.shutdown()
    assert result.returncode == 1 and "CAÍDA http://127.0.0.1:9" in result.stdout
