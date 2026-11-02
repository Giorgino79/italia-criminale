"""Protezione con password per le demo (HTTP Basic).

Se la variabile ACCESSO_PASSWORD è impostata, tutto il sito chiede utente e password
(utente: ACCESSO_UTENTE, default "demo"). Senza la variabile il sito è pubblico.
"""
import base64
import hmac

from django.conf import settings
from django.http import HttpResponse


class AccessoDemoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        password = settings.ACCESSO_PASSWORD
        if not password or request.path.startswith("/admin/"):
            return self.get_response(request)
        intestazione = request.META.get("HTTP_AUTHORIZATION", "")
        if intestazione.startswith("Basic "):
            try:
                utente, _, pwd = base64.b64decode(intestazione[6:]).decode().partition(":")
            except (ValueError, UnicodeDecodeError):
                utente, pwd = "", ""
            if hmac.compare_digest(utente, settings.ACCESSO_UTENTE) and hmac.compare_digest(pwd, password):
                return self.get_response(request)
        risposta = HttpResponse("Accesso riservato", status=401)
        risposta["WWW-Authenticate"] = 'Basic realm="Italia Criminale (anteprima)"'
        return risposta
