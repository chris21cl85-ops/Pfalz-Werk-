"""Meldungen vom Handy (wie „Melden“ im Excel-Handy-Abgleich → Blatt Aufgaben)."""
from django.conf import settings
from django.db import models


class Meldung(models.Model):
    class Art(models.TextChoices):
        MATERIAL = "Material fehlt", "Material fehlt / nachbestellen"
        BRUCH = "Bruch / Schaden", "Bruch / Schaden"
        MASCHINE = "Maschine / Werkzeug", "Maschine / Werkzeug defekt"
        KUNDE = "Kunde / Baustelle", "Kunde / Baustelle"
        SONSTIGES = "Sonstiges", "Sonstiges"

    art = models.CharField("Was ist los?", max_length=30, choices=Art.choices, default=Art.SONSTIGES)
    projekt = models.ForeignKey("projekte.Projekt", on_delete=models.PROTECT, null=True, blank=True, related_name="meldungen")
    text = models.CharField("Beschreibung", max_length=500)
    foto = models.CharField("Foto (Datei im Datenordner)", max_length=200, blank=True)
    von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    am = models.DateTimeField(auto_now_add=True)
    erledigt_am = models.DateTimeField(null=True, blank=True)
    erledigt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="+")
    antwort = models.CharField("Antwort / erledigt mit", max_length=300, blank=True)

    class Meta:
        verbose_name = "Meldung"
        verbose_name_plural = "Meldungen"
        ordering = ["erledigt_am", "-am"]

    def __str__(self):
        return f"{self.art}: {self.text[:40]}"
