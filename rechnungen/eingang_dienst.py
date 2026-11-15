"""Eingangsrechnungen – Abläufe wie Erfassen(), Bezahlen() und DoppelteNr() im Makro PW_Eingang."""
import datetime as dt
import re
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from kern.models import protokolliere
from lieferanten.models import Lieferant

from .dienst import RechnungFehler, euro, naechste_znr
from .models import Eingangsrechnung, Zahlung, runden

BELEG_TYPEN = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
BELEG_MAX = 15 * 1024 * 1024


def naechste_ernr() -> str:
    hoechste = 0
    for nr in Eingangsrechnung.objects.values_list("ernr", flat=True):
        try:
            hoechste = max(hoechste, int(nr.split("-")[-1]))
        except ValueError:
            pass
    return f"ER-{hoechste + 1:04d}"


def ist_doppelt(lieferant_name: str, lieferanten_nr: str) -> bool:
    """Gleicher Lieferant + gleiche Rechnungs-Nr. schon erfasst? (Groß-/Kleinschreibung egal, wie Makro)"""
    return Eingangsrechnung.objects.filter(lieferant__name__iexact=lieferant_name.strip(),
                                           lieferanten_nr__iexact=lieferanten_nr.strip(),
                                           storniert_am__isnull=True).exists()


def lieferanten_vorgaben(lieferant) -> dict:
    """Zahlungsziel und Skonto aus der Lieferantenkarte (Skonto steht dort als Text, z. B. „2 % bei 10 Tagen“)."""
    werte = {}
    if lieferant is None:
        return werte
    if lieferant.zahlungsziel_tage is not None:
        werte["ziel_tage"] = lieferant.zahlungsziel_tage
    treffer = re.search(r"(\d+(?:[.,]\d+)?)\s*%.*?(\d+)\s*Tag", lieferant.skonto or "", re.I)
    if treffer:
        werte["skonto_prozent"] = Decimal(treffer[1].replace(",", "."))
        werte["skonto_tage"] = int(treffer[2])
    return werte


def beleg_pruefen(datei):
    if datei is None:
        return
    endung = "." + datei.name.rsplit(".", 1)[-1].lower() if "." in datei.name else ""
    if endung not in BELEG_TYPEN:
        raise RechnungFehler("Als Beleg bitte eine PDF-Datei oder ein Foto (JPG, PNG) wählen.")
    if datei.size > BELEG_MAX:
        raise RechnungFehler("Der Beleg ist zu groß (höchstens 15 MB).")


@transaction.atomic
def erfassen(*, lieferant_name, lieferanten_nr, datum, kategorie, projekt, netto, ust_satz, ziel_tage,
             skonto_prozent, skonto_tage, benutzer, bestellung="", notiz="", beleg=None) -> Eingangsrechnung:
    lieferant_name, lieferanten_nr = lieferant_name.strip(), lieferanten_nr.strip()
    if not lieferant_name:
        raise RechnungFehler("Lieferant eintragen oder wählen.")
    if not lieferanten_nr:
        raise RechnungFehler("Rechnungsnummer des Lieferanten eintragen.")
    if not netto:
        raise RechnungFehler("Nettobetrag eintragen.")
    if ist_doppelt(lieferant_name, lieferanten_nr):
        raise RechnungFehler("Diese Rechnung dieses Lieferanten ist schon erfasst.")
    beleg_pruefen(beleg)
    lieferant = Lieferant.objects.filter(name__iexact=lieferant_name).first()
    if lieferant is None:  # neuer Lieferant wird angelegt (wie Freitext im Makro)
        lieferant = Lieferant.objects.create(name=lieferant_name)
        protokolliere("lieferant_angelegt", lieferant, details="beim Erfassen einer Eingangsrechnung", benutzer=benutzer)
    netto = runden(netto)
    ust = runden(netto * Decimal(ust_satz) / 100)
    skonto_prozent = Decimal(skonto_prozent or 0)
    er = Eingangsrechnung(
        ernr=naechste_ernr(), lieferant=lieferant, lieferanten_nr=lieferanten_nr, datum=datum, kategorie=kategorie,
        projekt=projekt, bestellung=bestellung.strip(), netto=netto, ust_satz=Decimal(ust_satz), ust=ust,
        brutto=netto + ust, ziel_tage=ziel_tage, faellig=datum + dt.timedelta(days=ziel_tage),
        skonto_prozent=skonto_prozent,
        skonto_bis=datum + dt.timedelta(days=skonto_tage or 0) if skonto_prozent else None,
        notiz=notiz, erfasst_von=benutzer)
    if beleg is not None:
        er.beleg = beleg.read()
        er.beleg_name = beleg.name[-200:]
        er.beleg_typ = BELEG_TYPEN["." + beleg.name.rsplit(".", 1)[-1].lower()]
    er.save()
    protokolliere("eingangsrechnung_erfasst", er.ernr, benutzer=benutzer, details=(
        f"{lieferant.name} {lieferanten_nr} vom {datum:%d.%m.%Y} · netto {euro(netto)} + {ust_satz} % = {euro(er.brutto)}"
        f" · {kategorie} · {projekt.projektnr if projekt else 'Gemeinkosten'}"
        + (f" · Beleg {er.beleg_name}" if er.beleg_name else " · ohne Beleg")))
    return er


VOLL, SKONTO, TEIL = "voll", "skonto", "teil"


def bezahlen(er, *, art, datum, benutzer, betrag=None, konto="Bank", notiz="") -> Zahlung:
    """Zahlung an den Lieferanten (Richtung „Aus“) – mit Skonto, voll oder Teilbetrag."""
    with transaction.atomic():
        er = Eingangsrechnung.objects.select_for_update().get(pk=er.pk)
        if er.ist_storniert:
            raise RechnungFehler("Diese Erfassung ist storniert.")
        if datum > timezone.localdate():
            raise RechnungFehler("Das Zahlungsdatum liegt in der Zukunft.")
        offen = er.offen
        if offen <= Decimal("0.005"):
            raise RechnungFehler(f"{er.ernr} ist schon vollständig bezahlt.")
        skonto = Decimal("0.00")
        if art == VOLL:
            betrag = offen
        elif art == SKONTO:
            if not er.skonto_moeglich(datum):
                raise RechnungFehler("Skonto ist hier nicht möglich (keine Skonto-Angabe, Frist vorbei oder schon "
                                     "teilweise bezahlt) – bitte voll oder als Teilbetrag buchen.")
            betrag = runden(offen - er.skonto_betrag)
            skonto = runden(offen - betrag)
        elif art == TEIL:
            if betrag is None or Decimal(betrag) <= 0:
                raise RechnungFehler("Bitte den bezahlten Betrag eintragen.")
            betrag = runden(betrag)
        else:
            raise RechnungFehler("Unbekannte Zahlungsart.")
        z = Zahlung.objects.create(znr=naechste_znr(), eingangsrechnung=er, richtung="Aus", datum=datum,
                                   betrag=betrag, skonto=skonto, konto=konto, notiz=notiz, erfasst_von=benutzer)
        er = Eingangsrechnung.objects.get(pk=er.pk)
        protokolliere("zahlung_gebucht", er.ernr, benutzer=benutzer, details=(
            f"{z.znr} (Aus) am {datum:%d.%m.%Y}: {euro(betrag)}" + (f" · Skonto {euro(skonto)}" if skonto else "")
            + f" · {konto}" + (f" · {notiz}" if notiz else "") + f"\nDanach offen: {euro(er.offen)} ({er.status_text})"))
    return z


def erfassung_stornieren(er, *, benutzer, grund) -> Eingangsrechnung:
    """Falsch erfasst? Die Erfassung wird als storniert markiert (bleibt sichtbar), danach neu erfassen."""
    if not grund.strip():
        raise RechnungFehler("Bitte kurz den Grund angeben.")
    with transaction.atomic():
        er = Eingangsrechnung.objects.select_for_update().get(pk=er.pk)
        if er.ist_storniert:
            raise RechnungFehler(f"{er.ernr} ist schon storniert.")
        if er.bezahlt or er.skonto_gesamt:
            raise RechnungFehler("Auf diese Rechnung wurde schon gezahlt. Erst die Zahlungen per Gegenbuchung "
                                 "aufheben, dann stornieren.")
        er.storniert_am, er.storniert_von, er.storno_grund = timezone.now(), benutzer, grund.strip()[:200]
        er.save(update_fields=["storniert_am", "storniert_von", "storno_grund"])
        protokolliere("eingangsrechnung_storniert", er.ernr, benutzer=benutzer, details=f"Grund: {er.storno_grund}")
    return er
