"""Import-Gerüst: liest eine Excel-Datei der alten Fassung blattweise ein.

Für jedes Tabellenblatt kann ein Importer registriert werden (ab Etappe 1:
Kunden, Projekte, Material ...). Ablauf immer: Probelauf -> Bericht -> Übernahme.
Vor jeder Übernahme wird automatisch gesichert.
"""
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from openpyxl import load_workbook

from kern.models import protokolliere

IMPORTER: dict[str, type["Importer"]] = {}


class ImportFehler(Exception):
    pass


class Importer:
    """Grundklasse. Unterklassen setzen ``blatt``, ``pflichtspalten`` und ``zeile_uebernehmen``."""

    blatt: str = ""
    titel: str = ""
    kopfzeile: int = 1
    pflichtspalten: tuple[str, ...] = ()

    def zeile_pruefen(self, zeile: dict) -> list[str]:
        """Liefert Fehlermeldungen für eine Zeile (leer = in Ordnung)."""
        return [f"„{s}“ fehlt" for s in self.pflichtspalten if zeile.get(s) in (None, "")]

    def zeile_uebernehmen(self, zeile: dict) -> str:
        """Speichert die Zeile. Rückgabe: 'neu', 'geaendert' oder 'unveraendert'."""
        raise NotImplementedError


def registrieren(klasse):
    """Dekorator: Importer für sein Tabellenblatt anmelden."""
    IMPORTER[klasse.blatt] = klasse
    return klasse


def _text(wert):
    return str(wert).strip() if wert is not None else ""


def datei_speichern(hochgeladen) -> Path:
    name = Path(hochgeladen.name).name
    if not name.lower().endswith((".xlsx", ".xlsm")):
        raise ImportFehler("Bitte eine Excel-Datei (.xlsx oder .xlsm) wählen.")
    ordner = Path(settings.IMPORT_DIR)
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{uuid.uuid4().hex[:8]}_{name}"
    with ziel.open("wb") as aus:
        for stueck in hochgeladen.chunks():
            aus.write(stueck)
    return ziel


def _arbeitsmappe(pfad):
    try:
        return load_workbook(pfad, read_only=True, data_only=True, keep_vba=False)
    except Exception as fehler:  # beschädigte oder falsche Datei
        raise ImportFehler(f"Die Datei lässt sich nicht öffnen: {fehler}") from fehler


def _zeilen(blatt, kopfzeile):
    """Liest ein Blatt als Liste von Wörterbüchern (Spaltenname -> Wert)."""
    kopf = None
    for nr, werte in enumerate(blatt.iter_rows(values_only=True), start=1):
        if nr < kopfzeile:
            continue
        if nr == kopfzeile:
            kopf = [_text(w) for w in werte]
            continue
        if all(w in (None, "") for w in werte):
            continue
        yield nr, {k: (w.strip() if isinstance(w, str) else w) for k, w in zip(kopf, werte) if k}


def ausfuehren(pfad, probelauf=True) -> dict:
    """Prüft (Probelauf) oder übernimmt alle Blätter mit registriertem Importer."""
    mappe = _arbeitsmappe(pfad)
    bericht = {"blaetter": [], "probelauf": probelauf}
    try:
        with transaction.atomic():
            for blatt in mappe.worksheets:
                klasse = IMPORTER.get(blatt.title)
                eintrag = {"blatt": blatt.title, "zeilen": 0, "importer": klasse.titel if klasse else None,
                           "neu": 0, "geaendert": 0, "unveraendert": 0, "fehler": []}
                if klasse is None:
                    eintrag["zeilen"] = max(blatt.max_row - 1, 0) if blatt.max_row else 0
                    bericht["blaetter"].append(eintrag)
                    continue
                imp = klasse()
                for nr, zeile in _zeilen(blatt, imp.kopfzeile):
                    eintrag["zeilen"] += 1
                    fehler = imp.zeile_pruefen(zeile)
                    if fehler:
                        eintrag["fehler"].append(f"Zeile {nr}: " + ", ".join(fehler))
                        continue
                    if not probelauf:
                        eintrag[imp.zeile_uebernehmen(zeile)] += 1
                bericht["blaetter"].append(eintrag)
            if probelauf:
                transaction.set_rollback(True)
    finally:
        mappe.close()
    bericht["fehler_gesamt"] = sum(len(b["fehler"]) for b in bericht["blaetter"])
    bericht["erkannt"] = sum(1 for b in bericht["blaetter"] if b["importer"])
    return bericht


def probelauf(lauf):
    from .models import Importlauf
    try:
        lauf.bericht = ausfuehren(lauf.gespeichert_als, probelauf=True)
        lauf.status = Importlauf.Status.PROBELAUF
    except ImportFehler as fehler:
        lauf.bericht = {"meldung": str(fehler)}
        lauf.status = Importlauf.Status.FEHLER
    lauf.save()
    return lauf


def uebernehmen(lauf, benutzer):
    """Übernimmt geprüfte Daten. Vorher wird automatisch gesichert."""
    from sicherung.dienst import sicherung_anlegen

    from .models import Importlauf
    if lauf.status != Importlauf.Status.PROBELAUF:
        raise ImportFehler("Bitte zuerst den Probelauf durchführen.")
    if lauf.bericht.get("erkannt", 0) == 0:
        raise ImportFehler("In der Datei wurde kein übernehmbares Tabellenblatt erkannt.")
    sicherung_anlegen(benutzer=benutzer, anlass=f"vor Import {lauf.dateiname}")
    lauf.bericht = ausfuehren(lauf.gespeichert_als, probelauf=False)
    lauf.status = Importlauf.Status.UEBERNOMMEN
    lauf.save()
    protokolliere("import", lauf.dateiname, details=str(lauf.bericht), benutzer=benutzer)
    return lauf


