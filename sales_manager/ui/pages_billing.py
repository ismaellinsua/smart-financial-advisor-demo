"""The business's own subscription to the service: state, subscribe through Stripe, manage it in Stripe's portal."""

from urllib.parse import urlencode, urlsplit

import streamlit as st

from core import billing, clock
from core.tenants import AlreadySubscribed
from ui.context import ctx, get_directory, logged_download, setting, stripe_client, tenant_code
from ui.styles import page_header


def _base_url() -> str:
    """Where Stripe sends the customer back: the `app_url` secret, or this app's own address."""
    configured = setting("app_url").rstrip("/")
    if configured:
        return configured
    try:
        parts = urlsplit(st.context.url)
    except Exception:  # no request context
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def _date(text: str) -> str:
    when = billing.parse_when(text)
    return f"{when:%d/%m/%Y}" if when else "—"


def billing_page() -> None:
    from ui.tenancy import tenant_info

    c = ctx()
    page_header("Suscripción", "Tu plan de NirKanA, la tarjeta y las facturas del servicio.", eyebrow="Ajustes")
    stripe, code = stripe_client(), tenant_code()
    tenant = tenant_info(code) if code else None
    if stripe is None or tenant is None:
        st.info("Este negocio no tiene cuotas que pagar.")
        return
    access = st.session_state.get("billing_access") or billing.access(tenant, billing.utc_now())
    status = "cortesia" if tenant["billing_exempt"] else tenant["billing_status"]

    a, b = st.columns(2)
    a.metric("Estado", billing.STATUS_LABELS.get(status, status))
    if status == "prueba":
        b.metric("Prueba gratuita hasta", _date(tenant["trial_ends"]))
    elif tenant["period_end"] and status in billing.LIVE - {"unpaid"} | {"canceled"}:
        b.metric("Termina" if tenant["cancel_at_period_end"] or status == "canceled" else "Próxima renovación",
                 _date(tenant["period_end"]))
    if access.message:
        (st.error if access.level == "readonly" else st.warning)(access.message)
    if not stripe.live:
        st.caption("Modo de prueba de Stripe: no se cobra nada de verdad (tarjeta de prueba 4242 4242 4242 4242).")
    if tenant["billing_exempt"]:
        st.success("Usas NirKanA sin cargo. Gracias por ayudarnos a mejorarlo.")
        return
    if not c.can("admin"):
        st.info("Solo el administrador del negocio puede gestionar la suscripción.")
        return

    # Back to the business's main address: Streamlit cannot open an inner page before the session is restored.
    back = f"{_base_url()}/?{urlencode({'negocio': code})}"
    live = bool(tenant["stripe_subscription"]) and tenant["billing_status"] in billing.LIVE
    try:
        if live and tenant["stripe_customer"]:
            if st.button("Gestionar tarjeta, facturas o baja", type="primary", icon=":material/credit_card:"):
                st.link_button("Abrir el portal de Stripe", stripe.portal_url(tenant["stripe_customer"], back),
                               type="primary", icon=":material/open_in_new:")
        else:
            trial_end = billing.parse_when(tenant["trial_ends"])
            if status == "prueba" and trial_end and trial_end - billing.utc_now() > billing.MIN_TRIAL_LEFT:
                st.caption(f"Si te suscribes ahora, el primer cobro será el {trial_end:%d/%m/%Y}, cuando termine tu "
                           "prueba gratuita.")
            if st.button("Suscribirme", type="primary", icon=":material/workspace_premium:"):
                try:
                    url = get_directory().checkout_url(code, stripe, c.settings.get("email", ""),
                                                       f"{back}&pago=ok&session_id={{CHECKOUT_SESSION_ID}}", back)
                except AlreadySubscribed as exc:
                    # Shown again with what Stripe has: the button to the portal instead of a second purchase.
                    tenant_info.clear()
                    st.session_state["billing_flash"] = str(exc)
                    st.rerun()
                else:
                    c.store.audit(c.username, "suscripcion_iniciada")
                    st.link_button("Ir al pago seguro de Stripe", url, type="primary", icon=":material/open_in_new:")
    except billing.BillingError as exc:
        st.error(str(exc))
    st.caption("El pago lo gestiona Stripe: NirKanA nunca ve ni guarda los datos de tu tarjeta. Recibirás las "
               "facturas del servicio por email y puedes darte de baja cuando quieras desde el portal.")

    st.markdown("##### Tus datos")
    st.caption("Son tuyos, pagues o no: descárgalos cuando quieras.")
    logged_download(st, "Descargar copia de seguridad", c.store.backup_bytes, f"ventas-{clock.today():%Y-%m-%d}.db",
                    "application/octet-stream", icon=":material/download:")
