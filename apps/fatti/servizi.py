"""Operazioni sui fatti."""
from django.db import transaction

from .models import EventoFatto, Fatto, FattoArticolo


@transaction.atomic
def unisci(principale: Fatto, duplicati: list[Fatto]) -> Fatto:
    """Sposta articoli, cronologia, segnalazioni e categorie dei duplicati sul fatto principale e li elimina.

    Il principale tiene la data più vecchia nota e la fase più avanzata."""
    from apps.reati.choices import fase_successiva

    for dup in duplicati:
        if dup.pk == principale.pk:
            continue
        for fa in FattoArticolo.objects.filter(fatto=dup):
            if not FattoArticolo.objects.filter(fatto=principale, articolo_id=fa.articolo_id).exists():
                fa.fatto = principale
                fa.ruolo = FattoArticolo.Ruolo.RIPRESA if fa.ruolo == FattoArticolo.Ruolo.PRIMO_LANCIO else fa.ruolo
                fa.save()
        dup.eventi.update(fatto=principale)
        dup.segnalazioni.update(fatto=principale)
        dup.revisioni.update(fatto=principale)
        principale.categorie.add(*dup.categorie.all())
        if dup.data_evento and (principale.data_evento is None or dup.data_evento < principale.data_evento):
            principale.data_evento = dup.data_evento
        if fase_successiva(principale.fase, dup.fase):
            principale.fase = dup.fase
        for campo in ("comune", "provincia", "quartiere"):
            if getattr(principale, campo) is None and getattr(dup, campo) is not None:
                setattr(principale, campo, getattr(dup, campo))
        EventoFatto.objects.create(
            fatto=principale, tipo=EventoFatto.Tipo.CORREZIONE,
            descrizione=f"Unito al fatto un duplicato (#{dup.pk}: {dup.sintesi[:120]})",
        )
        dup.delete()
    principale.save()
    principale.aggiorna_contatori()
    return principale
