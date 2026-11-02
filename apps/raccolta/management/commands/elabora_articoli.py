from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.fonti.models import Articolo
from apps.raccolta.servizi.pipeline import elabora_articolo


class Command(BaseCommand):
    help = "Elabora gli articoli nuovi e ricontrolla quelli in scadenza (traccia gli aggiornamenti)"

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=100)

    def handle(self, limite, **opts):
        da_fare = Articolo.objects.filter(
            Q(stato=Articolo.Stato.NUOVO) | Q(prossimo_controllo__lte=timezone.now())
        ).exclude(stato=Articolo.Stato.NON_CRONACA).order_by("prossimo_controllo")[:limite]
        fatti = 0
        for articolo in da_fare:
            fatto = elabora_articolo(articolo)
            fatti += fatto is not None
            self.stdout.write(f"[{articolo.stato}] {articolo.titolo[:80]}")
        self.stdout.write(self.style.SUCCESS(f"Articoli elaborati: {len(da_fare)} · collegati a fatti: {fatti}"))
