from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.core.management import call_command

from apps.fatti.models import Fatto
from apps.fonti.models import Articolo
from apps.fonti.models import Testata as ModelloTestata

from .conftest import finto_scaricatore

ROMA = ZoneInfo("Europe/Rome")


def test_pagina_giorno(client, dati_base):
    Fatto.objects.create(sintesi="Rapina in centro", comune=dati_base["roma"], data_evento=date(2026, 11, 1))
    Fatto.objects.create(sintesi="Furto senza luogo", data_evento=date(2026, 11, 1))
    Fatto.objects.create(sintesi="Altro giorno", data_evento=date(2026, 10, 31))
    pagina = client.get("/giorno/2026-11-01/").content.decode()
    assert "Rapina in centro" in pagina and "Furto senza luogo" in pagina and "Altro giorno" not in pagina
    assert pagina.index("Lazio") < pagina.index("Luogo non individuato")
    assert client.get("/giorno/").status_code == 200
    assert client.get("/giorno/", {"d": "2026-11-01"}).status_code == 302
    assert client.get("/giorno/non-una-data/").status_code == 404


def test_raccogli_giorno(db, dati_base, monkeypatch):
    call_command("carica_testate", verbosity=0)
    assert ModelloTestata.objects.filter(tipo="nazionale").count() >= 10
    ansa = ModelloTestata.objects.get(nome="ANSA")

    def finto_feed(testata):
        if testata == ansa:
            Articolo.objects.get_or_create(url="https://ansa.example/1", defaults={
                "testata": ansa, "titolo": "Rapina a Roma", "pubblicato_il": datetime(2026, 11, 1, 10, tzinfo=ROMA)})
            Articolo.objects.get_or_create(url="https://ansa.example/2", defaults={
                "testata": ansa, "titolo": "Sagra", "pubblicato_il": datetime(2026, 11, 2, 0, 30, tzinfo=ROMA)})
        return 0

    monkeypatch.setattr("apps.raccolta.management.commands.raccogli_giorno.leggi_feed", finto_feed)
    monkeypatch.setattr("apps.raccolta.servizi.pipeline.testo.scarica", finto_scaricatore(
        "Rapina a Roma", "ROMA – Rapina in via Tuscolana, arrestato un uomo dai carabinieri."))
    monkeypatch.setattr("apps.raccolta.servizi.luoghi.geocodifica", lambda luogo, comune: (None, None, "comune"))
    call_command("raccogli_giorno", data=date(2026, 11, 1), verbosity=0)
    fatto = Fatto.objects.get(data_evento=date(2026, 11, 1))
    assert fatto.comune.nome == "Roma" and fatto.fase == "arresto"
    assert Articolo.objects.get(url="https://ansa.example/2").stato == "nuovo"  # altro giorno: non elaborato
