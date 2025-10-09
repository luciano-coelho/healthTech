from django import template
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

register = template.Library()


def _format_brl(value):
    if value is None:
        return 'R$ 0,00'
    try:
        v = float(value)
    except Exception:
        return 'R$ 0,00'
    s = f"{v:,.2f}"
    # US -> pt-BR swap
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"R$ {s}"


@register.filter(name='brl')
def brl(value):
    return _format_brl(value)


@register.filter(name='pct')
def pct(value):
    if value is None:
        return '-'
    try:
        v = float(value)
    except Exception:
        return '-'
    s = f"{v:,.2f}"
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"{s}%"


def _to_decimal(value) -> Decimal:
    if value in (None, ''):
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


@register.filter(name='sub')
def sub(value, arg):
    """Subtract arg from value, treating None/empty as 0 and keeping Decimal precision."""
    return _to_decimal(value) - _to_decimal(arg)


def _parse_br_date(s: str):
    """Parse dates like dd/mm or dd/mm/yy or dd/mm/yyyy. Returns datetime.date or None."""
    if not s:
        return None
    s = str(s).strip()
    fmts = ["%d/%m/%Y", "%d/%m/%y", "%d/%m"]
    for f in fmts:
        try:
            dt = datetime.strptime(s, f)
            # For dd/mm without year, assume current year first; if in future > 30 days, assume previous year
            if f == "%d/%m":
                today = datetime.today().date()
                candidate = dt.replace(year=today.year).date()
                if candidate - today > timedelta(days=30):
                    candidate = dt.replace(year=today.year - 1).date()
                return candidate
            return dt.date()
        except ValueError:
            continue
    return None


@register.filter(name='is_older_than_days')
def is_older_than_days(date_str, days=60):
    """Return True if the given BR date string is older than N days from today."""
    d = _parse_br_date(date_str)
    if not d:
        return False
    try:
        n = int(days)
    except Exception:
        n = 60
    today = datetime.today().date()
    return (today - d).days > n
