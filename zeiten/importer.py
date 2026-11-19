"""Import Blatt „Arbeitsvertraege“ (Zeilen 8–207): A Vertrags-ID, B Mitarbeiter (Kürzel), D Vertragsart, E Status,
F Eintritt, G Befristet bis, H Probezeit bis, J–N Soll Mo–Fr, O Urlaub/Jahr, P Zeitkonto Start, Q Brutto/Monat,
R Stundenlohn, S Kündigungsfrist, T Tätigkeit, U Arbeitsort, W Bearbeitungsvermerk.
Je Mitarbeiter ein Vertrag; vorhandene Verträge werden nicht überschrieben. „Administrator“ wird übersprungen."""
from datetime import date, datetime
from decimal import Decimal

from importe.dienst import Importer, als_text, registrieren
from material.importer import als_zahl
from mitarbeiter.models import Mitarbeiter

from .models import Arbeitsvertrag


def _ma(text):
    t = als_text(text)
    return Mitarbeiter.objects.filter(kuerzel__iexact=t).first() or Mitarbeiter.objects.filter(name__iexact=t).first()


def _datum(w):
    if isinstance(w, datetime):
        return w.date()
    return w if isinstance(w, date) else None


def _zahl(w, standard=None):
    z = als_zahl(w)
    return standard if z is None or z is False else z  # 0 ist ein gültiger Wert (z. B. freier Freitag)


@registrieren
class VertragImporter(Importer):
    blatt = "Arbeitsvertraege"
    titel = "Arbeitsverträge"
    reihenfolge = 95
    spalten = {"A": "id", "B": "ma", "D": "art", "E": "status", "F": "eintritt", "G": "befristet", "H": "probe",
               "J": "mo", "K": "di", "L": "mi", "M": "do", "N": "fr", "O": "urlaub", "P": "konto", "Q": "brutto",
               "R": "lohn", "S": "frist", "T": "taetigkeit", "U": "ort", "W": "vermerk"}
    startzeile = 8
    endzeile = 207

    def zeile_leer(self, z):
        return not als_text(z["ma"]) or als_text(z["ma"]).lower() == "administrator" or \
            not als_text(z["id"]).upper().startswith("AV-")

    def zeile_pruefen(self, z):
        return [] if _ma(z["ma"]) else [f"Mitarbeiter {als_text(z['ma'])} unbekannt"]

    def zeile_uebernehmen(self, z):
        ma = _ma(z["ma"])
        vid = als_text(z["id"])
        if Arbeitsvertrag.objects.filter(mitarbeiter=ma).exists() or Arbeitsvertrag.objects.filter(vertragsid=vid).exists():
            return "unveraendert"
        art, status = als_text(z["art"]), als_text(z["status"])
        acht = Decimal("8")
        Arbeitsvertrag.objects.create(
            vertragsid=vid, mitarbeiter=ma, art=art if art in Arbeitsvertrag.Art.values else Arbeitsvertrag.Art.UNBEFRISTET,
            status=status if status in Arbeitsvertrag.Status.values else Arbeitsvertrag.Status.AKTIV,
            eintritt=_datum(z["eintritt"]) or ma.eintritt, befristet_bis=_datum(z["befristet"]),
            probezeit_bis=_datum(z["probe"]), soll_mo=_zahl(z["mo"], acht), soll_di=_zahl(z["di"], acht),
            soll_mi=_zahl(z["mi"], acht), soll_do=_zahl(z["do"], acht), soll_fr=_zahl(z["fr"], acht),
            urlaub_jahr=_zahl(z["urlaub"], ma.urlaubstage or Decimal("30")), zeitkonto_start=_zahl(z["konto"], Decimal("0")),
            brutto_monat=_zahl(z["brutto"]), stundenlohn=_zahl(z["lohn"]) or ma.stundensatz,
            kuendigungsfrist=als_text(z["frist"])[:60], taetigkeit=als_text(z["taetigkeit"])[:150],
            arbeitsort=als_text(z["ort"])[:150], vermerk=als_text(z["vermerk"])[:250])
        return "neu"
