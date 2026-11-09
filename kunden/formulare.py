from django import forms

from .models import Kunde

KUNDENARTEN = ["Privat", "Gewerbe", "Öffentlich", "Unbekannt"]


class KundeFormular(forms.ModelForm):
    class Meta:
        model = Kunde
        fields = ["kundennr", "name", "kundenart", "ansprechpartner", "telefon", "email",
                  "strasse", "plz", "ort", "hinweise", "status"]
        widgets = {"hinweise": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Vorschläge für die Kundenart, freie Eingabe bleibt möglich (wie in Excel)
        arten = set(KUNDENARTEN) | set(Kunde.objects.values_list("kundenart", flat=True))
        self.kundenarten = sorted(a for a in arten if a)
        self.fields["kundenart"].widget.attrs["list"] = "kundenarten"

    def clean_kundennr(self):
        nr = self.cleaned_data["kundennr"].strip()
        andere = Kunde.objects.filter(kundennr__iexact=nr)
        if self.instance.pk:
            andere = andere.exclude(pk=self.instance.pk)
        if andere.exists():
            raise forms.ValidationError("Diese Kunden-Nr. ist schon vergeben.")
        return nr

    def clean_plz(self):
        plz = self.cleaned_data["plz"].strip()
        if plz and not (plz.isdigit() and len(plz) == 5):
            raise forms.ValidationError("Die PLZ hat in Deutschland 5 Ziffern.")
        return plz
