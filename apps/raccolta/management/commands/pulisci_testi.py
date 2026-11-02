from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.fonti.models import VersioneArticolo


class Command(BaseCommand):
    help = "Cancella il testo integrale degli articoli più vecchi del periodo di conservazione"

    def handle(self, **opts):
        limite = timezone.now() - timedelta(days=settings.RACCOLTA["CONSERVA_TESTO_GIORNI"])
        n = VersioneArticolo.objects.filter(controllato_il__lt=limite).exclude(testo_temporaneo="").update(testo_temporaneo="")
        self.stdout.write(self.style.SUCCESS(f"Testi cancellati: {n}"))
