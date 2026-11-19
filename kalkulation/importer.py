"""Import der Blätter „Stueckliste“, „Kalkulation“ und „Auftraege“ (Spalten wie PW_Auftraege / Blattaufbau).

Stueckliste (Zeilen 4–316): A Pos., B Projekt-ID, C Material-ID, D Bezeichnung, E Menge, F Einheit, G EK/Einheit,
            I Status. Nur Zeilen mit Projekt und Menge; je Projekt nur, solange dort noch keine Stückliste existiert.
Kalkulation (Zeilen 4–100): A Projekt-ID, B Materialkosten, C Beschläge, D Lohn Std., E Lohn €/Std., G Maschine,
            H Montage, I Fahrt, J Fremd, L Zuschlag, M Risiko (als Anteil 0,15 oder Prozent 15), U Art.
            Nur wenn das Projekt noch keine Kalkulation hat.
Auftraege   (Zeilen 4–100): A Auftrags-ID, B Projekt-ID, D Leistung, G Angebot netto, H Status, I Freigabe Kunde,
            J Lieferung/Montage, K Chef-Freigabe, L Meister-Freigabe. Vorhandene Nummern nie überschrieben.
"""
from decimal import Decimal

from importe.dienst import Importer, als_text, registrieren
from material.importer import als_zahl
from material.models import Material
from projekte.models import Projekt

from .models import Auftrag, Kalkulation, Stuecklistenposition


def _projekt(zeile):
    return Projekt.objects.filter(projektnr=als_text(zeile["projekt"])).first()


def _zahl(wert, standard=Decimal("0")):
    z = als_zahl(wert)
    return standard if z in (None, False) else z


@registrieren
class StuecklistenImporter(Importer):
    blatt = "Stueckliste"
    titel = "Stückliste (Materialbedarf je Projekt)"
    reihenfolge = 60
    spalten = {"A": "pos", "B": "projekt", "C": "material", "D": "bezeichnung", "E": "menge", "F": "einheit",
               "G": "ek", "I": "status"}
    startzeile = 4
    endzeile = 316

    def __init__(self):
        self.vorhanden = set(Stuecklistenposition.objects.values_list("projekt__projektnr", flat=True))

    def zeile_leer(self, zeile):
        return not als_text(zeile["projekt"]) or als_zahl(zeile["menge"]) in (None, False) or not als_zahl(zeile["menge"])

    def zeile_pruefen(self, zeile):
        if _projekt(zeile) is None:
            return [f"Projekt {als_text(zeile['projekt'])} unbekannt"]
        nr = als_text(zeile["material"])
        if not nr and not als_text(zeile["bezeichnung"]):
            return ["weder Material noch Bezeichnung"]
        return []

    def zeile_uebernehmen(self, zeile):
        p = _projekt(zeile)
        if p.projektnr in self.vorhanden:
            return "unveraendert"
        m = Material.objects.filter(materialnr=als_text(zeile["material"])).first()
        status_text = als_text(zeile["status"]).lower()
        status = (Stuecklistenposition.Status.ENTNOMMEN if "entnommen" in status_text
                  else Stuecklistenposition.Status.GEPLANT if ("geplant" in status_text or "idee" in status_text)
                  else Stuecklistenposition.Status.BENOETIGT)
        ek = als_zahl(zeile["ek"])
        pos = als_zahl(zeile["pos"])
        Stuecklistenposition.objects.create(
            projekt=p, material=m, pos=int(pos) if pos else (p.stueckliste.count() + 1),
            bezeichnung=als_text(zeile["bezeichnung"]) or (m.bezeichnung if m else ""), menge=als_zahl(zeile["menge"]),
            einheit=als_text(zeile["einheit"]) or (m.einheit if m else ""),
            ek=ek if ek is not None and ek is not False else (m.ek_netto if m else None), status=status,
            notiz=f"aus Excel (Status „{als_text(zeile['status'])}“)" if als_text(zeile["status"]) else "aus Excel")
        return "neu"

    def zusatz(self):
        return "Entnommene Positionen werden nicht noch einmal vom Lager abgebucht (Lagerbestand kommt aus Blatt „Lager“)."


@registrieren
class KalkulationImporter(Importer):
    blatt = "Kalkulation"
    titel = "Kalkulation je Projekt"
    reihenfolge = 61
    spalten = {"A": "projekt", "B": "material", "C": "beschlaege", "D": "lohn_std", "E": "lohn_satz", "G": "maschinen",
               "H": "montage", "I": "fahrt", "J": "fremd", "L": "zuschlag", "M": "risiko", "U": "art"}
    startzeile = 4
    endzeile = 100

    def zeile_leer(self, zeile):
        werte = [als_zahl(zeile[f]) for f in ("material", "beschlaege", "lohn_std", "maschinen", "montage", "fahrt", "fremd")]
        return not als_text(zeile["projekt"]) or not any(w for w in werte if w not in (None, False))

    def zeile_pruefen(self, zeile):
        return [] if _projekt(zeile) else [f"Projekt {als_text(zeile['projekt'])} unbekannt"]

    @staticmethod
    def _prozent(wert, standard):
        z = als_zahl(wert)
        if z in (None, False):
            return standard
        return (z * 100).quantize(Decimal("0.01")) if abs(z) <= 1 else z  # Makro speichert 15 % als 0,15

    def zeile_uebernehmen(self, zeile):
        p = _projekt(zeile)
        if Kalkulation.objects.filter(projekt=p).exists():
            return "unveraendert"
        art = als_text(zeile["art"])
        Kalkulation.objects.create(
            projekt=p, art=art if art in Kalkulation.Art.values else Kalkulation.Art.VOR,
            material_manuell=_zahl(zeile["material"], None), beschlaege=_zahl(zeile["beschlaege"]),
            lohn_std=_zahl(zeile["lohn_std"]), lohn_satz=_zahl(zeile["lohn_satz"]), maschinen=_zahl(zeile["maschinen"]),
            montage=_zahl(zeile["montage"]), fahrt=_zahl(zeile["fahrt"]), fremd=_zahl(zeile["fremd"]),
            zuschlag=self._prozent(zeile["zuschlag"], Decimal("0")), risiko=self._prozent(zeile["risiko"], Decimal("0")),
            notiz="aus Excel übernommen")
        return "neu"


@registrieren
class AuftragImporter(Importer):
    blatt = "Auftraege"
    titel = "Aufträge (Angebot, Status, Freigaben)"
    reihenfolge = 62
    spalten = {"A": "aunr", "B": "projekt", "D": "leistung", "G": "angebot", "H": "status", "I": "kunde",
               "J": "termin", "K": "chef", "L": "meister"}
    startzeile = 4
    endzeile = 100

    def zeile_leer(self, zeile):
        return not als_text(zeile["aunr"])

    def zeile_pruefen(self, zeile):
        fehler = []
        if _projekt(zeile) is None:
            fehler.append(f"Projekt {als_text(zeile['projekt'])} unbekannt")
        if not als_zahl(zeile["angebot"]):
            fehler.append("Angebot netto fehlt")
        return fehler

    @staticmethod
    def _freigabe(wert):
        t = als_text(wert)
        if t in ("Freigegeben", "Erteilt"):
            return Auftrag.Freigabe.FREIGEGEBEN
        return t if t in Auftrag.Freigabe.values else Auftrag.Freigabe.OFFEN

    def zeile_uebernehmen(self, zeile):
        p = _projekt(zeile)
        if Auftrag.objects.filter(aunr__iexact=als_text(zeile["aunr"])).exists() or Auftrag.objects.filter(projekt=p).exists():
            return "unveraendert"
        status = als_text(zeile["status"])
        Auftrag.objects.create(
            aunr=als_text(zeile["aunr"]), projekt=p, leistung=als_text(zeile["leistung"]), angebot_netto=als_zahl(zeile["angebot"]),
            status=status if status in Auftrag.Status.values else Auftrag.Status.ANGEBOT,
            termin=als_text(zeile["termin"])[:60], freigabe_kunde=self._freigabe(zeile["kunde"]),
            freigabe_chef=self._freigabe(zeile["chef"]), freigabe_meister=self._freigabe(zeile["meister"]))
        return "neu"
