"""Charging businesses with Stripe: what each billing state allows, the Stripe calls, signed webhooks applied once,
and the directory keeping each business's subscription."""

import json
import os
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
    stripe = Stripe("sk_test_1", "price_1", FakeTransport([(400, {"error": {"message": "No such price: price_1"}})]))
    with pytest.raises(BillingError, match="no ha aceptado") as refused:
        stripe.portal_url("cus_1", "https://app")
    assert "price_1" not in str(refused.value)  # Stripe's own detail stays in the server log

    def offline(*_):
        raise OSError("sin red")
    with pytest.raises(BillingError, match="conectar"):
        Stripe("sk_test_1", "price_1", offline).subscriptions("cus_1")
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
        def subscriptions(self, customer):
            assert customer == "cus_1"
            return [subscription("active")]

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
        def process_event(self, evt, stripe=None):
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
    except (urllib.error.URLError, ConnectionError):
        return "cortada"  # refused before the whole body was sent: the server may close the connection first


def test_webhook_service_only_accepts_signed_events(webhook_url):
    base, received = webhook_url
    body = json.dumps(event(event_id="evt_firmado")).encode()
    assert post(f"{base}/stripe/webhook", body, sign_webhook(body, SECRET)) == 200
    assert post(f"{base}/stripe/webhook", body, sign_webhook(body, "whsec_falso")) == 400
    assert post(f"{base}/stripe/webhook", body) == 400
    assert post(f"{base}/otra-cosa", body, sign_webhook(body, SECRET)) == 404
    big = b"x" * (600 * 1024)
    assert post(f"{base}/stripe/webhook", big, sign_webhook(big, SECRET)) in (413, "cortada")
    assert received == ["evt_firmado"]


# ------------------------------------------------------------------ against Stripe's own API description
STRIPE_MOCK = os.environ.get("STRIPE_MOCK_URL")  # stripe-mock checks every parameter against Stripe's OpenAPI spec


@pytest.mark.skipif(not STRIPE_MOCK, reason="STRIPE_MOCK_URL not set (run stripe/stripe-mock)")
def test_every_call_is_valid_for_stripe(caplog):
    stripe = Stripe("sk_test_123", "price_123", api_base=STRIPE_MOCK)
    back = "https://app.nirkana.es/?negocio=cafe"
    assert stripe.checkout_url(tenant(), "hola@cafe.es", back + "&pago=ok&session_id={CHECKOUT_SESSION_ID}", back)
    assert stripe.checkout_url(tenant(stripe_customer="cus_123"), "", back, back)
    in_trial = tenant(stripe_customer="cus_123", trial_ends=(billing.utc_now() + timedelta(days=20)).isoformat())
    assert stripe.checkout_url(in_trial, "", back, back)
    assert stripe.portal_url("cus_123", back)
    assert "client_reference_id" in stripe.checkout_session("cs_test_123")
    assert subscription_fields(stripe.subscriptions("cus_123")[0])["stripe_subscription"].startswith("sub_")
    assert stripe.create_customer(tenant(name="Café"), "hola@cafe.es").startswith("cus_")
    payer = stripe.charge_customer("ch_123")
    assert payer == "" or payer.startswith("cus_")  # Stripe's sample charge may have no customer
    assert stripe.charge_customer("ch_1/../../customers") == ""  # never sent to Stripe
    with pytest.raises(BillingError, match="no ha aceptado"):  # the simulator does reject what Stripe would
        stripe._call("POST", "/checkout/sessions", {"mode": "subscription", "parametro_inventado": "x"})
    assert "validation" in caplog.text  # Stripe's reason, for us, in the log


@needs_pg
def test_access_for_records_a_purchase_and_rechecks_stale_billing(directory):
    directory.create("cafe", "Café")

    class FakeStripe:
        def __init__(self):
            self.synced = 0

        def checkout_session(self, session_id):
            assert session_id == "cs_1"
            return {"client_reference_id": "cafe", "subscription": subscription("active")}

        def subscriptions(self, customer):
            self.synced += 1
            return [subscription("active")]

    assert directory.access_for(directory.get("cafe"), None) == (billing.Access("full"), "", False)
    stripe = FakeStripe()
    access_now, message, refreshed = directory.access_for(directory.get("cafe"), stripe, "cs_1")
    assert access_now.level == "full" and "suscripción está activa" in message and refreshed
    assert directory.get("cafe")["billing_status"] == "active"
    # Just synced: no call to Stripe on the next visits.
    calls = stripe.synced
    assert directory.access_for(directory.get("cafe"), stripe)[2] is False and stripe.synced == calls


@needs_pg
def test_access_for_ignores_a_session_of_another_business(directory):
    directory.create("cafe", "Café")

    class OtherBusiness:
        def checkout_session(self, session_id):
            return {"client_reference_id": "otro", "subscription": subscription("active", code="otro")}

    _, message, _ = directory.access_for(directory.get("cafe"), OtherBusiness(), "cs_x")
    assert message == "" and directory.get("cafe")["billing_status"] == "prueba"


# ------------------------------------------------------------------ payments audit
def test_checkout_keeps_the_trial_and_repeated_clicks_get_the_same_session():
    transport = FakeTransport([(200, {"url": "https://checkout.stripe.com/a"})] * 3)
    stripe = Stripe("sk_test_1", "price_1", transport)
    now = datetime(2026, 10, 5, 12, 0)
    trial = tenant(trial_ends=(now + timedelta(days=20)).isoformat(), stripe_customer="cus_1")
    stripe.checkout_url(trial, "", "https://app/ok", "https://app/back", now=now)
    stripe.checkout_url(trial, "", "https://app/ok", "https://app/back", now=now + timedelta(minutes=1))
    first, second = transport.calls[0], transport.calls[1]
    assert first[2]["subscription_data[trial_end]"] == [str(int((now + timedelta(days=20)).timestamp()))]
    assert first[3]["Idempotency-Key"] == second[3]["Idempotency-Key"]  # two tabs: one session, one subscription
    # A trial about to end (Stripe needs two days) or a business that already paid once: charged from today.
    stripe.checkout_url(tenant(billing_status="canceled", trial_ends=(now + timedelta(days=20)).isoformat()), "",
                        "https://app/ok", "https://app/back", now=now)
    assert "subscription_data[trial_end]" not in transport.calls[2][2]


def test_access_ends_when_the_subscription_did_not_at_the_end_of_an_unpaid_month():
    now = billing.utc_now()
    ts = lambda days: int((now + timedelta(days=days)).timestamp())  # noqa: E731
    # Stripe gave up after its retries: the period it could not charge is still «current», three weeks ahead.
    dropped = {"id": "sub_1", "customer": "cus_1", "status": "canceled", "current_period_end": ts(21),
               "current_period_start": ts(-9), "ended_at": ts(-8)}
    assert access(tenant(**subscription_fields(dropped), trial_ends=iso(-60)), now).level == "readonly"
    unpaid = {**dropped, "status": "unpaid", "ended_at": None}
    assert access(tenant(**subscription_fields(unpaid), trial_ends=iso(-60)), now).level == "readonly"
    # Cancelled in the portal today: the usual days of grace, from today.
    today = {**dropped, "ended_at": ts(0)}
    assert access(tenant(**subscription_fields(today), trial_ends=iso(-60)), now).level == "warn"


def test_the_paid_subscription_decides_whatever_stripe_lists_first():
    assert billing.best_subscription([]) is None
    newest_abandoned = [{"id": "sub_2", "status": "incomplete_expired"}, {"id": "sub_1", "status": "active"}]
    assert billing.best_subscription(newest_abandoned)["id"] == "sub_1"
    assert billing.best_subscription([{"id": "sub_3", "status": "canceled"},
                                      {"id": "sub_2", "status": "canceled"}])["id"] == "sub_3"


class StripeNow:
    """What Stripe has for the customer when the directory asks."""

    def __init__(self, *subs):
        self.subs, self.customers, self.checkouts = list(subs), [], []

    def subscriptions(self, customer):
        return list(self.subs)

    def create_customer(self, tenant, email):
        self.customers.append((tenant["code"], email))
        return "cus_nuevo"

    def checkout_url(self, tenant, email, success_url, cancel_url):
        self.checkouts.append(tenant["stripe_customer"])
        return "https://checkout.stripe.com/x"

    def charge_customer(self, charge):
        return "cus_1"


@needs_pg
def test_a_notice_that_fails_is_applied_when_stripe_retries_it(directory, monkeypatch):
    directory.create("cafe", "Café")
    notice = event(obj=subscription("active"), event_id="evt_reintento")
    real = directory._record

    def broken(*args, **kwargs):
        raise RuntimeError("se cayó la base de datos")
    monkeypatch.setattr(directory, "_record", broken)
    with pytest.raises(RuntimeError):
        directory.process_event(notice)
    monkeypatch.setattr(directory, "_record", real)
    assert directory.process_event(notice) == "actualizado"  # not «repetido»: nothing was kept from the failure
    assert directory.get("cafe")["billing_status"] == "active"


@needs_pg
def test_late_notices_do_not_bring_back_an_old_state(directory):
    directory.create("cafe", "Café")
    deleted = event("customer.subscription.deleted", subscription("canceled", days=-1))
    deleted["created"] = 2_000
    late = event(obj=subscription("active"))
    late["created"] = 1_000  # sent before the cancellation, delivered after it
    assert directory.process_event(deleted) == "actualizado"
    assert directory.process_event(late) == "antiguo"
    assert directory.get("cafe")["billing_status"] == "canceled"
    # With the Stripe key, a notice is only a cue: the state comes from Stripe as it is now.
    directory.process_event(event(obj=subscription("past_due")), StripeNow(subscription("active")))
    assert directory.get("cafe")["billing_status"] == "active"


@needs_pg
def test_two_paid_subscriptions_are_reported_and_cancelling_one_keeps_access(directory):
    directory.create("cafe", "Café")
    directory.process_event(event("customer.subscription.created", subscription("active", sub_id="sub_1")))
    directory.process_event(event("customer.subscription.created", subscription("active", sub_id="sub_2")))
    assert any(r["action"] == "suscripcion_duplicada" for r in directory.log())
    # The operator cancels the duplicate: the business keeps paying the other one and keeps its access.
    directory.process_event(event("customer.subscription.deleted", subscription("canceled", sub_id="sub_2", days=-1)),
                            StripeNow(subscription("canceled", sub_id="sub_2", days=-1),
                                      subscription("active", sub_id="sub_1")))
    t = directory.get("cafe")
    assert (t["billing_status"], t["stripe_subscription"]) == ("active", "sub_1")


@needs_pg
def test_checkout_is_never_offered_to_a_business_that_already_pays(directory):
    from core.tenants import AlreadySubscribed

    directory.create("cafe", "Café")
    stripe = StripeNow()
    assert directory.checkout_url("cafe", stripe, "hola@cafe.es", "ok", "back")
    # Its own customer in Stripe from the first click, so the next Checkout (and the check above) find it.
    assert stripe.customers == [("cafe", "hola@cafe.es")] and stripe.checkouts == ["cus_nuevo"]
    assert directory.get("cafe")["stripe_customer"] == "cus_nuevo"
    # Paid from another tab meanwhile: Stripe says so, even though no notice has arrived yet.
    stripe.subs = [subscription("active", customer="cus_nuevo")]
    with pytest.raises(AlreadySubscribed):
        directory.checkout_url("cafe", stripe, "hola@cafe.es", "ok", "back")
    assert stripe.checkouts == ["cus_nuevo"] and directory.get("cafe")["billing_status"] == "active"


@needs_pg
def test_refunds_and_disputes_reach_the_operator_log(directory):
    directory.create("cafe", "Café")
    directory.record_subscription("cafe", subscription("active"))
    assert directory.process_event(event("charge.refunded", {"id": "ch_1", "customer": "cus_1",
                                                             "amount_refunded": 2420, "currency": "eur"})) == "registrado"
    assert directory.process_event(event("charge.dispute.created", {"id": "dp_1", "charge": "ch_1", "amount": 2420,
                                                                    "currency": "eur", "reason": "fraudulent",
                                                                    "status": "needs_response"}),
                                   StripeNow()) == "registrado"
    log = {r["action"]: r["detail"] for r in directory.log()}
    assert log["reembolso"].startswith("cafe · ch_1 · 24,20 EUR")
    assert log["contracargo_abierto"].startswith("cafe · ch_1 · 24,20 EUR · fraudulent")


class LiveStripe(StripeNow):
    live = True


@needs_pg
def test_notices_from_the_other_stripe_mode_and_late_checkouts_change_nothing(directory):
    directory.create("cafe", "Café")
    directory.record_subscription("cafe", subscription("active"))
    test_notice = event(obj=subscription("canceled", days=-1))
    test_notice["livemode"] = False
    assert directory.process_event(test_notice, LiveStripe()) == "otro_modo"
    # A checkout's notice without the subscription in it does not hide the one already paid.
    directory.process_event(event("checkout.session.completed", {"client_reference_id": "cafe", "customer": "cus_1",
                                                                 "subscription": "sub_9"}))
    t = directory.get("cafe")
    assert (t["billing_status"], t["stripe_subscription"]) == ("active", "sub_1")


@needs_pg
def test_the_operator_sees_what_to_do_in_stripe(directory):
    directory.create("cafe", "Café")
    for sub_id in ("sub_1", "sub_2", "sub_2"):
        directory.process_event(event("customer.subscription.updated", subscription("active", sub_id=sub_id)))
    directory.process_event(event("charge.refunded", {"id": "ch_1", "customer": "cus_1", "amount_refunded": 2000,
                                                      "currency": "eur"}))
    alerts = {a["action"]: a for a in directory.billing_alerts()}
    assert set(alerts) == {"suscripcion_duplicada", "reembolso"}
    assert alerts["suscripcion_duplicada"]["detail"] == "cafe · sub_1, sub_2"
