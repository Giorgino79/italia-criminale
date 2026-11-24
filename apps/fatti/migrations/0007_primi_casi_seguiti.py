"""Crea i primi tre casi seguiti. I riassunti sono bozze: compaiono sul sito solo dopo la verifica in admin."""
from django.db import migrations

CASI = [
    {
        "slug": "garlasco",
        "nome": "Delitto di Garlasco",
        "tipo": "caso",
        "ordine": 1,
        "sottotitolo": "L'omicidio di Chiara Poggi, dalla condanna definitiva alla nuova indagine della Procura di Pavia",
        "parole_chiave": "garlasco\nchiara poggi\nsempio\nalberto stasi",
        "parole_escluse": "",
        "solo_reati": False,
        "riassunto": (
            "Il 13 agosto 2007 Chiara Poggi, 26 anni, fu uccisa nella villa di famiglia a Garlasco, in provincia di Pavia. "
            "Per l'omicidio il fidanzato Alberto Stasi, assolto in primo grado nel 2009 e in appello nel 2011, è stato "
            "condannato in via definitiva a 16 anni nel dicembre 2015, dopo che la Cassazione aveva annullato l'assoluzione."
            "\n\n"
            "Nel marzo 2025 la Procura di Pavia ha riaperto il caso indagando Andrea Sempio, amico del fratello della vittima, "
            "la cui posizione era già stata archiviata nel 2017 e nel 2020. Secondo l'accusa avrebbe agito da solo. "
            "Il 3 novembre 2026 la Procura ha chiesto il rinvio a giudizio: si attende la data dell'udienza preliminare. "
            "La difesa contesta le accuse e ha depositato proprie consulenze tecniche."
            "\n\n"
            "In un filone separato la Procura di Pavia indaga sull'archiviazione del 2017, con l'ipotesi di concussione."
        ),
    },
    {
        "slug": "via-damelio",
        "nome": "Strage di via D'Amelio: l'inchiesta sui depistaggi",
        "tipo": "caso",
        "ordine": 2,
        "sottotitolo": "L'indagine della Procura di Caltanissetta sull'agenda rossa di Paolo Borsellino e sui depistaggi",
        "parole_chiave": "via d'amelio\nd'amelio\nagenda rossa\nborsellino\nde gennaro",
        "parole_escluse": "",
        "solo_reati": False,
        "riassunto": (
            "Il 19 luglio 1992 un'autobomba in via D'Amelio, a Palermo, uccise il giudice Paolo Borsellino e cinque agenti "
            "della scorta. Indagini e processi sulla strage vanno avanti da oltre trent'anni, segnati dai depistaggi accertati "
            "nelle prime inchieste e dalla scomparsa dell'agenda rossa del magistrato."
            "\n\n"
            "La Procura di Caltanissetta conduce da circa tre anni un nuovo filone sulla scomparsa dell'agenda e su possibili "
            "depistaggi. A novembre 2026 ha disposto perquisizioni e ha indagato per depistaggio l'ex capo della Polizia "
            "Gianni De Gennaro insieme ad altre persone. Il gip ha respinto la richiesta di misura cautelare e la Procura ha "
            "presentato ricorso al Tribunale del Riesame."
            "\n\n"
            "Il 21 novembre 2026 De Gennaro è morto; secondo le fonti si è tolto la vita. Con la morte dell'indagato il "
            "procedimento nei suoi confronti si estingue."
        ),
    },
    {
        "slug": "superbonus",
        "nome": "Truffe sul Superbonus",
        "tipo": "tema",
        "ordine": 3,
        "sottotitolo": "Crediti d'imposta fittizi, lavori mai eseguiti e società cartiere",
        "parole_chiave": "superbonus\nbonus edilizi\nbonus edilizio\n110%\ncrediti fittizi\ncrediti d'imposta fittizi",
        "parole_escluse": "",
        "solo_reati": True,
        "riassunto": (
            "Il Superbonus è l'agevolazione introdotta nel 2020 per i lavori di efficientamento energetico e antisismici, "
            "con la possibilità di cedere il credito d'imposta a banche e imprese. La cessione dei crediti ha aperto la "
            "strada a frodi: lavori dichiarati ma mai eseguiti, fatture false e società «cartiere» usate per creare crediti "
            "fittizi da rivendere o compensare."
            "\n\n"
            "Un esempio: a giugno 2026 la Procura di Siracusa e la Guardia di Finanza hanno sequestrato oltre 560 milioni di "
            "euro di crediti, con 12 indagati e più di 60 società ritenute fittizie in tutta Italia."
            "\n\n"
            "Questa pagina raccoglie i singoli casi riportati dai giornali, con il luogo e la fase giudiziaria di ciascuno."
        ),
    },
]


def crea(apps, schema_editor):
    Caso = apps.get_model("fatti", "Caso")
    for dati in CASI:
        Caso.objects.get_or_create(slug=dati["slug"], defaults=dati)


def elimina(apps, schema_editor):
    apps.get_model("fatti", "Caso").objects.filter(slug__in=[c["slug"] for c in CASI]).delete()


class Migration(migrations.Migration):
    dependencies = [("fatti", "0006_casi_seguiti")]
    operations = [migrations.RunPython(crea, elimina)]
