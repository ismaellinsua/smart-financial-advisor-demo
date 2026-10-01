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
    assert s.authenticate("ana", "4826", now=now + timedelta(minutes=LOCKOUT_MINUTES + 1))["name"] == "Ana"

    actions = list(s.audit_log()["action"])
    assert actions.count("acceso_fallido") == MAX_FAILED_LOGINS + 1 and "acceso" in actions

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
