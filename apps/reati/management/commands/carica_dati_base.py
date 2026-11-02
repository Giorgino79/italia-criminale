"""Carica regioni e tassonomia dei reati. Si può rieseguire senza creare duplicati."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.reati.models import CategoriaReato, MacroCategoria
from apps.reati.tassonomia import TASSONOMIA
from apps.territorio.dati import REGIONI
from apps.territorio.models import Regione


class Command(BaseCommand):
    help = "Carica regioni italiane e tassonomia dei reati"

    @transaction.atomic
    def handle(self, *args, **opts):
        for codice, nome in REGIONI:
            Regione.objects.update_or_create(codice_istat=codice, defaults={"nome": nome})

        ordine_macro = {}
        for macro_nome, nome, slug, rif, parole in TASSONOMIA:
            if macro_nome not in ordine_macro:
                ordine_macro[macro_nome] = len(ordine_macro) + 1
            macro, _ = MacroCategoria.objects.update_or_create(
                slug=slugify(macro_nome),
                defaults={"nome": macro_nome, "ordine": ordine_macro[macro_nome]},
            )
            CategoriaReato.objects.update_or_create(
                slug=slug,
                defaults={
                    "nome": nome,
                    "macro": macro,
                    "riferimento_normativo": rif,
                    "parole_chiave": "\n".join(parole),
                },
            )
        self.stdout.write(self.style.SUCCESS(
            f"Regioni: {Regione.objects.count()} · Macro-categorie: {MacroCategoria.objects.count()} · "
            f"Categorie: {CategoriaReato.objects.count()}"
        ))
