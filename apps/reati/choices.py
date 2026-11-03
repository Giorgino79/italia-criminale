"""Valori ammessi per gli attributi di un fatto (vedi documento di progetto, §1.2)."""
from django.db import models


class Fase(models.TextChoices):
    NOTIZIA = "notizia", "Notizia di reato"
    DENUNCIA = "denuncia", "Denuncia"
    FERMO = "fermo", "Fermo"
    ARRESTO = "arresto", "Arresto"
    MISURA_CAUTELARE = "misura_cautelare", "Misura cautelare"
    RINVIO_GIUDIZIO = "rinvio_giudizio", "Rinvio a giudizio"
    CONDANNA_NON_DEF = "condanna_non_definitiva", "Condanna non definitiva"
    CONDANNA_DEF = "condanna_definitiva", "Condanna definitiva"
    ASSOLUZIONE = "assoluzione", "Assoluzione"
    ARCHIVIAZIONE = "archiviazione", "Archiviazione"


class Contesto(models.TextChoices):
    SPAZIO_PUBBLICO = "spazio_pubblico", "Spazio pubblico"
    ABITAZIONE = "abitazione", "Abitazione"
    LAVORO = "lavoro", "Luogo di lavoro"
    MEZZI_PUBBLICI = "mezzi_pubblici", "Mezzi pubblici"
    LOCALE = "locale", "Locale notturno o pubblico esercizio"
    SCUOLA = "scuola", "Scuola"
    ONLINE = "online", "Online"
    MANIFESTAZIONE = "manifestazione", "Manifestazione o corteo"
    EVENTO_SPORTIVO = "evento_sportivo", "Evento sportivo"
    ALTRO = "altro", "Altro / non specificato"


class Arma(models.TextChoices):
    NESSUNA = "nessuna", "Nessuna"
    TAGLIO = "taglio", "Da taglio"
    FUOCO = "fuoco", "Da fuoco"
    CONTUNDENTE = "contundente", "Oggetto contundente"
    NON_SPECIFICATA = "non_specificata", "Non specificata"


class EsitoManifestazione(models.TextChoices):
    PACIFICA = "pacifica", "Pacifica"
    TENSIONI = "tensioni", "Tensioni"
    SCONTRI = "scontri", "Scontri con le forze dell'ordine"
    DANNEGGIAMENTI = "danneggiamenti", "Danneggiamenti"


class Confidenza(models.TextChoices):
    ALTA = "alta", "Alta (reato esplicito nella fonte)"
    MEDIA = "media", "Media (dedotto dal racconto)"
    BASSA = "bassa", "Bassa (informazioni scarse)"


class Precisione(models.TextChoices):
    INDIRIZZO = "indirizzo", "Indirizzo"
    VIA = "via", "Via"
    QUARTIERE = "quartiere", "Quartiere"
    COMUNE = "comune", "Solo comune"
    PROVINCIA = "provincia", "Solo provincia"
    NESSUNA = "nessuna", "Non localizzato"


# Ordine del procedimento: serve a non "tornare indietro" quando un articolo di riepilogo
# cita una fase già superata (es. "arrestato due anni fa" in un pezzo sulla condanna).
ORDINE_FASI = {
    Fase.NOTIZIA: 0,
    Fase.DENUNCIA: 1,
    Fase.FERMO: 2,
    Fase.ARRESTO: 2,
    Fase.MISURA_CAUTELARE: 3,
    Fase.RINVIO_GIUDIZIO: 4,
    Fase.CONDANNA_NON_DEF: 5,
    Fase.ASSOLUZIONE: 5,
    Fase.ARCHIVIAZIONE: 5,
    Fase.CONDANNA_DEF: 6,
}

FASI_GIUDIZIARIE = {
    Fase.RINVIO_GIUDIZIO, Fase.CONDANNA_NON_DEF, Fase.CONDANNA_DEF, Fase.ASSOLUZIONE, Fase.ARCHIVIAZIONE,
}
FASI_CON_ESITO = {Fase.CONDANNA_NON_DEF, Fase.CONDANNA_DEF, Fase.ASSOLUZIONE, Fase.ARCHIVIAZIONE}
FASI_IN_ATTESA = {Fase.DENUNCIA, Fase.FERMO, Fase.ARRESTO, Fase.MISURA_CAUTELARE, Fase.RINVIO_GIUDIZIO}


def fase_successiva(attuale: str, nuova: str) -> bool:
    """True se la nuova fase è un passo avanti nel procedimento (o un esito diverso allo stesso livello)."""
    a, n = ORDINE_FASI.get(attuale, 0), ORDINE_FASI.get(nuova, 0)
    return n > a or (n == a and n >= 5 and nuova != attuale)


class Cittadinanza(models.TextChoices):
    """Come RIPORTATA dalla fonte. 'Non indicata' è il valore normale, non un dato mancante da riempire."""

    NON_INDICATA = "non_indicata", "Non indicata"
    ITALIANA = "italiana", "Italiana"
    UE = "ue", "Straniera UE"
    EXTRA_UE = "extra_ue", "Straniera extra-UE"
    STRANIERA = "straniera", "Straniera (non specificata)"
    MISTA = "mista", "Mista (più persone)"
