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


def test_a_set_up_database_opens_with_one_query(shop, monkeypatch):
    import core.db as db

    target = shop.db._key if hasattr(shop.db, "_key") else None
    if target is None:  # SQLite: reopen the same file
        with shop.db.tx() as cur:
            target = cur.execute("PRAGMA database_list").fetchone()["file"]
    calls = []
    original = db._Cursor.execute
    monkeypatch.setattr(db._Cursor, "execute", lambda self, sql, params=(): calls.append(sql) or original(self, sql,
                                                                                                         params))
    db.Store(target).close()
    assert len(calls) == 1  # already set up by this version of the code

    calls.clear()
    monkeypatch.setattr(db, "SCHEMA_FINGERPRINT", "una-version-nueva")
    again = db.Store(target)
    assert len(calls) > 50  # a new version sets the database up once…
    assert again.products().shape[0] == shop.products().shape[0]  # …keeping the data
    again.close()
    calls.clear()
    db.Store(target).close()
    assert len(calls) == 1


def test_settings_and_locations_are_reused_but_never_stale_after_a_write(shop, monkeypatch):
    import core.db as db
    import core.engines as engines

    calls = []
    original = db._Cursor.execute
    monkeypatch.setattr(db._Cursor, "execute", lambda self, sql, params=(): calls.append(sql) or original(self, sql,
                                                                                                         params))
    shop.settings(), shop.locations()
    calls.clear()
    for _ in range(5):
        shop.settings(), shop.locations()
    assert calls == []  # one click reads them several times: no round trips

    shop.save_settings({"business_name": "Nuevo nombre"})
    assert shop.settings()["business_name"] == "Nuevo nombre"
    new = shop.add_location("Centro")
    assert new in [loc["id"] for loc in shop.locations()]
    with shop.db.tx() as cur:  # any write, even one the app makes by hand
        cur.execute("UPDATE settings SET value = 'EUR' WHERE key = 'currency'")
    assert shop.settings()["currency"] == "EUR"
    shop.settings()["business_name"] = "cambiado fuera"  # callers get a copy
    assert shop.settings()["business_name"] == "Nuevo nombre"

    monkeypatch.setattr(engines, "READ_TTL", 0)  # and after READ_TTL it reads again, for changes by other servers
    calls.clear()
    shop.settings()
    assert len(calls) == 1
