"""Einstellungen für PFALZ-WERK.

Datenbank, geheimer Schlüssel und Sicherungen liegen im Datenordner
(Standard: Dokumente/PFALZ-WERK-Daten) – getrennt vom Programm, damit ein Update
die Daten nie berührt. Nichts davon kommt ins Git.
"""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent



DB_NAME = "pfalzwerk.sqlite3"


def _beschreibbar(ordner: Path) -> bool:
    """Legt den Ordner an und prüft, ob Windows dort wirklich Schreiben erlaubt.

    Der „überwachte Ordnerzugriff“ von Windows Defender oder OneDrive kann „Dokumente“ sperren –
    dann kommt beim Anlegen z. B. ein FileNotFoundError oder PermissionError.
    """
    try:
        ordner.mkdir(parents=True, exist_ok=True)
        probe = ordner / ".schreibprobe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _kandidaten() -> list[Path]:
    """Mögliche Datenordner in der Reihenfolge, in der sie versucht werden."""
    heim = Path.home()
    dokumente = heim / "Documents"
    appdata = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else heim
    return [
        (dokumente if dokumente.is_dir() else heim) / "PFALZ-WERK-Daten",  # gut sichtbar für den Chef
        appdata / "PFALZ-WERK-Daten",  # von Windows nie gesperrt
        BASE_DIR / "lokal",  # letzter Ausweg: im Programmordner
    ]


def _datenordner() -> Path:
    """Fester Datenordner außerhalb des Programmordners – vorhandene Daten haben Vorrang."""
    if os.environ.get("PFALZWERK_LOKAL"):
        return Path(os.environ["PFALZWERK_LOKAL"])
    kandidaten = _kandidaten()
    # 1. Wo schon eine Datenbank liegt, wird weitergearbeitet
    for ordner in [kandidaten[2]] + kandidaten[:2]:
        if (ordner / DB_NAME).exists() and _beschreibbar(ordner):
            return ordner
    # 2. Sonst der erste Ordner, in den Windows schreiben lässt
    for ordner in kandidaten:
        if _beschreibbar(ordner):
            return ordner
    raise RuntimeError(
        "PFALZ-WERK findet keinen Ordner, in dem es seine Daten speichern darf. Versucht wurden: "
        + "; ".join(str(k) for k in kandidaten)
    )


# Ordner für alles, was nur auf diesem Rechner liegt (Datenbank, Schlüssel, Sicherungen)
LOKAL_DIR = _datenordner()
LOKAL_DIR.mkdir(parents=True, exist_ok=True)  # bei PFALZWERK_LOKAL (Tests) evtl. noch nicht vorhanden
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
    "material",
    "lieferanten",
    "mitarbeiter",
    "rechnungen",
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
        "NAME": LOKAL_DIR / DB_NAME,
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
