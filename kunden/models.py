import re

from django.db import models
from django.urls import reverse


class Kunde(models.Model):
    """Kunde der Schreinerei. Wird nie gelöscht, nur auf „Inaktiv“ gesetzt."""

    class Status(models.TextChoices):
        AKTIV = "Aktiv", "Aktiv"
        INAKTIV = "Inaktiv", "Inaktiv"

    kundennr = models.CharField("Kunden-Nr.", max_length=30, unique=True)
    name = models.CharField("Name / Firma", max_length=200)
    kundenart = models.CharField("Kundenart", max_length=30, default="Unbekannt", blank=True)
    ansprechpartner = models.CharField("Ansprechpartner", max_length=200, blank=True)
    telefon = models.CharField("Telefon", max_length=50, blank=True)
    email = models.EmailField("E-Mail", max_length=254, blank=True)
    strasse = models.CharField("Straße und Hausnummer", max_length=200, blank=True)
    plz = models.CharField("PLZ", max_length=10, blank=True)
    ort = models.CharField("Ort", max_length=100, blank=True)
    adresse_original = models.TextField("Adresse wie in Excel", blank=True,
                                        help_text="Unveränderte Adresse aus der Excel-Fassung.")
    hinweise = models.TextField("Hinweise", blank=True)
    status = models.CharField("Status", max_length=10, choices=Status.choices, default=Status.AKTIV)
    angelegt_am = models.DateTimeField("Angelegt am", auto_now_add=True)
    geaendert_am = models.DateTimeField("Geändert am", auto_now=True)

    class Meta:
        verbose_name = "Kunde"
        verbose_name_plural = "Kunden"
        ordering = ["name"]

    def __str__(self):
        return f"{self.kundennr} – {self.name}"

    def get_absolute_url(self):
        return reverse("kunden:detail", args=[self.pk])

    @property
    def ist_aktiv(self):
        return self.status == self.Status.AKTIV

    @property
    def adresse_einzeilig(self):
        teile = [self.strasse, " ".join(t for t in (self.plz, self.ort) if t)]
        text = ", ".join(t for t in teile if t)
        return text or self.adresse_original.replace("\n", ", ")


_PLZ_ORT = re.compile(r"^(?P<strasse>.*?)[,\n;]?\s*(?P<plz>\d{5})\s+(?P<ort>[^,\n]+?)\s*$", re.S)


def adresse_zerlegen(text: str) -> dict:
    """Zerlegt „Hauptstr. 5, 67433 Neustadt“ in Straße, PLZ, Ort. Klappt es nicht, bleibt alles leer."""
    text = (text or "").strip()
    treffer = _PLZ_ORT.match(text)
    if not treffer:
        return {"strasse": "", "plz": "", "ort": ""}
    strasse = treffer["strasse"].strip().rstrip(",;").strip()
    return {"strasse": strasse, "plz": treffer["plz"], "ort": treffer["ort"].strip()}


def naechste_kundennr() -> str:
    """Vorschlag für die nächste freie Kunden-Nr. im bisherigen Muster (z. B. K-007 -> K-008, 41 -> 42)."""
    muster = re.compile(r"^(?P<vorne>.*?)(?P<zahl>\d+)$")
    beste = None
    for nr in Kunde.objects.values_list("kundennr", flat=True):
        t = muster.match(nr)
        if t and (beste is None or int(t["zahl"]) > int(beste["zahl"])):
            beste = t
    if beste is None:
        return "1"
    zahl = str(int(beste["zahl"]) + 1).zfill(len(beste["zahl"]))
    vorschlag = f"{beste['vorne']}{zahl}"
    while Kunde.objects.filter(kundennr=vorschlag).exists():
        zahl = str(int(zahl) + 1).zfill(len(beste["zahl"]))
        vorschlag = f"{beste['vorne']}{zahl}"
    return vorschlag
