from django.contrib import admin

from .models import CategoriaReato, MacroCategoria


class CategoriaInline(admin.TabularInline):
    model = CategoriaReato
    extra = 0
    prepopulated_fields = {"slug": ["nome"]}


@admin.register(MacroCategoria)
class MacroCategoriaAdmin(admin.ModelAdmin):
    list_display = ["nome", "ordine"]
    prepopulated_fields = {"slug": ["nome"]}
    inlines = [CategoriaInline]


@admin.register(CategoriaReato)
class CategoriaReatoAdmin(admin.ModelAdmin):
    list_display = ["nome", "macro", "riferimento_normativo"]
    list_filter = ["macro"]
    search_fields = ["nome"]
    prepopulated_fields = {"slug": ["nome"]}
