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
    return projekt.rechnungen.filter(art=Rechnung.Art.ABSCHLAG, festgeschrieben_am__isnull=False).order_by("datum", "id")


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
            rechnung.skonto_prozent, rechnung.skonto_tage = Decimal("2"), 7
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
