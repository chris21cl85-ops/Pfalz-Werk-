"""Zeiterfassung: Buchen, Stornieren, Soll/Ist je Tag und Monat, Zeitkonto, Urlaub, Monatsabschluss, Lohnkosten."""
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from kern.models import protokolliere

from .feiertage import arbeitstage, feiertag
from .models import Arbeitsvertrag, Monatsabschluss, Zeitbuchung

NULL = Decimal("0")
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November",
          "Dezember"]
GUTSCHRIFT = {"Urlaub", "Krank", "Fortbildung", "Berufsschule"}  # zählen als erfüllte Soll-Zeit, Zeitausgleich nicht


class ZeitFehler(Exception):
    pass


def vertrag(ma):
    try:
        return ma.vertrag
    except Arbeitsvertrag.DoesNotExist:
        return None


def stundenlohn(ma) -> Decimal:
    """Lohnkosten: Stundenlohn aus dem Arbeitsvertrag (wie Spalte AJ), sonst Stundensatz am Mitarbeiter."""
    v = vertrag(ma)
    if v and v.stundenlohn:
        return v.stundenlohn
    return ma.stundensatz or NULL


def soll_tag(ma, tag: date) -> Decimal:
    """Soll-Stunden: Vertrag Mo–Fr, sonst Wochenstunden / 5, sonst 8 h. Wochenende und Feiertag = 0."""
    if tag.weekday() > 4 or feiertag(tag):
        return NULL
    v = vertrag(ma)
    if v and v.status != Arbeitsvertrag.Status.ENTWURF:
        if v.eintritt and tag < v.eintritt:
            return NULL
        return v.soll_wochentag(tag.weekday())
    if ma.eintritt and tag < ma.eintritt:
        return NULL
    if ma.wochenstunden:
        return (ma.wochenstunden / 5).quantize(Decimal("0.01"))
    return Decimal("8")


def monatsgrenzen(jahr, monat):
    return date(jahr, monat, 1), date(jahr, monat, calendar.monthrange(jahr, monat)[1])


def abgeschlossen(ma, tag: date) -> bool:
    return Monatsabschluss.objects.filter(mitarbeiter=ma, monat=tag.replace(day=1)).exists()


def gueltig(qs):
    return qs.filter(storniert_am__isnull=True)


# ------------------------------------------------------------------ Buchen
def _stunden(beginn, ende, pause_min) -> Decimal:
    a = datetime.combine(date.today(), beginn)
    b = datetime.combine(date.today(), ende)
    if b <= a:
        raise ZeitFehler("„Bis“ muss nach „Von“ liegen.")
    minuten = (b - a).seconds // 60 - (pause_min or 0)
    if minuten <= 0:
        raise ZeitFehler("Die Pause ist länger als die Arbeitszeit.")
    return (Decimal(minuten) / 60).quantize(Decimal("0.01"))


def buchen(*, mitarbeiter, datum, benutzer, stunden=None, beginn=None, ende=None, pause_min=0, projekt=None,
           arbeitsgang=None, taetigkeit=Zeitbuchung.Taetigkeit.FERTIGUNG, notiz="", quelle=Zeitbuchung.Quelle.HAND):
    """Eine Zeit buchen. Mit Arbeitsgang werden dessen Ist-Stunden mitgezählt (wie Rückmelden)."""
    if beginn and ende:
        stunden = _stunden(beginn, ende, pause_min)
    stunden = Decimal(str(stunden or 0)).quantize(Decimal("0.01"))
    if stunden <= 0:
        raise ZeitFehler("Stunden eintragen (oder Von und Bis).")
    if stunden > 16:
        raise ZeitFehler("Mehr als 16 Stunden an einem Tag – bitte prüfen.")
    if datum > timezone.localdate() + timedelta(days=1):
        raise ZeitFehler("Zeiten in der Zukunft können nicht gebucht werden.")
    if abgeschlossen(mitarbeiter, datum):
        raise ZeitFehler(f"{MONATE[datum.month - 1]} {datum.year} ist für {mitarbeiter.name} abgeschlossen.")
    if arbeitsgang is not None:
        if projekt is not None and arbeitsgang.projekt_id != projekt.pk:
            raise ZeitFehler("Der Arbeitsgang gehört zu einem anderen Projekt.")
        projekt = arbeitsgang.projekt
    with transaction.atomic():
        b = Zeitbuchung.objects.create(
            mitarbeiter=mitarbeiter, datum=datum, beginn=beginn, ende=ende, pause_min=pause_min or 0, stunden=stunden,
            projekt=projekt, arbeitsgang=arbeitsgang, taetigkeit=taetigkeit, notiz=(notiz or "")[:250],
            satz=stundenlohn(mitarbeiter), quelle=quelle, erfasst_von=benutzer)
        if arbeitsgang is not None:
            arbeitsgang.ist_std += stunden
            arbeitsgang.save(update_fields=["ist_std"])
    protokolliere("zeit_gebucht", f"{mitarbeiter.kuerzel} {datum:%d.%m.%Y}", benutzer=benutzer,
                  details=f"{stunden:g} h · {taetigkeit}" + (f" · {projekt.projektnr}" if projekt else "")
                  + (f" · {arbeitsgang.agid}" if arbeitsgang else "") + f" ({quelle})")
    return b


def stornieren(b: Zeitbuchung, grund: str, benutzer):
    """Buchung bleibt erhalten und wird nur als storniert markiert (nachvollziehbar)."""
    if b.storniert_am:
        raise ZeitFehler("Schon storniert.")
    if not (grund or "").strip():
        raise ZeitFehler("Bitte kurz den Grund angeben.")
    if abgeschlossen(b.mitarbeiter, b.datum):
        raise ZeitFehler("Der Monat ist abgeschlossen – Buchung gesperrt.")
    with transaction.atomic():
        b.storniert_am, b.storno_grund = timezone.now(), grund.strip()[:200]
        b.save(update_fields=["storniert_am", "storno_grund"])
        if b.arbeitsgang_id:
            ag = b.arbeitsgang
            ag.ist_std = max(NULL, ag.ist_std - b.stunden)
            ag.save(update_fields=["ist_std"])
    protokolliere("zeit_storniert", f"{b.mitarbeiter.kuerzel} {b.datum:%d.%m.%Y}", benutzer=benutzer,
                  details=f"{b.stunden:g} h · Grund: {b.storno_grund}")


# ------------------------------------------------------------------ Auswertung je Mitarbeiter
def _abwesenheiten(ma, von, bis):
    from planung.models import Abwesenheit
    tage = {}
    for a in ma.abwesenheiten.filter(status=Abwesenheit.Status.FREIGEGEBEN, von__lte=bis, bis__gte=von):
        d = max(a.von, von)
        while d <= min(a.bis, bis):
            tage[d] = a.art
            d += timedelta(days=1)
    return tage


def monat(ma, jahr: int, mon: int, bis_heute=True) -> dict:
    """Tagesliste mit Soll, Ist, Abwesenheit (freigegeben) und Feiertag; Summen. Soll nur bis heute."""
    von, bis = monatsgrenzen(jahr, mon)
    heute = timezone.localdate()
    grenze = min(bis, heute) if bis_heute else bis
    ist_je_tag = {}
    for b in gueltig(ma.zeitbuchungen.filter(datum__range=(von, bis))):
        ist_je_tag[b.datum] = ist_je_tag.get(b.datum, NULL) + b.stunden
    weg = _abwesenheiten(ma, von, bis)
    tage, summe = [], {"soll": NULL, "ist": NULL, "gutschrift": NULL}
    d = von
    while d <= bis:
        soll = soll_tag(ma, d) if d <= grenze else NULL
        art = weg.get(d, "")
        gut = soll if art in GUTSCHRIFT else NULL
        ist = ist_je_tag.get(d, NULL)
        tage.append({"datum": d, "soll": soll, "ist": ist, "abwesend": art, "gutschrift": gut, "feiertag": feiertag(d),
                     "wochenende": d.weekday() > 4, "zukunft": d > grenze, "diff": ist + gut - soll})
        summe["soll"] += soll
        summe["ist"] += ist
        summe["gutschrift"] += gut
        d += timedelta(days=1)
    summe["saldo"] = summe["ist"] + summe["gutschrift"] - summe["soll"]
    return {"tage": tage, "summe": summe, "von": von, "bis": bis, "name": f"{MONATE[mon - 1]} {jahr}",
            "abgeschlossen": Monatsabschluss.objects.filter(mitarbeiter=ma, monat=von).first()}


def kontobeginn(ma) -> date | None:
    v = vertrag(ma)
    eintritt = (v.eintritt if v and v.eintritt else None) or ma.eintritt
    erste = gueltig(ma.zeitbuchungen.all()).order_by("datum").values_list("datum", flat=True).first()
    # Das Konto läuft ab dem späteren von Eintritt und erster Buchung (Startwert = Übertrag aus der Excel)
    start = max(eintritt, erste) if eintritt and erste else (erste or eintritt)
    return start.replace(day=1) if start else None


def zeitkonto(ma, bis_monat: date | None = None) -> Decimal:
    """Startwert aus dem Vertrag + Saldo aller Monate ab Eintritt bzw. erster Buchung bis einschließlich bis_monat."""
    v = vertrag(ma)
    konto = v.zeitkonto_start if v else NULL
    beginn = kontobeginn(ma)
    ende = (bis_monat or timezone.localdate()).replace(day=1)
    if beginn is None:
        return konto
    m = beginn
    while m <= ende:
        konto += monat(ma, m.year, m.month)["summe"]["saldo"]
        m = (m + timedelta(days=32)).replace(day=1)
    return konto


def urlaub(ma, jahr: int) -> dict:
    """Wie UrlaubGenommen(): Arbeitstage (ohne Feiertage) der freigegebenen Urlaube im Jahr; beantragt extra."""
    from planung.models import Abwesenheit
    v = vertrag(ma)
    anspruch = v.urlaub_jahr if v else (ma.urlaubstage or NULL)
    genommen = beantragt = 0
    von, bis = date(jahr, 1, 1), date(jahr, 12, 31)
    for a in ma.abwesenheiten.filter(art="Urlaub", von__lte=bis, bis__gte=von).exclude(status=Abwesenheit.Status.ABGELEHNT):
        n = arbeitstage(max(a.von, von), min(a.bis, bis))
        if a.status == Abwesenheit.Status.FREIGEGEBEN:
            genommen += n
        else:
            beantragt += n
    return {"anspruch": anspruch, "genommen": genommen, "beantragt": beantragt, "rest": anspruch - genommen - beantragt}


def abschliessen(ma, jahr, mon, benutzer) -> Monatsabschluss:
    von, bis = monatsgrenzen(jahr, mon)
    if bis >= timezone.localdate():
        raise ZeitFehler("Ein Monat kann erst nach seinem letzten Tag abgeschlossen werden.")
    if Monatsabschluss.objects.filter(mitarbeiter=ma, monat=von).exists():
        raise ZeitFehler("Schon abgeschlossen.")
    m = monat(ma, jahr, mon)
    a = Monatsabschluss.objects.create(mitarbeiter=ma, monat=von, soll=m["summe"]["soll"], ist=m["summe"]["ist"],
                                       zeitkonto=zeitkonto(ma, von), abgeschlossen_von=benutzer)
    protokolliere("zeit_monat_abgeschlossen", f"{ma.kuerzel} {m['name']}", benutzer=benutzer,
                  details=f"Soll {a.soll:g} h, Ist {a.ist:g} h, Zeitkonto {a.zeitkonto:g} h")
    return a


def wieder_oeffnen(abschluss: Monatsabschluss, benutzer):
    name = f"{abschluss.mitarbeiter.kuerzel} {MONATE[abschluss.monat.month - 1]} {abschluss.monat.year}"
    protokolliere("zeit_monat_geoeffnet", name, benutzer=benutzer,
                  details=f"Abschluss vom {timezone.localtime(abschluss.abgeschlossen_am):%d.%m.%Y} aufgehoben")
    abschluss.delete()


# ------------------------------------------------------------------ Projekt / Lohnkosten
def lohn_ist(projekt) -> Decimal:
    """Lohnkosten Ist je Projekt: gültige Zeitbuchungen (Stunden × Stundenlohn bei Buchung) + Altbestand aus der
    Excel (Ist-Stunden an Arbeitsgängen ohne passende Buchungen × aktueller Stundenlohn)."""
    summe = sum((b.kosten for b in gueltig(projekt.zeitbuchungen.all())), NULL)
    for ag in projekt.arbeitsgaenge.select_related("mitarbeiter").all():
        gebucht = gueltig(ag.zeitbuchungen.all()).aggregate(s=Sum("stunden"))["s"] or NULL
        rest = ag.ist_std - gebucht
        if rest > 0 and ag.mitarbeiter_id:
            summe += (rest * stundenlohn(ag.mitarbeiter)).quantize(Decimal("0.01"))
    return summe


def stunden_je_projekt(projekt) -> Decimal:
    return gueltig(projekt.zeitbuchungen.all()).aggregate(s=Sum("stunden"))["s"] or NULL


# ------------------------------------------------------------------ Stundenzettel (PDF)
def stundenzettel_pdf(ma, jahr, mon) -> bytes:
    from io import BytesIO
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    m = monat(ma, jahr, mon, bis_heute=False)
    klein = ParagraphStyle("k", fontName="Helvetica", fontSize=8, leading=10)
    normal = ParagraphStyle("n", fontName="Helvetica", fontSize=9, leading=12)
    fett = ParagraphStyle("f", fontName="Helvetica-Bold", fontSize=14, leading=18)

    def p(t, s=klein):
        return Paragraph(escape(str(t)), s)

    def z(x):
        return f"{x:.2f}".replace(".", ",") if x else ""

    buchungen = {}
    for b in gueltig(ma.zeitbuchungen.filter(datum__range=(m["von"], m["bis"]))).select_related("projekt").order_by("beginn"):
        buchungen.setdefault(b.datum, []).append(b)
    puffer = BytesIO()
    doc = SimpleDocTemplate(puffer, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.3 * cm,
                            bottomMargin=1.3 * cm, title=f"Stundenzettel {ma.name} {m['name']}")
    zeilen = [[p(x) for x in ("Tag", "Soll", "Ist", "Projekt / Tätigkeit", "Bemerkung")]]
    for t in m["tage"]:
        texte = "; ".join((f"{b.beginn:%H:%M}–{b.ende:%H:%M} " if b.beginn and b.ende else "") + f"{b.stunden:g} h "
                          + (b.projekt.projektnr if b.projekt else b.get_taetigkeit_display()) for b in buchungen.get(t["datum"], []))
        bem = t["feiertag"] or t["abwesend"]
        zeilen.append([p(f"{['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'][t['datum'].weekday()]} {t['datum']:%d.%m.}"),
                       p(z(soll_tag(ma, t["datum"]))), p(z(t["ist"])), p(texte), p(bem)])
    soll_ganz = sum((soll_tag(ma, t["datum"]) for t in m["tage"]), NULL)
    gut = sum((soll_tag(ma, t["datum"]) for t in m["tage"] if t["abwesend"] in GUTSCHRIFT), NULL)
    zeilen.append([p("Summe", normal), p(z(soll_ganz), normal), p(z(m["summe"]["ist"]), normal),
                   p(f"Abwesenheit gutgeschrieben: {z(gut) or '0'} h", normal), p("")])
    t = Table(zeilen, colWidths=[2.2 * cm, 1.4 * cm, 1.4 * cm, 9.2 * cm, 3.8 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(231 / 255, 236 / 255, 232 / 255)),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.Color(.85, .87, .86)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.Color(53 / 255, 107 / 255, 74 / 255))]))
    ab = m["abgeschlossen"]
    teile = [p(f"Stundenzettel {m['name']}", fett),
             p(f"{ma.name} ({ma.kuerzel}) · gedruckt {timezone.localtime():%d.%m.%Y %H:%M}"
               + (f" · abgeschlossen am {timezone.localtime(ab.abgeschlossen_am):%d.%m.%Y}, Zeitkonto {z(ab.zeitkonto) or '0'} h"
                  if ab else " · Monat noch offen"), normal), Spacer(1, 0.3 * cm), t, Spacer(1, 1.2 * cm),
             p("_______________________________          _______________________________", normal),
             p("Mitarbeiter                                                         Betrieb", klein)]
    doc.build(teile)
    return puffer.getvalue()
