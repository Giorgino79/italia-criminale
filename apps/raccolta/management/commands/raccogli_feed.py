from django.core.management.base import BaseCommand

from apps.fonti.models import Testata
from apps.raccolta.servizi.feed import leggi_feed


class Command(BaseCommand):
    help = "Legge i feed RSS delle testate attive e registra gli articoli nuovi"

    def add_arguments(self, parser):
        parser.add_argument("--testata", help="Nome della testata (default: tutte le attive)")

    def handle(self, testata=None, **opts):
        testate = Testata.objects.filter(attiva=True)
        if testata:
            testate = testate.filter(nome__iexact=testata)
        totale = 0
        for t in testate:
            n = leggi_feed(t)
            totale += n
            self.stdout.write(f"{t.nome}: {n} articoli nuovi")
        self.stdout.write(self.style.SUCCESS(f"Totale articoli nuovi: {totale}"))
