"""The sign-in cookie written by the server (ops/deploy/sessions.py): HttpOnly, and only for our own pages."""

import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops" / "deploy"))


@pytest.fixture(scope="module")
def service():
    from sessions import Handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def post(url, body, site="same-origin", path="/_nk/sesion"):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    headers = {"Content-Type": "application/json", **({"Sec-Fetch-Site": site} if site else {})}
    request = urllib.request.Request(url + path, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.headers.get_all("Set-Cookie") or []
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get_all("Set-Cookie") or []


TOKEN = "Abc_def-123456789012345678901234567890123"


def test_our_page_gets_an_httponly_cookie(service):
    status, cookies = post(service, {"name": "nk_sesion_cafe_aurora", "token": TOKEN})
    assert status == 204
    assert cookies[0].startswith(f"__Host-nk_sesion_cafe_aurora={TOKEN};")
    for flag in ("HttpOnly", "Secure", "SameSite=Strict", "Path=/", "Max-Age=604800"):
        assert flag in cookies[0]
    assert cookies[1].startswith("nk_sesion_cafe_aurora=;") and "Max-Age=0" in cookies[1]  # the page-written one
    status, cookies = post(service, {"name": "nk_sesion", "token": ""})  # sign out
    assert status == 204 and "Max-Age=0" in cookies[0]


def test_other_sites_and_bad_requests_are_refused(service):
    good = {"name": "nk_sesion", "token": TOKEN}
    assert post(service, good, site="cross-site") == (403, [])  # another site planting a session
    assert post(service, good, site="same-site") == (403, [])  # another subdomain
    assert post(service, good, site=None) == (403, [])  # not a browser
    assert post(service, {"name": "otra; Domain=evil", "token": TOKEN})[0] == 400
    assert post(service, {"name": "nk_sesion", "token": "x; HttpOnly=false"})[0] == 400
    assert post(service, b"no es json")[0] == 400
    assert post(service, b"x" * 2048)[0] == 400
    assert post(service, good, path="/otra")[0] == 404
