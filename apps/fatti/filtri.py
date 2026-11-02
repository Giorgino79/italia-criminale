"""Filtri condivisi da pagine, esportazioni e API."""
import django_filters

from apps.reati.choices import FASI_CON_ESITO, FASI_IN_ATTESA, Cittadinanza, Contesto, Fase
from apps.reati.models import CategoriaReato, MacroCategoria
from apps.territorio.models import Comune, Provincia, Quartiere, Regione

from .models import Fatto


class FattoFilter(django_filters.FilterSet):
    dal = django_filters.DateFilter(field_name="data_evento", lookup_expr="gte", label="Dal")
    al = django_filters.DateFilter(field_name="data_evento", lookup_expr="lte", label="Al")
    macro = django_filters.ModelChoiceFilter(
        field_name="categorie__macro", queryset=MacroCategoria.objects.all(), label="Macro-categoria", distinct=True
    )
    categoria = django_filters.ModelChoiceFilter(
        field_name="categorie", queryset=CategoriaReato.objects.all(), label="Reato", distinct=True
    )
    regione = django_filters.ModelChoiceFilter(
        field_name="comune__provincia__regione", queryset=Regione.objects.all(), label="Regione"
    )
    provincia = django_filters.ModelChoiceFilter(
        field_name="comune__provincia", queryset=Provincia.objects.all(), label="Provincia"
    )
    comune = django_filters.ModelChoiceFilter(queryset=Comune.objects.filter(fatti__isnull=False).distinct(), label="Città")
    quartiere = django_filters.ModelChoiceFilter(queryset=Quartiere.objects.all(), label="Quartiere")
    fase = django_filters.ChoiceFilter(choices=Fase.choices, label="Fase")
    contesto = django_filters.ChoiceFilter(choices=Contesto.choices, label="Contesto")
    aggressione = django_filters.BooleanFilter(label="Aggressione")
    esito = django_filters.ChoiceFilter(
        choices=[("noto", "Esito noto"), ("in_attesa", "In attesa di esito")], method="filtra_esito", label="Esito"
    )
    min_testate = django_filters.NumberFilter(field_name="n_testate", lookup_expr="gte", label="Riportato da almeno N testate")
    cerca = django_filters.CharFilter(field_name="sintesi", lookup_expr="icontains", label="Testo")
    ordina = django_filters.OrderingFilter(
        fields=(("data_evento", "data"), ("n_testate", "testate"), ("data_ultimo_sviluppo", "sviluppo")),
        field_labels={"data_evento": "Data", "n_testate": "Più ripresi", "data_ultimo_sviluppo": "Ultimo sviluppo"},
        label="Ordina",
    )

    def filtra_esito(self, queryset, name, value):
        if value == "noto":
            return queryset.filter(fase__in=FASI_CON_ESITO)
        if value == "in_attesa":
            return queryset.filter(fase__in=FASI_IN_ATTESA)
        return queryset

    class Meta:
        model = Fatto
        fields = []


class FattoFilterStatistiche(FattoFilter):
    """Solo per le statistiche aggregate: la cittadinanza non si usa per elencare singoli fatti."""

    cittadinanza = django_filters.ChoiceFilter(
        field_name="cittadinanza_autori", choices=Cittadinanza.choices, label="Cittadinanza autori (riportata)"
    )


def filtra(params, statistiche=False):
    classe = FattoFilterStatistiche if statistiche else FattoFilter
    return classe(params, queryset=Fatto.objects.pubblicati().con_relazioni())
