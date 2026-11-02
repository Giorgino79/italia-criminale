from django.contrib import admin

from .models import Articolo, Testata, VersioneArticolo


@admin.register(Testata)
class TestataAdmin(admin.ModelAdmin):
    list_display = ["nome", "tipo", "orientamento", "attiva", "ultimo_controllo"]
    list_filter = ["tipo", "orientamento", "attiva", "regioni_copertura"]
    search_fields = ["nome"]
    filter_horizontal = ["regioni_copertura"]
    autocomplete_fields = ["comuni_copertura"]


class VersioneInline(admin.TabularInline):
    model = VersioneArticolo
    extra = 0
    fields = ["controllato_il", "titolo", "differenze"]
    readonly_fields = fields


@admin.register(Articolo)
class ArticoloAdmin(admin.ModelAdmin):
    list_display = ["titolo", "testata", "pubblicato_il", "stato", "controlli_eseguiti"]
    list_filter = ["stato", "testata"]
    search_fields = ["titolo", "url"]
    date_hierarchy = "pubblicato_il"
    inlines = [VersioneInline]
