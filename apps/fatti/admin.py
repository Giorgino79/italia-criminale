from django.contrib import admin

from .models import EventoFatto, Fatto, FattoArticolo, Revisione, SegnalazioneErrore


class InAttesaFilter(admin.SimpleListFilter):
    """Per seguire i procedimenti: arresti e denunce senza esito dopo molti mesi."""

    title = "in attesa di esito"
    parameter_name = "attesa"

    def lookups(self, request, model_admin):
        return [("12", "da oltre 12 mesi"), ("36", "da oltre 3 anni")]

    def queryset(self, request, queryset):
        if self.value():
            from datetime import timedelta

            from django.utils import timezone

            from apps.reati.choices import FASI_IN_ATTESA

            limite = timezone.localdate() - timedelta(days=30 * int(self.value()))
            return queryset.filter(fase__in=FASI_IN_ATTESA, data_evento__lt=limite)
        return queryset


class FonteInline(admin.TabularInline):
    model = FattoArticolo
    extra = 0
    autocomplete_fields = ["articolo"]


class EventoInline(admin.TabularInline):
    model = EventoFatto
    extra = 0


@admin.register(Fatto)
class FattoAdmin(admin.ModelAdmin):
    list_display = ["sintesi", "data_evento", "comune", "fase", "data_ultimo_sviluppo", "n_testate", "confidenza", "stato_revisione"]
    list_filter = ["stato_revisione", InAttesaFilter, "confidenza", "fase", "cittadinanza_autori", "categorie__macro",
                   "provincia__regione"]
    readonly_fields = ["n_testate", "n_articoli"]
    search_fields = ["sintesi", "luogo_testo"]
    date_hierarchy = "data_evento"
    filter_horizontal = ["categorie"]
    autocomplete_fields = ["provincia", "comune", "quartiere"]
    inlines = [FonteInline, EventoInline]
    actions = ["segna_verificato", "unisci_fatti"]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.aggiorna_contatori()

    @admin.action(description="Unisci i fatti selezionati (stesso episodio)")
    def unisci_fatti(self, request, queryset):
        from .servizi import unisci

        fatti = list(queryset.order_by("creato_il"))
        if len(fatti) < 2:
            self.message_user(request, "Seleziona almeno due fatti.", level="warning")
            return
        principale = unisci(fatti[0], fatti[1:])
        self.message_user(request, f"Uniti {len(fatti)} fatti nel #{principale.pk}: «{principale.sintesi[:80]}»")

    @admin.action(description="Segna come verificato")
    def segna_verificato(self, request, queryset):
        for fatto in queryset:
            Revisione.objects.create(fatto=fatto, revisore=request.user, esito=Fatto.StatoRevisione.VERIFICATO)
        queryset.update(stato_revisione=Fatto.StatoRevisione.VERIFICATO)


@admin.register(SegnalazioneErrore)
class SegnalazioneAdmin(admin.ModelAdmin):
    list_display = ["fatto", "creata_il", "gestita"]
    list_filter = ["gestita"]
    list_editable = ["gestita"]
