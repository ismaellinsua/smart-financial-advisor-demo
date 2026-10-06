"""Two people acting on the same ticket or table at the same moment, on a real PostgreSQL: one wins, the other is
refused or sees the result. (SQLite runs one transaction at a time, so it cannot race.) A pause is slipped into the
middle of each operation to make the overlap certain."""

import threading
import time

import pytest

from conftest import PG_URL
from core.db import SaleError, Store

pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def target(make_store):
    if make_store.targets.backend != "postgres":
        pytest.skip("only PostgreSQL runs transactions side by side")
    return make_store.targets.new()


@pytest.fixture(params=["postgres"])
def make_store(request, tmp_path):
    from conftest import Targets

    targets = Targets(request.param, tmp_path)
    stores = []

    def factory(t=None):
        s = Store(t or targets.new())
        stores.append(s)
        return s

    factory.targets = targets
    yield factory
    for s in stores:
        s.close()
    targets.cleanup()


def at_once(*calls):
    """Run each call in its own thread and connection; return what each one did ('ok' or the error)."""
    out = [None] * len(calls)

    def run(i, call):
        try:
            call()
            out[i] = "ok"
        except (SaleError, ValueError) as exc:
            out[i] = str(exc)

    threads = [threading.Thread(target=run, args=(i, c)) for i, c in enumerate(calls)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return out


def slow(monkeypatch, cls, name):
    original = getattr(cls, name)
    is_static = isinstance(cls.__dict__.get(name), staticmethod)

    def paused(*args, **kwargs):
        time.sleep(0.4)
        return original(*args, **kwargs)

    monkeypatch.setattr(cls, name, staticmethod(paused) if is_static else paused)


def stock_of(store, pid):
    return int(store.products().set_index("id").loc[pid, "stock"])


def test_the_same_ticket_is_returned_only_once(make_store, target, monkeypatch):
    import core.store_refunds as refunds

    shop = make_store(target)
    shop.load_preset("retail", with_demo_sales=False)
    pid = int(shop.products().iloc[0]["id"])
    sale = shop.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")
    item = shop.sale(sale["id"])["items"][0]["id"]
    before = stock_of(shop, pid)
    slow(monkeypatch, refunds.RefundsMixin, "_line_net")
    a, b = make_store(target), make_store(target)
    results = at_once(lambda: a.create_refund(sale["id"], {item: 1}, "Tarjeta", "devolución"),
                      lambda: b.create_refund(sale["id"], {item: 1}, "Tarjeta", "devolución"))
    assert sorted(r == "ok" for r in results) == [False, True], results
    assert len(shop.sale_refunds(sale["id"])) == 1 and stock_of(shop, pid) == before + 1


def test_a_sale_is_voided_only_once(make_store, target, monkeypatch):
    import core.store_locations as locations

    shop = make_store(target)
    shop.load_preset("retail", with_demo_sales=False)
    pid = int(shop.products().iloc[1]["id"])
    sale = shop.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")
    before = stock_of(shop, pid)
    slow(monkeypatch, locations.LocationsMixin, "_move_stock")
    a, b = make_store(target), make_store(target)
    results = at_once(lambda: a.cancel_sale(sale["id"]), lambda: b.cancel_sale(sale["id"]))
    assert sorted(r == "ok" for r in results) == [False, True], results
    assert stock_of(shop, pid) == before + 1


def test_a_void_and_a_return_of_the_same_sale_do_not_both_happen(make_store, target, monkeypatch):
    import core.store_locations as locations

    shop = make_store(target)
    shop.load_preset("retail", with_demo_sales=False)
    pid = int(shop.products().iloc[2]["id"])
    sale = shop.create_sale([{"product_id": pid, "quantity": 1}], "Tarjeta")
    item = shop.sale(sale["id"])["items"][0]["id"]
    before = stock_of(shop, pid)
    slow(monkeypatch, locations.LocationsMixin, "_move_stock")
    a, b = make_store(target), make_store(target)
    results = at_once(lambda: a.cancel_sale(sale["id"]),
                      lambda: b.create_refund(sale["id"], {item: 1}, "Tarjeta", "devolución"))
    assert sorted(r == "ok" for r in results) == [False, True], results
    assert stock_of(shop, pid) == before + 1


def test_a_table_is_charged_only_once(make_store, target, monkeypatch):
    shop = make_store(target)
    shop.load_preset("restaurant", with_demo_sales=False)
    table = shop.save_table("Mesa 1", "Sala", 4)
    order = shop.open_order(table)
    shop.add_order_item(order, int(shop.products().iloc[0]["id"]), 2)
    slow(monkeypatch, Store, "_insert_sale")
    a, b = make_store(target), make_store(target)
    results = at_once(lambda: a.charge_order(order, payment_method="Tarjeta"),
                      lambda: b.charge_order(order, payment_method="Tarjeta"))
    assert sorted(r == "ok" for r in results) == [False, True], results
    assert len(shop.sales()) == 1
