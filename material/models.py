from django.db import models
from django.urls import reverse

EINHEITEN = ["Stk", "m", "m²", "m³", "lfm", "kg", "l", "Pkg", "Platte", "Rolle", "Satz"]


class Material(models.Model):
    """Materialstamm (Platten, Beschläge, Kanten …). Wird nie gelöscht, nur inaktiv gesetzt."""

    materialnr = models.CharField("Material-Nr.", max_length=40, unique=True)
    bezeichnung = models.CharField("Bezeichnung", max_length=250)
    produktgruppe = models.CharField("Produktgruppe", max_length=100, blank=True)
    untergruppe = models.CharField("Untergruppe", max_length=100, blank=True)
    einheit = models.CharField("Einheit", max_length=20, blank=True)
    staerke_mm = models.DecimalField("Stärke (mm)", max_digits=8, decimal_places=2, null=True, blank=True)
    format = models.CharField("Format / Abmessung", max_length=100, blank=True)
    ek_netto = models.DecimalField("Einkaufspreis netto (€)", max_digits=12, decimal_places=4, null=True, blank=True)
    referenzpreis_brutto = models.DecimalField("Referenzpreis brutto (€)", max_digits=12, decimal_places=4,
                                               null=True, blank=True)
    preisquelle = models.CharField("Preisquelle", max_length=100, blank=True)
    preisstand = models.DateField("Preisstand", null=True, blank=True)
    preis_hinweis = models.CharField("Preishinweis", max_length=250, blank=True)
    lagerartikel = models.BooleanField("Lagerartikel", default=False)
    lagerplatz = models.CharField("Lagerplatz", max_length=100, blank=True)
    mindestbestand = models.DecimalField("Mindestbestand", max_digits=12, decimal_places=3, null=True, blank=True)
    zielbestand = models.DecimalField("Zielbestand", max_digits=12, decimal_places=3, null=True, blank=True)
    beschaffungsart = models.CharField("Beschaffungsart", max_length=100, blank=True)
    lieferzeit_tage = models.PositiveIntegerField("Lieferzeit (Tage)", null=True, blank=True)
    hinweise = models.TextField("Hinweise", blank=True)
    aktiv = models.BooleanField("Aktiv", default=True)
    angelegt_am = models.DateTimeField("Angelegt am", auto_now_add=True)
    geaendert_am = models.DateTimeField("Geändert am", auto_now=True)

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Material"
        ordering = ["produktgruppe", "bezeichnung"]

    def __str__(self):
        return f"{self.materialnr} – {self.bezeichnung}"

    def get_absolute_url(self):
        return reverse("material:detail", args=[self.pk])
