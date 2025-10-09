from django.core.management.base import BaseCommand
from django.db import models
from reconciliation.models import RemittanceItem


class Command(BaseCommand):
    help = "Lista itens onde o código coincide com o atendimento ou conta (possível duplicação indevida)."

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50, help='Limite de linhas a exibir')

    def handle(self, *args, **options):
        qs = RemittanceItem.objects.filter(codigo__isnull=False).exclude(codigo='')
        qs = qs.filter(models.Q(codigo=models.F('atendimento')) | models.Q(codigo=models.F('conta')))
        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('Nenhum item com colisão de código/atendimento/conta.'))
            return
        self.stdout.write(self.style.WARNING(f'Encontrados {count} itens com possível colisão. Exibindo até {options["limit"]}:'))
        for it in qs.select_related('header').order_by('-id')[: options['limit']]:
            self.stdout.write(f"#{it.id} Header {it.header_id} Data {it.data} Paciente {it.paciente} Atend {it.atendimento} Conta {it.conta} Código {it.codigo}")
