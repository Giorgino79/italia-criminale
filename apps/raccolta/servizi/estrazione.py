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


# Titoli che non sono cronaca di un singolo fatto: rassegne, riepiloghi, aggiornamenti in diretta
NON_FATTO = re.compile(
    r"notizie (?:da sapere|del giorno|di oggi|della giornata)|le altre notizie|per iniziare la giornata|"
    r"la giornata in \d+|rassegna stampa|\bdiretta\b|\blive\b|timeline\b|le notizie di|"
    # spettacolo, gossip, sport, servizi: non sono cronaca di reati anche se usano parole come "rubato" o "colpo"
    r"grande fratello|\bgf vip\b|temptation island|ballando con le stelle|x factor|\bsanremo\b|\breality\b|"
    r"\bpuntata\b|televoto|\bconcorrent[ei]\b|\bgossip\b|\boroscopo\b|serie a\b|champions league|"
    r"\bricett[ae]\b|meteo\b|previsioni del tempo|\bfilm\b|\bserie tv\b|\bfiction\b|\balbum\b|\bballando\b|\btrash\b|"
    # politica e approfondimenti, non singoli fatti
    r"\bmanovra\b|legge di bilancio|\bemendament|^speciale\b",
    re.IGNORECASE,
)


# Senza almeno uno di questi segnali un articolo non è cronaca di un reato, qualunque parola contenga
# (es. "costole rotte" a un programma tv, "rubato la scena").
CONTESTO_REATO = re.compile(
    r"carabinier|polizi|questur|procur|\bpm\b|magistrat|giudic|tribunal|indagin|indagat|inquirent|investigator|"
    r"denunci|querel|arrest|fermat[oaie]\b|manette|perquisizion|sequestr|guardia di finanza|\bgdf\b|"
    r"vittim|aggressor|reato|delitto|omicidi|processo|condann|assolt|accusat|appello|cassazione|sentenz|imputat|carcer|detenut|"
    r"rapinator|ladr[oi]\b|spacciator|malviv|criminal|clan\b|mafios|camorr|'ndrangh",
    re.IGNORECASE,
)


# Il suicidio non è un reato: "si è ucciso" non va contato come omicidio (salvo omicidio-suicidio o istigazione)
SUICIDIO = re.compile(r"suicid|si è (?:ucciso|uccisa|tolto la vita|tolta la vita)|si toglie la vita|si uccide\b", re.IGNORECASE)
OMICIDIO_ESPLICITO = re.compile(
    r"omicidio|femminicidio|istigazione|\buccide\b|ha ucciso|uccidendo|\buccis[oa] (?:da|dal|dalla|a colpi)|ammazza", re.IGNORECASE)


def e_suicidio(titolo: str) -> bool:
    return bool(SUICIDIO.search(titolo or "")) and not OMICIDIO_ESPLICITO.search(titolo or "")


# Fatti avvenuti all'estero: l'osservatorio conta solo i reati in Italia
PAESI_ESTERI = (
    "francia|germania|spagna|svizzera|austria|belgio|olanda|paesi bassi|portogallo|regno unito|inghilterra|"
    "gran bretagna|scozia|irlanda|stati uniti|america|canada|messico|brasile|argentina|colombia|venezuela|perù|"
    "cile|cina|giappone|corea|india|pakistan|russia|ucraina|bielorussia|israele|gaza|cisgiordania|libano|siria|iran|iraq|"
    "afghanistan|turchia|grecia|albania|romania|bulgaria|serbia|croazia|slovenia|bosnia|kosovo|polonia|ungheria|"
    "svezia|norvegia|danimarca|finlandia|egitto|marocco|tunisia|libia|algeria|nigeria|sudafrica|australia|thailandia|"
    "filippine|indonesia|dubai|emirati|arabia saudita|qatar|"
    "parigi|marsiglia|lione|nizza|londra|manchester|berlino|monaco di baviera|amburgo|madrid|barcellona|ibiza|"
    "lisbona|vienna|zurigo|ginevra|lugano|bruxelles|amsterdam|atene|istanbul|mosca|kiev|kyiv|varsavia|budapest|"
    "bucarest|tirana|belgrado|new york|los angeles|washington|chicago|miami|texas|california|florida|"
    "città del messico|rio de janeiro|san paolo|buenos aires|pechino|tokyo|tel aviv|gerusalemme"
)
_RE_ESTERO = re.compile(
    rf"\b(?:in|a|ad|nel|nella|nei|negli|dal|dalla|dagli|tra|fra)\s+(?:{PAESI_ESTERI})\b|"
    r"\b(?:polizia|esercito|gendarmeria|governo|autorità|procura|giustizia|tribunale|stampa|media|marina|polizia federale)\s+"
    r"(?:frances[ei]|tedesc[aoh]e?|spagnol[ao]|svizzer[ao]|messican[ao]|american[ao]|statunitens[ei]|britannic[ao]|"
    r"ingles[ei]|russ[ao]|ucrain[ao]|cines[ei]|brasilian[ao]|argentin[ao]|grec[ao]|turc[ao]|albanes[ei]|romen[ao]|"
    r"belg[ao]|olandes[ei]|austriac[ao]|israelian[ao]|egizian[ao]|marocchin[ao]|tunisin[ao]|colombian[ao])\b|"
    r"\bnegli usa\b|\bfbi\b|\bcontea di\b|\bcartello (?:di|del) |narcos\b",
    re.IGNORECASE,
)


# Sezioni dei siti dedicate all'estero (es. today.it/europa/, repubblica.it/esteri/)
_RE_URL_ESTERO = re.compile(r"/(?:esteri|estero|mondo|europa|world|internazionale|internazionali|international)/", re.IGNORECASE)


def e_estero(titolo: str, testo: str, url: str = "") -> bool:
    """Il fatto è avvenuto all'estero: segnali stranieri (titolo, attacco, sezione del sito) e nessun luogo italiano."""
    attacco = (testo or "")[:1500]
    segnali = len(_RE_ESTERO.findall(titolo or "")) * 2 + len(_RE_ESTERO.findall(attacco))
    segnali += 2 if _RE_URL_ESTERO.search(url or "") else 0
    if segnali < 1:
        return False
    from .luoghi import trova_luogo

    comune, provincia, _ = trova_luogo(None, titolo or "", testo or "")
    return comune is None and provincia is None


def _non_cronaca(titolo: str, motivo: str = "") -> dict:
    return {"is_crime_news": False, "sintesi": (titolo or "")[:200], "categorie": [], "fase": Fase.NOTIZIA,
            "contesto": Contesto.ALTRO, "aggressione": False, "arma": Arma.NON_SPECIFICATA,
            "confidenza": Confidenza.BASSA, "evidenza": "", "motivo_scarto": motivo}


def estrai_con_parole_chiave(titolo: str, testo: str, url: str = "") -> dict:
    """Classificatore di riserva: semplice, trasparente, con confidenza sempre bassa."""
    if e_suicidio(titolo):
        return _non_cronaca(titolo, "suicidio")
    if e_estero(titolo, testo, url):
        return _non_cronaca(titolo, "estero")
    if NON_FATTO.search(titolo or ""):
        return {"is_crime_news": False, "sintesi": titolo[:200], "categorie": [], "fase": Fase.NOTIZIA,
                "contesto": Contesto.ALTRO, "aggressione": False, "arma": Arma.NON_SPECIFICATA,
                "confidenza": Confidenza.BASSA, "evidenza": ""}
    t = f"{titolo}\n{testo}".lower()
    trovate, evidenza, nel_titolo, occorrenze = [], "", False, 0
    titolo_l = (titolo or "").lower()
    for cat in CategoriaReato.objects.exclude(parole_chiave=""):
        for parola in cat.lista_parole_chiave:
            trovati = list(re.finditer(rf"\b{re.escape(parola)}", t))
            if trovati:
                trovate.append(cat.slug)
                occorrenze += len(trovati)
                nel_titolo = nel_titolo or bool(re.search(rf"\b{re.escape(parola)}", titolo_l))
                if not evidenza:
                    m = trovati[0]
                    inizio = max(0, m.start() - 80)
                    evidenza = f"{titolo}\n{testo}"[inizio:m.end() + 80].replace("\n", " ").strip()
                break
    # Una parola isolata nel corpo ("ha rubato la scena") non basta: serve nel titolo o almeno due volte
    if trovate and not nel_titolo and occorrenze < 2:
        trovate = []
    # E serve un contesto da cronaca giudiziaria: forze dell'ordine, procura, denuncia, arresto, vittime...
    if trovate and not CONTESTO_REATO.search(t):
        trovate = []
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


def estrai(titolo: str, testo: str, url: str = "") -> dict:
    if settings.LLM["API_KEY"]:
        try:
            dati = estrai_con_llm(titolo, testo)
            dati["metodo"] = "llm"
            # le stesse esclusioni valgono anche per il modello
            if dati.get("is_crime_news") and (e_suicidio(titolo) or e_estero(titolo, testo, url)):
                dati["is_crime_news"] = False
            return dati
        except Exception as e:  # rete, quota, risposta malformata: si ripiega sulle parole chiave
            log.warning("Estrazione LLM fallita, uso parole chiave: %s", e)
    dati = estrai_con_parole_chiave(titolo, testo, url)
    dati["metodo"] = "parole_chiave"
    return dati


def a_json(dati: dict) -> str:
    return json.dumps(dati, ensure_ascii=False, default=str)
