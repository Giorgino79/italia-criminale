"""Riconoscimento di comune e quartiere e geocoding."""
import logging
import re

from django.conf import settings

from apps.reati.choices import Precisione
from apps.territorio.models import Comune, Quartiere

log = logging.getLogger(__name__)


def trova_comune(nome: str | None, testo: str, testata=None) -> Comune | None:
    """Prima il nome indicato dall'estrazione, poi i comuni coperti dalla testata citati nel testo."""
    if nome:
        comune = Comune.objects.filter(nome__iexact=nome.strip()).order_by("-popolazione").first()
        if comune:
            return comune
    candidati = testata.comuni_copertura.all() if testata else Comune.objects.none()
    for comune in sorted(candidati, key=lambda c: -len(c.nome)):
        if re.search(rf"\b{re.escape(comune.nome)}\b", testo, re.IGNORECASE):
            return comune
    # Testate nazionali o senza copertura impostata: cerca tra tutti i comuni, con iniziale maiuscola
    # (evita parole comuni che sono anche nomi di comune) e preferendo i più popolosi.
    for comune in _comuni_per_ricerca():
        nome = comune.nome
        if len(nome) < 4 or nome.lower() in NOMI_AMBIGUI:
            continue
        for variante in (nome, nome.upper()):
            if variante in testo and re.search(rf"\b{re.escape(variante)}\b", testo):
                return comune
    return None


# Comuni il cui nome è anche una parola comune: si riconoscono solo tramite la copertura della testata
NOMI_AMBIGUI = {
    "calcio", "paese", "cento", "bella", "vita", "ora", "lettere", "venere", "massa", "cassano", "monte", "ponte",
    "pace", "fiume", "porto", "piano", "colle", "valle", "rio", "scala", "orta", "lama", "nave", "mezzane", "carro",
    "bagno", "campo", "castello", "sale", "canale", "volta", "dello", "lei", "noi", "lu", "re", "vo", "ne",
    "sora", "osio", "cavour", "garibaldi", "marconi", "chiesa", "gallo", "gemona", "italia", "san", "santa",
}


def _comuni_per_ricerca():
    from django.db.models import F

    return list(
        Comune.objects.only("id", "nome")
        .order_by("-capoluogo", F("popolazione").desc(nulls_last=True), "nome")
    )


def trova_quartiere(comune: Comune | None, testo: str) -> Quartiere | None:
    if not comune:
        return None
    for q in comune.quartieri.all():
        nomi = [q.nome] + [a.strip() for a in q.alias.splitlines() if a.strip()]
        if any(re.search(rf"\b{re.escape(n)}\b", testo, re.IGNORECASE) for n in nomi):
            return q
    return None


def geocodifica(luogo_testo: str | None, comune: Comune | None) -> tuple[float | None, float | None, str]:
    """Restituisce (lat, lon, precisione). Usa Nominatim; rispettare il limite di 1 richiesta/secondo."""
    if comune is None:
        return None, None, Precisione.NESSUNA
    if not luogo_testo:
        return comune.lat, comune.lon, Precisione.COMUNE
    try:
        from geopy.extra.rate_limiter import RateLimiter
        from geopy.geocoders import Nominatim

        geo = Nominatim(user_agent=settings.GEOCODING["USER_AGENT"], domain=settings.GEOCODING["NOMINATIM_URL"])
        cerca = RateLimiter(geo.geocode, min_delay_seconds=1.1)
        risultato = cerca(f"{luogo_testo}, {comune.nome}, Italia", country_codes="it")
        if risultato:
            precisione = Precisione.INDIRIZZO if re.search(r"\d", luogo_testo) else Precisione.VIA
            return risultato.latitude, risultato.longitude, precisione
    except Exception as e:
        log.warning("Geocoding fallito per %s: %s", luogo_testo, e)
    return comune.lat, comune.lon, Precisione.COMUNE
