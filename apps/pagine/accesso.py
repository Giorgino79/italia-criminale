"""Protezione con password per le demo (HTTP Basic).

Se la variabile ACCESSO_PASSWORD è impostata, tutto il sito chiede utente e password
(utente: ACCESSO_UTENTE, default "demo"). Senza la variabile il sito è pubblico.
Nella finestra del browser funzionano anche le credenziali di qualsiasi utente Django attivo
(creati con createsuperuser o da /admin → Utenti). Chi ha già fatto login in /admin entra senza
seconda password.
"""
import base64
import hmac

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponse


class AccessoDemoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        password = settings.ACCESSO_PASSWORD
        if not password or request.path.startswith("/admin/"):
            return self.get_response(request)
        utente_django = getattr(request, "user", None)
        if utente_django is not None and utente_django.is_authenticated:
            return self.get_response(request)
        intestazione = request.META.get("HTTP_AUTHORIZATION", "")
        if intestazione.startswith("Basic "):
            try:
                utente, _, pwd = base64.b64decode(intestazione[6:]).decode().partition(":")
            except (ValueError, UnicodeDecodeError):
                utente, pwd = "", ""
            if hmac.compare_digest(utente, settings.ACCESSO_UTENTE) and hmac.compare_digest(pwd, password):
                return self.get_response(request)
            if utente and pwd:
                persona = authenticate(request, username=utente, password=pwd)
                if persona is not None and persona.is_active:
                    return self.get_response(request)
        risposta = HttpResponse("Accesso riservato", status=401)
        risposta["WWW-Authenticate"] = 'Basic realm="Italia Criminale (anteprima)"'
        return risposta
