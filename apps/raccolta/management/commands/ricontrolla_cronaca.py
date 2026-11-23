"""Riesamina i fatti già registrati con le regole attuali del classificatore e scarta quelli che non sono reati.

    python manage.py ricontrolla_cronaca --prova
    python manage.py ricontrolla_cronaca

Un fatto resta se almeno uno dei suoi articoli supera le regole. Non tocca i fatti verificati da una persona
né quelli classificati dal modello (LLM). Il testo integrale è disponibile solo per i giorni di conservazione:
per gli articoli più vecchi si usa il titolo.
"""
from django.core.management.base import BaseCommand

from apps.fatti.models import Fatto, Revisione
from apps.raccolta.servizi.estrazione import NON_FATTO, estrai_con_parole_chiave


class Command(BaseCommand):
    help = "Scarta i fatti che con le regole attuali non risultano cronaca di reati"

    def add_arguments(self, parser):
        parser.add_argument("--prova", action="store_true")

    def handle(self, prova=False, **opts):
        scartati = 0
        for fatto in Fatto.objects.pubblicati().exclude(stato_revisione=Fatto.StatoRevisione.VERIFICATO):
            esiti = []
            for articolo in fatto.articoli.all():
                versione = articolo.versioni.order_by("-controllato_il").first()
                if versione and (versione.dati_estratti or {}).get("metodo") == "llm":
                    esiti.append(True)
                    continue
                testo = versione.testo_temporaneo if versione else ""
                if NON_FATTO.search(articolo.titolo or ""):
                    esiti.append(False)
                else:
                    esiti.append(bool(estrai_con_parole_chiave(articolo.titolo, testo, articolo.url)["is_crime_news"]))
            if esiti and not any(esiti):
                scartati += 1
                self.stdout.write(f"#{fatto.pk} {fatto.sintesi[:100]}")
                if not prova:
                    fatto.stato_revisione = Fatto.StatoRevisione.SCARTATO
                    fatto.save(update_fields=["stato_revisione"])
                    Revisione.objects.create(fatto=fatto, esito=Fatto.StatoRevisione.SCARTATO,
                                             modifiche="Riesame automatico: non risulta cronaca di un reato")
        self.stdout.write(self.style.SUCCESS(f"Fatti {'da scartare' if prova else 'scartati'}: {scartati}"))
