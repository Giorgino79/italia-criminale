from django.core.management.base import BaseCommand

from apps.fonti.models import Testata
from apps.fonti.testate_iniziali import TESTATE


class Command(BaseCommand):
    help = "Inserisce il primo elenco di testate nazionali con i feed di cronaca (non sovrascrive le modifiche)"

    def handle(self, **opts):
        nuove = 0
        for nome, home, feed in TESTATE:
            _, creata = Testata.objects.get_or_create(
                nome=nome, defaults={"url_home": home, "feed": feed, "tipo": Testata.Tipo.NAZIONALE}
            )
            nuove += creata
        self.stdout.write(self.style.SUCCESS(f"Testate nuove: {nuove} · totale attive: {Testata.objects.filter(attiva=True).count()}"))
