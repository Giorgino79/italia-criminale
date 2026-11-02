from datetime import datetime, timezone

import pytest
from django.contrib.auth.models import User

from apps.fatti import statistiche
from apps.fatti.models import Fatto, FattoArticolo
from apps.fonti.models import Articolo
from apps.fonti.models import Testata as ModelloTestata
from apps.raccolta.servizi.pipeline import elabora_articolo
from apps.reati.models import CategoriaReato

from .conftest import finto_scaricatore

ARRESTO = ("Roma, rapina a San Lorenzo: un uomo aggredito con un coltello e rapinato del portafoglio. "
           "Arrestato un 25enne marocchino dai carabinieri.")


@pytest.fixture(autouse=True)
def niente_geocoding(monkeypatch):
    monkeypatch.setattr("apps.raccolta.servizi.luoghi.geocodifica", lambda luogo, comune: (None, None, "comune"))


def _articolo(testata, n, quando):
    return Articolo.objects.create(testata=testata, url=f"https://example.org/{n}", titolo="x", pubblicato_il=quando)


def test_contatori_testate_e_articoli(dati_base):
    t1 = dati_base["testata"]
    t2 = ModelloTestata.objects.create(nome="Altra testata", url_home="https://altra.example.org")
    oggi = datetime(2026, 10, 30, 9, tzinfo=timezone.utc)
    f = elabora_articolo(_articolo(t1, 1, oggi), scarica=finto_scaricatore("Rapina a San Lorenzo", ARRESTO))
    elabora_articolo(_articolo(t1, 2, oggi), scarica=finto_scaricatore("Rapina a San Lorenzo, i dettagli", ARRESTO + " Ferito lievemente."))
    elabora_articolo(_articolo(t2, 3, oggi), scarica=finto_scaricatore("San Lorenzo, rapina e arresto", ARRESTO + " Fonte diversa."))
    f.refresh_from_db()
    assert (f.n_testate, f.n_articoli) == (2, 3)
    ruoli = set(FattoArticolo.objects.filter(fatto=f).values_list("ruolo", flat=True))
    assert ruoli == {"primo_lancio", "aggiornamento", "ripresa"}


def test_seguito_giudiziario_anni_dopo(dati_base):
    t = dati_base["testata"]
    fatto = elabora_articolo(_articolo(t, 1, datetime(2026, 3, 10, tzinfo=timezone.utc)),
                             scarica=finto_scaricatore("Rapina a San Lorenzo", ARRESTO))
    assert fatto.fase == "arresto"
    sentenza = ("Roma, assolto in appello il giovane accusato della rapina a San Lorenzo del 2026: "
                "il fatto non sussiste.")
    seguito = elabora_articolo(_articolo(t, 2, datetime(2029, 5, 20, tzinfo=timezone.utc)),
                               scarica=finto_scaricatore("Rapina a San Lorenzo, assolto in appello", sentenza))
    assert seguito.pk == fatto.pk
    fatto.refresh_from_db()
    assert fatto.fase == "assoluzione"
    assert fatto.data_ultimo_sviluppo.year == 2029
    assert fatto.stato_revisione == Fatto.StatoRevisione.DA_RIVEDERE
    evento = fatto.eventi.get(tipo="cambio_fase")
    assert (evento.fase_precedente, evento.fase_nuova) == ("arresto", "assoluzione")
    assert FattoArticolo.objects.get(fatto=fatto, articolo__url__endswith="/2").ruolo == "seguito"


def test_la_fase_non_torna_indietro(dati_base):
    fatto = Fatto.objects.create(sintesi="x", fase="condanna_non_definitiva")
    assert fatto.cambia_fase("arresto") is False
    assert fatto.cambia_fase("condanna_definitiva") is True
    assert fatto.fase == "condanna_definitiva"


def test_cittadinanza_riportata_e_aggregata(dati_base):
    fatto = elabora_articolo(_articolo(dati_base["testata"], 1, datetime(2026, 10, 1, tzinfo=timezone.utc)),
                             scarica=finto_scaricatore("Rapina a San Lorenzo", ARRESTO))
    assert fatto.cittadinanza_autori == "extra_ue"
    altro = Fatto.objects.create(sintesi="Furto", comune=dati_base["roma"])
    altro.categorie.add(CategoriaReato.objects.get(slug="furto"))
    dati = statistiche.cittadinanza(Fatto.objects.all())
    assert dati["totale"] == 2 and dati["indicata"] == 1 and dati["quota_indicata"] == 50.0


def test_cittadinanza_non_esposta_per_singolo_fatto(client, dati_base):
    Fatto.objects.create(sintesi="Aggressione", comune=dati_base["roma"], cittadinanza_autori="extra_ue")
    Fatto.objects.create(sintesi="Furto", comune=dati_base["roma"])
    pagina = client.get("/fatti/", {"cittadinanza": "extra_ue"}).content.decode()
    assert "Aggressione" in pagina and "Furto" in pagina  # il filtro è ignorato negli elenchi
    assert "cittadinanza_autori" not in client.get("/api/fatti/").json()["results"][0]
    assert client.get("/statistiche/", {"cittadinanza": "extra_ue"}).status_code == 200


def test_pagina_orientamento_solo_staff(client, dati_base):
    assert client.get("/interno/orientamento/").status_code == 302
    User.objects.create_user("redazione", password="x", is_staff=True)
    client.login(username="redazione", password="x")
    assert client.get("/interno/orientamento/").status_code == 200


def test_filtro_esito_e_ordinamento(client, dati_base):
    Fatto.objects.create(sintesi="Condannato", fase="condanna_definitiva", n_testate=5)
    Fatto.objects.create(sintesi="Arrestato", fase="arresto", n_testate=1)
    pagina = client.get("/fatti/", {"esito": "in_attesa"}).content.decode()
    assert "Arrestato" in pagina and "Condannato" not in pagina
    pagina = client.get("/fatti/", {"ordina": "-testate"}).content.decode()
    assert pagina.index("Condannato") < pagina.index("Arrestato")
