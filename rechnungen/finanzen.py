"""Finanz-Übersicht und DATEV-Export – nach PW_FIN_Cockpit/CockpitBauen und PW_FIN_Export im Makro PW_Eingang.

DATEV: EXTF-Buchungsstapel (Format 700, Version 13), SKR03, Personenkonten wie im Makro
(Debitor = 10000 + Ziffern der Kunden-Nr., Kreditor = 70000 + Nummer des Lieferanten im Programm).
Gegenüber dem Makro verbessert: BU-Schlüssel für Aufwandskonten ohne Vorsteuer-Automatik,
Barzahlungen über Kasse 1000, Gegenbuchung stornierter Eingangsrechnungen.
"""
import calendar
import datetime as dt
import io
import re
import zipfile
from collections import defaultdict
from decimal import Decimal

from django.utils import timezone

from .models import Eingangsrechnung, Firmendaten, Rechnung, Zahlung

NULL = Decimal("0")


# ------------------------------------------------------------------ Finanz-Übersicht
def _monatsgrenzen(jahr, monat):
    return dt.date(jahr, monat, 1), dt.date(jahr, monat, calendar.monthrange(jahr, monat)[1])


def vormonat(heute=None):
    heute = heute or timezone.localdate()
    erster = heute.replace(day=1) - dt.timedelta(days=1)
    return erster.year, erster.month


def uebersicht(heute=None) -> dict:
    """Kennzahlen, Liquidität 6 Wochen, Deckungsbeitrag je Projekt, offene Posten (wie Finanz-Cockpit)."""
    heute = heute or timezone.localdate()
    rechnungen = list(Rechnung.objects.filter(festgeschrieben_am__isnull=False)
                      .select_related("kunde", "projekt").prefetch_related("zahlungen"))
    belege = list(Eingangsrechnung.objects.select_related("lieferant", "projekt").prefetch_related("zahlungen"))
    forderungen = sorted([r for r in rechnungen if r.offen > Decimal("0.005")], key=lambda r: r.faellig)
    verbindlichkeiten = sorted([e for e in belege if e.offen > Decimal("0.005")], key=lambda e: e.faellig)

    # USt-Zahllast Vormonat: USt der Ausgangsrechnungen − Vorsteuer der Eingangsrechnungen (nach Rechnungsdatum)
    vj, vm = vormonat(heute)
    von, bis = _monatsgrenzen(vj, vm)
    ust = sum((r.ust for r in rechnungen if von <= r.datum <= bis), NULL)
    vorsteuer = sum((e.ust for e in belege if von <= e.datum <= bis and not e.ist_storniert), NULL)

    # Liquidität: 6 Wochen ab Montag dieser Woche; Woche 1 enthält auch alles Überfällige (wie Makro)
    montag = heute - dt.timedelta(days=heute.weekday())
    wochen, kumuliert = [], NULL
    for i in range(6):
        start, ende = montag + dt.timedelta(days=7 * i), montag + dt.timedelta(days=7 * i + 7)
        def drin(f):
            return f < ende if i == 0 else start <= f < ende
        ein = sum((r.offen for r in forderungen if drin(r.faellig)), NULL)
        aus = sum((e.offen for e in verbindlichkeiten if drin(e.faellig)), NULL)
        kumuliert += ein - aus
        wochen.append({"start": start, "ein": ein, "aus": aus, "saldo": ein - aus, "kumuliert": kumuliert})

    # Deckungsbeitrag je Projekt: Erlös (Rechnungen netto, Storno negativ) − Kosten (Eingangsrechnungen netto)
    db = defaultdict(lambda: {"erloes": NULL, "kosten": NULL})
    for r in rechnungen:
        db[r.projekt]["erloes"] += r.netto
    for e in belege:
        if e.projekt and not e.ist_storniert:
            db[e.projekt]["kosten"] += e.netto
    projekte = sorted(({"projekt": p, **w, "db": w["erloes"] - w["kosten"]} for p, w in db.items()),
                      key=lambda x: x["projekt"].projektnr, reverse=True)

    return {
        "jahr": heute.year,
        "umsatz_jahr": sum((r.netto for r in rechnungen if r.datum.year == heute.year), NULL),
        "forderungen": forderungen, "forderungen_summe": sum((r.offen for r in forderungen), NULL),
        "forderungen_ueberfaellig": sum(1 for r in forderungen if r.ist_ueberfaellig),
        "verbindlichkeiten": verbindlichkeiten,
        "verbindlichkeiten_summe": sum((e.offen for e in verbindlichkeiten), NULL),
        "verbindlichkeiten_ueberfaellig": sum(1 for e in verbindlichkeiten if e.ist_ueberfaellig),
        "vormonat": dt.date(vj, vm, 1), "ust": ust, "vorsteuer": vorsteuer, "zahllast": ust - vorsteuer,
        "wochen": wochen, "projekte": projekte,
    }


# ------------------------------------------------------------------ DATEV
BANK, KASSE = "1200", "1000"


def debitor(kundennr: str) -> str:
    """Wie Debitor() im Makro: 10000 + Ziffern der Kunden-Nr. (K-007 → 10007)."""
    ziffern = "".join(z for z in kundennr if z.isdigit())
    return str(10000 + int(ziffern or 0))


def kreditor(lieferant) -> str:
    """70000 + Nummer des Lieferanten im Programm – bleibt dauerhaft gleich."""
    return str(70000 + lieferant.pk)


def erloeskonto(rechnung) -> str:
    """8400 Erlöse 19 % (Automatik), 8300 Erlöse 7 %, 8195 Kleinunternehmer – wie Makro."""
    if str(rechnung.firma.get("kleinunternehmer")).lower() in ("true", "ja", "1"):
        return "8195"
    return "8300" if Decimal(rechnung.ust_satz or 0) == 7 else "8400"


def sachkonto(kategorie: str, ust_satz) -> tuple[str, str]:
    """Kategorie → (Konto, BU-Schlüssel). 3400/3300 haben Vorsteuer-Automatik; die anderen Konten brauchen
    den BU-Schlüssel 9 (19 % Vorsteuer) bzw. 8 (7 %), sonst wird keine Vorsteuer gebucht."""
    satz = Decimal(ust_satz or 0)
    if kategorie.startswith("Material"):  # Wareneingang: 3400 (19 %), 3300 (7 %), 3200 (ohne Vorsteuer)
        return {Decimal(19): "3400", Decimal(7): "3300"}.get(satz, "3200"), ""
    konto = {"Fremd": "3100", "Fahrzeug": "4530", "Maschine": "4985", "Büro": "4930"}
    for anfang, k in konto.items():
        if kategorie.startswith(anfang):
            break
    else:
        k = "4900"
    return k, {Decimal(19): "9", Decimal(7): "8"}.get(satz, "")


def skontokonto(eingang: bool, ust_satz, kleinunternehmer=False) -> str:
    """Gewährte Skonti (Kunden): 8736 bei 19 %, 8731 bei 7 %, 8730 ohne USt.
    Erhaltene Skonti (Lieferanten): 3736 bei 19 %, 3731 bei 7 %, 3730 ohne Vorsteuer."""
    satz = Decimal(ust_satz or 0)
    grund = "873" if eingang else "373"
    if kleinunternehmer or satz == 0:
        return grund + "0"
    return grund + ("1" if satz == 7 else "6")


def _betrag(x) -> str:
    return f"{abs(Decimal(x)):.2f}".replace(".", ",")


def _text(s: str, laenge=60) -> str:
    return '"' + str(s).replace('"', "")[:laenge] + '"'


def buchungszeile(betrag, sh, konto, gegen, datum, beleg, text, bu="") -> str:
    """Wie zeile() im Makro; negative Beträge drehen Soll/Haben."""
    betrag = Decimal(betrag)
    if betrag < 0:
        sh = "H" if sh == "S" else "S"
    return ";".join([_betrag(betrag), _text(sh), _text("EUR"), "", "", "", konto, gegen, _text(bu) if bu else "",
                     f"{datum:%d%m}", _text(beleg, 36), "", "", _text(text)])


SPALTEN = ("Umsatz (ohne Soll/Haben-Kz);Soll/Haben-Kennzeichen;WKZ Umsatz;Kurs;Basis-Umsatz;WKZ Basis-Umsatz;"
           "Konto;Gegenkonto (ohne BU-Schlüssel);BU-Schlüssel;Belegdatum;Belegfeld 1;Belegfeld 2;Skonto;Buchungstext")


def wj_beginn(fd: Firmendaten, von: dt.date) -> dt.date:
    tag, monat = (int(x) for x in re.findall(r"\d+", fd.wj_beginn or "01.01.")[:2] or (1, 1))
    jahr = von.year if (von.month, von.day) >= (monat, tag) else von.year - 1
    return dt.date(jahr, monat, tag)


def buchungen(jahr: int, monat: int) -> tuple[list[dict], list[str]]:
    """Alle Buchungen des Monats als Liste (für Vorschau und Datei) und Warnungen."""
    von, bis = _monatsgrenzen(jahr, monat)
    zeilen, warnungen = [], []

    def neu(betrag, sh, konto, gegen, datum, beleg, text, bu="", art=""):
        zeilen.append({"betrag": Decimal(betrag), "sh": sh, "konto": konto, "gegen": gegen, "bu": bu,
                       "datum": datum, "beleg": beleg, "text": text, "art": art})

    for r in Rechnung.objects.filter(festgeschrieben_am__isnull=False, datum__range=(von, bis)).select_related("kunde"):
        neu(r.brutto, "S", debitor(r.kunde.kundennr), erloeskonto(r), r.datum, r.nummer, f"{r.art} {r.kunde.name}",
            art="Rechnung")
    for e in Eingangsrechnung.objects.select_related("lieferant").filter(
            datum__lte=bis).exclude(datum__lt=von, storniert_am__isnull=True):
        konto, bu = sachkonto(e.kategorie, e.ust_satz)
        storno_monat = e.ist_storniert and von <= timezone.localtime(e.storniert_am).date() <= bis
        im_monat = von <= e.datum <= bis
        if im_monat and storno_monat:
            continue  # im selben Monat erfasst und storniert → nichts zu buchen
        if im_monat:
            neu(e.brutto, "H", kreditor(e.lieferant), konto, e.datum, e.lieferanten_nr,
                f"{e.ernr} {e.lieferant.name}", bu, art="Eingangsrechnung")
        elif storno_monat:
            neu(-e.brutto, "H", kreditor(e.lieferant), konto, timezone.localtime(e.storniert_am).date(),
                e.lieferanten_nr, f"Storno {e.ernr} {e.lieferant.name}", bu, art="Storno Eingang")
    for z in Zahlung.objects.filter(datum__range=(von, bis)).select_related(
            "rechnung__kunde", "eingangsrechnung__lieferant"):
        geld = KASSE if z.konto == "Bar" else BANK
        if z.rechnung_id:
            r = z.rechnung
            neu(z.betrag, "S", geld, debitor(r.kunde.kundennr), z.datum, r.nummer, f"Zahlung {r.nummer}", art="Zahlung Ein")
            if z.skonto:
                klein = str(r.firma.get("kleinunternehmer")).lower() in ("true", "ja", "1")
                neu(z.skonto, "S", skontokonto(True, r.ust_satz, klein), debitor(r.kunde.kundennr), z.datum,
                    r.nummer, f"Skonto {r.nummer}", art="Skonto Ein")
        else:
            e = z.eingangsrechnung
            neu(z.betrag, "H", geld, kreditor(e.lieferant), z.datum, e.lieferanten_nr,
                f"Zahlung {e.ernr} {e.lieferant.name}", art="Zahlung Aus")
            if z.skonto:
                neu(z.skonto, "H", skontokonto(False, e.ust_satz), kreditor(e.lieferant), z.datum, e.lieferanten_nr,
                    f"Skonto {e.ernr}", art="Skonto Aus")

    # Doppelte Debitorennummern (z. B. „K-7“ und „7“) würden zwei Kunden auf ein Konto buchen
    from kunden.models import Kunde
    gesehen = {}
    for k in Kunde.objects.all():
        nr = debitor(k.kundennr)
        if nr in gesehen:
            warnungen.append(f"Kunden {gesehen[nr]} und {k.kundennr} bekommen beide das Debitorenkonto {nr}.")
        gesehen[nr] = k.kundennr
    zeilen.sort(key=lambda b: (b["datum"], b["beleg"]))
    for b in zeilen:  # so, wie es in der Datei steht: Betrag ohne Vorzeichen, Soll/Haben ggf. gedreht
        b["datei_betrag"] = abs(b["betrag"])
        b["datei_sh"] = ("H" if b["sh"] == "S" else "S") if b["betrag"] < 0 else b["sh"]
    return zeilen, warnungen


def kopfzeile(fd: Firmendaten, von: dt.date, bis: dt.date, jetzt=None) -> str:
    """EXTF-Kopf wie im Makro (Format 700, Kategorie 21 Buchungsstapel, Version 13)."""
    jetzt = jetzt or timezone.localtime()
    return (f'"EXTF";700;21;"Buchungsstapel";13;{jetzt:%Y%m%d%H%M%S}000;;"PW";"";"";{fd.datev_berater};'
            f'{fd.datev_mandant};{wj_beginn(fd, von):%Y%m%d};{fd.sachkontenlaenge or 4};{von:%Y%m%d};{bis:%Y%m%d};'
            f'"PFALZ-WERK {von:%m/%Y}";"";1;0;0;"EUR";;"";;;"";;;"";""')


def datev_zip(jahr: int, monat: int) -> tuple[bytes, dict]:
    """ZIP mit EXTF-Buchungsstapel, Offenen Posten, Personenkonten und allen Belegen des Monats."""
    fd = Firmendaten.laden()
    if not fd.datev_berater or not fd.datev_mandant:
        raise ValueError("Ohne Berater- und Mandantennummer kein Export. Bitte in den Firmendaten eintragen.")
    von, bis = _monatsgrenzen(jahr, monat)
    liste, warnungen = buchungen(jahr, monat)
    csv = "\r\n".join([kopfzeile(fd, von, bis), SPALTEN] + [
        buchungszeile(b["betrag"], b["sh"], b["konto"], b["gegen"], b["datum"], b["beleg"], b["text"], b["bu"])
        for b in liste]) + "\r\n"

    op = ["Art;Beleg;Partner;Datum;Fällig;Brutto;Offen;Status"]
    for r in Rechnung.objects.filter(festgeschrieben_am__isnull=False).select_related("kunde").prefetch_related("zahlungen"):
        if r.offen > Decimal("0.005"):
            op.append(f"Forderung;{r.nummer};{r.kunde.name};{r.datum:%d.%m.%Y};{r.faellig:%d.%m.%Y};"
                      f"{_betrag(r.brutto)};{_betrag(r.offen)};{r.status_text}")
    for e in Eingangsrechnung.objects.select_related("lieferant").prefetch_related("zahlungen"):
        if e.offen > Decimal("0.005"):
            op.append(f"Verbindlichkeit;{e.ernr} / {e.lieferanten_nr};{e.lieferant.name};{e.datum:%d.%m.%Y};"
                      f"{e.faellig:%d.%m.%Y};{_betrag(e.brutto)};{_betrag(e.offen)};{e.status_text}")

    from kunden.models import Kunde
    from lieferanten.models import Lieferant
    konten = ["Konto;Name"] + [f"{debitor(k.kundennr)};{k.name}" for k in Kunde.objects.order_by("kundennr")]
    konten += [f"{kreditor(l)};{l.name}" for l in Lieferant.objects.filter(eingangsrechnungen__isnull=False).distinct()]

    puffer, belege = io.BytesIO(), 0
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        # DATEV erwartet Windows-Zeichensatz (wie Print # im Makro)
        z.writestr(f"EXTF_Buchungsstapel_{von:%Y-%m}.csv", csv.encode("cp1252", errors="replace"))
        z.writestr(f"Offene_Posten_{timezone.localdate():%Y-%m-%d}.csv",
                   ("\r\n".join(op) + "\r\n").encode("cp1252", errors="replace"))
        z.writestr("Personenkonten.csv", ("\r\n".join(konten) + "\r\n").encode("cp1252", errors="replace"))
        for r in Rechnung.objects.filter(festgeschrieben_am__isnull=False, datum__range=(von, bis)):
            z.writestr(f"Belege/{r.nummer}.pdf", bytes(r.pdf))
            belege += 1
            if r.xml:
                z.writestr(f"Belege/{r.nummer}_XRechnung.xml", bytes(r.xml))
        for e in Eingangsrechnung.objects.filter(datum__range=(von, bis), beleg__isnull=False):
            z.writestr(f"Belege/{e.ernr}_{e.beleg_name}", bytes(e.beleg))
            belege += 1
    return puffer.getvalue(), {"buchungen": len(liste), "belege": belege, "warnungen": warnungen}
