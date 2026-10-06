"""Staff accounts: first-run administrator setup, login, recovery, idle timeout and logout."""

import hmac
import secrets
import threading
import time as _time
from collections import deque

import streamlit as st

from core import logs, throttle
from core.db import AuthError, Store
from core.security import check_secret_strength
from ui.context import secrets_lookup, setting
from ui.styles import page_header

SESSION_USER = "user"
SESSION_SEEN = "last_seen"
SESSION_TOKEN = "session_token"
# The browser remembers the sign-in in a cookie (only a random token), so reloading or reopening the tab keeps
# staff signed in until the business's idle time runs out. The server decides; the cookie only identifies.
COOKIE = "nk_sesion"  # one per business in multi-business mode: nk_sesion_<code>
COOKIE_DAYS = 7
_COOKIE_SET, _COOKIE_CLEAR = "cookie_to_set", "cookie_to_clear"
MUST_CHANGE = "must_change_secret"
NEW_CODES = "new_recovery_codes"

# Guessing is slowed per device (browser address), not per account (see core/throttle.py). With a database the
# counters live there, so every server shares them and a restart does not reset them.
CLIENT_MAX_FAILURES, CLIENT_WINDOW_SECONDS = throttle.MAX_FAILURES, throttle.WINDOW_SECONDS
CLIENT_FIRST_BLOCK_MINUTES, CLIENT_MAX_BLOCK_MINUTES = throttle.FIRST_BLOCK_MINUTES, throttle.MAX_BLOCK_MINUTES
_MEMORY = throttle.MemoryThrottle()
log = logs.get("auth")

# Setup-password attempts are throttled across every visitor, not per browser tab.
_SETUP_FAILURES: deque = deque()
_SETUP_LOCK = threading.Lock()
SETUP_MAX_FAILURES, SETUP_WINDOW_SECONDS = 10, 600
_SETUP_CODE: str | None = None


def configured_password() -> str | None:
    """`app_password` (Streamlit secrets or APP_PASSWORD): proves ownership when the first administrator is created."""
    return setting("app_password") or None


def client_key() -> str:
    """The visitor's address as seen by the hosting proxy (its last X-Forwarded-For entry), or the socket peer."""
    try:
        forwarded = st.context.headers.get("X-Forwarded-For") or ""
        if forwarded.strip():
            return forwarded.split(",")[-1].strip()
        return st.context.ip_address or "local"
    except Exception:  # no request context (tests, bare mode)
        return "local"


def client_blocked_minutes(key: str, now: float | None = None, store=None) -> int:
    """`store`: a Store or the operator Directory that keeps the counters; None keeps them in memory."""
    return store.throttle_blocked_minutes(key, now) if store is not None else _MEMORY.blocked_minutes(key, now)


def client_failed(key: str, now: float | None = None, store=None) -> None:
    if store is not None:
        store.throttle_failed(key, now)
    else:
        _MEMORY.failed(key, now)


def client_succeeded(key: str, store=None) -> None:
    if store is not None:
        store.throttle_succeeded(key)
    else:
        _MEMORY.succeeded(key)


def current_user() -> dict | None:
    return st.session_state.get(SESSION_USER)


def _cookie_name() -> str:
    from ui.context import tenant_code

    code = tenant_code()
    return f"{COOKIE}_{code.replace('-', '_')}" if code else COOKIE


def _cookie_token() -> str:
    try:
        cookies = st.context.cookies
        value = cookies.get(f"__Host-{_cookie_name()}") or cookies.get(_cookie_name())
    except Exception:  # no request context (tests, bare mode)
        return ""
    return value if isinstance(value, str) else ""


def _user_agent() -> str:
    try:
        return st.context.headers.get("User-Agent") or ""
    except Exception:
        return ""


def _write_cookie() -> None:
    """Send the pending cookie change to the browser (the token only travels to this person's own page)."""
    token = st.session_state.pop(_COOKIE_SET, None)
    clear = st.session_state.pop(_COOKIE_CLEAR, False)
    if token is None and not clear:
        return
    value, age = (token, COOKIE_DAYS * 86400) if token else ("", 0)
    # Over HTTPS the name carries the __Host- prefix: the browser then refuses it unless it is Secure, for this
    # exact host and path /, so no other subdomain or plain-HTTP page can plant or overwrite it.
    st.html(f"""<script>
(() => {{
  const name = "{_cookie_name()}", secure = location.protocol === "https:";
  document.cookie = (secure ? "__Host-" : "") + name + "={value}; Path=/; Max-Age={age}; SameSite=Strict"
    + (secure ? "; Secure" : "");
  if (secure) document.cookie = name + "=; Path=/; Max-Age=0; SameSite=Strict";  // the old, unprefixed one
}})();
</script>""", unsafe_allow_javascript=True)


def _remember(store: Store, user: dict) -> None:
    st.session_state[SESSION_TOKEN] = st.session_state[_COOKIE_SET] = store.create_session(user["id"], _user_agent())


def _forget(store: Store) -> None:
    store.end_session(st.session_state.pop(SESSION_TOKEN, "") or _cookie_token())
    st.session_state[_COOKIE_CLEAR] = True


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
    _remember(store, user)
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
            log.warning("setup_code code=%s (para crear el primer administrador)", _SETUP_CODE)
        return _SETUP_CODE


def _bootstrap(store: Store) -> None:
    """No accounts yet: create the administrator, proving ownership with `app_password` or the setup code.
    With several businesses in one app, each business proves it with the one-time code the operator gave it."""
    from ui.context import get_directory, multi_tenant, tenant_code

    business = tenant_code() if multi_tenant() else ""
    if business:
        def valid(entered: str) -> bool:
            return get_directory().check_setup_code(business, entered)
    else:
        expected = configured_password() or setup_code()

        def valid(entered: str) -> bool:
            return hmac.compare_digest(entered.strip().encode(), expected.encode())
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header("Crea tu cuenta de administrador",
                    "Será la cuenta con todos los permisos. Después podrás dar de alta a tu equipo.",
                    eyebrow="Primer acceso")
        if business:
            code_label = "Código de instalación de tu negocio"
            st.info("Es el código de 8 caracteres que te dimos al dar de alta tu negocio. Solo sirve una vez.",
                    icon=":material/key:")
        elif configured_password():
            code_label = "Contraseña de instalación (app_password)"
        else:
            code_label = "Código de instalación"
            st.info("Escribe el código de instalación que aparece en el registro del servidor: en tu ordenador, "
                    "en la terminal; en Streamlit, en «Manage app → Logs». Si configuras `app_password` en los "
                    "*Secrets*, se usará esa contraseña en su lugar.", icon=":material/key:")
        with st.form("bootstrap"):
            code = st.text_input(code_label, type="password", max_chars=128)
            name = st.text_input("Tu nombre", max_chars=120)
            username = st.text_input("Usuario", max_chars=30, placeholder="p. ej. marta",
                                     help="Minúsculas, números, punto o guion. Lo usarás para entrar.")
            secret = st.text_input("Contraseña", type="password", max_chars=128,
                                   help="Al menos 8 caracteres, con letras y números o símbolos.")
            repeat = st.text_input("Repite la contraseña", type="password", max_chars=128)
            if st.form_submit_button("Crear administrador", type="primary", width="stretch"):
                if _setup_blocked():
                    st.error("Demasiados intentos. Espera unos minutos.")
                    return
                if not valid(code):
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
                if business:
                    get_directory().mark_setup_used(business)
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
            if st.form_submit_button("Entrar", type="primary", width="stretch"):
                if minutes := client_blocked_minutes(key, store=store):
                    st.error(f"Demasiados intentos desde este dispositivo. Espera {minutes} min.")
                    return
                try:
                    user = store.authenticate(username, secret, otp=otp)
                except AuthError as exc:
                    client_failed(key, store=store)
                    _time.sleep(0.8)  # slows down scripted guessing from a single session
                    st.error(str(exc))
                else:
                    client_succeeded(key, store=store)
                    _sign_in(store, user, secret)
        with st.expander("¿Eres el administrador y no puedes entrar?"):
            _recover(store, key)
        if mailer() is not None:
            with st.expander("¿Has olvidado tu contraseña de administrador? Recíbela por email"):
                _email_reset(store, key)


def mailer():
    """The app's sending account (secrets smtp_*), or None when email is not set up."""
    from core.mailer import Mailer

    return Mailer.from_settings(secrets_lookup)


def _email_reset(store: Store, key: str) -> None:
    """Step 1: a 6-digit code to the business email. Step 2: the code and a new password. The answer to step 1 is
    the same whether or not the user exists, so it reveals nothing about who works here."""
    st.caption("Te enviaremos un código al email del negocio (el que figura en Configuración). Caduca en 15 minutos.")
    with st.form("email_reset_start", border=False):
        username = st.text_input("Usuario del administrador", max_chars=30, key="reset_user")
        if st.form_submit_button("Enviarme el código", width="stretch"):
            if minutes := client_blocked_minutes(key, store=store):
                st.error(f"Demasiados intentos desde este dispositivo. Espera {minutes} min.")
                return
            started = store.start_password_reset(username)
            if started:
                code, email = started
                try:
                    mailer().send(email, "Tu código para cambiar la contraseña",
                                  f"Hola:\n\nTu código es {code}. Caduca en 15 minutos.\n\nSi no lo has pedido tú, "
                                  "ignora este mensaje: tu contraseña no cambia.\n\nNirKanA")
                except Exception as exc:  # noqa: BLE001 - the visitor gets the same answer; the log keeps the cause
                    store.audit(username, "email_no_enviado", type(exc).__name__)
                    log.warning("email_not_sent purpose=password_reset error=%s", type(exc).__name__)
            _time.sleep(0.5)
            st.info("Si ese usuario es administrador y el negocio tiene email, te hemos enviado un código al email "
                    "del negocio. ¿No llega en unos minutos? Usa uno de tus códigos de recuperación.")
    with st.form("email_reset_finish", clear_on_submit=True, border=False):
        code = st.text_input("Código recibido", max_chars=6)
        new = st.text_input("Nueva contraseña", type="password", max_chars=128,
                            help="Al menos 8 caracteres, con letras y números o símbolos.")
        repeat = st.text_input("Repite la nueva contraseña", type="password", max_chars=128)
        if st.form_submit_button("Cambiar contraseña", width="stretch"):
            if new != repeat:
                st.error("Las contraseñas no coinciden.")
                return
            try:
                changed = store.finish_password_reset(st.session_state.get("reset_user", ""), code, new)
            except ValueError as exc:
                st.error(str(exc))
                return
            if not changed:
                client_failed(key, store=store)
                _time.sleep(0.8)
                st.error("El código no es correcto o ha caducado. Pide otro.")
                return
            client_succeeded(key, store=store)
            st.success("Contraseña cambiada. Ya puedes entrar con ella.")


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
        if st.form_submit_button("Cambiar contraseña y entrar", width="stretch"):
            if minutes := client_blocked_minutes(key, store=store):
                st.error(f"Demasiados intentos desde este dispositivo. Espera {minutes} min.")
                return
            if new != repeat:
                st.error("Las contraseñas no coinciden.")
                return
            try:
                user = store.recover_with_code(username, code, new)
            except AuthError as exc:
                client_failed(key, store=store)
                _time.sleep(0.8)
                st.error(str(exc))
            except ValueError as exc:
                st.error(str(exc))
            else:
                client_succeeded(key, store=store)
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
        if st.button("Ya los he guardado", type="primary", width="stretch"):
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
        if st.form_submit_button("Guardar", type="primary", width="stretch"):
            if new != repeat:
                st.error("No coinciden.")
                return False
            try:
                store.change_own_secret(user["id"], current, new)
            except ValueError as exc:
                st.error(str(exc))
                return False
            _remember(store, user)  # the change signs out every device; this one stays in
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
    idle_minutes = max(5, int(settings.get("session_minutes") or 480))
    user = current_user()
    if user is None and not st.session_state.get(_COOKIE_CLEAR):
        token = _cookie_token()
        resumed = store.resume_session(token, idle_minutes, _user_agent()) if token else None
        if resumed is not None:  # a reload or a reopened tab: carry on where they were
            user = st.session_state[SESSION_USER] = resumed
            st.session_state[SESSION_SEEN] = _time.time()
            st.session_state[SESSION_TOKEN] = token
    if user is not None:
        fresh = store.user(user["id"])  # role or access changes apply on the next click
        expired = _time.time() - st.session_state.get(SESSION_SEEN, 0) > idle_minutes * 60
        token = st.session_state.get(SESSION_TOKEN)
        ended = token is not None and store.resume_session(token, idle_minutes, _user_agent()) is None  # PIN changed
        if fresh is None or not fresh["active"] or expired or ended:
            st.session_state.pop(SESSION_USER, None)
            st.session_state.pop("cart", None)
            _forget(store)
            if expired:
                st.info("Tu sesión se cerró por inactividad. Vuelve a entrar.")
        else:
            _write_cookie()
            st.session_state[SESSION_SEEN] = _time.time()
            user = {k: fresh[k] for k in ("id", "username", "name", "role", "location_id")}
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
    _write_cookie()
    _login(store, settings.get("business_name") or "Gestor de Ventas")
    return None


def logout_button(store: Store, user: dict) -> None:
    if st.sidebar.button("Cambiar mi PIN", icon=":material/password:", width="stretch"):
        change_own_secret_dialog(store, user)
    if st.sidebar.button(f"Cerrar sesión · {user['name']}", icon=":material/logout:", width="stretch"):
        store.audit(user["username"], "salida")
        _forget(store)
        for key in (SESSION_USER, "cart", MUST_CHANGE, NEW_CODES):
            st.session_state.pop(key, None)
        st.rerun()


def stamp(user: dict | None) -> str:
    """How a user signs what they do (sales, invoices, closings)."""
    return user["name"] if user else ""
