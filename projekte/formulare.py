from django import forms

from kunden.models import Kunde

from .models import STATUS_VORSCHLAEGE, Projekt


class DatumFeld(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class ProjektFormular(forms.ModelForm):
    class Meta:
        model = Projekt
        fields = ["projektnr", "name", "kunde", "projektart", "status", "phase", "projektpate",
                  "startdatum", "zieldatum", "naechster_schritt", "risiko", "anfrage_id", "hinweise"]
        widgets = {"hinweise": forms.Textarea(attrs={"rows": 4}),
                   "startdatum": DatumFeld(), "zieldatum": DatumFeld()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kunden = Kunde.objects.filter(status=Kunde.Status.AKTIV)
        if self.instance.pk:  # bisheriger Kunde bleibt wählbar, auch wenn inaktiv
            kunden = Kunde.objects.filter(pk=self.instance.kunde_id) | kunden
        self.fields["kunde"].queryset = kunden.order_by("name")
        self.fields["kunde"].empty_label = "– Kunde wählen –"
        self.vorschlaege = {
            "status": sorted(set(STATUS_VORSCHLAEGE) | set(Projekt.objects.values_list("status", flat=True)) - {""}),
            "projektart": sorted(set(Projekt.objects.values_list("projektart", flat=True)) - {""}),
            "projektpate": sorted(set(Projekt.objects.values_list("projektpate", flat=True)) - {""}),
        }
        for feld in self.vorschlaege:
            self.fields[feld].widget.attrs["list"] = f"liste-{feld}"

    def clean_projektnr(self):
        nr = self.cleaned_data["projektnr"].strip()
        andere = Projekt.objects.filter(projektnr__iexact=nr)
        if self.instance.pk:
            andere = andere.exclude(pk=self.instance.pk)
        if andere.exists():
            raise forms.ValidationError("Diese Projekt-Nr. ist schon vergeben.")
        return nr

    def clean(self):
        daten = super().clean()
        start, ziel = daten.get("startdatum"), daten.get("zieldatum")
        if start and ziel and ziel < start:
            self.add_error("zieldatum", "Das Zieldatum liegt vor dem Startdatum.")
        return daten
