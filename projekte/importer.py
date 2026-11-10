"""Import des Excel-Blatts „Projekte“ – Spalten wie im Makro PFALZ_WERK_SQL_Erstuebertragung."""
import datetime as dt

from openpyxl.utils.datetime import from_excel

from importe.dienst import Importer, als_text, registrieren
from kunden.models import Kunde

from .models import Projekt


def als_datum(wert):
    """Excel-Datum, Text „TT.MM.JJJJ“ oder Excel-Zahl -> Datum. Sonst None (wie im Makro)."""
    if wert in (None, ""):
        return None
    if isinstance(wert, dt.datetime):
        return wert.date()
    if isinstance(wert, dt.date):
        return wert
    if isinstance(wert, (int, float)) and 1 < wert < 80000:
        try:
            return from_excel(wert).date()
        except (ValueError, OverflowError):
            return None
    text = str(wert).strip()
    for muster in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, muster).date()
        except ValueError:
            pass
    return None


@registrieren
class ProjekteImporter(Importer):
    blatt = "Projekte"
    titel = "Projekte"
    reihenfolge = 20  # nach Kunden
    spalten = {"A": "projektnr", "B": "name", "C": "kundennr", "D": "phase", "E": "status",
               "F": "projektpate", "G": "startdatum", "H": "zieldatum", "K": "risiko",
               "L": "naechster_schritt", "S": "projektart_s", "Y": "projektart_y", "AL": "anfrage_id"}
    startzeile = 4
    endzeile = 300

    def __init__(self):
        self.gesehen = set()

    def zeile_pruefen(self, zeile):
        nr = als_text(zeile["projektnr"])
        if not nr:
            return ["Projekt-Nr. fehlt"]
        fehler = []
        if not als_text(zeile["name"]):
            fehler.append(f"Projekt {nr} hat keinen Projektnamen")
        kundennr = als_text(zeile["kundennr"])
        if not kundennr:
            fehler.append(f"Projekt {nr} hat keine Kunden-Nr.")
        elif not Kunde.objects.filter(kundennr__iexact=kundennr).exists():
            fehler.append(f"Projekt {nr}: Kunde {kundennr} gibt es nicht")
        if nr.lower() in self.gesehen:
            fehler.append(f"Projekt-Nr. {nr} steht doppelt in der Excel")
        self.gesehen.add(nr.lower())
        return fehler

    def zeile_uebernehmen(self, zeile):
        nr = als_text(zeile["projektnr"])
        if Projekt.objects.filter(projektnr__iexact=nr).exists():
            return "unveraendert"  # bestehende Nummern werden nie überschrieben
        hinweise = []
        for feld, titel in (("startdatum", "Startdatum"), ("zieldatum", "Zieldatum")):
            if zeile[feld] not in (None, "") and als_datum(zeile[feld]) is None:
                hinweise.append(f"{titel} aus Excel nicht lesbar: {als_text(zeile[feld])}")
        Projekt.objects.create(
            projektnr=nr,
            name=als_text(zeile["name"]),
            kunde=Kunde.objects.get(kundennr__iexact=als_text(zeile["kundennr"])),
            phase=als_text(zeile["phase"]),
            status=als_text(zeile["status"]) or "Planung",
            projektpate=als_text(zeile["projektpate"]),
            startdatum=als_datum(zeile["startdatum"]),
            zieldatum=als_datum(zeile["zieldatum"]),
            risiko=als_text(zeile["risiko"]),
            naechster_schritt=als_text(zeile["naechster_schritt"]),
            projektart=als_text(zeile["projektart_y"]) or als_text(zeile["projektart_s"]) or "Nicht zugeordnet",
            anfrage_id=als_text(zeile["anfrage_id"]),
            hinweise="\n".join(hinweise),
        )
        return "neu"
