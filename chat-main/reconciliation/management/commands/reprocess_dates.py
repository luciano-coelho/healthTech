from django.core.management.base import BaseCommand
from django.db import transaction
from pathlib import Path

from reconciliation.models import RemittanceHeader, RemittanceItem
from reconciliation.services import parse_pdf


class Command(BaseCommand):
    help = "Reprocessa PDFs originais para atualizar datas dos itens (e demais campos caso necessário)."

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Reprocessa todos os headers, não apenas os que possuem itens sem data.')
        parser.add_argument('--ids', type=str, help='Lista de IDs de headers separados por vírgula para reprocessar.')

    def handle(self, *args, **options):
        qs = RemittanceHeader.objects.all()
        if options.get('ids'):
            try:
                ids = [int(x) for x in options['ids'].split(',') if x.strip()]
            except ValueError:
                self.stderr.write(self.style.ERROR('IDs inválidos.'))
                return
            qs = qs.filter(id__in=ids)
        elif not options.get('all'):
            # Somente com itens sem data
            qs = qs.filter(items__data__exact='').distinct()

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('Nenhum header para reprocessar.'))
            return

        processed = 0
        for hdr in qs.iterator():
            if not hdr.original_file:
                self.stderr.write(self.style.WARNING(f'Header {hdr.id} sem arquivo original. Pulando.'))
                continue
            pdf_path = Path(hdr.original_file.path)
            try:
                parsed_header, items = parse_pdf(pdf_path)
                # Mantemos os dados do header existente; apenas substituímos os itens
                with transaction.atomic():
                    RemittanceItem.objects.filter(header=hdr).delete()
                    RemittanceItem.objects.bulk_create([
                        RemittanceItem(
                            header=hdr,
                            atendimento=i.atendimento,
                            conta=i.conta,
                            paciente=i.paciente,
                            convenio=i.convenio,
                            categoria=i.categoria,
                            data=i.data,
                            codigo=i.codigo,
                            procedimento=i.procedimento,
                            funcao=i.funcao,
                            quantidade=i.quantidade,
                            valor_produzido=i.valor_produzido,
                            imposto=i.imposto,
                            valor_liquido=i.valor_liquido,
                        ) for i in items
                    ])
                processed += 1
                self.stdout.write(self.style.SUCCESS(f'Reprocessado header {hdr.id} ({len(items)} itens).'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Falha ao reprocessar header {hdr.id}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Concluído. {processed}/{total} headers reprocessados.'))
