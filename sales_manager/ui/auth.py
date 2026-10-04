"""Staff accounts: first-run administrator setup, login, recovery, idle timeout and logout."""

import hmac
import secrets
import threading
import time as _time
from collections import deque

import streamlit as st

from core.db import AuthError, Store
from core.security import check_secret_strength
from ui.styles import page_header

SESSION_USER = "user"
SESSION_SEEN = "last_seen"
MUST_CHANGE = "must_change_secret"
NEW_CODES = "new_recovery_codes"

# Guessing is slowed per device (browser address), not per account: whoever keeps failing waits longer and longer,
# while the owner, from their own device, can still sign in. Best effort: kept in this server's memory.
CLIENT_MAX_FAILURES, CLIENT_WINDOW_SECONDS = 8, 15 * 60
CLIENT_FIRST_BLOCK_MINUTES, CLIENT_MAX_BLOCK_MINUTES = 15, 24 * 60
_CLIENTS: dict[str, dict] = {}
_CLIENTS_LOCK = threading.Lock()

# Setup-password attempts are throttled across every visitor, not per browser tab.
_SETUP_FAILURES: deque = deque()
_SETUP_LOCK = threading.Lock()
SETUP_MAX_FAILURES, SETUP_WINDOW_SECONDS = 10, 600
_SETUP_CODE: str | None = None


def configured_password() -> str | None:
    """`app_password` from Streamlit secrets: proves ownership when the first administrator is created."""
    try:
        return st.secrets.get("app_password") or None
    except Exception:  # no secrets file: running locally
        return None


def client_key() -> str:
    """The visitor's address as seen by the hosting proxy (its last X-Forwarded-For entry), or the socket peer."""
    try:
        forwarded = st.context.headers.get("X-Forwarded-For") or ""
        if forwarded.strip():
            return forwarded.split(",")[-1].strip()
        return st.context.ip_address or "local"
    except Exception:  # no request context (tests, bare mode)
        return "local"


def client_blocked_minutes(key: str, now: float | None = None) -> int:
    now = _time.time() if now is None else now
    with _CLIENTS_LOCK:
        entry = _CLIENTS.get(key)
        if entry and entry["until"] > now:
            return max(1, round((entry["until"] - now) / 60))
    return 0


def client_failed(key: str, now: float | None = None) -> None:
    now = _time.time() if now is None else now
    with _CLIENTS_LOCK:
        if len(_CLIENTS) > 10_000:  # forget old visitors so memory stays bounded
            for k in [k for k, e in _CLIENTS.items() if e["until"] < now and not e["fails"]]:
                del _CLIENTS[k]
        entry = _CLIENTS.setdefault(key, {"fails": deque(), "until": 0.0, "level": 0})
        fails = entry["fails"]
        fails.append(now)
        while fails and fails[0] < now - CLIENT_WINDOW_SECONDS:
            fails.popleft()
        if len(fails) >= CLIENT_MAX_FAILURES:
            minutes = min(CLIENT_FIRST_BLOCK_MINUTES * 2 ** entry["level"], CLIENT_MAX_BLOCK_MINUTES)
            entry.update(until=now + minutes * 60, level=entry["level"] + 1)
            fails.clear()


def client_succeeded(key: str) -> None:
    with _CLIENTS_LOCK:
        _CLIENTS.pop(key, None)


def current_user() -> dict | None:
    return st.session_state.get(SESSION_USER)


def _setup_blocked() -> bool:
    with _SETUP_LOCK:
        while _SETUP_FAILURES and _SETUP_FAILURES[0] < _time.time() - SETUP_WINDOW_SECONDS:
            _SETUP_FAILURES.popleft()
        return len(_SETUP_FAILURES) >= SETUP_MAX_FAILURES


def _setup_failed() -> None:
    with _SETUP_LOCK:
        _SETUP_FAILURES.append(_time.time())


def _sign_in(store: Store, user: dict, secret: str | None = None) -> None:
    st.session_state[SESSION_USER] = user
    st.session_state[SESSION_SEEN] = _time.time()
    if secret is not None:
        try:
            check_secret_strength(secret, user["role"])
        except ValueError:  # set before the current rules: ask for a stronger one now
            st.session_state[MUST_CHANGE] = True
    st.rerun()


def setup_code() -> str:
    """One-time code for creating the first administrator when no `app_password` is configured.

    It is written to the server log (the terminal locally, «Manage app → Logs» on Streamlit Cloud), which only
    the owner can read. Unlike a check on the request's Host header, a visitor cannot forge it.
    """
    global _SETUP_CODE
    with _SETUP_LOCK:
        if _SETUP_CODE is None:
            _SETUP_CODE = secrets.token_hex(4).upper()
            print(f"[Gestor de Ventas] Código de instalación para crear el administrador: {_SETUP_CODE}", flush=True)
        return _SETUP_CODE


def _bootstrap(store: Store) -> None:
    """No accounts yet: create the administrator, proving ownership with `app_password` or the setup code."""
    expected = configured_password() or setup_code()
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header("Crea tu cuenta de administrador",
                    "Será la cuenta con todos los permisos. Después podrás dar de alta a tu equipo.",
                    eyebrow="Primer acceso")
        if configured_password():
            code_label = "Contraseña de instalación (app_password)"
        else:
            code_label = "Código de instalación"
            st.info("Escribe el código de instalación que aparece en el registro del servidor: en tu ordenador, "
                    "en la terminal; en Streamlit, en «Manage app → Logs». Si configuras `app_password` en los "
                    "*Secrets*, se usará esa contraseña en su lugar.", icon=":material/key:")
        with st.form("bootstrap"):
            code = st.text_input(code_label, type="password", max_chars=128)
            name = st.text_input("Tu nombre", max_chars=120)
            username = st.text_input("Usuario", max_chars=30, placeholder="p. ej. ismael",
                                     help="Minúsculas, números, punto o guion. Lo usarás para entrar.")
            secret = st.text_input("Contraseña", type="password", max_chars=128,
                                   help="Al menos 8 caracteres, con letras y números o símbolos.")
            repeat = st.text_input("Repite la contraseña", type="password", max_chars=128)
            if st.form_submit_button("Crear administrador", type="primary", use_container_width=True):
                if _setup_blocked():
                    st.error("Demasiados intentos. Espera unos minutos.")
                    return
                if not hmac.compare_digest(code.strip().encode(), expected.encode()):
                    _setup_failed()
                    _time.sleep(1)
                    st.error("La contraseña o el código de instalación no es correcto.")
                    return
                if secret != repeat:
                    st.error("Las contraseñas no coinciden.")
                    return
                if store.has_users():  # someone else finished first
                    st.rerun()
                try:
                    uid = store.create_user(name, username, "admin", secret)
                except ValueError as exc:
                    st.error(str(exc))
                    return
                st.session_state[NEW_CODES] = store.create_recovery_codes(uid)
                _sign_in(store, store.authenticate(username, secret))


def _login(store: Store, business_name: str) -> None:
    key = client_key()
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header(business_name, "Escribe tu usuario y tu PIN o contraseña.", eyebrow="Acceso del equipo")
        with st.form("login"):
            username = st.text_input("Usuario", max_chars=30, autocomplete="username")
            secret = st.text_input("PIN o contraseña", type="password", max_chars=128, autocomplete="current-password")
            otp = st.text_input("Código de verificación", max_chars=6, autocomplete="one-time-code",
                                help="Solo si tienes activada la verificación en dos pasos: el código de 6 cifras de "
                                     "tu app de autenticación.")
            if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                if minutes := client_blocked_minutes(key):
                    st.error(f"Demasiados intentos desde este dispositivo. Espera {minutes} min.")
                    return
                try:
                    user = store.authenticate(username, secret, otp=otp)
                except AuthError as exc:
                    client_failed(key)
                    _time.sleep(0.8)  # slows down scripted guessing from a single session
                    st.error(str(exc))
                else:
                    client_succeeded(key)
                    _sign_in(store, user, secret)
        with st.expander("¿Eres el administrador y no puedes entrar?"):
            _recover(store, key)


def _recover(store: Store, key: str) -> None:
    st.caption("Usa uno de tus códigos de recuperación (los que guardaste al crear la cuenta o en «Equipo y "
               "seguridad»). Cada código sirve una sola vez; también desbloquea la cuenta y desactiva la "
               "verificación en dos pasos, que podrás volver a activar.")
    with st.form("recover", clear_on_submit=True, border=False):
        username = st.text_input("Usuario del administrador", max_chars=30)
        code = st.text_input("Código de recuperación", max_chars=20, placeholder="XXXX-XXXX-XXXX")
        new = st.text_input("Nueva contraseña", type="password", max_chars=128,
                            help="Al menos 8 caracteres, con letras y números o símbolos.")
        repeat = st.text_input("Repite la nueva contraseña", type="password", max_chars=128)
        if st.form_submit_button("Cambiar contraseña y entrar", use_container_width=True):
            if minutes := client_blocked_minutes(key):
                st.error(f"Demasiados intentos desde este dispositivo. Espera {minutes} min.")
                return
            if new != repeat:
                st.error("Las contraseñas no coinciden.")
                return
            try:
                user = store.recover_with_code(username, code, new)
            except AuthError as exc:
                client_failed(key)
                _time.sleep(0.8)
                st.error(str(exc))
            except ValueError as exc:
                st.error(str(exc))
            else:
                client_succeeded(key)
                remaining = store.recovery_codes_left(user["id"])
                st.session_state["recovery_flash"] = (
                    f"Contraseña cambiada. Te quedan {remaining} códigos de recuperación"
                    + (": genera otros nuevos en «Equipo y seguridad»." if remaining <= 2 else "."))
                _sign_in(store, user)


def _show_new_codes() -> None:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header("Guarda tus códigos de recuperación",
                    "Te permiten volver a entrar si olvidas la contraseña, pierdes el móvil o alguien bloquea tu cuenta. "
                    "Cada uno sirve una vez. No se volverán a mostrar.", eyebrow="Importante")
        st.code("\n".join(st.session_state[NEW_CODES]), language=None)
        st.caption("Cópialos o haz una foto y guárdalos fuera de este dispositivo (en papel, o en tu gestor de "
                   "contraseñas).")
        if st.button("Ya los he guardado", type="primary", use_container_width=True):
            st.session_state.pop(NEW_CODES, None)
            st.rerun()


def _force_change(store: Store, user: dict) -> None:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header("Elige un PIN o contraseña más seguro",
                    "El tuyo es de antes de las normas actuales: ahora el PIN debe tener al menos 6 cifras y no "
                    "puede ser una serie fácil (123456, 111111…); la contraseña del administrador, 8 caracteres con "
                    "letras y números.", eyebrow="Seguridad")
        if change_secret_form(store, user, key="force_change"):
            st.session_state.pop(MUST_CHANGE, None)
            st.rerun()


def change_secret_form(store: Store, user: dict, key: str) -> bool:
    with st.form(key, clear_on_submit=True, border=False):
        current = st.text_input("PIN o contraseña actual", type="password", max_chars=128)
        new = st.text_input("Nuevo PIN o contraseña", type="password", max_chars=128)
        repeat = st.text_input("Repítelo", type="password", max_chars=128)
        if st.form_submit_button("Guardar", type="primary", use_container_width=True):
            if new != repeat:
                st.error("No coinciden.")
                return False
            try:
                store.change_own_secret(user["id"], current, new)
            except ValueError as exc:
                st.error(str(exc))
                return False
            return True
    return False


@st.dialog("Cambiar mi PIN o contraseña")
def change_own_secret_dialog(store: Store, user: dict) -> None:
    if change_secret_form(store, user, key="own_change"):
        st.success("Guardado. Úsalo la próxima vez que entres.")


def require_user(store: Store, settings: dict) -> dict | None:
    """Return the signed-in user, or draw the setup/login screen and return None."""
    if not store.has_users():
        _bootstrap(store)
        return None
    user = current_user()
    if user is not None:
        fresh = store.user(user["id"])  # role or access changes apply on the next click
        idle_limit = max(5, int(settings.get("session_minutes") or 720)) * 60
        expired = _time.time() - st.session_state.get(SESSION_SEEN, 0) > idle_limit
        if fresh is None or not fresh["active"] or expired:
            st.session_state.pop(SESSION_USER, None)
            if expired:
                st.info("Tu sesión se cerró por inactividad. Vuelve a entrar.")
        else:
            st.session_state[SESSION_SEEN] = _time.time()
            user = {k: fresh[k] for k in ("id", "username", "name", "role")}
            st.session_state[SESSION_USER] = user
            if st.session_state.get(NEW_CODES):
                _show_new_codes()
                return None
            if st.session_state.get(MUST_CHANGE):
                _force_change(store, user)
                return None
            if flash := st.session_state.pop("recovery_flash", None):
                st.success(flash)
            return user
    _login(store, settings.get("business_name") or "Gestor de Ventas")
    return None


def logout_button(store: Store, user: dict) -> None:
    if st.sidebar.button("Cambiar mi PIN", icon=":material/password:", use_container_width=True):
        change_own_secret_dialog(store, user)
    if st.sidebar.button(f"Cerrar sesión · {user['name']}", icon=":material/logout:", use_container_width=True):
        store.audit(user["username"], "salida")
        for key in (SESSION_USER, "cart", MUST_CHANGE, NEW_CODES):
            st.session_state.pop(key, None)
        st.rerun()


def stamp(user: dict | None) -> str:
    """How a user signs what they do (sales, invoices, closings)."""
    return user["name"] if user else ""
