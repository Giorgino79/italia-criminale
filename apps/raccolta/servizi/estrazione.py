"""Estrazione strutturata dei dati di un fatto da un articolo.

Con ANTHROPIC_API_KEY impostata usa un LLM vincolato allo schema; altrimenti un classificatore
di riserva a parole chiave, utile per sviluppo e test ma molto meno accurato.
"""
import json
import logging
import re

from django.conf import settings

from apps.reati.choices import Arma, Cittadinanza, Confidenza, Contesto, EsitoManifestazione, Fase
from apps.reati.models import CategoriaReato

log = logging.getLogger(__name__)


def schema(slugs: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "is_crime_news": {"type": "boolean", "description": "L'articolo racconta un fatto di reato specifico?"},
            "sintesi": {"type": "string", "description": "Una frase neutra sul fatto, SENZA nomi di persone, max 200 caratteri"},
            "categorie": {"type": "array", "items": {"type": "string", "enum": slugs}},
            "fase": {"type": "string", "enum": Fase.values},
            "data_evento": {"type": ["string", "null"], "description": "AAAA-MM-GG, data del fatto se indicata"},
            "luogo_testo": {"type": ["string", "null"], "description": "Via, zona o quartiere come scritto nella fonte"},
            "comune": {"type": ["string", "null"]},
            "contesto": {"type": "string", "enum": Contesto.values},
            "aggressione": {"type": "boolean"},
            "arma": {"type": "string", "enum": Arma.values},
            "esito_manifestazione": {"type": ["string", "null"], "enum": EsitoManifestazione.values + [None]},
            "noto_forze_ordine": {"type": ["boolean", "null"], "description": "Solo se la fonte lo dice esplicitamente"},
            "e_seguito": {
                "type": "boolean",
                "description": "True se l'articolo racconta sviluppi (processo, sentenza, assoluzione, archiviazione) di un fatto avvenuto in precedenza",
            },
            "data_fatto_originale": {
                "type": ["string", "null"],
                "description": "Se e_seguito: data (AAAA-MM-GG) o anno (AAAA) del fatto originale, se indicata",
            },
            "data_sviluppo": {"type": ["string", "null"], "description": "Data della sentenza o dello sviluppo giudiziario, se indicata"},
            "cittadinanza_autori": {
                "type": "string",
                "enum": Cittadinanza.values,
                "description": "Solo se la fonte la indica esplicitamente; altrimenti non_indicata. Non dedurla da nomi o aspetto.",
            },
            "numero_autori": {"type": ["integer", "null"]},
            "cittadinanza_vittime": {"type": "string", "enum": Cittadinanza.values, "description": "Stesse regole degli autori"},
            "confidenza": {"type": "string", "enum": Confidenza.values},
            "evidenza": {"type": "string", "description": "Breve frase della fonte (max 200 caratteri) che giustifica la classificazione"},
        },
        "required": ["is_crime_news", "sintesi", "categorie", "fase", "contesto", "aggressione", "arma", "confidenza", "evidenza"],
    }


ISTRUZIONI = (
    "Sei un analista che cataloga la cronaca giudiziaria italiana. Leggi l'articolo e compila lo schema. "
    "Regole: non riportare MAI nomi, iniziali, età esatte o altri dati che identificano persone; "
    "la categoria è una stima giornalistica; se un'informazione manca usa null; "
    "un arresto non è una condanna, indica la fase procedurale effettivamente riportata; "
    "la cittadinanza va indicata SOLO se scritta nella fonte, mai dedotta da nomi, aspetto o quartiere."
)


def estrai_con_llm(titolo: str, testo: str) -> dict:
    import anthropic

    categorie = list(CategoriaReato.objects.values_list("slug", flat=True))
    cliente = anthropic.Anthropic(api_key=settings.LLM["API_KEY"])
    risposta = cliente.messages.create(
        model=settings.LLM["MODELLO"],
        max_tokens=1024,
        system=ISTRUZIONI,
        tools=[{"name": "registra_fatto", "description": "Registra i dati del fatto", "input_schema": schema(categorie)}],
        tool_choice={"type": "tool", "name": "registra_fatto"},
        messages=[{"role": "user", "content": f"TITOLO: {titolo}\n\nTESTO:\n{testo[:12000]}"}],
    )
    for blocco in risposta.content:
        if blocco.type == "tool_use":
            return dict(blocco.input)
    raise ValueError("Risposta del modello senza dati strutturati")


_FASI = [
    (r"\bassolt[oia]\b", Fase.ASSOLUZIONE),
    (r"\barchiviat[oa]\b|archiviazione", Fase.ARCHIVIAZIONE),
    (r"condannat[oiae] in via definitiva|cassazione ha confermato", Fase.CONDANNA_DEF),
    (r"\bcondannat[oiae]\b", Fase.CONDANNA_NON_DEF),
    (r"rinviat[oiae] a giudizio", Fase.RINVIO_GIUDIZIO),
    (r"domiciliari|custodia cautelare|obbligo di firma|divieto di avvicinamento", Fase.MISURA_CAUTELARE),
    (r"\barrestat[oiae]\b|in manette", Fase.ARRESTO),
    (r"\bfermat[oiae]\b|\bfermo\b", Fase.FERMO),
    (r"\bdenunciat[oiae]\b|\bdenuncia\b", Fase.DENUNCIA),
]


NAZIONALITA_UE = [
    "romeno", "romena", "rumeno", "rumena", "polacco", "polacca", "bulgaro", "bulgara", "francese", "tedesco",
    "tedesca", "spagnolo", "spagnola", "croato", "croata", "slovacco", "slovacca", "ungherese", "portoghese",
]
NAZIONALITA_EXTRA_UE = [
    "albanese", "marocchino", "marocchina", "tunisino", "tunisina", "egiziano", "egiziana", "nigeriano", "nigeriana",
    "senegalese", "cinese", "ucraino", "ucraina", "pakistano", "pakistana", "bengalese", "indiano", "indiana",
    "algerino", "algerina", "gambiano", "gambiana", "peruviano", "peruviana", "ecuadoriano", "ecuadoriana",
    "brasiliano", "brasiliana", "moldavo", "moldava", "georgiano", "georgiana", "russo", "russa", "kosovaro",
    "serbo", "serba", "filippino", "filippina", "srilankese", "ghanese", "maliano", "eritreo", "somalo",
]


def _cittadinanza_da_testo(t: str) -> str:
    """Riconosce solo menzioni esplicite (aggettivi di nazionalità o 'italiano/straniero')."""
    trovate = set()
    if re.search(r"\bital(iano|iana|iani|iane)\b", t) and not re.search(r"\b(polizia|stato|governo|cittadinanza) italian", t):
        trovate.add(Cittadinanza.ITALIANA)
    if any(re.search(rf"\b{n}\b", t) for n in NAZIONALITA_UE):
        trovate.add(Cittadinanza.UE)
    if any(re.search(rf"\b{n}\b", t) for n in NAZIONALITA_EXTRA_UE):
        trovate.add(Cittadinanza.EXTRA_UE)
    if not trovate and re.search(r"\bstranier[oaie]\b|extracomunitari[oa]?\b", t):
        trovate.add(Cittadinanza.STRANIERA)
    if len(trovate) > 1:
        return Cittadinanza.MISTA
    return trovate.pop() if trovate else Cittadinanza.NON_INDICATA


def estrai_con_parole_chiave(titolo: str, testo: str) -> dict:
    """Classificatore di riserva: semplice, trasparente, con confidenza sempre bassa."""
    t = f"{titolo}\n{testo}".lower()
    trovate, evidenza = [], ""
    for cat in CategoriaReato.objects.exclude(parole_chiave=""):
        for parola in cat.lista_parole_chiave:
            m = re.search(rf"\b{re.escape(parola)}", t)
            if m:
                trovate.append(cat.slug)
                if not evidenza:
                    inizio = max(0, m.start() - 80)
                    evidenza = f"{titolo}\n{testo}"[inizio:m.end() + 80].replace("\n", " ").strip()
                break
    fase = next((f for pattern, f in _FASI if re.search(pattern, t)), Fase.NOTIZIA)
    arma = Arma.NON_SPECIFICATA
    if re.search(r"coltell|accoltell|lama", t):
        arma = Arma.TAGLIO
    elif re.search(r"pistola|fucile|spar[aoi]|colpi d'arma", t):
        arma = Arma.FUOCO
    aggressione = bool(re.search(r"aggredit|picchiat|pestaggio|accoltell|ferit[oa]|percoss", t))
    contesto = Contesto.ALTRO
    for pattern, valore in [
        (r"corteo|manifestazion", Contesto.MANIFESTAZIONE),
        (r"in casa|abitazione|appartamento", Contesto.ABITAZIONE),
        (r"autobus|metro|treno|stazione", Contesto.MEZZI_PUBBLICI),
        (r"discoteca|\bbar\b|locale|pub\b", Contesto.LOCALE),
        (r"scuola|liceo|istituto", Contesto.SCUOLA),
        (r"stadio|partita|ultras", Contesto.EVENTO_SPORTIVO),
        (r"\bonline\b|social|web", Contesto.ONLINE),
        (r"\bvia\b|piazza|strada|parco", Contesto.SPAZIO_PUBBLICO),
    ]:
        if re.search(pattern, t):
            contesto = valore
            break
    luogo = re.search(
        r"\b(?:via|viale|piazza|corso|largo|piazzale)\s+(?:(?:dei|del|della|delle|degli|di|de)\s+)?"
        r"[A-ZÀ-Ü][\w'À-ü]+(?:\s+[A-ZÀ-Ü][\w'À-ü]+){0,3}",
        f"{titolo} {testo}",
    )
    return {
        "is_crime_news": bool(trovate),
        "sintesi": titolo[:200],
        "categorie": trovate,
        "fase": fase,
        "data_evento": None,
        "luogo_testo": luogo.group(0) if luogo else None,
        "comune": None,
        "contesto": contesto,
        "aggressione": aggressione,
        "arma": arma,
        "esito_manifestazione": None,
        "e_seguito": bool(re.search(r"processo|sentenza|condannat|assolt|archiviat|rinviat[oiae] a giudizio|in appello|cassazione", t)),
        "data_fatto_originale": (m.group(1) if (m := re.search(r"\bnel (20\d\d|19\d\d)\b", t)) else None),
        "data_sviluppo": None,
        # Il classificatore a parole chiave non distingue autori e vittime: assegna agli autori solo
        # quando la nazionalità compare vicino a parole che indicano l'autore.
        "cittadinanza_autori": _cittadinanza_da_testo(
            " ".join(re.findall(r"[^.]*\b(?:arrestat|denunciat|fermat|indagat|condannat|autore|aggressore|rapinator|ladr)[^.]*", t))
        ),
        "numero_autori": None,
        "cittadinanza_vittime": Cittadinanza.NON_INDICATA,
        "noto_forze_ordine": True if re.search(r"già not[oaie] alle forze dell'ordine|pregiudicat", t) else None,
        "confidenza": Confidenza.BASSA,
        "evidenza": evidenza[:300],
    }


def estrai(titolo: str, testo: str) -> dict:
    if settings.LLM["API_KEY"]:
        try:
            dati = estrai_con_llm(titolo, testo)
            dati["metodo"] = "llm"
            return dati
        except Exception as e:  # rete, quota, risposta malformata: si ripiega sulle parole chiave
            log.warning("Estrazione LLM fallita, uso parole chiave: %s", e)
    dati = estrai_con_parole_chiave(titolo, testo)
    dati["metodo"] = "parole_chiave"
    return dati


def a_json(dati: dict) -> str:
    return json.dumps(dati, ensure_ascii=False, default=str)
