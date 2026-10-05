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
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# STRIPE_API_BASE points at a local fake (stripe-mock, the test suite) instead of Stripe.
API = os.environ.get("STRIPE_API_BASE", "https://api.stripe.com/v1").rstrip("/")
TRIAL_DAYS = 30
GRACE_DAYS = 7
WEBHOOK_TOLERANCE = 300  # seconds a signed webhook stays valid (Stripe's own default)

# Stripe subscription states that mean «paid up».
PAID = {"active", "trialing"}
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
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BillingError(Exception):
    """Stripe refused a call or could not be reached. The message is safe to show."""


@dataclass(frozen=True)
class Access:
    level: str  # "full", "warn" (full access with a notice) or "readonly"
    message: str = ""
    days_left: int | None = None


def _when(text: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        return None


def access(tenant: dict, now: datetime) -> Access:
    """What a business may do given its billing state. `tenant` is a row of the directory."""
    if tenant.get("billing_exempt"):
        return Access("full")
    status = tenant.get("billing_status") or "prueba"
    period_end = _when(tenant.get("period_end"))
    trial_end = _when(tenant.get("trial_ends"))
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

    def _call(self, method: str, path: str, params: dict | None = None, idempotency_key: str | None = None) -> dict:
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
        except (OSError, urllib.error.URLError):
            raise BillingError("No hemos podido conectar con Stripe. Inténtalo en unos minutos.") from None
        try:
            payload = json.loads(body or b"{}")
        except ValueError:
            payload = {}
        if status >= 400:
            message = (payload.get("error") or {}).get("message") or f"error {status}"
            raise BillingError(f"Stripe no ha aceptado la operación: {message}")
        return payload

    def checkout_url(self, tenant: dict, email: str, success_url: str, cancel_url: str) -> str:
        """A Stripe-hosted page where the business enters its card and tax details and subscribes."""
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
        session = self._call("POST", "/checkout/sessions", params)
        return session["url"]

    def portal_url(self, customer: str, return_url: str) -> str:
        """Stripe's customer portal: card, invoices, cancel or reactivate."""
        return self._call("POST", "/billing_portal/sessions", {"customer": customer, "return_url": return_url})["url"]

    def checkout_session(self, session_id: str) -> dict:
        if not session_id.startswith("cs_") or not session_id.replace("_", "").isalnum():
            raise BillingError("Referencia de pago no válida.")
        return self._call("GET", f"/checkout/sessions/{session_id}", {"expand": ["subscription"]})

    def latest_subscription(self, customer: str) -> dict | None:
        found = self._call("GET", "/subscriptions", {"customer": customer, "status": "all", "limit": 1})
        return (found.get("data") or [None])[0]


def subscription_fields(subscription: dict) -> dict:
    """What the directory keeps of a Stripe subscription."""
    end = subscription.get("current_period_end")
    if end is None:  # newer API versions keep the period on each item
        items = (subscription.get("items") or {}).get("data") or [{}]
        end = items[0].get("current_period_end")
    customer = subscription.get("customer")
    return {
        "stripe_customer": customer["id"] if isinstance(customer, dict) else customer,
        "stripe_subscription": subscription.get("id") or "",
        "billing_status": subscription.get("status") or "incomplete",
        "period_end": datetime.fromtimestamp(int(end), timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
        if end else "",
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
