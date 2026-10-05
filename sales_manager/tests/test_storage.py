"""Amounts are stored exactly, and one-off schema changes run once, in order, and are recorded."""

import pytest

from core.db import VERSIONED_MIGRATIONS, Store


@pytest.fixture
def shop(make_store):
    s = make_store()
    s.load_preset("retail", with_demo_sales=False)
    return s


def pid(store, sku):
    return int(store.products().set_index("sku").loc[sku]["id"])


def float_columns(store):
    with store.db.tx() as cur:
        return store.db.float_columns(cur)


def test_new_database_is_at_the_latest_version(shop):
    assert shop.schema_version() == VERSIONED_MIGRATIONS[-1][0]
    assert float_columns(shop) == []


def test_many_small_amounts_add_up_exactly(shop):
    p = pid(shop, "CAM-001")
    shop.upsert_product({**shop.products().set_index("id").loc[p].to_dict(), "price": 0.1, "stock": 100,
                         "sku": "CAM-001"}, p)
    for _ in range(30):
        shop.create_sale([{"product_id": p, "quantity": 1}], "Efectivo")
    with shop.db.tx() as cur:
        total = cur.execute("SELECT SUM(total) AS t, SUM(1) AS n FROM sales").fetchone()
    assert isinstance(total["t"], float) and isinstance(total["n"], int)
    if shop.db.real.startswith("NUMERIC"):
        assert total["t"] == 3.0  # binary floats would give 3.0000000000000013
    assert round(total["t"], 2) == 3.0
    assert shop.day_summary(shop.sales().iloc[0]["created_at"].date())["total"] == pytest.approx(3.0)


def test_old_postgres_database_becomes_exact_once(make_store):
    s = make_store()
    if not s.db.real.startswith("NUMERIC"):
        pytest.skip("SQLite has no exact decimal type")
    s.load_preset("retail", with_demo_sales=True)
    before = s.sales()[["number", "total", "tax"]].sort_values("number").reset_index(drop=True)
    prices = s.products()[["sku", "price", "cost"]].sort_values("sku").reset_index(drop=True)
    with s.db.tx() as cur:  # what a database from before this change looks like
        cols = cur.execute("SELECT table_name, column_name FROM information_schema.columns WHERE "
                           "table_schema = current_schema() AND data_type = 'numeric'").fetchall()
        for c in cols:
            cur.execute(f"ALTER TABLE {c['table_name']} ALTER COLUMN {c['column_name']} TYPE DOUBLE PRECISION")
        cur.execute("DELETE FROM schema_migrations")
    assert len(float_columns(s)) == len(cols) > 30

    reopened = Store(s.db._key)
    try:
        assert float_columns(reopened) == [] and reopened.schema_version() == 1
        after = reopened.sales()[["number", "total", "tax"]].sort_values("number").reset_index(drop=True)
        assert after.equals(before)
        assert reopened.products()[["sku", "price", "cost"]].sort_values("sku").reset_index(drop=True).equals(prices)
        Store(s.db._key).close()  # a second start does nothing more
        assert reopened.schema_version() == 1
    finally:
        reopened.close()
