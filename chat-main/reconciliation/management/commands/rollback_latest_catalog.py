from django.core.management.base import BaseCommand
from reconciliation.models import PriceCatalog, ProcedurePrice


class Command(BaseCommand):
    help = 'Remove o catálogo de preços mais recente (rollback para o anterior).'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Confirma a exclusão sem perguntar')

    def handle(self, *args, **opts):
        latest = PriceCatalog.objects.order_by('-id').first()
        if not latest:
            self.stdout.write(self.style.WARNING('Nenhum catálogo encontrado.'))
            return
        count_latest = ProcedurePrice.objects.filter(catalog=latest).count()
        self.stdout.write(f"Catálogo a remover: #{latest.id} {latest} (preços: {count_latest})")
        if not opts.get('yes'):
            self.stdout.write('Use --yes para confirmar.')
            return
        latest.delete()
        new_latest = PriceCatalog.objects.order_by('-id').first()
        new_count = ProcedurePrice.objects.filter(catalog=new_latest).count() if new_latest else 0
        if new_latest:
            self.stdout.write(self.style.SUCCESS(f"Removido. Agora o catálogo ativo é #{new_latest.id}: {new_latest} (preços: {new_count})"))
        else:
            self.stdout.write(self.style.WARNING('Todos os catálogos foram removidos.'))
