from django.db import migrations
from django.db.models import Min


def compila(apps, schema_editor):
    """Ai fatti senza nessuna data assegna la data della prima notizia (pubblicazione dell'articolo)."""
    Fatto = apps.get_model("fatti", "Fatto")
    for fatto in Fatto.objects.filter(data_evento__isnull=True, data_ultimo_sviluppo__isnull=True):
        prima = fatto.articoli.aggregate(d=Min("pubblicato_il"))["d"] or fatto.creato_il
        fatto.data_ultimo_sviluppo = prima.date()
        fatto.save(update_fields=["data_ultimo_sviluppo"])


class Migration(migrations.Migration):
    dependencies = [("fatti", "0003_provincia_e_precisione"), ("fonti", "0002_testata_orientamento_testata_orientamento_fonte")]
    operations = [migrations.RunPython(compila, migrations.RunPython.noop)]
