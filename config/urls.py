from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.decorators.cache import cache_page
from django.views.generic import RedirectView

from apps.pagine.seo import SITEMAPS, ads_txt, robots_txt

admin.site.site_header = "Osservatorio Reati – amministrazione"
admin.site.site_title = "Osservatorio Reati"

urlpatterns = [
    # i browser chiedono /favicon.ico anche senza il tag nella pagina
    path("favicon.ico", RedirectView.as_view(url=settings.STATIC_URL + "favicon.ico", permanent=True)),
    path("robots.txt", robots_txt),
    path("ads.txt", ads_txt),
    path("sitemap.xml", cache_page(60 * 60)(sitemap), {"sitemaps": SITEMAPS}, name="sitemap"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("esporta/", include("apps.esportazioni.urls")),
    path("", include("apps.pagine.urls")),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
