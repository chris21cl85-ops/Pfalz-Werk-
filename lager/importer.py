"""Import der Blätter „Lager“ und „Bestellungen“ (Zeilen 4–350, Spalten wie PW_Wareneingang).

Lager:        A Material-ID, D Istbestand, I Lagerort → Startbestand (nur wenn das Material noch keine
              Lagerbewegung hat) und Lagerplatz (nur wenn leer).
Bestellungen: nur Zeilen mit Bestell-ID „B-…“ (die übrigen sind Vorschlags-/Formelzeilen):
              A Bestell-ID, B Projekt-ID, C Material-ID, D Lieferant, E bestellt am, F Menge, G Einheit,
              H erwarteter Liefertermin, J Wareneingang am, M geliefert kumuliert, AO eingelagert kumuliert,
              AS Status („abgeschlossen“). Vorhandene Bestell-Nummern werden nie überschrieben.
"""
from decimal import Decimal

from django.utils import timezone

from importe.dienst import Importer, als_text, registrieren
from lieferanten.models import Lieferant
from material.importer import als_zahl
from material.models import Material
from projekte.importer import als_datum
from projekte.models import Projekt

from .models import Bestellung, Lagerbewegung, Wareneingang


@registrieren
class LagerImporter(Importer):
    blatt = "Lager"
    titel = "Lagerbestand (Startbestand, Lagerort)"
    reihenfolge = 50  # nach Material
    spalten = {"A": "materialnr", "D": "bestand", "I": "lagerort"}
    startzeile = 4
    endzeile = 350

    def zeile_leer(self, zeile):
        return not als_text(zeile["materialnr"]) or als_zahl(zeile["bestand"]) in (None,)

    def zeile_pruefen(self, zeile):
        nr = als_text(zeile["materialnr"])
        if not Material.objects.filter(materialnr=nr).exists():
            return [f"Material {nr} gibt es nicht (erst Blatt „Material“ übernehmen)"]
        wert = als_zahl(zeile["bestand"])
        if wert is False:
            return [f"Bestand von {nr} ist keine Zahl: {als_text(zeile['bestand'])}"]
        if wert < 0:
            return [f"Bestand von {nr} ist negativ"]
        return []

    def zeile_uebernehmen(self, zeile):
        m = Material.objects.get(materialnr=als_text(zeile["materialnr"]))
        ergebnis = "unveraendert"
        lagerort = als_text(zeile["lagerort"])
        if lagerort and not m.lagerplatz:
            m.lagerplatz = lagerort
            m.save(update_fields=["lagerplatz"])
            ergebnis = "geaendert"
        if not m.lagerbewegungen.exists():
            Lagerbewegung.objects.create(material=m, datum=timezone.localdate(), art=Lagerbewegung.Art.START,
                                         menge=als_zahl(zeile["bestand"]), notiz="aus Excel-Blatt „Lager“")
            ergebnis = "neu"
        return ergebnis


@registrieren
class BestellungenImporter(Importer):
    blatt = "Bestellungen"
    titel = "Bestellungen (mit Wareneingang)"
    reihenfolge = 55
    spalten = {"A": "bnr", "B": "projekt", "C": "material", "D": "lieferant", "E": "bestellt", "F": "menge",
               "G": "einheit", "H": "erwartet", "J": "we_am", "M": "geliefert", "AO": "eingelagert", "AS": "status"}
    startzeile = 4
    endzeile = 350

    def zeile_leer(self, zeile):
        return not als_text(zeile["bnr"]).upper().startswith("B-")

    def zeile_pruefen(self, zeile):
        fehler = []
        nr = als_text(zeile["bnr"])
        if not Material.objects.filter(materialnr=als_text(zeile["material"])).exists():
            fehler.append(f"{nr}: Material {als_text(zeile['material'])} unbekannt")
        menge = als_zahl(zeile["menge"])
        if not menge or menge is False or menge <= 0:
            fehler.append(f"{nr}: Bestellmenge fehlt")
        if als_text(zeile["projekt"]) and not Projekt.objects.filter(projektnr=als_text(zeile["projekt"])).exists():
            fehler.append(f"{nr}: Projekt {als_text(zeile['projekt'])} unbekannt")
        return fehler

    def zeile_uebernehmen(self, zeile):
        nr = als_text(zeile["bnr"])
        if Bestellung.objects.filter(bnr__iexact=nr).exists():
            return "unveraendert"
        m = Material.objects.get(materialnr=als_text(zeile["material"]))
        name = als_text(zeile["lieferant"])
        lieferant = (Lieferant.objects.filter(name__iexact=name).first() if name else None) or m.lieferant
        if lieferant is None:
            lieferant = Lieferant.objects.create(name=name or "Unbekannter Lieferant")
        bestellt = als_datum(zeile["bestellt"]) or timezone.localdate()
        b = Bestellung.objects.create(
            bnr=nr, material=m, lieferant=lieferant,
            projekt=Projekt.objects.filter(projektnr=als_text(zeile["projekt"])).first(),
            menge=als_zahl(zeile["menge"]), einheit=als_text(zeile["einheit"]) or m.einheit,
            art=Bestellung.Art.MANUELL, bestellt_am=bestellt, erwartet_am=als_datum(zeile["erwartet"]),
            freigegeben_von="Excel", notiz="aus Excel übernommen",
            eingelagert_vorher=als_zahl(zeile["eingelagert"]) or Decimal("0"),
            abgeschlossen="abgeschlossen" in als_text(zeile["status"]).lower())
        geliefert = als_zahl(zeile["geliefert"]) or Decimal("0")
        if geliefert > 0:
            Wareneingang.objects.create(bestellung=b, datum=als_datum(zeile["we_am"]) or bestellt, menge=geliefert,
                                        notiz="aus Excel (geliefert kumuliert)")
        return "neu"
