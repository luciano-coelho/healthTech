import json
from pathlib import Path
from typing import Any, Dict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reconciliation.models import PriceCatalog, ProcedurePrice


def norm_code(code: str | None) -> str:
    if not code:
        return ""
    s = str(code)
    # Keep only digits for normalized lookup
    digits = ''.join(ch for ch in s if ch.isdigit())
    return digits or s.strip()


def ptbr_to_decimal(val: Any) -> float:
    if val is None:
        return 0.0
    s = str(val).strip()
    if not s:
        return 0.0
    s = s.replace('R$', '').replace('\xa0', ' ').replace(' ', '')
    neg = False
    if s.endswith('-'):
        neg = True
        s = s[:-1]
    if s.startswith('(') and s.endswith(')'):
        neg = True
        s = s[1:-1]
    s = s.replace('.', '').replace(',', '.')
    try:
        v = float(s)
    except Exception:
        raise CommandError(f"Não foi possível converter valor: {val!r}")
    return -v if neg else v


class Command(BaseCommand):
    help = "Carrega um catálogo de preços de procedimentos a partir de um JSON."

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Caminho do arquivo JSON')
        parser.add_argument('--name', required=False, help='Nome do catálogo')
        parser.add_argument('--version', required=False, help='Versão/identificador do catálogo')
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

        if not isinstance(data, list):
            raise CommandError('Formato do JSON não reconhecido: esperado lista de objetos')

        catalog = PriceCatalog.objects.create(
            name=opts.get('name') or f"Catálogo {path.stem}",
            version=opts.get('version') or '',
            competencia=opts.get('competencia') or '',
            source_file=str(path),
        )

        key_map_variants = {
            'codigo': ['codigo', 'código', 'tuss', 'cod', 'cd'],
            'descricao': ['descricao', 'descrição', 'procedimento', 'nome'],
            'convenio': ['convenio', 'convênio', 'plano'],
            'categoria': ['categoria', 'setor'],
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
                funcao = pick(row, 'funcao') or ''
                preco_val = pick(row, 'preco')
                if preco_val is None:
                    # tente campo 'valor' literal
                    preco_val = row.get('valor')
                preco = ptbr_to_decimal(preco_val)

                vi = pick(row, 'vigencia_inicio')
                vf = pick(row, 'vigencia_fim')
                # datas são opcionais; armazenar como texto em metadata se não parsearmos agora

                ProcedurePrice.objects.create(
                    catalog=catalog,
                    codigo=codigo_norm,
                    codigo_original=str(codigo_raw or ''),
                    descricao=str(descricao or ''),
                    convenio=str(convenio or ''),
                    categoria=str(categoria or ''),
                    funcao=str(funcao or ''),
                    preco_referencia=preco,
                    metadata={'raw': row, 'vigencia_inicio': vi, 'vigencia_fim': vf},
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Catálogo '{catalog}' criado com {created} preços."))
