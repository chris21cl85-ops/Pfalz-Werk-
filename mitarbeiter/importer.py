"""Import der Mitarbeiter.

Blatt „Mitarbeiter“ (Kopf Zeile 3, Daten ab Zeile 4): A Kürzel, B Name, C Rolle, D Team-täglich verfügbar,
E Telefon, F Kann Montage leiten, G Hinweis, H Verfügbarkeit, I Besonderheit (Arbeitstage), J Uhrzeit.
Blatt „Dashboard Steuerung“ (ab Zeile 6, wie Makro MeinTag_Sync2/Vertragsfreigabe): A Kürzel,
AB Eintritt, AD Wochenstunden, AJ Urlaub. PINs (Spalte M) werden bewusst NICHT übernommen.
"""
import re

from importe.dienst import Importer, als_text, registrieren
from material.importer import als_ja, als_zahl
from projekte.importer import als_datum

from .models import Mitarbeiter


def pin_schwaerzen(text: str) -> str:
    """Steht in einem Hinweis eine PIN, wird sie unkenntlich gemacht (PINs gibt nur der Chef ein)."""
    return re.sub(r"(PIN\D{0,25}?)\d{3,}", r"\1****", text, flags=re.I)


@registrieren
class MitarbeiterImporter(Importer):
    blatt = "Mitarbeiter"
    titel = "Mitarbeiter"
    reihenfolge = 40
    spalten = {"A": "kuerzel", "B": "name", "C": "rolle", "D": "team", "E": "telefon", "F": "montage",
               "G": "hinweis", "H": "verfuegbarkeit", "I": "arbeitstage", "J": "arbeitszeit"}
    startzeile = 4
    endzeile = 300

    def __init__(self):
        self.gesehen = set()

    def zeile_pruefen(self, zeile):
        kuerzel = als_text(zeile["kuerzel"])
        if not kuerzel:
            return ["Kürzel fehlt"]
        fehler = []
        if not als_text(zeile["name"]):
            fehler.append(f"Mitarbeiter {kuerzel} hat keinen Namen")
        if kuerzel.lower() in self.gesehen:
            fehler.append(f"Kürzel {kuerzel} steht doppelt in der Excel")
        self.gesehen.add(kuerzel.lower())
        return fehler

    def zeile_uebernehmen(self, zeile):
        kuerzel = als_text(zeile["kuerzel"])
        if Mitarbeiter.objects.filter(kuerzel__iexact=kuerzel).exists():
            return "unveraendert"
        Mitarbeiter.objects.create(
            kuerzel=kuerzel,
            name=als_text(zeile["name"]),
            rolle=als_text(zeile["rolle"]),
            telefon=als_text(zeile["telefon"]),
            team_taeglich_verfuegbar=als_ja(zeile["team"]) if als_text(zeile["team"]) else True,
            kann_montage_leiten=als_ja(zeile["montage"]),
            hinweise=pin_schwaerzen(als_text(zeile["hinweis"])),
            verfuegbarkeit=als_text(zeile["verfuegbarkeit"]),
            arbeitstage=als_text(zeile["arbeitstage"]),
            arbeitszeit=als_text(zeile["arbeitszeit"]),
        )
        return "neu"


@registrieren
class VertragsdatenImporter(Importer):
    """Ergänzt Eintritt, Wochenstunden und Urlaub – füllt nur leere Felder, überschreibt nichts."""

    blatt = "Dashboard Steuerung"
    titel = "Mitarbeiter-Vertragsdaten (Eintritt, Wochenstunden, Urlaub)"
    reihenfolge = 41
    spalten = {"A": "kuerzel", "AB": "eintritt", "AD": "wochenstunden", "AJ": "urlaub"}
    startzeile = 6
    endzeile = 205

    def zeile_pruefen(self, zeile):
        return []

    def zeile_uebernehmen(self, zeile):
        kuerzel = als_text(zeile["kuerzel"])
        m = Mitarbeiter.objects.filter(kuerzel__iexact=kuerzel).first() if kuerzel else None
        if m is None:
            return "unveraendert"
        geaendert = []
        eintritt = als_datum(zeile["eintritt"])
        if m.eintritt is None and eintritt:
            m.eintritt = eintritt
            geaendert.append("eintritt")
        for feld, quelle in (("wochenstunden", "wochenstunden"), ("urlaubstage", "urlaub")):
            zahl = als_zahl(zeile[quelle])
            if getattr(m, feld) is None and zahl not in (None, False) and zahl >= 0:
                setattr(m, feld, zahl)
                geaendert.append(feld)
        if not geaendert:
            return "unveraendert"
        m.save(update_fields=geaendert + ["geaendert_am"])
        return "geaendert"
