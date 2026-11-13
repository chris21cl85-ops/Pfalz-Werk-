"""Import Blatt „Firmendaten“ (Kopf Zeile 3, ab Zeile 4: A Feld, B Wert, C Hinweis).

Zuordnung über den Feldnamen in Spalte A (wie FDNAMEN im Makro PW_Rechnung). Nur leere Felder im Programm
werden gefüllt – was hier schon eingetragen wurde, wird nie überschrieben. Die laufende Rechnungsnummer
wird nur erhöht, nie verkleinert.
"""
import re

from importe.dienst import Importer, als_text, registrieren
from material.importer import als_ja, als_zahl

from .models import Firmendaten


def _schluessel(text: str) -> str:
    return re.sub(r"[^a-z0-9äöüß]", "", text.lower())


# Feldname in der Excel (Spalte A) -> Feld im Programm
FELDER = {_schluessel(k): v for k, v in {
    "Firmenname": "firmenname", "Inhaber / Ansprechpartner": "inhaber", "Straße und Hausnummer": "strasse",
    "PLZ": "plz", "Ort": "ort", "Land (DE)": "land", "Land": "land", "Telefon": "telefon", "E-Mail": "email",
    "Steuernummer": "steuernummer", "USt-IdNr.": "ust_idnr", "IBAN": "iban", "BIC": "bic", "Bank": "bank",
    "Zahlungsziel Tage": "zahlungsziel_tage", "Kleinunternehmer (Ja/Nein)": "kleinunternehmer",
    "USt-Satz %": "ust_satz", "Rechnungs-Präfix": "rechnungs_praefix",
    "Letzte Rechnungsnummer": "letzte_rechnungsnummer", "Fußtext Rechnung": "fusstext",
    "Mahngebühr 2. Mahnung €": "mahngebuehr",
}.items()}
ZAHLEN = {"zahlungsziel_tage", "ust_satz", "letzte_rechnungsnummer", "mahngebuehr"}


@registrieren
class FirmendatenImporter(Importer):
    blatt = "Firmendaten"
    titel = "Firmendaten (Briefkopf, Bank, Steuer)"
    reihenfolge = 5
    spalten = {"A": "feld", "B": "wert"}
    startzeile = 4
    endzeile = 40

    def __init__(self):
        self.unbekannt = []
        self.firma = Firmendaten.laden()
        self.vorgabe = Firmendaten()  # Standardwerte eines frischen Datensatzes

    def zeile_leer(self, zeile):
        return not als_text(zeile["feld"]) or not als_text(zeile["wert"])

    def zeile_pruefen(self, zeile):
        feld = FELDER.get(_schluessel(als_text(zeile["feld"])))
        if feld is None:
            self.unbekannt.append(als_text(zeile["feld"]))
            return []
        if feld in ZAHLEN and als_zahl(zeile["wert"]) is False:
            return [f"„{als_text(zeile['feld'])}“ ist keine Zahl: {als_text(zeile['wert'])}"]
        return []

    def zeile_uebernehmen(self, zeile):
        feld = FELDER.get(_schluessel(als_text(zeile["feld"])))
        if feld is None:
            return "unveraendert"
        if feld in ZAHLEN:
            wert = als_zahl(zeile["wert"])
            if feld in ("zahlungsziel_tage", "letzte_rechnungsnummer"):
                wert = int(wert)
        elif feld == "kleinunternehmer":
            wert = als_ja(zeile["wert"])
        elif feld == "iban":
            wert = als_text(zeile["wert"]).replace(" ", "").upper()
        else:
            wert = als_text(zeile["wert"])
        bisher = getattr(self.firma, feld)
        if feld == "letzte_rechnungsnummer":
            if wert <= bisher:
                return "unveraendert"
        elif bisher not in ("", None) and bisher != getattr(self.vorgabe, feld):
            return "unveraendert"  # schon im Programm gepflegt – nie überschreiben
        if bisher == wert:
            return "unveraendert"
        setattr(self.firma, feld, wert)
        self.firma.save()
        return "geaendert"

    def zusatz(self):
        if self.unbekannt:
            return "Nicht übernommen (unbekanntes Feld): " + ", ".join(self.unbekannt)
        return ""
