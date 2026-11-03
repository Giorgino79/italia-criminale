from django.core import mail
from django.test import override_settings

from apps.fatti.models import Fatto


@override_settings(SEGNALAZIONI_EMAIL=["redazione@example.org"])
def test_segnalazione_manda_email(client, db):
    fatto = Fatto.objects.create(sintesi="Rapina in centro")
    r = client.post(f"/fatti/{fatto.pk}/", {"testo": "Il luogo è sbagliato", "email": "lettore@example.org"})
    assert r.status_code == 302
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    assert m.to == ["redazione@example.org"] and m.reply_to == ["lettore@example.org"]
    assert "Il luogo è sbagliato" in m.body and f"/admin/fatti/fatto/{fatto.pk}/change/" in m.body


@override_settings(SEGNALAZIONI_EMAIL=[])
def test_senza_destinatari_nessuna_email(client, db):
    fatto = Fatto.objects.create(sintesi="Furto")
    client.post(f"/fatti/{fatto.pk}/", {"testo": "Errore"})
    assert len(mail.outbox) == 0 and fatto.segnalazioni.count() == 1


@override_settings(SEGNALAZIONI_EMAIL=["redazione@example.org"],
                   EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="host.inesistente.invalid",
                   EMAIL_TIMEOUT=2)
def test_errore_smtp_non_blocca_il_lettore(client, db):
    fatto = Fatto.objects.create(sintesi="Furto")
    r = client.post(f"/fatti/{fatto.pk}/", {"testo": "Errore"})
    assert r.status_code == 302 and fatto.segnalazioni.count() == 1
