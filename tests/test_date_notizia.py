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
    assert "Sviluppi su reati precedenti" in giorno and "Cassazione conferma la condanna" in giorno


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


def test_spettacolo_e_parole_isolate_non_sono_cronaca(db):
    from django.core.management import call_command
    call_command("carica_dati_base", verbosity=0)
    gf = estrai_con_parole_chiave(
        "Grande Fratello Vip, eliminato e finalista: Alex lascia lo studio. Chi sono i concorrenti al televoto",
        "Cesara ha rubato la scena in puntata.")
    assert gf["is_crime_news"] is False
    isolata = estrai_con_parole_chiave("Il campione che ha conquistato tutti", "Ha rubato il cuore dei tifosi con una prestazione da record.")
    assert isolata["is_crime_news"] is False
    vero = estrai_con_parole_chiave("Furto in una villa, rubati gioielli", "I ladri sono entrati di notte.")
    assert vero["is_crime_news"] is True and "furto" in vero["categorie"]


def test_esempi_reali_non_sono_reati(db):
    from django.core.management import call_command
    call_command("carica_dati_base", verbosity=0)
    casi = [
        ("Ballando con le Stelle, le pagelle: Ornella Muti s'è scordata le costole rotte?! (4), Carlucci ipocrita",
         "La concorrente è caduta durante le prove, ferita a una costola, ma ha ballato lo stesso. Ferita anche la partner."),
        ("La maestra che ha rinunciato al posto fisso: «Ho rifiutato privilegi e soldi in più»",
         "Racconta gli abusi di potere che ha visto nella scuola e la scelta di lasciare: abusi sessuali mai, dice."),
        ("Ornella Muti parla con Barbara d' Urso ma scoppia il putiferio con Mariotto",
         "Minacce di lasciare lo show, minacciato di squalifica il ballerino."),
    ]
    for titolo, testo in casi:
        assert estrai_con_parole_chiave(titolo, testo)["is_crime_news"] is False, titolo
    vero = estrai_con_parole_chiave("Roma, rapina a mano armata nel negozio di Muller: rubate carte Pokemon",
                                    "I carabinieri cercano i due rapinatori fuggiti con il bottino.")
    assert vero["is_crime_news"] is True and "rapina" in vero["categorie"]
