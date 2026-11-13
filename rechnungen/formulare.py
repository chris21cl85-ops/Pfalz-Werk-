from decimal import Decimal

from django import forms
from django.utils import timezone

from material.formulare import deutsche_zahl
from projekte.models import Projekt

from .models import Firmendaten, Position, Rechnung


def deutsch_lesen(wert):
    """„12.500,00 €“ -> „12500,00“: Tausenderpunkte, Euro-Zeichen und Leerzeichen weg."""
    if not isinstance(wert, str):
        return wert
    text = wert.replace("€", "").replace(" ", "").strip()
    if "," in text:
        text = text.replace(".", "")
    return text


def komma_felder(formular, felder, mindestens=0):
    """Zahlenfelder mit deutschem Komma (12,50) statt Punkt; Tausenderpunkte sind erlaubt."""
    for feld in felder:
        original = formular.fields[feld].to_python
        formular.fields[feld].to_python = lambda wert, original=original: original(deutsch_lesen(wert))
        formular.fields[feld].localize = True
        formular.fields[feld].widget = forms.TextInput(attrs={"inputmode": "decimal"})
        formular.fields[feld].widget.is_localized = True
        wert = formular.initial.get(feld)
        if isinstance(wert, Decimal) and not formular.is_bound:
            formular.initial[feld] = deutsche_zahl(wert, mindestens=mindestens)


class NeueRechnungFormular(forms.Form):
    projekt = forms.ModelChoiceField(Projekt.objects.select_related("kunde").order_by("-projektnr"),
                                     label="Projekt", empty_label="– Projekt wählen –")
    art = forms.ChoiceField(label="Art der Rechnung", widget=forms.RadioSelect, initial=Rechnung.Art.RECHNUNG,
                            choices=[(Rechnung.Art.RECHNUNG, "Rechnung – Positionen selbst eintragen"),
                                     (Rechnung.Art.ABSCHLAG, "Abschlagsrechnung – Prozent vom Auftragswert"),
                                     (Rechnung.Art.SCHLUSS, "Schlussrechnung – Auftragswert abzüglich Abschläge")])
    abschlag_prozent = forms.DecimalField(label="Abschlag in %", required=False, min_value=1, max_value=100,
                                          initial=Decimal("30"), decimal_places=2)
    auftragswert = forms.DecimalField(label="Auftragswert netto (€)", required=False, min_value=Decimal("0.01"),
                                      decimal_places=2)
    leistungszeitraum = forms.CharField(label="Leistungszeitraum", required=False, max_length=60)
    zahlungsziel = forms.ChoiceField(label="Zahlungsziel", choices=Rechnung.ZAHLUNGSZIELE, widget=forms.RadioSelect)
    mit_xrechnung = forms.ChoiceField(
        label="E-Rechnung (XRechnung)", widget=forms.RadioSelect, initial="auto", required=False,
        choices=[("auto", "Automatisch: für Firmen und Behörden ja, für Privatkunden nein"),
                 ("ja", "Ja, XRechnung mit erzeugen"), ("nein", "Nein, nur PDF")])
    kaeufer_referenz = forms.CharField(label="Leitweg-ID / Bestellzeichen des Kunden", required=False,
                                       max_length=100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault("leistungszeitraum", f"{timezone.localdate():%m/%Y}")
        komma_felder(self, ["abschlag_prozent"])
        komma_felder(self, ["auftragswert"], mindestens=2)

    def clean(self):
        daten = super().clean()
        art = daten.get("art")
        if art in (Rechnung.Art.ABSCHLAG, Rechnung.Art.SCHLUSS) and not daten.get("auftragswert"):
            self.add_error("auftragswert", "Für Abschlags- und Schlussrechnungen bitte den Auftragswert eintragen.")
        if art == Rechnung.Art.ABSCHLAG and not daten.get("abschlag_prozent"):
            self.add_error("abschlag_prozent", "Bitte den Prozentsatz eintragen (z. B. 30 oder 50).")
        return daten


class KopfFormular(forms.ModelForm):
    class Meta:
        model = Rechnung
        fields = ["leistungszeitraum", "zahlungsziel", "mit_xrechnung", "kaeufer_referenz"]
        widgets = {"zahlungsziel": forms.RadioSelect}


class PositionFormular(forms.ModelForm):
    class Meta:
        model = Position
        fields = ["text", "menge", "einheit", "einzelpreis"]
        widgets = {"text": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["einheit"].widget.attrs["list"] = "liste-einheit"
        komma_felder(self, ["menge"])
        komma_felder(self, ["einzelpreis"], mindestens=2)
        self.fields["einzelpreis"].label = "Einzelpreis netto (€)"


PositionenFormularsatz = forms.inlineformset_factory(
    Rechnung, Position, form=PositionFormular, extra=3, max_num=25, can_delete=True)

EINHEITEN = ["Stk", "pausch.", "Std", "m", "m²", "lfm", "kg", "Satz"]


class FirmendatenFormular(forms.ModelForm):
    class Meta:
        model = Firmendaten
        exclude = ["geaendert_am"]
        widgets = {"fusstext": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        komma_felder(self, ["ust_satz"])
        komma_felder(self, ["mahngebuehr"], mindestens=2)
        self.fields["letzte_rechnungsnummer"].help_text = (
            "Laufende Nummer der zuletzt geschriebenen Rechnung. Darf nur erhöht werden.")

    def clean_letzte_rechnungsnummer(self):
        neu = self.cleaned_data["letzte_rechnungsnummer"]
        alt = Firmendaten.laden().letzte_rechnungsnummer
        if neu < alt:
            raise forms.ValidationError(
                f"Die Nummer darf nicht kleiner werden (bisher {alt}) – sonst gäbe es doppelte Rechnungsnummern.")
        return neu

    def clean_iban(self):
        iban = self.cleaned_data["iban"].replace(" ", "").upper()
        if iban and not iban_gueltig(iban):
            raise forms.ValidationError("Diese IBAN ist ungültig (Prüfziffer stimmt nicht). Bitte noch einmal abtippen.")
        return iban


def iban_gueltig(iban: str) -> bool:
    """Prüfziffer nach ISO 13616 (Rest 1 bei Division durch 97) – wie BR-DE-19 der XRechnung."""
    iban = iban.replace(" ", "").upper()
    if len(iban) < 15 or not iban[:2].isalpha() or not iban[2:4].isdigit() or not iban.isalnum():
        return False
    umgestellt = iban[4:] + iban[:4]
    return int("".join(str(int(z, 36)) for z in umgestellt)) % 97 == 1
