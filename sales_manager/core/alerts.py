"""An email to the operator as soon as the app hits an error, so they hear about it before the customer calls.

It says which business, the reference the person saw, the kind of error and the line of NirKanA's code: never the
error message or any data (they can contain customers' details). The same error is emailed at most once an hour per
server, and no more than MAX_PER_HOUR emails go out in an hour whatever happens.
"""

import threading
import time

from . import logs

WINDOW = 3600
MAX_PER_HOUR = 20
log = logs.get("alerts")
_lock = threading.Lock()
_last_sent: dict[tuple, float] = {}
_recent: list[float] = []


def _allowed(key: tuple, now: float) -> bool:
    with _lock:
        _recent[:] = [t for t in _recent if now - t < WINDOW]
        if now - _last_sent.get(key, -WINDOW) < WINDOW or len(_recent) >= MAX_PER_HOUR:
            return False
        _last_sent[key] = now
        _recent.append(now)
        return True


def _send(mailer, to: str, subject: str, text: str) -> None:
    try:
        mailer.send(to, subject, text)
    except Exception as exc:  # noqa: BLE001 - an alert that cannot be sent must never break the page
        log.warning("alert_not_sent error=%s", type(exc).__name__)


def error_happened(mailer, to: str, business: str, ref: str, kind: str, where: str, page: str,
                   now: float | None = None, wait: bool = False) -> bool:
    """Email the operator about one error unless the same one was sent within the hour. Returns whether it was sent.
    The email goes out in the background: the person who hit the error is not kept waiting."""
    if mailer is None or not to:
        return False
    now = time.time() if now is None else now
    if not _allowed((business, kind, where), now):
        return False
    subject = f"NirKanA: error en {business or 'la app'} ({kind})"
    text = (f"Negocio: {business or '(único)'}\nReferencia que vio la persona: {ref}\nPantalla: {page}\n"
            f"Tipo de error: {kind}\nDónde, en el código: {where or 'fuera del código de la app'}\n\n"
            "El detalle completo está en el registro del servidor, buscando la referencia. Si el mismo error se "
            "repite, no te llegará otro email durante una hora.")
    sender = threading.Thread(target=_send, args=(mailer, to, subject, text), daemon=True)
    sender.start()
    if wait:
        sender.join(timeout=30)
    return True
