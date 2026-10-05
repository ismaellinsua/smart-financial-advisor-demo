"""Is each app up? Asks every address for its health check; a failure is retried before it counts.

    python ops/uptime.py

Environment:
    UPTIME_URLS      one app address per line, e.g. https://app.nirkana.es
    OPERATOR_EMAIL   optional: also email this address when an app is down (needs SMTP_*, see core/mailer.py)
Exit code 1 when an app is down, so GitHub Actions marks the run failed and notifies the repository owner.
"""

import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sales_manager"))

ATTEMPTS, WAIT_SECONDS = 3, 20


def healthy(base: str) -> tuple[bool, str]:
    url = base.rstrip("/") + "/_stcore/health"
    last = ""
    for attempt in range(ATTEMPTS):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                body = response.read(200).decode(errors="replace").strip()
                if response.status == 200 and body == "ok":
                    return True, "ok"
                last = f"respuesta {response.status}"
        except urllib.error.HTTPError as exc:
            last = f"error HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = f"sin respuesta ({type(exc).__name__})"
        if attempt < ATTEMPTS - 1:
            time.sleep(WAIT_SECONDS)
    return False, last


def main() -> int:
    urls = [u.strip() for u in os.environ.get("UPTIME_URLS", "").splitlines() if u.strip()]
    if not urls:
        print("Sin direcciones que vigilar: define UPTIME_URLS.")
        return 0
    down = []
    for url in urls:
        ok, detail = healthy(url)
        print(f"{'OK ' if ok else 'CAÍDA'} {url} · {detail}")
        if not ok:
            down.append(f"{url} · {detail}")
    if down and os.environ.get("OPERATOR_EMAIL"):
        from core.mailer import Mailer

        mailer = Mailer.from_settings()
        if mailer:
            mailer.send(os.environ["OPERATOR_EMAIL"], f"NirKanA: {len(down)} app(s) sin responder",
                        "Estas apps no responden tras 3 intentos:\n\n" + "\n".join(down) +
                        "\n\nRevisa «Manage app → Logs» en Streamlit y el estado de Neon (manual de operación, "
                        "apartado Incidencias).")
    return 1 if down else 0


if __name__ == "__main__":
    sys.exit(main())
