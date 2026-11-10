from django.db import models
from django.urls import reverse

from kunden.models import Kunde

# Vorschläge wie in der Excel-Fassung; freie Eingabe bleibt möglich
STATUS_VORSCHLAEGE = ["Planung", "Angebot", "Auftrag", "In Arbeit", "Montage", "Abgeschlossen", "Storniert"]
ABGESCHLOSSEN = ["abgeschlossen", "erledigt", "storniert", "abgerechnet", "archiviert"]


class Projekt(models.Model):
    """Auftrag / Baustelle eines Kunden. Wird nie gelöscht."""

    projektnr = models.CharField("Projekt-Nr.", max_length=40, unique=True)
    name = models.CharField("Projektname", max_length=200)
    kunde = models.ForeignKey(Kunde, on_delete=models.PROTECT, related_name="projekte", verbose_name="Kunde")
    projektart = models.CharField("Projektart", max_length=80, default="Nicht zugeordnet", blank=True)
    status = models.CharField("Status", max_length=40, default="Planung")
    phase = models.CharField("Phase", max_length=80, blank=True)
    projektpate = models.CharField("Projektpate", max_length=100, blank=True)
    startdatum = models.DateField("Startdatum", null=True, blank=True)
    zieldatum = models.DateField("Zieldatum", null=True, blank=True)
    risiko = models.CharField("Risiko", max_length=200, blank=True)
    naechster_schritt = models.CharField("Nächster Schritt", max_length=300, blank=True)
    anfrage_id = models.CharField("Anfrage-ID", max_length=40, blank=True)
    hinweise = models.TextField("Hinweise", blank=True)
    angelegt_am = models.DateTimeField("Angelegt am", auto_now_add=True)
    geaendert_am = models.DateTimeField("Geändert am", auto_now=True)

    class Meta:
        verbose_name = "Projekt"
        verbose_name_plural = "Projekte"
        ordering = ["-projektnr"]

    def __str__(self):
        return f"{self.projektnr} – {self.name}"

    def get_absolute_url(self):
        return reverse("projekte:detail", args=[self.pk])

    @property
    def ist_offen(self):
        return self.status.strip().lower() not in ABGESCHLOSSEN
