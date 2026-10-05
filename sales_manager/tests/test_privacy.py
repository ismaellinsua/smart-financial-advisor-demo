"""Customers' data protection rights: access, erasure and consent to marketing."""

import json

import pytest


@pytest.fixture
def store(make_store):
    s = make_store()
    s.load_preset("retail", with_demo_sales=False)
    s.save_settings({"tax_id": "B12345678", "address": "Calle Mayor 1, Madrid", "business_name": "Tienda Sol"})
    for pid in s.promotions()["id"]:
        s.delete_promotion(int(pid))
    return s


def _buy(store, cid):
    df = store.products()
    pid = int(df.loc[df["sku"] == "CAM-001", "id"].iloc[0])
    return store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta", customer_id=cid)


def test_a_customer_can_take_all_their_data(store):
    cid = store.upsert_customer({"name": "Lucía Pérez", "email": "lucia@example.com", "phone": "612345678"})
    sale = _buy(store, cid)
    store.create_invoice(sale["id"], {"name": "Lucía Pérez", "tax_id": "12345678Z", "address": "C/ Luna 2"})
    data = json.loads(store.customer_data_export(cid, by="ana"))
    assert data["cliente"]["email"] == "lucia@example.com" and data["responsable"]["nif"] == "B12345678"
    assert data["compras"][0]["number"] == sale["number"] and data["compras"][0]["items"]
    assert data["facturas"][0]["customer_tax_id"] == "12345678Z"
    assert "datos_exportados" in set(store.audit_log()["action"])


def test_erasure_keeps_invoices_and_figures(store):
    cid = store.upsert_customer({"name": "Lucía Pérez", "email": "lucia@example.com", "phone": "612345678",
                                 "tax_id": "12345678Z", "notes": "Alérgica"})
    store.set_marketing_consent(cid, True)
    sale = _buy(store, cid)
    invoice = store.create_invoice(sale["id"], {"name": "Lucía Pérez", "tax_id": "12345678Z", "address": "C/ Luna"})
    store.forget_customer(cid, by="ana")
    row = store.customers().set_index("id").loc[cid]
    assert row["name"] == f"Cliente eliminado #{cid}"
    assert (row["email"], row["phone"], row["tax_id"], row["notes"], row["marketing_consent"]) == ("", "", "", "", 0)
    kept = store.invoice(invoice["id"])
    assert (kept["customer_name"], kept["customer_tax_id"]) == ("Lucía Pérez", "12345678Z")  # required by law
    assert store.sale(sale["id"])["customer_id"] == cid  # still counts in the figures
    with pytest.raises(ValueError):
        store.forget_customer(cid)
    with pytest.raises(ValueError):
        store.set_marketing_consent(cid, True)


def test_marketing_only_reaches_customers_who_agreed(store):
    yes = store.upsert_customer({"name": "Sí", "email": "si@example.com"})
    no = store.upsert_customer({"name": "No", "email": "no@example.com"})
    store.set_marketing_consent(yes, True, by="ana")
    customers = store.customers()
    assert set(customers.loc[customers["marketing_consent"] == 1, "id"]) == {yes}
    store.set_marketing_consent(yes, False, by="ana")
    assert store.customers().set_index("id").loc[yes, "consent_at"]
    assert not store.customers().set_index("id").loc[no, "consent_at"]
