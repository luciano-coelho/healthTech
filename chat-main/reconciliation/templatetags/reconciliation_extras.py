from django import template
from decimal import Decimal, InvalidOperation

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
