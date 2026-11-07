from datetime import date, datetime, timezone

from django.core.management import call_command

from apps.fatti.models import Fatto, FattoArticolo
from apps.fonti.models import Articolo
from apps.raccolta.servizi.estrazione import estrai_con_parole_chiave


def test_seguito_senza_data_mostra_data_notizia_e_va_in_ordine(client, dati_base):
    vecchio = Fatto.objects.create(sintesi="Rapina di ottobre", data_evento=date(2026, 10, 1))
    seguito = Fatto.objects.create(sintesi="Cassazione conferma la condanna", data_ultimo_sviluppo=date(2026, 11, 6))
    nuovo = Fatto.objects.create(sintesi="Furto di ieri", data_evento=date(2026, 11, 5))
    ordine = list(Fatto.objects.recenti().values_list("pk", flat=True))
    assert ordine == [seguito.pk, nuovo.pk, vecchio.pk]
    home = client.get("/").content.decode()
    assert "data n.d." not in home and "notizia del" in home
    giorno = client.get("/giorno/2026-11-06/").content.decode()
    assert "Sviluppi su fatti precedenti" in giorno and "Cassazione conferma la condanna" in giorno


def test_rassegne_escluse_e_scartate(dati_base):
    dati = estrai_con_parole_chiave(
        "Slittano gli sconti sulle bollette, lo strappo di Salvini e le altre notizie da sapere per iniziare la giornata",
        "Arrestato un uomo per rapina a Roma.")
    assert dati["is_crime_news"] is False
    f = Fatto.objects.create(sintesi="Le notizie da sapere per iniziare la giornata")
    a = Articolo.objects.create(testata=dati_base["testata"], url="https://example.org/r1",
                                titolo="Le notizie da sapere per iniziare la giornata",
                                pubblicato_il=datetime(2026, 11, 6, tzinfo=timezone.utc))
    FattoArticolo.objects.create(fatto=f, articolo=a)
    call_command("scarta_rassegne", verbosity=0)
    f.refresh_from_db()
    assert f.stato_revisione == "scartato"
