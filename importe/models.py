from django.conf import settings
from django.db import models


class Importlauf(models.Model):
    """Ein Versuch, eine Excel-Datei einzulesen – mit Probelauf und Bericht."""

    class Status(models.TextChoices):
        HOCHGELADEN = "hochgeladen", "Hochgeladen"
        PROBELAUF = "probelauf", "Probelauf geprüft"
        UEBERNOMMEN = "uebernommen", "Übernommen"
        FEHLER = "fehler", "Fehler"

    zeitpunkt = models.DateTimeField(auto_now_add=True)
    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    dateiname = models.CharField(max_length=255)
    gespeichert_als = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.HOCHGELADEN)
    bericht = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Importlauf"
        verbose_name_plural = "Importläufe"
        ordering = ["-zeitpunkt"]

    def __str__(self):
        return f"{self.dateiname} ({self.get_status_display()})"
