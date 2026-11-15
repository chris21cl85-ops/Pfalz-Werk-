from django import forms
from django.utils import timezone

from material.models import Material
from projekte.models import Projekt
from rechnungen.formulare import komma_felder

DATUM = {"type": "date"}


class BestellFormular(forms.Form):
    material = forms.ModelChoiceField(Material.objects.filter(aktiv=True).select_related("lieferant").order_by("bezeichnung"),
                                      label="Material", empty_label="– Material wählen –")
    menge = forms.DecimalField(label="Bestellmenge", decimal_places=3, min_value=0.001)
    projekt = forms.ModelChoiceField(Projekt.objects.order_by("-projektnr"), label="Für Projekt (optional)",
                                     required=False, empty_label="– fürs Lager –")
    erwartet_am = forms.DateField(label="Erwarteter Liefertermin (optional)", required=False,
                                  widget=forms.DateInput(attrs=DATUM, format="%Y-%m-%d"))
    grund = forms.CharField(label="Bestellgrund (optional)", required=False, max_length=200)
    notiz = forms.CharField(label="Notiz (optional)", required=False, max_length=300)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material"].label_from_instance = lambda m: (
            f"{m.materialnr} – {m.bezeichnung}" + (f" ({m.lieferant.name})" if m.lieferant else " (kein Lieferant!)"))
        komma_felder(self, ["menge"])


class WareneingangFormular(forms.Form):
    was = forms.ChoiceField(label="Was ist angekommen?", widget=forms.RadioSelect,
                            choices=[("alles", "Alles da"), ("teil", "Teillieferung – Menge eintragen"),
                                     ("nichts", "Noch nichts – Liefertermin setzen")])
    menge = forms.DecimalField(label="Gelieferte Menge", required=False, decimal_places=3, min_value=0.001)
    datum = forms.DateField(label="Geliefert am", required=False, widget=forms.DateInput(attrs=DATUM, format="%Y-%m-%d"))
    termin = forms.DateField(label="Neuer Liefertermin", required=False, widget=forms.DateInput(attrs=DATUM, format="%Y-%m-%d"))
    einlagern = forms.ChoiceField(label="Gleich einlagern?", widget=forms.RadioSelect, initial="ja",
                                  choices=[("ja", "Ja, einlagern"), ("spaeter", "Später (erst prüfen / Lager voll)")])
    mehr = forms.BooleanField(label="Ja, es wurde mehr geliefert als bestellt", required=False)
    notiz = forms.CharField(label="Notiz (optional, z. B. Lieferschein-Nr.)", required=False, max_length=300)

    def __init__(self, bestellung, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault("datum", timezone.localdate())
        self.initial.setdefault("termin", timezone.localdate() + timezone.timedelta(days=2))  # wie Makro: heute + 2
        self.fields["was"].choices = [("alles", f"Alles da – {bestellung.rest_offen.normalize():f} {bestellung.einheit}".replace(".", ",")),
                                      *self.fields["was"].choices[1:]]
        self.initial.setdefault("was", "alles")
        komma_felder(self, ["menge"])


class KorrekturFormular(forms.Form):
    neuer_bestand = forms.DecimalField(label="Gezählter Bestand", decimal_places=3, min_value=0)
    grund = forms.CharField(label="Grund", max_length=200, widget=forms.TextInput(attrs={"placeholder": "z. B. gezählt, Bruch, Verschnitt"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        komma_felder(self, ["neuer_bestand"])
