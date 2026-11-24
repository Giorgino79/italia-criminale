"""Collegamento automatico degli articoli ai casi seguiti."""
import logging

log = logging.getLogger(__name__)


def collega(articolo, casi=None) -> list:
    """Collega l'articolo ai casi il cui elenco di parole chiave compare nel titolo. Non solleva mai errori."""
    from .models import Caso

    collegati = []
    try:
        casi = casi if casi is not None else list(Caso.objects.filter(attivo=True))
        e_reato = None
        for caso in casi:
            if not caso.corrisponde(articolo.titolo):
                continue
            if caso.solo_reati:
                if e_reato is None:
                    e_reato = articolo.fatti.exclude(stato_revisione="scartato").exists()
                if not e_reato:
                    continue
            caso.articoli.add(articolo)
            collegati.append(caso)
    except Exception as e:  # un caso mal configurato non deve fermare la raccolta
        log.warning("Collegamento ai casi fallito per l'articolo %s: %s", getattr(articolo, "pk", "?"), e)
    return collegati
