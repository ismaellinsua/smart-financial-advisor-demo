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
def compute_totals(lines, discount_pct: float = 0.0, tax_rate: float = 0.0, loyalty_amount: float = 0.0) -> dict:
    """Compute sale totals.

    `lines` are dicts with `quantity`, `unit_price` (prices exclude tax) and optionally `line_discount`
    (promotions). Order: promotions per line, then the manual percentage discount, then the loyalty discount
    (`loyalty_amount` is the amount off the final, tax-included price), then tax on the remaining base.
    The result also allocates the final base to each line (`net_amounts`) so analytics add up exactly.
    """
    if not 0 <= discount_pct <= 100:
        raise ValueError("El descuento debe estar entre 0 y 100 %.")
    if tax_rate < 0:
        raise ValueError("El impuesto no puede ser negativo.")
    if loyalty_amount < 0:
        raise ValueError("El descuento por puntos no puede ser negativo.")

    gross_lines = [_money(_money(l["unit_price"]) * int(l["quantity"])) for l in lines]
    promo_lines = [min(_money(l.get("line_discount") or 0), g) for l, g in zip(lines, gross_lines)]
    subtotal = sum(gross_lines, Decimal("0"))
    promo = sum(promo_lines, Decimal("0"))
    after_promo = subtotal - promo
    manual = _money(after_promo * Decimal(str(discount_pct)) / 100)
    after_manual = after_promo - manual
    rate = Decimal(str(tax_rate)) / 100
    loyalty = min(_money(Decimal(str(loyalty_amount)) / (1 + rate)), after_manual)
    base = after_manual - loyalty
    tax = _money(base * rate)
    total = base + tax

    # Spread the base over the lines in proportion to what each line contributes; the last takes the remainder.
    net_lines = [g - p for g, p in zip(gross_lines, promo_lines)]
    allocated, net_amounts = Decimal("0"), []
    for i, net in enumerate(net_lines):
        if i == len(net_lines) - 1:
            share = base - allocated
        else:
            share = _money(base * net / after_promo) if after_promo else Decimal("0")
            allocated += share
        net_amounts.append(float(share))
    return {
        "subtotal": float(subtotal),
        "promo_discount": float(promo),
        "manual_discount": float(manual),
        "loyalty_discount": float(loyalty),
        "discount": float(promo + manual + loyalty),
        "base": float(base),
        "tax": float(tax),
        "total": float(total),
        "net_amounts": net_amounts,
    }


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
