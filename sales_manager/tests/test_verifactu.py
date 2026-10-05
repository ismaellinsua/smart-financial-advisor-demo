"""VERI*FACTU billing register: AEAT fingerprint, chaining over every kind of invoice and immutability."""

import pytest

from core.db import FiscalDataError
from core.verifactu import alta_hash, anulacion_hash, verify_chain


@pytest.fixture
def store(make_store):
    s = make_store()
    s.load_preset("retail", with_demo_sales=False)
    s.save_settings({"tax_id": "B12345678", "address": "Calle Mayor 1, 28001 Madrid"})
    for pid in s.promotions()["id"]:
        s.delete_promotion(int(pid))
    return s


def _sale(store, quantity=1):
    df = store.products()
    pid = int(df.loc[df["sku"] == "CAM-001", "id"].iloc[0])
    return store.create_sale([{"product_id": pid, "quantity": quantity}], "Tarjeta")


def test_fingerprint_matches_the_aeat_example():
    # Example from the AEAT specification «Detalle de las especificaciones técnicas para generación de la huella».
    assert alta_hash("89890001K", "12345678/G33", "01-01-2024", "F1", "12.35", "123.45", "",
                     "2024-01-01T19:20:30+01:00") == \
        "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60"
    # Cancellations hash their own fields: changing the previous fingerprint changes the result.
    one = anulacion_hash("89890001K", "12345678/G33", "01-01-2024", "A" * 64, "2024-01-01T19:20:40+01:00")
    assert len(one) == 64 and one == one.upper()
    assert one != anulacion_hash("89890001K", "12345678/G33", "01-01-2024", "B" * 64, "2024-01-01T19:20:40+01:00")


def test_nothing_is_recorded_until_turned_on_or_in_demo(store, make_store):
    _sale(store)
    assert store.billing_records().empty
    demo = make_store()
    demo.load_preset("retail", with_demo_sales=True)
    demo.save_settings({"tax_id": "B12345678"})
    with pytest.raises(ValueError):
        demo.enable_billing_register()
    demo.save_settings({"verifactu": "si"})  # even if forced, demo data is never registered
    _sale(demo)
    assert demo.billing_records().empty
    store.save_settings({"tax_id": ""})
    with pytest.raises(ValueError):
        store.enable_billing_register()


def test_every_invoice_kind_is_chained(store):
    store.enable_billing_register("admin")
    ticket = _sale(store, quantity=2)
    invoiced = _sale(store, quantity=2)
    invoice = store.create_invoice(invoiced["id"], {"name": "Norte S.L.", "tax_id": "B87654321", "address": "C/ 1"})
    voided = _sale(store)
    store.cancel_sale(voided["id"])
    ticket_item = store.sale(ticket["id"])["items"][0]["id"]
    invoice_item = store.sale(invoiced["id"])["items"][0]["id"]
    refund = store.create_refund(ticket["id"], {ticket_item: 1}, "Efectivo", "No le queda bien")
    note = store.create_refund(invoiced["id"], {invoice_item: 1}, "Efectivo", "Defectuoso")

    records = store.billing_records()
    assert list(records["invoice_type"]) == ["F2", "F2", "F3", "F2", "", "R5", "R1"]
    kinds = [(r.kind, r.invoice_type, r.number) for r in records.itertuples()]
    assert kinds[0] == ("alta", "F2", ticket["number"])
    assert ("alta", "F3", invoice["number"]) in kinds
    assert ("anulacion", "", voided["number"]) in kinds
    assert ("alta", "R5", refund["number"]) in kinds
    assert ("alta", "R1", note["credit_note"]["number"]) in kinds
    r5 = records[records["invoice_type"] == "R5"].iloc[0]
    assert r5["amount_total"].startswith("-") and float(r5["amount_total"]) == -float(refund["total"])
    f2 = records.iloc[0]
    assert f2["amount_total"] == f"{float(ticket['total']):.2f}" and f2["issuer_tax_id"] == "B12345678"
    # Each record points to the previous one and the first starts the chain.
    assert records.iloc[0]["previous_hash"] == ""
    assert all(records["previous_hash"].iloc[1:].values == records["hash"].iloc[:-1].values)
    assert store.verify_billing_chain() == {"ok": True, "checked": len(records), "broken_at": None, "reason": ""}


def test_records_cannot_be_changed_deleted_or_wiped(store):
    store.enable_billing_register()
    _sale(store)
    for sql in ("UPDATE billing_records SET amount_total = '0.00'", "DELETE FROM billing_records"):
        with pytest.raises(Exception, match="no se pueden modificar"):
            with store.db.tx() as cur:
                cur.execute(sql)
    assert len(store.billing_records()) == 1
    store.save_settings({"demo_mode": "si"})  # not even after pretending to be a demonstration
    assert not store.can_replace_data()
    with pytest.raises(FiscalDataError):
        store.reset()


def test_a_tampered_record_breaks_the_chain():
    rows = []
    previous = ""
    for i, total in enumerate(["10.00", "20.00", "30.00"], 1):
        row = {"id": i, "kind": "alta", "invoice_type": "F2", "number": f"VTA-{i}", "issued_on": "04-10-2026",
               "issuer_tax_id": "B12345678", "tax_total": "1.00", "amount_total": total,
               "generated_at": f"2026-10-04T10:00:0{i}+02:00", "previous_hash": previous}
        row["hash"] = alta_hash(row["issuer_tax_id"], row["number"], row["issued_on"], "F2", "1.00", total,
                                previous, row["generated_at"])
        rows.append(row)
        previous = row["hash"]
    assert verify_chain(rows)["ok"]
    rows[1]["amount_total"] = "2.00"
    assert verify_chain(rows) == {"ok": False, "checked": 1, "broken_at": 2, "reason": "un registro ha sido alterado"}
    rows[1]["amount_total"] = "20.00"
    del rows[1]
    assert verify_chain(rows)["reason"] == "la cadena está rota"


def test_backup_keeps_the_register(store, make_store):
    store.enable_billing_register()
    _sale(store)
    copy = make_store()
    copy.restore(store.backup_bytes())
    assert list(copy.billing_records()["hash"]) == list(store.billing_records()["hash"])
    assert copy.verify_billing_chain()["ok"]


def test_qr_address_follows_the_aeat_format():
    from core.verifactu import qr_png, qr_url

    record = {"issuer_tax_id": "89890001K", "number": "12345678/G33", "issued_on": "01-01-2024",
              "amount_total": "241.40"}
    assert qr_url(record) == ("https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQRNoVerifactu"
                              "?nif=89890001K&numserie=12345678%2FG33&fecha=01-01-2024&importe=241.40")
    assert qr_url(record, "pruebas").startswith("https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQRNoVerifactu?")
    assert qr_png(qr_url(record)).startswith(b"\x89PNG")


def test_documents_carry_the_qr_only_with_a_billing_record(store):
    from core.pdfs import credit_note_pdf, invoice_pdf
    from core.receipts import receipt_html, refund_receipt_html

    before = _sale(store)
    assert "QR tributario" not in receipt_html(store.sale(before["id"]), store.settings())
    store.enable_billing_register()
    ticket = _sale(store, quantity=2)
    sale = store.sale(ticket["id"])
    assert sale["billing"]["number"] == ticket["number"]
    assert "QR tributario" in receipt_html(sale, store.settings())
    item = sale["items"][0]["id"]
    refund = store.refund(store.create_refund(ticket["id"], {item: 1}, "Efectivo", "Talla")["id"])
    assert refund["billing"]["invoice_type"] == "R5"
    assert "QR tributario" in refund_receipt_html(refund, store.settings())

    invoiced = _sale(store)
    invoice = store.create_invoice(invoiced["id"], {"name": "Norte S.L.", "tax_id": "B87654321", "address": "C/ 1"})
    assert invoice["billing"]["invoice_type"] == "F3"
    assert invoice_pdf(invoice, store.settings()).startswith(b"%PDF")
    note_refund = store.create_refund(invoiced["id"], {store.sale(invoiced["id"])["items"][0]["id"]: 1},
                                      "Efectivo", "Defectuoso")
    note = store.credit_note(note_refund["id"])
    assert note["billing"]["invoice_type"] == "R1"
    assert credit_note_pdf(note, store.settings()).startswith(b"%PDF")
    assert store.refund(note_refund["id"])["billing"] is None  # its QR goes on the corrective invoice
