"""Avviso email a ogni segnalazione di errore inviata dai lettori."""
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse

log = logging.getLogger(__name__)


def avvisa_segnalazione(request, segnalazione) -> bool:
    """Invia l'email ai destinatari in SEGNALAZIONI_EMAIL. Un errore di invio non blocca il lettore:
    la segnalazione resta comunque salvata in /admin."""
    destinatari = settings.SEGNALAZIONI_EMAIL
    if not destinatari:
        return False
    fatto = segnalazione.fatto
    link_pubblico = request.build_absolute_uri(reverse("dettaglio_fatto", args=[fatto.pk]))
    link_admin = request.build_absolute_uri(reverse("admin:fatti_fatto_change", args=[fatto.pk]))
    link_segnalazioni = request.build_absolute_uri(reverse("admin:fatti_segnalazioneerrore_changelist"))
    corpo = (
        f"Nuova segnalazione di errore sul fatto #{fatto.pk}\n"
        f"«{fatto.sintesi}»\n\n"
        f"Testo della segnalazione:\n{segnalazione.testo}\n\n"
        f"Email del lettore: {segnalazione.email or 'non indicata'}\n\n"
        f"Scheda pubblica: {link_pubblico}\n"
        f"Modifica il fatto: {link_admin}\n"
        f"Tutte le segnalazioni: {link_segnalazioni}\n"
    )
    messaggio = EmailMessage(
        subject=f"[Italia Criminale] Segnalazione sul fatto #{fatto.pk}",
        body=corpo,
        to=destinatari,
        reply_to=[segnalazione.email] if segnalazione.email else None,
    )
    try:
        messaggio.send()
        return True
    except Exception as e:  # SMTP non configurato o non raggiungibile
        log.error("Avviso segnalazione non inviato: %s", e)
        return False
