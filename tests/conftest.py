import hashlib

import pytest
from django.core.management import call_command

from apps.fonti.models import Articolo, Testata
from apps.territorio.models import Comune, Provincia, Quartiere, Regione


@pytest.fixture
def dati_base(db):
    call_command("carica_dati_base", verbosity=0)
    lazio = Regione.objects.get(nome="Lazio")
    roma_prov = Provincia.objects.create(nome="Roma", sigla="RM", regione=lazio)
    roma = Comune.objects.create(nome="Roma", provincia=roma_prov, popolazione=2_750_000, lat=41.9, lon=12.5)
    Quartiere.objects.create(nome="San Lorenzo", comune=roma)
    testata = Testata.objects.create(nome="Cronaca di prova", url_home="https://example.org", feed=[])
    testata.comuni_copertura.add(roma)
    return {"roma": roma, "testata": testata}


def finto_scaricatore(titolo, testo):
    def scarica(url):
        return {"titolo": titolo, "testo": testo, "data": None, "hash": hashlib.sha256(testo.encode()).hexdigest()}
    return scarica


@pytest.fixture
def articolo(dati_base):
    return Articolo.objects.create(testata=dati_base["testata"], url="https://example.org/a1", titolo="bozza")
