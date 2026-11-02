from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Italia Criminale – amministrazione"
admin.site.site_title = "Italia Criminale"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("esporta/", include("apps.esportazioni.urls")),
    path("", include("apps.pagine.urls")),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
