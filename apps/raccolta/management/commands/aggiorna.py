"""Aggiornamento completo per lo Scheduler: legge i feed ed elabora gli articoli in coda.

    python manage.py aggiorna                 # da mettere nello Scheduler ogni ora
    python manage.py aggiorna --limite 500

Una testata o un articolo in errore non fermano il resto: alla fine stampa un riepilogo.
"""
import time

from django.core.management.base import BaseCommand

from apps.fonti.models import Testata
from apps.raccolta.servizi.coda import da_elaborare
from apps.raccolta.servizi.feed import leggi_feed
from apps.raccolta.servizi.pipeline import elabora_articolo


class Command(BaseCommand):
    help = "Legge i feed di tutte le testate attive ed elabora gli articoli in coda"

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=400)

    def handle(self, limite, **opts):
        inizio = time.monotonic()
        nuovi = 0
        for t in Testata.objects.filter(attiva=True):
            try:
                nuovi += leggi_feed(t)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Testata {t.nome}: {e}"))
        elaborati = errori = fatti = 0
        for articolo in da_elaborare(limite):
            try:
                fatto = elabora_articolo(articolo)
                fatti += fatto is not None
                elaborati += 1
            except Exception as e:
                errori += 1
                self.stdout.write(self.style.WARNING(f"Articolo {articolo.pk}: {e}"))
                from apps.fonti.models import Articolo

                Articolo.objects.filter(pk=articolo.pk).update(
                    stato=Articolo.Stato.ERRORE, errore=str(e)[:500], prossimo_controllo=None
                )
        durata = round(time.monotonic() - inizio)
        self.stdout.write(self.style.SUCCESS(
            f"Aggiornamento completato in {durata}s: {nuovi} articoli nuovi dai feed, {elaborati} elaborati, "
            f"{fatti} collegati a fatti, {errori} errori"
        ))
