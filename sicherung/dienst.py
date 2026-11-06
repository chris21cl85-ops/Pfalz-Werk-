"""Datensicherung der SQLite-Datenbank. Sicherungen werden nie automatisch gelöscht."""
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

from kern.models import protokolliere

PRAEFIX = "pfalzwerk_"


@dataclass
class Sicherung:
    pfad: Path
    zeitpunkt: datetime
    groesse: int

    @property
    def name(self):
        return self.pfad.name

    @property
    def groesse_mb(self):
        return round(self.groesse / 1024 / 1024, 2)


class SicherungFehler(Exception):
    pass


def _ordner() -> Path:
    ordner = Path(settings.SICHERUNG_DIR)
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def sicherung_anlegen(benutzer=None, anlass="manuell") -> Path:
    """Kopiert die laufende Datenbank sicher (SQLite-Backup) und prüft die Kopie."""
    jetzt = timezone.localtime()
    ziel = _ordner() / f"{PRAEFIX}{jetzt:%Y-%m-%d_%H-%M-%S}.sqlite3"
    zaehler = 1
    while ziel.exists():
        ziel = ziel.with_name(f"{PRAEFIX}{jetzt:%Y-%m-%d_%H-%M-%S}_{zaehler}.sqlite3")
        zaehler += 1

    connection.ensure_connection()
    quelle = connection.connection
    kopie = sqlite3.connect(ziel)
    try:
        quelle.backup(kopie)
        ergebnis = kopie.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        kopie.close()
    if ergebnis != "ok":
        raise SicherungFehler(f"Die Sicherung {ziel.name} ist beschädigt: {ergebnis}")

    protokolliere("sicherung", ziel.name, details=f"Anlass: {anlass}", benutzer=benutzer)
    return ziel


def sicherungen() -> list[Sicherung]:
    """Alle vorhandenen Sicherungen, neueste zuerst."""
    liste = []
    for pfad in _ordner().glob(f"{PRAEFIX}*.sqlite3"):
        info = pfad.stat()
        liste.append(Sicherung(pfad, datetime.fromtimestamp(info.st_mtime), info.st_size))
    return sorted(liste, key=lambda s: s.name, reverse=True)


def heute_gesichert() -> bool:
    heute = timezone.localdate().strftime("%Y-%m-%d")
    return any(s.name.startswith(f"{PRAEFIX}{heute}") for s in sicherungen())


def sicherung_wenn_faellig(anlass="täglich") -> Path | None:
    """Legt höchstens eine automatische Sicherung pro Tag an."""
    if heute_gesichert():
        return None
    return sicherung_anlegen(anlass=anlass)
