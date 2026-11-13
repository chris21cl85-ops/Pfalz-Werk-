from django import forms

from konten.models import Benutzer
from projekte.formulare import DatumFeld

from .models import Mitarbeiter


class MitarbeiterFormular(forms.ModelForm):
    class Meta:
        model = Mitarbeiter
        fields = ["kuerzel", "name", "rolle", "telefon", "team_taeglich_verfuegbar", "kann_montage_leiten",
                  "verfuegbarkeit", "arbeitstage", "arbeitszeit", "arbeitszeitmodell", "einsatzmuster",
                  "einschraenkung", "eintritt", "wochenstunden", "urlaubstage",
                  "stundensatz", "benutzer", "hinweise", "aktiv"]
        widgets = {"hinweise": forms.Textarea(attrs={"rows": 3}), "eintritt": DatumFeld()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        frei = Benutzer.objects.filter(mitarbeiter__isnull=True)
        if self.instance.pk and self.instance.benutzer_id:
            frei = frei | Benutzer.objects.filter(pk=self.instance.benutzer_id)
        self.fields["benutzer"].queryset = frei.order_by("username")
        self.fields["benutzer"].empty_label = "– kein Zugang –"
        from material.formulare import deutsche_zahl
        for feld in ("wochenstunden", "urlaubstage", "stundensatz"):
            self.fields[feld].localize = True
            self.fields[feld].widget = forms.TextInput(attrs={"inputmode": "decimal"})
            self.fields[feld].widget.is_localized = True
            wert = self.initial.get(feld)
            if wert is not None and not self.is_bound:
                self.initial[feld] = deutsche_zahl(wert, mindestens=2 if feld == "stundensatz" else 0)
        werte = lambda f: sorted(set(Mitarbeiter.objects.values_list(f, flat=True)) - {""})  # noqa: E731
        self.vorschlaege = {"rolle": sorted(set(werte("rolle")) | {"Meister", "Geselle", "Azubi", "Helfer"}),
                            "verfuegbarkeit": werte("verfuegbarkeit"), "arbeitstage": werte("arbeitstage"),
                            "arbeitszeit": werte("arbeitszeit")}
        for feld in self.vorschlaege:
            self.fields[feld].widget.attrs["list"] = f"liste-{feld}"

    def clean_kuerzel(self):
        k = self.cleaned_data["kuerzel"].strip().upper()
        andere = Mitarbeiter.objects.filter(kuerzel__iexact=k)
        if self.instance.pk:
            andere = andere.exclude(pk=self.instance.pk)
        if andere.exists():
            raise forms.ValidationError("Dieses Kürzel ist schon vergeben.")
        return k

    def clean(self):
        daten = super().clean()
        for feld in ("wochenstunden", "urlaubstage", "stundensatz"):
            if daten.get(feld) is not None and daten[feld] < 0:
                self.add_error(feld, "Bitte keine negative Zahl.")
        if daten.get("wochenstunden") and daten["wochenstunden"] > 60:
            self.add_error("wochenstunden", "Mehr als 60 Wochenstunden? Bitte prüfen.")
        return daten
