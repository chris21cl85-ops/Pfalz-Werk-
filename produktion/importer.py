"""Import der Produktions-Blätter der Excel-Fassung.

Arbeitsgangbibliothe(k) (ab Zeile 5): A Code, B Kategorie, C Arbeitsgang, D Typ (mit Zeichen), E Standardfolge,
    F QM danach?, G Wartezeit möglich?, H Hinweis. Vorhandene Codes werden aktualisiert.
Routenvorlagen (ab Zeile 5): B Route, C Werkstoffgruppe, D Schritt, E AG-Code, F Arbeitsgang, G Typ, H Plan-Std.,
    I Wartezeit Std., J Hinweis. Je Route nur, solange sie im Programm noch nicht existiert.
Arbeitsgänge (Zeilen 6–205): A AG-ID, C Projekt-ID, D Bauteil, E Arbeitsgang, F Reihenfolge, G Mitarbeiter, I/J Plan,
    K Status, L Priorität, M Plan-Std., N Ist-Std., P Problem, Q Begonnen, R Fertig, S Bemerkung, U Vorgänger,
    AD Vorgangstyp, AE Wartezeit. Vorhandene AG-IDs werden nie überschrieben.
QM (Zeilen 5–204): A QM-ID, C Projekt-ID, D Bauteil, E Prüfpunkt, F Prüfer, G Datum, H Ergebnis, I Abweichung,
    J Nacharbeit nötig, K erledigt, L Nachprüfung, N AG-ID.
"""
import re
from datetime import date, datetime, time
from decimal import Decimal

from django.utils import timezone

from importe.dienst import Importer, als_text, registrieren
from material.importer import als_zahl
from mitarbeiter.models import Mitarbeiter
from projekte.models import Projekt

from .models import TYPEN, Arbeitsgang, QMPruefung, Route, Routenschritt, Vorlage


def _typ(text):
    """„👷 Arbeitszeit“ → „Arbeitszeit“."""
    t = als_text(text)
    for typ in TYPEN:
        if typ.lower() in t.lower():
            return typ
    return re.sub(r"^\W+\s*", "", t)[:30]


def _ja(text):
    return als_text(text).lower() in ("ja", "x", "1", "true", "wahr")


def _zahl(wert):
    z = als_zahl(wert)
    return Decimal("0") if z in (None, False) else z


def _datum(wert):
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    return None


def _zeitpunkt(wert):
    if isinstance(wert, datetime):
        return timezone.make_aware(wert) if timezone.is_naive(wert) else wert
    if isinstance(wert, date):
        return timezone.make_aware(datetime.combine(wert, time(12)))
    return None


def _mitarbeiter(text):
    t = als_text(text)
    if not t:
        return None
    return (Mitarbeiter.objects.filter(kuerzel__iexact=t).first() or Mitarbeiter.objects.filter(name__iexact=t).first())


@registrieren
class BibliothekImporter(Importer):
    blatt = "Produktion Arbeitsgangbibliothe"
    titel = "Arbeitsgangbibliothek"
    reihenfolge = 80
    spalten = {"A": "code", "B": "kategorie", "C": "name", "D": "typ", "E": "folge", "F": "qm", "G": "warte", "H": "hinweis"}
    startzeile = 5
    endzeile = 300

    def zeile_leer(self, z):
        return not als_text(z["code"]) or als_text(z["code"]).upper() == "AG-CODE"

    def zeile_pruefen(self, z):
        return [] if als_text(z["name"]) else ["Arbeitsgang fehlt"]

    def zeile_uebernehmen(self, z):
        werte = {"kategorie": als_text(z["kategorie"])[:60], "name": als_text(z["name"])[:150], "typ": _typ(z["typ"]),
                 "standardfolge": int(_zahl(z["folge"])), "qm_danach": _ja(z["qm"]), "wartezeit_moeglich": _ja(z["warte"]),
                 "hinweis": als_text(z["hinweis"])[:250]}
        v = Vorlage.objects.filter(code=als_text(z["code"])).first()
        if v is None:
            Vorlage.objects.create(code=als_text(z["code"]), **werte)
            return "neu"
        if all(getattr(v, k) == w for k, w in werte.items()):
            return "unveraendert"
        for k, w in werte.items():
            setattr(v, k, w)
        v.save()
        return "geaendert"


@registrieren
class RoutenImporter(Importer):
    blatt = "Produktion Routenvorlagen"
    titel = "Routenvorlagen"
    reihenfolge = 81
    spalten = {"B": "route", "C": "gruppe", "D": "schritt", "E": "code", "F": "name", "G": "typ", "H": "std",
               "I": "warte", "J": "hinweis"}
    startzeile = 5
    endzeile = 400

    def __init__(self):
        self.vorhanden = set(Route.objects.values_list("name", flat=True))

    def zeile_leer(self, z):
        return not als_text(z["route"]) or not als_text(z["code"]) or als_text(z["route"]).upper() == "ROUTENVORLAGE"

    def zeile_pruefen(self, z):
        return [] if als_zahl(z["schritt"]) else ["Schritt-Nummer fehlt"]

    def zeile_uebernehmen(self, z):
        name = als_text(z["route"])[:100]
        if name in self.vorhanden:
            return "unveraendert"
        route, _ = Route.objects.get_or_create(name=name, defaults={"werkstoffgruppe": als_text(z["gruppe"])[:60]})
        Routenschritt.objects.update_or_create(route=route, schritt=int(als_zahl(z["schritt"])), defaults={
            "code": als_text(z["code"])[:20], "name": als_text(z["name"])[:150], "typ": _typ(z["typ"]),
            "plan_std": _zahl(z["std"]), "wartezeit_std": _zahl(z["warte"]), "hinweis": als_text(z["hinweis"])[:250]})
        return "neu"


@registrieren
class ArbeitsgangImporter(Importer):
    blatt = "Produktion Arbeitsgänge"
    titel = "Arbeitsgänge (Produktion)"
    reihenfolge = 82
    spalten = {"A": "agid", "C": "projekt", "D": "bereich", "E": "name", "F": "folge", "G": "ma", "I": "start", "J": "ende",
               "K": "status", "L": "prio", "M": "plan", "N": "ist", "P": "problem", "Q": "begonnen", "R": "fertig",
               "S": "bemerkung", "U": "vorgaenger", "AD": "typ", "AE": "warte"}
    startzeile = 6
    endzeile = 205

    def __init__(self):
        self.vorgaenger = {}

    def zeile_leer(self, z):
        return not als_text(z["agid"])

    def zeile_pruefen(self, z):
        fehler = []
        if not Projekt.objects.filter(projektnr=als_text(z["projekt"])).exists():
            fehler.append(f"Projekt {als_text(z['projekt'])} unbekannt")
        if not als_text(z["name"]):
            fehler.append("Arbeitsgang fehlt")
        if als_text(z["ma"]) and _mitarbeiter(z["ma"]) is None:
            fehler.append(f"Mitarbeiter {als_text(z['ma'])} unbekannt")
        return fehler

    def zeile_uebernehmen(self, z):
        agid = als_text(z["agid"])
        if Arbeitsgang.objects.filter(agid=agid).exists():
            return "unveraendert"
        status = als_text(z["status"])
        prio = als_text(z["prio"])
        bemerkung = als_text(z["bemerkung"])
        code = re.search(r"\b([A-Z]{2,3}-\d{3})\b", bemerkung)
        Arbeitsgang.objects.create(
            agid=agid, projekt=Projekt.objects.get(projektnr=als_text(z["projekt"])), bereich=als_text(z["bereich"])[:200],
            name=als_text(z["name"])[:150], code=code.group(1) if code else "", typ=_typ(z["typ"]),
            reihenfolge=int(_zahl(z["folge"])), mitarbeiter=_mitarbeiter(z["ma"]), plan_start=_datum(z["start"]),
            plan_ende=_datum(z["ende"]), status=status if status in Arbeitsgang.Status.values else Arbeitsgang.Status.GEPLANT,
            prioritaet=prio if prio in Arbeitsgang.Prioritaet.values else Arbeitsgang.Prioritaet.MITTEL,
            plan_std=_zahl(z["plan"]), ist_std=_zahl(z["ist"]), wartezeit_std=_zahl(z["warte"]),
            problem=als_text(z["problem"])[:250], begonnen_am=_zeitpunkt(z["begonnen"]), fertig_am=_zeitpunkt(z["fertig"]),
            bemerkung=bemerkung[:250], ist_nacharbeit="-NA" in agid)
        if als_text(z["vorgaenger"]):
            self.vorgaenger[agid] = als_text(z["vorgaenger"])
        return "neu"

    def zusatz(self):
        n = 0
        for agid, vor in self.vorgaenger.items():
            v = Arbeitsgang.objects.filter(agid=vor).first()
            if v:
                Arbeitsgang.objects.filter(agid=agid).update(vorgaenger=v)
                n += 1
        return f"{n} Vorgänger-Verknüpfungen gesetzt." if self.vorgaenger else ""


@registrieren
class QMImporter(Importer):
    blatt = "Produktion QM"
    titel = "QM-Prüfungen"
    reihenfolge = 83
    spalten = {"A": "qmid", "C": "projekt", "D": "bauteil", "E": "punkt", "F": "pruefer", "G": "datum", "H": "ergebnis",
               "I": "abweichung", "J": "noetig", "K": "erledigt", "L": "nach", "N": "agid"}
    startzeile = 5
    endzeile = 204

    def zeile_leer(self, z):
        return not als_text(z["projekt"]) or not als_text(z["ergebnis"])

    def zeile_pruefen(self, z):
        fehler = []
        if not Projekt.objects.filter(projektnr=als_text(z["projekt"])).exists():
            fehler.append(f"Projekt {als_text(z['projekt'])} unbekannt")
        if als_text(z["ergebnis"]) not in QMPruefung.Ergebnis.values:
            fehler.append(f"Ergebnis „{als_text(z['ergebnis'])}“ unbekannt")
        return fehler

    def zeile_uebernehmen(self, z):
        from .dienst import _naechste_qmid
        qmid = als_text(z["qmid"])
        p = Projekt.objects.get(projektnr=als_text(z["projekt"]))
        ag = Arbeitsgang.objects.filter(agid=als_text(z["agid"])).first()
        if (qmid and QMPruefung.objects.filter(qmid=qmid).exists()) or QMPruefung.objects.filter(
                projekt=p, arbeitsgang=ag, datum=_datum(z["datum"]), ergebnis=als_text(z["ergebnis"]),
                abweichung=als_text(z["abweichung"])[:300]).exists():
            return "unveraendert"
        QMPruefung.objects.create(
            qmid=qmid or _naechste_qmid(), projekt=p, arbeitsgang=ag, bauteil=als_text(z["bauteil"])[:150] or "Gesamt",
            pruefpunkt=als_text(z["punkt"])[:150] or "Endkontrolle", pruefer=als_text(z["pruefer"])[:100] or "–",
            datum=_datum(z["datum"]) or timezone.localdate(), ergebnis=als_text(z["ergebnis"]),
            abweichung=als_text(z["abweichung"])[:300], nacharbeit_noetig=_ja(z["noetig"]),
            nacharbeit_erledigt=_ja(z["erledigt"]), nachpruefung=als_text(z["nach"])[:20])
        return "neu"
