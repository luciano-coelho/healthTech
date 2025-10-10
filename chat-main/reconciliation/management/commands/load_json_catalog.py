from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from reconciliation.models import PriceCatalog, ProcedurePrice


def _digits(s: str) -> str:
    return ''.join(ch for ch in str(s or '') if ch.isdigit())


def _norm_text(s: str) -> str:
    return ' '.join(str(s or '').strip().split())


def _norm_categoria(s: str) -> str:
    txt = (s or '').strip().upper()
    if 'ENF' in txt:
        return 'Enfermaria'
    if 'APT' in txt or 'APART' in txt:
        return 'Apartamento'
    # Title-case fallback
    return (s or '').strip().title()


class Command(BaseCommand):
    help = 'Carrega um catálogo de preços a partir de um JSON no formato do anexo (procedimentos_30_registros.json).'

    def add_arguments(self, parser):
        parser.add_argument('json_path', type=str, help='Caminho do arquivo JSON')
        parser.add_argument('--name', type=str, default='Catálogo JSON', help='Nome do catálogo')
        # '--version' conflita com a flag global do Django; usar '--cat-version'
        parser.add_argument('--cat-version', type=str, default='', help='Versão opcional do catálogo')
        parser.add_argument('--competencia', type=str, default='', help='Competência opcional, ex: 2025-09')

    def handle(self, *args, **opts):
        path = Path(opts['json_path'])
        if not path.exists():
            raise CommandError(f"Arquivo não encontrado: {path}")

        with path.open('r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise CommandError(f"JSON inválido: {e}")

        if not isinstance(data, list):
            raise CommandError('JSON deve ser uma lista de objetos.')

        # Cria o catálogo
        catalog = PriceCatalog.objects.create(
            name=opts['name'],
            version=opts.get('cat_version') or '',
            competencia=opts.get('competencia') or '',
            source_file=str(path),
            notes='Importado via load_json_catalog.'
        )

        # Preparar deduplicação por (codigo, convenio, categoria, hospital): manter o MENOR preço
        best = {}  # key -> dict(fields)

        def parse_decimal(v):
            if v is None or v == '':
                return Decimal('0')
            try:
                return Decimal(str(v)).quantize(Decimal('0.01'))
            except (InvalidOperation, ValueError):
                # fallback: remove milhar e troca vírgula por ponto
                s = str(v)
                s = s.replace('.', '').replace(',', '.')
                return Decimal(s)

        for obj in data:
            fields = obj.get('fields') or {}
            convenio = _norm_text(fields.get('convenio') or '')
            hospital_nome = _norm_text(fields.get('hospital_clinica') or '')
            categoria = _norm_categoria(fields.get('acomodacao') or '')
            codigo_original = str(fields.get('codigo_tuss') or '').strip()
            codigo = _digits(codigo_original)
            descricao = fields.get('descricao') or ''
            preco = parse_decimal(fields.get('valor_referencia'))

            key = (codigo, convenio.lower(), categoria, hospital_nome.lower())
            prev = best.get(key)
            if (prev is None) or (preco is not None and preco < prev['preco']):
                best[key] = {
                    'codigo': codigo,
                    'codigo_original': codigo_original,
                    'descricao': descricao,
                    'convenio': convenio,
                    'hospital_nome': hospital_nome,
                    'categoria': categoria,
                    'preco': preco,
                }

        to_create = [
            ProcedurePrice(
                catalog=catalog,
                codigo=v['codigo'],
                codigo_original=v['codigo_original'],
                descricao=v['descricao'],
                convenio=v['convenio'],
                hospital_cnpj='',
                hospital_nome=v['hospital_nome'],
                categoria=v['categoria'],
                preco_referencia=v['preco'],
                ativo=True,
                metadata={'source': 'json'}
            )
            for v in best.values()
        ]
        with transaction.atomic():
            ProcedurePrice.objects.bulk_create(to_create, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f"Importados {len(to_create)} preços no catálogo #{catalog.id}: {catalog}"
        ))
