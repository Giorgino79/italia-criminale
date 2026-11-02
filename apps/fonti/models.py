"""Testate monitorate, articoli e versioni successive di ogni articolo."""
from django.db import models


class Testata(models.Model):
    class Orientamento(models.TextChoices):
        """Uso SOLO interno: serve a misurare se la copertura dei reati cambia con la linea editoriale.
        Non è esposto sul sito pubblico né nell'API."""

        NON_CLASSIFICATA = "non_classificata", "Non classificata"
        SINISTRA = "sinistra", "Sinistra"
        CENTRO_SINISTRA = "centro_sinistra", "Centro-sinistra"
        CENTRO = "centro", "Centro / generalista"
        CENTRO_DESTRA = "centro_destra", "Centro-destra"
        DESTRA = "destra", "Destra"
        INDIPENDENTE_LOCALE = "locale", "Locale senza linea politica marcata"

    class Tipo(models.TextChoices):
        NAZIONALE = "nazionale", "Nazionale"
        REGIONALE = "regionale", "Regionale"
        LOCALE = "locale", "Locale"

    nome = models.CharField(max_length=120, unique=True)
    url_home = models.URLField()
    feed = models.JSONField(default=list, blank=True, help_text='Elenco di URL RSS, es. ["https://.../rss"]')
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.LOCALE)
    regioni_copertura = models.ManyToManyField("territorio.Regione", blank=True, related_name="testate")
    comuni_copertura = models.ManyToManyField("territorio.Comune", blank=True, related_name="testate")
    attiva = models.BooleanField(default=True)
    orientamento = models.CharField(
        max_length=20, choices=Orientamento.choices, default=Orientamento.NON_CLASSIFICATA, db_index=True,
        help_text="Uso interno, non pubblicato",
    )
    orientamento_fonte = models.CharField(
        max_length=300, blank=True,
        help_text="Su cosa si basa la classificazione (studio, ranking, valutazione redazionale) e data",
    )
    note = models.TextField(blank=True, help_text="Es. riserve sul text and data mining, termini d'uso")
    ultimo_controllo = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "testate"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Articolo(models.Model):
    class Stato(models.TextChoices):
        NUOVO = "nuovo", "Da elaborare"
        NON_CRONACA = "non_cronaca", "Non è cronaca di reati"
        ELABORATO = "elaborato", "Elaborato"
        ERRORE = "errore", "Errore"

    testata = models.ForeignKey(Testata, on_delete=models.PROTECT, related_name="articoli")
    url = models.URLField(max_length=600, unique=True)
    titolo = models.CharField(max_length=500)
    pubblicato_il = models.DateTimeField(null=True, blank=True)
    rilevato_il = models.DateTimeField(auto_now_add=True)
    ultimo_controllo = models.DateTimeField(null=True, blank=True)
    prossimo_controllo = models.DateTimeField(null=True, blank=True, db_index=True)
    controlli_eseguiti = models.PositiveSmallIntegerField(default=0)
    stato = models.CharField(max_length=12, choices=Stato.choices, default=Stato.NUOVO, db_index=True)
    errore = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "articoli"
        ordering = ["-pubblicato_il", "-rilevato_il"]

    def __str__(self):
        return self.titolo


class VersioneArticolo(models.Model):
    """Fotografia di un articolo a un dato controllo.

    Il testo integrale è conservato solo temporaneamente (vedi RACCOLTA['CONSERVA_TESTO_GIORNI']):
    restano hash, titolo, dati estratti e differenze.
    """

    articolo = models.ForeignKey(Articolo, on_delete=models.CASCADE, related_name="versioni")
    controllato_il = models.DateTimeField(auto_now_add=True)
    hash_testo = models.CharField(max_length=64)
    titolo = models.CharField(max_length=500)
    aggiornato_il = models.DateTimeField(null=True, blank=True, help_text="Data di aggiornamento dichiarata dalla testata")
    dati_estratti = models.JSONField(default=dict, blank=True)
    differenze = models.TextField(blank=True, help_text="Cosa è cambiato rispetto alla versione precedente")
    testo_temporaneo = models.TextField(blank=True)

    class Meta:
        verbose_name = "versione articolo"
        verbose_name_plural = "versioni articolo"
        ordering = ["articolo", "controllato_il"]

    def __str__(self):
        return f"{self.articolo} @ {self.controllato_il:%d/%m/%Y %H:%M}"
