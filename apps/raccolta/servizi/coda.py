"""Quali articoli elaborare a ogni giro."""
from django.utils import timezone

from apps.fonti.models import Articolo


def da_elaborare(limite: int):
    """Prima gli articoli nuovi (i più recenti per primi), poi i ricontrolli in scadenza.
    Gli articoli in errore non vengono ripresi in automatico."""
    nuovi = list(Articolo.objects.filter(stato=Articolo.Stato.NUOVO).order_by("-pubblicato_il", "-rilevato_il")[:limite])
    posti = limite - len(nuovi)
    ricontrolli = []
    if posti > 0:
        ricontrolli = list(
            Articolo.objects.filter(stato=Articolo.Stato.ELABORATO, prossimo_controllo__lte=timezone.now())
            .order_by("prossimo_controllo")[:posti]
        )
    return nuovi + ricontrolli
