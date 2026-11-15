"""Produktion wie Blätter „Produktion Arbeitsgänge“, „Produktion QM“, „Arbeitsgangbibliothek“, „Routenvorlagen“."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

TYPEN = ["Logistik", "QM", "Arbeitszeit", "Maschinenzeit", "Prozess-/Wartezeit", "Nacharbeit"]
WARTEZEIT = "Prozess-/Wartezeit"


class Vorlage(models.Model):
    """Ein Eintrag der Arbeitsgangbibliothek."""
    code = models.CharField("AG-Code", max_length=20, unique=True)
    kategorie = models.CharField("Kategorie", max_length=60, blank=True)
    name = models.CharField("Arbeitsgang", max_length=150)
    typ = models.CharField("Typ", max_length=30, choices=[(t, t) for t in TYPEN], default="Arbeitszeit")
    standardfolge = models.PositiveIntegerField("Standardfolge", default=100)
    qm_danach = models.BooleanField("QM danach?", default=False)
    wartezeit_moeglich = models.BooleanField("Wartezeit möglich?", default=False)
    hinweis = models.CharField("Hinweis", max_length=250, blank=True)

    class Meta:
        verbose_name = "Arbeitsgang-Vorlage"
        verbose_name_plural = "Arbeitsgangbibliothek"
        ordering = ["standardfolge", "code"]

    def __str__(self):
        return f"{self.code} {self.name}"


class Route(models.Model):
    """Routenvorlage: Standardfolge von Arbeitsgängen (Startpunkt, kein Zwangsablauf)."""
    name = models.CharField("Routenvorlage", max_length=100, unique=True)
    werkstoffgruppe = models.CharField("Werkstoffgruppe", max_length=60, blank=True)

    class Meta:
        verbose_name = "Routenvorlage"
        verbose_name_plural = "Routenvorlagen"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Routenschritt(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="schritte")
    schritt = models.PositiveIntegerField("Schritt")
    code = models.CharField("AG-Code", max_length=20)
    name = models.CharField("Arbeitsgang", max_length=150)
    typ = models.CharField("Typ", max_length=30, blank=True)
    plan_std = models.DecimalField("Plan-Std. Richtwert", max_digits=7, decimal_places=2, default=0)
    wartezeit_std = models.DecimalField("Wartezeit Std.", max_digits=7, decimal_places=2, default=0)
    hinweis = models.CharField("QM / Hinweis", max_length=250, blank=True)

    class Meta:
        ordering = ["route", "schritt"]
        constraints = [models.UniqueConstraint(fields=["route", "schritt"], name="route_schritt_einmal")]


class Arbeitsgang(models.Model):
    class Status(models.TextChoices):
        GEPLANT = "Geplant", "Geplant"
        IN_ARBEIT = "In Arbeit", "In Arbeit"
        FERTIG = "Fertig", "Fertig"

    class Prioritaet(models.TextChoices):
        NIEDRIG = "Niedrig", "Niedrig"
        MITTEL = "Mittel", "Mittel"
        HOCH = "Hoch", "Hoch"

    agid = models.CharField("AG-ID", max_length=60, unique=True)
    projekt = models.ForeignKey("projekte.Projekt", on_delete=models.PROTECT, related_name="arbeitsgaenge")
    moebel = models.ForeignKey("moebel.MoebelPosition", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="arbeitsgaenge")
    bereich = models.CharField("Bauteil / Bereich", max_length=200, blank=True)
    name = models.CharField("Arbeitsgang", max_length=150)
    code = models.CharField("AG-Code", max_length=20, blank=True)
    typ = models.CharField("Vorgangstyp", max_length=30, blank=True)
    reihenfolge = models.PositiveIntegerField("Reihenfolge", default=10)
    mitarbeiter = models.ForeignKey("mitarbeiter.Mitarbeiter", on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="arbeitsgaenge")
    plan_start = models.DateField("Planstart", null=True, blank=True)
    plan_ende = models.DateField("Planende", null=True, blank=True)
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.GEPLANT)
    prioritaet = models.CharField("Priorität", max_length=10, choices=Prioritaet.choices, default=Prioritaet.MITTEL)
    plan_std = models.DecimalField("Plan-Std.", max_digits=7, decimal_places=2, default=0)
    ist_std = models.DecimalField("Ist-Std.", max_digits=7, decimal_places=2, default=0)
    wartezeit_std = models.DecimalField("Wartezeit Std.", max_digits=7, decimal_places=2, default=0)
    problem = models.CharField("Problem / Grund", max_length=250, blank=True)
    begonnen_am = models.DateTimeField("Begonnen am", null=True, blank=True)
    fertig_am = models.DateTimeField("Fertig am", null=True, blank=True)
    bemerkung = models.CharField("Bemerkung", max_length=250, blank=True)
    vorgaenger = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="nachfolger",
                                   verbose_name="Vorgänger")
    ist_nacharbeit = models.BooleanField("Nacharbeit aus QM", default=False)
    angelegt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Arbeitsgang"
        verbose_name_plural = "Arbeitsgänge"
        ordering = ["projekt__projektnr", "pk"]

    def __str__(self):
        return f"{self.agid} {self.name}"

    # ------------------------------------------------ wie Spalten V–AI (Formeln der Excel)
    @property
    def vorgaenger_qm(self) -> str:
        """Y: Freigabe der QM-Prüfung zum Vorgänger, sonst „Nicht erforderlich“."""
        if self.vorgaenger_id is None:
            return "Nicht erforderlich"
        pruefung = self.vorgaenger.qm_pruefungen.order_by("-pk").first()
        return pruefung.freigabe if pruefung else "Nicht erforderlich"

    @property
    def nacharbeit_offen(self) -> bool:
        """AH: QM-Prüfung zu diesem Arbeitsgang mit Nacharbeit nötig und nicht freigegeben."""
        return any(p.nacharbeit_noetig and p.freigabe != "Freigegeben" for p in self.qm_pruefungen.all())

    @property
    def fruehester_start(self):
        """AF: Vorgänger fertig am + Wartezeit."""
        if not self.wartezeit_std or self.vorgaenger_id is None or not self.vorgaenger.fertig_am:
            return None
        return self.vorgaenger.fertig_am + timedelta(hours=float(self.wartezeit_std))

    @property
    def startfreigabe(self) -> str:
        """Z: Startfreigabe wie Excel-Formel."""
        if self.nacharbeit_offen:
            return "🔒 Nacharbeit/QM offen"
        if self.typ == WARTEZEIT:
            fs = self.fruehester_start
            if fs is None:
                return "⚪ Wartezeit unvollständig"
            if timezone.now() < fs:
                return f"⏱ Prozess läuft bis {timezone.localtime(fs):%d.%m. %H:%M}"
            return "🟢 Wartezeit erfüllt"
        if self.vorgaenger_id is None:
            return "🟢 Start möglich"
        if self.vorgaenger.status == self.Status.FERTIG and self.vorgaenger_qm in ("Freigegeben", "Nicht erforderlich"):
            return "🟢 Start möglich"
        return "🔒 wartet auf Vorgänger/QM"

    @property
    def startbereit(self) -> bool:
        return self.startfreigabe.startswith("🟢")

    @property
    def lohnkosten_ist(self) -> Decimal | None:
        """AJ: Ist-Stunden × Stundensatz des Mitarbeiters."""
        if not self.mitarbeiter_id or not self.ist_std:
            return None
        return (self.ist_std * (self.mitarbeiter.stundensatz or 0)).quantize(Decimal("0.01"))


class QMPruefung(models.Model):
    """Zeile im Blatt „Produktion QM“. Nicht bestanden erzeugt Nacharbeit und erneute Prüfung."""

    class Ergebnis(models.TextChoices):
        BESTANDEN = "Bestanden", "Bestanden"
        NICHT = "Nicht bestanden", "Nicht bestanden"

    qmid = models.CharField("QM-ID", max_length=20, unique=True)
    projekt = models.ForeignKey("projekte.Projekt", on_delete=models.PROTECT, related_name="qm_pruefungen")
    arbeitsgang = models.ForeignKey(Arbeitsgang, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="qm_pruefungen", verbose_name="AG-ID")
    bauteil = models.CharField("Bauteil", max_length=150, default="Gesamt")
    pruefpunkt = models.CharField("Prüfpunkt", max_length=150, default="Endkontrolle")
    pruefer = models.CharField("Prüfer", max_length=100)
    datum = models.DateField("Prüfdatum")
    ergebnis = models.CharField("Ergebnis", max_length=20, choices=Ergebnis.choices)
    abweichung = models.CharField("Abweichung / Mangel", max_length=300, blank=True)
    nacharbeit_noetig = models.BooleanField("Nacharbeit nötig", default=False)
    nacharbeit_erledigt = models.BooleanField("Nacharbeit erledigt", default=False)
    nachpruefung = models.CharField("Nachprüfung", max_length=20, blank=True)
    nacharbeit_ag = models.ForeignKey(Arbeitsgang, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="+", verbose_name="Nacharbeit-Arbeitsgang")
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="+")
    erfasst_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "QM-Prüfung"
        verbose_name_plural = "QM-Prüfungen"
        ordering = ["-datum", "-pk"]

    def __str__(self):
        return f"{self.qmid} {self.projekt.projektnr} {self.ergebnis}"

    @property
    def freigabe(self) -> str:
        """O: Produktionsfreigabe wie Excel-Formel."""
        if self.ergebnis == self.Ergebnis.BESTANDEN:
            return "Freigegeben"
        if self.nacharbeit_erledigt and self.nachpruefung == "Bestanden":
            return "Freigegeben"
        return "Gesperrt"
