"""Riconoscimento di comune e quartiere e geocoding."""
import logging
import re

from django.conf import settings

from apps.reati.choices import Precisione
from apps.territorio.models import Comune, Quartiere

log = logging.getLogger(__name__)


# Aggettivi territoriali usati dalla cronaca ("nel Comasco", "nella Bergamasca") → sigla della provincia
AGGETTIVI_PROVINCIA = {
    "comasco": "CO", "comasca": "CO", "milanese": "MI", "bergamasco": "BG", "bergamasca": "BG", "bresciano": "BS",
    "bresciana": "BS", "varesotto": "VA", "varesino": "VA", "lecchese": "LC", "pavese": "PV", "cremonese": "CR",
    "mantovano": "MN", "mantovana": "MN", "lodigiano": "LO", "lodigiana": "LO", "monzese": "MB", "brianza": "MB",
    "torinese": "TO", "cuneese": "CN", "astigiano": "AT", "alessandrino": "AL", "novarese": "NO", "biellese": "BI",
    "vercellese": "VC", "genovese": "GE", "savonese": "SV", "spezzino": "SP", "imperiese": "IM", "veronese": "VR",
    "vicentino": "VI", "padovano": "PD", "padovana": "PD", "trevigiano": "TV", "trevigiana": "TV", "veneziano": "VE",
    "rodigino": "RO", "bellunese": "BL", "udinese": "UD", "triestino": "TS", "goriziano": "GO", "pordenonese": "PN",
    "bolognese": "BO", "modenese": "MO", "parmense": "PR", "piacentino": "PC", "ferrarese": "FE", "ravennate": "RA",
    "forlivese": "FC", "riminese": "RN", "fiorentino": "FI", "pisano": "PI", "livornese": "LI", "lucchese": "LU",
    "senese": "SI", "aretino": "AR", "grossetano": "GR", "pratese": "PO", "pistoiese": "PT", "perugino": "PG",
    "ternano": "TR", "anconetano": "AN", "maceratese": "MC", "pesarese": "PU", "fermano": "FM", "ascolano": "AP",
    "viterbese": "VT", "reatino": "RI", "frusinate": "FR", "ciociaria": "FR", "pontino": "LT", "aquilano": "AQ",
    "teramano": "TE", "pescarese": "PE", "chietino": "CH", "napoletano": "NA", "casertano": "CE", "beneventano": "BN",
    "sannio": "BN", "avellinese": "AV", "irpinia": "AV", "salernitano": "SA", "barese": "BA", "foggiano": "FG",
    "tarantino": "TA", "brindisino": "BR", "leccese": "LE", "salento": "LE", "potentino": "PZ", "materano": "MT",
    "cosentino": "CS", "catanzarese": "CZ", "crotonese": "KR", "vibonese": "VV", "reggino": "RC",
    "palermitano": "PA", "catanese": "CT", "messinese": "ME", "siracusano": "SR", "ragusano": "RG",
    "agrigentino": "AG", "trapanese": "TP", "nisseno": "CL", "ennese": "EN", "cagliaritano": "CA",
    "sassarese": "SS", "nuorese": "NU", "oristanese": "OR",
}

_RE_AGGETTIVO = re.compile(
    r"\b(?:nel|nella|del|della|dal|dalla|sul|sulla|in)\s+(" + "|".join(sorted(AGGETTIVI_PROVINCIA, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_RE_IN_PROVINCIA = re.compile(r"\b(?:in )?provincia di ([A-ZÀ-Ü][\w'À-ü]+(?:[ -][A-ZÀ-Ü][\w'À-ü]+)?)")
_RE_SIGLA = re.compile(r"\(([A-Z]{2})\)")
# Un comune citato dopo queste parole è di solito l'origine della persona, non il luogo del fatto
_RE_ORIGINE = re.compile(
    r"(originari[oaie]|nat[oaie]|residente|residenti|trasferit[oaie]|provenient[ei]|di origin[ei]|anche a|come a)"
    r"\s+(?:di|a|da|in|ad)?\s*$",
    re.IGNORECASE,
)


def trova_provincia(titolo: str, testo: str):
    """Riconosce la provincia da 'nel Comasco', 'in provincia di Como' o '(CO)'. Il titolo ha la precedenza."""
    from apps.territorio.models import Provincia

    for parte in (titolo, testo[:600]):
        m = _RE_AGGETTIVO.search(parte)
        if m:
            prov = Provincia.objects.filter(sigla=AGGETTIVI_PROVINCIA[m.group(1).lower()]).first()
            if prov:
                return prov, m.group(0)
        m = _RE_IN_PROVINCIA.search(parte)
        if m:
            capo = Comune.objects.filter(nome__iexact=m.group(1), capoluogo=True).select_related("provincia").first()
            if capo:
                return capo.provincia, m.group(0)
        m = _RE_SIGLA.search(parte)
        if m:
            prov = Provincia.objects.filter(sigla=m.group(1)).first()
            if prov:
                return prov, ""
    return None, ""


def _punteggio(nome: str, titolo: str, testo: str) -> float:
    """Più alto se il comune è nel titolo o nell'attacco dell'articolo, negativo se è citato come origine."""
    punti = 0.0
    for variante in {nome, nome.upper()}:
        if re.search(rf"\b{re.escape(variante)}\b", titolo):
            punti += 6
        for m in re.finditer(rf"\b{re.escape(variante)}\b", testo):
            prima = testo[max(0, m.start() - 30):m.start()]
            if _RE_ORIGINE.search(prima):
                punti -= 6
            else:
                punti += 3 if m.start() < 250 else 1
    return punti


def trova_luogo(nome: str | None, titolo: str, testo: str, testata=None):
    """Restituisce (comune, provincia, area_testo).

    Ordine: comune indicato dall'estrazione, comuni coperti dalla testata, poi tutti i comuni citati,
    scelti per punteggio (titolo, attacco, numero di citazioni) e coerenti con la provincia se citata.
    Se c'è solo la provincia ("nel Comasco") il fatto resta a livello di provincia.
    """
    provincia, area = trova_provincia(titolo, testo)

    if nome:
        stessi = Comune.objects.filter(nome__iexact=nome.strip()).select_related("provincia")
        if provincia:
            stessi = stessi.filter(provincia=provincia) or stessi
        comune = stessi.order_by("-capoluogo").first()
        if comune and (provincia is None or comune.provincia_id == provincia.id):
            return comune, comune.provincia, area

    gruppi = []
    if testata:
        gruppi.append((list(testata.comuni_copertura.select_related("provincia")), True))
    gruppi.append((_comuni_per_ricerca(), False))
    for candidati, copertura in gruppi:
        migliori = []
        for comune in candidati:
            if copertura:  # comuni della testata: anche in minuscolo, nessuna esclusione
                nome_c, t, b = comune.nome.lower(), titolo.lower(), testo.lower()
            else:
                if len(comune.nome) < 4 or comune.nome.lower() in NOMI_AMBIGUI:
                    continue
                nome_c, t, b = comune.nome, titolo, testo
            if nome_c not in t and nome_c not in b and nome_c.upper() not in b:
                continue
            punti = _punteggio(nome_c, t, b)
            if provincia:
                punti += 5 if comune.provincia_id == provincia.id else -10
            punti += 0.5 if comune.capoluogo else 0
            # una citazione isolata in fondo al testo (es. "Leggi anche") non basta
            if punti >= (1 if copertura else 2.5):
                migliori.append((punti, comune))
        if migliori:
            migliori.sort(key=lambda x: -x[0])
            comune = migliori[0][1]
            return comune, comune.provincia, area
    return None, provincia, area


def trova_comune(nome: str | None, testo: str, testata=None) -> Comune | None:
    """Compatibilità: solo il comune."""
    titolo, _, corpo = testo.partition("\n")
    return trova_luogo(nome, titolo, corpo, testata)[0]


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
        Comune.objects.select_related("provincia")
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


def geocodifica(luogo_testo: str | None, comune: Comune | None, provincia=None) -> tuple[float | None, float | None, str]:
    """Restituisce (lat, lon, precisione). Usa Nominatim; rispettare il limite di 1 richiesta/secondo."""
    if comune is None:
        return None, None, Precisione.PROVINCIA if provincia else Precisione.NESSUNA
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
