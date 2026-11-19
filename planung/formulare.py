from django import forms

from mitarbeiter.models import Mitarbeiter
from projekte.models import Projekt

from .models import FAHRZEUGE, TEAMARTEN, Abwesenheit, Montage, Team, Termin

DATUM = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
ZEIT = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")


def _ma(required=True, label="Mitarbeiter"):
    f = forms.ModelChoiceField(Mitarbeiter.objects.filter(aktiv=True).order_by("name"), label=label, required=required,
                               empty_label="– wählen –")
    f.label_from_instance = lambda m: m.name
    return f


class TeamFormular(forms.Form):
    name = forms.CharField(label="Teamname", max_length=100)
    art = forms.ChoiceField(label="Teamart", choices=[(a, a) for a in TEAMARTEN], initial="Montage")


class AbwesenheitFormular(forms.Form):
    mitarbeiter = _ma()
    von = forms.DateField(label="Von", widget=DATUM)
    bis = forms.DateField(label="Bis (gleicher Tag = eintägig)", widget=DATUM, required=False)
    art = forms.ChoiceField(label="Zeitart", choices=Abwesenheit.Art.choices)
    status = forms.ChoiceField(label="Status", choices=Abwesenheit.Status.choices[:2], initial="Freigegeben")
    stunden = forms.DecimalField(label="Stunden je Tag (leer = ganzer Tag)", required=False, min_value=0.25, max_value=12,
                                 decimal_places=2)
    hinweis = forms.CharField(label="Hinweis", max_length=250, required=False)

    def __init__(self, *args, leitung=True, eigener=None, **kwargs):
        super().__init__(*args, **kwargs)
        from rechnungen.formulare import komma_felder
        komma_felder(self, ["stunden"])
        if not leitung:  # Mitarbeiter beantragen nur für sich
            del self.fields["status"]
            self.fields["mitarbeiter"].queryset = Mitarbeiter.objects.filter(pk=getattr(eigener, "pk", None))
            self.fields["mitarbeiter"].initial = eigener

    def clean(self):
        d = super().clean()
        if d.get("von") and not d.get("bis"):
            d["bis"] = d["von"]
        if d.get("von") and d.get("bis") and d["bis"] < d["von"]:
            self.add_error("bis", "„Bis“ liegt vor „Von“.")
        return d


class MontageFormular(forms.ModelForm):
    fahrzeug = forms.ChoiceField(label="Fahrzeug", required=False)

    class Meta:
        model = Montage
        fields = ["datum", "beginn", "ende", "team", "fahrzeug", "adresse", "aufgaben", "material", "werkzeug", "hinweise"]
        widgets = {"datum": DATUM, "beginn": ZEIT, "ende": ZEIT}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = Team.objects.filter(aktiv=True)
        self.fields["team"].required = True
        self.fields["team"].empty_label = "– Team wählen –"
        fz = list(FAHRZEUGE)
        for f in Montage.objects.exclude(fahrzeug="").values_list("fahrzeug", flat=True).distinct():
            if f not in fz:
                fz.append(f)
        self.fields["fahrzeug"].choices = [("", "– ohne –")] + [(f, f) for f in fz]

    def clean(self):
        d = super().clean()
        if d.get("beginn") and d.get("ende") and d["ende"] <= d["beginn"]:
            self.add_error("ende", "Ende muss nach dem Beginn liegen.")
        return d


class TerminFormular(forms.Form):
    mitarbeiter = _ma(required=False, label="Mitarbeiter")
    team = forms.ModelChoiceField(Team.objects.filter(aktiv=True), label="… oder ganzes Team", required=False,
                                  empty_label="– kein Team –")
    datum = forms.DateField(label="Datum", widget=DATUM)
    beginn = forms.TimeField(label="Start", widget=ZEIT, required=False)
    ende = forms.TimeField(label="Ende", widget=ZEIT, required=False)
    art = forms.ChoiceField(label="Terminart", choices=[c for c in Termin.Art.choices if c[0] != "Montage"])
    aufgabe = forms.CharField(label="Aufgabe", max_length=200)
    projekt = forms.ModelChoiceField(Projekt.objects.order_by("-projektnr"), label="Projekt (optional)", required=False,
                                     empty_label="– ohne Projekt –")
    ort = forms.CharField(label="Ort", max_length=200, required=False)

    def clean(self):
        d = super().clean()
        if not d.get("mitarbeiter") and not d.get("team"):
            self.add_error("mitarbeiter", "Mitarbeiter oder Team wählen.")
        if d.get("beginn") and d.get("ende") and d["ende"] <= d["beginn"]:
            self.add_error("ende", "Ende muss nach dem Start liegen.")
        return d
