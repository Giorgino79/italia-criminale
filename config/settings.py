"""Impostazioni del progetto Italia Criminale.

I valori sensibili e quelli che cambiano tra sviluppo e produzione
si leggono dal file .env (vedi .env.example).
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="solo-per-sviluppo-cambiami")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # terze parti
    "rest_framework",
    "django_filters",
    # app del progetto
    "apps.territorio",
    "apps.reati",
    "apps.fonti",
    "apps.fatti",
    "apps.raccolta",
    "apps.esportazioni",
    "apps.pagine",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# In sviluppo SQLite; in produzione: DATABASE_URL=postgres://utente:password@host:5432/nome
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}
if DATABASES["default"]["ENGINE"].endswith("postgresql"):
    DATABASES["default"]["CONN_MAX_AGE"] = 600
    DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = env("DB_SSLMODE", default="require")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "it"
TIME_ZONE = "Europe/Rome"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/minute"},
}

# --- Raccolta e analisi ---
RACCOLTA = {
    # User-Agent dichiarato alle testate: deve permettere di contattarvi
    "USER_AGENT": env("RACCOLTA_USER_AGENT", default="ItaliaCriminaleBot/0.1 (+https://example.org/bot)"),
    "TIMEOUT_SECONDI": env.int("RACCOLTA_TIMEOUT", default=20),
    # Intervalli di ricontrollo degli articoli per tracciare gli aggiornamenti
    "RICONTROLLI_ORE": [1, 6, 24, 168],
    # Giorni dopo cui si cancella il testo integrale (si tengono solo metadati ed estratti)
    "CONSERVA_TESTO_GIORNI": env.int("CONSERVA_TESTO_GIORNI", default=7),
}

LLM = {
    "API_KEY": env("ANTHROPIC_API_KEY", default=""),
    "MODELLO": env("LLM_MODELLO", default="claude-sonnet-5-5"),
}

GEOCODING = {
    "USER_AGENT": env("GEOCODING_USER_AGENT", default="ItaliaCriminale/0.1"),
    # Nominatim pubblico: massimo 1 richiesta al secondo. In produzione usare un'istanza propria.
    "NOMINATIM_URL": env("NOMINATIM_URL", default="nominatim.openstreetmap.org"),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"apps": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")}},
}

# --- Email ---
# EMAIL_URL, es. con Gmail: smtp+tls://indirizzo%40gmail.com:PASSWORD-PER-APP@smtp.gmail.com:587
# Senza EMAIL_URL le email vengono stampate nel terminale (utile in locale).
if env("EMAIL_URL", default=""):
    vars().update(env.email_url("EMAIL_URL"))
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Italia Criminale <noreply@localhost>")
# Chi riceve l'avviso a ogni segnalazione di errore (più indirizzi separati da virgola)
SEGNALAZIONI_EMAIL = env.list("SEGNALAZIONI_EMAIL", default=[])

# Produzione (Heroku): HTTPS dietro il proxy
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Strumenti di sviluppo
if DEBUG:
    try:
        import debug_toolbar  # noqa: F401

        INSTALLED_APPS.append("debug_toolbar")
        MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
        INTERNAL_IPS = ["127.0.0.1"]
    except ImportError:
        pass
