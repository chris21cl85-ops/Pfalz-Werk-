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
    reihenfolge: int = 100  # kleinere Zahl wird zuerst eingelesen (z. B. Kunden vor Projekten)
    kopfzeile: int = 1
    pflichtspalten: tuple[str, ...] = ()
    # Optional: feste Zuordnung Spaltenbuchstabe -> Feldname (wie in der Excel-Fassung).
    # Dann wird nicht nach Überschriften gelesen, sondern ab ``startzeile`` bis ``endzeile``.
    spalten: dict[str, str] = {}
    startzeile: int = 2
    endzeile: int | None = None

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


def als_text(wert) -> str:
    """Excel-Wert als sauberer Text: 12.0 -> '12', Leerzeichen weg, None -> ''."""
    if wert is None:
        return ""
    if isinstance(wert, float) and wert.is_integer():
        return str(int(wert))
    return str(wert).strip()


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


def _spalten_zeilen(blatt, imp):
    """Liest feste Spalten (Buchstaben) ab der Startzeile."""
    from openpyxl.utils import column_index_from_string
    index = {buchstabe: column_index_from_string(buchstabe) - 1 for buchstabe in imp.spalten}
    letzte = max(index.values()) + 1
    for nr, werte in enumerate(blatt.iter_rows(min_row=imp.startzeile, max_row=imp.endzeile,
                                                max_col=letzte, values_only=True), start=imp.startzeile):
        werte = list(werte) + [None] * (letzte - len(werte))
        zeile = {feld: werte[index[b]] for b, feld in imp.spalten.items()}
        zeile = {k: (v.strip() if isinstance(v, str) else v) for k, v in zeile.items()}
        if all(v in (None, "") for v in zeile.values()):
            continue
        yield nr, zeile


KOPF_ZEILEN = 5    # nur Überschriften – keine Datenzeilen mit PINs o. Ä.
KOPF_SPALTEN = 60  # bis Spalte BH


def kopfbereich(blatt) -> dict:
    """Zeilen 1–5 eines Blatts mit Spaltenbuchstaben – damit man den Aufbau ohne Excel sieht."""
    from openpyxl.utils import get_column_letter
    zeilen = []
    for werte in blatt.iter_rows(min_row=1, max_row=KOPF_ZEILEN, max_col=KOPF_SPALTEN, values_only=True):
        zeilen.append([als_text(w)[:40] for w in werte])
    breite = 0
    for z in zeilen:
        for i, w in enumerate(z):
            if w:
                breite = max(breite, i + 1)
    return {"spalten": [get_column_letter(i + 1) for i in range(breite)],
            "zeilen": [z[:breite] + [""] * (breite - len(z)) for z in zeilen]}


def ausfuehren(pfad, probelauf=True) -> dict:
    """Prüft (Probelauf) oder übernimmt alle Blätter mit registriertem Importer."""
    mappe = _arbeitsmappe(pfad)
    bericht = {"blaetter": [], "probelauf": probelauf}
    try:
        with transaction.atomic():
            reihenfolge = {name: (IMPORTER[name].reihenfolge if name in IMPORTER else 999, i)
                           for i, name in enumerate(mappe.sheetnames)}
            for blatt in sorted(mappe.worksheets, key=lambda b: reihenfolge[b.title]):
                klasse = IMPORTER.get(blatt.title)
                eintrag = {"blatt": blatt.title, "zeilen": 0, "importer": klasse.titel if klasse else None,
                           "neu": 0, "geaendert": 0, "unveraendert": 0, "fehler": []}
                if klasse is None:
                    eintrag["zeilen"] = max(blatt.max_row - 1, 0) if blatt.max_row else 0
                    eintrag["kopf"] = kopfbereich(blatt)
                    bericht["blaetter"].append(eintrag)
                    continue
                imp = klasse()
                zeilen = _spalten_zeilen(blatt, imp) if imp.spalten else _zeilen(blatt, imp.kopfzeile)
                for nr, zeile in zeilen:
                    eintrag["zeilen"] += 1
                    fehler = imp.zeile_pruefen(zeile)
                    if fehler:
                        eintrag["fehler"].append(f"Zeile {nr}: " + ", ".join(fehler))
                        continue
                    # Auch im Probelauf wird „übernommen“ – am Ende aber alles zurückgerollt.
                    # So zeigt schon der Probelauf, was neu wäre und was schon da ist.
                    eintrag[imp.zeile_uebernehmen(zeile)] += 1
                if hasattr(imp, "zusatz"):
                    eintrag["zusatz"] = imp.zusatz()
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


