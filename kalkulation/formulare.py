from django import forms

from material.models import Material
from rechnungen.formulare import komma_felder

from .models import Auftrag, Kalkulation, Stuecklistenposition


class PositionFormular(forms.Form):
    material = forms.ModelChoiceField(Material.objects.filter(aktiv=True).order_by("bezeichnung"), required=False,
                                      label="Material", empty_label="– freie Position (ohne Materialstamm) –")
    bezeichnung = forms.CharField(label="Bezeichnung (leer = aus Material)", required=False, max_length=250)
    menge = forms.DecimalField(label="Menge", decimal_places=3, min_value=0.001)
    einheit = forms.CharField(label="Einheit (leer = aus Material)", required=False, max_length=20)
    ek = forms.DecimalField(label="EK / Einheit netto (leer = aus Material)", required=False, decimal_places=4)
    status = forms.ChoiceField(label="Status", choices=Stuecklistenposition.Status.choices,
                               initial=Stuecklistenposition.Status.BENOETIGT)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material"].label_from_instance = lambda m: f"{m.materialnr} – {m.bezeichnung}"
        komma_felder(self, ["menge"])
        komma_felder(self, ["ek"], mindestens=2)


class KalkulationFormular(forms.ModelForm):
    GELD = ["material_manuell", "beschlaege", "lohn_satz", "maschinen", "montage", "fahrt", "fremd"]

    class Meta:
        model = Kalkulation
        fields = ["art", "material_manuell", "beschlaege", "lohn_std", "lohn_satz", "maschinen", "montage", "fahrt",
                  "fremd", "zuschlag", "risiko", "notiz"]
        widgets = {"notiz": forms.Textarea(attrs={"rows": 2}), "art": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        komma_felder(self, self.GELD, mindestens=2)
        komma_felder(self, ["lohn_std", "zuschlag", "risiko"])


class AuftragFormular(forms.ModelForm):
    class Meta:
        model = Auftrag
        fields = ["angebot_netto", "status", "termin", "leistung"]
        widgets = {"leistung": forms.Textarea(attrs={"rows": 2}), "status": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        komma_felder(self, ["angebot_netto"], mindestens=2)
