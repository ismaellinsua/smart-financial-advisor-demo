from datetime import datetime, timedelta

import pytest

from core import automation
from core.db import SaleError, Store
from core.presets import PRESETS
from core.pricing import compute_totals, format_money, format_money_short
from core.receipts import receipt_html


@pytest.fixture
def store(make_store):
    s = make_store()
    s.load_preset("retail", with_demo_sales=False)
    for pid in s.promotions()["id"]:  # template promotions depend on the weekday; tests add their own
        s.delete_promotion(int(pid))
    return s


def product_id(store, sku):
    df = store.products()
    return int(df.loc[df["sku"] == sku, "id"].iloc[0])


def test_compute_totals_applies_discount_before_tax():
    totals = compute_totals([{"unit_price": 10, "quantity": 3}, {"unit_price": 5.5, "quantity": 2}], 10, 21)
    assert {k: totals[k] for k in ("subtotal", "discount", "tax", "total")} == {
        "subtotal": 41.0, "discount": 4.1, "tax": 7.75, "total": 44.65}
    assert sum(totals["net_amounts"]) == pytest.approx(totals["base"])


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
    assert len(s.sales()) > (15 if business_type == "services" else 50)
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
    store.save_settings({"demo_mode": "si"})  # only demonstration data may be replaced
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


def test_format_money_short():
    assert format_money_short(9876.5) == "9.876,50 €"
    assert format_money_short(294474.2) == "294,5 mil €"
    assert format_money_short(1_250_000) == "1,2 M €"


def test_freelancer_demo_figures_are_believable(make_store):
    s = make_store()
    s.load_preset("services")
    start, end, prev_start = automation.period_bounds(30)
    k = automation.kpis(s.sales(), s.sale_lines(), start, end, prev_start)
    assert 3_000 < k["revenue"] < 25_000


# ------------------------------------------------------------------ invoices
def _completed_sale(store, sku="CAM-001", **kwargs):
    return store.create_sale([{"product_id": product_id(store, sku), "quantity": 1}], "Tarjeta", **kwargs)


def test_invoice_numbering_and_rules(store):
    year = datetime.now().year
    cid = store.upsert_customer({"name": "Norte S.L."})
    first = _completed_sale(store, customer_id=cid)
    second = _completed_sale(store)
    with pytest.raises(ValueError):
        store.create_invoice(first["id"], {"name": "Norte S.L.", "tax_id": ""})
    inv1 = store.create_invoice(first["id"], {"name": "Norte S.L.", "tax_id": "B12345678", "address": "Calle 1"})
    inv2 = store.create_invoice(second["id"], {"name": "Ana", "tax_id": "12345678Z"})
    assert (inv1["number"], inv2["number"]) == (f"FAC-{year}-0001", f"FAC-{year}-0002")
    assert inv1["sale"]["total"] == first["total"]
    with pytest.raises(SaleError):
        store.create_invoice(first["id"], {"name": "Norte S.L.", "tax_id": "B12345678"})
    with pytest.raises(SaleError):
        store.cancel_sale(first["id"])  # invoiced sales need a corrective invoice
    customer = store.customers().set_index("id").loc[cid]
    assert (customer["tax_id"], customer["address"]) == ("B12345678", "Calle 1")
    third = _completed_sale(store)
    store.cancel_sale(third["id"])
    with pytest.raises(SaleError):
        store.create_invoice(third["id"], {"name": "Ana", "tax_id": "12345678Z"})
    assert list(store.invoices()["number"]) == [inv2["number"], inv1["number"]]


def test_pdfs_are_generated(store):
    from core.pdfs import cash_closing_pdf, invoice_pdf

    store.save_settings({"business_name": "Café <Aurora> & Co", "accent_color": "no-es-un-color"})
    sale = _completed_sale(store)
    invoice = store.create_invoice(sale["id"], {"name": "Cliente <b>", "tax_id": "X"})
    assert invoice_pdf(invoice, store.settings()).startswith(b"%PDF")
    closing = store.close_cash(datetime.now().date(), 100, 100)
    assert cash_closing_pdf(closing, store.settings()).startswith(b"%PDF")


# -------------------------------------------------------------- appointments
def test_appointments_overlap_charge_and_status(make_store):
    s = make_store()
    s.load_preset("services", with_demo_sales=False)
    pid = int(s.products()["id"].iloc[0])
    day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    a1 = s.create_appointment(day.replace(hour=10), 60, product_id=pid, customer_name="Laura")
    with pytest.raises(ValueError, match="solapa"):
        s.create_appointment(day.replace(hour=10, minute=30), 60, product_id=pid, customer_name="Pablo")
    s.create_appointment(day.replace(hour=11), 30, product_id=pid, customer_name="Pablo")  # back to back is fine
    s.create_appointment(day.replace(hour=10, minute=30), 60, customer_name="Mesa", allow_overlap=True)
    with pytest.raises(ValueError):
        s.create_appointment(day.replace(hour=12), 30, product_id=pid)  # no customer

    sale = s.charge_appointment(a1, "Efectivo")
    assert sale["items"][0]["product_id"] == pid
    appts = s.appointments(day, day + timedelta(days=1)).set_index("id")
    assert appts.loc[a1, "status"] == "completada" and appts.loc[a1, "sale_id"] == sale["id"]
    with pytest.raises(SaleError):
        s.charge_appointment(a1, "Efectivo")
    with pytest.raises(ValueError):
        s.set_appointment_status(a1, "cancelada")  # already charged
    no_product = int(appts[appts["product_id"].isna()].index[0])
    with pytest.raises(SaleError):
        s.charge_appointment(no_product, "Tarjeta")
    s.set_appointment_status(no_product, "no_presentado")
    with pytest.raises(ValueError):
        s.set_appointment_status(no_product, "inventado")


def test_demo_agenda_only_for_agenda_businesses(make_store):
    now = datetime.now()
    for business_type, expected in [("services", True), ("retail", False)]:
        s = make_store()
        s.load_preset(business_type)
        assert (not s.appointments(now, now + timedelta(days=8)).empty) is expected
        assert len(s.cash_closings()) == 5


# --------------------------------------------------------------- cash closing
def test_cash_closing(store):
    today = datetime.now().date()
    pid = product_id(store, "CAM-001")
    store.create_sale([{"product_id": pid, "quantity": 1}], "Efectivo")
    store.create_sale([{"product_id": pid, "quantity": 2}], "Tarjeta")
    cancelled = store.create_sale([{"product_id": pid, "quantity": 1}], "Efectivo")
    store.cancel_sale(cancelled["id"])
    summary = store.day_summary(today)
    assert summary["count"] == 2 and summary["cancelled"] == 1
    assert summary["cash"] == pytest.approx(39.90 * 1.21, abs=0.01)

    closing = store.close_cash(today, 100, 100 + summary["cash"] - 5, "Falta cambio")
    assert closing["expected_cash"] == pytest.approx(100 + summary["cash"], abs=0.01)
    assert closing["difference"] == pytest.approx(-5, abs=0.01)
    assert closing["breakdown"]["Tarjeta"]["count"] == 1
    with pytest.raises(ValueError):
        store.close_cash(today, 100, 100)
    with pytest.raises(ValueError):
        store.close_cash(today - timedelta(days=1), -1, 0)
    store.reopen_cash(today)
    assert store.cash_closing(today) is None
    store.close_cash(today, 0, 0)
    assert len(store.cash_closings()) == 1


# ------------------------------------------------------- upgrades & backups
def test_old_database_is_upgraded(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
        "email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', tax_id TEXT NOT NULL DEFAULT '', "
        "notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);"
        "INSERT INTO customers(name, created_at) VALUES ('Antiguo', '2026-01-01T10:00:00');"
    )
    conn.commit()
    conn.close()
    s = Store(path)
    assert s.customers().iloc[0]["address"] == ""
    s.upsert_customer({"name": "Antiguo", "address": "Calle Nueva 3"}, 1)
    assert s.customers().iloc[0]["address"] == "Calle Nueva 3"
    s.upsert_customer({"name": "Antiguo renombrado"}, 1)  # fields not given are kept
    assert s.customers().iloc[0]["address"] == "Calle Nueva 3"
    s.close()


def test_backup_carries_new_tables(store, make_store):
    sale = _completed_sale(store)
    store.create_invoice(sale["id"], {"name": "Ana", "tax_id": "1Z"})
    store.close_cash(datetime.now().date(), 50, 50)
    pid = product_id(store, "CAM-001")
    store.create_appointment(datetime.now() + timedelta(days=1), 30, product_id=pid, customer_name="Eva")
    other = make_store()
    other.restore(store.backup_bytes())
    assert len(other.invoices()) == 1 and len(other.cash_closings()) == 1
    nxt = datetime.now() + timedelta(days=2)
    assert len(other.appointments(datetime.now(), nxt)) == 1
    # Numbering keeps going after a restore.
    again = other.create_invoice(_completed_sale(other)["id"], {"name": "Ana", "tax_id": "1Z"})
    assert again["number"].endswith("0002")


# ---------------------------------------------------------- users & security
def test_users_and_login_lockout(make_store):
    from core.db import AuthError, LOCKOUT_MINUTES, MAX_FAILED_LOGINS

    s = make_store()
    with pytest.raises(ValueError):
        s.create_user("Ana", "ana", "admin", "corta")  # admin needs 8+ chars
    with pytest.raises(ValueError):
        s.create_user("Ana", "Ana López", "empleado", "4826")  # bad username
    with pytest.raises(ValueError):
        s.create_user("Ana", "ana", "empleado", "1234")  # too easy
    admin = s.create_user("Ismael", "ismael", "admin", "Segura2026")
    s.create_user("Ana", "ANA", "empleado", "4826")
    with pytest.raises(ValueError, match="Ya existe"):
        s.create_user("Otra", "ana", "empleado", "4826")
    assert "secret_hash" not in s.users().columns

    assert s.authenticate("Ana ", "4826")["role"] == "empleado"
    with pytest.raises(AuthError, match="incorrectos"):
        s.authenticate("nadie", "4826")
    now = datetime.now()
    for _ in range(MAX_FAILED_LOGINS - 1):
        with pytest.raises(AuthError, match="incorrectos"):
            s.authenticate("ana", "0000", now=now)
    with pytest.raises(AuthError, match="bloqueada"):
        s.authenticate("ana", "0000", now=now)
    with pytest.raises(AuthError, match="Demasiados"):
        s.authenticate("ana", "4826", now=now)  # even the right PIN waits
    later = now + timedelta(minutes=LOCKOUT_MINUTES + 1)
    for _ in range(MAX_FAILED_LOGINS - 1):
        with pytest.raises(AuthError, match="incorrectos"):
            s.authenticate("ana", "0000", now=later)
    with pytest.raises(AuthError, match=f"bloqueada {2 * LOCKOUT_MINUTES} minutos"):
        s.authenticate("ana", "0000", now=later)  # second lock lasts twice as long
    after = later + timedelta(minutes=2 * LOCKOUT_MINUTES + 1)
    assert s.authenticate("ana", "4826", now=after)["name"] == "Ana"

    actions = list(s.audit_log()["action"])
    assert actions.count("acceso_fallido") == 2 * MAX_FAILED_LOGINS + 1 and "acceso" in actions

    with pytest.raises(ValueError, match="administrador"):
        s.update_user(admin, role="empleado")  # last admin
    with pytest.raises(ValueError, match="administrador"):
        s.update_user(admin, active=False)
    ana = int(s.users().query("username == 'ana'").iloc[0]["id"])
    s.update_user(ana, active=False)
    with pytest.raises(AuthError, match="incorrectos"):
        s.authenticate("ana", "4826")


def test_secret_hashing():
    from core.security import hash_secret, verify_secret

    stored = hash_secret("Segura2026")
    assert stored.startswith("pbkdf2_sha256$") and "Segura2026" not in stored
    assert verify_secret("Segura2026", stored) and not verify_secret("segura2026", stored)
    assert hash_secret("Segura2026") != stored  # salted
    assert not verify_secret("x", "basura")


def test_backups_never_contain_accounts(store, make_store):
    import sqlite3
    import tempfile
    from pathlib import Path

    store.create_user("Ismael", "ismael", "admin", "Segura2026")
    data = store.backup_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "b.db"
        path.write_bytes(data)
        conn = sqlite3.connect(path)
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0
        conn.close()
    other = make_store()
    other.create_user("Otra", "otra", "admin", "Segura2026")
    other.restore(data)
    assert list(other.users()["username"]) == ["otra"]  # restoring keeps this server's team


def test_restore_ignores_unknown_columns(store):
    """A crafted backup cannot smuggle SQL through column names."""
    import sqlite3
    import tempfile
    from pathlib import Path

    data = store.backup_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "evil.db"
        path.write_bytes(data)
        conn = sqlite3.connect(path)
        conn.execute('ALTER TABLE customers ADD COLUMN "x) VALUES (1); DROP TABLE sales; --" TEXT')
        conn.execute("INSERT INTO customers(name, created_at) VALUES ('Eva', '2026-01-01T00:00:00')")
        conn.commit()
        conn.close()
        store.restore(path.read_bytes())
    assert "Eva" in set(store.customers()["name"])
    assert store.sales() is not None  # sales table still there


def test_sales_record_who_sold(store):
    sale = store.create_sale([{"product_id": product_id(store, "CAM-001"), "quantity": 1}], "Tarjeta",
                             user_name="Lucía")
    assert store.sale(sale["id"])["user_name"] == "Lucía"
    assert store.sales().iloc[0]["user_name"] == "Lucía"


def test_text_limits(store):
    with pytest.raises(ValueError, match="demasiado largo"):
        store.upsert_customer({"name": "x" * 500})
    with pytest.raises(ValueError, match="demasiado largo"):
        store.create_appointment(datetime.now() + timedelta(days=1), 30, customer_name="Eva", notes="n" * 600)


def test_csv_safe_and_secure_url():
    import pandas as pd

    from core.db import _secure_url
    from core.security import csv_safe

    df = csv_safe(pd.DataFrame({"name": ["=HYPERLINK(\"x\")", "Ana", "+34 600", "@SUM(1)"], "n": [1, -2, 3, 4]}))
    assert list(df["name"]) == ["'=HYPERLINK(\"x\")", "Ana", "'+34 600", "'@SUM(1)"]
    assert list(df["n"]) == [1, -2, 3, 4]
    assert "sslmode=require" in _secure_url("postgresql://u:p@ep-x.neon.tech/db")
    assert "sslmode=verify-full" in _secure_url("postgresql://u:p@ep-x.neon.tech/db?sslmode=verify-full")
    assert "sslmode" not in _secure_url("postgresql://u:p@localhost:5432/db")


def test_receipt_rejects_css_injection(store):
    store.save_settings({"accent_color": "red;}</style><script>alert(1)</script>"})
    sale = store.create_sale([{"product_id": product_id(store, "CAM-001"), "quantity": 1}], "Tarjeta")
    html = receipt_html(sale, store.settings())
    assert "<script>" not in html and "#1F4E79" in html


# ------------------------------------------------- promotions, points, payments
def test_promotion_rules():
    from core.pricing import apply_promotions, promotion_active

    monday_19 = datetime(2026, 10, 5, 19, 0)  # a Monday
    happy = {"name": "HH", "kind": "porcentaje", "value": 30, "scope": "categoria", "target": "Bebidas",
             "days": "0123456", "start_time": "18:00", "end_time": "20:00", "active": 1}
    assert promotion_active(happy, monday_19) and not promotion_active(happy, monday_19.replace(hour=20))
    night = {**happy, "days": "4", "start_time": "22:00", "end_time": "02:00"}  # Friday night
    assert promotion_active(night, datetime(2026, 10, 9, 23, 0))   # Friday 23:00
    assert promotion_active(night, datetime(2026, 10, 10, 1, 30))  # Saturday 01:30, still Friday's promo
    assert not promotion_active(night, datetime(2026, 10, 10, 23, 0))

    two_for_one = {"name": "2x1", "kind": "nxm", "buy": 2, "pay": 1, "scope": "producto", "target": "7",
                   "days": "0123456", "active": 1}
    ten = {"name": "-10", "kind": "porcentaje", "value": 10, "scope": "todo", "days": "0123456", "active": 1}
    lines = [{"product_id": 7, "category": "Postres", "quantity": 5, "unit_price": 6.0},
             {"product_id": 8, "category": "Bebidas", "quantity": 1, "unit_price": 3.0}]
    out = apply_promotions(lines, [two_for_one, ten, happy], monday_19)
    assert (out[0]["line_discount"], out[0]["promo_name"]) == (12.0, "2x1")  # best of 2x1 (12) and -10 % (3)
    assert (out[1]["line_discount"], out[1]["promo_name"]) == (0.9, "HH")


def test_split_evenly():
    from core.pricing import split_evenly

    assert split_evenly(100, 3) == [33.33, 33.33, 33.34]
    assert sum(split_evenly(10.01, 4)) == pytest.approx(10.01)


def test_sale_with_promotion_points_and_mixed_payment(store):
    store.save_promotion({"name": "3x2 accesorios", "kind": "nxm", "buy": 3, "pay": 2, "scope": "categoria",
                          "target": "Accesorios", "days": "0123456"})
    cid = store.upsert_customer({"name": "Eva"})
    pid = product_id(store, "CIN-005")  # 24,50 €, Accesorios
    quote = store.quote([{"product_id": pid, "quantity": 3}], customer_id=cid)
    assert quote["lines"][0]["promo_name"] == "3x2 accesorios"
    total = quote["totals"]["total"]
    assert total == pytest.approx(49.00 * 1.21, abs=0.01)
    with pytest.raises(SaleError, match="suman"):
        store.create_sale([{"product_id": pid, "quantity": 3}], customer_id=cid,
                          payments=[{"method": "Tarjeta", "amount": 10}])
    sale = store.create_sale(
        [{"product_id": pid, "quantity": 3}], customer_id=cid,
        payments=[{"method": "Efectivo", "amount": 20, "tendered": 50}, {"method": "Tarjeta", "amount": total - 20}],
    )
    assert sale["payment_method"] == "Mixto" and len(sale["payments"]) == 2
    assert sale["points_earned"] == int(total) and store.customer_points(cid) == int(total)
    summary = store.day_summary(datetime.now().date())
    assert summary["breakdown"]["Efectivo"]["total"] == 20 and summary["cash"] == 20
    lines = store.sale_lines()
    assert lines["revenue"].sum() == pytest.approx(total - sale["tax"], abs=0.01)


def test_redeem_points(store):
    cid = store.upsert_customer({"name": "Leo"})
    pid = product_id(store, "BOL-004")  # 120 €
    store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta", customer_id=cid)
    balance = store.customer_points(cid)
    assert balance == int(120 * 1.21)
    with pytest.raises(SaleError, match="a partir de"):
        store.quote([{"product_id": pid, "quantity": 1}], customer_id=cid, redeem_points=50)
    with pytest.raises(SaleError, match="solo tiene"):
        store.quote([{"product_id": pid, "quantity": 1}], customer_id=cid, redeem_points=balance + 1)
    with pytest.raises(SaleError, match="cliente"):
        store.quote([{"product_id": pid, "quantity": 1}], redeem_points=100)
    sale = store.create_sale([{"product_id": product_id(store, "CAM-001"), "quantity": 1}], "Efectivo",
                             customer_id=cid, redeem_points=100)
    assert sale["loyalty_discount"] > 0
    assert sale["total"] == pytest.approx(39.90 * 1.21 - 1.00, abs=0.02)  # 100 points = 1 €
    after = store.customer_points(cid)
    assert after == balance - 100 + sale["points_earned"]
    store.cancel_sale(sale["id"])
    assert store.customer_points(cid) == balance  # cancelling gives the points back and removes the earned ones


def test_promotion_validation(store):
    with pytest.raises(ValueError):
        store.save_promotion({"name": "x", "kind": "nxm", "buy": 2, "pay": 2, "scope": "todo", "days": "0"})
    with pytest.raises(ValueError):
        store.save_promotion({"name": "x", "kind": "porcentaje", "value": 150, "scope": "todo", "days": "0"})
    with pytest.raises(ValueError):
        store.save_promotion({"name": "x", "kind": "porcentaje", "value": 10, "scope": "categoria", "days": "0"})
    with pytest.raises(ValueError):
        store.save_promotion({"name": "x", "kind": "porcentaje", "value": 10, "scope": "todo", "days": "0",
                              "start_time": "25:00", "end_time": "26:00"})
    pid = store.save_promotion({"name": "ok", "kind": "porcentaje", "value": 10, "scope": "todo", "days": "06"})
    store.set_promotion_active(pid, False)
    assert store.promotions().iloc[0]["active"] == 0
    store.delete_promotion(pid)
    assert store.promotions().empty


# ------------------------------------------------------------ refunds
def test_partial_refunds_add_up_exactly(store):
    cid = store.upsert_customer({"name": "Eva"})
    cam, cin = product_id(store, "CAM-001"), product_id(store, "CIN-005")
    stock_before = int(store.products().set_index("id").loc[cam, "stock"])
    sale = store.create_sale([{"product_id": cam, "quantity": 3}, {"product_id": cin, "quantity": 1}], "Efectivo",
                             customer_id=cid, discount_pct=10)
    cam_item = next(i for i in sale["items"] if i["product_id"] == cam)
    cin_item = next(i for i in sale["items"] if i["product_id"] == cin)
    with pytest.raises(ValueError, match="motivo"):
        store.create_refund(sale["id"], {cam_item["id"]: 1}, "Efectivo", "")
    with pytest.raises(SaleError, match="quedan 3"):
        store.create_refund(sale["id"], {cam_item["id"]: 4}, "Efectivo", "Talla")

    points_before = store.customer_points(cid)
    first = store.create_refund(sale["id"], {cam_item["id"]: 1}, "Efectivo", "Talla equivocada", user_name="Ana")
    assert first["number"].startswith("DEV-") and first["credit_note"] is None
    assert first["total"] == pytest.approx(39.90 * 0.9 * 1.21, abs=0.02)
    assert int(store.products().set_index("id").loc[cam, "stock"]) == stock_before - 3 + 1
    assert store.customer_points(cid) < points_before
    assert [i["remaining"] for i in store.returnable(sale["id"])] == [2, 1]
    assert store.day_summary(datetime.now().date())["cash"] == pytest.approx(sale["total"] - first["total"])

    with pytest.raises(SaleError, match="devoluciones"):
        store.cancel_sale(sale["id"])
    second = store.create_refund(sale["id"], {cam_item["id"]: 2, cin_item["id"]: 1}, "Tarjeta", "No le gusta")
    assert first["total"] + second["total"] == pytest.approx(sale["total"], abs=0.001)
    assert store.sale_lines()["revenue"].sum() == pytest.approx(0, abs=0.001)
    with pytest.raises(SaleError):
        store.create_refund(sale["id"], {cin_item["id"]: 1}, "Tarjeta", "Otra vez")


def test_refund_of_invoiced_sale_issues_corrective_invoice(store):
    from core.pdfs import credit_note_pdf

    sale = store.create_sale([{"product_id": product_id(store, "BOL-004"), "quantity": 1}], "Tarjeta")
    store.create_invoice(sale["id"], {"name": "Norte S.L.", "tax_id": "B12345678"})
    refund = store.create_refund(sale["id"], {sale["items"][0]["id"]: 1}, "Tarjeta", "Defecto de fábrica")
    assert refund["credit_note"]["number"] == f"FACR-{datetime.now().year}-0001"
    note = store.credit_note(refund["id"])
    assert note["invoice"]["number"].startswith("FAC-")
    assert credit_note_pdf(note, store.settings()).startswith(b"%PDF")
    assert len(store.refunds()) == 1 and store.refunds().iloc[0]["credit_note"] == refund["credit_note"]["number"]


def test_kpis_are_net_of_refunds(store):
    pid = product_id(store, "CAM-001")
    sale = store.create_sale([{"product_id": pid, "quantity": 2}], "Tarjeta")
    store.create_refund(sale["id"], {sale["items"][0]["id"]: 1}, "Tarjeta", "Talla")
    start, end, prev_start = automation.period_bounds(7)
    k = automation.kpis(store.sales(), store.sale_lines(), start, end, prev_start, store.refunds())
    assert k["revenue"] == pytest.approx(sale["total"] / 2, abs=0.01)


# ------------------------------------------------------------ tables & orders
def test_orders_split_payment_and_kitchen(make_store):
    s = make_store()
    s.load_preset("restaurant", with_demo_sales=False)
    for pid in s.promotions()["id"]:
        s.delete_promotion(int(pid))
    mesa = s.save_table("Mesa 1", "Sala", 4)
    other = s.save_table("Mesa 2", "Sala", 2)
    order_id = s.open_order(mesa, guests=3, opened_by="Marta")
    assert s.open_order(mesa, opened_by="Diego") == order_id  # second waiter joins the same order
    products = s.products().set_index("sku")
    beer, steak = int(products.loc["BEB-007", "id"]), int(products.loc["PRI-004", "id"])
    s.add_order_item(order_id, beer, 2, added_by="Marta")
    s.add_order_item(order_id, beer, 2, added_by="Diego")  # merges with the line still pending
    steak_line = s.add_order_item(order_id, steak, 1, "poco hecho", added_by="Diego")
    order = s.order(order_id)
    assert [(i["name"], i["quantity"]) for i in order["items"]] == [
        ("Vino de la casa (copa)", 4), ("Solomillo a la brasa", 1)]

    s.advance_kitchen(steak_line)
    assert s.kitchen_queue().set_index("id").loc[steak_line, "kitchen"] == "preparando"
    with pytest.raises(ValueError, match="encargado"):
        s.change_order_item(steak_line, -1)
    s.change_order_item(steak_line, +1)  # adding more is always fine

    beer_line = order["items"][0]["id"]
    first = s.charge_order(order_id, {beer_line: 2}, payment_method="Efectivo", user_name="Marta")
    assert [(i["name"], i["quantity"]) for i in first["items"]] == [("Vino de la casa (copa)", 2)]
    left = s.order(order_id)
    assert left["status"] == "abierta" and sum(i["quantity"] for i in left["unpaid"]) == 2 + 2
    with pytest.raises(ValueError, match="cobrada"):
        s.cancel_order(order_id)
    s.open_order(other, opened_by="Sara")
    with pytest.raises(ValueError, match="ocupada"):
        s.move_order(order_id, other)
    s.charge_order(order_id, payment_method="Tarjeta", user_name="Marta")
    assert s.order(order_id)["status"] == "cobrada"
    import pandas as pd
    assert pd.isna(s.dining_tables().set_index("id").loc[mesa, "order_id"])  # the table is free again
    assert len(s.sales()) == 2


def test_order_without_table_and_cancel(make_store):
    s = make_store()
    s.load_preset("restaurant", with_demo_sales=False)
    with pytest.raises(ValueError):
        s.open_order(None)
    order_id = s.open_order(None, label="Para llevar · Ana")
    s.add_order_item(order_id, int(s.products().iloc[0]["id"]))
    s.cancel_order(order_id)
    with pytest.raises(ValueError, match="abierta"):
        s.add_order_item(order_id, int(s.products().iloc[0]["id"]))


# --------------------------------------------- suppliers, purchases, expenses
def test_purchase_receive_updates_stock_cost_and_expenses(store):
    from core.pdfs import purchase_order_pdf

    supplier = store.save_supplier({"name": "Textiles Norte", "email": "p@x.example.com"})
    pid = product_id(store, "CAM-001")  # cost 16, stock 25
    po = store.create_purchase(supplier, [{"product_id": pid, "quantity": 25, "unit_cost": 20}], created_by="Ana")
    order = store.purchase(po)
    assert order["number"] == f"PED-{datetime.now().year}-0001" and order["total"] == 500
    assert purchase_order_pdf(order, store.settings()).startswith(b"%PDF")
    store.set_purchase_status(po, "enviado")
    item = order["items"][0]
    store.receive_purchase(po, {item["id"]: 25}, received_by="Ana", method="Transferencia")
    product = store.products().set_index("id").loc[pid]
    assert int(product["stock"]) == 50 and float(product["cost"]) == pytest.approx(18.0)  # (25·16 + 25·20) / 50
    expense = store.expenses().iloc[0]
    assert (expense["category"], expense["amount"]) == ("Compras a proveedores", 500)
    with pytest.raises(ValueError):
        store.receive_purchase(po)  # already received
    with pytest.raises(ValueError):
        store.create_purchase(supplier, [{"product_id": pid, "quantity": 0, "unit_cost": 1}])


def test_drafts_from_reorder_suggestions(store):
    import pandas as pd

    a = store.save_supplier({"name": "A"})
    b = store.save_supplier({"name": "B"})
    store.set_product_supplier(product_id(store, "CAM-001"), a)
    store.set_product_supplier(product_id(store, "CIN-005"), b)
    numbers = store.draft_purchases(pd.DataFrame({"sku": ["CAM-001", "CIN-005", "VEL-006"],
                                                  "suggested_qty": [5, 3, 2]}))
    assert len(numbers) == 3  # supplier A, supplier B and one without supplier
    assert set(store.purchases()["status"]) == {"borrador"}


def test_recurring_expenses_and_profit(store):
    from datetime import date

    store.save_recurring("Alquiler", "Local", 900, 31)
    store.save_recurring("Suministros", "Luz", 100, 10)
    created = store.apply_recurring(until=date(2026, 3, 31), since=date(2026, 1, 1))
    assert created == 6  # 2 a month for 3 months; day 31 falls on 28 Feb
    assert store.apply_recurring(until=date(2026, 3, 31), since=date(2026, 1, 1)) == 0  # idempotent
    feb = store.expenses(date(2026, 2, 1), date(2026, 3, 1))
    assert sorted(feb["day"].dt.day) == [10, 28]

    store.add_expense(date(2026, 3, 5), "Compras a proveedores", "Mercancía", 300)
    store.create_sale([{"product_id": product_id(store, "CAM-001"), "quantity": 10}], "Tarjeta",
                      when=datetime(2026, 3, 15, 12, 0))
    p = store.profit(date(2026, 3, 1), date(2026, 4, 1))
    assert p["net_sales"] == pytest.approx(399.0) and p["cogs"] == pytest.approx(160.0)
    assert p["opex"] == pytest.approx(1000.0) and p["purchases"] == pytest.approx(300.0)
    assert p["net"] == pytest.approx(399 - 160 - 1000)
    with pytest.raises(ValueError):
        store.add_expense(date(2026, 3, 5), "Inventada", "x", 10)



# ------------------------------------------------------------------ intelligence
def test_abc_classifies_by_margin(store):
    from core import intelligence
    now = datetime.now()
    for sku, qty in [("ZAP-003", 10), ("CAM-001", 3), ("CIN-005", 1)]:
        store.create_sale([{"product_id": product_id(store, sku), "quantity": qty}], "Tarjeta",
                          when=now - timedelta(days=1))
    abc = intelligence.abc_analysis(store.products(), store.sale_lines(start=now - timedelta(days=30)))
    klass = dict(zip(abc["name"], abc["abc"]))
    assert abc.iloc[0]["name"] == "Zapatilla urbana" and klass["Zapatilla urbana"] == "A"
    assert klass["Camisa de lino"] == "B"  # 80 % of the margin is already covered by the first product
    assert klass["Vela aromática"] == "C"  # active but unsold
    assert abc["share"].sum() == pytest.approx(100, abs=0.2)
    summary = intelligence.abc_summary(abc)
    assert sum(v["count"] for v in summary.values()) == len(store.products())


def test_price_suggestions_and_apply(store):
    from core import intelligence
    assert intelligence.round_price(7.01) == 7.05 and intelligence.round_price(12.31) == 12.4
    assert intelligence.round_price(150.2) == 151.0 and intelligence.round_price(7.05) == 7.05
    sug = intelligence.price_suggestions(store.products(), 60)
    assert set(sug["name"]) == {"Camisa de lino", "Pantalón chino", "Zapatilla urbana", "Bolso de piel"}
    row = sug.set_index("name").loc["Camisa de lino"]
    assert row["suggested"] == 40.0 and row["new_margin_pct"] >= 60  # 16 / 0.4
    with pytest.raises(ValueError):
        intelligence.price_suggestions(store.products(), 0)
    assert store.set_prices({int(row["id"]): row["suggested"]}) == 1
    assert store.products().set_index("sku").loc["CAM-001", "price"] == 40.0
    with pytest.raises(ValueError):
        store.set_prices({int(row["id"]): 0})


def test_smart_alerts(store):
    now = datetime.now()
    shirt, bag = product_id(store, "CAM-001"), product_id(store, "BOL-004")
    # Busy week two weeks ago, quiet this week: sales drop.
    for d in range(8, 14):
        store.create_sale([{"product_id": shirt, "quantity": 1}], "Tarjeta", when=now - timedelta(days=d),
                          user_name="Ana")
    store.create_sale([{"product_id": shirt, "quantity": 1}], "Tarjeta", when=now - timedelta(days=1),
                      user_name="Ana")
    # The bag keeps selling and runs out.
    store.create_sale([{"product_id": bag, "quantity": 2}], "Tarjeta", when=now - timedelta(days=9), user_name="Ana")
    # Pablo's sales get voided and returned again and again.
    for i in range(4):
        sale = store.create_sale([{"product_id": shirt, "quantity": 1}], "Efectivo", when=now - timedelta(days=3, hours=i),
                                 user_name="Pablo")
        if i % 2:
            store.cancel_sale(sale["id"], by="Encargada")
        else:
            item = store.returnable(sale["id"])[0]
            store.create_refund(sale["id"], {item["id"]: 1}, "Efectivo", "Defectuoso", user_name="Encargada")
    store.close_cash((now - timedelta(days=2)).date(), 100, 50)  # 50 short
    table = store.save_table("Terraza 1", "Terraza", 4)
    order = store.open_order(table, 2, "Ana")
    with store.db.tx() as cur:
        cur.execute("UPDATE orders SET opened_at = ? WHERE id = ?",
                    ((now - timedelta(hours=5)).isoformat(timespec="seconds"), order))

    alerts = store.alerts(now)
    by_area = {a["area"]: a for a in alerts}
    assert by_area["Ventas"]["level"] == "alta"
    assert by_area["Caja"]["level"] == "alta" and "50,00" in by_area["Caja"]["detail"]
    assert "Bolso de piel" in by_area["Stock"]["detail"]
    assert by_area["Equipo"]["title"].endswith("Pablo")
    assert "Terraza 1" in by_area["Mesas"]["detail"]
    assert "Catálogo" in by_area
    assert [a["level"] for a in alerts] == sorted((a["level"] for a in alerts), key=["alta", "media", "baja"].index)
    voided = store.sales()
    assert set(voided[voided["status"] == "anulada"]["voided_by"]) == {"Encargada"}


def test_no_alerts_without_activity(store):
    assert store.alerts() == []


def test_weekly_report_and_pdf(store):
    from core.pdfs import weekly_report_pdf
    from core.store_intel import week_start
    start = week_start(datetime.now().date()) - timedelta(days=7)
    shirt = product_id(store, "CAM-001")
    store.create_sale([{"product_id": shirt, "quantity": 2}], "Tarjeta", when=start + timedelta(days=1, hours=10),
                      user_name="Ana")
    store.create_sale([{"product_id": shirt, "quantity": 1}], "Tarjeta", when=start - timedelta(days=3), user_name="Ana")
    report = store.weekly_report(start)
    n = report["numbers"]
    assert n["cur"]["count"] == 1 and n["prev"]["count"] == 1
    assert n["delta"]["revenue"] == pytest.approx(100)
    assert n["by_day"][1][2] == 1 and len(n["by_day"]) == 7
    assert report["complete"]
    store.save_recurring("Alquiler", "Local", 520, 1)
    report = store.weekly_report(start)
    assert report["profit"]["fixed"] == pytest.approx(120)  # 520 a month is 120 a week
    assert report["profit"]["net"] == pytest.approx(n["cur"]["margin"] - 120)
    pdf = weekly_report_pdf(report, store.settings())
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000


@pytest.fixture
def madrid():
    from core import clock
    clock.set_timezone("Europe/Madrid")
    yield clock
    clock.set_timezone(clock.DEFAULT_TIMEZONE)


def test_clock_follows_business_timezone_not_server(madrid):
    from zoneinfo import ZoneInfo
    expected = datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
    assert abs((madrid.now() - expected).total_seconds()) < 5
    canary = datetime.now(ZoneInfo("Atlantic/Canary")).replace(tzinfo=None)
    madrid.set_timezone("Atlantic/Canary")
    assert abs((madrid.now() - canary).total_seconds()) < 5
    assert madrid.timezone_name() == "Atlantic/Canary"


def test_sale_is_stamped_with_business_local_time(store, madrid):
    from zoneinfo import ZoneInfo
    sale = store.create_sale([{"product_id": product_id(store, "CAM-001"), "quantity": 1}], "Tarjeta")
    local = datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
    assert abs((datetime.fromisoformat(sale["created_at"]) - local).total_seconds()) < 60


def test_invalid_timezone_is_rejected_and_never_breaks_the_clock(store, madrid):
    with pytest.raises(ValueError):
        store.save_settings({"timezone": "Marte/Olympus"})
    madrid.set_timezone("Marte/Olympus")
    assert madrid.timezone_name() == madrid.DEFAULT_TIMEZONE
    store.save_settings({"timezone": "Atlantic/Canary"})
    assert store.settings()["timezone"] == "Atlantic/Canary"



def _sell(store, n=1):
    return store.create_sale([{"product_id": product_id(store, "CAM-001"), "quantity": n}], "Tarjeta")


def test_real_fiscal_records_cannot_be_wiped_or_replaced(store, make_store):
    from core.db import FiscalDataError
    sale = _sell(store)
    store.create_invoice(sale["id"], {"name": "Cliente SL", "tax_id": "B12345678"})
    backup = make_store()
    backup.load_preset("services", with_demo_sales=False)
    assert not store.is_demo() and store.has_fiscal_records() and not store.can_replace_data()
    with pytest.raises(FiscalDataError):
        store.reset()
    with pytest.raises(FiscalDataError):
        store.load_preset("restaurant")
    with pytest.raises(FiscalDataError):
        store.restore(backup.backup_bytes())
    assert len(store.sales()) == 1 and len(store.invoices()) == 1


def test_business_without_sales_can_still_load_a_template(store):
    assert store.can_replace_data()
    store.load_preset("restaurant", with_demo_sales=False)
    assert not store.is_demo()


def test_demo_data_is_disposable_and_real_numbering_starts_at_one(make_store):
    s = make_store()
    s.load_preset("services")
    assert s.is_demo() and not s.sales().empty and s.can_replace_data()
    s.reset()
    assert not s.is_demo() and s.is_empty()
    s.load_preset("retail", with_demo_sales=False)
    year = datetime.now().year
    assert _sell(s)["number"] == f"VTA-{year}-00001"


def test_numbering_has_no_yearly_limit(store):
    year = datetime.now().year
    first = _sell(store)
    with store.db.tx() as cur:  # an existing series that already reached 99,999 tickets
        cur.execute("UPDATE sales SET number = ? WHERE id = ?", (f"VTA-{year}-99999", first["id"]))
        cur.execute("DELETE FROM counters")
    assert [_sell(store)["number"] for _ in range(2)] == [f"VTA-{year}-100000", f"VTA-{year}-100001"]
    invoice_for = lambda: store.create_invoice(_sell(store)["id"], {"name": "Cliente SL", "tax_id": "B1"})["number"]
    first_invoice = invoice_for()
    with store.db.tx() as cur:
        cur.execute("UPDATE invoices SET number = ? WHERE number = ?", (f"FAC-{year}-9999", first_invoice))
        cur.execute("DELETE FROM counters WHERE series LIKE 'FAC-%'")
    assert [invoice_for() for _ in range(2)] == [f"FAC-{year}-10000", f"FAC-{year}-10001"]


def test_simultaneous_charges_all_succeed_with_unique_numbers(store):
    import threading
    pid = product_id(store, "CAM-001")
    store.adjust_stock(pid, 100)
    barrier, numbers, errors = threading.Barrier(8), [], []

    def charge():
        barrier.wait()
        try:
            numbers.append(store.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")["number"])
        except Exception as exc:  # noqa: BLE001 - the test reports any failure
            errors.append(exc)

    threads = [threading.Thread(target=charge) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and len(set(numbers)) == 8
    assert sorted(int(n.rsplit("-", 1)[1]) for n in numbers) == list(range(1, 9))


def test_prefix_with_like_wildcards_is_numbered_exactly(store):
    store.save_settings({"invoice_prefix": "T_1"})
    year = datetime.now().year
    assert [_sell(store)["number"] for _ in range(2)] == [f"T_1-{year}-00001", f"T_1-{year}-00002"]
