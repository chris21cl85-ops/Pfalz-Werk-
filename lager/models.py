"""Bestellungen, Wareneingang und Lagerbestand – nach PW_Bestellassistent und PW_Wareneingang.

Der Lagerbestand wird nie direkt überschrieben: jede Veränderung ist eine Lagerbewegung (Buchungsjournal wie
Blatt „Lagerbewegungen“). Bestand = Summe der Bewegungen. Geliefert/eingelagert einer Bestellung werden aus
Wareneingängen und Bewegungen berechnet.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

NULL = Decimal("0")


class Gesperrt(Exception):
    """Buchungen werden nie geändert oder gelöscht – Korrektur über eine neue Buchung."""


class NurAnfuegen(models.Model):
    """Gemeinsame Sperre: einmal gespeichert, nie mehr ändern oder löschen."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise Gesperrt("Buchungen werden nie geändert – bitte eine Korrektur buchen.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise Gesperrt("Buchungen werden nie gelöscht – bitte eine Korrektur buchen.")


def bestand(material) -> Decimal:
    return material.lagerbewegungen.aggregate(s=Sum("menge"))["s"] or NULL


# ------------------------------------------------------------------ Bestellung
class Bestellung(models.Model):
    class Art(models.TextChoices):
        AUTOMATISCH = "Automatisch", "Automatisch (Vorschlag)"
        MANUELL = "Manuell", "Manuell"
        PROJEKT = "Projekt", "Für ein Projekt"

    bnr = models.CharField("Bestell-Nr.", max_length=20, unique=True)
    material = models.ForeignKey("material.Material", on_delete=models.PROTECT, related_name="bestellungen")
    lieferant = models.ForeignKey("lieferanten.Lieferant", on_delete=models.PROTECT, related_name="bestellungen")
    projekt = models.ForeignKey("projekte.Projekt", on_delete=models.PROTECT, null=True, blank=True,
                                related_name="bestellungen")
    menge = models.DecimalField("Bestellmenge", max_digits=12, decimal_places=3)
    einheit = models.CharField("Einheit", max_length=20, blank=True)
    art = models.CharField("Bestellart", max_length=20, choices=Art.choices, default=Art.MANUELL)
    grund = models.CharField("Bestellgrund", max_length=200, blank=True)
    bestellt_am = models.DateField("Bestellt am")
    erwartet_am = models.DateField("Erwarteter Liefertermin", null=True, blank=True)
    freigegeben_von = models.CharField("Freigegeben von", max_length=150, blank=True)
    notiz = models.CharField("Notiz", max_length=300, blank=True)
    eingelagert_vorher = models.DecimalField("Eingelagert (aus Excel)", max_digits=12, decimal_places=3, default=NULL)
    abgeschlossen = models.BooleanField("Abgeschlossen", default=False)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="+")
    angelegt_am = models.DateTimeField("Angelegt am", auto_now_add=True)

    class Meta:
        verbose_name = "Bestellung"
        verbose_name_plural = "Bestellungen"
        ordering = ["-bestellt_am", "-id"]

    def __str__(self):
        return f"{self.bnr} – {self.material.bezeichnung}"

    def get_absolute_url(self):
        return reverse("lager:bestellung", args=[self.pk])

    # Mengen wie im Makro PW_Wareneingang (Bestellt, Geliefert, Eingelagert, RestOffen, ZuLagern)
    @property
    def geliefert(self) -> Decimal:
        return sum((w.menge for w in self.wareneingaenge.all()), NULL)

    @property
    def eingelagert(self) -> Decimal:
        gebucht = sum((b.menge for b in self.lagerbewegungen.all()), NULL)
        return Decimal(self.eingelagert_vorher) + gebucht

    @property
    def rest_offen(self) -> Decimal:
        return max(Decimal(self.menge) - self.geliefert, NULL)

    @property
    def zu_lagern(self) -> Decimal:
        return max(self.geliefert - self.eingelagert, NULL)

    @property
    def ist_offen(self) -> bool:
        return not self.abgeschlossen and (self.rest_offen > 0 or self.zu_lagern > 0)

    @property
    def status_text(self) -> str:
        """Wie StatusText() im Makro: einlagern / überfällig / unterwegs / teilweise; dazu geliefert/abgeschlossen."""
        if self.abgeschlossen:
            return "abgeschlossen"
        rest, lagern = self.rest_offen, self.zu_lagern
        if rest <= 0 and lagern > 0:
            return "einlagern"
        if rest <= 0:
            return "geliefert"
        if self.erwartet_am and self.erwartet_am < timezone.localdate():
            return "überfällig"
        return "teilweise" if self.geliefert > 0 else "unterwegs"

    @property
    def bestellwert(self) -> Decimal:
        """Wie Bestellwert() im Makro PW_Eingang: Menge × Einkaufspreis aus dem Materialstamm."""
        if self.material.ek_netto is None:
            return NULL
        return (Decimal(self.menge) * Decimal(self.material.ek_netto)).quantize(Decimal("0.01"))


class Wareneingang(NurAnfuegen):
    """Eine Lieferung zu einer Bestellung (kann eine Teillieferung sein)."""

    bestellung = models.ForeignKey(Bestellung, on_delete=models.PROTECT, related_name="wareneingaenge")
    datum = models.DateField("Wareneingang am")
    menge = models.DecimalField("Gelieferte Menge", max_digits=12, decimal_places=3)
    notiz = models.CharField("Notiz", max_length=300, blank=True)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="+")
    erfasst_am = models.DateTimeField("Erfasst am", auto_now_add=True)

    class Meta:
        verbose_name = "Wareneingang"
        verbose_name_plural = "Wareneingänge"
        ordering = ["datum", "id"]


class Lagerbewegung(NurAnfuegen):
    """Buchungsjournal (Blatt „Lagerbewegungen“): jede Bestandsänderung, nie überschrieben."""

    class Art(models.TextChoices):
        START = "Startbestand", "Startbestand"
        WARENEINGANG = "Wareneingang", "Wareneingang (eingelagert)"
        KORREKTUR = "Korrektur", "Korrektur / Inventur"
        ENTNAHME = "Entnahme", "Entnahme"

    material = models.ForeignKey("material.Material", on_delete=models.PROTECT, related_name="lagerbewegungen")
    datum = models.DateField("Datum")
    art = models.CharField("Bewegungsart", max_length=20, choices=Art.choices)
    menge = models.DecimalField("Menge +/-", max_digits=12, decimal_places=3)
    bestellung = models.ForeignKey(Bestellung, on_delete=models.PROTECT, null=True, blank=True,
                                   related_name="lagerbewegungen")
    projekt = models.ForeignKey("projekte.Projekt", on_delete=models.PROTECT, null=True, blank=True,
                                related_name="lagerbewegungen")
    notiz = models.CharField("Notiz", max_length=300, blank=True)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="+")
    erfasst_am = models.DateTimeField("Erfasst am", auto_now_add=True)

    class Meta:
        verbose_name = "Lagerbewegung"
        verbose_name_plural = "Lagerbewegungen"
        ordering = ["-datum", "-id"]
