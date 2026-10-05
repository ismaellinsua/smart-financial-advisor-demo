"""Several locations: each one sells from its own stock and counts its own cash, the total stays consistent, a
business with one place notices nothing, and databases from before keep their closings."""

import json
import sqlite3
from datetime import date, datetime

import pytest

from core.db import SaleError, Store

DAY = date(2026, 10, 5)
AT = datetime(2026, 10, 5, 12, 0)


@pytest.fixture
def shop(make_store):
    s = make_store()
    s.load_preset("retail", with_demo_sales=False)
    s.save_settings({"business_name": "Tienda Sol", "address": "Calle Mayor 1", "demo_mode": "no"})
    return s


def tracked(store) -> dict:
    """A stocked product with 20 more units, so every test has enough to move around."""
    p = store.products()
    pid = int(p[p["track_stock"] == 1].iloc[0]["id"])
    store.adjust_stock(pid, 20, "Prueba")
    return store.products().set_index("id").loc[pid].to_dict() | {"id": pid}


def stock_sum_matches(store) -> bool:
    by_loc = store.stock_by_location()
    names = [loc["name"] for loc in store.locations(include_inactive=True)]
    return bool((by_loc[names].sum(axis=1) == by_loc["Total"]).all())


def test_one_location_works_as_always(shop):
    assert shop.locations() == [] and not shop.multi_location() and shop.stock_at(None) == {}
    p = tracked(shop)
    shop.create_sale([{"product_id": p["id"], "quantity": 1}], when=AT)
    assert shop.sales().iloc[0]["location_id"] is None or pd_isna(shop.sales().iloc[0]["location_id"])
    shop.close_cash(DAY, 100, 100)
    assert shop.cash_closing(DAY)["counted_cash"] == 100


def pd_isna(value) -> bool:
    import pandas as pd

    return pd.isna(value)


def test_second_location_turns_the_first_into_principal_with_all_the_stock(shop):
    p = tracked(shop)
    shop.create_sale([{"product_id": p["id"], "quantity": 1}], when=AT)
    shop.close_cash(DAY, 100, 100)
    centro = shop.add_location("Centro", "Plaza 2")
    main = shop.locations()[0]
    assert [loc["name"] for loc in shop.locations()] == ["Principal", "Centro"] and shop.multi_location()
    assert main["address"] == "Calle Mayor 1"  # taken from the business data
    assert shop.stock_at(main["id"])[p["id"]] == p["stock"] - 1 and shop.stock_at(centro).get(p["id"], 0) == 0
    assert shop.sales().iloc[0]["location_id"] == main["id"]  # the past belongs to the main location
    assert shop.cash_closing(DAY, main["id"])["counted_cash"] == 100 and shop.cash_closing(DAY, centro) is None
    assert stock_sum_matches(shop)
    with pytest.raises(ValueError):
        shop.add_location("centro")
    with pytest.raises(ValueError):
        shop.add_location("")


def test_each_location_sells_its_own_stock(shop):
    p = tracked(shop)
    centro = shop.add_location("Centro")
    main = shop.locations()[0]["id"]
    with pytest.raises(SaleError, match="en este local"):
        shop.create_sale([{"product_id": p["id"], "quantity": 1}], when=AT, location_id=centro)
    shop.transfer_stock(p["id"], 3, main, centro, "Ana")
    sale = shop.create_sale([{"product_id": p["id"], "quantity": 2}], when=AT, location_id=centro)
    assert shop.stock_at(centro)[p["id"]] == 1 and shop.stock_at(main)[p["id"]] == p["stock"] - 3
    assert int(shop.products().set_index("id").loc[p["id"], "stock"]) == p["stock"] - 2
    shop.cancel_sale(sale["id"], by="Ana")  # units go back to the location that sold them
    assert shop.stock_at(centro)[p["id"]] == 3
    assert stock_sum_matches(shop)
    moves = shop.stock_moves()
    assert {"Traspaso a Centro", "Traspaso desde Principal"} <= set(moves["reason"])


def test_transfers_are_checked(shop):
    p = tracked(shop)
    centro = shop.add_location("Centro")
    main = shop.locations()[0]["id"]
    for args in ((p["id"], 0, main, centro), (p["id"], 1, main, main), (p["id"], p["stock"] + 1, main, centro)):
        with pytest.raises(ValueError):
            shop.transfer_stock(*args)
    service = shop.upsert_product({"sku": "SRV-1", "name": "Arreglo", "price": 10, "cost": 0, "stock": 0,
                                   "min_stock": 0, "track_stock": 0, "active": 1})
    with pytest.raises(ValueError, match="control de stock"):
        shop.transfer_stock(service, 1, main, centro)


def test_adjustments_purchases_and_refunds_land_in_the_right_location(shop):
    p = tracked(shop)
    centro = shop.add_location("Centro")
    shop.adjust_stock(p["id"], 5, "Recuento", "Ana", location_id=centro)
    with pytest.raises(ValueError):
        shop.adjust_stock(p["id"], -6, "Rotura", "Ana", location_id=centro)
    po = shop.create_purchase(None, [{"product_id": p["id"], "quantity": 4, "unit_cost": 1.0}], location_id=centro)
    shop.receive_purchase(po, received_by="Ana")
    assert shop.stock_at(centro)[p["id"]] == 9
    sale = shop.create_sale([{"product_id": p["id"], "quantity": 2}], when=AT, location_id=centro)
    item = shop.sale(sale["id"])["items"][0]
    shop.create_refund(sale["id"], {item["id"]: 1}, "Efectivo", "No le vale", "Ana", when=AT)
    assert shop.stock_at(centro)[p["id"]] == 8
    new = shop.upsert_product({"sku": "NEW-1", "name": "Nuevo", "price": 5, "cost": 1, "stock": 7, "min_stock": 0,
                               "track_stock": 1, "active": 1})
    assert shop.stock_at(shop.locations()[0]["id"])[new] == 7
    assert stock_sum_matches(shop)


def test_each_location_counts_its_own_cash(shop):
    p = tracked(shop)
    centro = shop.add_location("Centro")
    main = shop.locations()[0]["id"]
    shop.transfer_stock(p["id"], 2, main, centro)
    shop.create_sale([{"product_id": p["id"], "quantity": 1}], "Efectivo", when=AT, location_id=main)
    shop.create_sale([{"product_id": p["id"], "quantity": 2}], "Efectivo", when=AT, location_id=centro)
    price = float(p["price"])
    assert shop.day_summary(DAY, main)["cash"] == pytest.approx(price)
    assert shop.day_summary(DAY, centro)["cash"] == pytest.approx(price * 2)
    assert shop.day_summary(DAY)["cash"] == pytest.approx(price * 3)  # the whole business
    shop.close_cash(DAY, 50, 50 + price, location_id=main)
    shop.close_cash(DAY, 50, 50 + price * 2, location_id=centro)  # same day, other till: allowed
    with pytest.raises(ValueError, match="ya está cerrada"):
        shop.close_cash(DAY, 50, 50, location_id=centro)
    assert shop.cash_closing(DAY, centro)["difference"] == 0
    shop.reopen_cash(DAY, centro)
    assert shop.cash_closing(DAY, centro) is None and shop.cash_closing(DAY, main) is not None
    assert len(shop.sales(location_id=centro)) == 1


def test_closing_a_location_needs_its_stock_moved_first(shop):
    p = tracked(shop)
    centro = shop.add_location("Centro")
    main = shop.locations()[0]["id"]
    shop.transfer_stock(p["id"], 1, main, centro)
    with pytest.raises(ValueError, match="traspásalas"):
        shop.update_location(centro, "Centro", active=False)
    with pytest.raises(ValueError, match="principal"):
        shop.update_location(main, "Principal", active=False)
    shop.transfer_stock(p["id"], 1, centro, main)
    shop.update_location(centro, "Centro (cerrado)", active=False)
    assert [loc["name"] for loc in shop.locations()] == ["Principal"]


def test_offline_till_of_a_location_sells_from_that_location(shop):
    p = tracked(shop)
    centro = shop.add_location("Centro")
    main = shop.locations()[0]["id"]
    shop.transfer_stock(p["id"], 3, main, centro)
    pkg = json.loads(shop.offline_package(2, centro))
    assert pkg["location"] == "Centro" and pkg["location_id"] == centro
    item = next(x for x in pkg["products"] if x["id"] == p["id"])
    sale = {"id": "0f8c2a3e-1111-4a5b-9c1d-123456789abc", "number": f"{pkg['series']}000001",
            "created_at": "2026-10-05T11:00:00", "payment_method": "Efectivo", "total": item["price"] * 2,
            "items": [{"product_id": p["id"], "quantity": 2, "unit_price": item["price"], "tax_rate": item["vat"]}]}
    payload = {"kind": "nirkana-ventas", "version": 1, "key": pkg["key"], "device": 2, "location_id": centro,
               "sales": [sale]}
    result = shop.import_offline_sales(json.dumps(payload).encode(), now=datetime(2026, 10, 5, 18, 0))
    assert result["imported"] == 1 and shop.stock_at(centro)[p["id"]] == 1
    assert shop.sales(location_id=centro).iloc[0]["number"] == "VTA-SC2-000001"


def test_old_sqlite_databases_keep_their_closings_and_allow_one_per_location(tmp_path):
    path = tmp_path / "old.db"
    Store(str(path)).close()
    conn = sqlite3.connect(path)  # rebuild cash_closings as it was before locations: day UNIQUE
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'cash_closings'").fetchone()[0]
    cols = [r[1] for r in conn.execute("PRAGMA table_info(cash_closings)")]
    conn.execute("DROP INDEX IF EXISTS cash_closings_day_location")
    conn.execute("DROP TABLE schema_state")  # older versions had no setup fingerprint
    conn.execute("ALTER TABLE cash_closings RENAME TO cc")
    conn.execute(sql.replace("day TEXT NOT NULL", "day TEXT UNIQUE NOT NULL"))
    conn.execute("DROP TABLE cc")
    conn.execute(f"INSERT INTO cash_closings({', '.join(c for c in cols if c != 'id')}) VALUES "
                 f"({', '.join('?' * (len(cols) - 1))})",
                 [{"day": "2026-10-01", "breakdown": "{}", "notes": "", "closed_at": "2026-10-01T21:00:00",
                   "closed_by": "", "location_id": None}.get(c, 0) for c in cols if c != "id"])
    conn.commit()
    conn.close()
    store = Store(str(path))
    try:
        assert store.cash_closing(date(2026, 10, 1)) is not None
        centro = store.add_location("Centro")
        store.close_cash(DAY, 0, 0)
        store.close_cash(DAY, 0, 0, location_id=centro)
        assert len(store.cash_closings()) == 3
    finally:
        store.close()
