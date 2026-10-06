"""Writes the sign-in cookie from the server, so it can be HttpOnly: page scripts can never read it.

Streamlit can only set cookies from JavaScript, and a cookie written that way is readable by any script on the
page. Inside the container, Caddy sends POST /_nk/sesion here; the app's page asks for it right after signing in or
out (ui/auth.py) and only falls back to writing the cookie itself where this service is not running (Streamlit Cloud,
local runs). Only same-origin requests are honoured, so another site cannot plant a session in someone's browser.
"""

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sales_manager"))

from core import config, logs  # noqa: E402

PATH = "/_nk/sesion"
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
        self._reply(405)

    def log_message(self, *args):  # never log the request: its body carries a session token
        pass


def main() -> None:
    port = int(config.value("sessions_port"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
