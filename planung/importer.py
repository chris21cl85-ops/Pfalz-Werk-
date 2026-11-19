"""Import der Blätter „Teams“, „Zeitdaten“, „Montageplan“, „Zeitplan“ (Spalten wie PW_Produktion / PW_Kalender).

Teams (Zeilen 4–100): A Team-ID, B Teamart, J Status, L Teamname (ohne Namen = reservierter Platz, übersprungen);
       Mitglieder ab Zeile 110: A Team-ID, B Mitarbeiter, C Funktion (Leitung/Mitglied), F Zuordnung aktiv (Ja/Nein).
Zeitdaten (Zeilen 4–350): A Zeit-ID, B Mitarbeiter, C Von, D Bis, E Zeitart, H Status, L Hinweis.
Montageplan (Zeilen 4–254): B Projekt, C Adresse, D Datum, E Beginn, F Ende, G Team-ID, I Aufgaben, J Material,
       K Werkzeug, L Fahrzeug, M Hinweise, Q Ergebnis. Je Projekt eine Montage, vorhandene werden nicht überschrieben.
Zeitplan (Zeilen 4–500): A Termin-ID, B Mitarbeiter, C Datum, D Start, E Ende, F Projekt, H Aufgabe, I Ort, J Team-ID,
       K Terminart, X Quelle. Vorhandene Termin-IDs werden nie überschrieben.
Mitarbeiter werden über Kürzel (z. B. „D.Kaub“) oder Namen gefunden.
"""
from datetime import date, datetime, time

from importe.dienst import Importer, als_text, registrieren
from mitarbeiter.models import Mitarbeiter
from projekte.models import Projekt

from .dienst import naechste_id
from .models import TEAMARTEN, Abwesenheit, Montage, Team, TeamMitglied, Termin


def _ma(text):
    t = als_text(text)
    if not t:
        return None
    return Mitarbeiter.objects.filter(kuerzel__iexact=t).first() or Mitarbeiter.objects.filter(name__iexact=t).first()


def _datum(w):
    if isinstance(w, datetime):
        return w.date()
    if isinstance(w, date):
        return w
    return None


def _zeit(w):
    if isinstance(w, time):
        return w.replace(second=0, microsecond=0)
    if isinstance(w, datetime):
        return w.time().replace(second=0, microsecond=0)
    if isinstance(w, (int, float)) and 0 <= w < 1:
        minuten = round(w * 24 * 60)
        return time(minuten // 60, minuten % 60)
    t = als_text(w).replace(".", ":")
    if ":" in t:
        try:
            h, m = t.split(":")[:2]
            return time(int(h), int(m))
        except ValueError:
            return None
    return None


@registrieren
class TeamImporter(Importer):
    """Zeilen 4–100 Teams, ab Zeile 110 Mitglieder (gleiches Blatt, zwei Bereiche)."""
    blatt = "Teams"
    titel = "Teams und Mitglieder"
    reihenfolge = 90
    spalten = {"A": "id", "B": "b", "C": "funktion", "F": "aktiv", "J": "status", "K": "hinweis", "L": "name"}
    startzeile = 4
    endzeile = 409

    @staticmethod
    def _mitglied(z):
        return z["_zeile"] >= 110

    def zeile_leer(self, z):
        if not als_text(z["id"]).upper().startswith("TEAM-") or 100 < z["_zeile"] < 110:
            return True
        return not als_text(z["b"]) if self._mitglied(z) else not als_text(z["name"])  # reservierte Plätze

    def zeile_pruefen(self, z):
        if self._mitglied(z):
            fehler = [] if _ma(z["b"]) else [f"Mitarbeiter {als_text(z['b'])} unbekannt"]
            if not Team.objects.filter(teamid=als_text(z["id"])).exists():
                fehler.append(f"Team {als_text(z['id'])} hat keinen Namen oder fehlt")
            return fehler
        return []

    def zeile_uebernehmen(self, z):
        teamid = als_text(z["id"])
        if self._mitglied(z):
            team, ma = Team.objects.get(teamid=teamid), _ma(z["b"])
            if TeamMitglied.objects.filter(team=team, mitarbeiter=ma).exists():
                return "unveraendert"
            TeamMitglied.objects.create(team=team, mitarbeiter=ma, leitung=als_text(z["funktion"]) == "Leitung",
                                        aktiv=als_text(z["aktiv"]) != "Nein")
            return "neu"
        name = als_text(z["name"])
        if Team.objects.filter(teamid=teamid).exists() or Team.objects.filter(name__iexact=name).exists():
            return "unveraendert"
        art = als_text(z["b"])
        Team.objects.create(teamid=teamid, name=name[:100], art=art if art in TEAMARTEN else "Gemischt",
                            aktiv=als_text(z["status"]) not in ("Inaktiv", "Aufgelöst"), hinweis=als_text(z["hinweis"])[:250])
        return "neu"


def _stunden(z):
    """Zeitdaten: Einheit „Std“ und Auswirkung „Reduziert“ → Stunden je Tag, sonst ganzer Tag."""
    from material.importer import als_zahl
    umfang = als_zahl(z["umfang"])
    if als_text(z["einheit"]).lower().startswith("std") and als_text(z["auswirkung"]) == "Reduziert" \
            and umfang and umfang is not False and umfang > 0:
        return umfang
    return None


@registrieren
class ZeitdatenImporter(Importer):
    blatt = "Zeitdaten"
    titel = "Abwesenheiten (Zeitdaten)"
    reihenfolge = 91
    spalten = {"A": "id", "B": "ma", "C": "von", "D": "bis", "E": "art", "F": "umfang", "G": "einheit", "H": "status",
               "I": "auswirkung", "L": "hinweis"}
    startzeile = 4
    endzeile = 350

    def zeile_leer(self, z):
        return not als_text(z["ma"]) or _datum(z["von"]) is None

    def zeile_pruefen(self, z):
        return [] if _ma(z["ma"]) else [f"Mitarbeiter {als_text(z['ma'])} unbekannt"]

    def zeile_uebernehmen(self, z):
        zid = als_text(z["id"])
        ma, von = _ma(z["ma"]), _datum(z["von"])
        bis = max(_datum(z["bis"]) or von, von)
        if (zid and Abwesenheit.objects.filter(zid=zid).exists()) or \
                Abwesenheit.objects.filter(mitarbeiter=ma, von=von, bis=bis).exists():
            return "unveraendert"
        art = als_text(z["art"])
        status = als_text(z["status"])
        Abwesenheit.objects.create(
            zid=zid or naechste_id(Abwesenheit, "zid", "ZD-"), mitarbeiter=ma, von=von, bis=bis,
            art=art if art in Abwesenheit.Art.values else Abwesenheit.Art.SONSTIGES,
            status=status if status in Abwesenheit.Status.values else Abwesenheit.Status.FREIGEGEBEN,
            hinweis=(als_text(z["hinweis"]) or ("" if art in Abwesenheit.Art.values else art))[:250],
            stunden=_stunden(z))
        return "neu"


@registrieren
class MontageplanImporter(Importer):
    blatt = "Montageplan"
    titel = "Montageplan"
    reihenfolge = 92
    spalten = {"B": "projekt", "C": "adresse", "D": "datum", "E": "beginn", "F": "ende", "G": "team", "I": "aufgaben",
               "J": "material", "K": "werkzeug", "L": "fahrzeug", "M": "hinweise", "Q": "ergebnis"}
    startzeile = 4
    endzeile = 254

    def zeile_leer(self, z):
        return not als_text(z["projekt"]) or _datum(z["datum"]) is None

    def zeile_pruefen(self, z):
        return [] if Projekt.objects.filter(projektnr=als_text(z["projekt"])).exists() else \
            [f"Projekt {als_text(z['projekt'])} unbekannt"]

    def zeile_uebernehmen(self, z):
        p = Projekt.objects.get(projektnr=als_text(z["projekt"]))
        if Montage.objects.filter(projekt=p).exists():
            return "unveraendert"
        ergebnis = als_text(z["ergebnis"])
        Montage.objects.create(
            projekt=p, adresse=als_text(z["adresse"])[:250], datum=_datum(z["datum"]), beginn=_zeit(z["beginn"]) or time(7),
            ende=_zeit(z["ende"]) or time(16), team=Team.objects.filter(teamid=als_text(z["team"])).first(),
            aufgaben=als_text(z["aufgaben"])[:300], material=als_text(z["material"])[:250],
            werkzeug=als_text(z["werkzeug"])[:250], fahrzeug=als_text(z["fahrzeug"])[:60],
            hinweise=als_text(z["hinweise"])[:300], ergebnis=ergebnis if ergebnis in Montage.Ergebnis.values else "")
        return "neu"


@registrieren
class ZeitplanImporter(Importer):
    blatt = "Zeitplan"
    titel = "Zeitplan (Termine)"
    reihenfolge = 93
    spalten = {"A": "id", "B": "ma", "C": "datum", "D": "start", "E": "ende", "F": "projekt", "H": "aufgabe", "I": "ort",
               "J": "team", "K": "art", "X": "quelle"}
    startzeile = 4
    endzeile = 500

    def zeile_leer(self, z):
        return not als_text(z["ma"]) or _datum(z["datum"]) is None

    def zeile_pruefen(self, z):
        fehler = []
        if _ma(z["ma"]) is None:
            fehler.append(f"Mitarbeiter {als_text(z['ma'])} unbekannt")
        if als_text(z["projekt"]) and not Projekt.objects.filter(projektnr=als_text(z["projekt"])).exists():
            fehler.append(f"Projekt {als_text(z['projekt'])} unbekannt")
        return fehler

    def zeile_uebernehmen(self, z):
        tid = als_text(z["id"])
        ma, datum = _ma(z["ma"]), _datum(z["datum"])
        projekt = Projekt.objects.filter(projektnr=als_text(z["projekt"])).first() if als_text(z["projekt"]) else None
        aufgabe = als_text(z["aufgabe"]) or (f"Termin {projekt.name}" if projekt else "Termin")
        if (tid and Termin.objects.filter(terminid=tid).exists()) or \
                Termin.objects.filter(mitarbeiter=ma, datum=datum, aufgabe=aufgabe[:200]).exists():
            return "unveraendert"
        art = als_text(z["art"])
        Termin.objects.create(
            terminid=tid or naechste_id(Termin, "terminid", "T-"), mitarbeiter=ma, datum=datum, beginn=_zeit(z["start"]),
            ende=_zeit(z["ende"]), projekt=projekt, aufgabe=aufgabe[:200], ort=als_text(z["ort"])[:200],
            team=Team.objects.filter(teamid=als_text(z["team"])).first(),
            art=art if art in Termin.Art.values else Termin.Art.SONSTIGES,
            aus_montage=als_text(z["quelle"]) == "Montage")
        return "neu"
