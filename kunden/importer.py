"""Import des Excel-Blatts „Kunden“ – Spalten wie im Makro PFALZ_WERK_SQL_Erstuebertragung."""
from importe.dienst import Importer, als_text, registrieren

from .models import Kunde, adresse_zerlegen


@registrieren
class KundenImporter(Importer):
    blatt = "Kunden"
    titel = "Kunden"
    reihenfolge = 10  # vor Projekten
    spalten = {"A": "kundennr", "B": "name", "C": "ansprechpartner", "D": "telefon",
               "E": "email", "F": "adresse", "G": "kundenart", "I": "hinweise"}
    startzeile = 4
    endzeile = 97

    def __init__(self):
        self.gesehen = set()

    def zeile_pruefen(self, zeile):
        nr = als_text(zeile["kundennr"])
        if not nr:
            # Zeile ohne Nummer, aber mit Inhalt – in Excel ignoriert, hier melden
            return ["Kunden-Nr. fehlt"]
        fehler = []
        if not als_text(zeile["name"]):
            fehler.append(f"Kunde {nr} hat keinen Namen")
        if nr.lower() in self.gesehen:
            fehler.append(f"Kunden-Nr. {nr} steht doppelt in der Excel")
        self.gesehen.add(nr.lower())
        email = als_text(zeile["email"])
        if email and "@" not in email:
            fehler.append(f"E-Mail „{email}“ ist ungültig")
        return fehler

    def zeile_uebernehmen(self, zeile):
        nr = als_text(zeile["kundennr"])
        if Kunde.objects.filter(kundennr__iexact=nr).exists():
            return "unveraendert"  # bestehende Nummern werden nie überschrieben
        adresse = als_text(zeile["adresse"])
        Kunde.objects.create(
            kundennr=nr,
            name=als_text(zeile["name"]),
            ansprechpartner=als_text(zeile["ansprechpartner"]),
            telefon=als_text(zeile["telefon"]),
            email=als_text(zeile["email"]),
            adresse_original=adresse,
            **adresse_zerlegen(adresse),
            kundenart=als_text(zeile["kundenart"]) or "Unbekannt",
            hinweise=als_text(zeile["hinweise"]),
            status=Kunde.Status.AKTIV,
        )
        return "neu"
