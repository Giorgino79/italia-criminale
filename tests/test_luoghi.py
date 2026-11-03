import pytest

from apps.raccolta.servizi.luoghi import trova_luogo
from apps.territorio.models import Comune, Provincia, Regione


@pytest.fixture
def territorio(db):
    lom = Regione.objects.create(nome="Lombardia", codice_istat="03")
    cam = Regione.objects.create(nome="Campania", codice_istat="15")
    laz = Regione.objects.create(nome="Lazio", codice_istat="12")
    co = Provincia.objects.create(nome="Como", sigla="CO", regione=lom)
    bn = Provincia.objects.create(nome="Benevento", sigla="BN", regione=cam)
    rm = Provincia.objects.create(nome="Roma", sigla="RM", regione=laz)
    return {
        "como": Comune.objects.create(nome="Como", provincia=co, capoluogo=True),
        "cantu": Comune.objects.create(nome="Cantù", provincia=co),
        "benevento": Comune.objects.create(nome="Benevento", provincia=bn, capoluogo=True),
        "roma": Comune.objects.create(nome="Roma", provincia=rm, capoluogo=True),
        "co": co,
    }


def test_comasco_non_finisce_a_benevento(territorio):
    titolo = "Morta nella piscina di casa nel Comasco, arrestato l'ex marito: \"L'ha spinta\""
    testo = ("La donna, originaria di Benevento, è stata trovata nella piscina della villa. "
             "Leggi anche: Benevento, incidente sulla statale")
    comune, provincia, area = trova_luogo(None, titolo, testo)
    assert comune is None
    assert provincia == territorio["co"]
    assert area.lower() == "nel comasco"


def test_comune_della_provincia_citata_vince(territorio):
    titolo = "Morta nella piscina di casa nel Comasco"
    testo = "CANTÙ – La donna, originaria di Benevento, è stata trovata nella piscina di casa a Cantù."
    comune, provincia, _ = trova_luogo(None, titolo, testo)
    assert comune == territorio["cantu"] and provincia == territorio["co"]


def test_citazione_isolata_in_fondo_non_basta(territorio):
    testo = "Una lite è degenerata in un bar del centro. " + "Testo. " * 80 + "Leggi anche: Benevento, furto in farmacia"
    comune, provincia, _ = trova_luogo(None, "Lite in un bar, un ferito", testo)
    assert comune is None and provincia is None


def test_attacco_dell_articolo(territorio):
    comune, provincia, _ = trova_luogo(None, "Rapina in farmacia", "ROMA – Due uomini armati hanno rapinato una farmacia.")
    assert comune == territorio["roma"]


def test_nome_dal_modello_coerente_con_provincia(territorio):
    comune, _, _ = trova_luogo("Cantù", "Rapina nel Comasco", "Il fatto è avvenuto ieri sera.")
    assert comune == territorio["cantu"]


def test_in_provincia_di(territorio):
    _, provincia, _ = trova_luogo(None, "Incidente in provincia di Como", "Nessun altro dettaglio.")
    assert provincia == territorio["co"]
