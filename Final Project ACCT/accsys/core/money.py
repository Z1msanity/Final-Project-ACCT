# money helpers and small utils

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import date

CENT = Decimal("0.01")


def to_cents(amount):
    if amount is None or amount == "":
        return 0
    return int((Decimal(str(amount)) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def from_cents(c):
    return (Decimal(int(c)) / 100).quantize(CENT)


def money(v):
    d = v if isinstance(v, Decimal) else from_cents(v)
    if d < 0:
        return f"({abs(d):,.2f})"
    return f"{d:,.2f}"


def valid_date(s):
    try:
        date.fromisoformat(str(s))
        return True
    except (ValueError, TypeError):
        return False


def parse_amount(s):
    if s is None or str(s).strip() == "":
        return Decimal("0")
    s = str(s).strip().replace(",", "").replace("$", "").replace("₱", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError(f"'{s}' is not a valid number")