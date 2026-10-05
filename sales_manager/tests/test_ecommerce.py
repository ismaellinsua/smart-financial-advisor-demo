"""Online shop by files: the catalogue in each platform's CSV, and its orders imported once as sales."""

import csv
import io
from datetime import datetime

import pytest

from core.store_ecommerce import ShopImportError, _money, parse_orders

NOW = datetime(2026, 10, 5, 18, 0)


@pytest.fixture
def shop(make_store):
    s = make_store()
    s.load_preset("ecommerce", with_demo_sales=False)
    s.save_settings({"business_name": "TecnoShop", "demo_mode": "no"})
    return s


def product(store, sku):
    return store.products().set_index("sku").loc[sku]


def shopify_csv(rows: list[dict]) -> bytes:
    """Shopify's «Orders → Export»: one row per product; order fields only on the first row of each order."""
    cols = ["Name", "Email", "Financial Status", "Paid at", "Currency", "Subtotal", "Shipping", "Taxes", "Total",
            "Discount Code", "Discount Amount", "Created at", "Lineitem quantity", "Lineitem name", "Lineitem price",
            "Lineitem sku", "Billing Name", "Billing Address1"]
    out = io.StringIO()
    writer = csv.DictWriter(out, cols)
    writer.writeheader()
    for r in rows:
        writer.writerow({c: r.get(c, "") for c in cols})
    return out.getvalue().encode()


def test_amounts_and_dates_in_any_usual_format():
    assert [_money(x) for x in ("1.234,50", "1234.50", "12,5 €", "", "59.90")] == \
        [_money("1234.50"), _money("1234.5"), _money("12.50"), _money("0"), _money("59.9")]


def test_catalogue_for_shopify_and_woocommerce(shop):
    shopify = list(csv.DictReader(io.StringIO(shop.shop_catalog_csv("shopify").decode("utf-8-sig"))))
    woo = list(csv.DictReader(io.StringIO(shop.shop_catalog_csv("woocommerce").decode("utf-8-sig"))))
    assert len(shopify) == len(woo) == len(shop.products())
    a = next(r for r in shopify if r["Variant SKU"] == "ELE-001")
    assert a["Title"] == "Auriculares inalámbricos" and a["Variant Price"] == "59.90" and a["Handle"] == \
        "auriculares-inalambricos-ele-001"
    assert a["Variant Inventory Qty"] == str(int(product(shop, "ELE-001")["stock"]))
    shipping = next(r for r in woo if r["SKU"] == "ENV-006")
    assert shipping["Manage stock?"] == "0" and shipping["Stock"] == "" and shipping["Regular price"] == "6.90"
    with pytest.raises(ValueError):
        shop.shop_catalog_csv("amazon")


def test_shopify_orders_become_sales_once_with_discount_and_shipping(shop):
    ship = int(product(shop, "ENV-006")["id"])
    stock = int(product(shop, "ELE-001")["stock"])
    data = shopify_csv([
        {"Name": "#1001", "Email": "lucia@example.com", "Financial Status": "paid", "Shipping": "6.90",
         "Total": "132.60", "Discount Amount": "10.00", "Created at": "2026-10-04 12:30:00 +0200",
         "Lineitem quantity": "2", "Lineitem name": "Auriculares inalámbricos", "Lineitem price": "59.90",
         "Lineitem sku": "ELE-001", "Billing Name": "Lucía Privada"},
        {"Name": "#1001", "Lineitem quantity": "1", "Lineitem name": "Funda protectora", "Lineitem price": "15.90",
         "Lineitem sku": "ACC-003"},
        {"Name": "#1002", "Financial Status": "pending", "Total": "15.90", "Created at": "2026-10-04 13:00:00 +0200",
         "Lineitem quantity": "1", "Lineitem price": "15.90", "Lineitem sku": "ACC-003"},
        {"Name": "#1003", "Financial Status": "paid", "Total": "24.90", "Created at": "2026-10-04 14:00:00 +0200",
         "Lineitem quantity": "1", "Lineitem name": "Algo de otra tienda", "Lineitem price": "24.90",
         "Lineitem sku": "NO-EXISTE"},
    ])
    result = shop.import_shop_orders(data, "Tarjeta", shipping_product_id=ship, user_name="Ana", now=NOW)
    assert (result["platform"], result["imported"], result["skipped"], result["rejected"]) == ("shopify", 1, 1, 1)
    assert result["total"] == pytest.approx(132.60)
    sale = shop.sales().set_index("number").loc["WEB-1001"]
    assert sale["total"] == pytest.approx(132.60) and sale["created_at"] == datetime(2026, 10, 4, 12, 30)
    assert sale["user_name"] == "Tienda online · Ana" and sale["discount"] == pytest.approx(10.0)
    items = shop.sale(int(sale["id"]))["items"]
    assert sum(i["gross_amount"] for i in items) == pytest.approx(132.60)
    assert sum(i["line_discount"] for i in items) == pytest.approx(10.0)
    assert int(product(shop, "ELE-001")["stock"]) == stock - 2
    assert "Lucía" not in str(shop.sales().to_dict())  # customers' personal data is not imported

    again = shop.import_shop_orders(data, "Tarjeta", shipping_product_id=ship, now=NOW)
    assert (again["imported"], again["repeated"]) == (0, 1)


def test_shipping_without_a_product_is_reported_and_left_out(shop):
    data = shopify_csv([{"Name": "#2001", "Financial Status": "paid", "Shipping": "6.90", "Total": "22.80",
                         "Created at": "2026-10-04 12:30:00 +0200", "Lineitem quantity": "1",
                         "Lineitem price": "15.90", "Lineitem sku": "ACC-003"}])
    result = shop.import_shop_orders(data, now=NOW)
    assert result["imported"] == 1 and "envío" in result["notes"][0]
    assert shop.sales().iloc[0]["total"] == pytest.approx(15.90)


def test_prices_without_vat_are_caught_by_the_total(shop):
    data = shopify_csv([{"Name": "#3001", "Financial Status": "paid", "Total": "60.50",
                         "Created at": "2026-10-04 12:30:00 +0200", "Lineitem quantity": "1",
                         "Lineitem price": "50.00", "Lineitem sku": "ACC-003"}])
    result = shop.import_shop_orders(data, now=NOW)
    assert result["rejected"] == 1 and "sin IVA" in result["notes"][0]


def test_generic_csv_for_woocommerce_and_other_shops(shop):
    data = ("pedido;fecha;sku;cantidad;precio;envio;total\n"
            "W-55;03/10/2026 10:15;ACC-004;2;24,90;;49,80\n"
            "W-56;03/10/2026 11:00;ACC-003;1;15,90;;15,90\n").encode("latin-1")
    platform, orders = parse_orders(data)
    assert platform == "web" and [o["number"] for o in orders] == ["W-55", "W-56"]
    result = shop.import_shop_orders(data, "Bizum", now=NOW)
    assert result["imported"] == 2 and result["total"] == pytest.approx(65.70)
    assert set(shop.sales()["payment_method"]) == {"Bizum"}


def test_unknown_files_and_methods_are_refused(shop):
    with pytest.raises(ShopImportError):
        shop.import_shop_orders(b"a,b\n1,2\n", now=NOW)
    with pytest.raises(ShopImportError):
        shop.import_shop_orders(b"", now=NOW)
    with pytest.raises(ValueError):
        shop.import_shop_orders(shopify_csv([]), "Cheque", now=NOW)


def test_orders_go_to_the_chosen_location(shop):
    web = shop.add_location("Almacén web")
    main = shop.locations()[0]["id"]
    p = product(shop, "ACC-003")
    shop.transfer_stock(int(p["id"]), 5, main, web)
    data = "pedido,fecha,sku,cantidad,precio\nW-1,2026-10-03,ACC-003,2,15.90\n".encode()
    shop.import_shop_orders(data, location_id=web, now=NOW)
    assert shop.stock_at(web)[int(p["id"])] == 3
    assert len(shop.sales(location_id=web)) == 1
