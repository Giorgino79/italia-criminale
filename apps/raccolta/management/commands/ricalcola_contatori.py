from django.core.management.base import BaseCommand

from apps.fatti.models import Fatto


class Command(BaseCommand):
    help = "Ricalcola il numero di testate e articoli di ogni fatto"

    def handle(self, **opts):
        n = 0
        for fatto in Fatto.objects.all().iterator():
            fatto.aggiorna_contatori()
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Contatori aggiornati: {n} fatti"))
