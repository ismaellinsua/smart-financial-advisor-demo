"""Business intelligence: ABC analysis, price suggestions, smart alerts and the weekly report contents.

Pure functions over the data frames the store returns, so they are easy to test with any date as «now».
"""

import math
from datetime import datetime, timedelta

import pandas as pd

from .automation import WEEKDAYS

ABC_LIMITS = (80.0, 95.0)  # cumulative % of gross margin that closes classes A and B
LEVELS = {"alta": 0, "media": 1, "baja": 2}


# ------------------------------------------------------------------ ABC analysis
def abc_analysis(products: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    """Classify active products by their contribution to gross margin in `lines`.

    A: the few products that bring 80 % of the margin; B: the next 15 %; C: the rest, including products
    without sales or that lose money. Returns one row per active product, best first.
    """
    columns = ["id", "sku", "name", "category", "price", "cost", "units", "revenue", "margin", "margin_pct",
               "unit_margin_pct", "share", "cum_share", "abc"]
    active = products[products["active"] == 1]
    if active.empty:
        return pd.DataFrame(columns=columns)
    sold = lines.groupby("product_id").agg(units=("quantity", "sum"), revenue=("revenue", "sum"),
                                           margin=("margin", "sum"))
    df = active[["id", "sku", "name", "category", "price", "cost"]].assign(net=_net(active)).merge(
        sold, left_on="id", right_index=True, how="left")
    df[["units", "revenue", "margin"]] = df[["units", "revenue", "margin"]].fillna(0.0).astype(float)
    df["price"], df["cost"] = df["price"].astype(float), df["cost"].astype(float)
    df["margin_pct"] = (df["margin"] / df["revenue"].where(df["revenue"] > 0) * 100).round(1)
    df["unit_margin_pct"] = ((df["net"] - df["cost"]) / df["net"].where(df["net"] > 0) * 100).round(1)
    df = df.drop(columns=["net"]).sort_values(["margin", "revenue"], ascending=False).reset_index(drop=True)

    positive = df["margin"].clip(lower=0)
    total = positive.sum()
    df["share"] = (positive / total * 100).round(1) if total else 0.0
    before = (positive.cumsum() - positive) / total * 100 if total else pd.Series(100.0, index=df.index)
    df["cum_share"] = (before + (df["share"] if total else 0)).round(1)

    def klass(i: int) -> str:
        if df.at[i, "margin"] <= 0:
            return "C"
        if before[i] < ABC_LIMITS[0]:
            return "A"
        return "B" if before[i] < ABC_LIMITS[1] else "C"

    df["abc"] = [klass(i) for i in df.index]
    return df[columns]


def abc_summary(abc: pd.DataFrame) -> dict:
    """Per class: number of products and share of margin and revenue."""
    out = {}
    total_margin = abc["margin"].clip(lower=0).sum()
    total_revenue = abc["revenue"].sum()
    for k in "ABC":
        part = abc[abc["abc"] == k]
        out[k] = {
            "count": len(part),
            "margin_share": float(part["margin"].clip(lower=0).sum() / total_margin * 100) if total_margin else 0.0,
            "revenue_share": float(part["revenue"].sum() / total_revenue * 100) if total_revenue else 0.0,
        }
    return out


# ------------------------------------------------------------------ prices
def round_price(value: float) -> float:
    """Round a price up to a tidy amount: 5 cents below 10, 10 cents below 100, whole units above."""
    step = 0.05 if value < 10 else 0.10 if value < 100 else 1.0
    return round(math.ceil(round(value / step, 6)) * step, 2)


def _net(df: pd.DataFrame) -> pd.Series:
    """Price without VAT (what the business keeps). Catalog prices include VAT; margins are on the net price."""
    if "net_price" in df:
        return df["net_price"].astype(float)
    return df["price"].astype(float)


def _vat(df: pd.DataFrame) -> pd.Series:
    return df["vat"].astype(float) if "vat" in df else pd.Series(0.0, index=df.index)


def price_suggestions(products: pd.DataFrame, target_pct: float, abc: pd.DataFrame | None = None) -> pd.DataFrame:
    """Products whose margin on price is under `target_pct`, with the price that reaches it.

    Catalog prices include VAT: the margin is measured on the price without VAT, and the suggestion is a shelf
    price (VAT included) rounded to a comfortable amount. Products without a cost are skipped: there is nothing to
    compare against. Class A products come first because they matter most.
    """
    columns = ["id", "sku", "name", "category", "cost", "price", "unit_margin_pct", "suggested", "new_margin_pct",
               "increase_pct", "units", "abc"]
    if not 0 < target_pct < 95:
        raise ValueError("El margen objetivo debe estar entre 1 y 94 %.")
    df = products[(products["active"] == 1) & (products["cost"] > 0) & (products["price"] > 0)].copy()
    df["price"], df["cost"] = df["price"].astype(float), df["cost"].astype(float)
    net, vat = _net(df), _vat(df)
    df["unit_margin_pct"] = ((net - df["cost"]) / net * 100).round(1)
    keep = df["unit_margin_pct"] < target_pct - 0.05
    df, vat = df[keep], vat[keep]
    if df.empty:
        return pd.DataFrame(columns=columns)
    df["suggested"] = [round_price(cost / (1 - target_pct / 100) * (1 + v / 100)) for cost, v in zip(df["cost"], vat)]
    new_net = df["suggested"] / (1 + vat / 100)
    df["new_margin_pct"] = ((new_net - df["cost"]) / new_net * 100).round(1)
    df["increase_pct"] = ((df["suggested"] / df["price"] - 1) * 100).round(1)
    if abc is not None and not abc.empty:
        df = df.merge(abc[["id", "abc", "units"]], on="id", how="left")
    else:
        df["abc"], df["units"] = "C", 0.0
    df["abc"] = df["abc"].fillna("C")
    df["units"] = df["units"].fillna(0.0)
    return df.sort_values(["abc", "units"], ascending=[True, False])[columns].reset_index(drop=True)


# ------------------------------------------------------------------ alerts
def _alert(level: str, area: str, title: str, detail: str, page: str = "") -> dict:
    return {"level": level, "area": area, "title": title, "detail": detail, "page": page}


def _names(values, limit: int = 4) -> str:
    values = list(values)
    shown = ", ".join(f"«{v}»" for v in values[:limit])
    return shown + (f" y {len(values) - limit} más" if len(values) > limit else "")


def smart_alerts(data: dict, now: datetime, money=lambda v: f"{v:,.2f}") -> list[dict]:
    """Things that need a decision, most urgent first. Each alert says what happened and where to look.

    `data` holds: products, lines (≥ 60 days), sales (≥ 60 days), customers, closings, open_orders, incidents
    (voids and returns with the seller, ≥ 30 days), profit_last_month and settings.
    """
    s = data.get("settings", {})
    out: list[dict] = []
    lines, sales, products = data["lines"], data["sales"], data["products"]
    done = sales[sales["status"] == "completada"]

    # 1. Sales trend: the last 7 days against the 7 before.
    week = lines[lines["created_at"] >= now - timedelta(days=7)]["revenue"].sum()
    prev = lines[(lines["created_at"] >= now - timedelta(days=14)) & (lines["created_at"] < now - timedelta(days=7))]
    prev = prev["revenue"].sum()
    drop = float(s.get("alert_sales_drop", 20) or 20)
    if prev > 0 and (week - prev) / prev * 100 <= -drop:
        pct = (prev - week) / prev * 100
        out.append(_alert("alta", "Ventas", f"Las ventas han bajado un {pct:.0f} % esta semana",
                          f"Últimos 7 días: {money(week)} netos frente a {money(prev)} la semana anterior. "
                          "Revisa horarios, personal y promociones.", "dashboard"))

    # 2. Cash counts that did not match.
    closings = data["closings"]
    if not closings.empty:
        recent = closings[pd.to_datetime(closings["day"]) >= pd.Timestamp(now.date() - timedelta(days=14))]
        off = recent[recent["difference"].abs() >= 0.995]
        if not off.empty:
            worst = off.loc[off["difference"].abs().idxmax()]
            level = "alta" if off["difference"].abs().max() >= 10 or off["difference"].abs().sum() >= 20 else "media"
            out.append(_alert(level, "Caja", f"{len(off)} cierre(s) de caja con descuadre en 14 días",
                              f"Suman {money(off['difference'].sum())}; el mayor fue el "
                              f"{pd.to_datetime(worst['day']):%d/%m} ({money(worst['difference'])}).", "cash"))

    # 3. Stock that runs out soon, at the pace of the last 14 days.
    cover = int(s.get("alert_cover_days", 3) or 3)
    tracked = products[(products["track_stock"] == 1) & (products["active"] == 1)]
    recent_lines = lines[lines["created_at"] >= now - timedelta(days=14)]
    daily = recent_lines.groupby("product_id")["quantity"].sum() / 14
    out_now, soon = [], []
    for _, p in tracked.iterrows():
        demand = float(daily.get(p["id"], 0.0))
        if demand <= 0:
            continue
        if p["stock"] <= 0:
            out_now.append(p["name"])
        elif p["stock"] / demand <= cover:
            days = p["stock"] / demand
            soon.append(f"{p['name']} ({f'{days:.0f} d' if days >= 1 else 'hoy'})")
    if out_now:
        out.append(_alert("alta", "Stock", f"{len(out_now)} producto(s) agotado(s) que se siguen vendiendo",
                          f"{_names(out_now)}. Pide ya al proveedor.", "purchases"))
    if soon:
        out.append(_alert("media", "Stock", f"{len(soon)} producto(s) se agotan en {cover} días o menos",
                          f"Al ritmo actual: {_names(soon)}.", "automations"))

    # 4. Best customers who stopped coming, compared with their own habits.
    with_customer = done[done["customer_id"].notna()]
    if not with_customer.empty:
        stats = with_customer.groupby("customer_id").agg(
            n=("id", "count"), value=("total", "sum"), first=("created_at", "min"), last=("created_at", "max"))
        stats = stats[stats["n"] >= 3]
        if not stats.empty:
            vip = stats[stats["value"] >= stats["value"].quantile(0.6)]
            gap = (vip["last"] - vip["first"]).dt.days / (vip["n"] - 1)
            away = (now - vip["last"]).dt.days
            lost = vip[(away > (gap * 2).clip(lower=14))]
            if not lost.empty:
                names = data["customers"].set_index("id")["name"]
                who = [f"{names.get(i, 'Cliente')} ({int(away[i])} d)" for i in lost.sort_values("value",
                                                                                                    ascending=False).index]
                out.append(_alert("media", "Clientes", f"{len(lost)} cliente(s) habitual(es) han dejado de venir",
                                  f"{_names(who)}. Envíales un mensaje desde Automatizaciones.", "automations"))

    # 5. Forgotten open tables.
    orders = data.get("open_orders")
    if orders is not None and not orders.empty:
        opened = pd.to_datetime(orders["opened_at"])
        stale = orders[opened <= now - timedelta(hours=3)]
        if not stale.empty:
            names = [t or l for t, l in zip(stale["table_name"].fillna(""), stale["label"].fillna(""))]
            out.append(_alert("media", "Mesas", f"{len(stale)} comanda(s) abiertas desde hace más de 3 horas",
                              f"{_names(names)}. ¿Se olvidó cobrarlas o cerrarlas?", "tables"))

    # 6. Sellers with many more voids and returns than the rest of the team.
    incidents = data.get("incidents")
    month_sales = done[done["created_at"] >= now - timedelta(days=30)]
    if incidents is not None and not incidents.empty:
        per_seller = month_sales[month_sales["user_name"] != ""].groupby("user_name")["id"].count()
        voided = sales[(sales["status"] == "anulada") & (sales["created_at"] >= now - timedelta(days=30))]
        per_seller = per_seller.add(voided.groupby("user_name")["id"].count(), fill_value=0)
        inc = incidents[incidents["seller"] != ""].groupby("seller").agg(n=("kind", "count"), amount=("amount", "sum"))
        for seller, row in inc.iterrows():
            others_inc = inc["n"].sum() - row["n"]
            others_sales = per_seller.sum() - per_seller.get(seller, 0)
            mine = row["n"] / max(per_seller.get(seller, 0), 1)
            team = others_inc / others_sales if others_sales else 0
            if row["n"] >= 3 and mine > max(2 * team, 0.02):
                out.append(_alert("alta", "Equipo", f"Muchas anulaciones y devoluciones en ventas de {seller}",
                                  f"{int(row['n'])} en 30 días ({mine * 100:.0f} % de sus ventas, el resto del "
                                  f"equipo {team * 100:.0f} %) por {money(row['amount'])}. Revísalo en el "
                                  "Historial.", "history"))

    # 7. Money: losses or heavy expenses last month.
    pm = data.get("profit_last_month")
    if pm and pm["net_sales"] > 0:
        if pm["net"] < 0:
            out.append(_alert("alta", "Beneficio", "El mes pasado cerraste con pérdidas",
                              f"Beneficio neto {money(pm['net'])}: ventas netas {money(pm['net_sales'])}, "
                              f"gastos {money(pm['opex'])}.", "expenses"))
        elif pm["opex"] / pm["net_sales"] * 100 > float(s.get("alert_expense_pct", 40) or 40):
            out.append(_alert("media", "Gastos", "Los gastos se comen gran parte de las ventas",
                              f"El mes pasado los gastos fueron el {pm['opex'] / pm['net_sales'] * 100:.0f} % de "
                              "las ventas netas. Revisa los gastos fijos.", "expenses"))

    # 8. Thin margins on products that sell.
    month_lines = lines[lines["created_at"] >= now - timedelta(days=30)]
    sold_ids = set(month_lines["product_id"])
    priced = products[(products["active"] == 1) & (products["price"] > 0) & (products["cost"] > 0)
                      & products["id"].isin(sold_ids)]
    thin = priced[(_net(priced) - priced["cost"]) / _net(priced) * 100 < float(s.get("alert_margin_pct", 25) or 25)]
    if not thin.empty:
        out.append(_alert("media", "Precios", f"{len(thin)} producto(s) vendidos con margen bajo",
                          f"{_names(thin['name'])}. Mira la sugerencia de precio en Inteligencia.", "intelligence"))

    # 9. Products that do not sell.
    if not month_lines.empty:
        idle = products[(products["active"] == 1) & ~products["id"].isin(sold_ids)]
        if not idle.empty:
            out.append(_alert("baja", "Catálogo", f"{len(idle)} producto(s) sin ventas en 30 días",
                              f"{_names(idle['name'])}. Valora destacarlos, ponerlos en promoción o retirarlos.",
                              "products"))
    return sorted(out, key=lambda a: LEVELS[a["level"]])


# ------------------------------------------------------------------ weekly report
def _change(cur: float, prev: float):
    return None if not prev else (cur - prev) / prev * 100


def weekly_numbers(sales: pd.DataFrame, lines: pd.DataFrame, refunds: pd.DataFrame, start: datetime) -> dict:
    """KPIs of the week starting `start` (a Monday) and of the week before, net of returns."""
    def week(lo, hi):
        done = sales[(sales["status"] == "completada") & (sales["created_at"] >= lo) & (sales["created_at"] < hi)]
        ln = lines[(lines["created_at"] >= lo) & (lines["created_at"] < hi)]
        back = refunds[(refunds["created_at"] >= lo) & (refunds["created_at"] < hi)]["total"].sum() \
            if not refunds.empty else 0.0
        revenue = float(done["total"].sum() - back)
        net = float(ln["revenue"].sum())
        return {"revenue": revenue, "net": net, "count": len(done), "ticket": revenue / len(done) if len(done) else 0.0,
                "margin": float(ln["margin"].sum()), "margin_pct": float(ln["margin"].sum() / net * 100) if net else 0.0,
                "refunds": float(back), "units": float(ln["quantity"].sum())}

    end = start + timedelta(days=7)
    cur, prev = week(start, end), week(start - timedelta(days=7), start)
    cur_sales = sales[(sales["status"] == "completada") & (sales["created_at"] >= start) & (sales["created_at"] < end)]
    by_day = []
    for i in range(7):
        d = start + timedelta(days=i)
        day = cur_sales[(cur_sales["created_at"] >= d) & (cur_sales["created_at"] < d + timedelta(days=1))]
        by_day.append((WEEKDAYS[d.weekday()].capitalize(), d, len(day), float(day["total"].sum())))
    cur_lines = lines[(lines["created_at"] >= start) & (lines["created_at"] < end)]
    top = (cur_lines.groupby("name").agg(units=("quantity", "sum"), revenue=("revenue", "sum"),
                                         margin=("margin", "sum"))
           .sort_values("revenue", ascending=False).head(10))
    team = (cur_sales[cur_sales["user_name"] != ""].groupby("user_name")["total"].agg(["count", "sum"])
            .sort_values("sum", ascending=False))
    return {"start": start, "end": end, "cur": cur, "prev": prev,
            "delta": {k: _change(cur[k], prev[k]) for k in ("revenue", "count", "ticket", "margin")},
            "by_day": by_day, "top": top, "team": team}


def recommendations(numbers: dict, alerts: list[dict], abc: pd.DataFrame, insights: list[tuple[str, str]]) -> list[str]:
    """A short to-do list for the coming week, in plain language."""
    out = []
    d = numbers["delta"]["revenue"]
    if d is not None and d <= -10:
        out.append("Las ventas bajaron respecto a la semana anterior: lanza una promoción en tus días flojos.")
    elif d is not None and d >= 10:
        out.append("Buena semana: mantén lo que ha funcionado y asegura stock de lo más vendido.")
    days = [x for x in numbers["by_day"] if x[3] > 0]
    if len(days) >= 3:
        worst = min(days, key=lambda x: x[3])
        best = max(days, key=lambda x: x[3])
        out.append(f"El {best[0].lower()} fue el mejor día y el {worst[0].lower()} el más flojo: ajusta turnos y "
                   "ofertas a ese ritmo.")
    a = abc[abc["abc"] == "A"]
    if not a.empty:
        out.append(f"Cuida tus productos clase A ({_names(a['name'], 3)}): nunca deben faltar ni bajar de precio.")
    for alert in alerts:
        if alert["level"] == "alta":
            out.append(f"{alert['title']}. {alert['detail']}")
    out += [msg for level, msg in insights if level == "warning"][:2]
    seen, unique = set(), []
    for item in out:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique[:7]
