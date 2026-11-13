"""Abläufe rund um Rechnungen: Entwurf anlegen, Nummer vergeben, festschreiben, verwerfen."""
import datetime as dt
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from kern.models import protokolliere

from .models import Firmendaten, Position, Rechnung, RechnungGesperrt, runden


class RechnungFehler(Exception):
    """Fachlicher Grund, warum etwas nicht geht – Text ist für den Benutzer gedacht."""


def euro(betrag) -> str:
    """1234.5 -> „1.234,50 €“."""
    text = f"{Decimal(betrag):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} €"


def nummer_bilden(fd: Firmendaten, zaehler: int, jahr: int) -> str:
    """Wie NaechsteNr() im Makro: Präfix + Jahr + „-“ + vierstellige laufende Nummer (z. B. RE-2026-0001)."""
    return f"{fd.rechnungs_praefix}{jahr}-{zaehler:04d}"


def naechste_nummer_vorschau() -> str:
    fd = Firmendaten.laden()
    return nummer_bilden(fd, fd.letzte_rechnungsnummer + 1, timezone.localdate().year)


def ziel_aus_firmendaten(fd: Firmendaten) -> str:
    """Vorbelegung des Zahlungsziels wie ZielKachel() im Makro."""
    if fd.zahlungsziel_tage == 0:
        return "0"
    if fd.zahlungsziel_tage == 30:
        return "30"
    return "14"


def abschlaege(projekt):
    """Festgeschriebene Abschlagsrechnungen eines Projekts (Storno folgt in eigenem Paket)."""
    return (projekt.rechnungen.filter(art=Rechnung.Art.ABSCHLAG, festgeschrieben_am__isnull=False)
            .exclude(storniert_durch__isnull=False).order_by("datum", "id"))  # stornierte zählen nicht (wie Makro)


def letzter_auftragswert(projekt):
    a = projekt.rechnungen.filter(auftragswert__isnull=False).exclude(status=Rechnung.Status.VERWORFEN)
    a = a.order_by("-angelegt_am").first()
    return a.auftragswert if a else None


def xrechnung_vorschlag(kunde) -> bool:
    """E-Rechnung für Firmen und Behörden vorschlagen, nicht für Privatkunden."""
    return "rivat" not in (kunde.kundenart or "")


@transaction.atomic
def entwurf_anlegen(*, projekt, art, benutzer, leistungszeitraum="", zahlungsziel="14",
                    auftragswert=None, abschlag_prozent=None, mit_xrechnung=None,
                    kaeufer_referenz="") -> Rechnung:
    """Legt einen Entwurf an und schlägt Positionen vor (Abschlag/Schluss wie Positionen() im Makro)."""
    if art in (Rechnung.Art.ABSCHLAG, Rechnung.Art.SCHLUSS) and not auftragswert:
        raise RechnungFehler("Für Abschlags- und Schlussrechnungen bitte den Auftragswert (netto) eintragen.")
    rechnung = Rechnung.objects.create(
        projekt=projekt, kunde=projekt.kunde, art=art, leistungszeitraum=leistungszeitraum,
        zahlungsziel=zahlungsziel, erstellt_von=benutzer, kaeufer_referenz=kaeufer_referenz,
        mit_xrechnung=xrechnung_vorschlag(projekt.kunde) if mit_xrechnung is None else mit_xrechnung,
        auftragswert=auftragswert if art != Rechnung.Art.RECHNUNG else None,
        abschlag_prozent=abschlag_prozent if art == Rechnung.Art.ABSCHLAG else None,
    )
    bezug = f"das Projekt {projekt.projektnr} ({projekt.name})"
    if art == Rechnung.Art.ABSCHLAG:
        prozent = Decimal(abschlag_prozent or 30)
        Position.objects.create(
            rechnung=rechnung, pos=1, menge=1, einheit="pausch.",
            text=f"{prozent.normalize():f} % Abschlag auf {bezug}, Auftragswert netto {euro(auftragswert)}",
            einzelpreis=runden(Decimal(auftragswert) * prozent / 100))
    elif art == Rechnung.Art.SCHLUSS:
        Position.objects.create(rechnung=rechnung, pos=1, menge=1, einheit="pausch.",
                                text=f"Leistungen gemäß Projekt {projekt.projektnr} ({projekt.name})",
                                einzelpreis=runden(auftragswert))
        for i, a in enumerate(abschlaege(projekt), start=2):
            Position.objects.create(rechnung=rechnung, pos=i, menge=-1, einheit="pausch.",
                                    text=f"abzgl. Abschlagsrechnung {a.nummer} vom {a.datum:%d.%m.%Y} (netto)",
                                    einzelpreis=a.netto)
    protokolliere("rechnung_entwurf", f"Entwurf {rechnung.pk}",
                  details=f"{rechnung.get_art_display()} für Projekt {projekt.projektnr}", benutzer=benutzer)
    return rechnung


def empfaenger_text(kunde) -> str:
    """Anschrift wie im Makro: Name, ggf. Ansprechpartner, Straße, PLZ Ort."""
    zeilen = [kunde.name]
    if kunde.ansprechpartner and kunde.ansprechpartner != kunde.name:
        zeilen.append(kunde.ansprechpartner)
    if kunde.strasse or kunde.plz or kunde.ort:
        zeilen += [kunde.strasse, f"{kunde.plz} {kunde.ort}".strip()]
    elif kunde.adresse_original:
        zeilen += kunde.adresse_original.replace(",", "\n").splitlines()
    return "\n".join(z.strip() for z in zeilen if z and z.strip())


def pruefen(rechnung) -> list[str]:
    """Was fehlt noch, bevor festgeschrieben werden darf? Leere Liste = alles in Ordnung."""
    fehlt = []
    if not rechnung.ist_entwurf:
        return ["Nur Entwürfe können festgeschrieben werden."]
    fd = Firmendaten.laden()
    if fd.fehlende_angaben():
        fehlt.append("In den Firmendaten fehlt noch: " + ", ".join(fd.fehlende_angaben()) + ".")
    positionen = list(rechnung.positionen.all())
    if not positionen:
        fehlt.append("Mindestens eine Position mit Text und Betrag eintragen.")
    for p in positionen:
        if not p.text.strip():
            fehlt.append(f"Position {p.pos} hat keine Beschreibung.")
        if p.gesamt == 0:
            fehlt.append(f"Position {p.pos} hat keinen Betrag.")
    if positionen and rechnung.summen(fd.effektiver_ust_satz)["brutto"] <= 0:
        fehlt.append("Der Rechnungsbetrag muss größer als 0 sein.")
    if not empfaenger_text(rechnung.kunde).count("\n"):
        fehlt.append(f"Beim Kunden {rechnung.kunde.kundennr} fehlt die Anschrift.")
    if rechnung.mit_xrechnung:
        from .xrechnung import fehlende_angaben
        fehlt += fehlende_angaben(rechnung, fd)
    return fehlt


def festschreiben(rechnung, benutzer, heute: dt.date | None = None) -> Rechnung:
    """Vergibt die Nummer, rechnet, erzeugt das PDF und sperrt die Rechnung. Alles oder nichts."""
    from .pdf import rechnung_pdf

    with transaction.atomic():
        rechnung = Rechnung.objects.select_for_update().get(pk=rechnung.pk)
        if rechnung.ist_festgeschrieben:
            raise RechnungGesperrt(f"Rechnung {rechnung.nummer} ist schon festgeschrieben.")
        fehlt = pruefen(rechnung)
        if fehlt:
            raise RechnungFehler(" ".join(fehlt))
        fd = Firmendaten.objects.select_for_update().get(pk=1)
        heute = heute or timezone.localdate()

        # Fortlaufende Nummer – Lücken und Doppelte ausgeschlossen
        zaehler = fd.letzte_rechnungsnummer + 1
        while Rechnung.objects.filter(nummer=nummer_bilden(fd, zaehler, heute.year)).exists():
            zaehler += 1
        fd.letzte_rechnungsnummer = zaehler
        fd.save()

        # Positionen lückenlos durchnummerieren
        for i, p in enumerate(rechnung.positionen.order_by("pos", "id"), start=1):
            if p.pos != i:
                p.pos = i
                p.save()

        summen = rechnung.summen(fd.effektiver_ust_satz)
        tage = {"0": 0, "14": 14, "30": 30, "14s": 14}[rechnung.zahlungsziel]
        rechnung.nummer = nummer_bilden(fd, zaehler, heute.year)
        rechnung.datum = heute
        rechnung.ziel_tage = tage
        rechnung.faellig = heute + dt.timedelta(days=tage)
        if rechnung.zahlungsziel == "14s":
            rechnung.skonto_prozent, rechnung.skonto_tage = Decimal("2.00"), 7
        rechnung.ust_satz, rechnung.netto = summen["ust_satz"], summen["netto"]
        rechnung.ust, rechnung.brutto = summen["ust"], summen["brutto"]
        if rechnung.art == Rechnung.Art.ABSCHLAG:
            rechnung.abschlag_nr = abschlaege(rechnung.projekt).count() + 1
        if not rechnung.leistungszeitraum:
            rechnung.leistungszeitraum = f"{heute:%d.%m.%Y}"
        rechnung.kundentyp = rechnung.kunde.kundenart
        rechnung.empfaenger = empfaenger_text(rechnung.kunde)
        rechnung.firma = fd.als_kopie()
        rechnung.status = Rechnung.Status.OFFEN
        rechnung.festgeschrieben_von = benutzer
        rechnung.pdf = rechnung_pdf(rechnung)
        if rechnung.mit_xrechnung:
            from .xrechnung import xrechnung_xml
            rechnung.xml = xrechnung_xml(rechnung)
        rechnung.pruefsumme = rechnung.berechne_pruefsumme()
        rechnung.festgeschrieben_am = timezone.now()
        rechnung.save()
        protokolliere("rechnung_festgeschrieben", rechnung.nummer, benutzer=benutzer, details=(
            f"{rechnung.titel} für {rechnung.kunde} · Projekt {rechnung.projekt.projektnr}\n"
            f"Netto {euro(rechnung.netto)} · USt {euro(rechnung.ust)} · Brutto {euro(rechnung.brutto)}\n"
            f"Fällig {rechnung.faellig:%d.%m.%Y} · {'mit' if rechnung.xml else 'ohne'} XRechnung"
            f" · Prüfsumme {rechnung.pruefsumme}"))
    return rechnung


def verwerfen(rechnung, benutzer) -> Rechnung:
    """Ein Entwurf wird nicht gelöscht, sondern als „Verworfen“ markiert (bekam nie eine Nummer)."""
    if not rechnung.ist_entwurf:
        raise RechnungFehler("Nur Entwürfe können verworfen werden.")
    rechnung.status = Rechnung.Status.VERWORFEN
    rechnung.save()
    protokolliere("rechnung_entwurf_verworfen", f"Entwurf {rechnung.pk}", benutzer=benutzer,
                  details=f"Projekt {rechnung.projekt.projektnr}")
    return rechnung


# ------------------------------------------------------------------ Zahlungen (wie ZahlungBuchen() im Makro)
VOLL, SKONTO, TEIL = "voll", "skonto", "teil"


def naechste_znr() -> str:
    """Z-0001, Z-0002 … fortlaufend (wie im Blatt „Zahlungen“)."""
    from .models import Zahlung
    hoechste = 0
    for znr in Zahlung.objects.values_list("znr", flat=True):
        try:
            hoechste = max(hoechste, int(znr.split("-")[-1]))
        except ValueError:
            pass
    return f"Z-{hoechste + 1:04d}"


def zahlung_buchen(rechnung, *, art, datum, benutzer, betrag=None, konto="Bank", notiz=""):
    """Bucht einen Zahlungseingang.

    art „voll“: der ganze offene Betrag. „skonto“: offen minus Skonto (Rest gilt als Skonto, Rechnung erledigt).
    „teil“: frei eingegebener Betrag, Rest bleibt offen.
    """
    from .models import Zahlung
    with transaction.atomic():
        rechnung = Rechnung.objects.select_for_update().get(pk=rechnung.pk)
        if not rechnung.ist_festgeschrieben:
            raise RechnungFehler("Zahlungen gibt es nur zu festgeschriebenen Rechnungen.")
        if datum > timezone.localdate():
            raise RechnungFehler("Das Zahlungsdatum liegt in der Zukunft.")
        offen = rechnung.offen
        if offen <= Decimal("0.005"):
            raise RechnungFehler(f"Rechnung {rechnung.nummer} ist schon vollständig bezahlt.")
        skonto = Decimal("0.00")
        if art == VOLL:
            betrag = offen
        elif art == SKONTO:
            if not rechnung.skonto_prozent:
                raise RechnungFehler("Auf dieser Rechnung wurde kein Skonto angeboten.")
            if datum > rechnung.skonto_bis:
                raise RechnungFehler(f"Die Zahlung vom {datum:%d.%m.%Y} liegt nach der Skonto-Frist "
                                     f"({rechnung.skonto_bis:%d.%m.%Y}) – bitte als Teilbetrag buchen.")
            betrag = runden(offen - rechnung.skonto_betrag)
            skonto = runden(offen - betrag)
        elif art == TEIL:
            if betrag is None or Decimal(betrag) <= 0:
                raise RechnungFehler("Bitte den eingegangenen Betrag eintragen.")
            betrag = runden(betrag)
        else:
            raise RechnungFehler("Unbekannte Zahlungsart.")
        zahlung = Zahlung.objects.create(
            znr=naechste_znr(), rechnung=rechnung, datum=datum, betrag=betrag, skonto=skonto,
            konto=konto, notiz=notiz, erfasst_von=benutzer)
        rechnung = Rechnung.objects.get(pk=rechnung.pk)
        protokolliere("zahlung_gebucht", rechnung.nummer, benutzer=benutzer, details=(
            f"{zahlung.znr} am {datum:%d.%m.%Y}: {euro(betrag)}"
            + (f" · Skonto {euro(skonto)}" if skonto else "") + f" · {konto}"
            + (f" · {notiz}" if notiz else "") + f"\nDanach offen: {euro(rechnung.offen)} ({rechnung.status_text})"))
    return zahlung


def zahlung_gegenbuchen(zahlung, *, benutzer, grund):
    """Macht eine falsch gebuchte Zahlung rückgängig – durch eine Gegenbuchung, nie durch Löschen."""
    from .models import Zahlung
    if not grund.strip():
        raise RechnungFehler("Bitte kurz den Grund angeben (z. B. „Betrag vertippt“).")
    with transaction.atomic():
        zahlung = Zahlung.objects.select_for_update().get(pk=zahlung.pk)
        if zahlung.gegenbuchung_zu_id:
            raise RechnungFehler("Eine Gegenbuchung kann nicht noch einmal gegengebucht werden.")
        if zahlung.ist_gegengebucht:
            raise RechnungFehler(f"{zahlung.znr} wurde schon gegengebucht.")
        gegen = Zahlung.objects.create(
            znr=naechste_znr(), rechnung=zahlung.rechnung, datum=timezone.localdate(), betrag=-zahlung.betrag,
            skonto=-zahlung.skonto, konto=zahlung.konto, notiz=f"Gegenbuchung zu {zahlung.znr}: {grund.strip()}",
            gegenbuchung_zu=zahlung, erfasst_von=benutzer)
        protokolliere("zahlung_gegengebucht", zahlung.rechnung.nummer, benutzer=benutzer,
                      details=f"{gegen.znr} hebt {zahlung.znr} auf ({euro(zahlung.betrag)}). Grund: {grund.strip()}")
    return gegen


# ------------------------------------------------------------------ Storno (wie Stornieren() im Makro)
def storno_moeglich(rechnung) -> str:
    """Leerer Text = Storno möglich, sonst der Grund, warum nicht (Regeln wie im Makro)."""
    if not rechnung.ist_festgeschrieben:
        return "Nur festgeschriebene Rechnungen können storniert werden."
    if rechnung.art == Rechnung.Art.STORNO:
        return "Eine Stornorechnung kann nicht storniert werden."
    if rechnung.ist_storniert:
        return f"Diese Rechnung wurde schon storniert ({rechnung.stornorechnung.nummer})."
    if rechnung.bezahlt != 0 or rechnung.skonto_gesamt != 0:
        return ("Auf diese Rechnung ist schon Geld eingegangen. Erst die Zahlungen per Gegenbuchung aufheben "
                "(bzw. das Geld zurücküberweisen), dann stornieren.")
    return ""


def stornieren(rechnung, benutzer, grund="") -> Rechnung:
    """Erzeugt eine Stornorechnung (eigene Nummer, alle Beträge negativ). Das Original bleibt unverändert und
    gilt danach als „Storniert“. Ein Storno lässt sich nicht zurücknehmen."""
    from .pdf import rechnung_pdf
    with transaction.atomic():
        alt = Rechnung.objects.select_for_update().get(pk=rechnung.pk)
        warum_nicht = storno_moeglich(alt)
        if warum_nicht:
            raise RechnungFehler(warum_nicht)
        fd = Firmendaten.objects.select_for_update().get(pk=1)
        heute = timezone.localdate()
        zaehler = fd.letzte_rechnungsnummer + 1
        while Rechnung.objects.filter(nummer=nummer_bilden(fd, zaehler, heute.year)).exists():
            zaehler += 1
        fd.letzte_rechnungsnummer = zaehler
        fd.save()
        storno = Rechnung.objects.create(
            nummer=None, art=Rechnung.Art.STORNO, storno_von=alt, projekt=alt.projekt, kunde=alt.kunde,
            leistungszeitraum=alt.leistungszeitraum, zahlungsziel="0", mit_xrechnung=bool(alt.xml),
            kaeufer_referenz=alt.kaeufer_referenz, erstellt_von=benutzer)
        for p in alt.positionen.order_by("pos", "id"):
            Position.objects.create(rechnung=storno, pos=p.pos, text=p.text, menge=-p.menge, einheit=p.einheit,
                                    einzelpreis=p.einzelpreis)
        storno.nummer = nummer_bilden(fd, zaehler, heute.year)
        storno.datum = storno.faellig = heute
        storno.ziel_tage = 0
        storno.ust_satz = alt.ust_satz
        storno.netto, storno.ust, storno.brutto = -alt.netto, -alt.ust, -alt.brutto
        storno.kundentyp, storno.empfaenger, storno.firma = alt.kundentyp, alt.empfaenger, alt.firma
        storno.status = Rechnung.Status.OFFEN
        storno.festgeschrieben_von = benutzer
        storno.pdf = rechnung_pdf(storno)
        if storno.mit_xrechnung:
            from .xrechnung import xrechnung_xml
            storno.xml = xrechnung_xml(storno)
        storno.pruefsumme = storno.berechne_pruefsumme()
        storno.festgeschrieben_am = timezone.now()
        storno.save()
        protokolliere("rechnung_storniert", alt.nummer, benutzer=benutzer,
                      details=f"durch Stornorechnung {storno.nummer} ({euro(storno.brutto)})"
                              + (f"\nGrund: {grund.strip()}" if grund.strip() else ""))
    return storno


# ------------------------------------------------------------------ Mahnungen (wie Mahnen() im Makro)
MAHNFRIST_TAGE = 7


def mahnen(rechnung, stufe, benutzer):
    from .models import Mahnung
    from .pdf import mahnung_pdf
    with transaction.atomic():
        rechnung = Rechnung.objects.select_for_update().get(pk=rechnung.pk)
        if not rechnung.ist_festgeschrieben or rechnung.art == Rechnung.Art.STORNO or rechnung.ist_storniert:
            raise RechnungFehler("Diese Rechnung kann nicht gemahnt werden.")
        if rechnung.offen <= Decimal("0.005"):
            raise RechnungFehler("Diese Rechnung ist bezahlt – keine Mahnung nötig.")
        stufe = int(stufe)
        if stufe not in Mahnung.Stufe.values:
            raise RechnungFehler("Unbekannte Mahnstufe.")
        fd = Firmendaten.laden()
        heute = timezone.localdate()
        mahnung = Mahnung(
            rechnung=rechnung, stufe=stufe, datum=heute, frist=heute + dt.timedelta(days=MAHNFRIST_TAGE),
            offen=rechnung.offen, gebuehr=fd.mahngebuehr if stufe == Mahnung.Stufe.MAHNUNG2 else Decimal("0"),
            erstellt_von=benutzer)
        mahnung.pdf = mahnung_pdf(mahnung, fd)
        mahnung.save()
        protokolliere("rechnung_gemahnt", rechnung.nummer, benutzer=benutzer, details=(
            f"{mahnung.get_stufe_display()} · offen {euro(mahnung.offen)}"
            + (f" + Gebühr {euro(mahnung.gebuehr)}" if mahnung.gebuehr else "")
            + f" · neue Frist {mahnung.frist:%d.%m.%Y}"))
    return mahnung


def naechste_mahnstufe(rechnung) -> int:
    return min(rechnung.mahnstufe + 1, 3)
