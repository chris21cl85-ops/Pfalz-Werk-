"""Arbeitsverträge (Blatt „Arbeitsvertraege“), Zeitbuchungen und Monatsabschlüsse."""
from decimal import Decimal

from django.conf import settings
from django.db import models


class Arbeitsvertrag(models.Model):
    class Art(models.TextChoices):
        UNBEFRISTET = "Unbefristet", "Unbefristet"
        BEFRISTET = "Befristet", "Befristet"
        AUSBILDUNG = "Ausbildung", "Ausbildung"
        TEILZEIT = "Teilzeit", "Teilzeit"
        MINIJOB = "Minijob", "Minijob"

    class Status(models.TextChoices):
        ENTWURF = "Entwurf", "Entwurf"
        AKTIV = "Aktiv", "Aktiv"
        BEENDET = "Beendet", "Beendet"

    vertragsid = models.CharField("Vertrags-ID", max_length=20, unique=True)
    mitarbeiter = models.OneToOneField("mitarbeiter.Mitarbeiter", on_delete=models.PROTECT, related_name="vertrag")
    art = models.CharField("Vertragsart", max_length=20, choices=Art.choices, default=Art.UNBEFRISTET)
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.AKTIV)
    eintritt = models.DateField("Eintritt", null=True, blank=True)
    befristet_bis = models.DateField("Befristet bis", null=True, blank=True)
    probezeit_bis = models.DateField("Probezeit bis", null=True, blank=True)
    soll_mo = models.DecimalField("Soll Mo (h)", max_digits=4, decimal_places=2, default=8)
    soll_di = models.DecimalField("Soll Di (h)", max_digits=4, decimal_places=2, default=8)
    soll_mi = models.DecimalField("Soll Mi (h)", max_digits=4, decimal_places=2, default=8)
    soll_do = models.DecimalField("Soll Do (h)", max_digits=4, decimal_places=2, default=8)
    soll_fr = models.DecimalField("Soll Fr (h)", max_digits=4, decimal_places=2, default=8)
    urlaub_jahr = models.DecimalField("Urlaub/Jahr (Tage)", max_digits=4, decimal_places=1, default=30)
    zeitkonto_start = models.DecimalField("Zeitkonto Start (h)", max_digits=7, decimal_places=2, default=0)
    brutto_monat = models.DecimalField("Brutto/Monat (€)", max_digits=9, decimal_places=2, null=True, blank=True)
    stundenlohn = models.DecimalField("Stundenlohn (€)", max_digits=7, decimal_places=2, null=True, blank=True)
    kuendigungsfrist = models.CharField("Kündigungsfrist", max_length=60, blank=True)
    taetigkeit = models.CharField("Tätigkeit", max_length=150, blank=True)
    arbeitsort = models.CharField("Arbeitsort", max_length=150, blank=True)
    vermerk = models.CharField("Bearbeitungsvermerk", max_length=250, blank=True)
    geaendert_am = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Arbeitsvertrag"
        verbose_name_plural = "Arbeitsverträge"
        ordering = ["mitarbeiter__name"]

    def __str__(self):
        return f"{self.vertragsid} {self.mitarbeiter.name}"

    @property
    def soll_woche(self) -> Decimal:
        return self.soll_mo + self.soll_di + self.soll_mi + self.soll_do + self.soll_fr

    def soll_wochentag(self, wochentag: int) -> Decimal:
        return [self.soll_mo, self.soll_di, self.soll_mi, self.soll_do, self.soll_fr][wochentag] if wochentag < 5 else Decimal("0")


class Zeitbuchung(models.Model):
    class Taetigkeit(models.TextChoices):
        FERTIGUNG = "Fertigung", "Fertigung / Werkstatt"
        MONTAGE = "Montage", "Montage"
        PLANUNG = "Planung", "Aufmaß / Planung"
        FAHRT = "Fahrt", "Fahrt"
        LAGER = "Lager", "Lager / Material"
        BUERO = "Büro", "Büro"
        SONSTIGES = "Sonstiges", "Sonstiges"

    class Quelle(models.TextChoices):
        HAND = "Hand", "von Hand"
        PRODUKTION = "Produktion", "Rückmeldung Produktion"
        IMPORT = "Import", "Excel-Import"

    mitarbeiter = models.ForeignKey("mitarbeiter.Mitarbeiter", on_delete=models.PROTECT, related_name="zeitbuchungen")
    datum = models.DateField("Datum")
    beginn = models.TimeField("Von", null=True, blank=True)
    ende = models.TimeField("Bis", null=True, blank=True)
    pause_min = models.PositiveIntegerField("Pause (Min.)", default=0)
    stunden = models.DecimalField("Stunden", max_digits=5, decimal_places=2)
    projekt = models.ForeignKey("projekte.Projekt", on_delete=models.PROTECT, null=True, blank=True,
                                related_name="zeitbuchungen")
    arbeitsgang = models.ForeignKey("produktion.Arbeitsgang", on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="zeitbuchungen")
    taetigkeit = models.CharField("Tätigkeit", max_length=20, choices=Taetigkeit.choices, default=Taetigkeit.FERTIGUNG)
    notiz = models.CharField("Notiz", max_length=250, blank=True)
    satz = models.DecimalField("Stundenlohn bei Buchung (€)", max_digits=7, decimal_places=2, default=0)
    quelle = models.CharField("Quelle", max_length=20, choices=Quelle.choices, default=Quelle.HAND)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="+")
    erfasst_am = models.DateTimeField(auto_now_add=True)
    storniert_am = models.DateTimeField("Storniert am", null=True, blank=True)
    storno_grund = models.CharField("Storno-Grund", max_length=200, blank=True)

    class Meta:
        verbose_name = "Zeitbuchung"
        verbose_name_plural = "Zeitbuchungen"
        ordering = ["-datum", "beginn", "pk"]

    def __str__(self):
        return f"{self.mitarbeiter} {self.datum:%d.%m.%Y} {self.stunden} h"

    @property
    def kosten(self) -> Decimal:
        return (self.stunden * self.satz).quantize(Decimal("0.01"))


class Monatsabschluss(models.Model):
    """Abgeschlossener Monat je Mitarbeiter: Buchungen darin sind gesperrt (Grundlage Lohnabrechnung)."""
    mitarbeiter = models.ForeignKey("mitarbeiter.Mitarbeiter", on_delete=models.PROTECT, related_name="monatsabschluesse")
    monat = models.DateField("Monat (1. Tag)")
    soll = models.DecimalField(max_digits=7, decimal_places=2)
    ist = models.DecimalField(max_digits=7, decimal_places=2)
    zeitkonto = models.DecimalField(max_digits=7, decimal_places=2)
    abgeschlossen_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    abgeschlossen_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Monatsabschluss"
        verbose_name_plural = "Monatsabschlüsse"
        constraints = [models.UniqueConstraint(fields=["mitarbeiter", "monat"], name="ein_abschluss_je_monat")]
