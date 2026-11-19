from django import forms
from django.db.models import Q

from produktion.models import Arbeitsgang
from projekte.models import ABGESCHLOSSEN, Projekt
from rechnungen.formulare import komma_felder

from .models import Arbeitsvertrag, Zeitbuchung

DATUM = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
ZEIT = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")


class BuchungFormular(forms.Form):
    datum = forms.DateField(label="Datum", widget=DATUM)
    beginn = forms.TimeField(label="Von", widget=ZEIT, required=False)
    ende = forms.TimeField(label="Bis", widget=ZEIT, required=False)
    pause_min = forms.IntegerField(label="Pause (Min.)", min_value=0, max_value=240, required=False, initial=0)
    stunden = forms.DecimalField(label="… oder Stunden", required=False, min_value=0, max_value=16, decimal_places=2)
    projekt = forms.ModelChoiceField(Projekt.objects.none(), label="Projekt", required=False,
                                     empty_label="– ohne Projekt (Werkstatt allgemein) –")
    arbeitsgang = forms.ModelChoiceField(Arbeitsgang.objects.none(), label="Arbeitsgang (optional)", required=False,
                                         empty_label="– kein bestimmter Arbeitsgang –")
    taetigkeit = forms.ChoiceField(label="Tätigkeit", choices=Zeitbuchung.Taetigkeit.choices)
    notiz = forms.CharField(label="Notiz", max_length=250, required=False)

    def __init__(self, *args, mitarbeiter=None, **kwargs):
        super().__init__(*args, **kwargs)
        offen = Q()
        for s in ABGESCHLOSSEN:
            offen &= ~Q(status__iexact=s)
        self.fields["projekt"].queryset = Projekt.objects.filter(offen).order_by("-projektnr")
        self.fields["projekt"].label_from_instance = lambda p: f"{p.projektnr} – {p.name}"
        ags = Arbeitsgang.objects.exclude(status="Fertig").select_related("projekt").order_by("projekt__projektnr", "pk")
        if mitarbeiter is not None:  # eigene Arbeitsgänge zuerst
            eigene = list(ags.filter(mitarbeiter=mitarbeiter))
            andere = list(ags.exclude(mitarbeiter=mitarbeiter))
            self.fields["arbeitsgang"].queryset = ags
            self.fields["arbeitsgang"].choices = [("", "– kein bestimmter Arbeitsgang –")] + [
                (a.pk, f"{'★ ' if a in eigene else ''}{a.projekt.projektnr} · {a.name}") for a in eigene + andere]
        else:
            self.fields["arbeitsgang"].queryset = ags
            self.fields["arbeitsgang"].label_from_instance = lambda a: f"{a.projekt.projektnr} · {a.name}"
        komma_felder(self, ["stunden"])

    def clean(self):
        d = super().clean()
        von, bis, std = d.get("beginn"), d.get("ende"), d.get("stunden")
        if (von and not bis) or (bis and not von):
            self.add_error("ende" if von else "beginn", "Von und Bis zusammen eintragen – oder nur Stunden.")
        elif not (von and bis) and not std:
            self.add_error("stunden", "Von/Bis oder Stunden eintragen.")
        ag, p = d.get("arbeitsgang"), d.get("projekt")
        if ag and p and ag.projekt_id != p.pk:
            self.add_error("arbeitsgang", "Der Arbeitsgang gehört zu einem anderen Projekt.")
        return d


class VertragFormular(forms.ModelForm):
    ZAHLEN = ["soll_mo", "soll_di", "soll_mi", "soll_do", "soll_fr", "urlaub_jahr", "zeitkonto_start", "brutto_monat",
              "stundenlohn"]

    class Meta:
        model = Arbeitsvertrag
        fields = ["art", "status", "eintritt", "befristet_bis", "probezeit_bis", "soll_mo", "soll_di", "soll_mi",
                  "soll_do", "soll_fr", "urlaub_jahr", "zeitkonto_start", "brutto_monat", "stundenlohn",
                  "kuendigungsfrist", "taetigkeit", "arbeitsort", "vermerk"]
        widgets = {"eintritt": DATUM, "befristet_bis": DATUM, "probezeit_bis": DATUM}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        komma_felder(self, self.ZAHLEN)

    def clean(self):
        d = super().clean()
        if d.get("art") == Arbeitsvertrag.Art.BEFRISTET and not d.get("befristet_bis"):
            self.add_error("befristet_bis", "Bei befristeten Verträgen das Enddatum eintragen.")
        return d
