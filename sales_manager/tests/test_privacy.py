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


def test_old_logs_errors_and_sessions_are_deleted_on_schedule(store):
    from datetime import timedelta

    from core import clock
    from core.store_privacy import RETENTION_DAYS

    now = clock.now()
    uid = store.create_user("Ana", "ana", "admin", "Segura2026!")
    old, recent = store.create_session(uid), store.create_session(uid)
    long_ago = (now - timedelta(days=RETENTION_DAYS["audit_log"] + 1)).isoformat(timespec="seconds")
    stale = (now - timedelta(days=RETENTION_DAYS["sessions"] + 1)).isoformat(timespec="seconds")
    with store.db.tx() as cur:
        cur.execute("INSERT INTO audit_log(happened_at, username, action, detail) VALUES (?, 'ana', 'acceso', '')",
                    (long_ago,))
        cur.execute("INSERT INTO app_errors(happened_at, ref, kind) VALUES (?, 'E1', 'KeyError')", (long_ago,))
        cur.execute("UPDATE sessions SET last_seen = ? WHERE id = (SELECT MIN(id) FROM sessions)", (stale,))
    before = len(store.audit_log(limit=10_000))

    done = store.apply_retention(now)
    assert done == {"audit_log": 1, "app_errors": 1, "sessions": 1}
    log = store.audit_log(limit=10_000)
    assert len(log) == before  # the old line went, the note of what was deleted came in
    assert log.iloc[0]["action"] == "datos_caducados_borrados"
    assert store.resume_session(recent, 60) is not None and store.resume_session(old, 10**6) is None
    assert store.apply_retention(now) == {"audit_log": 0, "app_errors": 0, "sessions": 0}


def test_erasure_also_clears_the_contact_kept_on_their_appointments(store):
    from datetime import timedelta

    from core import clock

    cid = store.upsert_customer({"name": "Iker Sanz", "email": "iker@example.com", "phone": "699000111"})
    start = clock.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=3)
    store.create_appointment(start, 30, customer_id=cid, customer_name="Iker Sanz", phone="699000111")
    exported = json.loads(store.customer_data_export(cid, by="ana"))
    assert exported["citas"][0]["phone"] == "699000111"  # the right of access covers it too
    store.forget_customer(cid, by="ana")
    with store.db.tx() as cur:
        row = cur.execute("SELECT customer_name, phone, email, cancel_hash FROM appointments "
                          "WHERE customer_id = ?", (cid,)).fetchone()
    assert row["phone"] == "" and row["email"] == "" and row["cancel_hash"] == ""
    assert row["customer_name"].startswith("Cliente eliminado")


def test_retention_runs_from_the_app_once_a_day(store):
    from datetime import datetime

    day = datetime(2026, 10, 6, 9, 0)
    assert store.daily_housekeeping(day) is True
    assert store.daily_housekeeping(day.replace(hour=18)) is False  # already done today
    assert store.daily_housekeeping(day.replace(day=7)) is True


def test_sensitive_operations_check_the_role_themselves(store):
    from core.errors import PermissionDenied

    cid = store.upsert_customer({"name": "Ana Ruiz", "email": "ana@example.com"})
    sale = _buy(store, cid)
    for call in (lambda: store.cancel_sale(sale["id"], by="lucia", as_role="empleado"),
                 lambda: store.customer_data_export(cid, by="lucia", as_role="empleado"),
                 lambda: store.forget_customer(cid, by="lucia", as_role="empleado")):
        with pytest.raises(PermissionDenied):
            call()
    store.cancel_sale(sale["id"], by="javier", as_role="encargado")  # a manager may
