"""Elaborazione completa di un articolo: testo > versione > estrazione > luogo > fatto."""
import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.fatti.models import Fatto, FattoArticolo
from apps.fonti.models import Articolo, VersioneArticolo
from apps.reati.choices import FASI_GIUDIZIARIE, Cittadinanza, Confidenza
from apps.reati.models import CategoriaReato

from . import deduplica, estrazione, luoghi, testo

log = logging.getLogger(__name__)


def _prossimo_controllo(articolo: Articolo):
    ore = settings.RACCOLTA["RICONTROLLI_ORE"]
    if articolo.controlli_eseguiti >= len(ore):
        return None
    base = articolo.pubblicato_il or articolo.rilevato_il
    return base + timedelta(hours=ore[articolo.controlli_eseguiti])


def _differenze(precedente: VersioneArticolo | None, titolo: str, dati: dict) -> str:
    if precedente is None:
        return ""
    righe = []
    if precedente.titolo != titolo:
        righe.append(f"Titolo: «{precedente.titolo}» → «{titolo}»")
    for campo in ("fase", "categorie", "luogo_testo", "comune"):
        prima, dopo = precedente.dati_estratti.get(campo), dati.get(campo)
        if prima != dopo:
            righe.append(f"{campo}: {prima} → {dopo}")
    return "\n".join(righe) or "Testo modificato"


def _data(valore) -> date | None:
    try:
        return date.fromisoformat(str(valore)[:10]) if valore else None
    except ValueError:
        return None


def elabora_articolo(articolo: Articolo, scarica=None, escludi_fatto: int | None = None) -> Fatto | None:
    """escludi_fatto: id di un fatto a cui l'articolo NON va ricollegato (separazione manuale)."""
    scarica = scarica or testo.scarica
    try:
        contenuto = scarica(articolo.url)
    except testo.TestoNonDisponibile as e:
        articolo.stato, articolo.errore = Articolo.Stato.ERRORE, str(e)
        articolo.ultimo_controllo = timezone.now()
        articolo.prossimo_controllo = None
        articolo.save(update_fields=["stato", "errore", "ultimo_controllo", "prossimo_controllo"])
        return None

    precedente = articolo.versioni.order_by("-controllato_il").first()
    articolo.controlli_eseguiti += 1
    articolo.ultimo_controllo = timezone.now()
    articolo.prossimo_controllo = _prossimo_controllo(articolo)

    if precedente and precedente.hash_testo == contenuto["hash"]:
        articolo.save(update_fields=["controlli_eseguiti", "ultimo_controllo", "prossimo_controllo"])
        return articolo.fatti.first()

    titolo = contenuto["titolo"] or articolo.titolo
    dati = estrazione.estrai(titolo, contenuto["testo"])

    with transaction.atomic():
        VersioneArticolo.objects.create(
            articolo=articolo,
            hash_testo=contenuto["hash"],
            titolo=titolo[:500],
            dati_estratti=dati,
            differenze=_differenze(precedente, titolo, dati),
            testo_temporaneo=contenuto["testo"],
        )
        articolo.titolo = titolo[:500]
        if not dati.get("is_crime_news"):
            articolo.stato = Articolo.Stato.NON_CRONACA
            articolo.save()
            return None
        articolo.stato = Articolo.Stato.ELABORATO
        articolo.save()
        return _registra_fatto(articolo, dati, contenuto["testo"], escludi_fatto)


def _data_originale(valore):
    """Accetta 'AAAA' (solo anno) o una data completa."""
    if not valore:
        return None
    v = str(valore).strip()
    return v if len(v) == 4 and v.isdigit() else _data(v)


def _registra_fatto(articolo: Articolo, dati: dict, testo_articolo: str, escludi_fatto: int | None = None) -> Fatto:
    testo_completo = f"{articolo.titolo}\n{testo_articolo}"
    comune, provincia, area = luoghi.trova_luogo(dati.get("comune"), articolo.titolo, testo_articolo, articolo.testata)
    quartiere = luoghi.trova_quartiere(comune, testo_completo)
    if not dati.get("luogo_testo") and area:
        dati["luogo_testo"] = area
    data_articolo = timezone.localtime(articolo.pubblicato_il).date() if articolo.pubblicato_il else None
    slugs = dati.get("categorie") or ["altro"]
    nuova_fase = dati.get("fase")
    data_sviluppo = _data(dati.get("data_sviluppo")) or data_articolo
    e_seguito = bool(dati.get("e_seguito")) or nuova_fase in FASI_GIUDIZIARIE
    confronto = f"{articolo.titolo}\n{dati.get('sintesi', '')}"

    # 1) articolo già collegato (nuova versione dello stesso pezzo)
    fatto = articolo.fatti.first()
    # 2) seguito giudiziario di un fatto vecchio, anche di anni prima
    if fatto is None and e_seguito:
        fatto = deduplica.trova_fatto_per_seguito(
            comune=comune, provincia=provincia, categorie_slug=slugs, testo_confronto=confronto, salta=escludi_fatto,
            data_fatto_originale=_data_originale(dati.get("data_fatto_originale")), data_limite=data_articolo,
        )
    # 3) stesso episodio raccontato da un'altra testata nei giorni vicini
    data_evento = _data(dati.get("data_evento")) or data_articolo
    if fatto is None and not e_seguito:
        fatto = deduplica.trova_fatto_esistente(
            comune=comune, provincia=provincia, data_evento=data_evento, categorie_slug=slugs, testo_confronto=confronto,
            salta=escludi_fatto,
        )

    if fatto is None:
        if e_seguito:
            # Seguito di un fatto che non abbiamo in archivio: lo registriamo con la data originale se nota
            originale = _data_originale(dati.get("data_fatto_originale"))
            data_evento = originale if isinstance(originale, date) else None
        lat, lon, precisione = luoghi.geocodifica(dati.get("luogo_testo") if comune else None, comune, provincia)
        fatto = Fatto.objects.create(
            sintesi=dati.get("sintesi", articolo.titolo)[:300],
            fase=nuova_fase or "notizia",
            data_evento=data_evento,
            data_ultimo_sviluppo=data_sviluppo if e_seguito else None,
            provincia=provincia,
            comune=comune,
            quartiere=quartiere,
            luogo_testo=(dati.get("luogo_testo") or "")[:300],
            lat=lat, lon=lon, precisione=precisione,
            contesto=dati.get("contesto", "altro"),
            aggressione=bool(dati.get("aggressione")),
            arma=dati.get("arma", "non_specificata"),
            esito_manifestazione=dati.get("esito_manifestazione") or "",
            noto_forze_ordine=dati.get("noto_forze_ordine"),
            cittadinanza_autori=dati.get("cittadinanza_autori") or Cittadinanza.NON_INDICATA,
            numero_autori=dati.get("numero_autori"),
            cittadinanza_vittime=dati.get("cittadinanza_vittime") or Cittadinanza.NON_INDICATA,
            confidenza=dati.get("confidenza", Confidenza.BASSA),
            evidenza=(dati.get("evidenza") or "")[:1000],
            stato_revisione=Fatto.StatoRevisione.DA_RIVEDERE
            if dati.get("confidenza") != Confidenza.ALTA or e_seguito else Fatto.StatoRevisione.AUTOMATICO,
        )
        fatto.categorie.set(CategoriaReato.objects.filter(slug__in=slugs))
        ruolo = FattoArticolo.Ruolo.PRIMO_LANCIO
    else:
        if e_seguito and not fatto.articoli.filter(pk=articolo.pk).exists():
            ruolo = FattoArticolo.Ruolo.SEGUITO
        elif fatto.articoli.filter(testata=articolo.testata).exists():
            ruolo = FattoArticolo.Ruolo.AGGIORNAMENTO
        else:
            ruolo = FattoArticolo.Ruolo.RIPRESA
        fatto.cambia_fase(nuova_fase, articolo=articolo, data=data_sviluppo)
        _completa_cittadinanza(fatto, dati)
        if e_seguito and ruolo == FattoArticolo.Ruolo.SEGUITO:
            # un collegamento a distanza di tempo va sempre controllato da una persona
            Fatto.objects.filter(pk=fatto.pk).update(stato_revisione=Fatto.StatoRevisione.DA_RIVEDERE)

    FattoArticolo.objects.get_or_create(fatto=fatto, articolo=articolo, defaults={"ruolo": ruolo})
    fatto.aggiorna_contatori()
    return fatto


def _completa_cittadinanza(fatto: Fatto, dati: dict):
    """Un articolo successivo può indicare la cittadinanza che il primo non riportava: non si sovrascrive mai un valore già noto."""
    campi = []
    for campo in ("cittadinanza_autori", "cittadinanza_vittime"):
        nuovo = dati.get(campo)
        if nuovo and nuovo != Cittadinanza.NON_INDICATA and getattr(fatto, campo) == Cittadinanza.NON_INDICATA:
            setattr(fatto, campo, nuovo)
            campi.append(campo)
    if dati.get("numero_autori") and not fatto.numero_autori:
        fatto.numero_autori = dati["numero_autori"]
        campi.append("numero_autori")
    if campi:
        fatto.save(update_fields=campi)
