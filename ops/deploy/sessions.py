"""Writes the sign-in cookie from the server, so it can be HttpOnly: page scripts can never read it.

Streamlit can only set cookies from JavaScript, and a cookie written that way is readable by any script on the
page. Inside the container, Caddy sends POST /_nk/sesion here; the app's page asks for it right after signing in or
out (ui/auth.py) and only falls back to writing the cookie itself where this service is not running (Streamlit Cloud,
local runs). Only same-origin requests are honoured, so another site cannot plant a session in someone's browser.

It also answers GET /_nk/salud for an external uptime monitor: «ok» (200) only when Streamlit answers AND the database
accepts a query, «no» (503) otherwise. Streamlit's own health check says the process is alive even when the database
is down, and then nobody can sell.
"""

import json
import re
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sales_manager"))

from core import config, logs  # noqa: E402

PATH = "/_nk/sesion"
HEALTH_PATH = "/_nk/salud"
HEALTH_TTL = 10  # seconds a result is reused: a monitor (or anyone) asking often never adds load on the database
MAX_BODY = 1024
MAX_AGE = 7 * 86400  # as SESSION_MAX_AGE: the server ends the session anyway after that
NAME_RE = re.compile(r"nk_sesion(_[a-z0-9_]{1,40})?")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{20,100}")
log = logs.get("sessions")


def cookie_headers(name: str, token: str) -> list[str]:
    """The HttpOnly cookie (empty token: delete it), and the removal of any older cookie written by the page."""
    age = MAX_AGE if token else 0
    return [f"__Host-{name}={token}; Path=/; Max-Age={age}; HttpOnly; Secure; SameSite=Strict",
            f"{name}=; Path=/; Max-Age=0; SameSite=Strict"]


_health = {"at": 0.0, "ok": False}
_health_lock = threading.Lock()


def check_health(app_url: str, database_url: str) -> bool:
    """Streamlit answers and the database runs a query, each within a few seconds."""
    try:
        with urllib.request.urlopen(f"{app_url}/_stcore/health", timeout=5) as response:
            if response.status != 200:
                return False
        if database_url:
            import psycopg

            from core.engines import secure_url

            with psycopg.connect(secure_url(database_url), connect_timeout=5) as conn:
                conn.execute("SELECT 1")
        return True
    except Exception as exc:  # noqa: BLE001 - any failure means «not healthy»; the reason goes to the log only
        log.warning("health_failed error=%s", type(exc).__name__)
        return False


def healthy(now: float | None = None) -> bool:
    now = time.time() if now is None else now
    with _health_lock:
        if now - _health["at"] < HEALTH_TTL:
            return _health["ok"]
        _health["ok"] = check_health(f"http://127.0.0.1:{config.value('streamlit_port')}",
                                     config.value("database_url"))
        _health["at"] = now
        return _health["ok"]


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code: int, cookies: list[str] = ()) -> None:
        self.send_response(code)
        for value in cookies:
            self.send_header("Set-Cookie", value)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):  # noqa: N802 - http.server's naming
        if self.path.split("?")[0] != PATH:
            return self._reply(404)
        # Browsers send Sec-Fetch-Site on every fetch; a request from another site, or from no browser, is refused.
        if self.headers.get("Sec-Fetch-Site") != "same-origin":
            log.warning("session_cookie_refused reason=not_same_origin")
            return self._reply(403)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._reply(400)
        if not 0 < length <= MAX_BODY or "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._reply(400)
        try:
            data = json.loads(self.rfile.read(length))
            name, token = str(data["name"]), str(data.get("token") or "")
        except (ValueError, KeyError, TypeError):
            return self._reply(400)
        if not NAME_RE.fullmatch(name) or (token and not TOKEN_RE.fullmatch(token)):
            return self._reply(400)
        self._reply(204, cookie_headers(name, token))

    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] != HEALTH_PATH:
            return self._reply(405)
        ok = healthy()
        body = b"ok" if ok else b"no"
        self.send_response(200 if ok else 503)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # never log the request: its body carries a session token
        pass


def main() -> None:
    port = int(config.value("sessions_port"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
