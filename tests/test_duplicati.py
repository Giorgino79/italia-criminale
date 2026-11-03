from datetime import datetime, timezone

import pytest
from django.core.management import call_command

from apps.fatti.models import Fatto, FattoArticolo, SegnalazioneErrore
from apps.fatti.servizi import unisci
from apps.fonti.models import Articolo
from apps.fonti.models import Testata as ModelloTestata
from apps.raccolta.servizi.deduplica import nomi_propri
from apps.raccolta.servizi.pipeline import elabora_articolo
from apps.reati.models import CategoriaReato

from .conftest import finto_scaricatore

OGGI = datetime(2026, 11, 2, 9, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def niente_geocoding(monkeypatch):
    monkeypatch.setattr("apps.raccolta.servizi.luoghi.geocodifica", lambda luogo, comune, provincia=None: (None, None, "comune"))


def _art(testata, n):
    return Articolo.objects.create(testata=testata, url=f"https://example.org/d{n}", titolo="x", pubblicato_il=OGGI)


def test_nomi_propri():
    assert "pasolini" in nomi_propri("Pasolini, 51 anni fa l'omicidio all'Idroscalo di Ostia")
    assert "idroscalo" in nomi_propri("Pasolini, 51 anni fa l'omicidio all'Idroscalo di Ostia")
    assert "rapina" not in nomi_propri("Rapina in farmacia a Roma")
    assert "carabinieri" not in nomi_propri("Arrestato dai Carabinieri un uomo")


def test_titoli_diversi_stesso_episodio_un_solo_fatto(dati_base):
    t1 = dati_base["testata"]
    t2 = ModelloTestata.objects.create(nome="Altra", url_home="https://altra.example.org")
    f1 = elabora_articolo(_art(t1, 1), scarica=finto_scaricatore(
        "Pasolini, 51 anni fa l'omicidio all'Idroscalo",
        "Roma ricorda Pier Paolo Pasolini, ucciso all'Idroscalo di Ostia. Il processo condannò Pelosi."))
    f2 = elabora_articolo(_art(t2, 2), scarica=finto_scaricatore(
        "Ostia, fiaccolata per Pasolini nel luogo dell'omicidio",
        "A Roma una fiaccolata all'Idroscalo per ricordare l'omicidio di Pasolini."))
    assert f1.pk == f2.pk
    assert Fatto.objects.count() == 1
    f1.refresh_from_db()
    assert (f1.n_articoli, f1.n_testate) == (2, 2)


def test_episodi_diversi_restano_separati(dati_base):
    t = dati_base["testata"]
    a = elabora_articolo(_art(t, 1), scarica=finto_scaricatore(
        "Rapina in farmacia al Tuscolano", "ROMA – Rapina alla farmacia Bianchi del Tuscolano, arrestato un uomo."))
    b = elabora_articolo(_art(t, 2), scarica=finto_scaricatore(
        "Rapina al supermercato di Centocelle", "ROMA – Rapina al supermercato Esposito di Centocelle, arrestato un giovane."))
    assert a.pk != b.pk


def test_unisci_sposta_tutto(dati_base):
    t = dati_base["testata"]
    furto = CategoriaReato.objects.get(slug="furto")
    rapina = CategoriaReato.objects.get(slug="rapina")
    p = Fatto.objects.create(sintesi="Primo", fase="arresto")
    p.categorie.add(furto)
    d = Fatto.objects.create(sintesi="Doppione", fase="condanna_non_definitiva")
    d.categorie.add(rapina)
    FattoArticolo.objects.create(fatto=p, articolo=_art(t, 1), ruolo="primo_lancio")
    FattoArticolo.objects.create(fatto=d, articolo=_art(t, 2), ruolo="primo_lancio")
    SegnalazioneErrore.objects.create(fatto=d, testo="x")
    unisci(p, [d])
    p.refresh_from_db()
    assert not Fatto.objects.filter(pk=d.pk).exists()
    assert p.n_articoli == 2 and p.segnalazioni.count() == 1
    assert set(p.categorie.values_list("slug", flat=True)) == {"furto", "rapina"}
    assert p.fase == "condanna_non_definitiva"
    assert p.eventi.filter(tipo="correzione").exists()


def test_comando_unisci_duplicati(dati_base):
    t = dati_base["testata"]
    lesioni = CategoriaReato.objects.get(slug="omicidio")
    a = Fatto.objects.create(sintesi="Pasolini, 51 anni fa l'omicidio", comune=dati_base["roma"])
    a.categorie.add(lesioni)
    FattoArticolo.objects.create(fatto=a, articolo=_art(t, 1))
    b = Fatto.objects.create(sintesi="Fiaccolata per Pasolini all'Idroscalo", comune=dati_base["roma"])
    b.categorie.add(lesioni)
    FattoArticolo.objects.create(fatto=b, articolo=_art(t, 2))
    call_command("unisci_duplicati", prova=True, verbosity=0)
    assert Fatto.objects.count() == 2
    call_command("unisci_duplicati", verbosity=0)
    assert Fatto.objects.count() == 1


def test_riga_mostra_altri_articoli(client, dati_base):
    t = dati_base["testata"]
    f = Fatto.objects.create(sintesi="Fatto ripreso", data_evento=OGGI.date())
    for n in range(1, 7):
        FattoArticolo.objects.create(fatto=f, articolo=_art(t, n))
    f.aggiorna_contatori()
    pagina = client.get("/").content.decode()
    assert pagina.count("Fatto ripreso") == 1
    assert "+ altri 5 articoli per questo fatto" in pagina
