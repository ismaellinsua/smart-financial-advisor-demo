from datetime import datetime, timedelta

import pytest

from core import automation
from core.db import SaleError, Store
from core.presets import PRESETS
from core.pricing import compute_totals, format_money
from core.receipts import receipt_html


@pytest.fixture
def store(make_store):
    s = make_store()
    s.load_preset("retail", with_demo_sales=False)
    return s


def product_id(store, sku):
    df = store.products()
    return int(df.loc[df["sku"] == sku, "id"].iloc[0])


def test_compute_totals_applies_discount_before_tax():
    totals = compute_totals([{"unit_price": 10, "quantity": 3}, {"unit_price": 5.5, "quantity": 2}], 10, 21)
    assert totals == {"subtotal": 41.0, "discount": 4.1, "tax": 7.75, "total": 44.65}


def test_compute_totals_rejects_invalid_discount():
    with pytest.raises(ValueError):
        compute_totals([{"unit_price": 1, "quantity": 1}], 120, 21)


def test_format_money():
    assert format_money(1234.5) == "1.234,50 €"


def test_sale_decrements_stock_and_numbers_sequentially(store):
    pid = product_id(store, "CAM-001")
    before = int(store.products().set_index("id").loc[pid, "stock"])
    first = store.create_sale([{"product_id": pid, "quantity": 2}], "Tarjeta")
    second = store.create_sale([{"product_id": pid, "quantity": 1}], "Efectivo")
    year = datetime.now().year
    assert first["number"] == f"VTA-{year}-00001"
    assert second["number"] == f"VTA-{year}-00002"
    assert int(store.products().set_index("id").loc[pid, "stock"]) == before - 3
    assert first["total"] == pytest.approx(39.90 * 2 * 1.21, abs=0.01)


def test_sale_rejects_insufficient_stock_without_side_effects(store):
    pid = product_id(store, "BOL-004")
    stock = int(store.products().set_index("id").loc[pid, "stock"])
    with pytest.raises(SaleError):
        store.create_sale([{"product_id": pid, "quantity": stock + 1}], "Tarjeta")
    assert store.sales().empty
    assert int(store.products().set_index("id").loc[pid, "stock"]) == stock


def test_cancel_sale_restores_stock(store):
    pid = product_id(store, "CIN-005")
    stock = int(store.products().set_index("id").loc[pid, "stock"])
    sale = store.create_sale([{"product_id": pid, "quantity": 4}], "Tarjeta")
    store.cancel_sale(sale["id"])
    assert int(store.products().set_index("id").loc[pid, "stock"]) == stock
    assert store.sale(sale["id"])["status"] == "anulada"
    with pytest.raises(SaleError):
        store.cancel_sale(sale["id"])


def test_services_preset_does_not_track_stock(make_store):
    s = make_store()
    s.load_preset("services", with_demo_sales=False)
    pid = int(s.products()["id"].iloc[0])
    sale = s.create_sale([{"product_id": pid, "quantity": 5}], "Transferencia")
    assert sale["items"][0]["quantity"] == 5


@pytest.mark.parametrize("business_type", list(PRESETS))
def test_every_preset_generates_demo_activity(make_store, business_type):
    s = make_store()
    s.load_preset(business_type)
    assert len(s.sales()) > 50
    assert (s.products()["stock"] >= 0).all()


def test_reorder_suggestions_cover_lead_time(store):
    pid = product_id(store, "VEL-006")
    now = datetime.now()
    for d in range(10):
        store.create_sale([{"product_id": pid, "quantity": 3}], "Tarjeta", when=now - timedelta(days=d))
    products = store.products()
    suggestions = automation.reorder_suggestions(products, store.sale_lines(), lead_days=14, now=now)
    row = suggestions[suggestions["sku"] == "VEL-006"].iloc[0]
    # 30 units in a 30-day window -> 1/day; target = 14 + min_stock(12) = 26; stock = 40 - 30 = 10.
    assert row["suggested_qty"] == 16


def test_low_stock_and_inactive_customers(store):
    pid = product_id(store, "BOL-004")
    cid = store.upsert_customer({"name": "Ana López", "email": "ana@example.com"})
    store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta", customer_id=cid,
                      when=datetime.now() - timedelta(days=90))
    assert "BOL-004" in set(automation.low_stock(store.products())["sku"])
    inactive = automation.inactive_customers(store.customers(), store.sales(), days=60)
    assert list(inactive["name"]) == ["Ana López"]
    assert "Ana" in automation.followup_message("Ana López", "Mi Negocio")


def test_kpis_compare_periods(store):
    pid = product_id(store, "CAM-001")
    now = datetime.now()
    store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta", when=now - timedelta(days=10))
    store.create_sale([{"product_id": pid, "quantity": 2}], "Tarjeta", when=now)
    start, end, prev_start = automation.period_bounds(7, now)
    k = automation.kpis(store.sales(), store.sale_lines(), start, end, prev_start)
    assert k["count"] == 1
    assert k["revenue_delta"] == pytest.approx(100.0)


def test_receipt_escapes_html(store):
    store.save_settings({"business_name": "<script>x</script>"})
    pid = product_id(store, "CAM-001")
    sale = store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")
    html = receipt_html(sale, store.settings())
    assert "<script>x" not in html
    assert sale["number"] in html


def test_backup_and_restore_round_trip(store, make_store):
    pid = product_id(store, "CAM-001")
    store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")
    backup = store.backup_bytes()

    other = make_store()
    other.load_preset("services", with_demo_sales=False)
    other.restore(backup)
    assert len(other.sales()) == 1
    assert set(other.products()["sku"]) == set(store.products()["sku"])


def test_restore_rejects_invalid_files(store):
    import sqlite3, tempfile
    from pathlib import Path

    with pytest.raises(ValueError):
        store.restore(b"esto no es una base de datos")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "other.db"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE foo (x)")
        conn.commit()
        conn.close()
        with pytest.raises(ValueError):
            store.restore(path.read_bytes())
    assert not store.products().empty  # untouched


def test_ids_continue_after_reload(store):
    """After a reset or restore, new rows get fresh ids instead of colliding with copied ones."""
    pid = product_id(store, "CAM-001")
    first = store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")
    store.restore(store.backup_bytes())
    second = store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")
    assert second["id"] > first["id"]
    store.reset()
    assert store.is_empty()
    new_id = store.upsert_product({"sku": "X-1", "name": "Nuevo", "category": "General", "price": 1, "cost": 0,
                                   "stock": 1, "min_stock": 0, "track_stock": 1, "active": 1})
    assert new_id >= 1


def test_postgres_reconnects_after_server_drops_connections(make_store):
    """Free cloud databases suspend and drop idle connections; the next request must still work."""
    if make_store.targets.backend != "postgres":
        pytest.skip("PostgreSQL only")
    import psycopg

    from conftest import PG_URL

    store = make_store()
    store.load_preset("retail", with_demo_sales=False)
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid()"
        )
    assert not store.products().empty
