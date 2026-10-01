"""Optional password gate, enabled by setting `app_password` in Streamlit secrets."""

import hmac

import streamlit as st

from ui.styles import page_header


def configured_password() -> str | None:
    try:
        return st.secrets.get("app_password") or None
    except Exception:  # no secrets file: running locally without protection
        return None


def require_login() -> bool:
    """Render the login screen and return False until the visitor enters the right password."""
    password = configured_password()
    if not password or st.session_state.get("authenticated"):
        return True
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header("Gestor de Ventas", "Introduce la contraseña para acceder a tu negocio.", eyebrow="Acceso privado")
        with st.form("login"):
            attempt = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                if hmac.compare_digest(attempt.encode(), str(password).encode()):
                    st.session_state["authenticated"] = True
                    st.rerun()
                st.error("Contraseña incorrecta. Inténtalo de nuevo.")
    return False


def logout_button() -> None:
    if configured_password() and st.sidebar.button("Cerrar sesión", icon=":material/logout:"):
        st.session_state.pop("authenticated", None)
        st.rerun()
