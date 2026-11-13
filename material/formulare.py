from django import forms

from projekte.formulare import DatumFeld

from .models import EINHEITEN, Material


PREISFELDER = {"ek_netto", "referenzpreis_brutto"}


def deutsche_zahl(wert, mindestens=0) -> str:
    """12.5000 -> „12,50“ (Preise), 19.00 -> „19“; keine überflüssigen Nullen."""
    text = format(wert.normalize() if hasattr(wert, "normalize") else wert, "f")
    ganz, _, komma = text.partition(".")
    komma = komma.rstrip("0").ljust(mindestens, "0")
    return f"{ganz},{komma}" if komma else ganz


class MaterialFormular(forms.ModelForm):
    class Meta:
        model = Material
        fields = ["materialnr", "bezeichnung", "produktgruppe", "untergruppe", "einheit", "staerke_mm", "format",
                  "lieferant", "ek_netto", "referenzpreis_brutto", "preisquelle", "preisstand", "preis_hinweis",
                  "lagerartikel", "lagerplatz", "mindestbestand", "zielbestand", "beschaffungsart",
                  "lieferzeit_tage", "hinweise", "aktiv"]
        widgets = {"hinweise": forms.Textarea(attrs={"rows": 3}), "preisstand": DatumFeld()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        def werte(feld):
            return sorted(set(Material.objects.values_list(feld, flat=True)) - {""})
        self.vorschlaege = {
            "produktgruppe": werte("produktgruppe"), "untergruppe": werte("untergruppe"),
            "einheit": sorted(set(EINHEITEN) | set(werte("einheit"))), "beschaffungsart": werte("beschaffungsart"),
            "lagerplatz": werte("lagerplatz"), "preisquelle": werte("preisquelle"),
        }
        for feld in self.vorschlaege:
            self.fields[feld].widget.attrs["list"] = f"liste-{feld}"
        from lieferanten.models import Lieferant
        lieferanten = Lieferant.objects.filter(aktiv=True)
        if self.instance.pk and self.instance.lieferant_id:
            lieferanten = lieferanten | Lieferant.objects.filter(pk=self.instance.lieferant_id)
        self.fields["lieferant"].queryset = lieferanten.order_by("name")
        self.fields["lieferant"].empty_label = "– kein Lieferant –"
        for feld in ("staerke_mm", "ek_netto", "referenzpreis_brutto", "mindestbestand", "zielbestand"):
            self.fields[feld].localize = True
            self.fields[feld].widget = forms.TextInput(attrs={"inputmode": "decimal"})
            self.fields[feld].widget.is_localized = True
            wert = self.initial.get(feld)
            if wert is not None and not self.is_bound:
                self.initial[feld] = deutsche_zahl(wert, mindestens=2 if feld in PREISFELDER else 0)

    def clean_materialnr(self):
        nr = self.cleaned_data["materialnr"].strip()
        andere = Material.objects.filter(materialnr__iexact=nr)
        if self.instance.pk:
            andere = andere.exclude(pk=self.instance.pk)
        if andere.exists():
            raise forms.ValidationError("Diese Material-Nr. ist schon vergeben.")
        return nr

    def clean(self):
        daten = super().clean()
        for feld in ("ek_netto", "referenzpreis_brutto", "mindestbestand", "zielbestand", "staerke_mm"):
            if daten.get(feld) is not None and daten[feld] < 0:
                self.add_error(feld, "Bitte keine negative Zahl.")
        return daten
