"""Store side of the intelligence features: data for alerts, price changes and the weekly report."""

from datetime import date, datetime, time, timedelta

import pandas as pd

from . import automation, intelligence
from .pricing import format_money
from .presets import CURRENCIES, PRESETS
from . import clock


def week_start(day: date) -> datetime:
    """Monday 00:00 of the week that contains `day`."""
    return datetime.combine(day - timedelta(days=day.weekday()), time.min)


class IntelligenceMixin:
    """Mixed into `Store`."""

    def incidents(self, start: datetime) -> pd.DataFrame:
        """Voids and returns since `start`, with the person who made the original sale."""
        stamp = start.isoformat(timespec="seconds")
        df = self._frame(
            "SELECT 'anulación' AS kind, COALESCE(voided_at, created_at) AS created_at, user_name AS seller, "
            "voided_by AS done_by, total AS amount, number FROM sales "
            "WHERE status = 'anulada' AND COALESCE(voided_at, created_at) >= ? "
            "UNION ALL "
            "SELECT 'devolución', r.created_at, s.user_name, r.user_name, r.total, r.number FROM refunds r "
            "JOIN sales s ON s.id = r.sale_id WHERE r.created_at >= ?",
            [stamp, stamp],
        )
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["amount"] = df["amount"].astype(float)
        return df

    def set_prices(self, changes: dict) -> int:
        """Apply new prices {product_id: price}. Returns how many products changed."""
        clean = {}
        for pid, price in changes.items():
            price = round(float(price), 2)
            if not 0 < price < 10_000_000:
                raise ValueError("Los precios deben ser mayores que cero.")
            clean[int(pid)] = price
        with self.db.tx() as cur:
            for pid, price in clean.items():
                cur.execute("UPDATE products SET price = ? WHERE id = ?", (price, pid))
        return len(clean)

    def _money(self):
        settings = self.settings()
        symbol = CURRENCIES.get(settings.get("currency", "EUR"), "€")
        return lambda v: format_money(v, symbol)

    def data_version(self) -> tuple:
        """Changes whenever something the alerts and reports read changes: a cheap key for sharing them."""
        with self.db.tx() as cur:
            row = cur.execute(
                "SELECT (SELECT COALESCE(MAX(id), 0) FROM sales) AS s, "
                "(SELECT COUNT(*) FROM sales WHERE status = 'anulada') AS v, "
                "(SELECT COALESCE(MAX(id), 0) FROM refunds) AS r, (SELECT COALESCE(MAX(id), 0) FROM stock_moves) AS m, "
                "(SELECT COALESCE(MAX(id), 0) FROM cash_closings) AS c, (SELECT COALESCE(MAX(id), 0) FROM expenses) AS e, "
                "(SELECT COUNT(*) FROM orders WHERE status = 'abierta') AS o").fetchone()
        return tuple(row.values())

    def alerts(self, now: datetime | None = None) -> list[dict]:
        now = now or clock.now()
        this_month = now.date().replace(day=1)
        last_month = (this_month - timedelta(days=1)).replace(day=1)
        data = {
            "settings": self.settings(),
            "products": self.products(),
            # Only what the rules read: 30 days of lines and tickets, and per-customer totals summed in SQL.
            "lines": self.sale_lines(start=now - timedelta(days=30)),
            "sales": self.sales(start=now - timedelta(days=30)),
            "customer_totals": self.customer_totals(start=now - timedelta(days=400)),
            "customers": self.customers(),
            "closings": self.cash_closings(),
            "open_orders": self.open_orders(),
            "incidents": self.incidents(now - timedelta(days=30)),
            "profit_last_month": self.profit(last_month, this_month),
        }
        return intelligence.smart_alerts(data, now, self._money())

    def _week_profit(self, start: datetime, end: datetime, numbers: dict) -> dict:
        """Gross margin of the week minus its share of fixed costs (monthly × 12 / 52) and the one-off
        expenses noted that week. Fixed costs are spread so a rent paid on day 1 does not sink one week."""
        from .store_purchases import PURCHASES_CATEGORY
        exp = self.expenses(start.date(), end.date())
        variable = exp[(exp["category"] != PURCHASES_CATEGORY) & exp["recurring_id"].isna()]
        recurring = self.recurring_expenses()
        fixed = float(recurring[recurring["active"] == 1]["amount"].astype(float).sum()) * 12 / 52
        gross = numbers["cur"]["margin"]
        opex = fixed + float(variable["amount"].sum())
        return {"net_sales": numbers["cur"]["net"], "gross": gross, "fixed": fixed,
                "variable": float(variable["amount"].sum()), "opex": opex, "net": gross - opex}

    def weekly_report(self, start: datetime, now: datetime | None = None, alerts: list[dict] | None = None) -> dict:
        """Everything the weekly PDF shows for the week that starts on Monday `start`."""
        now = now or clock.now()
        end = start + timedelta(days=7)
        settings = self.settings()
        preset = PRESETS[settings.get("business_type", "retail")]
        sales = self.sales(start=start - timedelta(days=7), end=end)
        month_lines = self.sale_lines(start=end - timedelta(days=30), end=end)  # one query covers both uses
        lines = month_lines[month_lines["created_at"] >= start - timedelta(days=7)]
        refunds = self.refunds(start=start - timedelta(days=7), end=end)
        numbers = intelligence.weekly_numbers(sales, lines, refunds, start)
        products = self.products()
        week_lines = lines[lines["created_at"] >= start]
        abc = intelligence.abc_analysis(products, month_lines)
        closings = self.cash_closings()
        if not closings.empty:
            days = pd.to_datetime(closings["day"])
            closings = closings[(days >= start) & (days < end)]
        profit = self._week_profit(start, end, numbers)
        if alerts is None or now >= end:  # the current week reuses today's alerts; a past one is judged as it ended
            alerts = self.alerts(min(now, end))
        insights = automation.insights(products, week_lines, preset["item_label"])
        return {
            "start": start, "end": end, "numbers": numbers, "abc": abc,
            "abc_summary": intelligence.abc_summary(abc), "closings": closings, "profit": profit,
            "alerts": alerts, "recommendations": intelligence.recommendations(numbers, alerts, abc, insights),
            "complete": now >= end,
        }
