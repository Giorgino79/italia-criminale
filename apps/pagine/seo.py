"""SEO: sitemap per Google, robots.txt e indirizzo canonico del sito."""
from datetime import date

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.cache import cache_page

from apps.fatti.models import Fatto


class PagineStatiche(Sitemap):
    protocol = "https"

    def items(self):
        return ["home", "casi", "fatti_del_giorno", "elenco_fatti", "statistiche", "mappa", "metodologia", "chi_siamo", "contatti", "privacy", "cookie"]

    def location(self, item):
        return reverse(item)

    def changefreq(self, item):
        return "hourly" if item in ("home", "casi", "fatti_del_giorno", "elenco_fatti") else "monthly"

    def priority(self, item):
        return 1.0 if item == "home" else 0.7


class Reati(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.6
    limit = 5000

    def items(self):
        return Fatto.objects.pubblicati().order_by("-pk")

    def location(self, fatto):
        return reverse("dettaglio_fatto", args=[fatto.pk])

    def lastmod(self, fatto):
        return fatto.aggiornato_il


class Giorni(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.5

    def items(self):
        giorni = (Fatto.objects.pubblicati()
                  .annotate(g=Coalesce("data_ultimo_sviluppo", "data_evento"))
                  .exclude(g=None).values_list("g", flat=True).distinct())
        return sorted({g for g in giorni if g <= date.today()}, reverse=True)

    def location(self, giorno):
        return reverse("fatti_del_giorno_data", args=[giorno.isoformat()])


class Casi(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.8

    def items(self):
        from apps.fatti.models import Caso

        return Caso.objects.filter(articoli__isnull=False).distinct()

    def lastmod(self, caso):
        ultimo = caso.articoli.order_by("-pubblicato_il").values_list("pubblicato_il", flat=True).first()
        return max(filter(None, [ultimo, caso.aggiornato_il]))


SITEMAPS = {"pagine": PagineStatiche, "casi": Casi, "reati": Reati, "giorni": Giorni}


@cache_page(60 * 60)
def robots_txt(request):
    righe = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /esporta/",
        "Disallow: /interno/",
        "",
        f"Sitemap: {settings.SITO_URL}/sitemap.xml",
    ]
    return HttpResponse("\n".join(righe) + "\n", content_type="text/plain")


def sito(request):
    """Context processor: indirizzo canonico della pagina (senza parametri di ricerca) e pubblicità."""
    return {
        "SITO_URL": settings.SITO_URL,
        "url_canonico": f"{settings.SITO_URL}{request.path}",
        # niente annunci a chi amministra il sito: Google vieta i clic sui propri annunci
        "ADSENSE_CLIENT": "" if getattr(request, "user", None) and request.user.is_staff else settings.ADSENSE_CLIENT,
    }


def ads_txt(request):
    """Dichiara a Google chi è autorizzato a vendere gli annunci di questo sito."""
    righe = []
    if settings.ADSENSE_CLIENT:
        pub = settings.ADSENSE_CLIENT.removeprefix("ca-")
        righe.append(f"google.com, {pub}, DIRECT, f08c47fec0942fa0")
    return HttpResponse("\n".join(righe) + "\n", content_type="text/plain")
