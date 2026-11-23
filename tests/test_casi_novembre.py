"""Casi reali del 21-22 novembre 2026: esteri, suicidi, politica, luoghi e duplicati."""
from datetime import datetime, timezone

import pytest

from apps.fatti.models import Fatto
from apps.fonti.models import Articolo, Testata
from apps.raccolta.servizi.estrazione import estrai_con_parole_chiave
from apps.raccolta.servizi.luoghi import trova_luogo
from apps.raccolta.servizi.pipeline import elabora_articolo
from apps.territorio.models import Comune, Provincia, Regione

from .conftest import finto_scaricatore

OGGI = datetime(2026, 11, 22, 9, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def niente_geocoding(monkeypatch):
    monkeypatch.setattr("apps.raccolta.servizi.luoghi.geocodifica", lambda luogo, comune, provincia=None: (None, None, "comune"))


@pytest.fixture
def luoghi(dati_base):
    reg = lambda n: Regione.objects.get(nome=n)  # noqa: E731
    tv = Provincia.objects.create(nome="Treviso", sigla="TV", regione=reg("Veneto"))
    ud = Provincia.objects.create(nome="Udine", sigla="UD", regione=reg("Friuli-Venezia Giulia"))
    bt = Provincia.objects.create(nome="Barletta-Andria-Trani", sigla="BT", regione=reg("Puglia"))
    ba = Provincia.objects.create(nome="Bari", sigla="BA", regione=reg("Puglia"))
    av = Provincia.objects.create(nome="Avellino", sigla="AV", regione=reg("Campania"))
    return {
        "treviso": Comune.objects.create(nome="Treviso", provincia=tv, capoluogo=True),
        "udine": Comune.objects.create(nome="Udine", provincia=ud, capoluogo=True),
        "trani": Comune.objects.create(nome="Trani", provincia=bt, capoluogo=True),
        "spinazzola": Comune.objects.create(nome="Spinazzola", provincia=bt),
        "bari": Comune.objects.create(nome="Bari", provincia=ba, capoluogo=True),
        "contrada": Comune.objects.create(nome="Contrada", provincia=av),
        "bt": bt,
    }


@pytest.mark.parametrize("titolo,testo,url", [
    ("Viene licenziato perché fuma in azienda e lui si vendica incendiando tutto: danni per 19 milioni di euro",
     "Un uomo voleva distruggere un edificio della società a Saint-Ouen-l'Aumone, in Francia. La polizia francese "
     "lo ha arrestato dopo l'incendio.", "https://www.today.it/europa/attualita/dipendente-incendia-azienda.html"),
    ("Spari dagli elicotteri, camion in fiamme e paura allo stadio: l'esercito messicano cattura El Chapo Isidro",
     "Il narcotrafficante è stato arrestato in Messico dopo uno scontro a fuoco.", "https://example.org/x"),
])
def test_reati_all_estero_esclusi(dati_base, titolo, testo, url):
    assert estrai_con_parole_chiave(titolo, testo, url)["is_crime_news"] is False


def test_italiano_con_straniero_resta(dati_base):
    dati = estrai_con_parole_chiave("Roma, rapina in farmacia: arrestato un cittadino francese",
                                    "I carabinieri hanno arrestato a Roma un uomo di nazionalità francese.")
    assert dati["is_crime_news"] is True


@pytest.mark.parametrize("titolo", [
    "L'ex capo della Polizia De Gennaro si è ucciso. Mantovano: \"Sconvolto\"",
    "Guido Contrada e il suicidio di De Gennaro: \"Ha lottato fino alla fine\"",
    "Multe per la pipì dei cani e strade della birra: cosa hanno proposto i parlamentari per la manovra",
    "Ballando in Italia senza trash non lo vedrebbe nessuno",
])
def test_non_reati(dati_base, titolo):
    testo = "Indagini della procura, il pm ha disposto l'autopsia. L'omicidio di mafia del 1992 e l'arresto del boss."
    assert estrai_con_parole_chiave(titolo, testo)["is_crime_news"] is False


def test_omicidio_suicidio_resta(dati_base):
    dati = estrai_con_parole_chiave("Uccide la moglie e poi si toglie la vita: omicidio-suicidio a Roma",
                                    "I carabinieri hanno trovato i corpi nell'abitazione.")
    assert dati["is_crime_news"] is True


def test_comune_nel_titolo_batte_copertura_testata(luoghi):
    testata = Testata.objects.create(nome="Friuli", url_home="https://friuli.example.org", feed=[])
    testata.comuni_copertura.add(luoghi["udine"])
    comune, _, _ = trova_luogo(None, "Ubriaco aggredisce sanitari al pronto soccorso di Treviso, arrestato",
                               "L'uomo è stato portato in carcere. Sul caso indaga la procura, come già accaduto a udine.",
                               testata)
    assert comune == luoghi["treviso"]


def test_nord_barese_e_bat(luoghi):
    _, provincia, _ = trova_luogo(None, "Auto si ribalta nel nord Barese, muore un 17enne", "Indagini in corso.")
    assert provincia == luoghi["bt"]


def test_cognome_non_e_comune(luoghi):
    comune, _, _ = trova_luogo(None, "Guido Contrada e il suicidio di De Gennaro",
                               "Le parole di Contrada. Guido Contrada ha ricordato l'amico.")
    assert comune is None


def test_luoghi_vicini_stesso_incidente_un_solo_fatto(luoghi):
    t1 = Testata.objects.create(nome="A", url_home="https://a.example.org", feed=[])
    t2 = Testata.objects.create(nome="B", url_home="https://b.example.org", feed=[])
    a1 = Articolo.objects.create(testata=t1, url="https://a.example.org/1", titolo="x", pubblicato_il=OGGI)
    a2 = Articolo.objects.create(testata=t2, url="https://b.example.org/1", titolo="x", pubblicato_il=OGGI)
    f1 = elabora_articolo(a1, scarica=finto_scaricatore(
        "Auto si ribalta a Spinazzola, morto un 17enne e tre feriti: omicidio stradale",
        "Il conducente è indagato per omicidio stradale dalla procura di Trani."))
    f2 = elabora_articolo(a2, scarica=finto_scaricatore(
        "Trani, auto si ribalta: morto un 17enne, tre feriti. Omicidio stradale",
        "Il conducente è indagato per omicidio stradale dalla procura di Trani."))
    assert f1 is not None and f1.pk == f2.pk
    assert Fatto.objects.count() == 1


def test_seo_sitemap_robots_canonico(client, dati_base):
    f = Fatto.objects.create(sintesi="Rapina in farmacia", data_evento=datetime(2026, 11, 20).date(), comune=dati_base["roma"])
    robots = client.get("/robots.txt").content.decode()
    assert "Disallow: /admin/" in robots and "Sitemap: https://www.osservatorioreati.it/sitemap.xml" in robots
    mappa = client.get("/sitemap.xml").content.decode()
    assert f"/fatti/{f.pk}/" in mappa and "/giorno/2026-11-20/" in mappa and "<loc>https://" in mappa
    pagina = client.get(f"/fatti/{f.pk}/").content.decode()
    assert f'rel="canonical" href="https://www.osservatorioreati.it/fatti/{f.pk}/"' in pagina
    assert 'name="description" content="Rapina in farmacia' in pagina
    assert "noindex" in client.get("/fatti/?regione=12").content.decode()
