"""Inventur wie PW_Inventur.bas und Blätter „Inventur Einstellungen / Erfassung / Nachzählung / Abweichungen /
Abschluss / Bericht / Historie“: Zählen → Nachzählen (Vier-Augen) → Freigeben → Korrektur buchen → Abschluss."""
from decimal import Decimal

from django.conf import settings
from django.db import models

URSACHEN = ["Bruch / Verschnitt", "Falsch gebucht", "Schwund", "Zählfehler", "Sonstiges"]


class Inventur(models.Model):
    class Art(models.TextChoices):
        VOLL = "Vollinventur", "Vollinventur"
        STICHPROBE = "Stichprobeninventur", "Stichprobeninventur"
        TEIL = "Teilinventur", "Teilinventur (ein Lagerbereich)"

    class Status(models.TextChoices):
        VORBEREITUNG = "Vorbereitung", "Vorbereitung"
        AKTIV = "Aktiv", "Aktiv (Zählen läuft)"
        ABGESCHLOSSEN = "Abgeschlossen", "Abgeschlossen"

    invid = models.CharField("Inventur-ID", max_length=20, unique=True)
    art = models.CharField("Inventurart", max_length=30, choices=Art.choices, default=Art.VOLL)
    lagerbereich = models.CharField("Lagerbereich (leer = alle)", max_length=100, blank=True)
    stichtag = models.DateField("Stichtag")
    verantwortlich = models.CharField("Verantwortlicher", max_length=100, blank=True)
    blind = models.BooleanField("Blindzählung (Soll für Zähler verborgen)", default=True)
    toleranz_prozent = models.DecimalField("Toleranz % (ab hier Nachzählung)", max_digits=5, decimal_places=2, default=2)
    toleranz_wert = models.DecimalField("Toleranz Wert € (ab hier Nachzählung)", max_digits=9, decimal_places=2, default=50)
    hinweis = models.CharField("Zählteam / Hinweis", max_length=250, blank=True)
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.VORBEREITUNG)
    gestartet_am = models.DateTimeField(null=True, blank=True)
    gestartet_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")
    abgeschlossen_am = models.DateTimeField(null=True, blank=True)
    abgeschlossen_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                          related_name="+")
    angelegt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inventur"
        verbose_name_plural = "Inventuren"
        ordering = ["-stichtag", "-pk"]

    def __str__(self):
        return f"{self.invid} {self.get_art_display()} {self.stichtag:%d.%m.%Y}"


class Position(models.Model):
    """Eine Zeile der Inventur-Erfassung; Soll und EK werden beim Start festgeschrieben (Snapshot)."""

    class Freigabe(models.TextChoices):
        OFFEN = "", "offen"
        FREIGEGEBEN = "Freigegeben", "Freigegeben"
        ABGELEHNT = "Abgelehnt", "Abgelehnt"

    inventur = models.ForeignKey(Inventur, on_delete=models.CASCADE, related_name="positionen")
    material = models.ForeignKey("material.Material", on_delete=models.PROTECT, related_name="inventurpositionen")
    lagerplatz = models.CharField("Lagerbereich", max_length=100, blank=True)
    einheit = models.CharField("Einheit", max_length=20, blank=True)
    soll = models.DecimalField("Soll (Snapshot)", max_digits=12, decimal_places=3)
    ek = models.DecimalField("EK (Snapshot)", max_digits=12, decimal_places=4, null=True, blank=True)
    ist = models.DecimalField("Ist-Zählung", max_digits=12, decimal_places=3, null=True, blank=True)
    zaehler = models.CharField("Zähler", max_length=100, blank=True)
    gezaehlt_am = models.DateTimeField(null=True, blank=True)
    bemerkung = models.CharField("Bemerkung", max_length=250, blank=True)
    nach_ist = models.DecimalField("Nachzählung", max_digits=12, decimal_places=3, null=True, blank=True)
    nachzaehler = models.CharField("Nachzähler", max_length=100, blank=True)
    nach_am = models.DateTimeField(null=True, blank=True)
    nach_bemerkung = models.CharField("Bemerkung Nachzählung", max_length=250, blank=True)
    ursache = models.CharField("Ursache / Bemerkung", max_length=250, blank=True)
    pruefer = models.CharField("Prüfer", max_length=100, blank=True)
    freigabe = models.CharField("Freigabe", max_length=20, choices=Freigabe.choices, blank=True, default="")
    freigabe_am = models.DateTimeField(null=True, blank=True)
    buchung = models.OneToOneField("lager.Lagerbewegung", on_delete=models.PROTECT, null=True, blank=True,
                                   related_name="inventurposition")

    class Meta:
        verbose_name = "Inventurposition"
        verbose_name_plural = "Inventurpositionen"
        ordering = ["lagerplatz", "material__materialnr"]
        constraints = [models.UniqueConstraint(fields=["inventur", "material"], name="material_einmal_je_inventur")]

    # ------------------------------------------------ wie Formeln Erfassung H–M, Abweichungen H–O
    @property
    def gezaehlt(self) -> bool:
        return self.ist is not None

    @property
    def differenz(self) -> Decimal | None:
        return None if self.ist is None else self.ist - self.soll

    @property
    def prozent(self) -> Decimal | None:
        d = self.differenz
        if d is None:
            return None
        if self.soll == 0:
            return Decimal("0") if self.ist == 0 else Decimal("100")
        return (d / self.soll * 100).quantize(Decimal("0.1"))

    @property
    def wert(self) -> Decimal | None:
        d = self.differenz
        return None if d is None else (d * (self.ek or 0)).quantize(Decimal("0.01"))

    @property
    def kritisch(self) -> bool:
        """K: Abweichung ≥ Toleranz % oder ≥ Toleranz Wert → Nachzählung."""
        d = self.differenz
        if not d:
            return False
        return abs(self.prozent) >= self.inventur.toleranz_prozent or abs(self.wert) >= self.inventur.toleranz_wert

    @property
    def status(self) -> str:
        if self.ist is None:
            return "⚪ offen"
        if self.differenz == 0:
            return "🟢 OK"
        if self.kritisch:
            return "🟢 Nachzählung OK" if self.nach_ist is not None and self.freigabe_ist == self.soll else \
                ("🟡 Differenz bestätigt" if self.nach_ist is not None else "🔴 Nachzählung")
        return "🟡 prüfen"

    @property
    def nachzaehlung_offen(self) -> bool:
        return self.kritisch and self.nach_ist is None

    @property
    def freigabe_ist(self) -> Decimal | None:
        return self.nach_ist if self.nach_ist is not None else self.ist

    @property
    def korrektur(self) -> Decimal:
        """N: Korrekturmenge = Freigabe-Ist − Soll, nur wenn freigegeben."""
        if self.freigabe != self.Freigabe.FREIGEGEBEN or self.freigabe_ist is None:
            return Decimal("0")
        return self.freigabe_ist - self.soll

    @property
    def freigabe_offen(self) -> bool:
        """Wie ZuFreigeben(): Abweichung ≠ 0, Nachzählung erledigt, noch nicht entschieden."""
        if self.freigabe_ist is None or self.nachzaehlung_offen or self.freigabe:
            return False
        return self.freigabe_ist != self.soll

    @property
    def wert_freigabe(self) -> Decimal:
        if self.freigabe_ist is None:
            return Decimal("0")
        return ((self.freigabe_ist - self.soll) * (self.ek or 0)).quantize(Decimal("0.01"))
