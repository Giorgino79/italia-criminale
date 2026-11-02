"""Gerarchia territoriale: regione > provincia > comune > quartiere."""
from django.db import models


class Regione(models.Model):
    nome = models.CharField(max_length=60, unique=True)
    codice_istat = models.CharField(max_length=2, unique=True)
    popolazione = models.PositiveIntegerField(null=True, blank=True, help_text="Residenti (ISTAT)")
    popolazione_straniera = models.PositiveIntegerField(null=True, blank=True, help_text="Residenti stranieri (ISTAT)")

    class Meta:
        verbose_name_plural = "regioni"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Provincia(models.Model):
    nome = models.CharField(max_length=80)
    sigla = models.CharField(max_length=2, unique=True)
    regione = models.ForeignKey(Regione, on_delete=models.PROTECT, related_name="province")

    class Meta:
        verbose_name_plural = "province"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.sigla})"


class Comune(models.Model):
    nome = models.CharField(max_length=120)
    codice_istat = models.CharField(max_length=6, unique=True, null=True, blank=True)
    provincia = models.ForeignKey(Provincia, on_delete=models.PROTECT, related_name="comuni")
    popolazione = models.PositiveIntegerField(null=True, blank=True, help_text="Residenti (ISTAT)")
    popolazione_straniera = models.PositiveIntegerField(null=True, blank=True, help_text="Residenti stranieri (ISTAT)")
    capoluogo = models.BooleanField(default=False, help_text="Capoluogo di provincia o città metropolitana")
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "comuni"
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["nome", "provincia"], name="comune_unico_per_provincia")]

    def __str__(self):
        return self.nome

    @property
    def regione(self):
        return self.provincia.regione


class Quartiere(models.Model):
    nome = models.CharField(max_length=120)
    comune = models.ForeignKey(Comune, on_delete=models.CASCADE, related_name="quartieri")
    popolazione = models.PositiveIntegerField(null=True, blank=True)
    alias = models.TextField(blank=True, help_text="Altri nomi con cui la cronaca indica la zona, uno per riga")

    class Meta:
        verbose_name_plural = "quartieri"
        ordering = ["comune__nome", "nome"]
        constraints = [models.UniqueConstraint(fields=["nome", "comune"], name="quartiere_unico_per_comune")]

    def __str__(self):
        return f"{self.nome} ({self.comune})"
