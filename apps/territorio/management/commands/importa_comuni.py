"""Importa province e comuni dal CSV ufficiale ISTAT.

Senza argomenti scarica il file da ISTAT; in alternativa si passa il percorso di un CSV già scaricato
("Elenco comuni italiani", separatore ';', codifica latin-1).
"""
import csv
import io

from django.core.management.base import BaseCommand, CommandError

from apps.territorio.models import Comune, Provincia, Regione

URL_ISTAT = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv"


def _colonna(intestazioni, *frammenti):
    for i, nome in enumerate(intestazioni):
        n = nome.lower()
        if all(f in n for f in frammenti):
            return i
    raise CommandError(f"Colonna non trovata: {frammenti}")


class Command(BaseCommand):
    help = "Importa province e comuni dal CSV ISTAT"

    def add_arguments(self, parser):
        parser.add_argument("percorso_csv", nargs="?", help="CSV ISTAT già scaricato (facoltativo)")
        parser.add_argument("--encoding", default="latin-1")

    def handle(self, percorso_csv, encoding, **opts):
        if percorso_csv:
            with open(percorso_csv, encoding=encoding, newline="") as f:
                testo = f.read()
        else:
            import httpx

            self.stdout.write(f"Scarico {URL_ISTAT} ...")
            r = httpx.get(URL_ISTAT, timeout=60, follow_redirects=True)
            r.raise_for_status()
            testo = r.content.decode(encoding)
        righe = list(csv.reader(io.StringIO(testo), delimiter=";"))
        intest, dati = righe[0], righe[1:]
        c_reg = _colonna(intest, "codice regione")
        c_sigla = _colonna(intest, "sigla automobilistica")
        c_prov = _colonna(intest, "unità territoriale sovracomunale")
        c_cod = _colonna(intest, "codice comune formato alfanumerico")
        c_nome = _colonna(intest, "denominazione in italiano")
        try:
            c_capo = _colonna(intest, "capoluogo")
        except CommandError:
            c_capo = None

        regioni = {r.codice_istat: r for r in Regione.objects.all()}
        if not regioni:
            raise CommandError("Eseguire prima: python manage.py carica_dati_base")

        nuovi = 0
        for r in dati:
            if len(r) <= max(c_reg, c_sigla, c_prov, c_cod, c_nome):
                continue
            regione = regioni.get(r[c_reg].zfill(2))
            if not regione:
                continue
            provincia, _ = Provincia.objects.get_or_create(
                sigla=r[c_sigla], defaults={"nome": r[c_prov], "regione": regione}
            )
            capoluogo = c_capo is not None and r[c_capo].strip() == "1"
            # prima per codice ISTAT, poi per nome nella provincia (comuni inseriti a mano)
            comune = (Comune.objects.filter(codice_istat=r[c_cod]).first()
                      or Comune.objects.filter(nome__iexact=r[c_nome], provincia=provincia).first())
            creato = comune is None
            if creato:
                comune = Comune(provincia=provincia)
            comune.nome, comune.codice_istat, comune.provincia, comune.capoluogo = r[c_nome], r[c_cod], provincia, capoluogo
            comune.save()
            nuovi += creato
        self.stdout.write(self.style.SUCCESS(f"Comuni importati: {nuovi} nuovi, {len(dati)} righe lette"))
