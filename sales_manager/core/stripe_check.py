"""Is Stripe set up as the app needs it? Every check reads, or probes without creating anything, and says what to fix.

The operator runs it from the panel while configuring Stripe: a restricted key without some permission, a price
without VAT behaviour, a webhook missing events or a portal that lets customers switch plan are found here instead of
when a business tries to subscribe.
"""

from dataclasses import dataclass

from .billing import BillingError, Stripe

# What the webhook service handles (core/tenants.py): subscriptions, checkout, refunds and disputes.
WEBHOOK_EVENTS = {"checkout.session.completed", "customer.subscription.created", "customer.subscription.updated",
                  "customer.subscription.deleted", "charge.refunded", "charge.dispute.created",
                  "charge.dispute.closed"}
WEBHOOK_PATH = "/stripe/webhook"
# Write permissions are probed with a parameter Stripe does not know: a key without the permission is refused before
# the parameters are read (403), one with it gets a validation error (400). Nothing is ever created.
PROBE = {"nk_diagnostico": "1"}
OK, WARN, MISSING, UNKNOWN = "ok", "aviso", "falta", "sin comprobar"


@dataclass(frozen=True)
class Check:
    level: str
    title: str
    detail: str = ""


def _denied(status: int, payload: dict) -> bool:
    error = payload.get("error") or {}
    return status in (401, 403) or error.get("type") == "permission_error"


def _read(stripe: Stripe, path: str, params: dict | None = None) -> tuple[str, dict]:
    status, payload = stripe._raw("GET", path, params)
    if _denied(status, payload):
        return "denied", payload
    return ("ok" if status < 400 else "error"), payload


def _can_write(stripe: Stripe, path: str) -> bool | None:
    status, payload = stripe._raw("POST", path, PROBE)
    if _denied(status, payload):
        return False
    return True if status == 400 else None


def _key(stripe: Stripe) -> list[Check]:
    mode = "real (se cobra de verdad)" if stripe.live else "de prueba (no se cobra nada)"
    checks = [Check(OK, f"Clave en modo {mode}")]
    if stripe.secret_key.startswith("sk_"):
        checks.append(Check(WARN, "Clave secreta completa", "Mejor una clave restringida (rk_…) con solo los permisos "
                                  "que la app necesita: si se filtrara, el daño sería menor."))
    return checks


def _price(stripe: Stripe) -> list[Check]:
    state, price = _read(stripe, f"/prices/{stripe.price_id}", {"expand": ["product"]})
    if state == "denied":
        return [Check(MISSING, "No puedo leer el precio", "Da a la clave permiso de lectura en «Prices» y «Products».")]
    if state != "ok":
        return [Check(MISSING, f"El precio {stripe.price_id} no existe en esta cuenta",
                      "Revisa STRIPE_PRICE_ID: copia el ID (price_…) del producto, en el mismo modo (prueba o real) "
                      "que la clave.")]
    checks = []
    amount = f"{(price.get('unit_amount') or 0) / 100:.2f}".replace(".", ",")
    recurring = price.get("recurring") or {}
    interval = {"day": "día", "week": "semana", "month": "mes", "year": "año"}.get(recurring.get("interval"), "pago")
    label = f"{amount} {str(price.get('currency', '')).upper()} cada {interval}"
    if not price.get("active"):
        checks.append(Check(MISSING, "El precio está archivado", "Actívalo o crea uno nuevo y cambia STRIPE_PRICE_ID."))
    if recurring.get("interval") != "month":
        checks.append(Check(WARN, f"El precio no es mensual ({label})", "La app y las condiciones hablan de una "
                                  "suscripción mensual."))
    else:
        checks.append(Check(OK, f"Precio mensual: {label}"))
    if str(price.get("currency", "")).lower() != "eur":
        checks.append(Check(WARN, f"El precio no está en euros ({str(price.get('currency', '?')).upper()})",
                            "La web y las condiciones hablan de euros."))
    behaviour = price.get("tax_behavior") or "unspecified"
    if behaviour == "unspecified":
        checks.append(Check(MISSING, "El precio no dice si lleva IVA", "En Stripe, precio → «Comportamiento fiscal»: "
                                     "«Incluido» si el importe ya lleva el 21 % o «No incluido» si se suma. Decide "
                                     "también cómo lo dice la web («desde 20 € al mes»)."))
    else:
        checks.append(Check(OK, "IVA " + ("incluido en el precio" if behaviour == "inclusive" else "sumado al precio")))
    product = price.get("product") if isinstance(price.get("product"), dict) else {}
    if product and not product.get("active", True):
        checks.append(Check(MISSING, "El producto del precio está archivado"))
    return checks


def _permissions(stripe: Stripe) -> list[Check]:
    checks = []
    reads = {"Customers": "/customers", "Subscriptions": "/subscriptions", "Charges": "/charges",
             "Checkout Sessions": "/checkout/sessions"}
    for name, path in reads.items():
        state, _ = _read(stripe, path, {"limit": 1})
        if state == "denied":
            checks.append(Check(MISSING, f"Falta permiso de lectura en «{name}»"))
    writes = {"Customers": ("/customers", "sin él, «Suscribirme» falla al crear el cliente del negocio"),
              "Checkout Sessions": ("/checkout/sessions", "sin él no se puede abrir la página de pago"),
              "Customer portal": ("/billing_portal/sessions", "sin él no se abre el portal de tarjeta, facturas y baja")}
    for name, (path, why) in writes.items():
        allowed = _can_write(stripe, path)
        if allowed is False:
            checks.append(Check(MISSING, f"Falta permiso de escritura en «{name}»", why[0].upper() + why[1:] + "."))
        elif allowed is None:
            checks.append(Check(UNKNOWN, f"No he podido comprobar la escritura en «{name}»"))
    if not checks:
        checks.append(Check(OK, "La clave tiene los permisos que la app necesita"))
    return checks


def _webhook(stripe: Stripe, app_url: str) -> list[Check]:
    state, found = _read(stripe, "/webhook_endpoints", {"limit": 100})
    if state != "ok":
        return [Check(UNKNOWN, "No puedo ver los webhooks con esta clave",
                      "Da permiso de lectura en «Webhook Endpoints» o revisa a mano que el destino "
                      f"…{WEBHOOK_PATH} tenga estos eventos: {', '.join(sorted(WEBHOOK_EVENTS))}.")]
    wanted = (app_url.rstrip("/") + WEBHOOK_PATH) if app_url else ""
    ours = [e for e in found.get("data") or [] if str(e.get("url", "")).endswith(WEBHOOK_PATH)
            and (not wanted or e.get("url") == wanted)]
    if not ours:
        where = wanted or f"https://tu-app{WEBHOOK_PATH}"
        return [Check(MISSING, "No hay ningún webhook hacia la app", f"Desarrolladores → Webhooks → Añadir destino: "
                                f"{where}, con los eventos {', '.join(sorted(WEBHOOK_EVENTS))}.")]
    endpoint = ours[0]
    checks = []
    if endpoint.get("status") != "enabled":
        checks.append(Check(MISSING, "El webhook está desactivado", "Actívalo en Desarrolladores → Webhooks."))
    events = set(endpoint.get("enabled_events") or [])
    missing = set() if "*" in events else WEBHOOK_EVENTS - events
    if missing:
        checks.append(Check(MISSING, "Al webhook le faltan eventos", "Añade: " + ", ".join(sorted(missing)) + "."))
    else:
        checks.append(Check(OK, f"Webhook hacia {endpoint.get('url')} con todos los eventos"))
    return checks


def _portal(stripe: Stripe) -> list[Check]:
    state, found = _read(stripe, "/billing_portal/configurations", {"is_default": "true", "limit": 1})
    if state != "ok":
        return [Check(UNKNOWN, "No puedo ver la configuración del portal de clientes",
                      "Revísala a mano: cambiar tarjeta, ver facturas y cancelar, sí; cambiar de plan, no.")]
    configs = found.get("data") or []
    if not configs:
        return [Check(MISSING, "El portal de clientes no está configurado",
                      "Configuración → Facturación → Portal de clientes: actívalo (tarjeta, facturas, cancelar).")]
    features = configs[0].get("features") or {}
    checks = []
    if (features.get("subscription_update") or {}).get("enabled"):
        checks.append(Check(WARN, "El portal deja cambiar de plan", "Desactívalo: la app da acceso a cualquier "
                                  "suscripción activa, sea del precio que sea."))
    if not (features.get("invoice_history") or {}).get("enabled", True):
        checks.append(Check(WARN, "El portal no muestra las facturas", "Las condiciones dicen que se descargan ahí."))
    if not (features.get("subscription_cancel") or {}).get("enabled", True):
        checks.append(Check(WARN, "El portal no deja darse de baja", "Las condiciones dicen que se hace desde ahí."))
    return checks or [Check(OK, "Portal de clientes: tarjeta, facturas y baja, sin cambio de plan")]


def _promotions(stripe: Stripe) -> list[Check]:
    state, found = _read(stripe, "/promotion_codes", {"active": "true", "limit": 100, "expand": ["data.coupon"]})
    if state != "ok":
        return []  # optional: without the permission there is nothing to say
    free = [p.get("code", "?") for p in found.get("data") or []
            if (p.get("coupon") or {}).get("percent_off") == 100 and (p.get("coupon") or {}).get("duration") == "forever"]
    if free:
        return [Check(WARN, "Códigos promocionales que regalan el servicio para siempre: " + ", ".join(free),
                      "Quien los use tendrá acceso completo sin pagar. Para regalarlo a propósito usa «Sin cargo» en "
                      "el panel de operador.")]
    return []


def _server(webhook_secret: str, key_in_environment: bool) -> list[Check]:
    checks = []
    if not webhook_secret:
        checks.append(Check(MISSING, "Falta STRIPE_WEBHOOK_SECRET en el servidor",
                            "Sin él no se reciben los avisos de Stripe; la app solo se pone al día cada 6 horas."))
    if not key_in_environment:
        checks.append(Check(WARN, "STRIPE_SECRET_KEY no está en las variables del servidor",
                            "Ponla como variable de entorno (Render → Environment): así el servicio de avisos "
                            "también la tiene y consulta a Stripe el estado real en vez de fiarse del orden de los "
                            "avisos."))
    return checks or [Check(OK, "El servidor tiene el secreto del webhook y la clave para el servicio de avisos")]


def diagnose(stripe: Stripe, app_url: str = "", webhook_secret: str = "", key_in_environment: bool = True) -> list[Check]:
    """Everything, in the order it is configured. Stripe unreachable → a single check saying so."""
    try:
        return [*_key(stripe), *_price(stripe), *_permissions(stripe), *_webhook(stripe, app_url), *_portal(stripe),
                *_promotions(stripe), *_server(webhook_secret, key_in_environment)]
    except BillingError as exc:
        return [Check(MISSING, "No se puede conectar con Stripe", str(exc))]
