"""Small improvements from the audit: barcode scanning at the till, the customer card, one redemption of the same
points at a time, and each fixed expense once a month."""

import threading
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.db import SaleError, Store
from test_app import SCRIPT

ROOT = str(Path(__file__).resolve().parent.parent)


def test_a_scanned_code_goes_straight_to_the_ticket(module_targets):
    target = module_targets.new()
    store = Store(target)
    store.load_preset("retail", with_demo_sales=False)
    sku = store.products().iloc[0]["sku"]
    store.close()
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=target, fn="point_of_sale", role="empleado"),
                             default_timeout=30).run()
    box = next(t for t in at.text_input if t.key == "pos_query")
    box.input(sku.lower()).run()  # the scanner types the code and Enter
    assert not at.exception, at.exception
    assert next(t for t in at.text_input if t.key == "pos_query").value == ""
    assert any("Ver ticket y cobrar (1)" in b.label for b in at.button)
    next(t for t in at.text_input if t.key == "pos_query").input("bolso").run()  # a search is just a search
    assert next(t for t in at.text_input if t.key == "pos_query").value == "bolso"


def test_customer_card_shows_purchases_favourites_and_points(make_store):
    store = make_store()
    store.load_preset("retail", with_demo_sales=False)
    cid = store.upsert_customer({"name": "Lucía", "phone": "600111222"})
    p = store.products().iloc[0]
    store.adjust_stock(int(p["id"]), 10, "Prueba")
    store.create_sale([{"product_id": int(p["id"]), "quantity": 2}], customer_id=cid)
    store.create_sale([{"product_id": int(p["id"]), "quantity": 1}], customer_id=cid)
    card = store.customer_history(cid)
    assert len(card["sales"]) == 2 and card["favourites"].iloc[0]["name"] == p["name"]
    assert int(card["favourites"].iloc[0]["units"]) == 3 and card["points"] > 0


def test_customer_card_renders(module_targets):
    target = module_targets.new()
    store = Store(target)
    store.load_preset("retail")
    store.close()
    at = AppTest.from_string(SCRIPT.format(root=ROOT, db=target, fn="customers_page", role="admin"),
                             default_timeout=30).run()
    assert not at.exception, at.exception
    assert any(m.label == "Compras" for m in at.metric)


def test_the_same_points_cannot_be_spent_twice_at_once(make_store):
    store = make_store()
    store.load_preset("retail", with_demo_sales=False)
    store.save_settings({"points_per_euro": "1", "point_value": "0.01", "min_redeem_points": "100"})
    cid = store.upsert_customer({"name": "Lucía"})
    p = store.products().sort_values("price").iloc[-1]
    store.adjust_stock(int(p["id"]), 20, "Prueba")
    store.create_sale([{"product_id": int(p["id"]), "quantity": 2}], customer_id=cid)
    balance = store.customer_points(cid)
    assert balance >= 100
    results = []

    def redeem():
        try:
            store.create_sale([{"product_id": int(p["id"]), "quantity": 1}], customer_id=cid, redeem_points=balance)
            results.append("ok")
        except SaleError as exc:
            results.append(str(exc))

    threads = [threading.Thread(target=redeem) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 1, results
    assert store.customer_points(cid) >= 0


def test_fixed_expenses_once_a_month_even_posted_twice(make_store):
    store = make_store()
    store.load_preset("retail", with_demo_sales=False)
    rid = store.save_recurring("Alquiler", "Local", 800, 1)
    store.apply_recurring(until=date(2026, 10, 5))
    with pytest.raises(store.db.integrity_errors):  # the database itself refuses a second one for the same month
        store.add_expense(date(2026, 10, 2), "Alquiler", "Local", 800, recurring_id=rid)
    assert store.apply_recurring(until=date(2026, 10, 5)) == 0
    expenses = store.expenses(date(2026, 10, 1), date(2026, 11, 1))
    assert len(expenses[expenses["description"] == "Local"]) == 1


def test_a_hand_edited_backup_with_huge_texts_is_refused(make_store, tmp_path):
    import sqlite3

    source = make_store()
    source.load_preset("retail", with_demo_sales=False)
    path = tmp_path / "copia.db"
    path.write_bytes(source.backup_bytes())
    conn = sqlite3.connect(path)
    conn.execute("UPDATE products SET name = ?", ("x" * 50_000,))
    conn.commit()
    conn.close()
    target = make_store()
    with pytest.raises(ValueError, match="demasiado largos"):
        target.restore(path.read_bytes())


def test_replacing_data_asks_for_the_password_again(make_store):
    store = make_store()
    uid = store.create_user("Ana", "ana", "admin", "Segura2026!")
    assert store.confirm_secret(uid, "Segura2026!")
    assert not store.confirm_secret(uid, "otra") and not store.confirm_secret(uid, "")
    assert store.settings()["session_minutes"] == "480"  # a work shift, not a whole day
