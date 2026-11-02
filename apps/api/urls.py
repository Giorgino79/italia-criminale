from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("fatti", views.FattoViewSet)
router.register("categorie", views.CategoriaViewSet)
router.register("testate", views.TestataViewSet)

urlpatterns = [
    path("statistiche/", views.statistiche_view, name="api-statistiche"),
    path("", include(router.urls)),
]
