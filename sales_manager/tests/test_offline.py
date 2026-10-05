"""Selling without internet: the catalogue file for the offline till, and importing its sales back exactly once."""

import json
import uuid
from datetime import datetime

import pytest

from core.store_offline import OfflineImportError

NOW = datetime(2026, 10, 5, 18, 0)


@pytest.fixture
def shop(make_store):
    s = make_store()
    s.load_preset("retail", with_demo_sales=False)
    s.save_settings({"business_name": "Tienda Sol", "tax_id": "B12345678", "demo_mode": "no"})
    return s


def package(store, device=1) -> dict:
    return json.loads(store.offline_package(device))


def sale(pkg, n, lines, method="Efectivo", when="2026-10-05T12:30:00", total=None):
    """A sale as the offline till writes it: price charged (VAT included) and VAT rate per line."""
    items = [{"product_id": p["id"], "name": p["name"], "quantity": q, "unit_price": p["price"], "tax_rate": p["vat"]}
             for p, q in lines]
    return {"id": str(uuid.uuid4()), "number": f"{pkg['series']}{n:06d}", "created_at": when, "payment_method": method,
            "total": total if total is not None else round(sum(p["price"] * q for p, q in lines), 2), "items": items}


def sales_file(pkg, sales) -> bytes:
    return json.dumps({"kind": "nirkana-ventas", "version": 1, "key": pkg["key"], "device": pkg["device"],
                       "sales": sales}).encode()


def test_catalogue_file_has_what_a_ticket_needs_and_nothing_personal(shop):
    shop.upsert_customer({"name": "Lucía Privada", "email": "lucia@example.com", "phone": "600111222"})
    pkg = package(shop, 3)
    assert pkg["kind"] == "nirkana-caja" and pkg["series"] == "VTA-SC3-" and pkg["next_number"] == 1
    assert pkg["business"]["tax_id"] == "B12345678" and len(pkg["products"]) == len(shop.products())
    assert {"id", "name", "category", "price", "vat"} == set(pkg["products"][0])
    assert "Lucía" not in json.dumps(pkg) and "600111222" not in json.dumps(pkg)
    assert package(shop, 3)["key"] == pkg["key"]  # stable for this business
    with pytest.raises(ValueError):
        shop.offline_package(10)


def test_sales_are_imported_once_with_the_price_charged(shop):
    pkg = package(shop)
    a, b = pkg["products"][0], pkg["products"][1]
    stock_before = shop.products().set_index("id")["stock"]
    sales = [sale(pkg, 1, [(a, 2), (b, 1)]), sale(pkg, 2, [(b, 3)], method="Tarjeta", when="2026-10-05T13:05:00")]
    shop.update_product(a["id"], {**shop.products().set_index("id").loc[a["id"]].to_dict(), "price": 999.0})

    result = shop.import_offline_sales(sales_file(pkg, sales), "Marta", now=NOW)
    assert (result["imported"], result["repeated"], result["rejected"]) == (2, 0, 0)
    assert result["total"] == round(a["price"] * 2 + b["price"] * 4, 2)
    again = shop.import_offline_sales(sales_file(pkg, sales), "Marta", now=NOW)
    assert (again["imported"], again["repeated"]) == (0, 2)

    imported = shop.sales(start=datetime(2026, 10, 5), include_cancelled=True)
    first = imported[imported["number"] == "VTA-SC1-000001"].iloc[0]
    assert first["total"] == pytest.approx(a["price"] * 2 + b["price"])  # what the customer paid, not today's 999
    assert first["created_at"] == pd_ts("2026-10-05T12:30:00") and first["payment_method"] == "Efectivo"
    assert "Caja sin conexión 1" in first["user_name"]
    stock = shop.products().set_index("id")["stock"]
    assert stock[a["id"]] == stock_before[a["id"]] - 2 and stock[b["id"]] == stock_before[b["id"]] - 4
    assert shop.day_summary(datetime(2026, 10, 5).date())["count"] == 2
    assert package(shop)["next_number"] == 3  # a reinstalled till carries on after what was imported


def pd_ts(value):
    import pandas as pd

    return pd.Timestamp(value)


def test_a_file_from_another_business_or_not_a_sales_file_is_refused(shop, make_store):
    other = make_store()
    other.load_preset("retail", with_demo_sales=False)
    pkg = package(other)
    with pytest.raises(OfflineImportError, match="otro negocio"):
        shop.import_offline_sales(sales_file(pkg, [sale(pkg, 1, [(pkg["products"][0], 1)])]), now=NOW)
    for junk in (b"no es json", b"{}", json.dumps({"kind": "nirkana-ventas", "sales": "x"}).encode()):
        with pytest.raises(OfflineImportError):
            shop.import_offline_sales(junk, now=NOW)


def test_wrong_sales_are_reported_and_the_rest_imported(shop):
    pkg = package(shop)
    p = pkg["products"][0]
    good = sale(pkg, 1, [(p, 1)])
    bad_total = sale(pkg, 2, [(p, 1)], total=p["price"] + 5)
    future = sale(pkg, 3, [(p, 1)], when="2026-10-09T10:00:00")
    other_device = {**sale(pkg, 4, [(p, 1)]), "number": "VTA-SC2-000004"}
    bad_vat = sale(pkg, 5, [(p, 1)])
    bad_vat["items"][0]["tax_rate"] = 7
    missing = sale(pkg, 6, [({**p, "id": 99999}, 1)])
    result = shop.import_offline_sales(sales_file(pkg, [good, bad_total, future, other_device, bad_vat, missing]),
                                       now=NOW)
    assert (result["imported"], result["rejected"]) == (1, 5)
    joined = " ".join(result["notes"])
    assert "no cuadra" in joined and "reloj" in joined and "número de ticket" in joined and "IVA" in joined
    assert "ya no existe" in joined


def test_a_reused_number_is_flagged_not_skipped(shop):
    pkg = package(shop)
    p = pkg["products"][0]
    shop.import_offline_sales(sales_file(pkg, [sale(pkg, 1, [(p, 1)])]), now=NOW)
    reused = sale(pkg, 1, [(p, 2)])  # a till reinstalled without a fresh catalogue starts again at 1
    result = shop.import_offline_sales(sales_file(pkg, [reused]), now=NOW)
    assert result["rejected"] == 1 and "ya existe" in result["notes"][0]


def test_overselling_offline_is_reported_and_stock_stays_at_zero(shop):
    pkg = package(shop)
    p = pkg["products"][0]
    have = int(shop.products().set_index("id").loc[p["id"], "stock"])
    result = shop.import_offline_sales(sales_file(pkg, [sale(pkg, 1, [(p, have + 3)])]), now=NOW)
    assert result["imported"] == 1 and "revisa el stock" in result["notes"][0]
    assert shop.products().set_index("id").loc[p["id"], "stock"] == 0


def test_vat_is_broken_down_like_any_other_sale(shop):
    pkg = package(shop)
    p = pkg["products"][0]
    shop.import_offline_sales(sales_file(pkg, [sale(pkg, 1, [(p, 3)])]), now=NOW)
    items = shop._frame("SELECT net_amount, tax_amount, gross_amount, tax_rate FROM sale_items")
    gross = round(p["price"] * 3, 2)
    assert items.iloc[0]["gross_amount"] == pytest.approx(gross)
    assert items.iloc[0]["net_amount"] == pytest.approx(round(gross / (1 + p["vat"] / 100), 2))
    assert items.iloc[0]["net_amount"] + items.iloc[0]["tax_amount"] == pytest.approx(gross)
