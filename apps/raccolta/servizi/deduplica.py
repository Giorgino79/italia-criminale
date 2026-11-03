"""Raggruppamento degli articoli in fatti: evita di contare più volte lo stesso episodio.

Due segnali di somiglianza:
- il testo: titoli e sintesi a confronto (anche con i titoli di TUTTI gli articoli già collegati al fatto);
- i nomi propri in comune (es. "Pasolini", "Idroscalo"): titoli diversi sullo stesso episodio
  li condividono quasi sempre, due episodi diversi quasi mai.
"""
import re
from datetime import timedelta

from django.db.models import Q
from rapidfuzz import fuzz

from apps.fatti.models import Fatto

SOGLIA_SOMIGLIANZA = 60
FINESTRA_GIORNI = 3
# Seguiti giudiziari: un processo può arrivare anni dopo il fatto
FINESTRA_SEGUITI_GIORNI = 365 * 12
SOGLIA_SEGUITI = 55
BONUS_NOME_PROPRIO = 20

# Parole con l'iniziale maiuscola che non identificano un episodio
NON_NOMI = {
    "carabinieri", "carabiniere", "polizia", "procura", "questura", "questore", "prefetto", "prefettura", "guardia",
    "finanza", "tribunale", "corte", "cassazione", "appello", "assise", "italia", "italiano", "italiana", "comune",
    "stato", "vigili", "fuoco", "pronto", "soccorso", "leggi", "anche", "video", "foto", "ansa", "gip", "gup", "pm",
    "dda", "squadra", "mobile", "polfer", "locale", "municipale", "regione", "provincia", "ministero", "governo",
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
    "novembre", "dicembre", "lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica",
    "nord", "sud", "est", "ovest", "centro", "europa", "aggiornamento", "ultime", "notizie", "cronaca", "esclusivo",
    "tutto", "come", "dove", "quando", "perché", "chi", "cosa", "dopo", "prima", "ecco", "oggi", "ieri",
}
_PAROLA = re.compile(r"[A-ZÀ-Ü][a-zà-ü'’]{3,}")


def nomi_propri(testo: str) -> set[str]:
    """Parole con iniziale maiuscola che non stanno a inizio frase (o che a inizio frase sono seguite da virgola o
    due punti, come in "Pasolini, 51 anni fa")."""
    trovati = set()
    for frase in re.split(r"(?<=[.!?])\s+|\n+", testo or ""):
        for m in _PAROLA.finditer(frase):
            parola = m.group(0).strip("'’")
            inizio = m.start() == len(frase) - len(frase.lstrip(" \"«“'"))
            seguita = frase[m.end():m.end() + 1] in (",", ":")
            if inizio and not seguita:
                continue
            if parola.lower() not in NON_NOMI:
                trovati.add(parola.lower())
    return trovati


def somiglianza(fatto: Fatto, testo: str, escludi: set[str] = frozenset()) -> float:
    """0-140 circa: somiglianza testuale migliore + bonus per i nomi propri condivisi."""
    titoli = [fatto.sintesi] + list(fatto.articoli.values_list("titolo", flat=True)[:15])
    testo_l = testo.lower()
    base = max((fuzz.token_set_ratio(t.lower(), testo_l) for t in titoli if t), default=0)
    comuni = (nomi_propri(testo) & nomi_propri("\n".join(titoli))) - escludi
    return base + BONUS_NOME_PROPRIO * min(2, len(comuni))


def _zona(comune, provincia):
    """Filtro sul luogo: il comune se noto, altrimenti la provincia, altrimenti i fatti senza luogo."""
    if comune is not None:
        return {"comune": comune}
    if provincia is not None:
        return {"provincia": provincia}
    return {"comune": None, "provincia": None}


def _escludi(comune, provincia) -> set[str]:
    """Il nome del luogo è già nel filtro: non deve valere anche come nome proprio in comune."""
    nomi = set()
    for x in (comune, provincia):
        if x is not None:
            nomi |= {p.lower() for p in re.findall(r"\w+", x.nome)}
    return nomi


def _migliore(candidati, testo, soglia, escludi, salta=None):
    migliore, punteggio_max = None, 0
    for fatto in candidati:
        if salta is not None and fatto.pk == salta:
            continue
        punteggio = somiglianza(fatto, testo, escludi)
        if punteggio > punteggio_max:
            migliore, punteggio_max = fatto, punteggio
    return migliore if punteggio_max >= soglia else None


def trova_fatto_esistente(*, comune, data_evento, categorie_slug, testo_confronto, provincia=None,
                          salta=None) -> Fatto | None:
    """Stesso luogo, date vicine, almeno una categoria in comune, testo simile o nomi propri condivisi."""
    if not categorie_slug:
        return None
    candidati = Fatto.objects.filter(**_zona(comune, provincia), categorie__slug__in=categorie_slug).distinct()
    if data_evento:
        finestra = (data_evento - timedelta(days=FINESTRA_GIORNI), data_evento + timedelta(days=FINESTRA_GIORNI))
        # anche i fatti senza data registrati negli stessi giorni (es. articoli che parlano di un fatto passato)
        candidati = candidati.filter(Q(data_evento__range=finestra) | Q(data_evento=None, creato_il__date__range=finestra))
    return _migliore(candidati[:200], testo_confronto, SOGLIA_SOMIGLIANZA, _escludi(comune, provincia), salta)


def trova_fatto_per_seguito(*, comune, categorie_slug, testo_confronto, data_fatto_originale=None, data_limite=None,
                            provincia=None, salta=None) -> Fatto | None:
    """Cerca il fatto originale di cui un articolo racconta gli sviluppi, anche di anni prima."""
    if not categorie_slug:
        return None
    candidati = Fatto.objects.filter(**_zona(comune, provincia), categorie__slug__in=categorie_slug).distinct()
    if data_fatto_originale:
        if len(str(data_fatto_originale)) == 4:
            candidati = candidati.filter(Q(data_evento__year=int(data_fatto_originale)) | Q(data_evento=None))
        else:
            candidati = candidati.filter(
                Q(data_evento__range=(data_fatto_originale - timedelta(days=FINESTRA_GIORNI),
                                      data_fatto_originale + timedelta(days=FINESTRA_GIORNI))) | Q(data_evento=None)
            )
    elif data_limite:
        candidati = candidati.filter(
            Q(data_evento__gte=data_limite - timedelta(days=FINESTRA_SEGUITI_GIORNI)) | Q(data_evento=None)
        )
    return _migliore(candidati.order_by("-data_evento")[:500], testo_confronto, SOGLIA_SEGUITI,
                     _escludi(comune, provincia), salta)
