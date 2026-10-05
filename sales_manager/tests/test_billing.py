"""Charging businesses with Stripe: what each billing state allows, the Stripe calls, signed webhooks applied once,
and the directory keeping each business's subscription."""

import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

from conftest import PG_URL
from core import billing
from core.billing import BillingError, Stripe, access, sign_webhook, subscription_fields, verify_webhook

NOW = datetime(2026, 10, 5, 12, 0)
SECRET = "whsec_test_secreto"


def tenant(**fields):
    return {"code": "cafe", "billing_status": "prueba", "trial_ends": "", "period_end": "", "billing_exempt": 0,
            "cancel_at_period_end": 0, "stripe_customer": "", "stripe_subscription": "", **fields}


def iso(days: float) -> str:
    return (NOW + timedelta(days=days)).isoformat(timespec="seconds")


# ------------------------------------------------------------------ what each state allows
@pytest.mark.parametrize("fields, level", [
    ({"trial_ends": iso(20)}, "full"),
    ({"trial_ends": iso(3)}, "warn"),
    ({"trial_ends": iso(-2)}, "warn"),  # trial over: grace days
    ({"trial_ends": iso(-8)}, "readonly"),
    ({"billing_status": "active", "period_end": iso(20)}, "full"),
    ({"billing_status": "trialing", "period_end": iso(20)}, "full"),
    ({"billing_status": "active", "period_end": iso(9), "cancel_at_period_end": 1}, "warn"),
    ({"billing_status": "past_due", "period_end": iso(-1)}, "warn"),
    ({"billing_status": "canceled", "period_end": iso(-3)}, "warn"),
    ({"billing_status": "canceled", "period_end": iso(-30), "trial_ends": iso(-60)}, "readonly"),
    ({"billing_status": "unpaid", "period_end": iso(-10)}, "readonly"),
    ({"billing_status": "canceled", "period_end": iso(-30), "billing_exempt": 1}, "full"),
])
def test_access_by_billing_state(fields, level):
    result = access(tenant(**fields), NOW)
    assert result.level == level
    assert (result.message != "") == (level != "full")
    if level == "readonly":
        assert "No hemos borrado nada" in result.message


# ------------------------------------------------------------------ Stripe calls
class FakeTransport:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, method, url, data, headers):
        self.calls.append((method, url, urllib.parse.parse_qs(data.decode()) if data else None, headers))
        status, body = self.responses.pop(0)
        return status, json.dumps(body).encode()


def test_checkout_asks_stripe_for_a_subscription_of_this_business():
    transport = FakeTransport([(200, {"url": "https://checkout.stripe.com/c/pay/cs_test_1"})])
    stripe = Stripe("sk_test_123", "price_123", transport)
    assert not stripe.live
    url = stripe.checkout_url(tenant(), "hola@cafe.es", "https://app/ok", "https://app/back")
    assert url.startswith("https://checkout.stripe.com/")
    method, endpoint, form, headers = transport.calls[0]
    assert method == "POST" and endpoint.endswith("/checkout/sessions")
    assert form["mode"] == ["subscription"] and form["line_items[0][price]"] == ["price_123"]
    assert form["client_reference_id"] == ["cafe"] and form["subscription_data[metadata][tenant]"] == ["cafe"]
    assert form["customer_email"] == ["hola@cafe.es"] and form["tax_id_collection[enabled]"] == ["true"]
    assert headers["Authorization"] == "Bearer sk_test_123" and headers["Idempotency-Key"]

    transport = FakeTransport([(200, {"url": "u"})])
    Stripe("sk_test_123", "price_123", transport).checkout_url(tenant(stripe_customer="cus_9"), "x@y.es", "a", "b")
    form = transport.calls[0][2]
    assert form["customer"] == ["cus_9"] and "customer_email" not in form  # returning customers keep their record


def test_stripe_errors_are_readable_and_keys_checked():
    with pytest.raises(BillingError, match="sk_"):
        Stripe("pk_test_123", "price_1")
    stripe = Stripe("sk_test_1", "price_1", FakeTransport([(402, {"error": {"message": "Tarjeta rechazada"}})]))
    with pytest.raises(BillingError, match="Tarjeta rechazada"):
        stripe.portal_url("cus_1", "https://app")

    def offline(*_):
        raise OSError("sin red")
    with pytest.raises(BillingError, match="conectar"):
        Stripe("sk_test_1", "price_1", offline).latest_subscription("cus_1")
    with pytest.raises(BillingError, match="no válida"):
        Stripe("sk_test_1", "price_1", offline).checkout_session("cs_test_1/../../charges")


def test_subscription_fields_from_either_api_version():
    old = {"id": "sub_1", "customer": "cus_1", "status": "active", "current_period_end": 1_791_000_000}
    new = {"id": "sub_1", "customer": {"id": "cus_1"}, "status": "past_due", "cancel_at_period_end": True,
           "items": {"data": [{"current_period_end": 1_791_000_000}]}}
    a, b = subscription_fields(old), subscription_fields(new)
    assert a["period_end"] == b["period_end"] == "2026-10-03T04:00:00"
    assert (a["stripe_customer"], b["stripe_customer"]) == ("cus_1", "cus_1")
    assert (a["cancel_at_period_end"], b["cancel_at_period_end"]) == (0, 1)


# ------------------------------------------------------------------ webhook signatures
def event(kind="customer.subscription.updated", obj=None, event_id=None):
    return {"id": event_id or f"evt_{uuid.uuid4().hex[:12]}", "type": kind, "data": {"object": obj or {}}}


def test_webhook_signature_is_checked():
    payload = json.dumps(event()).encode()
    header = sign_webhook(payload, SECRET, timestamp=1_000_000)
    assert verify_webhook(payload, header, SECRET, now=1_000_100)["type"] == "customer.subscription.updated"
    assert verify_webhook(payload, f"{header},v1=otra", SECRET, now=1_000_000)  # rotated secrets: any v1 matches
    with pytest.raises(BillingError, match="Firma"):
        verify_webhook(payload, header, "whsec_otro", now=1_000_000)
    with pytest.raises(BillingError, match="Firma"):
        verify_webhook(payload + b" ", header, SECRET, now=1_000_000)  # altered body
    with pytest.raises(BillingError, match="caducado"):
        verify_webhook(payload, header, SECRET, now=1_000_000 + 301)  # replayed later
    with pytest.raises(BillingError):
        verify_webhook(payload, "", SECRET)
    with pytest.raises(BillingError):
        verify_webhook(payload, header, "")


# ------------------------------------------------------------------ the directory keeps each subscription
needs_pg = pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def directory():
    import psycopg

    from core.tenants import Directory

    name = f"nk_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    url = urlunsplit(urlsplit(PG_URL)._replace(path=f"/{name}"))
    yield Directory(url)
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def subscription(status="active", sub_id="sub_1", customer="cus_1", days=30, code="cafe"):
    end = int((billing.utc_now() + timedelta(days=days)).timestamp())
    return {"id": sub_id, "object": "subscription", "customer": customer, "status": status,
            "current_period_end": end, "cancel_at_period_end": False, "metadata": {"tenant": code}}


@needs_pg
def test_new_business_starts_a_trial_and_pays_through_stripe(directory):
    directory.create("cafe", "Café")
    t = directory.get("cafe")
    trial = datetime.fromisoformat(t["trial_ends"]) - billing.utc_now()
    assert t["billing_status"] == "prueba" and timedelta(days=29) < trial <= timedelta(days=30)
    assert access(t, billing.utc_now()).level == "full"

    paid = event("checkout.session.completed", {"client_reference_id": "cafe", "customer": "cus_1",
                                                "subscription": subscription()}, "evt_pago")
    assert directory.process_event(paid) == "vinculado"
    assert directory.process_event(paid) == "repetido"  # Stripe may deliver twice
    t = directory.get("cafe")
    assert (t["billing_status"], t["stripe_customer"], t["stripe_subscription"]) == ("active", "cus_1", "sub_1")

    assert directory.process_event(event(obj=subscription("past_due"))) == "actualizado"
    assert access(directory.get("cafe"), billing.utc_now()).level == "warn"
    gone = subscription("canceled", days=-10)
    gone["metadata"] = {}  # found by customer when the metadata is missing
    assert directory.process_event(event("customer.subscription.deleted", gone)) == "actualizado"
    t = directory.get("cafe")
    assert t["billing_status"] == "canceled"
    assert access(t, billing.utc_now()).level == "warn"  # cancelling during the trial keeps the days left
    assert access(t, billing.utc_now() + timedelta(days=38)).level == "readonly"

    log = [r["action"] for r in directory.log()]
    assert "suscripcion_contratada" in log and "suscripcion_deleted" in log


@needs_pg
def test_events_in_any_order_and_strangers_ignored(directory):
    directory.create("cafe", "Café")
    # The subscription's own event arrives before checkout's, which only carries ids.
    directory.process_event(event("customer.subscription.created", subscription()))
    directory.process_event(event("checkout.session.completed", {"client_reference_id": "cafe", "customer": "cus_1",
                                                                 "subscription": "sub_1"}))
    assert directory.get("cafe")["billing_status"] == "active"
    # An abandoned older attempt must not overwrite the subscription that is paid.
    directory.process_event(event(obj=subscription("incomplete_expired", sub_id="sub_0")))
    assert directory.get("cafe")["billing_status"] == "active"
    assert directory.process_event(event(obj=subscription(code="otro", customer="cus_x"))) == "ignorado"
    assert directory.process_event(event("checkout.session.completed", {"client_reference_id": "nadie"})) == "ignorado"
    assert directory.process_event(event("invoice.paid", {"id": "in_1"})) == "ignorado"


@needs_pg
def test_operator_courtesy_trial_and_sync(directory):
    directory.create("cafe", "Café", trial_days=0)
    directory.set_billing_exempt("cafe", True)
    assert access(directory.get("cafe"), billing.utc_now() + timedelta(days=90)).level == "full"
    directory.set_billing_exempt("cafe", False)
    before = datetime.fromisoformat(directory.get("cafe")["trial_ends"])
    directory.extend_trial("cafe", 14)
    assert datetime.fromisoformat(directory.get("cafe")["trial_ends"]) - before >= timedelta(days=14)
    with pytest.raises(ValueError):
        directory.extend_trial("cafe", 0)

    class FakeStripe:
        def latest_subscription(self, customer):
            assert customer == "cus_1"
            return subscription("active")

    assert directory.sync_subscription("cafe", FakeStripe())["billing_status"] == "prueba"  # no customer yet
    directory.process_event(event("checkout.session.completed", {"client_reference_id": "cafe", "customer": "cus_1",
                                                                 "subscription": "sub_1"}))
    t = directory.sync_subscription("cafe", FakeStripe())
    assert t["billing_status"] == "active" and t["billing_synced_at"]


@needs_pg
def test_businesses_from_before_billing_get_a_fresh_trial(directory):
    import psycopg

    from core.tenants import DIRECTORY_SCHEMA, Directory

    directory.create("cafe", "Café")
    with psycopg.connect(directory._url, autocommit=True) as conn:
        conn.execute(f"UPDATE {DIRECTORY_SCHEMA}.tenants SET trial_ends = ''")
    t = Directory(directory._url).get("cafe")
    assert datetime.fromisoformat(t["trial_ends"]) > billing.utc_now() + timedelta(days=29)


# ------------------------------------------------------------------ the webhook service
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops" / "deploy"))


@pytest.fixture
def webhook_url():
    from webhook import make_handler

    received = []

    class FakeDirectory:
        def process_event(self, evt):
            received.append(evt["id"])
            return "actualizado"

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(SECRET, FakeDirectory))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", received
    server.shutdown()


def post(url, body: bytes, signature: str = ""):
    request = urllib.request.Request(url, data=body, method="POST", headers={"Stripe-Signature": signature})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_webhook_service_only_accepts_signed_events(webhook_url):
    base, received = webhook_url
    body = json.dumps(event(event_id="evt_firmado")).encode()
    assert post(f"{base}/stripe/webhook", body, sign_webhook(body, SECRET)) == 200
    assert post(f"{base}/stripe/webhook", body, sign_webhook(body, "whsec_falso")) == 400
    assert post(f"{base}/stripe/webhook", body) == 400
    assert post(f"{base}/otra-cosa", body, sign_webhook(body, SECRET)) == 404
    big = b"x" * (600 * 1024)
    assert post(f"{base}/stripe/webhook", big, sign_webhook(big, SECRET)) == 413
    assert received == ["evt_firmado"]
