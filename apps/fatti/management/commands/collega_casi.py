"""Collega ai casi seguiti tutti gli articoli già in archivio (da lanciare dopo aver creato o modificato un caso).

    python manage.py collega_casi
    python manage.py collega_casi --caso garlasco
"""
from django.core.management.base import BaseCommand

from apps.fatti.casi import collega
from apps.fatti.models import Caso
from apps.fonti.models import Articolo


class Command(BaseCommand):
    help = "Collega gli articoli in archivio ai casi seguiti"

    def add_arguments(self, parser):
        parser.add_argument("--caso", help="slug di un solo caso")

    def handle(self, caso=None, **opts):
        casi = Caso.objects.all()
        if caso:
            casi = casi.filter(slug=caso)
        casi = list(casi)
        for c in casi:
            c.articoli.clear()  # si ricalcola da zero: le parole chiave possono essere cambiate
        for articolo in Articolo.objects.only("pk", "titolo").iterator():
            collega(articolo, casi)
        for c in casi:
            self.stdout.write(f"{c.nome}: {c.articoli.count()} articoli, {c.reati().count()} reati")
