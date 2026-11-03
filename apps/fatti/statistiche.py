"""Aggregazioni per data, reato, quartiere, città, regione.

Le statistiche contano i FATTI riportati dalla cronaca, non i reati commessi (vedi metodologia).
"""
from django.db.models import Count, F, Q
from django.db.models.functions import TruncMonth

from apps.reati.choices import Fase


def _conta(qs, *campi, limite=None):
    righe = qs.values(*campi).annotate(totale=Count("id", distinct=True)).order_by("-totale")
    return list(righe[:limite] if limite else righe)


def riepilogo(qs) -> dict:
    return qs.aggregate(
        fatti=Count("id", distinct=True),
        aggressioni=Count("id", filter=Q(aggressione=True), distinct=True),
        arresti=Count("id", filter=Q(fase=Fase.ARRESTO), distinct=True),
        manifestazioni=Count("id", filter=~Q(esito_manifestazione=""), distinct=True),
        comuni=Count("comune", distinct=True),
        province=Count("provincia", distinct=True),
    )


def per_giorno(qs):
    return list(
        qs.exclude(data_evento=None).values(giorno=F("data_evento"))
        .annotate(totale=Count("id", distinct=True)).order_by("giorno")
    )


def per_mese(qs):
    return list(
        qs.exclude(data_evento=None).annotate(mese=TruncMonth("data_evento"))
        .values("mese").annotate(totale=Count("id", distinct=True)).order_by("mese")
    )


def per_categoria(qs, limite=None):
    return _conta(qs, "categorie__nome", "categorie__macro__nome", limite=limite)


def per_regione(qs):
    return _conta(qs.exclude(provincia=None), "provincia__regione__nome")


def per_provincia(qs, limite=30):
    return _conta(qs.exclude(provincia=None), "provincia__nome", "provincia__sigla", limite=limite)


def per_comune(qs, limite=30):
    return _conta(qs.exclude(comune=None), "comune__nome", "comune__provincia__sigla", "comune__popolazione", limite=limite)


def per_quartiere(qs, limite=30):
    return _conta(qs.exclude(quartiere=None), "quartiere__nome", "quartiere__comune__nome", limite=limite)


def per_fase(qs):
    return _conta(qs, "fase")


def tasso_per_100mila(totale: int, popolazione: int | None) -> float | None:
    """Rapporto sui residenti: da leggere con cautela dove la popolazione presente è molto più alta."""
    if not popolazione:
        return None
    return round(totale / popolazione * 100_000, 1)


# ---------------------------------------------------------------- copertura
def piu_ripresi(qs, limite=10):
    return list(qs.filter(n_testate__gt=0).order_by("-n_testate", "-n_articoli", "-data_evento")[:limite])


def distribuzione_copertura(qs):
    """Quanti fatti sono riportati da 1, 2, 3-5, 6+ testate."""
    fasce = [("1 testata", 1, 1), ("2 testate", 2, 2), ("3-5 testate", 3, 5), ("6 o più", 6, 10_000)]
    return [{"fascia": nome, "totale": qs.filter(n_testate__range=(a, b)).count()} for nome, a, b in fasce]


# ---------------------------------------------------------------- esiti giudiziari
def esiti(qs, mesi_attesa=12):
    from datetime import timedelta

    from django.utils import timezone

    from apps.reati.choices import FASI_CON_ESITO, FASI_IN_ATTESA

    limite = timezone.localdate() - timedelta(days=30 * mesi_attesa)
    procedimenti = qs.exclude(fase="notizia")
    con_esito = procedimenti.filter(fase__in=FASI_CON_ESITO).count()
    totale = procedimenti.count()
    return {
        "procedimenti": totale,
        "con_esito": con_esito,
        "quota_con_esito": round(con_esito / totale * 100, 1) if totale else None,
        "condanne": procedimenti.filter(fase__in=["condanna_non_definitiva", "condanna_definitiva"]).count(),
        "assoluzioni": procedimenti.filter(fase="assoluzione").count(),
        "archiviazioni": procedimenti.filter(fase="archiviazione").count(),
        "in_attesa_da_oltre": procedimenti.filter(fase__in=FASI_IN_ATTESA, data_evento__lt=limite).count(),
        "mesi_attesa": mesi_attesa,
    }


# ---------------------------------------------------------------- cittadinanza (solo aggregata)
STRANIERE = ["ue", "extra_ue", "straniera"]


def _quota(parte, totale):
    return round(parte / totale * 100, 1) if totale else None


def cittadinanza(qs, campo="cittadinanza_autori"):
    """Distribuzione della cittadinanza COME RIPORTATA dalla fonte, con la quota 'non indicata' in evidenza."""
    from apps.reati.choices import Cittadinanza

    totale = qs.count()
    conteggi = {r[campo]: r["totale"] for r in qs.values(campo).annotate(totale=Count("id", distinct=True))}
    indicati = totale - conteggi.get(Cittadinanza.NON_INDICATA, 0)
    stranieri = sum(conteggi.get(v, 0) for v in STRANIERE)
    return {
        "totale": totale,
        "indicata": indicati,
        "quota_indicata": _quota(indicati, totale),
        "righe": [
            {"valore": v, "etichetta": e, "totale": conteggi.get(v, 0), "quota_su_tutti": _quota(conteggi.get(v, 0), totale),
             "quota_su_indicati": None if v == Cittadinanza.NON_INDICATA else _quota(conteggi.get(v, 0), indicati)}
            for v, e in Cittadinanza.choices
        ],
        "quota_straniera_su_indicati": _quota(stranieri, indicati - conteggi.get(Cittadinanza.MISTA, 0)),
    }


def cittadinanza_per_categoria(qs, limite=12, minimo_indicati=5):
    """Per ogni reato: quota di fatti con cittadinanza indicata e, tra questi, quota straniera.
    Sotto `minimo_indicati` fatti la quota non viene calcolata (numeri troppo piccoli)."""
    righe = (
        qs.values("categorie__nome")
        .annotate(
            totale=Count("id", distinct=True),
            indicati=Count("id", filter=~Q(cittadinanza_autori__in=["non_indicata", "mista"]), distinct=True),
            stranieri=Count("id", filter=Q(cittadinanza_autori__in=STRANIERE), distinct=True),
        )
        .exclude(categorie__nome=None)
        .order_by("-totale")
    )
    if limite:
        righe = righe[:limite]
    return [
        {**r, "quota_indicata": _quota(r["indicati"], r["totale"]),
         "quota_straniera": _quota(r["stranieri"], r["indicati"]) if r["indicati"] >= minimo_indicati else None}
        for r in righe
    ]


def cittadinanza_per_regione(qs, minimo_indicati=5):
    """Confronto tra quota straniera nei fatti (con cittadinanza indicata) e quota di stranieri tra i residenti.
    Attenzione: residenti ≠ presenti, e i giornali indicano la cittadinanza in modo selettivo."""
    righe = (
        qs.exclude(provincia=None)
        .values("provincia__regione__nome", "provincia__regione__popolazione",
                "provincia__regione__popolazione_straniera")
        .annotate(
            totale=Count("id", distinct=True),
            indicati=Count("id", filter=~Q(cittadinanza_autori__in=["non_indicata", "mista"]), distinct=True),
            stranieri=Count("id", filter=Q(cittadinanza_autori__in=STRANIERE), distinct=True),
        )
        .order_by("-totale")
    )
    risultato = []
    for r in righe:
        pop, pop_str = r["provincia__regione__popolazione"], r["provincia__regione__popolazione_straniera"]
        risultato.append({
            "regione": r["provincia__regione__nome"],
            "totale": r["totale"],
            "indicati": r["indicati"],
            "quota_indicata": _quota(r["indicati"], r["totale"]),
            "quota_straniera_fatti": _quota(r["stranieri"], r["indicati"]) if r["indicati"] >= minimo_indicati else None,
            "quota_straniera_residenti": _quota(pop_str, pop) if pop and pop_str else None,
        })
    return risultato


# ---------------------------------------------------------------- uso interno: linea editoriale delle testate
def copertura_per_orientamento(qs_articoli):
    """Per ogni orientamento: articoli di cronaca, fatti coperti, quota di articoli che indicano la cittadinanza.
    Si basa sui dati estratti da ogni articolo (ultima versione)."""
    from apps.fonti.models import Testata

    risultato = []
    for valore, etichetta in Testata.Orientamento.choices:
        articoli = qs_articoli.filter(testata__orientamento=valore, stato="elaborato")
        n = articoli.count()
        if not n:
            continue
        con_cittadinanza = 0
        for dati in articoli.values_list("versioni__dati_estratti", flat=True):
            if dati and dati.get("cittadinanza_autori") not in (None, "non_indicata"):
                con_cittadinanza += 1
        risultato.append({
            "orientamento": etichetta,
            "testate": Testata.objects.filter(orientamento=valore, attiva=True).count(),
            "articoli": n,
            "fatti": articoli.values("fatti").distinct().count(),
            "quota_cittadinanza_indicata": _quota(con_cittadinanza, articoli.values("versioni").count()),
        })
    return risultato
