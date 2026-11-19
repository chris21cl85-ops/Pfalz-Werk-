"""Kapazität je Mitarbeiter und Tag – wie Blätter „Einsatzplanung“, „Personal-Leitstand“ und Zeitplan-Spalten M, P–AE.

Soll aus dem Arbeitsvertrag (Zeiterfassung), Abwesenheit ganztags = blockiert, mit Stunden = reduziert,
Gebucht = Termine (Zeitplan) + eingeplante Arbeitsgänge der Produktion (Plan-Stunden gleich auf die Werktage verteilt –
das ist neu gegenüber der Excel), Rest = Soll − Abwesenheit − Gebucht."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from mitarbeiter.models import Mitarbeiter

from .models import Abwesenheit, Termin

NULL = Decimal("0")
STATUS_PLANUNG = {"🟢 verfügbar": "einplanbar", "🟡 knapp": "nur kurze Aufgabe"}


def _dauer(t) -> Decimal:
    if not t.beginn or not t.ende:
        return NULL
    a, b = datetime.combine(date.today(), t.beginn), datetime.combine(date.today(), t.ende)
    return Decimal(max(0, (b - a).seconds) / 3600).quantize(Decimal("0.01"))


def _werktage(von, bis):
    from zeiten.feiertage import feiertag
    d, tage = von, []
    while d <= bis:
        if d.weekday() < 5 and not feiertag(d):
            tage.append(d)
        d += timedelta(days=1)
    return tage


def werkstatt_stunden(ma, tag) -> tuple[Decimal, list]:
    """Plan-Stunden offener Arbeitsgänge des Mitarbeiters an diesem Tag (gleich auf die Werktage verteilt)."""
    from produktion.models import Arbeitsgang
    summe, liste = NULL, []
    for ag in Arbeitsgang.objects.filter(mitarbeiter=ma, plan_start__lte=tag).exclude(status="Fertig") \
            .select_related("projekt"):
        bis = ag.plan_ende or ag.plan_start
        if bis < tag:
            continue
        tage = _werktage(ag.plan_start, bis)
        if tag not in tage or not ag.plan_std:
            continue
        anteil = (ag.plan_std / len(tage)).quantize(Decimal("0.01"))
        summe += anteil
        liste.append({"text": f"{ag.projekt.projektnr}: {ag.name}", "stunden": anteil})
    return summe, liste


def konflikte(termine) -> set:
    """Wie Zeitplan Spalte M: überlappende Termine desselben Mitarbeiters am selben Tag."""
    mit_zeit = [t for t in termine if t.beginn and t.ende]
    hit = set()
    for i, a in enumerate(mit_zeit):
        for b in mit_zeit[i + 1:]:
            if a.beginn < b.ende and b.beginn < a.ende:
                hit |= {a.pk, b.pk}
    return hit


def tag(ma, tag: date, termine=None) -> dict:
    """Wie Einsatzplanung O–V für einen Mitarbeiter."""
    from zeiten.dienst import soll_tag
    soll = soll_tag(ma, tag) if ma.aktiv else NULL
    abw = (ma.abwesenheiten.filter(status=Abwesenheit.Status.FREIGEGEBEN, von__lte=tag, bis__gte=tag).first())
    blockiert = bool(abw and abw.ganztags)
    abw_h = soll if blockiert else (min(abw.stunden, soll) if abw else NULL)
    if termine is None:
        termine = list(Termin.objects.filter(mitarbeiter=ma, datum=tag, abgesagt=False).select_related("projekt"))
    termine_h = sum((_dauer(t) for t in termine), NULL)
    werkstatt_h, werkstatt = werkstatt_stunden(ma, tag)
    gebucht = termine_h + werkstatt_h
    rest = max(NULL, soll - abw_h - gebucht)
    k = konflikte(termine)
    if blockiert:
        status = "🔴 abwesend"
    elif soll == 0:
        status = "⚪ keine Sollzeit"
    elif gebucht > soll - abw_h:
        status = "🔴 überplant"
    elif rest < 2:
        status = "🟡 knapp"
    else:
        status = "🟢 verfügbar"
    return {"ma": ma, "datum": tag, "soll": soll, "abwesenheit": abw.art if abw else "", "abw_h": abw_h,
            "termine": termine, "termine_h": termine_h, "werkstatt": werkstatt, "werkstatt_h": werkstatt_h,
            "gebucht": gebucht, "rest": rest, "status": status, "planung": STATUS_PLANUNG.get(status, "nicht einplanen"),
            "konflikte": len(k) // 2 if k else 0, "konflikt_ids": k,
            "auslastung": int((gebucht + abw_h) / soll * 100) if soll else None}


def tag_alle(datum: date) -> dict:
    zeilen = [tag(ma, datum) for ma in Mitarbeiter.objects.filter(aktiv=True).order_by("name")]
    soll = sum((z["soll"] for z in zeilen), NULL)
    gebucht = sum((z["gebucht"] for z in zeilen), NULL)
    abw = sum((z["abw_h"] for z in zeilen), NULL)
    return {"zeilen": zeilen, "aktiv": len(zeilen), "verfuegbar": sum(z["status"] == "🟢 verfügbar" for z in zeilen),
            "abwesend": sum(z["status"] == "🔴 abwesend" for z in zeilen),
            "ueberplant": sum(z["status"] == "🔴 überplant" for z in zeilen), "soll": soll, "gebucht": gebucht,
            "rest": sum((z["rest"] for z in zeilen), NULL), "konflikte": sum(z["konflikte"] for z in zeilen),
            "auslastung": int((gebucht + abw) / soll * 100) if soll else None}


def woche(mo: date) -> list[dict]:
    """Rest-Stunden je Mitarbeiter Mo–Fr (Wochenübersicht)."""
    tage = [mo + timedelta(days=i) for i in range(5)]
    return [{"ma": ma, "tage": [tag(ma, d) for d in tage]}
            for ma in Mitarbeiter.objects.filter(aktiv=True).order_by("name")]


def h(x) -> str:
    return f"{float(x):g}".replace(".", ",")


def warnung_fuer(ma, datum, zusatz_h=NULL, ohne_projekt=None) -> str:
    """Kurzer Hinweis für Planungs-Dialoge (Termin, Montage, Einplanen). ohne_projekt: Montage-Termine dieses
    Projekts nicht mitzählen (beim Umplanen)."""
    termine = Termin.objects.filter(mitarbeiter=ma, datum=datum, abgesagt=False)
    if ohne_projekt is not None:
        termine = termine.exclude(projekt=ohne_projekt, aus_montage=True)
    k = tag(ma, datum, termine=list(termine))
    if k["status"] == "🔴 abwesend":
        return f"{ma.name} ist am {datum:%d.%m.} abwesend ({k['abwesenheit']})."
    if k["soll"] == 0:
        return f"{ma.name} hat am {datum:%d.%m.} keine Sollzeit."
    if k["gebucht"] + zusatz_h > k["soll"] - k["abw_h"]:
        return (f"{ma.name} ist am {datum:%d.%m.} überplant ({h(k['gebucht'] + zusatz_h)} h gebucht bei "
                f"{h(k['soll'] - k['abw_h'])} h Soll).")
    if k["konflikte"]:
        return f"{ma.name} hat am {datum:%d.%m.} überschneidende Termine."
    return ""
