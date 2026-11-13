from django.db import models
from django.urls import reverse


class Lieferant(models.Model):
    """Bezugsquelle für Material. Wird nie gelöscht, nur inaktiv gesetzt."""

    name = models.CharField("Name / Firma", max_length=200, unique=True)
    ansprechpartner = models.CharField("Ansprechpartner", max_length=200, blank=True)
    telefon = models.CharField("Telefon", max_length=50, blank=True)
    email = models.EmailField("E-Mail", max_length=254, blank=True)
    strasse = models.CharField("Straße und Hausnummer", max_length=200, blank=True)
    plz = models.CharField("PLZ", max_length=10, blank=True)
    ort = models.CharField("Ort", max_length=100, blank=True)
    webseite = models.CharField("Webseite / Bestellportal", max_length=250, blank=True)
    unsere_kundennr = models.CharField("Unsere Kunden-Nr. beim Lieferanten", max_length=60, blank=True)
    zahlungsziel_tage = models.PositiveIntegerField("Zahlungsziel (Tage)", null=True, blank=True)
    skonto = models.CharField("Skonto", max_length=60, blank=True, help_text="z. B. 2 % bei 10 Tagen")
    hinweise = models.TextField("Hinweise", blank=True)
    aktiv = models.BooleanField("Aktiv", default=True)
    angelegt_am = models.DateTimeField("Angelegt am", auto_now_add=True)
    geaendert_am = models.DateTimeField("Geändert am", auto_now=True)

    class Meta:
        verbose_name = "Lieferant"
        verbose_name_plural = "Lieferanten"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("lieferanten:detail", args=[self.pk])
