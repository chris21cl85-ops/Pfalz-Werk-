"""Abläufe: Bestellvorschläge, Bestellen, Wareneingang, Einlagern, Korrektur."""
import datetime as dt
from decimal import ROUND_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from kern.models import protokolliere
from material.models import Material

from .models import NULL, Bestellung, Lagerbewegung, Wareneingang, bestand


class LagerFehler(Exception):
    """Fachlicher Grund, warum etwas nicht geht – Text für den Benutzer."""


def zahl(x) -> str:
    """1234.500 -> „1.234,5“ (wie Zahl() im Makro)."""
    d = Decimal(x).normalize()
    ganz, _, komma = f"{d:f}".partition(".")
    vz = "-" if ganz.startswith("-") else ""
    ganz = f"{int(ganz.lstrip('-') or 0):,}".replace(",", ".")
    return f"{vz}{ganz},{komma}" if komma else f"{vz}{ganz}"


def naechste_bnr() -> str:
    hoechste = 0
    for nr in Bestellung.objects.values_list("bnr", flat=True):
        try:
            hoechste = max(hoechste, int(nr.split("-")[-1]))
        except ValueError:
            pass
    return f"B-{hoechste + 1:04d}"


def offene_menge(material) -> Decimal:
    """Bestellt, aber noch nicht geliefert (wie Spalte AA „Offene Bestellung“)."""
    return sum((b.rest_offen for b in material.bestellungen.filter(abgeschlossen=False)
                .prefetch_related("wareneingaenge")), NULL)


def zielmenge(material) -> Decimal:
    """Wie Ziel() im Makro: Zielbestand, mindestens aber der Mindestbestand."""
    ziel = Decimal(material.zielbestand or 0)
    mindest = Decimal(material.mindestbestand or 0)
    return max(ziel, mindest)


def vorschlaege() -> list[dict]:
    """Bestellvorschläge: Lagerartikel, bei denen Bestand + offene Bestellungen unter dem Mindestbestand liegen.
    Vorschlag = Ziel − Bestand − offen (wie Alles() im Makro), auf ganze Einheiten aufgerundet."""
    ergebnis = []
    bestaende = dict(Lagerbewegung.objects.values_list("material").annotate(s=Sum("menge")).values_list("material", "s"))
    for m in Material.objects.filter(aktiv=True, lagerartikel=True, mindestbestand__gt=0).select_related("lieferant"):
        ist = bestaende.get(m.pk) or NULL
        offen = offene_menge(m)
        if ist + offen >= Decimal(m.mindestbestand):
            continue
        menge = (zielmenge(m) - ist - offen).quantize(Decimal("1"), rounding=ROUND_UP)
        if menge <= 0:
            continue
        ergebnis.append({"material": m, "bestand": ist, "offen": offen, "mindest": m.mindestbestand,
                         "ziel": zielmenge(m), "menge": menge, "lieferant": m.lieferant,
                         "wert": (menge * Decimal(m.ek_netto)).quantize(Decimal("0.01")) if m.ek_netto else None})
    return sorted(ergebnis, key=lambda v: (v["lieferant"].name if v["lieferant"] else "", v["material"].bezeichnung))


@transaction.atomic
def bestellen(*, material, menge, benutzer, art=Bestellung.Art.MANUELL, projekt=None, erwartet_am=None,
              grund="", notiz="", datum=None) -> Bestellung:
    menge = Decimal(menge)
    if menge <= 0:
        raise LagerFehler("Bitte eine Bestellmenge größer 0 eintragen.")
    if material.lieferant is None:  # wie LiefFehlt() im Makro
        raise LagerFehler(f"{material.bezeichnung}: kein Lieferant im Materialstamm – erst beim Material eintragen.")
    datum = datum or timezone.localdate()
    if erwartet_am is None and material.lieferzeit_tage:
        erwartet_am = datum + dt.timedelta(days=material.lieferzeit_tage)
    b = Bestellung.objects.create(
        bnr=naechste_bnr(), material=material, lieferant=material.lieferant, projekt=projekt, menge=menge,
        einheit=material.einheit, art=art, grund=grund, bestellt_am=datum, erwartet_am=erwartet_am, notiz=notiz,
        freigegeben_von="Automatik" if art == Bestellung.Art.AUTOMATISCH else benutzer.get_username(),
        erfasst_von=benutzer)
    protokolliere("bestellung_angelegt", b.bnr, benutzer=benutzer, details=(
        f"{zahl(menge)} {b.einheit} {material.bezeichnung} bei {b.lieferant.name} · {b.get_art_display()}"
        + (f" · Projekt {projekt.projektnr}" if projekt else "") + (f" · {grund}" if grund else "")))
    return b


def alle_vorschlaege_bestellen(benutzer) -> tuple[list[Bestellung], list[str]]:
    """Wie PW_Best_AlleAuto: alle Vorschläge mit Lieferant als „Automatisch“ bestellen."""
    erledigt, uebersprungen = [], []
    for v in vorschlaege():
        try:
            erledigt.append(bestellen(material=v["material"], menge=v["menge"], benutzer=benutzer,
                                      art=Bestellung.Art.AUTOMATISCH, grund="unter Mindestbestand"))
        except LagerFehler as fehler:
            uebersprungen.append(str(fehler))
    return erledigt, uebersprungen


ALLES, TEIL, NICHTS = "alles", "teil", "nichts"


def wareneingang(bestellung, *, was, benutzer, menge=None, einlagern=True, datum=None, termin=None,
                 mehr_bestaetigt=False, notiz="") -> str:
    """Wie PW_WE_Aktion: Was ist angekommen? (alles / Teillieferung / noch nichts) → gleich einlagern?"""
    with transaction.atomic():
        b = Bestellung.objects.select_for_update().get(pk=bestellung.pk)
        if b.abgeschlossen:
            raise LagerFehler(f"{b.bnr} ist abgeschlossen.")
        heute = timezone.localdate()
        datum = datum or heute
        if was == NICHTS:
            if termin is None:
                raise LagerFehler("Bitte den neuen Liefertermin eintragen.")
            alt = b.erwartet_am
            b.erwartet_am = termin
            b.save(update_fields=["erwartet_am"])
            protokolliere("bestellung_termin", b.bnr, benutzer=benutzer,
                          details=f"Liefertermin {alt:%d.%m.%Y} → {termin:%d.%m.%Y}" if alt else f"Liefertermin {termin:%d.%m.%Y}")
            return f"Liefertermin für {b.bnr} auf {termin:%d.%m.%Y} gesetzt."
        if was == ALLES:
            menge = b.rest_offen
        elif was == TEIL:
            menge = Decimal(menge or 0)
        else:
            raise LagerFehler("Bitte wählen, was angekommen ist.")
        if menge <= 0:
            raise LagerFehler("Bitte die gelieferte Menge eintragen.")
        if datum > heute:
            raise LagerFehler("Das Datum liegt in der Zukunft.")
        if menge > b.rest_offen and not mehr_bestaetigt:
            raise LagerFehler(f"Es werden {zahl(menge)} {b.einheit} gebucht, offen sind nur {zahl(b.rest_offen)} "
                              f"{b.einheit}. Bitte bestätigen, dass mehr geliefert wurde.")
        Wareneingang.objects.create(bestellung=b, datum=datum, menge=menge, notiz=notiz, erfasst_von=benutzer)
        text = f"{b.bnr}: +{zahl(menge)} {b.einheit} geliefert"
        if einlagern:
            einlagern_buchen(b, benutzer, datum)
            text += " und eingelagert"
        protokolliere("wareneingang", b.bnr, benutzer=benutzer, details=text + (f" · {notiz}" if notiz else ""))
        return text + "."


def einlagern_buchen(bestellung, benutzer, datum=None) -> Decimal:
    """Bucht alles Gelieferte, was noch nicht im Lager ist, als Lagerzugang (wie Lager V/U im Makro)."""
    b = Bestellung.objects.get(pk=bestellung.pk)
    menge = b.zu_lagern
    if menge <= 0:
        raise LagerFehler("Es gibt nichts einzulagern.")
    Lagerbewegung.objects.create(material=b.material, datum=datum or timezone.localdate(), art=Lagerbewegung.Art.WARENEINGANG,
                                 menge=menge, bestellung=b, projekt=b.projekt, erfasst_von=benutzer,
                                 notiz=f"{b.bnr} {b.lieferant.name}")
    return menge


def einlagern(bestellung, benutzer) -> str:
    with transaction.atomic():
        menge = einlagern_buchen(bestellung, benutzer)
        protokolliere("einlagerung", bestellung.bnr, benutzer=benutzer, details=f"{zahl(menge)} {bestellung.einheit}")
    return f"{bestellung.bnr}: {zahl(menge)} {bestellung.einheit} eingelagert."


def abschliessen(bestellung, benutzer, grund) -> str:
    """Rest kommt nicht mehr (z. B. Lieferant kann nicht liefern) – Bestellung wird abgeschlossen."""
    if not grund.strip():
        raise LagerFehler("Bitte kurz den Grund angeben.")
    b = Bestellung.objects.get(pk=bestellung.pk)
    if b.abgeschlossen:
        raise LagerFehler(f"{b.bnr} ist schon abgeschlossen.")
    b.abgeschlossen = True
    b.save(update_fields=["abgeschlossen"])
    protokolliere("bestellung_abgeschlossen", b.bnr, benutzer=benutzer,
                  details=f"Rest offen {zahl(b.rest_offen)} {b.einheit} · Grund: {grund.strip()}")
    return f"{b.bnr} abgeschlossen."


def korrektur(material, *, neuer_bestand, benutzer, grund) -> Lagerbewegung | None:
    """Bestand auf gezählten Wert setzen – als Korrekturbuchung (Differenz), nie durch Überschreiben."""
    if not grund.strip():
        raise LagerFehler("Bitte den Grund angeben (z. B. „gezählt“, „Bruch“).")
    neu = Decimal(neuer_bestand)
    if neu < 0:
        raise LagerFehler("Ein Bestand kann nicht negativ sein.")
    alt = bestand(material)
    diff = neu - alt
    if diff == 0:
        return None
    bew = Lagerbewegung.objects.create(material=material, datum=timezone.localdate(), art=Lagerbewegung.Art.KORREKTUR,
                                       menge=diff, notiz=grund.strip()[:300], erfasst_von=benutzer)
    protokolliere("lager_korrektur", material.materialnr, benutzer=benutzer,
                  details=f"{zahl(alt)} → {zahl(neu)} {material.einheit} ({'+' if diff > 0 else ''}{zahl(diff)}) · {grund.strip()}")
    return bew


def abgleich(bnr: str, netto) -> str:
    """Wie Abgleich() im Makro PW_Eingang: Eingangsrechnung gegen Bestellwert (Toleranz max. 0,50 € / 2 %)."""
    from rechnungen.dienst import euro
    if not bnr:
        return ""
    b = Bestellung.objects.filter(bnr__iexact=bnr.strip()).select_related("material").first()
    if b is None:
        return f"Bestellung {bnr} gibt es nicht im Programm"
    wert = b.bestellwert
    if wert == 0:
        return f"Bestellung {b.bnr}: kein Bestellwert (Einkaufspreis fehlt)"
    d = Decimal(netto) - wert
    if abs(d) <= max(Decimal("0.5"), wert * Decimal("0.02")):
        return f"✓ passt zur Bestellung ({euro(wert)})"
    return f"Abweichung {'+' if d > 0 else '−'}{euro(abs(d))} zur Bestellung ({euro(wert)})"
