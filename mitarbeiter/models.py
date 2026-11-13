from django.conf import settings
from django.db import models
from django.urls import reverse


class Mitarbeiter(models.Model):
    """Person im Betrieb (Werkstatt, Büro, Montage). Optional mit eigenem Zugang verknüpft."""

    kuerzel = models.CharField("Kürzel", max_length=10, unique=True)
    name = models.CharField("Name", max_length=150)
    rolle = models.CharField("Rolle im Betrieb", max_length=60, blank=True,
                             help_text="z. B. Meister, Geselle, Azubi, AV, CNC, Einkauf")
    telefon = models.CharField("Telefon", max_length=50, blank=True)
    team_taeglich_verfuegbar = models.BooleanField("Team-täglich verfügbar", default=True)
    kann_montage_leiten = models.BooleanField("Kann Montage leiten", default=False)
    verfuegbarkeit = models.CharField("Verfügbarkeit", max_length=100, blank=True)
    arbeitstage = models.CharField("Arbeitstage", max_length=100, blank=True)
    arbeitszeit = models.CharField("Arbeitszeit", max_length=100, blank=True)
    arbeitszeitmodell = models.CharField("Arbeitszeitmodell", max_length=100, blank=True)
    einsatzmuster = models.CharField("Einsatzmuster", max_length=150, blank=True)
    einschraenkung = models.CharField("Abwesenheit / Einschränkung", max_length=250, blank=True)
    eintritt = models.DateField("Eintritt", null=True, blank=True)
    wochenstunden = models.DecimalField("Wochenstunden", max_digits=5, decimal_places=2, null=True, blank=True)
    urlaubstage = models.DecimalField("Urlaubstage im Jahr", max_digits=5, decimal_places=1, null=True, blank=True)
    stundensatz = models.DecimalField("Stundensatz für Kalkulation (€)", max_digits=8, decimal_places=2,
                                      null=True, blank=True)
    benutzer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="mitarbeiter", verbose_name="Zugang zum Programm")
    hinweise = models.TextField("Hinweise", blank=True)
    aktiv = models.BooleanField("Aktiv", default=True)
    angelegt_am = models.DateTimeField("Angelegt am", auto_now_add=True)
    geaendert_am = models.DateTimeField("Geändert am", auto_now=True)

    class Meta:
        verbose_name = "Mitarbeiter"
        verbose_name_plural = "Mitarbeiter"
        ordering = ["name"]

    def __str__(self):
        return f"{self.kuerzel} – {self.name}"

    def get_absolute_url(self):
        return reverse("mitarbeiter:detail", args=[self.pk])
