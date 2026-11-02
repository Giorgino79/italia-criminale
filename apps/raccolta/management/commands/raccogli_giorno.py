"""Raccoglie dai feed ed elabora gli articoli pubblicati in un giorno.

    python manage.py raccogli_giorno                 # ieri
    python manage.py raccogli_giorno --data 2026-11-01

I feed RSS contengono solo gli ultimi articoli (di solito 1-3 giorni): per un giorno lontano
nel tempo il comando trova poco o niente.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.fonti.models import Articolo, Testata
from apps.raccolta.servizi.feed import leggi_feed
from apps.raccolta.servizi.pipeline import elabora_articolo

ROMA = ZoneInfo("Europe/Rome")


class Command(BaseCommand):
    help = "Legge i feed ed elabora gli articoli di un giorno (default: ieri)"

    def add_arguments(self, parser):
        parser.add_argument("--data", type=date.fromisoformat, help="AAAA-MM-GG, default ieri")
        parser.add_argument("--limite", type=int, default=1000, help="Massimo articoli da elaborare")
        parser.add_argument("--senza-feed", action="store_true", help="Non rilegge i feed, elabora solo")

    def handle(self, data=None, limite=1000, senza_feed=False, **opts):
        giorno = data or (datetime.now(ROMA).date() - timedelta(days=1))
        inizio = datetime.combine(giorno, time.min, ROMA)
        fine = inizio + timedelta(days=1)
        self.stdout.write(self.style.MIGRATE_HEADING(f"Giorno: {giorno:%d/%m/%Y}"))

        if not senza_feed:
            for t in Testata.objects.filter(attiva=True):
                try:
                    n = leggi_feed(t)
                    del_giorno = t.articoli.filter(pubblicato_il__gte=inizio, pubblicato_il__lt=fine).count()
                    stile = self.style.SUCCESS if del_giorno else self.style.WARNING
                    self.stdout.write(stile(f"  {t.nome}: {n} nuovi, {del_giorno} del giorno"))
                except Exception as e:  # una testata che non risponde non deve fermare le altre
                    self.stdout.write(self.style.ERROR(f"  {t.nome}: errore {e}"))

        da_fare = Articolo.objects.filter(
            pubblicato_il__gte=inizio, pubblicato_il__lt=fine, stato=Articolo.Stato.NUOVO
        ).select_related("testata")[:limite]
        totale = len(da_fare)
        self.stdout.write(f"Articoli da elaborare: {totale}")
        for i, articolo in enumerate(da_fare, 1):
            try:
                elabora_articolo(articolo)
            except Exception as e:
                Articolo.objects.filter(pk=articolo.pk).update(stato=Articolo.Stato.ERRORE, errore=str(e)[:500])
                self.stdout.write(self.style.ERROR(f"  errore su {articolo.url}: {e}"))
            if i % 20 == 0 or i == totale:
                self.stdout.write(f"  {i}/{totale}")

        esiti = dict(
            Articolo.objects.filter(pubblicato_il__gte=inizio, pubblicato_il__lt=fine)
            .values_list("stato").annotate(n=Count("id"))
        )
        from apps.fatti.models import Fatto

        fatti = Fatto.objects.filter(data_evento=giorno).count()
        self.stdout.write(self.style.SUCCESS(
            f"Fatto. Articoli: {esiti.get('elaborato', 0)} di cronaca, {esiti.get('non_cronaca', 0)} non di cronaca, "
            f"{esiti.get('errore', 0)} con errori. Fatti del {giorno:%d/%m/%Y}: {fatti}. "
            f"Pagina: /giorno/{giorno.isoformat()}/"
        ))
