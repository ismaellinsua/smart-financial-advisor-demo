"""Selling without internet: the catalogue goes to the offline till as a file, and its sales come back the same way.

The offline till (docs/caja, installed on a phone or tablet from the website) needs no connection at all. It sells
from the catalogue file the business downloaded here, numbers its tickets in its own series (e.g. VTA-SC1-000001,
one per device, so two tills never collide) and keeps the sales on the device until they are imported back.

Importing is idempotent (each offline sale carries its own id), checks that the file belongs to this business and
that every total adds up, and keeps the price that was actually charged even if the catalogue changed since.
"""

import json
import re
import secrets
from datetime import datetime, timedelta

from . import clock
from .presets import PAYMENT_METHODS
from .pricing import apply_promotions, compute_totals

PACKAGE_VERSION = 1
MAX_SALES_PER_FILE = 5000
MAX_LINES_PER_SALE = 200
DEVICES = range(1, 10)
_NUMBER = re.compile(r"^[A-Z0-9]{1,10}-SC[1-9]-\d{6}$")


class OfflineImportError(ValueError):
    """The file can't be imported at all (wrong business, not a sales file…)."""


class OfflineMixin:
    def _offline_key(self, cur) -> str:
        """A random id of this business's data, so a file from another business is never imported by mistake."""
        key = self._settings(cur).get("offline_key", "")
        if not key:
            key = secrets.token_hex(8)
            self._save_settings(cur, {"offline_key": key})
        return key

    def offline_package(self, device: int, location_id: int | None = None) -> bytes:
        """The file the offline till loads: business data for the ticket, active catalogue and the device's series."""
        device = int(device)
        if device not in DEVICES:
            raise ValueError("Elige un número de caja del 1 al 9.")
        with self.db.tx() as cur:
            settings = self._settings(cur)
            key = self._offline_key(cur)
            location_id = self._location_or_main(cur, location_id)
            location = cur.execute("SELECT name, address, phone FROM locations WHERE id = ?",
                                   (location_id,)).fetchone() if location_id else None
            products = cur.execute(
                "SELECT id, name, category, price, tax_rate FROM products WHERE active = 1 ORDER BY category, name"
            ).fetchall()
            default_rate = float(settings.get("tax_rate") or 0)
            prefix = (settings.get("invoice_prefix", "VTA").strip() or "VTA").upper()
            series = f"{re.sub(r'[^A-Z0-9]', '', prefix)[:10] or 'VTA'}-SC{device}-"
            used = [r["number"][len(series):] for r in cur.execute(
                "SELECT number FROM sales WHERE substr(number, 1, ?) = ?", (len(series), series)).fetchall()]
        # A till reinstalled (or a new phone for the same number) continues after what was already imported.
        next_number = max((int(n) for n in used if n.isdigit()), default=0) + 1
        package = {
            "kind": "nirkana-caja", "version": PACKAGE_VERSION, "key": key, "device": device,
            "location_id": location_id, "location": location["name"] if location else "",
            "series": series, "next_number": next_number,
            "generated_at": clock.now().isoformat(timespec="seconds"),
            "business": {**{k: settings.get(k, "") for k in ("business_name", "tax_id", "address", "phone",
                                                             "receipt_footer", "currency")},
                         **({"address": location["address"] or settings.get("address", ""),
                             "phone": location["phone"] or settings.get("phone", "")} if location else {})},
            "payment_methods": [m for m in PAYMENT_METHODS if m != "Transferencia"],
            "products": [{"id": p["id"], "name": p["name"], "category": p["category"], "price": float(p["price"]),
                          "vat": float(p["tax_rate"] if p["tax_rate"] is not None else default_rate)}
                         for p in products],
        }
        return json.dumps(package, ensure_ascii=False, indent=1).encode()

    def import_offline_sales(self, data: bytes, user_name: str = "", now: datetime | None = None) -> dict:
        """Save the sales of an offline till file. Returns counts and readable notes for what needs a look."""
        try:
            payload = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            raise OfflineImportError("El archivo no es una exportación de la caja sin conexión.") from None
        if not isinstance(payload, dict) or payload.get("kind") != "nirkana-ventas":
            raise OfflineImportError("El archivo no es una exportación de la caja sin conexión.")
        sales = payload.get("sales")
        if not isinstance(sales, list) or len(sales) > MAX_SALES_PER_FILE:
            raise OfflineImportError("El archivo no tiene una lista de ventas válida.")
        now = now or clock.now()
        result = {"imported": 0, "repeated": 0, "rejected": 0, "total": 0.0, "notes": []}
        with self.db.tx() as cur:
            if payload.get("key") != self._offline_key(cur):
                raise OfflineImportError("Este archivo es de la caja de otro negocio (o de otra base de datos).")
        for sale in sales:
            try:
                outcome = self._import_offline_sale(sale, payload.get("device"), user_name, now,
                                                    payload.get("location_id"))
            except ValueError as exc:
                result["rejected"] += 1
                number = sale.get("number") if isinstance(sale, dict) else None
                result["notes"].append(f"{number or 'Venta sin número'}: {exc}")
                continue
            if outcome is None:
                result["repeated"] += 1
                continue
            result["imported"] += 1
            result["total"] = round(result["total"] + outcome["total"], 2)
            result["notes"].extend(outcome["notes"])
        if result["imported"]:
            with self.db.tx() as cur:
                self._audit(cur, user_name, "ventas_sin_conexion",
                            f"{result['imported']} ventas importadas de la caja {payload.get('device')}")
        return result

    def _import_offline_sale(self, sale, device, user_name: str, now: datetime, location_id=None) -> dict | None:
        if not isinstance(sale, dict):
            raise ValueError("formato no válido.")
        offline_id = str(sale.get("id") or "")
        number = str(sale.get("number") or "")
        if not re.fullmatch(r"[0-9a-fA-F-]{16,40}", offline_id):
            raise ValueError("falta el identificador de la venta.")
        if not _NUMBER.fullmatch(number) or f"-SC{device}-" not in number:
            raise ValueError("número de ticket no válido.")
        try:
            when = datetime.fromisoformat(str(sale.get("created_at"))).replace(tzinfo=None, microsecond=0)
        except ValueError:
            raise ValueError("fecha no válida.") from None
        if when > now + timedelta(hours=1) or when < now - timedelta(days=400):
            raise ValueError(f"la fecha {when:%d/%m/%Y %H:%M} no es posible (¿reloj del dispositivo mal puesto?).")
        method = str(sale.get("payment_method") or "")
        if method not in PAYMENT_METHODS:
            raise ValueError(f"forma de pago no válida ({method or '—'}).")
        items = sale.get("items")
        if not isinstance(items, list) or not 0 < len(items) <= MAX_LINES_PER_SALE:
            raise ValueError("no tiene líneas.")
        notes = []
        with self.db.tx() as cur:
            location_id = self._location_or_main(cur, location_id) if location_id else self._main_location(cur)
            if cur.execute("SELECT 1 FROM sales WHERE offline_id = ?", (offline_id,)).fetchone():
                return None  # already imported (the same file, or an older export, sent twice)
            if cur.execute("SELECT 1 FROM sales WHERE number = ?", (number,)).fetchone():
                raise ValueError("ese número de ticket ya existe en otra venta (¿se reinstaló la caja sin cargar un "
                                 "catálogo nuevo?). Revísala a mano.")
            lines = []
            for item in items:
                try:
                    pid, qty = int(item["product_id"]), int(item["quantity"])
                    price, vat = round(float(item["unit_price"]), 2), float(item["tax_rate"])
                except (KeyError, TypeError, ValueError):
                    raise ValueError("una línea no es válida.") from None
                if qty <= 0 or qty > 10_000 or price < 0 or vat not in (0, 4, 5, 10, 21):
                    raise ValueError("una línea tiene cantidad, precio o IVA no válidos.")
                product = cur.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
                if product is None:
                    raise ValueError("incluye un producto que ya no existe en el catálogo.")
                lines.append((product, {"product_id": pid, "category": product["category"], "quantity": qty,
                                        "unit_price": price, "tax_rate": vat}))
            totals = compute_totals(apply_promotions([line for _, line in lines], [], when))
            if abs(totals["total"] - float(sale.get("total") or 0)) > 0.011:
                raise ValueError(f"el total no cuadra ({sale.get('total')} en la caja, {totals['total']:.2f} sumando "
                                 "las líneas).")
            row = cur.execute(
                "INSERT INTO sales(number, created_at, payment_method, discount_pct, tax_rate, subtotal, discount, "
                "tax, total, user_name, offline_id, location_id) VALUES (?, ?, ?, 0, ?, ?, 0, ?, ?, ?, ?, ?) "
                "RETURNING id",
                (number, when.isoformat(timespec="seconds"), method, float(lines[0][1]["tax_rate"]),
                 totals["subtotal"], totals["tax"], totals["total"],
                 (f"Caja sin conexión {device}" + (f" · {user_name}" if user_name else ""))[:120], offline_id,
                 location_id),
            ).fetchone()
            sale_id = row["id"]
            for (p, line), net, vat_amount, gross in zip(lines, totals["net_amounts"], totals["tax_amounts"],
                                                          totals["gross_amounts"]):
                cur.execute(
                    "INSERT INTO sale_items(sale_id, product_id, name, quantity, unit_price, unit_cost, line_discount, "
                    "promo_name, net_amount, tax_rate, tax_amount, gross_amount) "
                    "VALUES (?, ?, ?, ?, ?, ?, 0, '', ?, ?, ?, ?)",
                    (sale_id, p["id"], p["name"], line["quantity"], line["unit_price"], p["cost"], net,
                     line["tax_rate"], vat_amount, gross),
                )
                if p["track_stock"]:
                    # Already sold: the stock goes down even if the app thought there was less; never below zero.
                    have = max(self._stock_at(cur, p["id"], location_id), 0)
                    if have < line["quantity"]:
                        notes.append(f"{number}: revisa el stock de «{p['name']}» (se vendieron más de los que había).")
                    self._move_stock(cur, p["id"], -min(have, line["quantity"]), location_id)
            if totals["total"] > 0:
                cur.execute("INSERT INTO sale_payments(sale_id, method, amount, tendered) VALUES (?, ?, ?, 0)",
                            (sale_id, method, totals["total"]))
            self._register_issue(cur, "F2", number, when, totals["tax"], totals["total"], totals["taxes"], "sale",
                                 sale_id)
        return {"total": totals["total"], "notes": notes}
