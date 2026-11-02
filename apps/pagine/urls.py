from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("fatti/", views.elenco_fatti, name="elenco_fatti"),
    path("giorno/", views.fatti_del_giorno, name="fatti_del_giorno"),
    path("giorno/<str:giorno>/", views.fatti_del_giorno, name="fatti_del_giorno_data"),
    path("fatti/<int:pk>/", views.dettaglio_fatto, name="dettaglio_fatto"),
    path("statistiche/", views.statistiche_view, name="statistiche"),
    path("mappa/", views.mappa, name="mappa"),
    path("metodologia/", views.metodologia, name="metodologia"),
    path("interno/orientamento/", views.interno_orientamento, name="interno_orientamento"),
]
