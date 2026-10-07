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
    s = make_store(owner=True)  # rebuilds an old database by hand (DDL), as the schema's owner
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
        latest = max(v for v, *_ in VERSIONED_MIGRATIONS)
        assert float_columns(reopened) == [] and reopened.schema_version() == latest
        after = reopened.sales()[["number", "total", "tax"]].sort_values("number").reset_index(drop=True)
        assert after.equals(before)
        assert reopened.products()[["sku", "price", "cost"]].sort_values("sku").reset_index(drop=True).equals(prices)
        Store(s.db._key).close()  # a second start does nothing more
        assert reopened.schema_version() == latest
    finally:
        reopened.close()


def test_a_set_up_database_opens_with_one_query(shop, monkeypatch):
    import core.db as db

    target = shop.db._key if hasattr(shop.db, "_key") else None
    if target is None:  # SQLite: reopen the same file
        with shop.db.tx() as cur:
            target = cur.execute("PRAGMA database_list").fetchone()["file"]
    calls = []
    original = db.Cursor.execute
    monkeypatch.setattr(db.Cursor, "execute", lambda self, sql, params=(): calls.append(sql) or original(self, sql,
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
    original = db.Cursor.execute
    monkeypatch.setattr(db.Cursor, "execute", lambda self, sql, params=(): calls.append(sql) or original(self, sql,
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


def test_remote_database_certificate_is_checked():
    """With the app's settings a server whose certificate is not from a trusted authority is refused: here the
    local test server, which uses a self-signed one, reached by an address the app treats as remote."""
    import psycopg

    from conftest import PG_URL
    from core.engines import secure_url

    if not PG_URL or "localhost" not in PG_URL:
        pytest.skip("needs the local PostgreSQL of the test suite")
    url = secure_url(PG_URL.replace("localhost", "pg.example.invalid"))  # what the app would use for a remote host
    assert "sslmode=verify-full" in url
    checked = url.replace("pg.example.invalid", "127.0.0.1")
    with pytest.raises(psycopg.OperationalError, match="certificate|SSL|ssl"):
        psycopg.connect(checked, connect_timeout=5).close()


def test_hot_lookups_use_an_index(make_store):
    """The public cancel link, the hourly booking limit and per-product sales are found through an index, not by
    reading the whole table (checked with the database's own query plan)."""
    shop = make_store()
    with shop.db.tx() as cur:
        if shop.db.for_update:  # PostgreSQL: forbid sequential scans to see whether an index can be used at all
            cur.execute("SET LOCAL enable_seqscan = off")
            plan = lambda q, p=(): " ".join(r["QUERY PLAN"] for r in cur.execute("EXPLAIN " + q, p).fetchall())  # noqa: E731
        else:
            plan = lambda q, p=(): " ".join(r["detail"] for r in cur.execute("EXPLAIN QUERY PLAN " + q, p).fetchall())  # noqa: E731
        for query, index in [
            ("SELECT * FROM appointments WHERE cancel_hash = ? AND cancel_hash <> ''", "idx_appointments_cancel"),
            ("SELECT COUNT(*) FROM appointments WHERE source = 'online' AND created_at >= ?", "idx_appointments_source"),
            ("SELECT * FROM sale_items WHERE product_id = ?", "idx_items_product"),
            ("SELECT * FROM loyalty_moves WHERE sale_id = ?", "idx_loyalty_sale"),
        ]:
            params = ("x",) if "?" in query and "product_id" not in query and "sale_id" not in query else (1,)
            assert index in plan(query, params), (query, plan(query, params))
        names = {r["name"] for r in cur.execute(
            "SELECT indexname AS name FROM pg_indexes WHERE schemaname = current_schema()" if shop.db.for_update
            else "SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()}
    assert not {"idx_invoices_sale", "idx_credit_notes_refund"} & names  # redundant with UNIQUE


def test_locations_and_suppliers_are_real_foreign_keys(make_store):
    """A stock move or a product cannot point to a location or a supplier that does not exist."""
    shop = make_store()
    shop.load_preset("retail", with_demo_sales=False)
    for sql in ("INSERT INTO stock_moves(product_id, delta, stock_after, created_at, location_id) "
                "VALUES ((SELECT MIN(id) FROM products), 1, 1, '2026-01-01', 999999)",
                "UPDATE products SET supplier_id = 999999",
                "UPDATE users SET location_id = 999999"):
        if sql.startswith("UPDATE users"):
            shop.create_user("Ana", "ana", "empleado", "482619")
        with pytest.raises(shop.db.integrity_errors):
            with shop.db.tx() as cur:
                cur.execute(sql)


def test_old_databases_get_the_foreign_keys_once(make_store):
    """A PostgreSQL database from before keeps working and gains the keys at its next start (migration 2)."""
    target = make_store.targets.new()
    shop = make_store(target, owner=True)  # rebuilds an old database by hand (DDL)
    if not shop.db.for_update:
        pytest.skip("SQLite cannot add foreign keys to existing tables")
    with shop.db.tx() as cur:  # make it look like a database from before
        for name in [r["conname"] for r in cur.execute(
                "SELECT conname FROM pg_constraint WHERE conrelid = to_regclass('sales') AND contype = 'f' "
                "AND pg_get_constraintdef(oid) LIKE '%locations%'").fetchall()]:
            cur.execute(f"ALTER TABLE sales DROP CONSTRAINT {name}")
        cur.execute("DELETE FROM schema_migrations WHERE version = 2")
        cur.execute("DROP TABLE schema_state")
    again = make_store(target)  # the next start
    with again.db.tx() as cur:
        rows = cur.execute("SELECT conname, convalidated, pg_get_constraintdef(oid) AS d FROM pg_constraint "
                           "WHERE conrelid = to_regclass('sales') AND contype = 'f'").fetchall()
    added = [r for r in rows if "locations" in r["d"]]
    assert added and added[0]["conname"] == "fk_sales_location_id" and added[0]["convalidated"]
    assert again.schema_version() == max(v for v, *_ in VERSIONED_MIGRATIONS)


def test_only_known_states_and_roles_are_stored(make_store):
    """A typo in a status or a role can never be saved, even by hand, so reports never miss rows."""
    shop = make_store()
    shop.load_preset("retail", with_demo_sales=False)
    pid = int(shop.products().iloc[0]["id"])
    sale = shop.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")
    shop.create_user("Ana", "ana", "empleado", "482619")
    for sql in (f"UPDATE sales SET status = 'Anulada' WHERE id = {sale['id']}",
                "UPDATE users SET role = 'superadmin'"):
        with pytest.raises(shop.db.integrity_errors):
            with shop.db.tx() as cur:
                cur.execute(sql)


def test_old_databases_get_the_checks_once(make_store):
    target = make_store.targets.new()
    shop = make_store(target, owner=True)  # rebuilds an old database by hand (DDL)
    if not shop.db.for_update:
        pytest.skip("SQLite cannot add checks to existing tables")
    with shop.db.tx() as cur:  # a database from before: no checks, and one odd old row
        for name in ("ck_sales_status", "ck_users_role"):
            cur.execute(f"ALTER TABLE {'sales' if 'sales' in name else 'users'} DROP CONSTRAINT {name}")
        cur.execute("INSERT INTO users(username, name, role, secret_hash, created_at) "
                    "VALUES ('raro', 'Raro', 'otro', 'x', '2026-01-01')")
        cur.execute("DELETE FROM schema_migrations WHERE version = 3")
        cur.execute("DROP TABLE schema_state")
    again = make_store(target)  # starts fine despite the odd row
    with again.db.tx() as cur:
        checks = {r["conname"]: r["convalidated"] for r in cur.execute(
            "SELECT conname, convalidated FROM pg_constraint WHERE conname IN ('ck_sales_status', 'ck_users_role') "
            "AND connamespace = (SELECT oid FROM pg_namespace WHERE nspname = current_schema())").fetchall()}
    assert checks == {"ck_sales_status": True, "ck_users_role": False}  # enforced; the old row is left alone
    with pytest.raises(again.db.integrity_errors):
        with again.db.tx() as cur:
            cur.execute("UPDATE users SET role = 'superadmin' WHERE username = 'raro'")


def test_one_customer_per_tax_number_and_one_location_per_name(make_store):
    shop = make_store()
    shop.load_preset("retail", with_demo_sales=False)
    first = shop.upsert_customer({"name": "Cafés Sol SL", "tax_id": "b-1234567-4"})
    assert shop.customers().set_index("id").loc[first, "tax_id"] == "B12345674"  # one spelling
    with pytest.raises(ValueError, match="Ya hay un cliente con el NIF B12345674"):
        shop.upsert_customer({"name": "Otro", "tax_id": "B 1234567 4"})
    shop.upsert_customer({"name": "Cafés Sol, S.L."}, first)  # editing the same customer is fine
    shop.upsert_customer({"name": "Sin NIF"})
    shop.upsert_customer({"name": "Sin NIF tampoco"})  # empty tax numbers never clash
    with pytest.raises(shop.db.integrity_errors):  # the database refuses it too
        with shop.db.tx() as cur:
            cur.execute("INSERT INTO customers(name, tax_id, created_at) VALUES ('X', 'B12345674', '2026-01-01')")
    shop.add_location("Centro")
    with pytest.raises(shop.db.integrity_errors):
        with shop.db.tx() as cur:
            cur.execute("INSERT INTO locations(name, created_at) VALUES ('CENTRO', '2026-01-01')")


def test_product_summary_matches_the_line_by_line_figures(make_store):
    """The period report is added up by the database; it must equal adding up every line (returns included)."""
    from datetime import datetime

    shop = make_store()
    shop.load_preset("retail")  # demo sales
    products = shop.products()
    pid = int(products.sort_values("stock", ascending=False).iloc[0]["id"])  # one with stock to spare
    sale = shop.create_sale([{"product_id": pid, "quantity": 3}], "Tarjeta")
    shop.create_refund(sale["id"], {shop.sale(sale["id"])["items"][0]["id"]: 1}, "Tarjeta", "devolución")
    start, end = datetime(2000, 1, 1), datetime(2100, 1, 1)
    lines = shop.sale_lines(start, end)
    by_hand = (lines.groupby(["category", "name"])
               .agg(unidades=("quantity", "sum"), ventas_netas=("revenue", "sum"), margen=("margin", "sum"))
               .round(2).reset_index().sort_values(["category", "name"]).reset_index(drop=True))
    summary = shop.product_summary(start, end).sort_values(["category", "name"]).reset_index(drop=True)
    assert len(summary) == len(by_hand) > 3
    for column in ("unidades", "ventas_netas", "margen"):
        assert (summary[column] - by_hand[column]).abs().max() < 0.011, column
