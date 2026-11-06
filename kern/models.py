from django.conf import settings
from django.db import models


class ProtokollGesperrt(Exception):
    """Protokolleinträge dürfen weder geändert noch gelöscht werden."""


class ProtokollQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ProtokollGesperrt("Protokolleinträge sind unveränderbar.")

    def delete(self):
        raise ProtokollGesperrt("Protokolleinträge können nicht gelöscht werden.")


class Protokolleintrag(models.Model):
    """Nur-Anfügen-Protokoll aller wichtigen Vorgänge (Grundlage für GoBD)."""

    zeitpunkt = models.DateTimeField(auto_now_add=True, db_index=True)
    benutzer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    benutzername = models.CharField(max_length=150, blank=True)
    aktion = models.CharField(max_length=50, db_index=True)
    gegenstand = models.CharField(max_length=200, blank=True)
    details = models.TextField(blank=True)

    objects = ProtokollQuerySet.as_manager()

    class Meta:
        verbose_name = "Protokolleintrag"
        verbose_name_plural = "Protokoll"
        ordering = ["-zeitpunkt", "-id"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ProtokollGesperrt("Protokolleinträge sind unveränderbar.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ProtokollGesperrt("Protokolleinträge können nicht gelöscht werden.")

    def __str__(self):
        return f"{self.zeitpunkt:%d.%m.%Y %H:%M} {self.benutzername} {self.aktion} {self.gegenstand}"


def protokolliere(aktion, gegenstand="", details="", benutzer=None):
    """Schreibt einen Eintrag ins Protokoll."""
    angemeldet = benutzer is not None and getattr(benutzer, "is_authenticated", False)
    return Protokolleintrag.objects.create(
        benutzer=benutzer if angemeldet else None,
        benutzername=benutzer.get_username() if angemeldet else "",
        aktion=aktion,
        gegenstand=str(gegenstand)[:200],
        details=details,
    )
