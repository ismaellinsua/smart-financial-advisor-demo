"""After deploying: is the live app really set up as production needs? One command, a list of OK / FALLO.

    python ops/comprobar_produccion.py https://app.nirkana.es
    python ops/comprobar_produccion.py https://app.nirkana.es --web https://nirkana.es

Checks from outside, as a visitor's browser would see it:
  - HTTPS, and http:// sending to https://,
  - /_nk/salud answering «ok» (the app and its database),
  - the security headers of the container (HSTS, frames, CSP without any inline script but the app's own…),
  - the sign-in cookie service refusing another site,
  - the Stripe webhook answering (it refuses an unsigned notice: 400, not 404 or 502),
  - with --web, the legal pages every business accepts (condiciones, encargado, aviso legal).
Exit code 1 when anything fails. It sends nothing that changes data.
"""

import argparse
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit

TIMEOUT = 20
HEADERS = {
    "Strict-Transport-Security": None,
    "X-Frame-Options": "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": None,
    "Permissions-Policy": None,
}
LEGAL_PAGES = ("condiciones.html", "encargado.html", "aviso-legal.html")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(url: str, method: str = "GET", body: bytes | None = None, headers: dict | None = None,
            follow: bool = True) -> tuple[int, dict, str]:
    """(status, headers, body) — an HTTP error is an answer too; a connection failure is status 0."""
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"User-Agent": "NirKanA production check", **(headers or {})})
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            return response.status, dict(response.headers), response.read(100_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), ""
    except OSError as exc:
        return 0, {}, str(exc)


def _header(headers: dict, name: str) -> str:
    return next((v for k, v in headers.items() if k.lower() == name.lower()), "")


def check_app(base: str, get=None) -> list[tuple[bool, str]]:
    get = get or request
    base = base.rstrip("/")
    results = []
    parts = urlsplit(base)
    results.append((parts.scheme == "https", f"La dirección usa HTTPS ({base})"))
    if parts.scheme == "https":
        status, headers, _ = get(urlunsplit(parts._replace(scheme="http")) + "/", follow=False)
        location = _header(headers, "Location")
        results.append((status in (301, 302, 307, 308) and location.startswith("https://"),
                        f"http:// lleva a https:// (respuesta {status or 'sin conexión'})"))

    status, _, body = get(f"{base}/_nk/salud")
    results.append((status == 200 and body.strip() == "ok",
                    "La app y su base de datos responden (/_nk/salud = ok)" if status == 200 else
                    f"/_nk/salud responde {status or 'sin conexión'}: la app o la base de datos no funcionan"
                    + (" (¿no es el contenedor de NirKanA?)" if status == 404 else "")))

    status, headers, _ = get(f"{base}/")
    for name, expected in HEADERS.items():
        value = _header(headers, name)
        results.append((bool(value) and (expected is None or value.lower() == expected.lower()),
                        f"Cabecera {name}" + (f": {value}" if value else " ausente")))
    policy = _header(headers, "Content-Security-Policy")
    script_src = next((d.strip() for d in policy.split(";") if d.strip().startswith("script-src")), "")
    results.append(("default-src 'self'" in policy and "frame-ancestors 'self'" in policy,
                    "La CSP solo permite la propia app y nadie la puede incrustar"))
    results.append((bool(script_src) and "'unsafe-inline'" not in script_src and "'unsafe-eval'" not in script_src,
                    "La CSP solo ejecuta los scripts de la app (sin 'unsafe-inline')"))
    results.append((not _header(headers, "Server"), "La cabecera Server no delata el software"))

    status, _, _ = get(f"{base}/_nk/sesion", method="POST", body=b'{"name":"nk_sesion","token":"x"}',
                       headers={"Content-Type": "application/json", "Sec-Fetch-Site": "cross-site"})
    results.append((status == 403, f"Otra web no puede fijar la sesión (respuesta {status or 'sin conexión'})"))

    status, _, _ = get(f"{base}/stripe/webhook", method="POST", body=b"{}",
                       headers={"Content-Type": "application/json"})
    results.append((status == 400, "El webhook de Stripe responde y rechaza un aviso sin firma" if status == 400 else
                    f"El webhook de Stripe responde {status or 'sin conexión'}"
                    + (": falta STRIPE_WEBHOOK_SECRET o el servicio no arrancó" if status in (0, 502, 503) else "")))
    return results


def check_web(web: str, get=None) -> list[tuple[bool, str]]:
    get = get or request
    web = web.rstrip("/")
    results = []
    for page in LEGAL_PAGES:
        status, _, body = get(f"{web}/{page}")
        results.append((status == 200 and "PENDIENTE" not in body and "{{" not in body,
                        f"{web}/{page}" + (" publicada" if status == 200 else f" responde {status or 'sin conexión'}")
                        + (" pero con huecos sin rellenar" if status == 200 and ("PENDIENTE" in body or "{{" in body)
                           else "")))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("app", help="dirección pública de la app, p. ej. https://app.nirkana.es")
    parser.add_argument("--web", help="la web con los textos legales (TERMS_URL), p. ej. https://nirkana.es")
    args = parser.parse_args(argv)
    results = check_app(args.app) + (check_web(args.web) if args.web else [])
    for ok, text in results:
        print(f"{'OK   ' if ok else 'FALLO'}  {text}")
    failed = sum(not ok for ok, _ in results)
    print(f"\n{len(results) - failed} de {len(results)} comprobaciones correctas."
          + ("" if failed else " Producción lista para la prueba de venta, factura y suscripción."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
