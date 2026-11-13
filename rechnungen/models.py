"""Ausgangsrechnungen wie in der Excel-Fassung (Makro PW_Rechnung).

Eine Rechnung beginnt als **Entwurf** (frei änderbar, noch ohne Nummer). Beim **Festschreiben**
bekommt sie die nächste fortlaufende Nummer, Datum, Fälligkeit, Summen, eine Kopie der Firmen- und
Kundendaten, das PDF und eine Prüfsumme. Danach ist sie gesperrt: Änderungen nur noch per Storno
(eigenes Paket). Rechnungen werden nie gelöscht.
"""
import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from kunden.models import Kunde
from projekte.models import Projekt

CENT = Decimal("0.01")


def runden(betrag) -> Decimal:
    """Kaufmännisch auf Cent runden (wie Excel RUNDEN)."""
    return Decimal(betrag).quantize(CENT, rounding=ROUND_HALF_UP)


class RechnungGesperrt(Exception):
    """Eine festgeschriebene Rechnung darf nicht mehr verändert oder gelöscht werden."""


# ------------------------------------------------------------------ Firmendaten
class Firmendaten(models.Model):
    """Briefkopf, Bank und Steuerangaben – es gibt genau einen Datensatz (wie Blatt „Firmendaten“)."""

    firmenname = models.CharField("Firmenname", max_length=200, blank=True)
    inhaber = models.CharField("Inhaber / Ansprechpartner", max_length=200, blank=True)
    strasse = models.CharField("Straße und Hausnummer", max_length=200, blank=True)
    plz = models.CharField("PLZ", max_length=10, blank=True)
    ort = models.CharField("Ort", max_length=100, blank=True)
    land = models.CharField("Land", max_length=2, default="DE", blank=True)
    telefon = models.CharField("Telefon", max_length=50, blank=True)
    email = models.EmailField("E-Mail", blank=True)
    steuernummer = models.CharField("Steuernummer", max_length=40, blank=True)
    ust_idnr = models.CharField("USt-IdNr.", max_length=20, blank=True)
    iban = models.CharField("IBAN", max_length=40, blank=True)
    bic = models.CharField("BIC", max_length=15, blank=True)
    bank = models.CharField("Bank", max_length=100, blank=True)
    zahlungsziel_tage = models.PositiveIntegerField("Zahlungsziel Tage", default=14)
    kleinunternehmer = models.BooleanField("Kleinunternehmer (§ 19 UStG)", default=False)
    ust_satz = models.DecimalField("USt-Satz %", max_digits=5, decimal_places=2, default=Decimal("19"))
    rechnungs_praefix = models.CharField("Rechnungs-Präfix", max_length=10, default="RE-", blank=True)
    letzte_rechnungsnummer = models.PositiveIntegerField("Letzte Rechnungsnummer", default=0)
    fusstext = models.TextField("Fußtext Rechnung", blank=True, default="Vielen Dank für Ihren Auftrag.")
    mahngebuehr = models.DecimalField("Mahngebühr 2. Mahnung €", max_digits=8, decimal_places=2,
                                      default=Decimal("5"))
    geaendert_am = models.DateTimeField("Geändert am", auto_now=True)

    # Pflichtangaben für eine Rechnung (§ 14 UStG) – wie FirmaFehlt() im Makro
    PFLICHT = ["firmenname", "strasse", "plz", "ort", "iban"]

    class Meta:
        verbose_name = "Firmendaten"
        verbose_name_plural = "Firmendaten"

    def __str__(self):
        return self.firmenname or "Firmendaten"

    @classmethod
    def laden(cls) -> "Firmendaten":
        objekt, _ = cls.objects.get_or_create(pk=1)
        return objekt

    def save(self, *args, **kwargs):
        self.pk = 1  # immer derselbe Datensatz
        super().save(*args, **kwargs)

    def fehlende_angaben(self) -> list[str]:
        fehlt = [self._meta.get_field(f).verbose_name for f in self.PFLICHT if not getattr(self, f).strip()]
        if not self.steuernummer.strip() and not self.ust_idnr.strip():
            fehlt.append("Steuernummer oder USt-IdNr.")
        return fehlt

    @property
    def effektiver_ust_satz(self) -> Decimal:
        return Decimal("0") if self.kleinunternehmer else Decimal(self.ust_satz)

    def als_kopie(self) -> dict:
        """Stand der Firmendaten zum Zeitpunkt des Festschreibens (für PDF und Prüfung)."""
        felder = [f.name for f in self._meta.fields if f.name not in ("id", "geaendert_am", "letzte_rechnungsnummer")]
        return {f: str(getattr(self, f)) if not isinstance(getattr(self, f), bool) else getattr(self, f)
                for f in felder}


# ------------------------------------------------------------------ Rechnung
class RechnungQuerySet(models.QuerySet):
    def delete(self):
        raise RechnungGesperrt("Rechnungen werden nie gelöscht.")

    def update(self, **kwargs):
        if self.filter(festgeschrieben_am__isnull=False).exists():
            raise RechnungGesperrt("Festgeschriebene Rechnungen sind gesperrt.")
        return super().update(**kwargs)


class Rechnung(models.Model):
    class Art(models.TextChoices):
        RECHNUNG = "Rechnung", "Rechnung"
        ABSCHLAG = "Abschlag", "Abschlagsrechnung"
        SCHLUSS = "Schluss", "Schlussrechnung"

    class Status(models.TextChoices):
        ENTWURF = "Entwurf", "Entwurf"
        OFFEN = "Offen", "Offen"
        VERWORFEN = "Verworfen", "Verworfen (Entwurf)"

    # Zahlungsziele wie im Makro (Kacheln „sofort“, „14 Tage“, „30 Tage“, „14 Tage / 2 % Skonto“)
    ZAHLUNGSZIELE = [
        ("0", "zahlbar sofort"),
        ("14", "zahlbar in 14 Tagen"),
        ("30", "zahlbar in 30 Tagen"),
        ("14s", "14 Tage, 2 % Skonto bei Zahlung in 7 Tagen"),
    ]

    nummer = models.CharField("Rechnungs-Nr.", max_length=40, unique=True, null=True, blank=True)
    art = models.CharField("Art", max_length=20, choices=Art.choices, default=Art.RECHNUNG)
    abschlag_nr = models.PositiveIntegerField("Abschlag Nr.", null=True, blank=True)
    abschlag_prozent = models.DecimalField("Abschlag %", max_digits=5, decimal_places=2, null=True, blank=True)
    auftragswert = models.DecimalField("Auftragswert netto", max_digits=12, decimal_places=2, null=True, blank=True)
    projekt = models.ForeignKey(Projekt, on_delete=models.PROTECT, related_name="rechnungen", verbose_name="Projekt")
    kunde = models.ForeignKey(Kunde, on_delete=models.PROTECT, related_name="rechnungen", verbose_name="Kunde")
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.ENTWURF)
    leistungszeitraum = models.CharField("Leistungszeitraum", max_length=60, blank=True)
    zahlungsziel = models.CharField("Zahlungsziel", max_length=4, choices=ZAHLUNGSZIELE, default="14")
    mit_xrechnung = models.BooleanField("E-Rechnung (XRechnung) mit erzeugen", default=False)
    kaeufer_referenz = models.CharField(
        "Leitweg-ID / Bestellzeichen des Kunden", max_length=100, blank=True,
        help_text="Für Behörden die Leitweg-ID. Leer lassen = Kunden-Nr. wird verwendet.")

    # Wird beim Festschreiben gesetzt
    datum = models.DateField("Rechnungsdatum", null=True, blank=True)
    faellig = models.DateField("Fällig am", null=True, blank=True)
    ziel_tage = models.PositiveIntegerField("Ziel Tage", null=True, blank=True)
    skonto_prozent = models.DecimalField("Skonto %", max_digits=5, decimal_places=2, default=Decimal("0"))
    skonto_tage = models.PositiveIntegerField("Skonto Tage", default=0)
    ust_satz = models.DecimalField("USt %", max_digits=5, decimal_places=2, null=True, blank=True)
    netto = models.DecimalField("Netto", max_digits=12, decimal_places=2, null=True, blank=True)
    ust = models.DecimalField("USt", max_digits=12, decimal_places=2, null=True, blank=True)
    brutto = models.DecimalField("Brutto", max_digits=12, decimal_places=2, null=True, blank=True)
    kundentyp = models.CharField("Kundentyp", max_length=30, blank=True)
    empfaenger = models.TextField("Anschrift auf der Rechnung", blank=True)
    firma = models.JSONField("Firmendaten zum Zeitpunkt der Rechnung", default=dict, blank=True)
    pdf = models.BinaryField("PDF", null=True, blank=True, editable=False)
    xml = models.BinaryField("XRechnung", null=True, blank=True, editable=False)
    pruefsumme = models.CharField("Prüfsumme", max_length=64, blank=True)
    festgeschrieben_am = models.DateTimeField("Festgeschrieben am", null=True, blank=True)
    festgeschrieben_von = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                            on_delete=models.PROTECT, related_name="+")

    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.PROTECT, related_name="+")
    angelegt_am = models.DateTimeField("Angelegt am", auto_now_add=True)
    geaendert_am = models.DateTimeField("Geändert am", auto_now=True)

    objects = RechnungQuerySet.as_manager()

    class Meta:
        verbose_name = "Rechnung"
        verbose_name_plural = "Rechnungen"
        ordering = ["-festgeschrieben_am", "-angelegt_am", "-id"]

    def __str__(self):
        return self.nummer or f"Entwurf {self.pk}"

    def get_absolute_url(self):
        return reverse("rechnungen:detail", args=[self.pk])

    # ---------------------------------------------------------------- Sperre
    @property
    def ist_festgeschrieben(self) -> bool:
        return self.festgeschrieben_am is not None

    @property
    def ist_entwurf(self) -> bool:
        return self.status == self.Status.ENTWURF

    def save(self, *args, **kwargs):
        if self.pk is not None:
            alt = Rechnung.objects.filter(pk=self.pk).values_list("festgeschrieben_am", flat=True).first()
            if alt is not None:
                raise RechnungGesperrt(f"Rechnung {self.nummer} ist festgeschrieben und kann nicht geändert werden. "
                                       "Änderungen nur per Storno.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RechnungGesperrt("Rechnungen werden nie gelöscht. Ein Entwurf kann verworfen werden.")

    # ---------------------------------------------------------------- Anzeige
    @property
    def titel(self) -> str:
        if self.art == self.Art.SCHLUSS:
            return "Schlussrechnung"
        if self.art == self.Art.ABSCHLAG:
            return f"{self.abschlag_nr}. Abschlagsrechnung" if self.abschlag_nr else "Abschlagsrechnung"
        return "Rechnung"

    @property
    def zahlungsziel_text(self) -> str:
        return dict(self.ZAHLUNGSZIELE).get(self.zahlungsziel, "")

    # ---------------------------------------------------------------- Summen
    def summen(self, ust_satz=None) -> dict:
        """Netto, USt, Brutto wie im Makro: jede Position auf Cent, USt auf die Nettosumme."""
        if self.ist_festgeschrieben:
            return {"netto": self.netto, "ust_satz": self.ust_satz, "ust": self.ust, "brutto": self.brutto}
        if ust_satz is None:
            ust_satz = Firmendaten.laden().effektiver_ust_satz
        netto = runden(sum((p.gesamt for p in self.positionen.all()), Decimal("0")))
        ust = runden(netto * Decimal(ust_satz) / 100)
        return {"netto": netto, "ust_satz": Decimal(ust_satz), "ust": ust, "brutto": netto + ust}

    # ---------------------------------------------------------------- Prüfsumme
    def inhalt_fuer_pruefsumme(self) -> str:
        daten = {
            "nummer": self.nummer, "art": self.art, "abschlag_nr": self.abschlag_nr,
            "datum": str(self.datum), "faellig": str(self.faellig),
            "projekt": self.projekt.projektnr, "kunde": self.kunde.kundennr, "empfaenger": self.empfaenger,
            "leistungszeitraum": self.leistungszeitraum, "ziel_tage": self.ziel_tage,
            "skonto": [str(self.skonto_prozent), self.skonto_tage],
            "summen": [str(self.netto), str(self.ust_satz), str(self.ust), str(self.brutto)],
            "positionen": [[p.pos, p.text, str(p.menge), p.einheit, str(p.einzelpreis), str(p.gesamt)]
                           for p in self.positionen.order_by("pos")],
            "firma": self.firma,
            "pdf": hashlib.sha256(bytes(self.pdf or b"")).hexdigest(),
        }
        if self.xml:  # nur wenn vorhanden – ältere Rechnungen ohne XRechnung behalten ihre Prüfsumme
            daten["xml"] = hashlib.sha256(bytes(self.xml)).hexdigest()
            daten["kaeufer_referenz"] = self.kaeufer_referenz
        return json.dumps(daten, ensure_ascii=False, sort_keys=True)

    def berechne_pruefsumme(self) -> str:
        return hashlib.sha256(self.inhalt_fuer_pruefsumme().encode("utf-8")).hexdigest()

    def pruefsumme_stimmt(self) -> bool:
        return bool(self.pruefsumme) and self.pruefsumme == self.berechne_pruefsumme()


class PositionQuerySet(models.QuerySet):
    def delete(self):
        if self.filter(rechnung__festgeschrieben_am__isnull=False).exists():
            raise RechnungGesperrt("Positionen festgeschriebener Rechnungen sind gesperrt.")
        return super().delete()

    def update(self, **kwargs):
        if self.filter(rechnung__festgeschrieben_am__isnull=False).exists():
            raise RechnungGesperrt("Positionen festgeschriebener Rechnungen sind gesperrt.")
        return super().update(**kwargs)


class Position(models.Model):
    rechnung = models.ForeignKey(Rechnung, on_delete=models.PROTECT, related_name="positionen")
    pos = models.PositiveIntegerField("Pos.")
    text = models.TextField("Beschreibung")
    menge = models.DecimalField("Menge", max_digits=12, decimal_places=3, default=Decimal("1"))
    einheit = models.CharField("Einheit", max_length=20, default="Stk", blank=True)
    einzelpreis = models.DecimalField("Einzelpreis netto", max_digits=12, decimal_places=2)

    objects = PositionQuerySet.as_manager()

    class Meta:
        verbose_name = "Rechnungsposition"
        verbose_name_plural = "Rechnungspositionen"
        ordering = ["pos", "id"]

    def __str__(self):
        return f"{self.pos}. {self.text[:40]}"

    @property
    def gesamt(self) -> Decimal:
        return runden(Decimal(self.menge) * Decimal(self.einzelpreis))

    def _pruefe_sperre(self):
        if self.rechnung_id and Rechnung.objects.filter(pk=self.rechnung_id,
                                                        festgeschrieben_am__isnull=False).exists():
            raise RechnungGesperrt("Positionen festgeschriebener Rechnungen sind gesperrt.")

    def save(self, *args, **kwargs):
        self._pruefe_sperre()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._pruefe_sperre()
        return super().delete(*args, **kwargs)
