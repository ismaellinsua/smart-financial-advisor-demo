"""Pure pricing logic, independent of storage and UI."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- promotions
PROMO_KINDS = {"porcentaje": "Descuento %", "nxm": "Lleva N, paga M"}
PROMO_SCOPES = {"todo": "Todo", "categoria": "Categoría", "producto": "Producto"}


def promotion_active(promo: dict, when: datetime) -> bool:
    """Day-of-week and time window check. Windows may cross midnight (e.g. 22:00–02:00)."""
    if not promo.get("active", 1):
        return False
    days = str(promo.get("days") or "0123456")
    start, end = promo.get("start_time") or "", promo.get("end_time") or ""
    now = when.strftime("%H:%M")
    if not start or not end:
        return str(when.weekday()) in days
    if start <= end:
        return str(when.weekday()) in days and start <= now < end
    # After midnight the window belongs to the previous day's promotion.
    if now >= start:
        return str(when.weekday()) in days
    return now < end and str((when.weekday() - 1) % 7) in days


def _matches(promo: dict, line: dict) -> bool:
    scope, target = promo.get("scope"), str(promo.get("target") or "")
    if scope == "todo":
        return True
    if scope == "categoria":
        return line.get("category") == target
    if scope == "producto":
        return str(line.get("product_id")) == target
    return False


def _line_discount(promo: dict, line: dict) -> Decimal:
    qty, price = int(line["quantity"]), _money(line["unit_price"])
    if promo["kind"] == "porcentaje":
        pct = Decimal(str(promo["value"]))
        return _money(price * qty * pct / 100) if 0 < pct <= 100 else Decimal("0")
    if promo["kind"] == "nxm":
        n, m = int(promo["buy"]), int(promo["pay"])
        if n <= 0 or not 0 <= m < n:
            return Decimal("0")
        return _money(price * (qty // n) * (n - m))
    return Decimal("0")


def apply_promotions(lines: list[dict], promotions: list[dict], when: datetime) -> list[dict]:
    """Return a copy of `lines` with `line_discount` and `promo_name`: the best single promotion per line."""
    live = [p for p in promotions if promotion_active(p, when)]
    out = []
    for line in lines:
        best, best_name = Decimal("0"), ""
        for promo in live:
            if _matches(promo, line):
                amount = _line_discount(promo, line)
                if amount > best:
                    best, best_name = amount, promo["name"]
        out.append({**line, "line_discount": float(best), "promo_name": best_name})
    return out


# -------------------------------------------------------------------- totals
def _allocate(amount: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `amount` in proportion to `weights` in cents; the last share takes the remainder so it adds up."""
    total = sum(weights, Decimal("0"))
    shares, allocated = [], Decimal("0")
    for i, w in enumerate(weights):
        if i == len(weights) - 1:
            share = amount - allocated
        else:
            share = _money(amount * w / total) if total else Decimal("0")
            allocated += share
        shares.append(share)
    return shares


def compute_totals(lines, discount_pct: float = 0.0, tax_rate: float = 0.0, loyalty_amount: float = 0.0) -> dict:
    """Compute sale totals from shelf prices, which include VAT.

    `lines` are dicts with `quantity`, `unit_price` (VAT included, as on the menu or the label), optionally
    `tax_rate` (the product's VAT; `tax_rate` is the default) and `line_discount` (promotions). Order: promotions
    per line, then the manual percentage discount, then the loyalty discount (`loyalty_amount`, money off the
    final price). The total is what the customer pays, so a ticket always matches the menu; VAT is then broken
    down per rate (`taxes`), and each line gets its share of base and VAT so returns and analytics add up exactly.
    """
    if not 0 <= discount_pct <= 100:
        raise ValueError("El descuento debe estar entre 0 y 100 %.")
    if tax_rate < 0:
        raise ValueError("El impuesto no puede ser negativo.")
    if loyalty_amount < 0:
        raise ValueError("El descuento por puntos no puede ser negativo.")

    rates = [Decimal(str(l.get("tax_rate") if l.get("tax_rate") is not None else tax_rate)) for l in lines]
    if any(r < 0 for r in rates):
        raise ValueError("El impuesto no puede ser negativo.")
    gross_lines = [_money(_money(l["unit_price"]) * int(l["quantity"])) for l in lines]
    promo_lines = [min(_money(l.get("line_discount") or 0), g) for l, g in zip(lines, gross_lines)]
    after_promo = [g - p for g, p in zip(gross_lines, promo_lines)]
    subtotal, promo = sum(gross_lines, Decimal("0")), sum(promo_lines, Decimal("0"))
    after_promo_total = subtotal - promo
    manual = _money(after_promo_total * Decimal(str(discount_pct)) / 100)
    manual_lines = _allocate(manual, after_promo) if lines else []
    after_manual = [a - m for a, m in zip(after_promo, manual_lines)]
    loyalty = min(_money(loyalty_amount), after_promo_total - manual)
    loyalty_lines = _allocate(loyalty, after_manual) if lines else []
    final = [a - l for a, l in zip(after_manual, loyalty_lines)]
    total = sum(final, Decimal("0"))

    # VAT per rate on what is charged at that rate; each line then gets its share of that rate's base.
    taxes, net_amounts, tax_amounts = [], [Decimal("0")] * len(lines), [Decimal("0")] * len(lines)
    for rate in sorted(set(rates), reverse=True):
        idx = [i for i, r in enumerate(rates) if r == rate]
        gross = sum((final[i] for i in idx), Decimal("0"))
        base = _money(gross / (1 + rate / 100))
        for i, share in zip(idx, _allocate(base, [final[i] for i in idx])):
            net_amounts[i], tax_amounts[i] = share, final[i] - share
        taxes.append({"rate": float(rate), "base": float(base), "tax": float(gross - base), "total": float(gross)})
    base_total = sum((t["base"] for t in taxes), 0.0)
    return {
        "subtotal": float(subtotal),
        "promo_discount": float(promo),
        "manual_discount": float(manual),
        "loyalty_discount": float(loyalty),
        "discount": float(promo + manual + loyalty),
        "base": float(_money(base_total)),
        "tax": float(total - _money(base_total)),
        "total": float(total),
        "taxes": taxes,
        "net_amounts": [float(n) for n in net_amounts],
        "tax_amounts": [float(t) for t in tax_amounts],
        "gross_amounts": [float(f) for f in final],
    }


def tax_breakdown(items: list[dict], default_rate: float) -> list[dict]:
    """Base and VAT per rate of stored lines (sale or refund items: `net_amount`, `tax_amount`, `tax_rate`).

    Lines saved before per-product VAT have no `tax_amount`: they used the single rate of the sale."""
    groups: dict[Decimal, list[Decimal]] = {}
    for item in items:
        rate = Decimal(str(item["tax_rate"] if item.get("tax_rate") is not None else default_rate))
        base = _money(item.get("net_amount") or 0)
        tax = (_money(item["tax_amount"]) if item.get("tax_amount") is not None
               else _money(base * rate / 100))
        acc = groups.setdefault(rate, [Decimal("0"), Decimal("0")])
        acc[0] += base
        acc[1] += tax
    return [{"rate": float(r), "base": float(b), "tax": float(t), "total": float(b + t)}
            for r, (b, t) in sorted(groups.items(), reverse=True)]


def net_price(price: float, rate: float) -> float:
    """Shelf price without VAT (what the business keeps), for margins and price suggestions."""
    return float(Decimal(str(price)) / (1 + Decimal(str(rate)) / 100))


def split_evenly(total: float, people: int) -> list[float]:
    """Split an amount into `people` parts that add up exactly; the last part absorbs the rounding."""
    if people < 1:
        raise ValueError("Indica al menos una persona.")
    amount = _money(total)
    part = _money(amount / people)
    parts = [part] * (people - 1)
    return [float(p) for p in parts] + [float(amount - part * (people - 1))]


def format_money(amount: float, symbol: str = "€") -> str:
    """Spanish-style formatting: 1.234,56 €"""
    text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} {symbol}"


def format_money_short(amount: float, symbol: str = "€") -> str:
    """Compact figure for headline tiles: 1.234,56 € below 10.000; then 12,3 mil € and 1,2 M €."""
    if abs(amount) >= 1_000_000:
        return f"{amount / 1_000_000:.1f}".replace(".", ",") + f" M {symbol}"
    if abs(amount) >= 10_000:
        return f"{amount / 1_000:.1f}".replace(".", ",") + f" mil {symbol}"
    return format_money(amount, symbol)
