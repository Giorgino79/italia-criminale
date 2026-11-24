from datetime import datetime, timezone

import pytest
from django.core.cache import cache
from django.core.management import call_command

from apps.fatti.models import Caso, Fatto
from apps.fonti.models import Articolo
from apps.raccolta.servizi.pipeline import elabora_articolo

from .conftest import finto_scaricatore

OGGI = datetime(2026, 11, 24, 9, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def niente_geocoding(monkeypatch):
    monkeypatch.setattr("apps.raccolta.servizi.luoghi.geocodifica", lambda luogo, comune, provincia=None: (None, None, "comune"))


@pytest.fixture(autouse=True)
def senza_casi_iniziali(db):
    # la migrazione 0007 crea già Garlasco, via D'Amelio e Superbonus: qui si parte da zero
    assert Caso.objects.filter(slug__in=["garlasco", "via-damelio", "superbonus"]).count() == 3
    assert not Caso.objects.filter(riassunto_verificato=True).exists()
    Caso.objects.all().delete()


@pytest.fixture
def garlasco(db):
    return Caso.objects.create(nome="Delitto di Garlasco", slug="garlasco", parole_chiave="garlasco\nchiara poggi\nsempio",
                               parole_escluse="calcio", sottotitolo="L'omicidio di Chiara Poggi")


def _art(testata, n, titolo):
    return Articolo.objects.create(testata=testata, url=f"https://example.org/c{n}", titolo=titolo, pubblicato_il=OGGI)


def test_corrispondenza_parole_chiave(garlasco):
    assert garlasco.corrisponde("Garlasco, nuova perizia sulle impronte")
    assert garlasco.corrisponde("Sempio di nuovo in procura")
    assert garlasco.corrisponde("L’omicidio di Chiara Poggi, i genitori")
    assert not garlasco.corrisponde("Garlasco, la squadra di calcio vince")
    assert not garlasco.corrisponde("Rapina a Pavia")


def test_articolo_non_reato_si_collega_comunque(dati_base, garlasco):
    a = _art(dati_base["testata"], 1, "x")
    elabora_articolo(a, scarica=finto_scaricatore("Garlasco, parla la madre di Chiara Poggi", "Intervista televisiva."))
    assert list(a.casi.all()) == [garlasco]


def test_tema_solo_reati(dati_base):
    tema = Caso.objects.create(nome="Truffe sul Superbonus", slug="superbonus", tipo="tema", parole_chiave="superbonus",
                               solo_reati=True)
    politica = _art(dati_base["testata"], 2, "x")
    elabora_articolo(politica, scarica=finto_scaricatore("Superbonus, il governo cambia le regole", "Il ministro ha detto."))
    truffa = _art(dati_base["testata"], 3, "x")
    elabora_articolo(truffa, scarica=finto_scaricatore(
        "Roma, truffa sul Superbonus da 10 milioni: sequestro della Guardia di Finanza",
        "La guardia di finanza ha sequestrato crediti fittizi per una truffa aggravata. Indagati dalla procura."))
    assert list(tema.articoli.all()) == [truffa]
    assert tema.reati().count() == 1


def test_pagine_e_home(client, dati_base, garlasco):
    a = _art(dati_base["testata"], 4, "Garlasco, la procura chiude le indagini")
    garlasco.articoli.add(a)
    garlasco.riassunto = "Primo paragrafo.\n\nSecondo paragrafo."
    garlasco.save()
    home = client.get("/").content.decode()
    assert "Casi seguiti" in home and "/casi/garlasco/" in home
    pagina = client.get("/casi/garlasco/").content.decode()
    assert "Garlasco, la procura chiude le indagini" in pagina and "1 da 1 testata" in pagina
    assert "Primo paragrafo" not in pagina  # bozza non verificata: nascosta al pubblico
    garlasco.riassunto_verificato = True
    garlasco.save()
    assert "Secondo paragrafo" in client.get("/casi/garlasco/").content.decode()
    cache.clear()  # la sitemap è in cache per un'ora
    assert "/casi/garlasco/" in client.get("/sitemap.xml").content.decode()
    assert client.get("/casi/").status_code == 200


def test_comando_collega_casi(dati_base, garlasco):
    _art(dati_base["testata"], 5, "Garlasco, udienza rinviata")
    _art(dati_base["testata"], 6, "Furto a Milano")
    call_command("collega_casi", verbosity=0)
    assert garlasco.articoli.count() == 1
    assert Fatto.objects.count() == 0
