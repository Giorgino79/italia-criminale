from django.core.management.base import BaseCommand

from apps.fonti.models import Articolo
from apps.raccolta.servizi.coda import da_elaborare
from apps.raccolta.servizi.pipeline import elabora_articolo


class Command(BaseCommand):
    help = "Elabora gli articoli nuovi e ricontrolla quelli in scadenza (traccia gli aggiornamenti)"

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=100)

    def handle(self, limite, **opts):
        da_fare = da_elaborare(limite)
        fatti = 0
        for articolo in da_fare:
            try:
                fatti += elabora_articolo(articolo) is not None
            except Exception as e:
                Articolo.objects.filter(pk=articolo.pk).update(
                    stato=Articolo.Stato.ERRORE, errore=str(e)[:500], prossimo_controllo=None
                )
                self.stdout.write(self.style.WARNING(f"Articolo {articolo.pk}: {e}"))
        self.stdout.write(self.style.SUCCESS(f"Articoli elaborati: {len(da_fare)} · collegati a fatti: {fatti}"))
