"""Charging businesses for the service with Stripe subscriptions.

Dormant until the secrets `stripe_secret_key` and `stripe_price_id` are set (multi-business mode only): until then
nothing changes and nobody is asked to pay. With them:

- A new business gets a free trial (`trial_days`, 30 by default) and subscribes from its «Suscripción» page through
  Stripe Checkout; card changes, invoices and cancelling happen in Stripe's customer portal.
- Stripe tells the server about every change through a signed webhook (ops/deploy/webhook.py). As a safety net, and
  for hosts that cannot receive webhooks, the app also asks Stripe for the subscription's state.
- When a payment fails Stripe retries for several days and the business sees a notice. Once the subscription has
  ended (or the trial is over without one) there are GRACE_DAYS more; after that the business can only look up and
  download its data. Data is never deleted for not paying.

Stripe is called over HTTPS with the standard library: no extra dependency, and every call is easy to fake in tests.
"""

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC

from . import config, logs

log = logs.get("billing")

# STRIPE_API_BASE points at a local fake (stripe-mock, the test suite) instead of Stripe.
API = config.value("stripe_api_base").rstrip("/")
TRIAL_DAYS = 30
GRACE_DAYS = 7
WEBHOOK_TOLERANCE = 300  # seconds a signed webhook stays valid (Stripe's own default)

# Stripe subscription states that mean «paid up».
PAID = {"active", "trialing"}
# A subscription in one of these is still the business's own (Stripe retries, the portal can fix it): never open a
# second Checkout over it.
LIVE = PAID | {"past_due", "unpaid", "paused"}
# Same Checkout for repeated clicks (two tabs, two administrators) within this window: Stripe returns the session it
# already made, so a business cannot end up paying two subscriptions.
CHECKOUT_WINDOW = 15 * 60
# Stripe will not start a trial that ends sooner than this.
MIN_TRIAL_LEFT = timedelta(days=2)
STATUS_LABELS = {
    "prueba": "Periodo de prueba",
    "trialing": "Periodo de prueba",
    "active": "Activa",
    "past_due": "Pago pendiente",
    "unpaid": "Impagada",
    "canceled": "Cancelada",
    "incomplete": "Pago sin completar",
    "incomplete_expired": "Pago sin completar",
    "paused": "En pausa",
    "cortesia": "Sin cargo (cortesía)",
}


def utc_now() -> datetime:
    """Billing dates are kept in UTC (Stripe's), naive, whatever the business's time zone."""
    return datetime.now(UTC).replace(tzinfo=None)


class BillingError(Exception):
    """Stripe refused a call or could not be reached. The message is safe to show."""


@dataclass(frozen=True)
class Access:
    level: str  # "full", "warn" (full access with a notice) or "readonly"
    message: str = ""
    days_left: int | None = None


def parse_when(text: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        return None


def access(tenant: dict, now: datetime) -> Access:
    """What a business may do given its billing state. `tenant` is a row of the directory."""
    if tenant.get("billing_exempt"):
        return Access("full")
    status = tenant.get("billing_status") or "prueba"
    period_end = parse_when(tenant.get("period_end"))
    trial_end = parse_when(tenant.get("trial_ends"))
    if status in PAID:
        if tenant.get("cancel_at_period_end") and period_end:
            return Access("warn", f"Tu suscripción termina el {period_end:%d/%m/%Y}. Puedes reactivarla en "
                                  "«Suscripción».", (period_end - now).days)
        return Access("full")
    if status == "past_due":
        return Access("warn", "No hemos podido cobrar tu suscripción. Revisa la tarjeta en «Suscripción» para no "
                              "perder el acceso.")
    if status == "prueba" and trial_end and now < trial_end:
        days = max(0, (trial_end - now).days)
        if days <= 7:
            return Access("warn", f"Tu prueba gratuita termina en {days} días. Suscríbete en «Suscripción» para "
                                  "seguir vendiendo sin cortes.", days)
        return Access("full", days_left=days)
    # Trial over without a subscription, or the subscription ended: a few more days, then look-up only.
    ended = max(filter(None, [period_end, trial_end]), default=None) or now
    deadline = ended + timedelta(days=GRACE_DAYS)
    if now < deadline:
        days = max(0, (deadline - now).days)
        return Access("warn", f"Tu suscripción no está activa. Tienes {days} días para activarla en «Suscripción»; "
                              "después solo podrás consultar y descargar tus datos.", days)
    return Access("readonly", "Tu suscripción no está activa: puedes consultar y descargar tus datos. Suscríbete en "
                              "«Suscripción» para volver a vender. No hemos borrado nada.")


# ------------------------------------------------------------------ Stripe API
def _flatten(params: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's form encoding: {"a": {"b": 1}, "c": [{"d": 2}]} → a[b]=1, c[0][d]=2."""
    out = []
    for key, value in params.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if value is None:
            continue
        if isinstance(value, dict):
            out += _flatten(value, name)
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                out += _flatten(item, f"{name}[{i}]") if isinstance(item, dict) else [(f"{name}[{i}]", str(item))]
        elif isinstance(value, bool):
            out.append((name, "true" if value else "false"))
        else:
            out.append((name, str(value)))
    return out


def _send(method: str, url: str, data: bytes | None, headers: dict) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


class Stripe:
    """The few Stripe calls the service needs. `transport` replaces the network in tests."""

    def __init__(self, secret_key: str, price_id: str, transport=_send, api_base: str | None = None):
        if not secret_key.startswith(("sk_", "rk_")):
            raise BillingError("La clave de Stripe no es válida (debe empezar por sk_ o rk_).")
        self.secret_key, self.price_id, self._transport = secret_key, price_id, transport
        self.api = (api_base or API).rstrip("/")

    @property
    def live(self) -> bool:
        return "_live_" in self.secret_key

    def _raw(self, method: str, path: str, params: dict | None = None,
             idempotency_key: str | None = None) -> tuple[int, dict]:
        """Status and body of one call, without judging them. Raises BillingError only when Stripe can't be reached."""
        headers = {"Authorization": f"Bearer {self.secret_key}", "Stripe-Version": "2024-06-20"}
        url, data = f"{self.api}{path}", None
        encoded = urllib.parse.urlencode(_flatten(params or {}))
        if method == "GET":
            url += f"?{encoded}" if encoded else ""
        else:
            data = encoded.encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
        try:
            status, body = self._transport(method, url, data, headers)
        except (OSError, urllib.error.URLError) as exc:
            log.warning("stripe_unreachable method=%s path=%s error=%s", method, path.split("?")[0],
                        type(exc).__name__)
            raise BillingError("No hemos podido conectar con Stripe. Inténtalo en unos minutos.") from None
        try:
            payload = json.loads(body or b"{}")
        except ValueError:
            payload = {}
        return status, payload if isinstance(payload, dict) else {}

    def _call(self, method: str, path: str, params: dict | None = None, idempotency_key: str | None = None) -> dict:
        status, payload = self._raw(method, path, params, idempotency_key)
        if status >= 400:
            # Stripe's own message can name our price, account or parameters: it goes to the log, not to the business.
            error = payload.get("error") or {}
            log.warning("stripe_refused method=%s path=%s status=%s code=%s message=%s", method, path.split("?")[0],
                        status, error.get("code", ""), str(error.get("message", ""))[:300])
            raise BillingError("Stripe no ha aceptado la operación. Inténtalo de nuevo en unos minutos y, si sigue "
                               "fallando, escríbenos a nirkana.oficial@gmail.com.")
        return payload

    def create_customer(self, tenant: dict, email: str) -> str:
        """The business's customer in Stripe, made before its first Checkout so every later one reuses it."""
        params = {"name": tenant.get("name") or tenant["code"], "email": email or None,
                  "metadata": {"tenant": tenant["code"]}}
        return self._call("POST", "/customers", params, idempotency_key=f"nk-customer-{tenant['code']}")["id"]

    def checkout_url(self, tenant: dict, email: str, success_url: str, cancel_url: str,
                     now: datetime | None = None) -> str:
        """A Stripe-hosted page where the business enters its card and tax details and subscribes. Days left of the
        free trial stay free: Stripe charges first when they end."""
        now = now or utc_now()
        params = {
            "mode": "subscription",
            "line_items": [{"price": self.price_id, "quantity": 1}],
            "client_reference_id": tenant["code"],
            "metadata": {"tenant": tenant["code"]},
            "subscription_data": {"metadata": {"tenant": tenant["code"]}},
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": True,
            "billing_address_collection": "required",
            "tax_id_collection": {"enabled": True},
            "locale": "es",
        }
        if tenant.get("stripe_customer"):
            params["customer"] = tenant["stripe_customer"]
            params["customer_update"] = {"address": "auto", "name": "auto"}
        elif email:
            params["customer_email"] = email
        trial_end = parse_when(tenant.get("trial_ends"))
        if (tenant.get("billing_status") or "prueba") == "prueba" and trial_end and trial_end - now > MIN_TRIAL_LEFT:
            params["subscription_data"]["trial_end"] = int(trial_end.replace(tzinfo=UTC).timestamp())
        encoded = urllib.parse.urlencode(_flatten(params))
        window = int(now.replace(tzinfo=UTC).timestamp()) // CHECKOUT_WINDOW
        key = hashlib.sha256(f"{tenant['code']}|{window}|{encoded}".encode()).hexdigest()[:40]
        session = self._call("POST", "/checkout/sessions", params, idempotency_key=f"nk-checkout-{key}")
        return session["url"]

    def portal_url(self, customer: str, return_url: str) -> str:
        """Stripe's customer portal: card, invoices, cancel or reactivate."""
        return self._call("POST", "/billing_portal/sessions", {"customer": customer, "return_url": return_url})["url"]

    def checkout_session(self, session_id: str) -> dict:
        if not session_id.startswith("cs_") or not session_id.replace("_", "").isalnum():
            raise BillingError("Referencia de pago no válida.")
        return self._call("GET", f"/checkout/sessions/{session_id}", {"expand": ["subscription"]})

    def subscriptions(self, customer: str) -> list[dict]:
        """The customer's subscriptions as Stripe has them now, newest first."""
        return self._call("GET", "/subscriptions", {"customer": customer, "status": "all", "limit": 20}).get(
            "data") or []

    def charge_customer(self, charge: str) -> str:
        """Who paid a charge (disputes only name the charge)."""
        if not charge.startswith(("ch_", "py_")) or not charge.replace("_", "").isalnum():
            return ""
        customer = self._call("GET", f"/charges/{charge}").get("customer")
        return str((customer.get("id") if isinstance(customer, dict) else customer) or "")


def best_subscription(subscriptions: list[dict]) -> dict | None:
    """Stripe lists the newest first, but a newer abandoned or cancelled attempt must not hide one that is paid."""
    rank = {"active": 0, "trialing": 0, "past_due": 1, "unpaid": 2, "paused": 2}
    ordered = sorted(enumerate(subscriptions), key=lambda pair: (rank.get(pair[1].get("status"), 3), pair[0]))
    return ordered[0][1] if ordered else None


def _period(subscription: dict, field: str):
    value = subscription.get(field)
    if value is None:  # newer API versions keep the period on each item
        items = (subscription.get("items") or {}).get("data") or [{}]
        value = items[0].get(field)
    return value


def _iso(timestamp) -> str:
    return datetime.fromtimestamp(int(timestamp), UTC).replace(tzinfo=None).isoformat(timespec="seconds") \
        if timestamp else ""


def subscription_fields(subscription: dict) -> dict:
    """What the directory keeps of a Stripe subscription. `period_end` is when paid-for access ends: the end of the
    period while it runs; the day it actually ended once cancelled; and the start of the unpaid period when Stripe gave
    up charging it (that period was never paid, so the days of grace count from its start)."""
    status = subscription.get("status") or "incomplete"
    end = _period(subscription, "current_period_end")
    if status in ("canceled", "incomplete_expired"):
        end = subscription.get("ended_at") or subscription.get("canceled_at") or end
    elif status == "unpaid":
        end = _period(subscription, "current_period_start") or end
    customer = subscription.get("customer")
    return {
        "stripe_customer": customer["id"] if isinstance(customer, dict) else customer,
        "stripe_subscription": subscription.get("id") or "",
        "billing_status": status,
        "period_end": _iso(end),
        "cancel_at_period_end": 1 if subscription.get("cancel_at_period_end") else 0,
    }


# ------------------------------------------------------------------ webhooks
def verify_webhook(payload: bytes, signature_header: str, secret: str, now: float | None = None) -> dict:
    """Check Stripe's signature (HMAC-SHA256 of «timestamp.payload») and return the event. Raises BillingError."""
    if not secret:
        raise BillingError("Falta el secreto del webhook.")
    parts = {}
    for item in str(signature_header or "").split(","):
        key, _, value = item.strip().partition("=")
        parts.setdefault(key, []).append(value)
    try:
        timestamp = int(parts.get("t", [""])[0])
    except ValueError:
        raise BillingError("Firma de Stripe no válida.") from None
    if abs((now or time.time()) - timestamp) > WEBHOOK_TOLERANCE:
        raise BillingError("Aviso de Stripe caducado.")
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, given) for given in parts.get("v1", [])):
        raise BillingError("Firma de Stripe no válida.")
    try:
        event = json.loads(payload)
    except ValueError:
        raise BillingError("Aviso de Stripe ilegible.") from None
    if not isinstance(event, dict) or not str(event.get("id", "")).startswith("evt_"):
        raise BillingError("Aviso de Stripe ilegible.")
    return event


def sign_webhook(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """The header Stripe would send; used by tests and to check a deployment by hand."""
    timestamp = int(timestamp or time.time())
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"
