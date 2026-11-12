"""Import des Excel-Blatts „Material“ – Spalten wie im Makro PFALZ_WERK_SQL_MaterialLager (DEV-28.9A).

Lagerbestände (Blatt „Lager“: A Material-Nr., D Bestand, E Reserviert, I Lagerort) folgen in Etappe 3.
"""
from decimal import Decimal, InvalidOperation

from importe.dienst import Importer, als_text, registrieren
from projekte.importer import als_datum

from .models import Material


def als_zahl(wert):
    """Excel-Zahl oder Text wie „12,50“ / „1.234,5“ -> Decimal; leer -> None; unlesbar -> False."""
    if wert in (None, ""):
        return None
    if isinstance(wert, bool):
        return False
    if isinstance(wert, (int, float)):
        return Decimal(str(wert))
    text = str(wert).strip().replace("€", "").replace("mm", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return False


def als_ja(wert) -> bool:
    return als_text(wert).upper() in {"JA", "WAHR", "TRUE", "1", "X"}


def ist_aktiv(wert) -> bool:
    return als_text(wert).upper() not in {"INAKTIV", "NEIN", "0", "FALSCH", "FALSE"}


ZAHLFELDER = {"staerke_mm": "Stärke", "ek_netto": "EK netto", "mindestbestand": "Mindestbestand",
              "zielbestand": "Zielbestand", "referenzpreis_brutto": "Referenzpreis", "lieferzeit_tage": "Lieferzeit"}


@registrieren
class MaterialImporter(Importer):
    blatt = "Material"
    titel = "Material"
    reihenfolge = 30
    spalten = {"A": "materialnr", "B": "produktgruppe", "C": "bezeichnung", "D": "einheit",
               "E": "ek_netto", "F": "mindestbestand", "H": "lieferzeit_tage", "I": "preis_hinweis",
               "T": "untergruppe", "U": "staerke_mm", "V": "format", "W": "lagerartikel",
               "X": "aktiv", "Y": "beschaffungsart", "AF": "zielbestand", "AH": "lagerplatz",
               "AI": "referenzpreis_brutto", "AK": "preisquelle", "AL": "preisstand"}
    startzeile = 4
    endzeile = 350

    def __init__(self):
        self.gesehen = set()

    def zeile_pruefen(self, zeile):
        nr = als_text(zeile["materialnr"])
        if not nr:
            return ["Material-Nr. fehlt"]
        fehler = []
        if not als_text(zeile["bezeichnung"]):
            fehler.append(f"Material {nr} hat keine Bezeichnung")
        if nr.lower() in self.gesehen:
            fehler.append(f"Material-Nr. {nr} steht doppelt in der Excel")
        self.gesehen.add(nr.lower())
        return fehler

    def zeile_uebernehmen(self, zeile):
        nr = als_text(zeile["materialnr"])
        if Material.objects.filter(materialnr__iexact=nr).exists():
            return "unveraendert"  # vorhandene Materialnummern werden nicht verändert (wie im Makro)
        werte, hinweise = {}, []
        for feld, titel in ZAHLFELDER.items():
            zahl = als_zahl(zeile[feld])
            if zahl is False:
                hinweise.append(f"{titel} aus Excel nicht lesbar: {als_text(zeile[feld])}")
                zahl = None
            if feld == "lieferzeit_tage" and zahl is not None:
                zahl = max(int(zahl), 0)
            werte[feld] = zahl
        if zeile["preisstand"] not in (None, "") and als_datum(zeile["preisstand"]) is None:
            hinweise.append(f"Preisstand aus Excel nicht lesbar: {als_text(zeile['preisstand'])}")
        Material.objects.create(
            materialnr=nr,
            bezeichnung=als_text(zeile["bezeichnung"]),
            produktgruppe=als_text(zeile["produktgruppe"]),
            untergruppe=als_text(zeile["untergruppe"]),
            einheit=als_text(zeile["einheit"]),
            format=als_text(zeile["format"]),
            preis_hinweis=als_text(zeile["preis_hinweis"])[:250],
            lagerartikel=als_ja(zeile["lagerartikel"]),
            aktiv=ist_aktiv(zeile["aktiv"]),
            beschaffungsart=als_text(zeile["beschaffungsart"]),
            lagerplatz=als_text(zeile["lagerplatz"]),
            preisquelle=als_text(zeile["preisquelle"]),
            preisstand=als_datum(zeile["preisstand"]),
            hinweise="\n".join(hinweise),
            **werte,
        )
        return "neu"
