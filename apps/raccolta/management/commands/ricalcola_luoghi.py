"""Ricalcola comune e provincia dei fatti con le regole di riconoscimento aggiornate.

    python manage.py ricalcola_luoghi --prova     # mostra cosa cambierebbe, senza salvare
    python manage.py ricalcola_luoghi

Non tocca i fatti già verificati da una persona. Usa il titolo e il testo dell'articolo di primo lancio
(il testo integrale resta disponibile solo per i giorni di conservazione; oltre si usa il titolo).
"""
from django.core.management.base import BaseCommand

from apps.fatti.models import Fatto, FattoArticolo
from apps.raccolta.servizi import luoghi
from apps.reati.choices import Precisione


class Command(BaseCommand):
    help = "Ricalcola comune e provincia dei fatti non verificati"

    def add_arguments(self, parser):
        parser.add_argument("--prova", action="store_true", help="Mostra le modifiche senza salvarle")

    def handle(self, prova=False, **opts):
        cambiati = 0
        qs = Fatto.objects.exclude(stato_revisione=Fatto.StatoRevisione.VERIFICATO).select_related("comune", "provincia")
        for fatto in qs.iterator():
            fa = (FattoArticolo.objects.filter(fatto=fatto).select_related("articolo__testata")
                  .order_by("-ruolo", "collegato_il").first())
            if not fa:
                continue
            articolo = fa.articolo
            versione = articolo.versioni.order_by("-controllato_il").first()
            testo = versione.testo_temporaneo if versione else ""
            nome = (versione.dati_estratti or {}).get("comune") if versione else None
            comune, provincia, area = luoghi.trova_luogo(nome, articolo.titolo, testo, articolo.testata)
            if (comune, provincia) == (fatto.comune, fatto.provincia):
                continue
            prima = fatto.comune or fatto.provincia or "—"
            dopo = comune or (f"provincia di {provincia.nome}" if provincia else "—")
            self.stdout.write(f"#{fatto.pk} {fatto.sintesi[:60]}: {prima} → {dopo}")
            cambiati += 1
            if prova:
                continue
            fatto.comune, fatto.provincia = comune, provincia
            fatto.quartiere = luoghi.trova_quartiere(comune, f"{articolo.titolo}\n{testo}")
            if comune:
                fatto.lat, fatto.lon, fatto.precisione = comune.lat, comune.lon, Precisione.COMUNE
            else:
                fatto.lat = fatto.lon = None
                fatto.precisione = Precisione.PROVINCIA if provincia else Precisione.NESSUNA
            if not fatto.luogo_testo and area:
                fatto.luogo_testo = area
            fatto.save()
        azione = "da cambiare" if prova else "aggiornati"
        self.stdout.write(self.style.SUCCESS(f"Fatti {azione}: {cambiati}"))
