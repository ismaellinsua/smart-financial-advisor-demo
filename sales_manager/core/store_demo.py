"""Business templates and demonstration data, and the guard that keeps real fiscal records from being replaced.
Mixed into `Store`."""

import random
from datetime import datetime, time, timedelta

from . import clock
from .errors import FiscalDataError
from .presets import PAYMENT_METHODS, PRESETS
from .schema import DATA_TABLES, FISCAL_DATA_MESSAGE, FISCAL_TABLES


class DemoMixin:
    # ---------------------------------------------------------------- demo setup
    def is_empty(self) -> bool:
        # Not cached: another server may have just set the business up, and this decides showing onboarding.
        with self.db.tx() as cur:
            return cur.execute("SELECT 1 FROM products LIMIT 1").fetchone() is None

    # ------------------------------------------------- demonstration vs real data
    def is_demo(self) -> bool:
        return self.settings().get("demo_mode") == "si"

    def has_fiscal_records(self) -> bool:
        with self.db.tx() as cur:
            return any(cur.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone() for t in FISCAL_TABLES)

    def can_replace_data(self) -> bool:
        """Demonstration data, or a business with no sales yet, may be wiped; real fiscal records never."""
        with self.db.tx() as cur:
            if cur.execute("SELECT 1 FROM billing_records LIMIT 1").fetchone():
                return False  # chained billing records are never wiped, whatever the mode says
        return self.is_demo() or not self.has_fiscal_records()

    def _guard_replace(self) -> None:
        if not self.can_replace_data():
            raise FiscalDataError(FISCAL_DATA_MESSAGE)

    def reset(self) -> None:
        """Delete all data (to start for real after a demonstration). Refused once there are real records."""
        self._guard_replace()
        with self.db.tx() as cur:
            self._replace(cur, {t: [] for t in DATA_TABLES})
            self._save_settings(cur, {"demo_mode": "no"})

    def load_preset(self, business_type: str, with_demo_sales: bool = True, seed: int = 7) -> None:
        """Replace all data with a preset catalog and, optionally, ~60 days of realistic demo activity.

        The data is built in a scratch in-memory database and copied over in one transaction, which keeps
        this fast on a remote server and leaves the current data untouched if anything fails.
        """
        self._guard_replace()
        preset = PRESETS[business_type]
        new_settings = {"business_type": business_type, "tax_rate": preset["tax_rate"],
                        "demo_mode": "si" if with_demo_sales else "no"}
        scratch = type(self)(":memory:")
        try:
            scratch.save_settings({**self.settings(), **new_settings})
            scratch._populate(preset, with_demo_sales, seed)
            data = scratch._export(DATA_TABLES)
        finally:
            scratch.close()
        with self.db.tx() as cur:
            self._replace(cur, data)
            self._save_settings(cur, new_settings)

    def _populate(self, preset: dict, with_demo_sales: bool, seed: int) -> None:
        for promo in preset.get("promotions", []):
            self.save_promotion({"days": "0123456", **promo})
        targets = {}
        for row in preset["catalog"]:
            sku, name, category, price, cost, stock, min_stock = row[:7]
            track = row[7] if len(row) > 7 else preset["track_stock"]
            pid = self.upsert_product(
                {
                    "sku": sku,
                    "name": name,
                    "category": category,
                    "price": price,
                    "cost": cost,
                    # Ample stock while generating demo history; the target level is set afterwards.
                    "stock": (10_000 if with_demo_sales else stock) if track else 0,
                    "min_stock": min_stock if track else 0,
                    "track_stock": int(track),
                    "active": 1,
                }
            )
            targets[pid] = stock if track else 0
        if not with_demo_sales:
            return
        try:
            self._generate_demo_sales(seed, preset)
        finally:
            with self.db.tx() as cur:
                cur.executemany("UPDATE products SET stock = ? WHERE id = ?", [(v, k) for k, v in targets.items()])

    def _generate_demo_sales(self, seed: int, preset: dict) -> None:
        rng = random.Random(seed)
        names = [
            ("Lucía Fernández", "lucia@example.com"),
            ("Martín Gómez", "martin@example.com"),
            ("Sofía Ruiz", "sofia@example.com"),
            ("Distribuciones Norte S.L.", "compras@norte.example.com"),
            ("Carlos Méndez", "carlos@example.com"),
            ("Valentina Ortiz", "valentina@example.com"),
        ]
        customer_ids = [self.upsert_customer({"name": n, "email": e}) for n, e in names]
        products = self.products()
        now = clock.now().replace(second=0, microsecond=0)
        for days_ago in range(60, -1, -1):
            day = now - timedelta(days=days_ago)
            weekend_boost = 1.5 if day.weekday() >= 4 else 1.0
            low, high = preset.get("demo_sales_per_day", (1, 5))
            for _ in range(int(rng.randint(low, high) * weekend_boost)):
                when = day.replace(hour=rng.randint(9, 20), minute=rng.randint(0, 59))
                if when > now:
                    continue
                picks = products.sample(
                    n=rng.randint(1, min(preset.get("demo_max_items", 3), len(products))),
                    random_state=rng.randint(0, 10**6),
                )
                cart = [{"product_id": int(pid), "quantity": rng.randint(1, preset.get("demo_max_quantity", 3))} for pid in picks["id"]]
                # Customers who stopped buying a while ago give the follow-up automation something to show.
                pool = customer_ids if days_ago > 40 else customer_ids[:4]
                customer = rng.choice(pool + [None, None])
                self.create_sale(
                    cart,
                    payment_method=rng.choice(PAYMENT_METHODS[:4]),
                    customer_id=customer,
                    discount_pct=rng.choice([0, 0, 0, 5, 10]),
                    when=when,
                    user_name=rng.choice(["Marta", "Diego", "Sara"]),  # demo team, shown in the Panel
                )

        # One seller with more voids and returns than the rest, for the team alert to show.
        recent = self.sales(start=now - timedelta(days=12), include_cancelled=False)
        diego = recent[recent["user_name"] == "Diego"].head(5)
        for i, (sale_id, created) in enumerate(zip(diego["id"], diego["created_at"])):
            later = min(created.to_pydatetime() + timedelta(minutes=20), now)
            if i < 2:
                self.cancel_sale(int(sale_id), by="Marta", when=later)
            else:
                item = self.returnable(int(sale_id))[0]
                self.create_refund(int(sale_id), {item["id"]: 1}, "Efectivo", "El cliente no quedó satisfecho",
                                   user_name="Marta", when=later)

        # Closed tills for the last few days, with the small differences real counts have.
        for days_ago in range(5, 0, -1):
            day = (now - timedelta(days=days_ago)).date()
            net_cash = self.day_summary(day)["cash"]
            # Fictitious refunds can exceed cash receipts (e.g. an online card sale refunded in cash).
            # Seed enough opening cash to fund them; never manufacture a negative physical cash count.
            opening = round(150 + max(0, -net_cash), 2)
            expected = opening + net_cash
            self.close_cash(day, opening, round(expected + rng.choice([0, 0, 0, -2.5, 1.2, 5]), 2),
                            when=datetime.combine(day, time(21, 30)))

        agenda = preset.get("agenda")
        if agenda:
            self._generate_demo_appointments(rng, agenda, customer_ids, products, now)
        if preset.get("tables"):
            self._generate_demo_tables(rng, preset["tables"], products)
        self._generate_demo_purchasing(rng, preset, products, now)

    def _generate_demo_purchasing(self, rng, preset: dict, products, now) -> None:
        supplier_ids = [self.save_supplier({"name": name, "email": email, "tax_id": tax})
                        for name, email, tax in preset.get("suppliers", [])]
        if supplier_ids:
            for i, pid in enumerate(products["id"]):
                self.set_product_supplier(int(pid), supplier_ids[i % len(supplier_ids)])
        for category, description, amount, day in preset.get("fixed_costs", []):
            self.save_recurring(category, description, amount, day)
        self.apply_recurring(until=now.date(), since=(now - timedelta(days=60)).date())
        # One past delivery (already received and paid) and one order waiting to be sent.
        tracked = products[products["track_stock"] == 1]
        if not tracked.empty and supplier_ids:
            def items_from(supplier_id):  # each order only carries products that supplier provides
                own = [p for i, (_, p) in enumerate(products.iterrows())
                       if supplier_ids[i % len(supplier_ids)] == supplier_id and p["track_stock"] == 1]
                return [{"product_id": int(p["id"]), "quantity": rng.randint(10, 30), "unit_cost": float(p["cost"])}
                        for p in own[:3]]
            if items := items_from(supplier_ids[0]):
                past = self.create_purchase(supplier_ids[0], items, created_by="Demo", when=now - timedelta(days=20))
                self.receive_purchase(past, received_by="Demo", when=now - timedelta(days=18))
            if items := items_from(supplier_ids[-1])[:2]:
                self.create_purchase(supplier_ids[-1], items, "Pendiente de enviar", created_by="Demo")
        for days_ago, category, description, amount in [(25, "Marketing", "Anuncios en redes sociales", 120),
                                                         (12, "Mantenimiento", "Revisión de equipos", 85)]:
            self.add_expense((now - timedelta(days=days_ago)).date(), category, description, amount,
                             created_by="Demo")

    def _generate_demo_tables(self, rng, layout: dict, products) -> None:
        table_ids = [self.save_table(name, zone, seats) for zone, tables in layout.items() for name, seats in tables]
        waiters = ["Marta", "Diego", "Sara"]
        statuses = ["servido", "servido", "listo", "preparando", "pendiente"]
        for table_id in rng.sample(table_ids, k=min(4, len(table_ids))):
            order_id = self.open_order(table_id, guests=rng.randint(2, 5), opened_by=rng.choice(waiters))
            for _ in range(rng.randint(2, 5)):
                pid = int(rng.choice(list(products["id"])))
                category = products.set_index("id").loc[pid, "category"]
                note = rng.choice({"Principales": ["", "", "poco hecho", "al punto"],
                                   "Entrantes": ["", "", "para compartir", "sin cebolla"]}.get(category, [""]))
                item = self.add_order_item(order_id, pid, rng.randint(1, 3), note, added_by=rng.choice(waiters))
                self.set_kitchen_status(item, rng.choice(statuses))

    def _generate_demo_appointments(self, rng, agenda, customer_ids, products, now) -> None:
        walk_ins = ["Laura Pérez", "Javier Romero", "Elena Castro", "Pablo Navarro", "Marta Gil"]
        for days_ahead in range(7):
            day = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0)
            for hour in sorted(rng.sample(agenda["hours"], k=min(len(agenda["hours"]), rng.randint(2, 4)))):
                starts = day + timedelta(hours=hour)
                if starts <= now:
                    continue
                known = rng.random() < 0.6
                if agenda["single"]:
                    product, notes = int(rng.choice(list(products["id"]))), ""
                else:
                    product, notes = None, f"Mesa para {rng.randint(2, 6)} personas"
                self.create_appointment(
                    starts, agenda["duration"], product_id=product,
                    customer_id=rng.choice(customer_ids) if known else None,
                    customer_name="" if known else rng.choice(walk_ins),
                    notes=notes, allow_overlap=not agenda["single"],
                )

