"""Automations: KPIs, stock alerts, reorder suggestions, customer follow-ups and insights."""

import math
from datetime import datetime, timedelta

import pandas as pd
from . import clock


def period_bounds(days: int, now: datetime | None = None):
    """Current window of `days` days ending now, plus the previous window of equal length."""
    now = now or clock.now()
    end = now + timedelta(seconds=1)
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    prev_start = start - timedelta(days=days)
    return start, end, prev_start


def _pct_change(current: float, previous: float):
    if previous == 0:
        return None
    return (current - previous) / previous * 100


def kpis(sales: pd.DataFrame, lines: pd.DataFrame, start: datetime, end: datetime, prev_start: datetime,
         refunds: pd.DataFrame | None = None) -> dict:
    """Headline numbers for the window [start, end) compared with [prev_start, start), net of returns."""
    done = sales[sales["status"] == "completada"]
    cur = done[(done["created_at"] >= start) & (done["created_at"] < end)]
    prev = done[(done["created_at"] >= prev_start) & (done["created_at"] < start)]
    cur_lines = lines[(lines["created_at"] >= start) & (lines["created_at"] < end)]

    def returned(lo, hi) -> float:
        if refunds is None or refunds.empty:
            return 0.0
        return float(refunds[(refunds["created_at"] >= lo) & (refunds["created_at"] < hi)]["total"].sum())

    revenue = cur["total"].sum() - returned(start, end)
    prev_revenue = prev["total"].sum() - returned(prev_start, start)
    count, prev_count = len(cur), len(prev)
    ticket = revenue / count if count else 0.0
    prev_ticket = prev_revenue / prev_count if prev_count else 0.0
    net = cur_lines["revenue"].sum()
    margin_pct = cur_lines["margin"].sum() / net * 100 if net else 0.0
    return {
        "revenue": revenue,
        "revenue_delta": _pct_change(revenue, prev_revenue),
        "count": count,
        "count_delta": _pct_change(count, prev_count),
        "ticket": ticket,
        "ticket_delta": _pct_change(ticket, prev_ticket),
        "margin_pct": margin_pct,
    }


def low_stock(products: pd.DataFrame) -> pd.DataFrame:
    tracked = products[(products["track_stock"] == 1) & (products["active"] == 1)]
    return tracked[tracked["stock"] <= tracked["min_stock"]].sort_values("stock")


def reorder_suggestions(
    products: pd.DataFrame, lines: pd.DataFrame, lead_days: int = 14, window_days: int = 30, now: datetime | None = None
) -> pd.DataFrame:
    """Suggest purchase quantities so stock covers `lead_days` of demand plus the safety minimum.

    Demand is the average daily units sold over the last `window_days`.
    """
    now = now or clock.now()
    recent = lines[lines["created_at"] >= now - timedelta(days=window_days)]
    daily = recent.groupby("product_id")["quantity"].sum() / window_days

    rows = []
    for _, p in products[(products["track_stock"] == 1) & (products["active"] == 1)].iterrows():
        demand = float(daily.get(p["id"], 0.0))
        target = demand * lead_days + p["min_stock"]
        qty = math.ceil(target - p["stock"])
        if qty <= 0:
            continue
        rows.append(
            {
                "sku": p["sku"],
                "name": p["name"],
                "stock": int(p["stock"]),
                "daily_demand": round(demand, 2),
                "days_of_cover": round(p["stock"] / demand, 1) if demand else None,
                "suggested_qty": qty,
                "estimated_cost": round(qty * p["cost"], 2),
            }
        )
    columns = ["sku", "name", "stock", "daily_demand", "days_of_cover", "suggested_qty", "estimated_cost"]
    return pd.DataFrame(rows, columns=columns).sort_values("days_of_cover", na_position="first")


def inactive_customers(
    customers: pd.DataFrame, sales: pd.DataFrame, days: int = 60, now: datetime | None = None
) -> pd.DataFrame:
    """Customers with past purchases whose last purchase is older than `days` days."""
    now = now or clock.now()
    done = sales[(sales["status"] == "completada") & sales["customer_id"].notna()]
    if done.empty:
        return pd.DataFrame(columns=["id", "name", "email", "phone", "last_purchase", "days_inactive", "lifetime_value"])
    stats = done.groupby("customer_id").agg(last_purchase=("created_at", "max"), lifetime_value=("total", "sum"))
    merged = customers.merge(stats, left_on="id", right_index=True)
    merged["days_inactive"] = (now - merged["last_purchase"]).dt.days
    result = merged[merged["days_inactive"] >= days]
    return result[["id", "name", "email", "phone", "last_purchase", "days_inactive", "lifetime_value"]].sort_values(
        "lifetime_value", ascending=False
    )


def followup_message(customer_name: str, business_name: str) -> str:
    first = customer_name.split()[0] if customer_name.strip() else ""
    return (
        f"Hola {first}:\n\n"
        f"Hace un tiempo que no nos visitas y en {business_name} te echamos de menos. "
        "Tenemos novedades que creemos que te van a gustar y, como agradecimiento por tu confianza, "
        "te ofrecemos un 10 % de descuento en tu próxima compra.\n\n"
        f"Un saludo,\nEl equipo de {business_name}"
    )


def customer_ranking(customers: pd.DataFrame, sales: pd.DataFrame) -> pd.DataFrame:
    done = sales[(sales["status"] == "completada") & sales["customer_id"].notna()]
    stats = done.groupby("customer_id").agg(
        purchases=("id", "count"), lifetime_value=("total", "sum"), last_purchase=("created_at", "max")
    )
    merged = customers.merge(stats, left_on="id", right_index=True, how="left")
    merged["purchases"] = merged["purchases"].fillna(0).astype(int)
    merged["lifetime_value"] = merged["lifetime_value"].fillna(0.0)
    return merged.sort_values("lifetime_value", ascending=False)


WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def insights(products: pd.DataFrame, lines: pd.DataFrame, item_label: str = "producto") -> list[tuple[str, str]]:
    """Plain-language recommendations as (level, message); level is 'good', 'warning' or 'info'."""
    out: list[tuple[str, str]] = []
    if lines.empty:
        return [("info", "Aún no hay ventas suficientes para generar recomendaciones.")]

    by_product = lines.groupby("name").agg(revenue=("revenue", "sum"), margin=("margin", "sum"))
    top = by_product["revenue"].idxmax()
    share = by_product.loc[top, "revenue"] / by_product["revenue"].sum() * 100
    out.append(("good", f"«{top}» es tu {item_label.lower()} estrella: genera el {share:.0f} % de la facturación."))
    if share > 50:
        out.append(("warning", "Más de la mitad de tus ingresos dependen de un solo artículo: diversifica la oferta."))

    by_day = lines.assign(weekday=lines["created_at"].dt.weekday).groupby("weekday")["revenue"].sum()
    out.append(("info", f"El {WEEKDAYS[int(by_day.idxmax())]} es tu mejor día: refuerza personal y promociones."))

    active = products[products["active"] == 1]
    priced = active[active["price"] > 0]
    thin = priced[(priced["price"] - priced["cost"]) / priced["price"] < 0.25]
    for name in thin["name"].head(3):
        out.append(("warning", f"«{name}» tiene un margen inferior al 25 %: revisa su precio o su coste."))

    sold = set(lines["product_id"])
    unsold = active[~active["id"].isin(sold)]
    if not unsold.empty:
        names = ", ".join(f"«{n}»" for n in unsold["name"].head(3))
        out.append(("info", f"Sin ventas en el periodo: {names}. Valora destacarlos o retirarlos."))
    return out
