"""Möbelrechner: Regelwerk (Blatt „Möbel-Regeln“) und gespeicherte Möbel-Positionen (Blatt „Möbel-Positionen“)."""
from django.conf import settings
from django.db import models
from django.urls import reverse

from . import rechner


def standard_werte():
    return dict(rechner.STANDARD_REGELN)


def standard_baender():
    return [list(x) for x in rechner.STANDARD_BAENDER]


def standard_fachboden():
    return [list(x) for x in rechner.STANDARD_FACHBODEN]


def standard_verbinder():
    return {k: list(v) for k, v in rechner.STANDARD_VERBINDER.items()}


def standard_systeme():
    return {k: list(v) for k, v in rechner.STANDARD_SYSTEME.items()}


def standard_material():
    return dict(rechner.STANDARD_MATERIAL)


def standard_nennlaengen():
    return list(rechner.STANDARD_NENNLAENGEN)


def standard_oberflaechen():
    return [list(x) for x in rechner.STANDARD_OBERFLAECHEN]


def leere_liste():
    return []


class Regelwerk(models.Model):
    """Werkstatt-Standards – genau ein Datensatz. Startwerte wie im Makro, per Excel-Import oder Seite änderbar."""

    werte = models.JSONField(default=standard_werte)
    baender = models.JSONField(default=standard_baender)
    fachboden = models.JSONField(default=standard_fachboden)
    verbinder = models.JSONField(default=standard_verbinder)
    systeme = models.JSONField(default=standard_systeme)
    standardmaterial = models.JSONField(default=standard_material)
    nennlaengen = models.JSONField(default=standard_nennlaengen)
    oberflaechen = models.JSONField(default=standard_oberflaechen)
    im_programm_geaendert = models.BooleanField(default=False)
    geaendert_am = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Möbel-Regeln"
        verbose_name_plural = "Möbel-Regeln"

    @classmethod
    def laden(cls):
        objekt, _ = cls.objects.get_or_create(pk=1)
        return objekt

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def als_regeln(self) -> rechner.Regeln:
        werte = dict(rechner.STANDARD_REGELN)
        werte.update({k: v for k, v in self.werte.items() if v not in (None, "")})
        return rechner.Regeln(werte=werte, baender=[tuple(x) for x in self.baender],
                              fachboden=[tuple(x) for x in self.fachboden],
                              verbinder={k: tuple(v) for k, v in self.verbinder.items()}, systeme=dict(self.systeme),
                              nennlaengen=[float(x) for x in (self.nennlaengen or rechner.STANDARD_NENNLAENGEN)],
                              material={**rechner.STANDARD_MATERIAL, **(self.standardmaterial or {})},
                              oberflaechen=self.oberflaechen or [list(x) for x in rechner.STANDARD_OBERFLAECHEN])


class MoebelPosition(models.Model):
    class Status(models.TextChoices):
        ENTWURF = "Gespeichert", "Gespeichert"
        STUECKLISTE = "In Stückliste", "In Stückliste (Geplant)"
        ARBEITSGAENGE = "In Stückliste + Arbeitsgänge", "In Stückliste + Arbeitsgänge"

    projekt = models.ForeignKey("projekte.Projekt", on_delete=models.PROTECT, related_name="moebel")
    pos = models.CharField("Position", max_length=10)
    bezeichnung = models.CharField("Bezeichnung", max_length=200)
    eingaben = models.JSONField(default=dict)
    ergebnis = models.JSONField(default=dict)
    status = models.CharField("Status", max_length=40, choices=Status.choices, default=Status.ENTWURF)
    version = models.PositiveIntegerField("Version", default=1)
    aenderungen = models.JSONField("Änderungen (neueste zuerst)", default=leere_liste, blank=True)
    stueckliste_veraltet = models.BooleanField("Nach Übernahme geändert", default=False)
    gespeichert_von = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                        related_name="+")
    gespeichert_am = models.DateTimeField("Gespeichert am", auto_now=True)

    class Meta:
        verbose_name = "Möbel-Position"
        verbose_name_plural = "Möbel-Positionen"
        ordering = ["projekt__projektnr", "pos"]
        constraints = [models.UniqueConstraint(fields=["projekt", "pos"], name="moebel_pos_je_projekt")]

    def __str__(self):
        return f"{self.positions_id} {self.bezeichnung}"

    @property
    def positions_id(self) -> str:
        """Wie PositionsId() im Makro: Projekt-ID + „-“ + Position (z. B. P-2026-001-M01)."""
        return f"{self.projekt.projektnr}-{self.pos}"

    def get_absolute_url(self):
        return reverse("moebel:detail", args=[self.pk])

    @property
    def masse(self) -> str:
        e = self.eingaben
        return f"{e.get('breite', '')} × {e.get('hoehe', '')} × {e.get('tiefe', '')} mm"
