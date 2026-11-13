from django import forms

from .models import Lieferant


class LieferantFormular(forms.ModelForm):
    class Meta:
        model = Lieferant
        fields = ["name", "ansprechpartner", "telefon", "email", "strasse", "plz", "ort", "webseite",
                  "unsere_kundennr", "zahlungsziel_tage", "skonto", "hinweise", "aktiv"]
        widgets = {"hinweise": forms.Textarea(attrs={"rows": 4})}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        andere = Lieferant.objects.filter(name__iexact=name)
        if self.instance.pk:
            andere = andere.exclude(pk=self.instance.pk)
        if andere.exists():
            raise forms.ValidationError("Diesen Lieferanten gibt es schon.")
        return name

    def clean_plz(self):
        plz = self.cleaned_data["plz"].strip()
        if plz and not (plz.isdigit() and len(plz) == 5):
            raise forms.ValidationError("Die PLZ hat in Deutschland 5 Ziffern.")
        return plz
