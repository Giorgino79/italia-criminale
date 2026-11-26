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
        f"Nuova segnalazione di errore sul reato #{fatto.pk}\n"
        f"«{fatto.sintesi}»\n\n"
        f"Testo della segnalazione:\n{segnalazione.testo}\n\n"
        f"Email del lettore: {segnalazione.email or 'non indicata'}\n\n"
        f"Scheda pubblica: {link_pubblico}\n"
        f"Modifica il reato: {link_admin}\n"
        f"Tutte le segnalazioni: {link_segnalazioni}\n"
    )
    messaggio = EmailMessage(
        subject=f"[Osservatorio Reati] Segnalazione sul reato #{fatto.pk}",
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


def invia_contatto(dati: dict) -> bool:
    """Inoltra il messaggio del modulo Contatti agli indirizzi in SEGNALAZIONI_EMAIL."""
    destinatari = settings.SEGNALAZIONI_EMAIL
    if not destinatari:
        log.warning("Modulo contatti: SEGNALAZIONI_EMAIL non impostato, messaggio non inviato")
        return False
    corpo = (f"Motivo: {dati['motivo']}\nNome: {dati.get('nome') or 'non indicato'}\nEmail: {dati['email']}\n\n"
             f"{dati['messaggio']}\n")
    try:
        EmailMessage(subject=f"[Osservatorio Reati] Contatto: {dati['motivo']}", body=corpo, to=destinatari,
                     reply_to=[dati["email"]]).send()
        return True
    except Exception as e:
        log.error("Messaggio dal modulo contatti non inviato: %s", e)
        return False
