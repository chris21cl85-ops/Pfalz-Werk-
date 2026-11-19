"""Stückliste, Kalkulation und Auftrag je Projekt – nach PW_Auftraege (Kalkulieren → Angebot & Auftrag → Freigaben)
und den Blättern „Stueckliste“ (48), „Kalkulation“ (50), „Auftraege“ (37)."""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

NULL = Decimal("0")
CENT = Decimal("0.01")


class Stuecklistenposition(models.Model):
    class Status(models.TextChoices):
        GEPLANT = "Geplant", "Geplant (Idee, noch kein Bedarf)"
        BENOETIGT = "Benötigt", "Benötigt (fließt in Bestellvorschläge)"
        ENTNOMMEN = "Entnommen", "Entnommen (aus dem Lager gebucht)"

    projekt = models.ForeignKey("projekte.Projekt", on_delete=models.PROTECT, related_name="stueckliste")
    pos = models.PositiveIntegerField("Pos.")
    material = models.ForeignKey("material.Material", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="stuecklistenpositionen")
    bezeichnung = models.CharField("Bezeichnung", max_length=250)
    menge = models.DecimalField("Menge", max_digits=12, decimal_places=3)
    einheit = models.CharField("Einheit", max_length=20, blank=True)
    ek = models.DecimalField("EK / Einheit netto", max_digits=12, decimal_places=4, null=True, blank=True)
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.BENOETIGT)
    notiz = models.CharField("Notiz", max_length=300, blank=True)
    moebel = models.ForeignKey("moebel.MoebelPosition", on_delete=models.PROTECT, null=True, blank=True,
                               related_name="stuecklistenpositionen", verbose_name="aus Möbelrechner")
    geaendert_am = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Stücklistenposition"
        verbose_name_plural = "Stückliste"
        ordering = ["projekt", "pos", "id"]

    def __str__(self):
        return f"{self.pos}. {self.bezeichnung}"

    @property
    def gesamt(self) -> Decimal:
        """Gesamt EK = Menge × EK (wie Spalte H)."""
        if self.ek is None:
            return NULL
        return (Decimal(self.menge) * Decimal(self.ek)).quantize(CENT, rounding=ROUND_HALF_UP)


class Kalkulation(models.Model):
    """Eine Kalkulation je Projekt (Blatt „Kalkulation“ ist zeilengleich mit den Projekten)."""

    class Art(models.TextChoices):
        VOR = "Vorkalkulation", "Vorkalkulation"
        ZWISCHEN = "Zwischenkalkulation", "Zwischenkalkulation"
        NACH = "Nachkalkulation", "Nachkalkulation"

    projekt = models.OneToOneField("projekte.Projekt", on_delete=models.PROTECT, related_name="kalkulation")
    art = models.CharField("Kalkulationsart", max_length=30, choices=Art.choices, default=Art.VOR)
    material_manuell = models.DecimalField("Materialkosten (falls ohne Stückliste)", max_digits=12, decimal_places=2,
                                           null=True, blank=True)
    beschlaege = models.DecimalField("Beschläge / Sonstiges", max_digits=12, decimal_places=2, default=NULL)
    lohn_std = models.DecimalField("Lohn Stunden", max_digits=8, decimal_places=2, default=NULL)
    lohn_satz = models.DecimalField("Lohn € / Std.", max_digits=8, decimal_places=2, default=NULL)
    maschinen = models.DecimalField("Maschinenkosten", max_digits=12, decimal_places=2, default=NULL)
    montage = models.DecimalField("Montagekosten", max_digits=12, decimal_places=2, default=NULL)
    fahrt = models.DecimalField("Fahrtkosten", max_digits=12, decimal_places=2, default=NULL)
    fremd = models.DecimalField("Fremdleistungen", max_digits=12, decimal_places=2, default=NULL)
    zuschlag = models.DecimalField("Zuschlag %", max_digits=6, decimal_places=2, default=Decimal("15"))
    risiko = models.DecimalField("Risiko %", max_digits=6, decimal_places=2, default=Decimal("5"))
    notiz = models.TextField("Notiz", blank=True)
    geaendert_am = models.DateTimeField("Stand", auto_now=True)

    class Meta:
        verbose_name = "Kalkulation"
        verbose_name_plural = "Kalkulationen"

    def __str__(self):
        return f"Kalkulation {self.projekt.projektnr}"

    @property
    def material(self) -> Decimal:
        """Materialkosten aus der Stückliste (ohne nur geplante Ideen); sonst der von Hand eingetragene Wert."""
        positionen = [p for p in self.projekt.stueckliste.all() if p.status != Stuecklistenposition.Status.GEPLANT]
        if positionen:
            return sum((p.gesamt for p in positionen), NULL)
        return Decimal(self.material_manuell or 0)

    @property
    def lohnkosten(self) -> Decimal:
        return (Decimal(self.lohn_std) * Decimal(self.lohn_satz)).quantize(CENT, rounding=ROUND_HALF_UP)

    @property
    def kosten(self) -> Decimal:
        """Wie Entwurf() im Makro: Material + Beschläge + Std × €/Std + Maschine + Montage + Fahrt + Fremd."""
        return (self.material + Decimal(self.beschlaege) + self.lohnkosten + Decimal(self.maschinen)
                + Decimal(self.montage) + Decimal(self.fahrt) + Decimal(self.fremd))

    @property
    def vk(self) -> Decimal:
        """VK = Kosten × (1 + Zuschlag % + Risiko %), auf Cent gerundet (wie Spalte N)."""
        faktor = 1 + (Decimal(self.zuschlag) + Decimal(self.risiko)) / 100
        return (self.kosten * faktor).quantize(CENT, rounding=ROUND_HALF_UP)

    @property
    def ist_kosten(self) -> Decimal:
        """Nachkalkulation: Eingangsrechnungen (netto) + Lagerentnahmen + Lohnkosten Ist (Zeiterfassung)."""
        from rechnungen.models import Eingangsrechnung
        er = sum((e.netto for e in Eingangsrechnung.objects.filter(projekt=self.projekt, storniert_am__isnull=True)), NULL)
        entnahmen = sum((p.gesamt for p in self.projekt.stueckliste.all()
                         if p.status == Stuecklistenposition.Status.ENTNOMMEN), NULL)
        from zeiten.dienst import lohn_ist
        return er + entnahmen + lohn_ist(self.projekt)


class Auftrag(models.Model):
    """Angebot/Auftrag je Projekt (Blatt „Auftraege“) mit Freigaben Kunde / Chef / Meister."""

    class Status(models.TextChoices):
        ANGEBOT = "Angebot", "Angebot"
        BEAUFTRAGT = "Beauftragt", "Beauftragt"
        IN_ARBEIT = "In Arbeit", "In Arbeit"
        ABGESCHLOSSEN = "Abgeschlossen", "Abgeschlossen"

    class Freigabe(models.TextChoices):
        OFFEN = "Offen", "Offen"
        FREIGEGEBEN = "Freigegeben", "Freigegeben"
        RUECKFRAGE = "Rückfrage", "Rückfrage"
        ABGELEHNT = "Abgelehnt", "Abgelehnt"

    aunr = models.CharField("Auftrags-Nr.", max_length=20, unique=True)
    projekt = models.OneToOneField("projekte.Projekt", on_delete=models.PROTECT, related_name="auftrag")
    leistung = models.TextField("Leistung / Kurztext", blank=True)
    angebot_netto = models.DecimalField("Angebot netto", max_digits=12, decimal_places=2)
    status = models.CharField("Auftragsstatus", max_length=20, choices=Status.choices, default=Status.ANGEBOT)
    termin = models.CharField("Lieferung / Montage", max_length=60, blank=True)
    freigabe_kunde = models.CharField("Freigabe Kunde", max_length=20, choices=Freigabe.choices, default=Freigabe.OFFEN)
    freigabe_chef = models.CharField("Chef-Freigabe", max_length=20, choices=Freigabe.choices, default=Freigabe.OFFEN)
    freigabe_meister = models.CharField("Meister-Freigabe", max_length=20, choices=Freigabe.choices, default=Freigabe.OFFEN)
    angelegt_von = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                     related_name="+")
    angelegt_am = models.DateTimeField(auto_now_add=True)
    geaendert_am = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Auftrag"
        verbose_name_plural = "Aufträge"
        ordering = ["-aunr"]

    def __str__(self):
        return f"{self.aunr} – {self.projekt}"

    def get_absolute_url(self):
        return reverse("kalkulation:projekt", args=[self.projekt_id])

    @property
    def intern_freigegeben(self) -> bool:
        """Wie Makro: intern freigegeben erst mit Chef und Meister."""
        return self.freigabe_chef == self.Freigabe.FREIGEGEBEN and self.freigabe_meister == self.Freigabe.FREIGEGEBEN
