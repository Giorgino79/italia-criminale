"""Elenca i procedimenti rimasti senza esito: base per la ricerca dei seguiti (anche manuale).

Esempio: python manage.py fatti_senza_esito --mesi 18 --csv da_seguire.csv
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.fatti.models import Fatto
from apps.reati.choices import FASI_IN_ATTESA


class Command(BaseCommand):
    help = "Elenca i fatti con arresto/denuncia/misura cautelare senza esito noto dopo N mesi"

    def add_arguments(self, parser):
        parser.add_argument("--mesi", type=int, default=12)
        parser.add_argument("--csv", help="Salva l'elenco in un file CSV")

    def handle(self, mesi, csv=None, **opts):
        limite = timezone.localdate() - timedelta(days=30 * mesi)
        qs = (Fatto.objects.pubblicati().filter(fase__in=FASI_IN_ATTESA, data_evento__lt=limite)
              .select_related("comune").order_by("data_evento"))
        righe = [(f.pk, f.data_evento, f.get_fase_display(), f.comune or "", f.sintesi) for f in qs]
        if csv:
            import csv as csvmod

            with open(csv, "w", newline="", encoding="utf-8") as fh:
                w = csvmod.writer(fh, delimiter=";")
                w.writerow(["ID", "Data", "Fase", "Comune", "Sintesi"])
                w.writerows(righe)
        for r in righe[:50]:
            self.stdout.write(" · ".join(str(x) for x in r))
        self.stdout.write(self.style.SUCCESS(f"Fatti in attesa di esito da oltre {mesi} mesi: {len(righe)}"))
