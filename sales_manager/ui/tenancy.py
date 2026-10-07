"""Several businesses in one app: which business a visit is for, and the operator's panel to manage them.

Only active in multi-business mode (secret `multi_tenant = true`). Each business opens the app at
`…/?negocio=<code>`; the operator panel is at `…/?operador` and needs the secret `operator_password`, plus a
code from an authenticator app once `operator_totp_secret` is set.
"""

import hmac
import time as _time

import pandas as pd
import streamlit as st

from core import billing
from core.security import new_totp_secret, totp_step, totp_uri
from core.tenants import BILLING_ALERTS, CODE_RE, STATUSES, normalize_code
from ui.auth import client_blocked_minutes, client_failed, client_key, client_succeeded
from ui.context import get_directory, multi_tenant, setting, stripe_client, trial_days
from ui.styles import page_header

OPERATOR_SESSION_HOURS = 2


@st.cache_data(ttl=30, show_spinner=False)
def tenant_info(code: str) -> dict | None:
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
    # Trying codes one after another to learn which businesses exist is slowed down like a password guess. Only a
    # new lookup is checked: a session already in its business costs no extra query per click.
    lookup = "negocio:" + client_key()
    if st.session_state.get("tenant") != code and (minutes := client_blocked_minutes(lookup, store=get_directory())):
        _choose_business(error=f"Demasiados códigos que no existen desde este dispositivo. Espera {minutes} min.")
        return False
    tenant = tenant_info(code)
    if tenant is None:
        client_failed(lookup, store=get_directory())
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
    st.session_state["billing_access"] = _billing_access(tenant)
    if params.get("negocio") != code:
        st.query_params["negocio"] = code  # keep it in the address, so reloads and bookmarks land here
    if _remembered() != code:
        _remember(code)
    return True


def _billing_access(tenant: dict) -> billing.Access:
    """Billing state of this visit's business (see Directory.access_for); this only handles the address."""
    params = st.query_params
    returning = params.get("session_id", "") if params.get("pago") == "ok" else ""
    stripe = stripe_client()
    access, message, refreshed = get_directory().access_for(tenant, stripe, returning)
    if returning:
        for key in ("pago", "session_id"):
            params.pop(key, None)
    if message:
        st.session_state["billing_flash"] = message
    if refreshed:
        tenant_info.clear()  # the cached copy of the business is out of date
    return access


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
    expected = setting("operator_password")
    page_header("Panel de operador", "Alta de negocios, estado y actividad.", eyebrow="NirKanA")
    if not expected:
        st.error("El panel de operador está desactivado: define `operator_password` en los Secrets.")
        return
    if not _operator_signed_in():
        _operator_login(expected)
        return
    directory = get_directory()
    _operator_2fa_notice()
    _backup_status(directory)
    _billing_alerts(directory)
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
                    setup = directory.create(code, name, contact, trial_days=trial_days())
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["operator_created"] = (normalize_code(code), setup)
                tenant_info.clear()
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
        overview["pago"] = [billing.STATUS_LABELS["cortesia"] if exempt else billing.STATUS_LABELS.get(status, status)
                            for status, exempt in zip(overview["billing_status"], overview["billing_exempt"])]
        overview["hasta"] = [(end or trial)[:10] for end, trial in zip(overview["period_end"], overview["trial_ends"])]
        overview["condiciones"] = [f"v. {v} ({at[:10]})" if v else "Pendientes"
                                   for v, at in zip(overview["terms_version"], overview["terms_accepted_at"])]
        st.dataframe(overview[["code", "name", "estado", "pago", "hasta", "administrador", "condiciones", "users", "sales",
                               "last_sale", "errors", "contact", "created_at"]], hide_index=True, width="stretch",
                     column_config={"code": "Código", "name": "Nombre", "estado": "Estado", "pago": "Suscripción",
                                    "hasta": "Prueba o periodo hasta (UTC)",
                                    "administrador": "Administrador", "condiciones": "Condiciones aceptadas",
                                    "users": "Personas", "sales": "Ventas",
                                    "last_sale": "Última venta", "errors": "Errores 7 días",
                                    "contact": "Contacto", "created_at": "Alta"})
        if stripe_client() is None:
            st.caption("Cobro desactivado: sin `stripe_secret_key` y `stripe_price_id` en los Secrets, nadie paga.")
        with st.container(border=True):
            chosen = st.selectbox("Gestionar", list(overview["code"]), format_func=lambda c: f"{c} · " + str(
                overview.set_index("code").loc[c, "name"]))
            current = overview.set_index("code").loc[chosen, "status"]
            a, b = st.columns(2)
            target = "suspendido" if current == "activo" else "activo"
            if a.button("Suspender acceso" if target == "suspendido" else "Reactivar acceso", width="stretch",
                        icon=":material/pause_circle:" if target == "suspendido" else ":material/play_circle:"):
                directory.set_status(chosen, target)
                tenant_info.clear()
                st.rerun()
            if b.button("Nuevo código de instalación", width="stretch", icon=":material/key:",
                        help="Si el negocio perdió el suyo antes de crear su administrador."):
                st.session_state["operator_created"] = (chosen, directory.new_setup_code(chosen))
                st.rerun()
            row = overview.set_index("code").loc[chosen]
            x, y, z = st.columns(3)
            exempt = bool(row["billing_exempt"])
            if x.button("Quitar cortesía" if exempt else "Sin cargo (cortesía)", width="stretch",
                        icon=":material/redeem:", help="Negocios piloto o amigos: nunca se les pide pagar."):
                directory.set_billing_exempt(chosen, not exempt)
                tenant_info.clear()
                st.rerun()
            if y.button("Ampliar prueba 14 días", width="stretch", icon=":material/more_time:"):
                directory.extend_trial(chosen, 14)
                tenant_info.clear()
                st.rerun()
            stripe = stripe_client()
            if z.button("Comprobar en Stripe", width="stretch", icon=":material/sync:",
                        disabled=stripe is None or not row["stripe_customer"]):
                try:
                    directory.sync_subscription(chosen, stripe)
                except billing.BillingError as exc:
                    st.error(str(exc))
                else:
                    tenant_info.clear()
                    st.rerun()

    with st.expander("Registro del operador"):
        st.dataframe(pd.DataFrame(directory.log()), hide_index=True, width="stretch")


def _show_setup(code: str, setup: str, intro: str) -> None:
    st.success(f"{intro} Envía al negocio estos dos datos (el código solo se muestra ahora):", icon=":material/check:")
    st.code(f"Dirección: …/?negocio={code}\nCódigo de instalación: {setup}", language=None)


def _operator_login(expected: str) -> None:
    key = "operador:" + client_key()
    directory = get_directory()
    totp_secret = setting("operator_totp_secret")
    with st.form("operator_login"):
        secret = st.text_input("Contraseña de operador", type="password", max_chars=128)
        code = st.text_input("Código de tu app de autenticación", max_chars=8,
                             help="Las 6 cifras de Google Authenticator, Microsoft Authenticator o similar.") \
            if totp_secret else ""
        if st.form_submit_button("Entrar", type="primary"):
            if minutes := client_blocked_minutes(key, store=directory):
                st.error(f"Demasiados intentos. Vuelve a probar en {minutes} min.")
                return
            password_ok = hmac.compare_digest(secret.encode(), expected.encode())
            step = totp_step(totp_secret, code) if totp_secret else None
            # The step is claimed only with the right password, so guesses cannot burn the owner's next code.
            fresh = password_ok and step is not None and directory.claim_operator_step(step)
            if password_ok and (not totp_secret or fresh):
                client_succeeded(key, store=directory)
                st.session_state["operator_since"] = _time.time()
                st.rerun()
            client_failed(key, store=directory)
            _time.sleep(1)
            st.error("Contraseña o código incorrectos." if totp_secret else "Contraseña incorrecta.")


def _backup_status(directory) -> None:
    fine, message = directory.backup_status()
    (st.success if fine else st.error)(message, icon=":material/backup:" if fine else ":material/warning:")


def _billing_alerts(directory) -> None:
    """What needs doing in Stripe, at the top of the panel instead of somewhere in the log (last 30 days)."""
    for alert in directory.billing_alerts():
        times = f" ({alert['times']} avisos)" if alert["times"] > 1 else ""
        text = f"{BILLING_ALERTS[alert['action']]}: {alert['detail']}{times} · {alert['last'][:16].replace('T', ' ')}"
        (st.info if alert["action"] in ("reembolso", "contracargo_cerrado") else st.error)(
            text, icon=":material/payments:")


def _operator_2fa_notice() -> None:
    """Without `operator_totp_secret`, the panel that controls every business is guarded by a password alone."""
    if setting("operator_totp_secret"):
        return
    proposal = st.session_state.setdefault("operator_totp_proposal", new_totp_secret())
    with st.container(border=True):
        st.warning("Activa la verificación en dos pasos del panel de operador: ahora solo lo protege la contraseña.",
                   icon=":material/shield:")
        st.markdown("1. Añade esta clave a tu app de autenticación (o abre el enlace en el móvil).\n"
                    "2. Guárdala como secreto `operator_totp_secret` (Secrets de Streamlit o variable "
                    "`OPERATOR_TOTP_SECRET` del servidor) y reinicia la app.\n"
                    "3. Desde entonces el panel pedirá también el código de 6 cifras.")
        st.code(proposal, language=None)
        st.code(totp_uri(proposal, "operador"), language=None)
