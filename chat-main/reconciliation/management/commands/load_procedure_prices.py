import json
from pathlib import Path
from typing import Any, Dict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reconciliation.models import PriceCatalog, ProcedurePrice
from decimal import Decimal, InvalidOperation


def norm_code(code: str | None) -> str:
    if not code:
        return ""
    s = str(code)
    # Keep only digits for normalized lookup
    digits = ''.join(ch for ch in s if ch.isdigit())
    return digits or s.strip()


def parse_money_any(val: Any) -> Decimal:
    """Parse a money value that may come in pt-BR (1.234,56), en-US (1,234.56),
    plain numbers (98.45) or strings with currency symbols. Returns a Decimal.
    """
    if val is None:
        return Decimal('0.00')
    # If already numeric, convert safely to Decimal via str to avoid float issues
    if isinstance(val, (int, float, Decimal)):
        try:
            return Decimal(str(val))
        except InvalidOperation as e:
            raise CommandError(f"Não foi possível converter valor numérico: {val!r} - {e}")

    s = str(val).strip()
    if not s:
        return Decimal('0.00')
    # Remove currency and spaces
    s = s.replace('R$', '').replace('\u00a0', ' ').replace('\xa0', ' ').strip()
    # Handle negative formats like 123,45- or (123,45)
    neg = False
    if s.endswith('-'):
        neg = True
        s = s[:-1].strip()
    if s.startswith('(') and s.endswith(')'):
        neg = True
        s = s[1:-1].strip()

    # Remove any non-digit/sep/decimal characters (keep digits, comma, dot)
    allowed = set('0123456789.,')
    s = ''.join(ch for ch in s if ch in allowed)

    # Decide format
    has_comma = ',' in s
    has_dot = '.' in s
    if has_comma and has_dot:
        # If last comma appears after last dot, assume pt-BR: 1.234,56
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '')
            s = s.replace(',', '.')
        else:
            # en-US: 1,234.56
            s = s.replace(',', '')
            # keep '.' as decimal
    elif has_comma and not has_dot:
        # pt-BR: 123,45 or 1.234,56 (dots were removed above only if both existed)
        s = s.replace('.', '')
        s = s.replace(',', '.')
    else:
        # en-US or plain: remove thousands commas just in case
        s = s.replace(',', '')

    try:
        v = Decimal(s)
    except InvalidOperation:
        raise CommandError(f"Não foi possível converter valor: {val!r}")
    return -v if neg else v


class Command(BaseCommand):
    help = "Carrega um catálogo de preços de procedimentos a partir de um JSON."

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Caminho do arquivo JSON')
        parser.add_argument('--name', required=False, help='Nome do catálogo')
        # Evita conflito com --version global do manage.py
        parser.add_argument('--catalog-version', '--cat-version', dest='catalog_version', required=False, help='Versão/identificador do catálogo')
        parser.add_argument('--competencia', required=False, help='Competência (ex.: 07/2025)')
        parser.add_argument('--replace', action='store_true', help='Apaga preços existentes do catálogo antes de carregar')

    def handle(self, *args, **opts):
        path = Path(opts['file'])
        if not path.exists():
            raise CommandError(f"Arquivo não encontrado: {path}")

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            raise CommandError(f"Falha ao ler JSON: {e}")

        if isinstance(data, dict):
            # Se vier como objeto com a lista em alguma chave, tente detectar
            for k in ['procedimentos', 'items', 'dados', 'data']:
                if k in data and isinstance(data[k], list):
                    data = data[k]
                    break
            else:
                # Se for um dict de codigo -> {campos}
                data = [ { 'codigo': k, **(v or {}) } for k, v in data.items() ]

        # Suporte a fixture Django: lista de objetos com {'model', 'fields'}
        if isinstance(data, list) and data and isinstance(data[0], dict) and 'model' in data[0] and 'fields' in data[0]:
            data = [ (row.get('fields') or {}) for row in data if isinstance(row, dict) ]

        if not isinstance(data, list):
            raise CommandError('Formato do JSON não reconhecido: esperado lista de objetos')

        catalog = PriceCatalog.objects.create(
            name=opts.get('name') or f"Catálogo {path.stem}",
            version=opts.get('catalog_version') or '',
            competencia=opts.get('competencia') or '',
            source_file=str(path),
        )

        key_map_variants = {
            'codigo': ['codigo', 'código', 'tuss', 'cod', 'cd', 'codigo_tuss'],
            'descricao': ['descricao', 'descrição', 'procedimento', 'nome'],
            'convenio': ['convenio', 'convênio', 'plano'],
            'hospital_cnpj': ['hospital_cnpj', 'cnpj', 'cnpj_hospital'],
            'hospital_nome': ['hospital_nome', 'hospital', 'nome_hospital', 'hospital_clinica'],
            'categoria': ['categoria', 'setor', 'acomodacao'],
            'funcao': ['funcao', 'função'],
            'preco': ['preco', 'preço', 'valor', 'valor_referencia', 'valor referencia', 'vr'],
            'vigencia_inicio': ['vigencia_inicio', 'inicio', 'dt_inicio', 'data_inicio'],
            'vigencia_fim': ['vigencia_fim', 'fim', 'dt_fim', 'data_fim'],
        }

        def pick(obj: Dict[str, Any], key: str) -> Any:
            for variant in key_map_variants[key]:
                for actual in obj.keys():
                    if actual.strip().lower() == variant:
                        return obj.get(actual)
            return None

        created = 0
        with transaction.atomic():
            if opts.get('replace'):
                ProcedurePrice.objects.filter(catalog=catalog).delete()
            for row in data:
                if not isinstance(row, dict):
                    continue
                codigo_raw = pick(row, 'codigo') or row.get('codigo') or row.get('código')
                codigo_norm = norm_code(codigo_raw)
                if not codigo_norm:
                    continue
                descricao = pick(row, 'descricao') or ''
                convenio = pick(row, 'convenio') or ''
                categoria = pick(row, 'categoria') or ''
                hosp_cnpj_raw = pick(row, 'hospital_cnpj') or ''
                hosp_cnpj = ''.join(ch for ch in str(hosp_cnpj_raw) if ch.isdigit())
                hosp_nome = pick(row, 'hospital_nome') or ''
                funcao = pick(row, 'funcao') or ''
                preco_val = pick(row, 'preco')
                if preco_val is None:
                    # tente campo 'valor' literal
                    preco_val = row.get('valor')
                preco = parse_money_any(preco_val)

                vi = pick(row, 'vigencia_inicio')
                vf = pick(row, 'vigencia_fim')
                # datas são opcionais; armazenar como texto em metadata se não parsearmos agora

                # Exigir pelo menos as 4 chaves principais (plano, hospital, categoria, codigo)
                if not (convenio and (hosp_cnpj or hosp_nome) and categoria and codigo_norm):
                    # ainda assim criaremos registro se desejado, mas por padrão vamos exigir as 4
                    pass

                ProcedurePrice.objects.create(
                    catalog=catalog,
                    codigo=codigo_norm,
                    codigo_original=str(codigo_raw or ''),
                    descricao=str(descricao or ''),
                    convenio=str(convenio or ''),
                    hospital_cnpj=str(hosp_cnpj or ''),
                    hospital_nome=str(hosp_nome or ''),
                    categoria=str(categoria or ''),
                    funcao=str(funcao or ''),
                    preco_referencia=preco,
                    metadata={'raw': row, 'vigencia_inicio': vi, 'vigencia_fim': vf},
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Catálogo '{catalog}' criado com {created} preços."))
