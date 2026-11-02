from django.conf import settings
from django.contrib import admin
from django.templatetags.static import static
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "Italia Criminale – amministrazione"
admin.site.site_title = "Italia Criminale"

urlpatterns = [
    # i browser chiedono /favicon.ico anche senza il tag nella pagina
    path("favicon.ico", RedirectView.as_view(url=static("favicon.ico"), permanent=True)),
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("esporta/", include("apps.esportazioni.urls")),
    path("", include("apps.pagine.urls")),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
