"""Team accounts, roles and account security."""

import pandas as pd
import streamlit as st

from core.security import ROLES, new_totp_secret, totp_uri
from ui.context import ctx, logged_download
from ui.pages_common import csv_bytes, require_role
from ui.styles import page_header


# ---------------------------------------------------------------------- team
def team_page() -> None:
    c = ctx()
    if not require_role(c, "admin"):
        return
    page_header("Equipo y seguridad", "Da de alta a tu equipo: cada persona entra con su nombre y su PIN, y todo "
                "lo que hace queda firmado.", eyebrow="Ajustes")
    if "team_flash" in st.session_state:
        st.success(st.session_state.pop("team_flash"))

    users = c.store.users()
    m1, m2, m3 = st.columns(3)
    m1.metric("Personas activas", int(users["active"].sum()))
    m2.metric("Administradores", int(((users["role"] == "admin") & (users["active"] == 1)).sum()))
    m3.metric("Cierre de sesión por inactividad", f"{int(c.settings.get('session_minutes') or 480) // 60} h")

    roles_help = ("**Administrador:** todo, incluida la configuración y el equipo. "
                  "**Encargado:** panel, caja, catálogo, clientes, facturas y anulaciones. "
                  "**Empleado:** vender, agenda y consultar tickets.")
    st.caption(roles_help)
    places = {loc["id"]: loc["name"] for loc in c.locations}
    st.dataframe(
        users.assign(role=users["role"].map(ROLES), active=users["active"].astype(bool),
                     two_factor=users["two_factor"].astype(bool),
                     last_login=pd.to_datetime(users["last_login"].replace("", None)),
                     place=users["location_id"].map(places).fillna("Cualquiera")),
        hide_index=True, width="stretch",
        column_order=["name", "username", "role", *(["place"] if c.multi_location else []), "active", "two_factor",
                      "last_login"],
        column_config={"name": "Nombre", "username": "Usuario", "role": "Rol", "place": "Local",
                       "active": st.column_config.CheckboxColumn("Activo"),
                       "two_factor": st.column_config.CheckboxColumn("Dos pasos"),
                       "last_login": st.column_config.DatetimeColumn("Último acceso", format="DD/MM/YYYY HH:mm")},
    )

    add, manage = st.columns(2, gap="large")
    with add, st.container(border=True):
        st.markdown("**Añadir persona**")
        with st.form("new_user", clear_on_submit=True, border=False):
            name = st.text_input("Nombre", max_chars=120, placeholder="Ej.: Lucía")
            username = st.text_input("Usuario", max_chars=30, placeholder="Ej.: lucia")
            role = st.selectbox("Rol", list(ROLES), index=2, format_func=ROLES.get)
            secret = st.text_input("PIN o contraseña", type="password", max_chars=128,
                                   help="Empleados y encargados: mínimo 6 cifras o caracteres, sin series fáciles "
                                        "(123456, 111111). Administradores: mínimo 8, con letras y números.")
            if st.form_submit_button("Añadir", type="primary", icon=":material/person_add:"):
                try:
                    c.store.create_user(name, username, role, secret, by=c.username)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["team_flash"] = f"{name} ya puede entrar con su usuario «{username.lower()}»."
                    st.rerun()

    with manage, st.container(border=True):
        st.markdown("**Modificar persona**")
        if users.empty:
            st.caption("Todavía no hay nadie en el equipo.")
        else:
            options = dict(zip(users["id"].astype(int), users["name"] + " (" + users["username"] + ")"))
            uid = st.selectbox("Persona", list(options), format_func=options.get, key="team_user")
            _manage_user(c, users.set_index("id").loc[uid], uid)

    _own_account_security(c)

    st.markdown("#### Registro de actividad")
    st.caption("Accesos, intentos fallidos, anulaciones, facturas, cierres de caja, cambios de configuración y "
               "cada descarga de datos (exportaciones, copias y datos de clientes).")
    log = c.store.audit_log()
    views = {"Todo": None, "Accesos fallidos": {"acceso_fallido"},
             "Descargas de datos": {"exportacion", "datos_exportados"},
             "Clientes (RGPD)": {"datos_exportados", "cliente_suprimido", "consentimiento_publicidad"}}
    shown = st.segmented_control("Mostrar", list(views), default="Todo", key="audit_view") or "Todo"
    if views[shown]:
        log = log[log["action"].isin(views[shown])]
    st.dataframe(log, hide_index=True, width="stretch", column_config={
        "happened_at": st.column_config.DatetimeColumn("Cuándo", format="DD/MM/YYYY HH:mm:ss"),
        "username": "Usuario", "action": "Acción", "detail": "Detalle",
    })
    logged_download(st, "Exportar registro a CSV", csv_bytes(log), "registro_actividad.csv", "text/csv",
                       icon=":material/download:")
    errors = c.store.recent_errors(7)
    with st.expander(f"Errores de la app en 7 días: {len(errors)}", icon=":material/bug_report:"):
        if errors.empty:
            st.caption("Ninguno. Si alguna pantalla falla, aparecerá aquí con su referencia.")
        else:
            st.dataframe(errors, hide_index=True, width="stretch", column_config={
                "happened_at": st.column_config.DatetimeColumn("Cuándo", format="DD/MM/YYYY HH:mm"),
                "ref": "Referencia", "page": "Pantalla", "username": "Usuario", "kind": "Tipo", "where_": "Dónde"})


def _own_account_security(c) -> None:
    """Recovery codes and two-step verification for the administrator who is signed in."""
    st.markdown("#### Seguridad de tu cuenta")
    codes_col, totp_col = st.columns(2, gap="large")
    if c.user is None or c.user["role"] != "admin":
        return
    with codes_col, st.container(border=True):
        left = c.store.recovery_codes_left(c.user["id"])
        st.markdown("**Códigos de recuperación**")
        st.caption(f"Te quedan **{left}**. Sirven para volver a entrar si olvidas la contraseña, pierdes el móvil "
                   "o alguien bloquea tu cuenta." + (" **Genera unos nuevos.**" if left <= 2 else ""))
        if st.button("Generar códigos nuevos", key="new_codes", icon=":material/key:",
                     help="Los anteriores que no hayas usado dejarán de funcionar."):
            st.session_state["team_codes"] = c.store.create_recovery_codes(c.user["id"], by=c.username)
        if st.session_state.get("team_codes"):
            st.warning("Guárdalos ahora fuera de este dispositivo: no se volverán a mostrar.", icon=":material/key:")
            st.code("\n".join(st.session_state["team_codes"]), language=None)
            if st.button("Ya los he guardado", key="codes_saved"):
                st.session_state.pop("team_codes", None)
                st.rerun()
    with totp_col, st.container(border=True):
        st.markdown("**Verificación en dos pasos**")
        me = c.store.user(c.user["id"])
        if me is None:
            return
        enabled = bool(me["two_factor"])
        if enabled:
            st.success("Activada: al entrar se pide también el código de tu app de autenticación.",
                       icon=":material/verified_user:")
            with st.form("totp_off", clear_on_submit=True, border=False):
                code = st.text_input("Código actual de la app para desactivarla", max_chars=6)
                if st.form_submit_button("Desactivar"):
                    try:
                        c.store.disable_two_factor(c.user["id"], code)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.rerun()
            return
        st.caption("Recomendado para el administrador: aunque alguien adivine tu contraseña, sin tu móvil no entra. "
                   "Usa Google Authenticator, Microsoft Authenticator o similar.")
        secret = st.session_state.setdefault("totp_pending", new_totp_secret())
        st.markdown("1. En la app, añade una cuenta con **«Introducir clave de configuración»** y escribe esta clave "
                    "(tipo: basada en tiempo):")
        st.code(" ".join(secret[i:i + 4] for i in range(0, len(secret), 4)), language=None)
        st.caption(f"Cuenta: {c.username} · NirKanA. En el móvil también puedes abrir este enlace: "
                   f"[añadir a la app]({totp_uri(secret, c.username)}).")
        with st.form("totp_on", clear_on_submit=True, border=False):
            code = st.text_input("2. Escribe el código de 6 cifras que muestra la app", max_chars=6)
            if st.form_submit_button("Activar", type="primary"):
                try:
                    c.store.enable_two_factor(c.user["id"], secret, code)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.pop("totp_pending", None)
                    st.rerun()


def _manage_user(c, target, uid: int) -> None:
    new_role = st.selectbox("Rol", list(ROLES), index=list(ROLES).index(target["role"]), format_func=ROLES.get,
                            key=f"team_role_{uid}")
    active = st.toggle("Puede entrar", value=bool(target["active"]), key=f"team_active_{uid}")
    location = target.get("location_id")
    if c.multi_location:
        places = {0: "Cualquier local", **{loc["id"]: loc["name"] for loc in c.locations}}
        current = int(location) if pd.notna(location) and int(location) in places else 0
        location = st.selectbox("Local", list(places), index=list(places).index(current), format_func=places.get,
                                key=f"team_location_{uid}",
                                help="Fijado a un local, solo vende, cobra y ve la caja de ese local.") or None
    new_secret = st.text_input("Nuevo PIN o contraseña (opcional)", type="password", max_chars=128,
                               key=f"team_secret_{uid}")
    if st.button("Guardar cambios", type="primary", key=f"team_save_{uid}", icon=":material/save:"):
        try:
            c.store.update_user(uid, role=new_role, active=active, by=c.username)
            if c.multi_location:
                c.store.set_user_location(uid, location)
            if new_secret:
                c.store.set_user_secret(uid, new_secret, by=c.username)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["team_flash"] = f"Cambios guardados para {target['name']}."
            st.rerun()
