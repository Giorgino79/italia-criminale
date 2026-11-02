from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.fatti import statistiche
from apps.fatti.filtri import FattoFilter, filtra
from apps.fatti.models import Fatto
from apps.fonti.models import Testata
from apps.reati.models import CategoriaReato

from .serializers import CategoriaSerializer, FattoSerializer, TestataSerializer


class FattoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Fatto.objects.pubblicati().con_relazioni().prefetch_related("articoli__testata")
    serializer_class = FattoSerializer
    filterset_class = FattoFilter


class CategoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CategoriaReato.objects.select_related("macro")
    serializer_class = CategoriaSerializer
    lookup_field = "slug"
    pagination_class = None


class TestataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Testata.objects.filter(attiva=True)
    serializer_class = TestataSerializer
    pagination_class = None


@api_view(["GET"])
def statistiche_view(request):
    qs = filtra(request.GET, statistiche=True).qs
    return Response({
        "avvertenza": "Conteggi dei fatti riportati dalla cronaca, non dei reati commessi.",
        "riepilogo": statistiche.riepilogo(qs),
        "per_giorno": statistiche.per_giorno(qs),
        "per_categoria": statistiche.per_categoria(qs),
        "per_regione": statistiche.per_regione(qs),
        "per_comune": statistiche.per_comune(qs),
        "per_quartiere": statistiche.per_quartiere(qs),
        "per_fase": statistiche.per_fase(qs),
        "esiti": statistiche.esiti(qs),
        "copertura": statistiche.distribuzione_copertura(qs),
        "cittadinanza_autori": statistiche.cittadinanza(qs),
        "cittadinanza_per_categoria": statistiche.cittadinanza_per_categoria(qs),
        "cittadinanza_per_regione": statistiche.cittadinanza_per_regione(qs),
    })
