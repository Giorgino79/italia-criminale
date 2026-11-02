"""Il fatto è l'unità di analisi: più articoli sullo stesso episodio formano un solo fatto.

Nessun dato identificativo di persone (nomi, età precise, foto) viene memorizzato.
"""
from django.conf import settings
from django.db import models

from apps.reati.choices import (
    FASI_CON_ESITO,
    FASI_IN_ATTESA,
    Arma,
    Cittadinanza,
    Confidenza,
    Contesto,
    EsitoManifestazione,
    Fase,
    Precisione,
)


class FattoQuerySet(models.QuerySet):
    def pubblicati(self):
        return self.exclude(stato_revisione=Fatto.StatoRevisione.SCARTATO)

    def con_relazioni(self):
        return self.select_related("comune__provincia__regione", "quartiere").prefetch_related("categorie__macro")


class Fatto(models.Model):
    class StatoRevisione(models.TextChoices):
        AUTOMATICO = "automatico", "Classificato automaticamente"
        DA_RIVEDERE = "da_rivedere", "Da rivedere"
        VERIFICATO = "verificato", "Verificato da una persona"
        SCARTATO = "scartato", "Scartato"

    sintesi = models.CharField(max_length=300, help_text="Descrizione neutra del fatto, senza nomi")
    categorie = models.ManyToManyField("reati.CategoriaReato", related_name="fatti")
    fase = models.CharField(max_length=30, choices=Fase.choices, default=Fase.NOTIZIA)
    data_evento = models.DateField(null=True, blank=True, db_index=True)

    comune = models.ForeignKey("territorio.Comune", null=True, blank=True, on_delete=models.SET_NULL, related_name="fatti")
    quartiere = models.ForeignKey("territorio.Quartiere", null=True, blank=True, on_delete=models.SET_NULL, related_name="fatti")
    luogo_testo = models.CharField(max_length=300, blank=True, help_text="Luogo come citato dalla fonte")
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    precisione = models.CharField(max_length=10, choices=Precisione.choices, default=Precisione.NESSUNA)

    contesto = models.CharField(max_length=20, choices=Contesto.choices, default=Contesto.ALTRO)
    aggressione = models.BooleanField(default=False, help_text="Violenza fisica su persona")
    arma = models.CharField(max_length=20, choices=Arma.choices, default=Arma.NON_SPECIFICATA)
    esito_manifestazione = models.CharField(max_length=20, choices=EsitoManifestazione.choices, blank=True)
    noto_forze_ordine = models.BooleanField(
        null=True, blank=True, help_text="Solo se riportato dalla fonte; mai ricostruito collegando fatti diversi"
    )

    # Cittadinanza come riportata dalla fonte. Mostrata al pubblico solo in forma aggregata.
    cittadinanza_autori = models.CharField(max_length=14, choices=Cittadinanza.choices, default=Cittadinanza.NON_INDICATA, db_index=True)
    numero_autori = models.PositiveSmallIntegerField(null=True, blank=True)
    cittadinanza_vittime = models.CharField(max_length=14, choices=Cittadinanza.choices, default=Cittadinanza.NON_INDICATA)

    # Seguito giudiziario, anche a distanza di anni
    data_ultimo_sviluppo = models.DateField(null=True, blank=True, help_text="Data dell'ultimo cambio di fase rilevato")

    # Contatori di copertura (aggiornati da aggiorna_contatori)
    n_articoli = models.PositiveIntegerField(default=0, db_index=True)
    n_testate = models.PositiveIntegerField(default=0, db_index=True)

    confidenza = models.CharField(max_length=6, choices=Confidenza.choices, default=Confidenza.BASSA)
    evidenza = models.TextField(blank=True, help_text="Breve frase della fonte che giustifica la classificazione")
    stato_revisione = models.CharField(
        max_length=12, choices=StatoRevisione.choices, default=StatoRevisione.AUTOMATICO, db_index=True
    )

    articoli = models.ManyToManyField("fonti.Articolo", through="FattoArticolo", related_name="fatti")
    creato_il = models.DateTimeField(auto_now_add=True)
    aggiornato_il = models.DateTimeField(auto_now=True)

    objects = FattoQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "fatti"
        ordering = ["-data_evento", "-creato_il"]

    def __str__(self):
        return self.sintesi

    @property
    def regione(self):
        return self.comune.provincia.regione if self.comune else None

    @property
    def esito_noto(self) -> bool:
        return self.fase in FASI_CON_ESITO

    @property
    def in_attesa_di_esito(self) -> bool:
        return self.fase in FASI_IN_ATTESA

    def aggiorna_contatori(self, salva=True):
        self.n_articoli = self.articoli.count()
        self.n_testate = self.articoli.values("testata").distinct().count()
        if salva:
            Fatto.objects.filter(pk=self.pk).update(n_articoli=self.n_articoli, n_testate=self.n_testate)

    def cambia_fase(self, nuova: str, *, articolo=None, data=None, descrizione=""):
        """Registra un passo avanti nel procedimento nella cronologia del fatto."""
        from apps.reati.choices import fase_successiva

        if not nuova or not fase_successiva(self.fase, nuova):
            return False
        etichette = dict(Fase.choices)
        EventoFatto.objects.create(
            fatto=self, tipo=EventoFatto.Tipo.CAMBIO_FASE, articolo=articolo,
            fase_precedente=self.fase, fase_nuova=nuova, data_riferimento=data,
            descrizione=descrizione or f"{etichette.get(self.fase, self.fase)} → {etichette.get(nuova, nuova)}",
        )
        self.fase = nuova
        self.data_ultimo_sviluppo = data
        self.save(update_fields=["fase", "data_ultimo_sviluppo", "aggiornato_il"])
        return True

    @property
    def mostra_coordinate(self):
        """Per tutela delle persone, i fatti in abitazione si mostrano solo a livello di quartiere."""
        return self.lat is not None and self.contesto != Contesto.ABITAZIONE


class FattoArticolo(models.Model):
    class Ruolo(models.TextChoices):
        PRIMO_LANCIO = "primo_lancio", "Primo lancio"
        AGGIORNAMENTO = "aggiornamento", "Aggiornamento"
        RIPRESA = "ripresa", "Ripresa da altra testata"
        SEGUITO = "seguito", "Seguito giudiziario"

    fatto = models.ForeignKey(Fatto, on_delete=models.CASCADE)
    articolo = models.ForeignKey("fonti.Articolo", on_delete=models.CASCADE)
    ruolo = models.CharField(max_length=15, choices=Ruolo.choices, default=Ruolo.RIPRESA)
    collegato_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "fonte del fatto"
        verbose_name_plural = "fonti del fatto"
        constraints = [models.UniqueConstraint(fields=["fatto", "articolo"], name="articolo_unico_per_fatto")]


class EventoFatto(models.Model):
    """Cronologia: cambi di fase (es. da arresto ad assoluzione), correzioni, note."""

    class Tipo(models.TextChoices):
        CAMBIO_FASE = "cambio_fase", "Cambio di fase procedurale"
        CORREZIONE = "correzione", "Correzione"
        NOTA = "nota", "Nota"

    fatto = models.ForeignKey(Fatto, on_delete=models.CASCADE, related_name="eventi")
    data = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    descrizione = models.TextField()
    fase_precedente = models.CharField(max_length=30, choices=Fase.choices, blank=True)
    fase_nuova = models.CharField(max_length=30, choices=Fase.choices, blank=True)
    data_riferimento = models.DateField(null=True, blank=True, help_text="Data dello sviluppo (es. sentenza), se nota")
    articolo = models.ForeignKey("fonti.Articolo", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name_plural = "eventi del fatto"
        ordering = ["data"]


class Revisione(models.Model):
    fatto = models.ForeignKey(Fatto, on_delete=models.CASCADE, related_name="revisioni")
    revisore = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    data = models.DateTimeField(auto_now_add=True)
    esito = models.CharField(max_length=12, choices=Fatto.StatoRevisione.choices)
    modifiche = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "revisioni"
        ordering = ["-data"]


class SegnalazioneErrore(models.Model):
    fatto = models.ForeignKey(Fatto, on_delete=models.CASCADE, related_name="segnalazioni")
    testo = models.TextField()
    email = models.EmailField(blank=True, help_text="Facoltativa, solo per rispondere")
    creata_il = models.DateTimeField(auto_now_add=True)
    gestita = models.BooleanField(default=False)

    class Meta:
        verbose_name = "segnalazione di errore"
        verbose_name_plural = "segnalazioni di errore"
        ordering = ["gestita", "-creata_il"]
