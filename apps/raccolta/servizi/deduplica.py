"""Raggruppamento degli articoli in fatti: evita di contare più volte lo stesso episodio."""
from datetime import timedelta

from rapidfuzz import fuzz

from apps.fatti.models import Fatto

SOGLIA_SOMIGLIANZA = 60
FINESTRA_GIORNI = 3
# Seguiti giudiziari: un processo può arrivare anni dopo il fatto
FINESTRA_SEGUITI_GIORNI = 365 * 12
SOGLIA_SEGUITI = 55


def _zona(comune, provincia):
    """Filtro sul luogo: il comune se noto, altrimenti la provincia."""
    if comune is not None:
        return {"comune": comune}
    if provincia is not None:
        return {"provincia": provincia}
    return None


def trova_fatto_esistente(*, comune, data_evento, categorie_slug, testo_confronto, provincia=None) -> Fatto | None:
    """Cerca un fatto nello stesso comune, in date vicine, con almeno una categoria in comune
    e una descrizione simile. Restituisce il più simile sopra soglia."""
    zona = _zona(comune, provincia)
    if zona is None or not categorie_slug:
        return None
    candidati = Fatto.objects.filter(**zona, categorie__slug__in=categorie_slug).distinct()
    if data_evento:
        candidati = candidati.filter(
            data_evento__range=(data_evento - timedelta(days=FINESTRA_GIORNI), data_evento + timedelta(days=FINESTRA_GIORNI))
        )
    migliore, punteggio_max = None, 0
    for fatto in candidati[:200]:
        punteggio = fuzz.token_set_ratio(fatto.sintesi.lower(), testo_confronto.lower())
        if punteggio > punteggio_max:
            migliore, punteggio_max = fatto, punteggio
    return migliore if punteggio_max >= SOGLIA_SOMIGLIANZA else None


def trova_fatto_per_seguito(*, comune, categorie_slug, testo_confronto, data_fatto_originale=None, data_limite=None,
                            provincia=None) -> Fatto | None:
    """Cerca il fatto originale di cui un articolo racconta gli sviluppi giudiziari.

    Rispetto alla deduplicazione normale la finestra temporale è di anni e si guarda solo al passato.
    Con la data (o l'anno) del fatto originale la ricerca si restringe molto.
    """
    zona = _zona(comune, provincia)
    if zona is None or not categorie_slug:
        return None
    candidati = Fatto.objects.filter(**zona, categorie__slug__in=categorie_slug).distinct()
    if data_fatto_originale:
        if len(str(data_fatto_originale)) == 4:
            candidati = candidati.filter(data_evento__year=int(data_fatto_originale))
        else:
            candidati = candidati.filter(
                data_evento__range=(data_fatto_originale - timedelta(days=FINESTRA_GIORNI),
                                    data_fatto_originale + timedelta(days=FINESTRA_GIORNI))
            )
    elif data_limite:
        candidati = candidati.filter(data_evento__gte=data_limite - timedelta(days=FINESTRA_SEGUITI_GIORNI))
    migliore, punteggio_max = None, 0
    for fatto in candidati.order_by("-data_evento")[:500]:
        punteggio = fuzz.token_set_ratio(fatto.sintesi.lower(), testo_confronto.lower())
        if punteggio > punteggio_max:
            migliore, punteggio_max = fatto, punteggio
    return migliore if punteggio_max >= SOGLIA_SEGUITI else None
