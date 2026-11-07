"""Stacca un articolo da un fatto (es. dopo un'unione sbagliata) e lo rielabora da capo.

    python manage.py separa_articolo --fatto 25 --cerca "Ciampino"
"""
from django.core.management.base import BaseCommand, CommandError

from apps.fatti.models import Fatto, FattoArticolo
from apps.fonti.models import Articolo
from apps.raccolta.servizi.pipeline import elabora_articolo


class Command(BaseCommand):
    help = "Stacca da un fatto gli articoli il cui titolo contiene un testo e li rielabora"

    def add_arguments(self, parser):
        parser.add_argument("--fatto", type=int, required=True)
        parser.add_argument("--cerca", required=True, help="Parte del titolo dell'articolo da staccare")

    def handle(self, fatto, cerca, **opts):
        try:
            f = Fatto.objects.get(pk=fatto)
        except Fatto.DoesNotExist as e:
            raise CommandError(f"Fatto #{fatto} non trovato") from e
        legami = FattoArticolo.objects.filter(fatto=f, articolo__titolo__icontains=cerca).select_related("articolo")
        if not legami:
            raise CommandError(f"Nessun articolo del fatto #{fatto} contiene «{cerca}» nel titolo")
        for legame in legami:
            articolo = legame.articolo
            legame.delete()
            Articolo.objects.filter(pk=articolo.pk).update(stato=Articolo.Stato.NUOVO)
            articolo.refresh_from_db()
            articolo.versioni.all().delete()  # rielaborazione completa
            nuovo = elabora_articolo(articolo)
            dove = f"fatto #{nuovo.pk}" if nuovo else "non classificato come cronaca"
            self.stdout.write(f"Staccato «{articolo.titolo[:70]}» → {dove}")
        f.aggiorna_contatori()
        self.stdout.write(self.style.SUCCESS(f"Fatto #{f.pk}: ora {f.n_articoli} articoli"))
