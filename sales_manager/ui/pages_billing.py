"""The business's own subscription to the service: state, subscribe through Stripe, manage it in Stripe's portal."""

from urllib.parse import urlencode, urlsplit

import streamlit as st

from core import billing, clock
from ui.context import _secret, ctx, logged_download, stripe_client, tenant_code
from ui.styles import page_header


def _base_url() -> str:
    """Where Stripe sends the customer back: the `app_url` secret, or this app's own address."""
    configured = _secret("app_url").rstrip("/")
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
    from ui.tenancy import _tenant

    c = ctx()
    page_header("Suscripción", "Tu plan de NirKanA, la tarjeta y las facturas del servicio.", eyebrow="Ajustes")
    stripe, code = stripe_client(), tenant_code()
    tenant = _tenant(code) if code else None
    if stripe is None or tenant is None:
        st.info("Este negocio no tiene cuotas que pagar.")
        return
    access = st.session_state.get("billing_access") or billing.access(tenant, billing.utc_now())
    status = "cortesia" if tenant["billing_exempt"] else tenant["billing_status"]

    a, b = st.columns(2)
    a.metric("Estado", billing.STATUS_LABELS.get(status, status))
    if status == "prueba":
        b.metric("Prueba gratuita hasta", _date(tenant["trial_ends"]))
    elif tenant["period_end"]:
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
    paid = tenant["billing_status"] in billing.PAID or tenant["billing_status"] == "past_due"
    try:
        if paid and tenant["stripe_customer"]:
            if st.button("Gestionar tarjeta, facturas o baja", type="primary", icon=":material/credit_card:"):
                st.link_button("Abrir el portal de Stripe", stripe.portal_url(tenant["stripe_customer"], back),
                               type="primary", icon=":material/open_in_new:")
        elif st.button("Suscribirme", type="primary", icon=":material/workspace_premium:"):
            url = stripe.checkout_url(tenant, c.settings.get("email", ""),
                                      f"{back}&pago=ok&session_id={{CHECKOUT_SESSION_ID}}", back)
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
