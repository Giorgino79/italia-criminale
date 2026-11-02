"""Tassonomia dei reati: macro-categoria > categoria, con riferimento normativo indicativo."""
from django.db import models


class MacroCategoria(models.Model):
    nome = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "macro-categoria"
        verbose_name_plural = "macro-categorie"
        ordering = ["ordine", "nome"]

    def __str__(self):
        return self.nome


class CategoriaReato(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    macro = models.ForeignKey(MacroCategoria, on_delete=models.PROTECT, related_name="categorie")
    riferimento_normativo = models.CharField(
        max_length=200, blank=True, help_text="Indicativo, non è una qualificazione giuridica"
    )
    parole_chiave = models.TextField(
        blank=True, help_text="Parole usate dal classificatore di riserva, una per riga"
    )

    class Meta:
        verbose_name = "categoria di reato"
        verbose_name_plural = "categorie di reato"
        ordering = ["macro__ordine", "nome"]

    def __str__(self):
        return self.nome

    @property
    def lista_parole_chiave(self):
        return [p.strip().lower() for p in self.parole_chiave.splitlines() if p.strip()]
