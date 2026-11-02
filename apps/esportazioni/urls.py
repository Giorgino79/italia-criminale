from django.urls import path

from . import views

app_name = "esporta"
urlpatterns = [
    path("excel/", views.esporta_excel, name="excel"),
    path("pdf/", views.esporta_pdf, name="pdf"),
    path("csv/", views.esporta_csv, name="csv"),
]
