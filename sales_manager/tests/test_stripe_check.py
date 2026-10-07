"""The operator's Stripe check: what it reports for a well set-up account and for each usual mistake."""

import json
import os
from urllib.parse import urlsplit

import pytest

from core.billing import Stripe
from core.stripe_check import MISSING, OK, UNKNOWN, WARN, WEBHOOK_EVENTS, diagnose

DENIED = (403, {"error": {"type": "permission_error", "message": "The provided key does not have the required permissions"}})
BAD_PARAM = (400, {"error": {"type": "invalid_request_error", "message": "Received unknown parameter"}})


def account(overrides: dict | None = None):
    """A Stripe account answering by path, as it is set up; overrides replace one answer."""
    routes = {
        ("GET", "/v1/prices/price_1"): (200, {"id": "price_1", "active": True, "currency": "eur", "unit_amount": 2000,
                                              "recurring": {"interval": "month"}, "tax_behavior": "exclusive",
                                              "product": {"id": "prod_1", "active": True}}),
        ("GET", "/v1/customers"): (200, {"data": []}),
        ("GET", "/v1/subscriptions"): (200, {"data": []}),
        ("GET", "/v1/charges"): (200, {"data": []}),
        ("GET", "/v1/checkout/sessions"): (200, {"data": []}),
        ("POST", "/v1/customers"): BAD_PARAM,
        ("POST", "/v1/checkout/sessions"): BAD_PARAM,
        ("POST", "/v1/billing_portal/sessions"): BAD_PARAM,
        ("GET", "/v1/webhook_endpoints"): (200, {"data": [{"url": "https://app.nirkana.es/stripe/webhook",
                                                           "status": "enabled",
                                                           "enabled_events": sorted(WEBHOOK_EVENTS)}]}),
        ("GET", "/v1/billing_portal/configurations"): (200, {"data": [{"features": {
            "subscription_update": {"enabled": False}, "invoice_history": {"enabled": True},
            "subscription_cancel": {"enabled": True}}}]}),
        ("GET", "/v1/promotion_codes"): (200, {"data": []}),
    }
    routes.update(overrides or {})
    calls = []

    def transport(method, url, data, headers):
        path = urlsplit(url).path
        calls.append((method, path, data))
        status, body = routes.get((method, path), (404, {"error": {"message": "not found"}}))
        return status, json.dumps(body).encode()
    return transport, calls


def levels(checks):
    return {c.title: c.level for c in checks}


def test_a_well_set_up_account_is_ready_and_nothing_is_created():
    transport, calls = account()
    checks = diagnose(Stripe("rk_live_1", "price_1", transport), "https://app.nirkana.es", "whsec_1", True)
    assert all(c.level == OK for c in checks), [(c.title, c.level, c.detail) for c in checks]
    assert any("20,00 EUR cada mes" in c.title for c in checks) and any("sumado" in c.title for c in checks)
    for method, _, data in calls:  # every write is only a probe with an unknown parameter
        assert method == "GET" or data == b"nk_diagnostico=1"


def test_every_usual_mistake_is_named():
    transport, _ = account({
        ("GET", "/v1/prices/price_1"): (200, {"id": "price_1", "active": True, "currency": "eur", "unit_amount": 2000,
                                              "recurring": {"interval": "year"}, "tax_behavior": "unspecified",
                                              "product": {"id": "prod_1", "active": True}}),
        ("POST", "/v1/customers"): DENIED,
        ("GET", "/v1/charges"): DENIED,
        ("GET", "/v1/webhook_endpoints"): (200, {"data": [{"url": "https://app.nirkana.es/stripe/webhook",
                                                           "status": "enabled",
                                                           "enabled_events": ["checkout.session.completed"]}]}),
        ("GET", "/v1/billing_portal/configurations"): (200, {"data": [{"features": {
            "subscription_update": {"enabled": True}}}]}),
        ("GET", "/v1/promotion_codes"): (200, {"data": [{"code": "GRATIS", "coupon": {"percent_off": 100,
                                                                                     "duration": "forever"}}]}),
    })
    checks = diagnose(Stripe("sk_test_1", "price_1", transport), "https://app.nirkana.es", "", False)
    found = levels(checks)
    assert found["Clave secreta completa"] == WARN
    assert found["El precio no dice si lleva IVA"] == MISSING
    assert found["El precio no es mensual (20,00 EUR cada año)"] == WARN
    assert found["Falta permiso de escritura en «Customers»"] == MISSING
    assert "«Suscribirme» falla" in next(c.detail for c in checks if "escritura en «Customers»" in c.title)
    assert found["Falta permiso de lectura en «Charges»"] == MISSING
    assert "El precio no está en euros (EUR)" not in found
    missing_events = next(c for c in checks if c.title == "Al webhook le faltan eventos")
    assert "charge.dispute.created" in missing_events.detail and "charge.refunded" in missing_events.detail
    assert found["El portal deja cambiar de plan"] == WARN
    assert any("GRATIS" in t for t in found)
    assert found["Falta STRIPE_WEBHOOK_SECRET en el servidor"] == MISSING
    assert found["STRIPE_SECRET_KEY no está en las variables del servidor"] == WARN


def test_what_the_key_cannot_see_is_said_not_guessed():
    transport, _ = account({("GET", "/v1/webhook_endpoints"): DENIED,
                              ("GET", "/v1/billing_portal/configurations"): DENIED,
                              ("GET", "/v1/promotion_codes"): DENIED,
                              ("GET", "/v1/prices/price_1"): (404, {"error": {"message": "No such price"}})})
    found = levels(diagnose(Stripe("rk_test_1", "price_1", transport), "", "whsec_1", True))
    assert found["No puedo ver los webhooks con esta clave"] == UNKNOWN
    assert found["No puedo ver la configuración del portal de clientes"] == UNKNOWN
    assert found["El precio price_1 no existe en esta cuenta"] == MISSING


def test_stripe_unreachable_is_one_clear_line():
    def offline(*_):
        raise OSError("sin red")
    checks = diagnose(Stripe("rk_test_1", "price_1", offline))
    assert [c.level for c in checks[-1:]] == [MISSING] and "conectar" in checks[-1].detail


@pytest.mark.skipif(not os.environ.get("STRIPE_MOCK_URL"), reason="STRIPE_MOCK_URL not set (run stripe/stripe-mock)")
def test_every_probe_is_valid_for_stripe():
    stripe = Stripe("sk_test_123", "price_123", api_base=os.environ["STRIPE_MOCK_URL"])
    checks = diagnose(stripe, "https://app.nirkana.es", "whsec_1", True)
    assert not any("conectar" in c.title for c in checks)
    assert not any(c.title.startswith("Falta permiso") for c in checks)  # the simulator allows everything
