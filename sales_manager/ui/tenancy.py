"""Several businesses in one app: which business a visit is for, and the operator's panel to manage them.

Only active in multi-business mode (secret `multi_tenant = true`). Each business opens the app at
`…/?negocio=<code>`; the operator panel is at `…/?operador` and needs the secret `operator_password`.
"""

import hmac
import time as _time

import pandas as pd
import streamlit as st

from core.tenants import CODE_RE, STATUSES, normalize_code
from ui.auth import client_blocked_minutes, client_failed, client_key, client_succeeded
from ui.context import _secret, get_directory, multi_tenant
from ui.styles import page_header

OPERATOR_SESSION_HOURS = 2


@st.cache_data(ttl=30, show_spinner=False)
def _tenant(code: str) -> dict | None:
    """Looked up at most every 30 s: a suspension takes effect within half a minute."""
    return get_directory().get(code)


def gate() -> bool:
    """Decide which business this visit is for. Returns False when the page has already been drawn instead."""
    if not multi_tenant():
        return True
    params = st.query_params
    if "operador" in params:
        operator_panel()
        return False
    # The installed app opens at «/»: fall back to the business this browser last used.
    code = normalize_code(params.get("negocio", "")) or st.session_state.get("tenant", "") or _remembered()
    if not code:
        _choose_business()
        return False
    if st.session_state.get("tenant") not in (None, code):
        # Another business in the same browser tab: nothing of the previous one may carry over (user, ticket…).
        for key in list(st.session_state.keys()):
            del st.session_state[key]
    tenant = _tenant(code)
    if tenant is None:
        st.session_state.pop("tenant", None)
        _choose_business(error="No encontramos ese negocio. Revisa la dirección o el código que te dimos.")
        return False
    if tenant["status"] != "activo":
        st.session_state.pop("tenant", None)
        page_header(tenant["name"], eyebrow="Cuenta suspendida")
        st.warning("El acceso a este negocio está suspendido. Escríbenos a nirkana.oficial@gmail.com y lo "
                   "resolvemos.", icon=":material/pause_circle:")
        return False
    st.session_state["tenant"] = code
    if params.get("negocio") != code:
        st.query_params["negocio"] = code  # keep it in the address, so reloads and bookmarks land here
    if _remembered() != code:
        _remember(code)
    return True


REMEMBER_COOKIE = "nk_negocio"


def _remembered() -> str:
    try:
        value = st.context.cookies.get(REMEMBER_COOKIE)
    except Exception:  # no request context (tests, bare mode)
        return ""
    return normalize_code(value) if isinstance(value, str) and CODE_RE.fullmatch(normalize_code(value)) else ""


def _remember(code: str) -> None:
    """Only the business code (it is in the address anyway), for a year."""
    st.html(f"""<script>
document.cookie = "{REMEMBER_COOKIE}={code}; Path=/; Max-Age=31536000; SameSite=Lax"
  + (location.protocol === "https:" ? "; Secure" : "");
</script>""", unsafe_allow_javascript=True)


def _choose_business(error: str = "") -> None:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header("Entra en tu negocio", "Escribe el código de tu negocio. Lo encontrarás en el correo de alta.",
                    eyebrow="NirKanA")
        if error:
            st.error(error)
        with st.form("choose_business"):
            code = st.text_input("Código del negocio", placeholder="p. ej. cafe-aurora", max_chars=40)
            if st.form_submit_button("Continuar", type="primary", width="stretch"):
                st.query_params["negocio"] = normalize_code(code)
                st.rerun()


# ------------------------------------------------------------------ operator
def _operator_signed_in() -> bool:
    since = st.session_state.get("operator_since")
    return bool(since and _time.time() - since < OPERATOR_SESSION_HOURS * 3600)


def operator_panel() -> None:
    expected = _secret("operator_password")
    page_header("Panel de operador", "Alta de negocios, estado y actividad.", eyebrow="NirKanA")
    if not expected:
        st.error("El panel de operador está desactivado: define `operator_password` en los Secrets.")
        return
    if not _operator_signed_in():
        _operator_login(expected)
        return
    directory = get_directory()
    if st.button("Salir del panel", icon=":material/logout:"):
        st.session_state.pop("operator_since", None)
        st.rerun()

    st.markdown("##### Dar de alta un negocio")
    with st.form("new_business", clear_on_submit=True):
        a, b = st.columns(2)
        code = a.text_input("Código (va en la dirección)", placeholder="cafe-aurora", max_chars=40,
                            help="Minúsculas, números y guiones. No se puede cambiar después.")
        name = b.text_input("Nombre del negocio", max_chars=120)
        contact = st.text_input("Contacto (persona, email o teléfono)", max_chars=200)
        if st.form_submit_button("Crear negocio", type="primary"):
            try:
                with st.spinner("Creando el negocio…"):
                    setup = directory.create(code, name, contact)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["operator_created"] = (normalize_code(code), setup)
                _tenant.clear()
                st.rerun()
    if created := st.session_state.pop("operator_created", None):
        _show_setup(*created, intro="Negocio creado.")

    st.markdown("##### Negocios")
    overview = pd.DataFrame(directory.overview())
    if overview.empty:
        st.caption("Aún no hay negocios.")
    else:
        overview["estado"] = overview["status"].map(STATUSES)
        overview["administrador"] = overview["setup_used_at"].map(lambda v: "Creado" if v else "Pendiente")
        st.dataframe(overview[["code", "name", "estado", "administrador", "users", "sales", "last_sale", "errors",
                               "contact", "created_at"]], hide_index=True, width="stretch",
                     column_config={"code": "Código", "name": "Nombre", "estado": "Estado",
                                    "administrador": "Administrador", "users": "Personas", "sales": "Ventas",
                                    "last_sale": "Última venta", "errors": "Errores 7 días",
                                    "contact": "Contacto", "created_at": "Alta"})
        with st.container(border=True):
            chosen = st.selectbox("Gestionar", list(overview["code"]), format_func=lambda c: f"{c} · " + str(
                overview.set_index("code").loc[c, "name"]))
            current = overview.set_index("code").loc[chosen, "status"]
            a, b = st.columns(2)
            target = "suspendido" if current == "activo" else "activo"
            if a.button("Suspender acceso" if target == "suspendido" else "Reactivar acceso", width="stretch",
                        icon=":material/pause_circle:" if target == "suspendido" else ":material/play_circle:"):
                directory.set_status(chosen, target)
                _tenant.clear()
                st.rerun()
            if b.button("Nuevo código de instalación", width="stretch", icon=":material/key:",
                        help="Si el negocio perdió el suyo antes de crear su administrador."):
                st.session_state["operator_created"] = (chosen, directory.new_setup_code(chosen))
                st.rerun()

    with st.expander("Registro del operador"):
        st.dataframe(pd.DataFrame(directory.log()), hide_index=True, width="stretch")


def _show_setup(code: str, setup: str, intro: str) -> None:
    st.success(f"{intro} Envía al negocio estos dos datos (el código solo se muestra ahora):", icon=":material/check:")
    st.code(f"Dirección: …/?negocio={code}\nCódigo de instalación: {setup}", language=None)


def _operator_login(expected: str) -> None:
    key = "operador:" + client_key()
    with st.form("operator_login"):
        secret = st.text_input("Contraseña de operador", type="password", max_chars=128)
        if st.form_submit_button("Entrar", type="primary"):
            if minutes := client_blocked_minutes(key):
                st.error(f"Demasiados intentos. Vuelve a probar en {minutes} min.")
                return
            if hmac.compare_digest(secret.encode(), expected.encode()):
                client_succeeded(key)
                st.session_state["operator_since"] = _time.time()
                st.rerun()
            client_failed(key)
            _time.sleep(1)
            st.error("Contraseña incorrecta.")
