import io

import pytest
from openpyxl import load_workbook

from apps.fatti.models import Fatto
from apps.reati.models import CategoriaReato


@pytest.fixture
def fatti(dati_base):
    roma = dati_base["roma"]
    f = Fatto.objects.create(sintesi="Furto in un negozio del centro", comune=roma, data_evento="2026-10-30",
                             fase="denuncia", confidenza="alta")
    f.categorie.add(CategoriaReato.objects.get(slug="furto"))
    g = Fatto.objects.create(sintesi="Aggressione in strada", comune=roma, data_evento="2026-10-31",
                             aggressione=True, fase="arresto", contesto="abitazione", lat=41.9, lon=12.5)
    g.categorie.add(CategoriaReato.objects.get(slug="lesioni"))
    return [f, g]


@pytest.mark.parametrize("nome", ["home", "elenco_fatti", "statistiche", "mappa", "metodologia"])
def test_pagine(client, fatti, nome):
    from django.urls import reverse
    assert client.get(reverse(nome)).status_code == 200


def test_dettaglio_e_segnalazione(client, fatti):
    r = client.post(f"/fatti/{fatti[0].pk}/", {"testo": "La data è sbagliata"})
    assert r.status_code == 302
    assert fatti[0].segnalazioni.count() == 1


def test_filtro_per_reato(client, fatti):
    r = client.get("/fatti/", {"categoria": CategoriaReato.objects.get(slug="furto").pk})
    assert "Furto in un negozio" in r.content.decode()
    assert "Aggressione in strada" not in r.content.decode()


def test_export_excel(client, fatti):
    r = client.get("/esporta/excel/")
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames[:3] == ["Fatti", "Per reato", "Per regione"]
    assert wb["Fatti"].max_row == 3


def test_export_pdf(client, fatti):
    r = client.get("/esporta/pdf/")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_export_csv(client, fatti):
    r = client.get("/esporta/csv/")
    assert "Furto in un negozio" in r.content.decode("utf-8-sig")


def test_api_nasconde_coordinate_abitazione(client, fatti):
    dati = client.get("/api/fatti/").json()["results"]
    aggressione = next(d for d in dati if d["sintesi"] == "Aggressione in strada")
    assert aggressione["lat"] is None


def test_api_statistiche(client, fatti):
    dati = client.get("/api/statistiche/").json()
    assert dati["riepilogo"]["fatti"] == 2


def test_filtro_aggressione_e_mappa(client, fatti):
    pagina = client.get("/fatti/").content.decode()
    assert "Sconosciuto" not in pagina
    si = client.get("/fatti/", {"aggressione": "si"}).content.decode()
    assert "Aggressione in strada" in si and "Furto in un negozio" not in si
    mappa = client.get("/mappa/")
    assert "referrerPolicy" in mappa.content.decode()
    assert mappa["Referrer-Policy"] == "strict-origin-when-cross-origin"
