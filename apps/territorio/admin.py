from django.contrib import admin

from .models import Comune, Provincia, Quartiere, Regione


@admin.register(Regione)
class RegioneAdmin(admin.ModelAdmin):
    list_display = ["nome", "codice_istat"]


@admin.register(Provincia)
class ProvinciaAdmin(admin.ModelAdmin):
    list_display = ["nome", "sigla", "regione"]
    list_filter = ["regione"]
    search_fields = ["nome", "sigla"]


@admin.register(Comune)
class ComuneAdmin(admin.ModelAdmin):
    list_display = ["nome", "provincia", "popolazione"]
    list_filter = ["provincia__regione"]
    search_fields = ["nome"]
    autocomplete_fields = ["provincia"]


@admin.register(Quartiere)
class QuartiereAdmin(admin.ModelAdmin):
    list_display = ["nome", "comune", "popolazione"]
    search_fields = ["nome", "comune__nome"]
    autocomplete_fields = ["comune"]
