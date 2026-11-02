"""Lettura dei feed RSS delle testate e registrazione dei nuovi articoli."""
import logging
from datetime import datetime, timezone

import feedparser
import httpx
from django.utils import timezone as djtz

from apps.fonti.models import Articolo, Testata

from .http import client, consentito

log = logging.getLogger(__name__)


def _data(voce) -> datetime | None:
    t = voce.get("published_parsed") or voce.get("updated_parsed")
    return datetime(*t[:6], tzinfo=timezone.utc) if t else None


def leggi_feed(testata: Testata) -> int:
    """Registra gli articoli nuovi dei feed di una testata. Restituisce quanti ne ha aggiunti."""
    nuovi = 0
    with client() as c:
        for url_feed in testata.feed:
            if not consentito(url_feed):
                log.warning("robots.txt non consente %s", url_feed)
                continue
            try:
                risposta = c.get(url_feed)
                risposta.raise_for_status()
            except httpx.HTTPError as e:
                log.warning("Feed non raggiungibile %s: %s", url_feed, e)
                continue
            for voce in feedparser.parse(risposta.content).entries:
                link = voce.get("link")
                if not link:
                    continue
                _, creato = Articolo.objects.get_or_create(
                    url=link,
                    defaults={
                        "testata": testata,
                        "titolo": (voce.get("title") or "")[:500],
                        "pubblicato_il": _data(voce),
                        "prossimo_controllo": djtz.now(),
                    },
                )
                nuovi += creato
    testata.ultimo_controllo = djtz.now()
    testata.save(update_fields=["ultimo_controllo"])
    return nuovi
