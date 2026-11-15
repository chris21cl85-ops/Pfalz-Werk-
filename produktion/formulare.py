from django import forms

from mitarbeiter.models import Mitarbeiter
from rechnungen.formulare import komma_felder

from .models import Arbeitsgang, Route, Vorlage

DATUM = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def _ma_feld(label, required=False):
    feld = forms.ModelChoiceField(Mitarbeiter.objects.filter(aktiv=True).order_by("name"), label=label,
                                  required=required, empty_label="– niemand –")
    feld.label_from_instance = lambda m: m.name
    return feld


class PlanenFormular(forms.Form):
    start = forms.DateField(label="Fertigungsstart", widget=DATUM)
    mitarbeiter = _ma_feld("Mitarbeiter (nur wo noch leer)")


class RueckmeldeFormular(forms.Form):
    stunden = forms.DecimalField(label="Stunden heute", required=False, min_value=0, max_value=24, decimal_places=2)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        komma_felder(self, ["stunden"])
        self.fields["stunden"].widget.attrs.update({"placeholder": "z. B. 2,5", "style": "max-width:110px"})


class RouteFormular(forms.Form):
    route = forms.ModelChoiceField(Route.objects.all(), label="Routenvorlage", empty_label="– Route wählen –")
    bauteil = forms.CharField(label="Bauteil / Baugruppe (z. B. „Küche Unterschränke“)", max_length=150, required=False)


class EinzelFormular(forms.Form):
    vorlage = forms.ModelChoiceField(Vorlage.objects.all(), label="Arbeitsgang aus der Bibliothek",
                                     empty_label="– Arbeitsgang wählen –")
    bauteil = forms.CharField(label="Bauteil / Bereich", max_length=150, required=False)
    plan_std = forms.DecimalField(label="Plan-Stunden", required=False, min_value=0, decimal_places=2)
    mitarbeiter = _ma_feld("Mitarbeiter")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vorlage"].label_from_instance = lambda v: f"{v.code} – {v.name} ({v.typ})"
        komma_felder(self, ["plan_std"])


class QMFormular(forms.Form):
    ergebnis = forms.ChoiceField(label="Endkontrolle", widget=forms.RadioSelect, choices=[
        ("Bestanden", "Bestanden – QM freigeben"), ("Nicht bestanden", "Nicht bestanden – Nacharbeit anlegen")])
    abweichung = forms.CharField(label="Abweichung / Mangel (bei „Nicht bestanden“)", max_length=300, required=False)

    def clean(self):
        d = super().clean()
        if d.get("ergebnis") == "Nicht bestanden" and not (d.get("abweichung") or "").strip():
            self.add_error("abweichung", "Kurz beschreiben, was fehlt.")
        return d


class ArbeitsgangFormular(forms.ModelForm):
    class Meta:
        model = Arbeitsgang
        fields = ["name", "bereich", "mitarbeiter", "plan_start", "plan_ende", "plan_std", "prioritaet", "wartezeit_std",
                  "problem", "bemerkung"]
        widgets = {"plan_start": DATUM, "plan_ende": DATUM}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mitarbeiter"].queryset = Mitarbeiter.objects.filter(aktiv=True).order_by("name")
        self.fields["mitarbeiter"].label_from_instance = lambda m: m.name
        komma_felder(self, ["plan_std", "wartezeit_std"])

    def clean(self):
        d = super().clean()
        if d.get("plan_start") and d.get("plan_ende") and d["plan_ende"] < d["plan_start"]:
            self.add_error("plan_ende", "Planende liegt vor dem Planstart.")
        return d
