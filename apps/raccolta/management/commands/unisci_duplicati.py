"""Trova e unisce i fatti che raccontano lo stesso episodio, con le regole di somiglianza attuali.

    python manage.py unisci_duplicati --prova    # mostra le coppie, senza modificare
    python manage.py unisci_duplicati

I fatti già verificati da una persona non vengono uniti in automatico (si uniscono da /admin).
"""
from django.core.management.base import BaseCommand

from apps.fatti.models import Fatto
from apps.fatti.servizi import unisci
from apps.raccolta.servizi import deduplica


class Command(BaseCommand):
    help = "Unisce i fatti duplicati"

    def add_arguments(self, parser):
        parser.add_argument("--prova", action="store_true")

    def handle(self, prova=False, **opts):
        uniti = set()
        coppie = 0
        fatti = Fatto.objects.exclude(stato_revisione=Fatto.StatoRevisione.VERIFICATO).order_by("creato_il")
        for fatto in fatti:
            if fatto.pk in uniti:
                continue
            titoli = "\n".join([fatto.sintesi] + list(fatto.articoli.values_list("titolo", flat=True)[:5]))
            slugs = list(fatto.categorie.values_list("slug", flat=True))
            trova = deduplica.trova_fatto_per_seguito if fatto.data_evento is None else deduplica.trova_fatto_esistente
            kwargs = {"data_evento": fatto.data_evento} if fatto.data_evento else {}
            originale = trova(comune=fatto.comune, provincia=fatto.provincia, categorie_slug=slugs,
                              testo_confronto=titoli, salta=fatto.pk, **kwargs)
            if originale is None or originale.pk in uniti or originale.creato_il > fatto.creato_il:
                continue
            coppie += 1
            self.stdout.write(f"#{fatto.pk} «{fatto.sintesi[:60]}» → #{originale.pk} «{originale.sintesi[:60]}»")
            if not prova:
                unisci(originale, [fatto])
                uniti.add(fatto.pk)
        azione = "da unire" if prova else "uniti"
        self.stdout.write(self.style.SUCCESS(f"Duplicati {azione}: {coppie}"))
