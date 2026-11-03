from django.utils import timezone

from apps.fatti.models import Fatto
from apps.fonti.models import Articolo
from apps.raccolta.servizi.pipeline import elabora_articolo

from .conftest import finto_scaricatore

TESTO = ("Roma, rapina nella notte a San Lorenzo: un uomo è stato aggredito e ferito con un coltello. "
         "Il presunto autore è stato arrestato dai carabinieri.")


def test_articolo_diventa_fatto(articolo, monkeypatch):
    monkeypatch.setattr("apps.raccolta.servizi.luoghi.geocodifica", lambda luogo, comune, provincia=None: (41.9, 12.5, "quartiere"))
    fatto = elabora_articolo(articolo, scarica=finto_scaricatore("Rapina a San Lorenzo", TESTO))
    assert fatto is not None
    slugs = set(fatto.categorie.values_list("slug", flat=True))
    assert "rapina" in slugs
    assert fatto.fase == "arresto"
    assert fatto.aggressione and fatto.arma == "taglio"
    assert fatto.comune.nome == "Roma" and fatto.quartiere.nome == "San Lorenzo"
    assert fatto.stato_revisione == Fatto.StatoRevisione.DA_RIVEDERE


def test_seconda_testata_stesso_fatto_non_duplica(articolo, dati_base, monkeypatch):
    monkeypatch.setattr("apps.raccolta.servizi.luoghi.geocodifica", lambda luogo, comune, provincia=None: (41.9, 12.5, "quartiere"))
    articolo.pubblicato_il = timezone.now()
    articolo.save()
    primo = elabora_articolo(articolo, scarica=finto_scaricatore("Rapina a San Lorenzo", TESTO))
    altro = Articolo.objects.create(testata=dati_base["testata"], url="https://example.org/a2", titolo="x",
                                    pubblicato_il=timezone.now())
    secondo = elabora_articolo(altro, scarica=finto_scaricatore("Rapina a San Lorenzo, arrestato l'aggressore", TESTO))
    assert primo.pk == secondo.pk
    assert Fatto.objects.count() == 1
    assert primo.articoli.count() == 2


def test_aggiornamento_registra_versione_e_cambio_fase(articolo, monkeypatch):
    monkeypatch.setattr("apps.raccolta.servizi.luoghi.geocodifica", lambda luogo, comune, provincia=None: (None, None, "comune"))
    elabora_articolo(articolo, scarica=finto_scaricatore("Rapina a San Lorenzo", TESTO.replace("arrestato", "cercato")))
    fatto = elabora_articolo(articolo, scarica=finto_scaricatore("Rapina a San Lorenzo", TESTO))
    assert articolo.versioni.count() == 2
    assert fatto.fase == "arresto"
    assert fatto.eventi.filter(tipo="cambio_fase").exists()


def test_articolo_non_di_cronaca(articolo):
    elabora_articolo(articolo, scarica=finto_scaricatore("Sagra della castagna", "Festa in piazza con musica."))
    articolo.refresh_from_db()
    assert articolo.stato == Articolo.Stato.NON_CRONACA
    assert Fatto.objects.count() == 0
