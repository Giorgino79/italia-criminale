"""Scarta i "fatti" nati da rassegne e riepiloghi ("le notizie da sapere per iniziare la giornata"...).

    python manage.py scarta_rassegne --prova
    python manage.py scarta_rassegne
"""
from django.core.management.base import BaseCommand

from apps.fatti.models import Fatto, Revisione
from apps.raccolta.servizi.estrazione import NON_FATTO


class Command(BaseCommand):
    help = "Scarta i fatti i cui articoli sono tutti rassegne o riepiloghi"

    def add_arguments(self, parser):
        parser.add_argument("--prova", action="store_true")

    def handle(self, prova=False, **opts):
        n = 0
        for fatto in Fatto.objects.pubblicati().exclude(stato_revisione=Fatto.StatoRevisione.VERIFICATO):
            titoli = list(fatto.articoli.values_list("titolo", flat=True)) or [fatto.sintesi]
            if all(NON_FATTO.search(t or "") for t in titoli):
                n += 1
                self.stdout.write(f"#{fatto.pk} {fatto.sintesi[:90]}")
                if not prova:
                    fatto.stato_revisione = Fatto.StatoRevisione.SCARTATO
                    fatto.save(update_fields=["stato_revisione"])
                    Revisione.objects.create(fatto=fatto, esito=Fatto.StatoRevisione.SCARTATO,
                                             modifiche="Rassegna o riepilogo, non un singolo fatto")
        self.stdout.write(self.style.SUCCESS(f"Rassegne {'da scartare' if prova else 'scartate'}: {n}"))
