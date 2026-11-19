"""Auswertungen für den Chef – nach Cockpit, Finanz-Cockpit, Dashboards und Blatt „Kalkulationsvergleich“.
Nur lesen, nichts ändern."""
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

NULL = Decimal("0")
MONATE_KURZ = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _rechnungen():
    from rechnungen.models import Rechnung
    return Rechnung.objects.filter(festgeschrieben_am__isnull=False, datum__isnull=False).select_related("projekt")


def _eingang():
    from rechnungen.models import Eingangsrechnung
    return Eingangsrechnung.objects.filter(storniert_am__isnull=True)


def _buchungen():
    from zeiten.models import Zeitbuchung
    return Zeitbuchung.objects.filter(storniert_am__isnull=True)


def prozent(teil, ganz):
    return (Decimal(teil) / Decimal(ganz) * 100).quantize(Decimal("0.1")) if ganz else None


# ------------------------------------------------------------------ Jahr und Monate
def jahr(jahr: int, heute=None) -> dict:
    heute = heute or timezone.localdate()
    rechnungen = list(_rechnungen().filter(datum__year__in=[jahr, jahr - 1]))
    eingang = list(_eingang().filter(datum__year=jahr))
    buchungen = list(_buchungen().filter(datum__year=jahr))
    monate = []
    for m in range(1, 13):
        umsatz = sum((r.netto for r in rechnungen if r.datum.year == jahr and r.datum.month == m), NULL)
        er = sum((e.netto for e in eingang if e.datum.month == m), NULL)
        lohn = sum((b.kosten for b in buchungen if b.datum.month == m), NULL)
        monate.append({"name": MONATE_KURZ[m - 1], "monat": m, "umsatz": umsatz, "eingang": er, "lohn": lohn,
                       "ergebnis": umsatz - er - lohn, "zukunft": dt.date(jahr, m, 1) > heute})
    spitze = max([max(x["umsatz"], x["eingang"] + x["lohn"]) for x in monate] + [Decimal("1")])
    for x in monate:
        x["h_umsatz"] = int(x["umsatz"] / spitze * 100)
        x["h_kosten"] = int((x["eingang"] + x["lohn"]) / spitze * 100)
    stichtag = heute if heute.year == jahr else dt.date(jahr, 12, 31)
    try:
        vj_tag = stichtag.replace(year=jahr - 1)
    except ValueError:  # 29. Februar
        vj_tag = stichtag.replace(year=jahr - 1, day=28)
    umsatz = sum((x["umsatz"] for x in monate), NULL)
    vorjahr = sum((r.netto for r in rechnungen if r.datum.year == jahr - 1 and r.datum <= vj_tag), NULL)
    er = sum((x["eingang"] for x in monate), NULL)
    lohn = sum((x["lohn"] for x in monate), NULL)
    stunden = sum((b.stunden for b in buchungen), NULL)
    produktiv = sum((b.stunden for b in buchungen if b.projekt_id), NULL)
    return {"jahr": jahr, "monate": monate, "umsatz": umsatz, "vorjahr": vorjahr, "vj_tag": vj_tag,
            "wachstum": prozent(umsatz - vorjahr, vorjahr), "eingang": er, "lohn": lohn,
            "ergebnis": umsatz - er - lohn, "marge": prozent(umsatz - er - lohn, umsatz),
            "stunden": stunden, "produktiv": prozent(produktiv, stunden)}


# ------------------------------------------------------------------ Nachkalkulation (Kalkulationsvergleich)
def _ist_teile(projekt) -> dict:
    """Ist-Kosten nach Kostenart: Material (Entnahmen + Eingang Material), Fremd, Sonstiges, Lohn."""
    from kalkulation.models import Stuecklistenposition
    from rechnungen.models import KATEGORIEN
    from zeiten.dienst import lohn_ist
    entnahmen = sum((p.gesamt for p in projekt.stueckliste.all() if p.status == Stuecklistenposition.Status.ENTNOMMEN), NULL)
    er = defaultdict(lambda: NULL)
    for e in _eingang().filter(projekt=projekt):
        er[e.kategorie] += e.netto
    material = entnahmen + er.pop(KATEGORIEN[0], NULL)
    fremd = er.pop("Fremdleistung", NULL)
    sonst = sum(er.values(), NULL)
    lohn = lohn_ist(projekt)
    return {"material": material, "fremd": fremd, "sonstiges": sonst, "lohn": lohn,
            "gesamt": material + fremd + sonst + lohn}


def _ist_stunden(projekt) -> Decimal:
    """Ist-Stunden: Ist-Stunden der Arbeitsgänge + Buchungen ohne Arbeitsgang."""
    ag = projekt.arbeitsgaenge.aggregate(s=Sum("ist_std"))["s"] or NULL
    frei = _buchungen().filter(projekt=projekt, arbeitsgang__isnull=True).aggregate(s=Sum("stunden"))["s"] or NULL
    return ag + frei


def projekt_vergleich(projekt) -> dict:
    """Wie Blatt „Kalkulationsvergleich“: Kalkulation gegen Ist je Kostenart, Angebot, Erlös, Marge."""
    from kalkulation.models import Auftrag, Kalkulation
    k = Kalkulation.objects.filter(projekt=projekt).first()
    a = Auftrag.objects.filter(projekt=projekt).first()
    ist = _ist_teile(projekt)
    plan = {"material": k.material + k.beschlaege if k else None, "fremd": k.fremd if k else None,
            "sonstiges": k.maschinen + k.montage + k.fahrt if k else None, "lohn": k.lohnkosten if k else None,
            "gesamt": k.kosten if k else None}
    zeilen = []
    for key, name in (("material", "Material + Beschläge"), ("lohn", "Lohn"), ("fremd", "Fremdleistungen"),
                      ("sonstiges", "Maschine, Montage, Fahrt, Sonstiges"), ("gesamt", "Gesamtkosten")):
        p, i = plan[key], ist[key]
        zeilen.append({"name": name, "plan": p, "ist": i, "diff": (i - p) if p is not None else None,
                       "prozent": prozent(i - p, p) if p else None, "summe": key == "gesamt"})
    erloes = sum((r.netto for r in _rechnungen().filter(projekt=projekt)), NULL)
    angebot = a.angebot_netto if a else None
    soll_std = k.lohn_std if k else None
    ist_std = _ist_stunden(projekt)
    return {"projekt": projekt, "k": k, "a": a, "zeilen": zeilen, "plan": plan, "ist": ist, "erloes": erloes,
            "angebot": angebot, "marge_plan": prozent(angebot - plan["gesamt"], angebot) if angebot and k else None,
            "db": erloes - ist["gesamt"], "marge_ist": prozent(erloes - ist["gesamt"], erloes),
            "soll_std": soll_std, "ist_std": ist_std,
            "std_prozent": prozent(ist_std - soll_std, soll_std) if soll_std else None,
            "verbraucht": prozent(ist["gesamt"], plan["gesamt"]) if k and plan["gesamt"] else None}


def nachkalkulation(nur_offene=True) -> list[dict]:
    from projekte.models import ABGESCHLOSSEN, Projekt
    liste = []
    for p in Projekt.objects.select_related("kunde").order_by("-projektnr"):
        hat = (hasattr(p, "kalkulation") or hasattr(p, "auftrag") or p.zeitbuchungen.exists()
               or p.arbeitsgaenge.exists() or _eingang().filter(projekt=p).exists() or _rechnungen().filter(projekt=p).exists())
        if not hat or (nur_offene and p.status.strip().lower() in ABGESCHLOSSEN):
            continue
        v = projekt_vergleich(p)
        v["ampel"] = ("rot" if v["verbraucht"] and v["verbraucht"] > 100 else
                      "gelb" if v["verbraucht"] and v["verbraucht"] > 85 else "gruen")
        liste.append(v)
    return liste


# ------------------------------------------------------------------ Stunden, Werkstatt, Material
def stunden(jahr: int, monat: int) -> list[dict]:
    from mitarbeiter.models import Mitarbeiter
    from zeiten import dienst as zeiten
    zeilen = []
    for ma in Mitarbeiter.objects.filter(aktiv=True).order_by("name"):
        bs = list(_buchungen().filter(mitarbeiter=ma, datum__year=jahr, datum__month=monat))
        m = zeiten.monat(ma, jahr, monat)
        ist = sum((b.stunden for b in bs), NULL)
        je = defaultdict(lambda: NULL)
        for b in bs:
            je[b.get_taetigkeit_display()] += b.stunden
        produktiv = sum((b.stunden for b in bs if b.projekt_id), NULL)
        zeilen.append({"ma": ma, "soll": m["summe"]["soll"], "ist": ist, "produktiv": prozent(produktiv, ist),
                       "auslastung": prozent(ist + m["summe"]["gutschrift"], m["summe"]["soll"]),
                       "je": sorted(je.items(), key=lambda x: -x[1]), "kosten": sum((b.kosten for b in bs), NULL)})
    return zeilen


def werkstatt(heute=None) -> dict:
    from planung.models import Montage
    from produktion import dienst as produktion
    from produktion.models import Arbeitsgang
    from projekte.models import Projekt
    heute = heute or timezone.localdate()
    phasen = [0] * 5
    erster_durchlauf = gepruefte = 0
    for p in Projekt.objects.filter(arbeitsgaenge__isnull=False).distinct():
        phasen[produktion.phase(p)] += 1
        erste = p.qm_pruefungen.order_by("datum", "pk").first()
        if erste:
            gepruefte += 1
            erster_durchlauf += erste.ergebnis == "Bestanden"
    ueberfaellig = list(Arbeitsgang.objects.exclude(status="Fertig").filter(plan_ende__lt=heute)
                        .select_related("projekt", "mitarbeiter").order_by("plan_ende")[:15])
    montagen = list(Montage.objects.filter(datum__range=(heute, heute + dt.timedelta(days=14)))
                    .select_related("projekt", "team").order_by("datum"))
    return {"phasen": list(zip(produktion.SCHRITTE, phasen)), "ueberfaellig": ueberfaellig,
            "ueberfaellig_anzahl": Arbeitsgang.objects.exclude(status="Fertig").filter(plan_ende__lt=heute).count(),
            "montagen": montagen, "qm_quote": prozent(erster_durchlauf, gepruefte), "qm_projekte": gepruefte}


def material() -> dict:
    from lager.models import Bestellung, bestand
    from material.models import Material
    wert, unter = NULL, []
    for m in Material.objects.filter(aktiv=True, lagerartikel=True):
        b = bestand(m)
        if b > 0 and m.ek_netto:
            wert += (b * m.ek_netto).quantize(Decimal("0.01"))
        if m.mindestbestand and b < m.mindestbestand:
            unter.append({"m": m, "bestand": b})
    offen = [b for b in Bestellung.objects.filter(abgeschlossen=False) if b.rest_offen > 0]
    return {"lagerwert": wert, "unter": unter[:15], "unter_anzahl": len(unter),
            "bestellungen": len(offen), "bestellwert": sum((b.bestellwert for b in offen), NULL)}
