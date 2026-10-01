"""Staff accounts: first-run administrator setup, login, idle timeout and logout."""

import hmac
import threading
import time as _time
from collections import deque

import streamlit as st

from core.db import AuthError, Store
from core.security import ROLES
from ui.styles import page_header

SESSION_USER = "user"
SESSION_SEEN = "last_seen"

# Setup-password attempts are throttled across every visitor, not per browser tab.
_SETUP_FAILURES: deque = deque()
_SETUP_LOCK = threading.Lock()
SETUP_MAX_FAILURES, SETUP_WINDOW_SECONDS = 10, 600


def configured_password() -> str | None:
    """`app_password` from Streamlit secrets: proves ownership when the first administrator is created."""
    try:
        return st.secrets.get("app_password") or None
    except Exception:  # no secrets file: running locally
        return None


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


def _sign_in(store: Store, user: dict) -> None:
    st.session_state[SESSION_USER] = user
    st.session_state[SESSION_SEEN] = _time.time()
    st.rerun()


def _is_local_request() -> bool:
    try:
        host = (st.context.headers.get("Host") or "").split(":")[0].strip("[]").lower()
    except Exception:
        host = ""
    return host in {"", "localhost", "127.0.0.1", "::1"}


def _bootstrap(store: Store) -> None:
    """No accounts yet: create the administrator. Requires `app_password` when it is configured."""
    setup_password = configured_password()
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header("Crea tu cuenta de administrador",
                    "Será la cuenta con todos los permisos. Después podrás dar de alta a tu equipo.",
                    eyebrow="Primer acceso")
        if not setup_password and not _is_local_request():
            # Published without a setup password: whoever arrived first would own the app. Refuse.
            st.error("Para crear el administrador en una app publicada, añade primero `app_password` en los "
                     "*Secrets* de Streamlit (⋮ → Settings → Secrets) y recarga esta página.",
                     icon=":material/lock:")
            return
        if not setup_password:
            st.info("Estás en tu propio ordenador. Si publicas la app, configura `app_password` en los *Secrets* "
                    "para que solo tú puedas crear el administrador.", icon=":material/info:")
        with st.form("bootstrap"):
            code = st.text_input("Contraseña de instalación (app_password)", type="password") if setup_password else ""
            name = st.text_input("Tu nombre", max_chars=120)
            username = st.text_input("Usuario", max_chars=30, placeholder="p. ej. ismael",
                                     help="Minúsculas, números, punto o guion. Lo usarás para entrar.")
            secret = st.text_input("Contraseña", type="password", max_chars=128,
                                   help="Al menos 8 caracteres, con letras y números o símbolos.")
            repeat = st.text_input("Repite la contraseña", type="password", max_chars=128)
            if st.form_submit_button("Crear administrador", type="primary", use_container_width=True):
                if setup_password and _setup_blocked():
                    st.error("Demasiados intentos. Espera unos minutos.")
                    return
                if setup_password and not hmac.compare_digest(code.encode(), setup_password.encode()):
                    _setup_failed()
                    _time.sleep(1)
                    st.error("La contraseña de instalación no es correcta.")
                    return
                if secret != repeat:
                    st.error("Las contraseñas no coinciden.")
                    return
                if store.has_users():  # someone else finished first
                    st.rerun()
                try:
                    store.create_user(name, username, "admin", secret)
                except ValueError as exc:
                    st.error(str(exc))
                    return
                _sign_in(store, store.authenticate(username, secret))


def _login(store: Store, business_name: str) -> None:
    users = store.users()
    users = users[users["active"] == 1]
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header(business_name, "Elige tu nombre y escribe tu PIN o contraseña.", eyebrow="Acceso del equipo")
        with st.form("login"):
            options = dict(zip(users["username"], users["name"] + " · " + users["role"].map(ROLES)))
            username = st.selectbox("¿Quién eres?", list(options), format_func=options.get)
            secret = st.text_input("PIN o contraseña", type="password", max_chars=128)
            if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                try:
                    user = store.authenticate(username, secret)
                except AuthError as exc:
                    _time.sleep(0.8)  # slows down scripted guessing from a single session
                    st.error(str(exc))
                else:
                    _sign_in(store, user)


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
            return user
    _login(store, settings.get("business_name") or "Gestor de Ventas")
    return None


def logout_button(store: Store, user: dict) -> None:
    if st.sidebar.button(f"Cerrar sesión · {user['name']}", icon=":material/logout:", use_container_width=True):
        store.audit(user["username"], "salida")
        st.session_state.pop(SESSION_USER, None)
        st.session_state.pop("cart", None)
        st.rerun()


def stamp(user: dict | None) -> str:
    """How a user signs what they do (sales, invoices, closings)."""
    return user["name"] if user else ""
