"""Running the service: health for an external monitor, operator two-step on the real server, start-up migrations,
the per-server cache of businesses and real-time error alerts."""

import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from conftest import PG_URL

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops" / "deploy"))
sys.path.insert(0, str(ROOT / "ops"))
needs_pg = pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set")


def _serve(handler_class):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class FakeStreamlit(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


# ------------------------------------------------------------------ 9. health for an external monitor
@needs_pg
def test_health_needs_both_the_app_and_its_database():
    import sessions

    app, url = _serve(FakeStreamlit)
    try:
        assert sessions.check_health(url, PG_URL)
        assert not sessions.check_health(url, "postgresql://nadie:x@127.0.0.1:1/nada")  # the database is down
        assert sessions.check_health(url, "")  # no database configured: the app alone
    finally:
        app.shutdown()
    assert not sessions.check_health(url, PG_URL)  # the app is down


def test_health_answers_ok_or_503_and_is_reused_for_a_few_seconds(monkeypatch):
    import sessions

    calls = []
    monkeypatch.setattr(sessions, "check_health", lambda app, db: calls.append(1) or len(calls) == 1)
    monkeypatch.setitem(sessions._health, "at", 0.0)
    server, url = _serve(sessions.Handler)
    try:
        with urllib.request.urlopen(f"{url}/_nk/salud", timeout=5) as response:
            assert (response.status, response.read()) == (200, b"ok")
        with urllib.request.urlopen(f"{url}/_nk/salud", timeout=5) as response:
            assert response.read() == b"ok" and len(calls) == 1  # reused: a monitor never loads the database
        sessions._health["at"] = 0.0
        with pytest.raises(urllib.error.HTTPError) as down:
            urllib.request.urlopen(f"{url}/_nk/salud", timeout=5)
        assert down.value.code == 503 and down.value.read() == b"no"
        with pytest.raises(urllib.error.HTTPError) as other:
            urllib.request.urlopen(f"{url}/otra", timeout=5)
        assert other.value.code == 405
    finally:
        server.shutdown()


def test_uptime_uses_the_database_check_when_the_server_has_it(monkeypatch):
    import uptime

    class WithHealth(FakeStreamlit):
        def do_GET(self):  # noqa: N802
            if self.path == "/_nk/salud":
                self.send_response(503)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"no")
                return
            super().do_GET()

    server, url = _serve(WithHealth)
    try:
        monkeypatch.setattr(uptime, "ATTEMPTS", 1)
        monkeypatch.setattr(uptime, "WAIT_SECONDS", 0)
        ok, detail = uptime.healthy(url)
        assert not ok and "base de datos" in detail  # Streamlit alone would have said «ok»
    finally:
        server.shutdown()


# ------------------------------------------------------------------ 11. operator two-step on the real server
OPERATOR = """
import sys, time
sys.path.insert(0, {root!r})
import streamlit as st
import ui.tenancy
ui.tenancy.setting = lambda name: {{"operator_password": "una-clave-larga-2026", "operator_totp_secret": {totp!r}}}.get(name, "")
ui.tenancy.require_external_database = lambda: {production!r}
class Directory:
    def backup_status(self): return "ok", "copia"
    def role_isolation(self): return 1, 0
    def billing_alerts(self): return []
    def overview(self): return []
    def log(self): return []
ui.tenancy.get_directory = lambda: Directory()
ui.tenancy.stripe_client = lambda: None
st.session_state["operator_since"] = time.time()
ui.tenancy.operator_panel()
"""


@pytest.mark.parametrize("production, totp, opens", [(True, "", False), (True, "JBSWY3DPEHPK3PXP", True),
                                                     (False, "", True)])
def test_on_the_real_server_the_panel_never_opens_with_a_password_alone(production, totp, opens):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(OPERATOR.format(root=str(ROOT / "sales_manager"), production=production, totp=totp),
                             default_timeout=30).run()
    assert not at.exception, at.exception
    blocked = any("bloqueado" in e.value for e in at.error)
    assert blocked != opens
    assert any("Dar de alta un negocio" in m.value for m in at.markdown) == opens


# ------------------------------------------------------------------ 12. start-up migrations
@needs_pg
def test_a_deploy_without_schema_changes_opens_no_business(monkeypatch):
    import uuid
    from urllib.parse import urlsplit, urlunsplit

    import psycopg

    import core.tenants as tenants

    name = f"nk_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    url = urlunsplit(urlsplit(PG_URL)._replace(path=f"/{name}"))
    try:
        directory = tenants.Directory(url)
        for code in ("cafe", "bar", "tienda"):
            directory.create(code, code.title())
        with psycopg.connect(url, autocommit=True) as conn:  # one business is behind
            conn.execute("UPDATE n_bar.schema_state SET value = 'antigua' WHERE key = 'fingerprint'")
        opened = []
        real = tenants.Store

        class Counting(real):
            def __init__(self, *args, **kwargs):
                opened.append(kwargs.get("schema"))
                super().__init__(*args, **kwargs)
        monkeypatch.setattr(tenants, "Store", Counting)
        done = dict(tenants.migrate_all(url))
        assert opened == ["n_bar"] and set(done) == {"cafe", "bar", "tienda"}
        assert len(set(done.values())) == 1  # every business at the same version
        opened.clear()
        tenants.migrate_all(url)
        assert opened == []  # the next start opens nobody
        directory.close()
    finally:
        with psycopg.connect(PG_URL, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


# ------------------------------------------------------------------ 13. the per-server cache of businesses
def test_the_cache_of_open_businesses_is_configurable_and_closes_what_it_drops():
    import inspect

    import ui.context as context

    source = inspect.getsource(context)
    assert 'max_entries=config.integer("tenant_cache_size"' in source and "on_release=_release" in source
    closed = []

    class Store:
        def close(self):
            closed.append(1)
    context._release(Store())
    assert closed == [1]


# ------------------------------------------------------------------ 10. errors emailed as they happen, logs in JSON
class Mailbox:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, text):
        self.sent.append((to, subject, text))


def test_an_error_is_emailed_at_once_without_data_and_not_repeated_within_the_hour(monkeypatch):
    import core.alerts as alerts

    monkeypatch.setattr(alerts, "_last_sent", {})
    monkeypatch.setattr(alerts, "_recent", [])
    box = Mailbox()
    sent = alerts.error_happened(box, "op@example.com", "cafe-aurora", "A3F09C", "ZeroDivisionError",
                                 "ui/pages_pos.py:120 point_of_sale", "Vender", now=1000, wait=True)
    assert sent and box.sent[0][0] == "op@example.com" and "cafe-aurora" in box.sent[0][1]
    assert "A3F09C" in box.sent[0][2] and "ui/pages_pos.py:120" in box.sent[0][2]
    assert not alerts.error_happened(box, "op@example.com", "cafe-aurora", "B1", "ZeroDivisionError",
                                     "ui/pages_pos.py:120 point_of_sale", "Vender", now=1500, wait=True)
    assert alerts.error_happened(box, "op@example.com", "cafe-aurora", "B2", "ZeroDivisionError",
                                 "ui/pages_pos.py:120 point_of_sale", "Vender", now=1000 + 3601, wait=True)
    assert len(box.sent) == 2
    assert not alerts.error_happened(None, "op@example.com", "x", "r", "k", "w", "p")  # email not set up
    assert not alerts.error_happened(box, "", "x", "r", "k", "w", "p")  # nobody to tell


def test_a_storm_of_errors_sends_a_bounded_number_of_emails(monkeypatch):
    import core.alerts as alerts

    monkeypatch.setattr(alerts, "_last_sent", {})
    monkeypatch.setattr(alerts, "_recent", [])
    box = Mailbox()
    for i in range(100):
        alerts.error_happened(box, "op@example.com", "cafe", str(i), f"Error{i}", "ui/x.py:1", "P", now=50, wait=True)
    assert len(box.sent) == alerts.MAX_PER_HOUR


def test_a_failing_mailer_never_breaks_the_page(monkeypatch):
    import core.alerts as alerts

    class Broken:
        def send(self, *args):
            raise OSError("smtp caído")
    monkeypatch.setattr(alerts, "_last_sent", {})
    monkeypatch.setattr(alerts, "_recent", [])
    assert alerts.error_happened(Broken(), "op@example.com", "cafe", "R", "K", "W", "P", now=1, wait=True)


def test_json_logs_carry_the_key_value_pairs_as_fields():
    import json
    import logging

    from core.logs import JsonFormatter

    record = logging.LogRecord("nirkana.app", logging.WARNING, __file__, 1, "page_error ref=%s page=%s",
                               ("A3F09C", "Vender"), None)
    entry = json.loads(JsonFormatter().format(record))
    assert entry["level"] == "WARNING" and entry["ref"] == "A3F09C" and entry["page"] == "Vender"
    assert entry["message"] == "page_error ref=A3F09C page=Vender"


# ------------------------------------------------------------------ 8. several servers behind one address
def test_a_person_moved_to_another_server_keeps_sign_in_ticket_and_limits(make_store):
    """With several instances a reconnection may land on another server: nothing a person needs lives only in one
    server's memory."""
    server_a = make_store()
    if not hasattr(server_a.db, "_pool"):
        pytest.skip("several servers share a PostgreSQL database")
    target = next(t for t, r in make_store.targets.roles.items())
    server_b = make_store(target)
    server_a.load_preset("retail", with_demo_sales=False)
    uid = server_a.create_user("Ana", "ana", "admin", "Segura-2026!")
    token = server_a.create_session(uid, "navegador")
    product = int(server_a.products().iloc[0]["id"])
    server_a.save_cart(uid, {product: 2})
    from core import throttle

    now = time.time()
    for i in range(throttle.MAX_FAILURES):
        server_a.throttle_failed("1.2.3.4", now=now + i)
    assert server_b.resume_session(token, 60, "navegador")["username"] == "ana"
    assert server_b.saved_cart(uid) == {product: 2}
    assert server_b.throttle_blocked_minutes("1.2.3.4", now=now + throttle.MAX_FAILURES) > 0
