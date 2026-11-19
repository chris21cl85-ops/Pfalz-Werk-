from django import forms

from .models import Inventur

DATUM = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class InventurFormular(forms.ModelForm):
    class Meta:
        model = Inventur
        fields = ["art", "stichtag", "lagerbereich", "verantwortlich", "blind", "toleranz_prozent", "toleranz_wert", "hinweis"]
        widgets = {"stichtag": DATUM}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from material.models import Material
        from rechnungen.formulare import komma_felder
        plaetze = sorted(set(Material.objects.filter(aktiv=True, lagerartikel=True).exclude(lagerplatz="")
                             .values_list("lagerplatz", flat=True)))
        self.fields["lagerbereich"] = forms.ChoiceField(label="Lagerbereich", required=False,
                                                        choices=[("", "Alle")] + [(x, x) for x in plaetze])
        komma_felder(self, ["toleranz_prozent", "toleranz_wert"])
