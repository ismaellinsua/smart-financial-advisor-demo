"""Pure pricing logic, independent of storage and UI."""

from decimal import ROUND_HALF_UP, Decimal


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_totals(lines, discount_pct: float = 0.0, tax_rate: float = 0.0) -> dict:
    """Compute sale totals.

    `lines` is an iterable of dicts with `quantity` and `unit_price` (prices exclude tax).
    The discount is a percentage over the subtotal; tax applies to the discounted base.
    """
    if not 0 <= discount_pct <= 100:
        raise ValueError("El descuento debe estar entre 0 y 100 %.")
    if tax_rate < 0:
        raise ValueError("El impuesto no puede ser negativo.")

    subtotal = sum((_money(l["unit_price"]) * int(l["quantity"]) for l in lines), Decimal("0"))
    subtotal = _money(subtotal)
    discount = _money(subtotal * Decimal(str(discount_pct)) / 100)
    base = subtotal - discount
    tax = _money(base * Decimal(str(tax_rate)) / 100)
    total = base + tax
    return {
        "subtotal": float(subtotal),
        "discount": float(discount),
        "tax": float(tax),
        "total": float(total),
    }


def format_money(amount: float, symbol: str = "€") -> str:
    """Spanish-style formatting: 1.234,56 €"""
    text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} {symbol}"
