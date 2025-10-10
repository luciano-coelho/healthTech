from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from reconciliation.models import ProcedurePrice


def parse_money_any(val: Any) -> Decimal:
    # Local copy to avoid import cycles; same logic as in load_procedure_prices
    from decimal import Decimal, InvalidOperation

    if val is None:
        return Decimal('0.00')
    if isinstance(val, (int, float, Decimal)):
        try:
            return Decimal(str(val))
        except InvalidOperation:
            return Decimal('0.00')

    s = str(val).strip()
    if not s:
        return Decimal('0.00')
    s = s.replace('R$', '').replace('\u00a0', ' ').replace('\xa0', ' ').strip()
    neg = False
    if s.endswith('-'):
        neg = True
        s = s[:-1].strip()
    if s.startswith('(') and s.endswith(')'):
        neg = True
        s = s[1:-1].strip()

    allowed = set('0123456789.,')
    s = ''.join(ch for ch in s if ch in allowed)

    has_comma = ',' in s
    has_dot = '.' in s
    if has_comma and has_dot:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '')
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    elif has_comma and not has_dot:
        s = s.replace('.', '')
        s = s.replace(',', '.')
    else:
        s = s.replace(',', '')

    try:
        v = Decimal(s)
    except Exception:
        v = Decimal('0.00')
    return -v if neg else v


class Command(BaseCommand):
    help = "Reprocessa os preços de ProcedurePrice usando o metadata.raw para corrigir 'preco_referencia' mal interpretado."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Apenas exibe o que seria alterado, sem salvar')
        parser.add_argument('--limit', type=int, default=0, help='Limita a quantidade de registros a processar (0 = todos)')

    def handle(self, *args, **opts):
        qs = ProcedurePrice.objects.all().order_by('id')
        limit = int(opts.get('limit') or 0)
        if limit:
            qs = qs[:limit]

        updated = 0
        examined = 0
        with transaction.atomic():
            for pp in qs:
                examined += 1
                raw = (pp.metadata or {}).get('raw') if pp.metadata else None
                preco_val = None
                if isinstance(raw, dict):
                    # Try common keys
                    for k in ['preco', 'preço', 'valor', 'valor_referencia', 'valor referencia', 'vr']:
                        if k in raw:
                            preco_val = raw.get(k)
                            break
                    # fallback
                    if preco_val is None and 'valor' in (raw or {}):
                        preco_val = raw.get('valor')

                if preco_val is None:
                    # No raw price; skip
                    continue

                new_price = parse_money_any(preco_val)
                if new_price != pp.preco_referencia:
                    if opts.get('dry_run'):
                        self.stdout.write(f"ID {pp.id}: {pp.preco_referencia} -> {new_price}")
                    else:
                        pp.preco_referencia = new_price
                        pp.save(update_fields=['preco_referencia'])
                    updated += 1

            if opts.get('dry_run'):
                # rollback transaction implicitly by raising exception? We won't; just no writes were made.
                pass

        self.stdout.write(self.style.SUCCESS(f"Examined: {examined}, Updated: {updated}"))
