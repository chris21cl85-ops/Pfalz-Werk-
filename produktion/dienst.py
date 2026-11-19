"""Abläufe der Produktion wie PW_Produktion.bas: Planen → Fertigung → QM → Montage → Fertig."""
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from kern.models import protokolliere

from .models import WARTEZEIT, Arbeitsgang, QMPruefung, Route, Vorlage

SCHRITTE = ["Planen", "Fertigung", "QM", "Montage", "Fertig"]
QM_FOLGE = {"QM-010": 45, "QM-020": 125, "QM-030": 175, "QM-040": 195}  # wie AGSortiert() im Möbelrechner
S = Arbeitsgang.Status


class ProduktionsFehler(Exception):
    pass


def werktag(d: date, n: int) -> date:
    """n Arbeitstage nach d (Sa/So überspringen) – wie Werktag() im Makro."""
    while d.weekday() > 4:
        d += timedelta(days=1)
    for _ in range(n):
        d += timedelta(days=1)
        while d.weekday() > 4:
            d += timedelta(days=1)
    return d


def mitarbeiter_von(benutzer):
    try:
        return benutzer.mitarbeiter
    except Exception:
        return None


def benutzername(benutzer) -> str:
    m = mitarbeiter_von(benutzer)
    return m.name if m else (benutzer.get_full_name() or benutzer.username)


# ------------------------------------------------------------------ Stand und Phase
def qm_stand(projekt) -> int:
    """0 keine Prüfung, 1 freigegeben, 2 gesperrt (wie QMStand)."""
    pruefungen = list(projekt.qm_pruefungen.all())
    if not pruefungen:
        return 0
    return 1 if all(p.freigabe == "Freigegeben" for p in pruefungen) else 2


def stand(projekt) -> dict:
    ags = list(projekt.arbeitsgaenge.all())
    d = {"n": len(ags), "fertig": sum(a.status == S.FERTIG for a in ags),
         "gestartet": sum(a.status != S.GEPLANT for a in ags), "geplant": sum(a.plan_start is not None for a in ags),
         "soll": sum((a.plan_std for a in ags), Decimal("0")), "ist": sum((a.ist_std for a in ags), Decimal("0")),
         "lohn": _lohn(projekt), "qm": qm_stand(projekt),
         "montage_bestanden": _montage_bestanden(projekt)}
    d["phase"] = phase(projekt, d)
    return d


def _lohn(projekt) -> Decimal:
    from zeiten.dienst import lohn_ist
    return lohn_ist(projekt)


def _montage_bestanden(projekt) -> bool:
    try:
        return projekt.montage.ergebnis == "Bestanden"
    except Exception:  # noch keine Montage
        return False


def phase(projekt, d=None) -> int:
    """0 Planen, 1 Fertigung, 2 QM, 3 Montage, 4 Fertig (wie Phase())."""
    d = d or stand(projekt)
    if d["montage_bestanden"]:
        return 4
    if d["n"] == 0 or (d["geplant"] == 0 and d["gestartet"] == 0):
        return 0
    if d["fertig"] < d["n"]:
        return 1
    if d["qm"] != 1:
        return 2
    return 3


# ------------------------------------------------------------------ Arbeitsgänge anlegen
def _vorlage(code):
    return Vorlage.objects.filter(code=code).first()


def _naechste_nr(projekt, praefix) -> int:
    hoechste = 0
    for agid in Arbeitsgang.objects.filter(agid__startswith=praefix).values_list("agid", flat=True):
        rest = agid[len(praefix):]
        if rest.isdigit():
            hoechste = max(hoechste, int(rest))
    return hoechste + 1


def codes_fuer_moebel(position) -> list[tuple[str, str]]:
    """Wie ArbeitsgaengeBilden() + AGSortiert(): (Code, Bereich) aus dem Möbelrechner in Standardfolge
    (QM-Prüfungen direkt nach ihrem Arbeitsschritt)."""
    from moebel.dienst import rechnen
    ag = dict(rechnen(position.eingaben).get("arbeitsgaenge") or [])
    folge = {v.code: v.standardfolge for v in Vorlage.objects.filter(code__in=ag)}
    return sorted(ag.items(), key=lambda kv: QM_FOLGE.get(kv[0], folge.get(kv[0]) or 9999))


def aus_moebel(position, benutzer) -> int:
    """Wie PW_Moebel_Arbeitsgaenge: erst Stückliste, dann Arbeitsgänge; geplante werden ersetzt."""
    from moebel.models import MoebelPosition
    if position.status not in (MoebelPosition.Status.STUECKLISTE, MoebelPosition.Status.ARBEITSGAENGE):
        raise ProduktionsFehler("Reihenfolge: erst „In Stückliste übernehmen“, dann die Arbeitsgänge.")
    alt = Arbeitsgang.objects.filter(moebel=position)
    begonnen = alt.exclude(status=S.GEPLANT).first()
    if begonnen:
        raise ProduktionsFehler(f"Arbeitsgänge dieser Position sind schon begonnen ({begonnen.agid}: {begonnen.status}). "
                                "Keine Übernahme – Änderung bitte in der Produktion von Hand.")
    codes = codes_fuer_moebel(position)
    from moebel.models import Regelwerk
    warte = Decimal(str(Regelwerk.laden().als_regeln().r("WARTE_STD")))
    with transaction.atomic():
        alt.delete()
        vorher = None
        for n, (code, bereich) in enumerate(codes, start=1):
            v = _vorlage(code)
            vorher = Arbeitsgang.objects.create(
                agid=f"{position.positions_id}-AG{n:02d}", projekt=position.projekt, moebel=position,
                bereich=f"{position.bezeichnung} ({position.pos}) - {bereich}", name=v.name if v else code, code=code,
                typ=v.typ if v else "", reihenfolge=n * 10, bemerkung=f"aus Möbelrechner, {code}", vorgaenger=vorher,
                wartezeit_std=warte if v and v.typ == WARTEZEIT else Decimal("0"))
        position.status = MoebelPosition.Status.ARBEITSGAENGE
        position.save(update_fields=["status"])
    protokolliere("arbeitsgaenge_aus_moebel", position.positions_id, benutzer=benutzer,
                  details=f"{len(codes)} Arbeitsgänge: " + ", ".join(c for c, _ in codes))
    return len(codes)


def aus_route(projekt, route: Route, bauteil: str, benutzer) -> int:
    """Routenvorlage als Arbeitsgänge übernehmen (Startpunkt, danach frei änderbar)."""
    schritte = list(route.schritte.all())
    if not schritte:
        raise ProduktionsFehler("Diese Route hat keine Schritte.")
    praefix = f"{projekt.projektnr}-AG"
    with transaction.atomic():
        nr = _naechste_nr(projekt, praefix)
        vorher = projekt.arbeitsgaenge.order_by("-pk").first()
        basis = (vorher.reihenfolge if vorher else 0)
        for i, s in enumerate(schritte):
            v = _vorlage(s.code)
            vorher = Arbeitsgang.objects.create(
                agid=f"{praefix}{nr + i:02d}", projekt=projekt, bereich=bauteil or route.name, name=s.name, code=s.code,
                typ=s.typ or (v.typ if v else ""), reihenfolge=basis + (i + 1) * 10, plan_std=s.plan_std,
                wartezeit_std=s.wartezeit_std, bemerkung=(f"Route {route.name}" + (f" – {s.hinweis}" if s.hinweis else ""))[:250],
                vorgaenger=vorher)
    protokolliere("arbeitsgaenge_aus_route", projekt.projektnr, benutzer=benutzer,
                  details=f"Route „{route.name}“ ({bauteil or '–'}): {len(schritte)} Arbeitsgänge")
    return len(schritte)


def einzeln(projekt, vorlage: Vorlage, *, bauteil="", plan_std=Decimal("0"), mitarbeiter=None, benutzer) -> Arbeitsgang:
    """Einen Arbeitsgang aus der Bibliothek anhängen (Vorgänger = bisher letzter Arbeitsgang)."""
    praefix = f"{projekt.projektnr}-AG"
    vorher = projekt.arbeitsgaenge.order_by("-pk").first()
    ag = Arbeitsgang.objects.create(
        agid=f"{praefix}{_naechste_nr(projekt, praefix):02d}", projekt=projekt, bereich=bauteil, name=vorlage.name,
        code=vorlage.code, typ=vorlage.typ, reihenfolge=(vorher.reihenfolge if vorher else 0) + 10,
        plan_std=plan_std or Decimal("0"), mitarbeiter=mitarbeiter, vorgaenger=vorher, bemerkung="von Hand angelegt")
    protokolliere("arbeitsgang_angelegt", ag.agid, benutzer=benutzer, details=f"{ag.name} ({ag.code})")
    return ag


def entfernen(ag: Arbeitsgang, benutzer):
    """Nur geplante Arbeitsgänge ohne Stunden; Nachfolger rücken an den Vorgänger."""
    if ag.status != S.GEPLANT or ag.ist_std:
        raise ProduktionsFehler("Nur geplante Arbeitsgänge ohne Ist-Stunden können entfernt werden.")
    with transaction.atomic():
        ag.nachfolger.update(vorgaenger=ag.vorgaenger)
        protokolliere("arbeitsgang_entfernt", ag.agid, benutzer=benutzer, details=ag.name)
        ag.delete()


# ------------------------------------------------------------------ Planen
def einplanen(projekt, start: date, mitarbeiter, benutzer) -> int:
    """Wie PlanenSpeichern: Plan-Start/-Ende je Arbeitsgang nach Stunden (8 h/Tag) in Reihenfolge;
    Mitarbeiter nur dort, wo noch leer."""
    std, n = Decimal("0"), 0
    with transaction.atomic():
        for ag in projekt.arbeitsgaenge.exclude(status=S.FERTIG).order_by("pk"):
            dauer = ag.plan_std if ag.plan_std > 0 else Decimal("1")
            ag.plan_start = werktag(start, int(std / 8))
            ag.plan_ende = werktag(start, int((std + dauer - Decimal("0.01")) / 8))
            std += dauer
            if ag.mitarbeiter_id is None and mitarbeiter is not None:
                ag.mitarbeiter = mitarbeiter
            ag.save(update_fields=["plan_start", "plan_ende", "mitarbeiter"])
            n += 1
    protokolliere("produktion_eingeplant", projekt.projektnr, benutzer=benutzer,
                  details=f"{n} Arbeitsgänge ab {start:%d.%m.%Y}" + (f", {mitarbeiter.name}" if mitarbeiter else ""))
    return n


# ------------------------------------------------------------------ Fertigung
def starten(ag: Arbeitsgang, benutzer):
    if ag.status != S.GEPLANT:
        raise ProduktionsFehler(f"„{ag.name}“ ist schon {ag.status}.")
    if not ag.startbereit:
        raise ProduktionsFehler(f"Startet erst, wenn die Startfreigabe grün ist: {ag.startfreigabe}")
    ag.status, ag.begonnen_am = S.IN_ARBEIT, timezone.now()
    if ag.mitarbeiter_id is None:
        ag.mitarbeiter = mitarbeiter_von(benutzer)
    ag.save(update_fields=["status", "begonnen_am", "mitarbeiter"])
    protokolliere("arbeitsgang_gestartet", ag.agid, benutzer=benutzer, details=ag.name)


def rueckmelden(ag: Arbeitsgang, *, stunden, fertig: bool, benutzer):
    """Zwischenstand (Stunden addieren) oder fertig melden (Fertig am setzen)."""
    if ag.status != S.IN_ARBEIT:
        raise ProduktionsFehler("Rückmelden geht nur bei Arbeitsgängen „In Arbeit“.")
    stunden = Decimal(stunden or 0)
    if stunden < 0:
        raise ProduktionsFehler("Stunden können nicht negativ sein.")
    if not fertig and stunden == 0:
        raise ProduktionsFehler("Für einen Zwischenstand bitte Stunden eintragen.")
    felder = []
    if stunden > 0:
        from zeiten import dienst as zeiten
        ma = ag.mitarbeiter or mitarbeiter_von(benutzer)
        if ma is not None:  # Zeitbuchung zählt die Ist-Stunden am Arbeitsgang mit
            try:
                zeiten.buchen(mitarbeiter=ma, datum=timezone.localdate(), stunden=stunden, arbeitsgang=ag,
                              taetigkeit="Montage" if ag.code.startswith("MO") else "Fertigung",
                              quelle="Produktion", benutzer=benutzer)
            except zeiten.ZeitFehler as fehler:
                raise ProduktionsFehler(str(fehler)) from fehler
        else:
            ag.ist_std += stunden
            felder.append("ist_std")
    if fertig:
        ag.status, ag.fertig_am = S.FERTIG, timezone.now()
        felder += ["status", "fertig_am"]
    if felder:
        ag.save(update_fields=felder)
    protokolliere("arbeitsgang_fertig" if fertig else "arbeitsgang_zwischenstand", ag.agid, benutzer=benutzer,
                  details=f"{ag.name}: +{stunden:g} h, gesamt {ag.ist_std:g} h")


# ------------------------------------------------------------------ QM
def _naechste_qmid() -> str:
    hoechste = 0
    for q in QMPruefung.objects.values_list("qmid", flat=True):
        if q.startswith("QM-") and q[3:].isdigit():
            hoechste = max(hoechste, int(q[3:]))
    return f"QM-{hoechste + 1:04d}"


def endkontrolle(projekt, *, bestanden: bool, abweichung="", benutzer) -> QMPruefung:
    """Wie QMSpeichern: Endkontrolle nach der Fertigung. Nicht bestanden → Nacharbeit-Arbeitsgang, Projekt zurück
    in die Fertigung. Bestanden schließt frühere gesperrte Prüfungen (Nacharbeit erledigt, Nachprüfung bestanden)."""
    d = stand(projekt)
    if d["phase"] < 2:
        raise ProduktionsFehler("QM kommt nach der Fertigung – erst alle Arbeitsgänge fertig melden.")
    abweichung = (abweichung or "").strip()
    if not bestanden and not abweichung:
        raise ProduktionsFehler("Kurz beschreiben, was fehlt.")
    letzte = projekt.arbeitsgaenge.order_by("-pk").first()
    offen = [p for p in projekt.qm_pruefungen.all() if p.freigabe != "Freigegeben"]
    with transaction.atomic():
        for p in offen:  # Nachprüfung der früheren Mängel
            p.nacharbeit_erledigt = True
            p.nachpruefung = "Bestanden" if bestanden else "Nicht bestanden"
            p.save(update_fields=["nacharbeit_erledigt", "nachpruefung"])
        q = QMPruefung.objects.create(
            qmid=_naechste_qmid(), projekt=projekt, arbeitsgang=letzte, pruefer=benutzername(benutzer),
            datum=timezone.localdate(), ergebnis=QMPruefung.Ergebnis.BESTANDEN if bestanden else QMPruefung.Ergebnis.NICHT,
            abweichung="" if bestanden else abweichung[:300], nacharbeit_noetig=not bestanden, erfasst_von=benutzer)
        if not bestanden:
            praefix = f"{projekt.projektnr}-NA"
            morgen = werktag(timezone.localdate(), 1)
            na = Arbeitsgang.objects.create(
                agid=f"{praefix}{_naechste_nr(projekt, praefix):02d}", projekt=projekt, bereich="Nacharbeit (QM)",
                name=f"Nacharbeit: {abweichung}"[:150], code="NA-010", typ="Nacharbeit",
                reihenfolge=(letzte.reihenfolge if letzte else 0) + 5, mitarbeiter=letzte.mitarbeiter if letzte else None,
                plan_start=morgen, plan_ende=morgen, prioritaet=Arbeitsgang.Prioritaet.HOCH, plan_std=Decimal("1"),
                bemerkung=f"aus QM {timezone.localdate():%d.%m.%Y} ({q.qmid})", ist_nacharbeit=True)
            q.nacharbeit_ag = na
            q.save(update_fields=["nacharbeit_ag"])
    protokolliere("qm_endkontrolle", projekt.projektnr, benutzer=benutzer,
                  details=f"{q.qmid} {q.ergebnis}" + (f": {abweichung}" if not bestanden else ""))
    return q


def offene_fuer(mitarbeiter):
    """Arbeitsgänge des Mitarbeiters, die nicht fertig sind (wie Handy-Ableger)."""
    return (Arbeitsgang.objects.filter(mitarbeiter=mitarbeiter).exclude(status=S.FERTIG)
            .select_related("projekt", "projekt__kunde", "vorgaenger").order_by("plan_start", "pk"))


__all__ = ["SCHRITTE", "WARTEZEIT", "ProduktionsFehler"]
