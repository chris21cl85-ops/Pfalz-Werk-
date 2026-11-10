"""Einstellungen für PFALZ-WERK.

Datenbank, geheimer Schlüssel und Sicherungen liegen im Datenordner
(Standard: Dokumente/PFALZ-WERK-Daten) – getrennt vom Programm, damit ein Update
die Daten nie berührt. Nichts davon kommt ins Git.
"""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent



def _datenordner() -> Path:
    """Fester Datenordner außerhalb des Programmordners."""
    if os.environ.get("PFALZWERK_LOKAL"):
        return Path(os.environ["PFALZWERK_LOKAL"])
    alt = BASE_DIR / "lokal"  # frühere Ablage im Programmordner weiter nutzen, falls vorhanden
    if (alt / "pfalzwerk.sqlite3").exists():
        return alt
    dokumente = Path.home() / "Documents"
    return (dokumente if dokumente.is_dir() else Path.home()) / "PFALZ-WERK-Daten"


# Ordner für alles, was nur auf diesem Rechner liegt (Datenbank, Schlüssel, Sicherungen)
LOKAL_DIR = _datenordner()
LOKAL_DIR.mkdir(parents=True, exist_ok=True)
SICHERUNG_DIR = Path(os.environ.get("PFALZWERK_SICHERUNG", LOKAL_DIR / "sicherungen"))
IMPORT_DIR = LOKAL_DIR / "importe"


def _geheimer_schluessel() -> str:
    """Liest den Schlüssel aus lokal/geheim.txt oder erzeugt ihn beim ersten Start."""
    if os.environ.get("PFALZWERK_GEHEIM"):
        return os.environ["PFALZWERK_GEHEIM"]
    datei = LOKAL_DIR / "geheim.txt"
    if not datei.exists():
        datei.write_text(secrets.token_urlsafe(50), encoding="utf-8")
    return datei.read_text(encoding="utf-8").strip()


SECRET_KEY = _geheimer_schluessel()
DEBUG = os.environ.get("PFALZWERK_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"] + [
    h for h in os.environ.get("PFALZWERK_HOSTS", "").split(",") if h
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "konten",
    "kern",
    "sicherung",
    "importe",
    "kunden",
    "projekte",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "kern.middleware.AnmeldungErforderlich",
]

ROOT_URLCONF = "pfalzwerk.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "vorlagen"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "kern.kontext.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "pfalzwerk.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": LOKAL_DIR / "pfalzwerk.sqlite3",
    }
}

AUTH_USER_MODEL = "konten.Benutzer"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "anmelden"
LOGIN_REDIRECT_URL = "startseite"
LOGOUT_REDIRECT_URL = "anmelden"
SESSION_COOKIE_AGE = 60 * 60 * 10  # ein Arbeitstag

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
