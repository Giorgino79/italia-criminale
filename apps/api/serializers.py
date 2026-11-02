from rest_framework import serializers

from apps.fatti.models import Fatto
from apps.fonti.models import Articolo, Testata
from apps.reati.models import CategoriaReato


class CategoriaSerializer(serializers.ModelSerializer):
    macro = serializers.CharField(source="macro.nome")

    class Meta:
        model = CategoriaReato
        fields = ["slug", "nome", "macro", "riferimento_normativo"]


class FonteSerializer(serializers.ModelSerializer):
    testata = serializers.CharField(source="testata.nome")

    class Meta:
        model = Articolo
        fields = ["url", "titolo", "testata", "pubblicato_il"]


class FattoSerializer(serializers.ModelSerializer):
    categorie = serializers.SlugRelatedField(many=True, read_only=True, slug_field="slug")
    comune = serializers.CharField(source="comune.nome", default=None)
    regione = serializers.CharField(source="regione.nome", default=None)
    quartiere = serializers.CharField(source="quartiere.nome", default=None)
    fonti = FonteSerializer(source="articoli", many=True, read_only=True)
    lat = serializers.SerializerMethodField()
    lon = serializers.SerializerMethodField()

    class Meta:
        model = Fatto
        fields = ["id", "sintesi", "data_evento", "categorie", "fase", "regione", "comune", "quartiere",
                  "precisione", "lat", "lon", "contesto", "aggressione", "arma", "esito_manifestazione",
                  "confidenza", "evidenza", "stato_revisione", "n_testate", "n_articoli", "data_ultimo_sviluppo",
                  "fonti"]

    def get_lat(self, obj):
        return obj.lat if obj.mostra_coordinate else None

    def get_lon(self, obj):
        return obj.lon if obj.mostra_coordinate else None


class TestataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testata
        fields = ["nome", "url_home", "tipo"]
