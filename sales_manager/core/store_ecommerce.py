"""Online shop (Shopify, WooCommerce or any other) by files: no accounts, keys or monthly fees.

- Catalogue out: the products, prices (VAT included) and stock as the CSV each platform imports
  (Shopify «Products → Import», WooCommerce «Products → Import»).
- Orders in: Shopify's own «Orders → Export» CSV, or a simple generic CSV any shop or plugin can produce
  (order, date, sku, quantity, price…). Each order becomes a sale with the price actually charged, its stock goes
  down at the chosen location, and importing the same file again never duplicates anything. Customers' personal
  data in the file (names, emails, addresses) is not read.
"""

import csv
import io
import re
from datetime import datetime, timedelta
from decimal import Decimal

from . import clock
from .pricing import allocate, compute_totals
from .presets import PAYMENT_METHODS

MAX_ORDERS = 5000
PAID = {"paid", "partially_refunded", "pagado", "completado", "completed", "processing", ""}

SHOPIFY_PRODUCT_COLUMNS = [
    "Handle", "Title", "Body (HTML)", "Vendor", "Type", "Tags", "Published", "Option1 Name", "Option1 Value",
    "Variant SKU", "Variant Inventory Tracker", "Variant Inventory Qty", "Variant Inventory Policy",
    "Variant Fulfillment Service", "Variant Price", "Variant Requires Shipping", "Variant Taxable", "Status",
]
WOO_PRODUCT_COLUMNS = ["Type", "SKU", "Name", "Published", "Visibility in catalog", "Tax status", "In stock?",
                       "Manage stock?", "Stock", "Regular price", "Categories"]


class ShopImportError(ValueError):
    """The file can't be read as an orders export at all."""


def _handle(text: str) -> str:
    """Shopify's product handle: lowercase words joined by hyphens, no accents."""
    table = str.maketrans("áéíóúüñçàèìòù", "aeiouuncaeiou")
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower().translate(table)).strip("-") or "producto"


def _money(text) -> Decimal:
    """«1.234,50», «1234.50», «12,5 €» → Decimal."""
    value = re.sub(r"[^\d,.\-]", "", str(text or "")).strip()
    if not value:
        return Decimal("0")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".") if value.rfind(",") > value.rfind(".") else value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        return Decimal(value).quantize(Decimal("0.01"))
    except ArithmeticError:
        raise ValueError(f"importe no válido «{text}»") from None


def _date(text: str) -> datetime:
    text = str(text or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            when = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if when.tzinfo is not None:  # Shopify writes the shop's offset: convert to the business's wall time
            when = when.astimezone(clock.now_aware().tzinfo).replace(tzinfo=None)
        return when.replace(microsecond=0)
    raise ValueError(f"fecha no válida «{text}»")


def _read(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    sample = text[:4096]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delimiter))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in rows]


def parse_orders(data: bytes) -> tuple[str, list[dict]]:
    """Group the rows of an orders export into orders. Returns (platform, orders)."""
    rows = _read(data)
    if not rows:
        raise ShopImportError("El archivo está vacío.")
    columns = set(rows[0])
    if {"name", "lineitem quantity", "lineitem price", "lineitem sku"} <= columns:
        platform, keys = "shopify", {"order": "name", "date": "created at", "sku": "lineitem sku",
                                     "qty": "lineitem quantity", "price": "lineitem price", "status": "financial status",
                                     "discount": "discount amount", "shipping": "shipping", "total": "total",
                                     "item": "lineitem name"}
    elif {"pedido", "sku", "cantidad", "precio"} <= columns:
        platform, keys = "web", {"order": "pedido", "date": "fecha", "sku": "sku", "qty": "cantidad", "price": "precio",
                                 "status": "estado", "discount": "descuento", "shipping": "envio", "total": "total",
                                 "item": "producto"}
    else:
        raise ShopImportError("No reconocemos el archivo. Usa la exportación de pedidos de Shopify o la plantilla "
                              "genérica (pedido, fecha, sku, cantidad, precio).")
    orders: dict[str, dict] = {}
    for row in rows:
        number = row.get(keys["order"], "").lstrip("#").strip()
        if not number:
            continue
        order = orders.setdefault(number, {"number": number, "lines": [], "date": "", "status": "", "discount": "",
                                           "shipping": "", "total": ""})
        for field in ("date", "status", "discount", "shipping", "total"):
            if not order[field] and row.get(keys[field]):
                order[field] = row[keys[field]]  # Shopify writes order fields on the first row only
        if row.get(keys["qty"]):
            order["lines"].append({"sku": row.get(keys["sku"], ""), "qty": row[keys["qty"]],
                                   "price": row.get(keys["price"], ""), "name": row.get(keys["item"], "")})
    if len(orders) > MAX_ORDERS:
        raise ShopImportError(f"Demasiados pedidos en un archivo (máximo {MAX_ORDERS}). Expórtalos por fechas.")
    return platform, list(orders.values())


class EcommerceMixin:
    # ------------------------------------------------------------------ catalogue out
    def shop_catalog_csv(self, platform: str, location_id: int | None = None) -> bytes:
        """Active catalogue for Shopify or WooCommerce: price with VAT, stock (at a location, if given)."""
        products = self.products()
        if location_id is not None and self.multi_location():
            here = self.stock_at(location_id)
            products["stock"] = products["id"].map(here).fillna(0).astype(int)
        out = io.StringIO()
        if platform == "shopify":
            writer = csv.DictWriter(out, SHOPIFY_PRODUCT_COLUMNS)
            writer.writeheader()
            for p in products.itertuples():
                writer.writerow({
                    "Handle": _handle(f"{p.name}-{p.sku}"), "Title": p.name, "Body (HTML)": "", "Vendor": "",
                    "Type": p.category, "Tags": p.category, "Published": "TRUE", "Option1 Name": "Title",
                    "Option1 Value": "Default Title", "Variant SKU": p.sku,
                    "Variant Inventory Tracker": "shopify" if p.track_stock else "",
                    "Variant Inventory Qty": int(p.stock) if p.track_stock else "",
                    "Variant Inventory Policy": "deny", "Variant Fulfillment Service": "manual",
                    "Variant Price": f"{float(p.price):.2f}", "Variant Requires Shipping": "TRUE",
                    "Variant Taxable": "TRUE", "Status": "active",
                })
        elif platform == "woocommerce":
            writer = csv.DictWriter(out, WOO_PRODUCT_COLUMNS)
            writer.writeheader()
            for p in products.itertuples():
                writer.writerow({
                    "Type": "simple", "SKU": p.sku, "Name": p.name, "Published": 1, "Visibility in catalog": "visible",
                    "Tax status": "taxable", "In stock?": 1 if (not p.track_stock or p.stock > 0) else 0,
                    "Manage stock?": 1 if p.track_stock else 0, "Stock": int(p.stock) if p.track_stock else "",
                    "Regular price": f"{float(p.price):.2f}", "Categories": p.category,
                })
        else:
            raise ValueError("Plataforma no válida.")
        return out.getvalue().encode("utf-8-sig")

    # ------------------------------------------------------------------ orders in
    def import_shop_orders(self, data: bytes, payment_method: str = "Tarjeta", location_id: int | None = None,
                           shipping_product_id: int | None = None, user_name: str = "",
                           now: datetime | None = None) -> dict:
        """Turn an orders export into sales. Returns counts and readable notes for whatever needs a look."""
        if payment_method not in PAYMENT_METHODS:
            raise ValueError("Forma de pago no válida.")
        platform, orders = parse_orders(data)
        now = now or clock.now()
        result = {"platform": platform, "imported": 0, "repeated": 0, "skipped": 0, "rejected": 0, "total": 0.0,
                  "notes": []}
        for order in orders:
            label = f"Pedido {order['number']}"
            try:
                outcome = self._import_shop_order(platform, order, payment_method, location_id, shipping_product_id,
                                                  user_name, now)
            except ValueError as exc:
                result["rejected"] += 1
                result["notes"].append(f"{label}: {exc}")
                continue
            if outcome == "repeated":
                result["repeated"] += 1
            elif isinstance(outcome, str):
                result["skipped"] += 1
                result["notes"].append(f"{label}: {outcome}")
            else:
                result["imported"] += 1
                result["total"] = round(result["total"] + outcome["total"], 2)
                result["notes"].extend(f"{label}: {n}" for n in outcome["notes"])
        if result["imported"]:
            with self.db.tx() as cur:
                self._audit(cur, user_name, "pedidos_tienda_online",
                            f"{result['imported']} pedidos importados ({platform})")
        return result

    def _import_shop_order(self, platform, order, method, location_id, shipping_product_id, user_name, now):
        ref = f"{platform}:{order['number']}"[:80]
        status = order["status"].lower()
        if status not in PAID:
            return f"no está cobrado ({order['status']}), no se importa."
        if not order["lines"]:
            raise ValueError("no tiene productos.")
        when = _date(order["date"]) if order["date"] else now
        if when > now + timedelta(hours=1) or when < now - timedelta(days=400):
            raise ValueError(f"la fecha {when:%d/%m/%Y} no es posible.")
        notes = []
        with self.db.tx() as cur:
            if cur.execute("SELECT 1 FROM sales WHERE external_ref = ?", (ref,)).fetchone():
                return "repeated"
            location_id = self._location_or_main(cur, location_id)
            settings = self._settings(cur)
            default_rate = float(settings.get("tax_rate") or 0)
            lines = []
            for line in order["lines"]:
                product = cur.execute("SELECT * FROM products WHERE sku = ?", (line["sku"],)).fetchone() \
                    if line["sku"] else None
                if product is None:
                    raise ValueError(f"«{line['name'] or line['sku'] or 'producto sin código'}» no tiene un código (SKU) "
                                     "que exista en tu catálogo.")
                qty = int(Decimal(line["qty"] or "0"))
                if not 0 < qty <= 10_000:
                    raise ValueError("cantidad no válida.")
                lines.append((product, {"product_id": product["id"], "quantity": qty,
                                        "unit_price": float(_money(line["price"])),
                                        "tax_rate": float(product["tax_rate"] if product["tax_rate"] is not None
                                                          else default_rate)}))
            shipping = _money(order["shipping"])
            if shipping > 0:
                ship = cur.execute("SELECT * FROM products WHERE id = ?",
                                   (int(shipping_product_id),)).fetchone() if shipping_product_id else None
                if ship is None:
                    notes.append(f"el envío ({shipping} €) no se ha incluido: elige un producto para los envíos.")
                else:
                    lines.append((ship, {"product_id": ship["id"], "quantity": 1, "unit_price": float(shipping),
                                         "tax_rate": float(ship["tax_rate"] if ship["tax_rate"] is not None
                                                           else default_rate), "shipping": True}))
            # The order's discount, spread over its products in cents (as a promotion would be).
            discount = _money(order["discount"])
            goods = [Decimal(str(line["unit_price"])) * line["quantity"] for _, line in lines if not line.get("shipping")]
            shares = iter(allocate(discount, goods) if discount > 0 else [Decimal("0")] * len(goods))
            for _, line in lines:
                line["line_discount"] = 0.0 if line.get("shipping") else float(next(shares))
                line["promo_name"] = "Descuento del pedido" if line["line_discount"] else ""
            totals = compute_totals([line for _, line in lines], 0, default_rate)
            expected = _money(order["total"]) - (shipping if shipping > 0 and not shipping_product_id else 0)
            if order["total"] and abs(Decimal(str(totals["total"])) - expected) > Decimal("0.02"):
                raise ValueError(f"el total no cuadra ({expected} € en el pedido, {totals['total']:.2f} € sumando "
                                 "productos, descuento y envío). ¿Tu tienda muestra los precios sin IVA?")
            number = f"WEB-{re.sub(r'[^A-Za-z0-9]', '', order['number'])[:20]}"
            if cur.execute("SELECT 1 FROM sales WHERE number = ?", (number,)).fetchone():
                number = f"{number}-{platform[:3].upper()}"
            row = cur.execute(
                "INSERT INTO sales(number, created_at, payment_method, discount_pct, tax_rate, subtotal, discount, "
                "tax, total, user_name, promo_discount, external_ref, location_id) "
                "VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (number, when.isoformat(timespec="seconds"), method, default_rate, totals["subtotal"],
                 totals["discount"], totals["tax"], totals["total"],
                 (f"Tienda online · {user_name}" if user_name else "Tienda online")[:120], totals["promo_discount"],
                 ref, location_id),
            ).fetchone()
            sale_id = row["id"]
            for (p, line), net, vat, gross in zip(lines, totals["net_amounts"], totals["tax_amounts"],
                                                  totals["gross_amounts"]):
                cur.execute(
                    "INSERT INTO sale_items(sale_id, product_id, name, quantity, unit_price, unit_cost, line_discount, "
                    "promo_name, net_amount, tax_rate, tax_amount, gross_amount) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (sale_id, p["id"], p["name"], line["quantity"], line["unit_price"], p["cost"],
                     line["line_discount"], line["promo_name"], net, line["tax_rate"], vat, gross),
                )
                if p["track_stock"]:
                    have = max(self._stock_at(cur, p["id"], location_id), 0)
                    if have < line["quantity"]:
                        notes.append(f"revisa el stock de «{p['name']}» (se vendieron más de los que había).")
                    self._move_stock(cur, p["id"], -min(have, line["quantity"]), location_id)
            if totals["total"] > 0:
                cur.execute("INSERT INTO sale_payments(sale_id, method, amount, tendered) VALUES (?, ?, ?, 0)",
                            (sale_id, method, totals["total"]))
            self._register_issue(cur, "F2", number, when, totals["tax"], totals["total"], totals["taxes"], "sale",
                                 sale_id)
        if status == "partially_refunded":
            notes.append("tiene una devolución parcial en la tienda: regístrala en Historial → Devolver.")
        return {"total": totals["total"], "notes": notes}
