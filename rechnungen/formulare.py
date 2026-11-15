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
        self.fields["sachkontenlaenge"].required = False
        self.fields["sachkontenlaenge"].help_text = "Meist 4 – nur ändern, wenn der Steuerberater es sagt."
        self.fields["datev_berater"].help_text = "Vom Steuerberater – wird für den DATEV-Export gebraucht."
        self.fields["letzte_rechnungsnummer"].help_text = (
            "Laufende Nummer der zuletzt geschriebenen Rechnung. Darf nur erhöht werden.")

    def clean_letzte_rechnungsnummer(self):
        neu = self.cleaned_data["letzte_rechnungsnummer"]
        alt = Firmendaten.laden().letzte_rechnungsnummer
        if neu < alt:
            raise forms.ValidationError(
                f"Die Nummer darf nicht kleiner werden (bisher {alt}) – sonst gäbe es doppelte Rechnungsnummern.")
        return neu

    def clean_sachkontenlaenge(self):
        return self.cleaned_data.get("sachkontenlaenge") or 4

    def clean_datev_berater(self):
        wert = self.cleaned_data["datev_berater"].strip()
        if wert and not wert.isdigit():
            raise forms.ValidationError("Nur Ziffern (bis 7 Stellen) – steht auf Post vom Steuerberater.")
        return wert

    def clean_datev_mandant(self):
        wert = self.cleaned_data["datev_mandant"].strip()
        if wert and not wert.isdigit():
            raise forms.ValidationError("Nur Ziffern (bis 5 Stellen).")
        return wert

    def clean_wj_beginn(self):
        import re
        wert = self.cleaned_data["wj_beginn"].strip() or "01.01."
        if not re.fullmatch(r"\d{2}\.\d{2}\.", wert):
            raise forms.ValidationError("Bitte als TT.MM. eingeben, z. B. 01.01.")
        return wert

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


class ZahlungFormular(forms.Form):
    art = forms.ChoiceField(label="Was ist eingegangen?", widget=forms.RadioSelect)
    betrag = forms.DecimalField(label="Eingegangener Betrag (€)", required=False, decimal_places=2,
                                min_value=Decimal("0.01"))
    datum = forms.DateField(label="Zahlungsdatum (laut Kontoauszug)",
                            widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    konto = forms.ChoiceField(label="Wie bezahlt?", choices=[("Bank", "Überweisung (Bank)"), ("Bar", "Bar")],
                              widget=forms.RadioSelect, initial="Bank")
    notiz = forms.CharField(label="Notiz (optional)", required=False, max_length=300)

    def __init__(self, rechnung, *args, **kwargs):
        from .dienst import SKONTO, TEIL, VOLL, euro
        super().__init__(*args, **kwargs)
        self.initial.setdefault("datum", timezone.localdate())
        wahl = [(VOLL, f"Voller offener Betrag: {euro(rechnung.offen)}")]
        if rechnung.skonto_prozent:
            mit = rechnung.offen - rechnung.skonto_betrag
            bis = f" (Skonto-Frist bis {rechnung.skonto_bis:%d.%m.%Y})" if rechnung.skonto_bis else ""
            wahl.append((SKONTO, f"Mit {rechnung.skonto_prozent.normalize():f} % Skonto: {euro(mit)}{bis}"))
        wahl.append((TEIL, "Teilbetrag – Betrag selbst eintragen"))
        self.fields["art"].choices = wahl
        self.initial.setdefault("art", VOLL)
        komma_felder(self, ["betrag"], mindestens=2)

    def clean(self):
        daten = super().clean()
        if daten.get("art") == "teil" and not daten.get("betrag"):
            self.add_error("betrag", "Bitte den eingegangenen Betrag eintragen.")
        if daten.get("datum") and daten["datum"] > timezone.localdate():
            self.add_error("datum", "Das Datum liegt in der Zukunft.")
        return daten


class GegenbuchungFormular(forms.Form):
    grund = forms.CharField(label="Grund", max_length=200)


# ------------------------------------------------------------------ Eingangsrechnungen
class EingangFormular(forms.Form):
    from .models import KATEGORIEN as _KAT
    lieferant = forms.CharField(label="Lieferant", max_length=200)
    lieferanten_nr = forms.CharField(label="Rechnungs-Nr. des Lieferanten", max_length=60)
    datum = forms.DateField(label="Rechnungsdatum", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    kategorie = forms.ChoiceField(label="Kategorie", choices=[(k, k) for k in _KAT])
    projekt = forms.ModelChoiceField(Projekt.objects.order_by("-projektnr"), label="Projekt", required=False,
                                     empty_label="– Gemeinkosten (kein Projekt) –")
    netto = forms.DecimalField(label="Netto (€)", decimal_places=2)
    ust_satz = forms.ChoiceField(label="Vorsteuer", choices=[("19", "19 %"), ("7", "7 %"), ("0", "0 %")],
                                 widget=forms.RadioSelect, initial="19")
    ziel_tage = forms.IntegerField(label="Zahlungsziel (Tage)", min_value=0, max_value=365, initial=14)
    skonto_prozent = forms.DecimalField(label="Skonto % (falls angeboten)", required=False, min_value=0,
                                        max_value=20, decimal_places=2)
    skonto_tage = forms.IntegerField(label="Skonto-Frist (Tage)", required=False, min_value=0, max_value=90)
    bestellung = forms.CharField(label="Bestell-Nr. (optional)", required=False, max_length=40)
    beleg = forms.FileField(label="Beleg (PDF oder Foto)", required=False)
    notiz = forms.CharField(label="Notiz (optional)", required=False, max_length=300)

    def __init__(self, *args, **kwargs):
        from lieferanten.models import Lieferant
        super().__init__(*args, **kwargs)
        self.initial.setdefault("datum", timezone.localdate())
        self.fields["lieferant"].widget.attrs.update({"list": "liste-lieferant", "autocomplete": "off"})
        self.fields["bestellung"].widget.attrs.update({"list": "liste-bestellung", "autocomplete": "off"})
        from lager.models import Bestellung
        self.bestellungen = [b for b in Bestellung.objects.filter(abgeschlossen=False).select_related("lieferant", "material")
                             .order_by("-bestellt_am")[:200]]
        self.fields["beleg"].widget.attrs["accept"] = ".pdf,.jpg,.jpeg,.png,image/*,application/pdf"
        self.lieferanten = list(Lieferant.objects.filter(aktiv=True).order_by("name"))
        komma_felder(self, ["netto"], mindestens=2)
        komma_felder(self, ["skonto_prozent"])

    def clean(self):
        daten = super().clean()
        if daten.get("skonto_prozent") and daten.get("skonto_tage") in (None, ""):
            self.add_error("skonto_tage", "Bitte die Skonto-Frist in Tagen eintragen.")
        if daten.get("netto") == 0:
            self.add_error("netto", "Nettobetrag eintragen.")
        return daten


class EingangZahlungFormular(forms.Form):
    art = forms.ChoiceField(label="Was wurde bezahlt?", widget=forms.RadioSelect)
    betrag = forms.DecimalField(label="Bezahlter Betrag (€)", required=False, decimal_places=2,
                                min_value=Decimal("0.01"))
    datum = forms.DateField(label="Bezahlt am", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    konto = forms.ChoiceField(label="Wie bezahlt?", choices=[("Bank", "Überweisung (Bank)"), ("Bar", "Bar")],
                              widget=forms.RadioSelect, initial="Bank")
    notiz = forms.CharField(label="Notiz (optional)", required=False, max_length=300)

    def __init__(self, er, *args, **kwargs):
        from .dienst import euro
        super().__init__(*args, **kwargs)
        heute = timezone.localdate()
        self.initial.setdefault("datum", heute)
        wahl = []
        if er.skonto_moeglich(heute):
            wahl.append(("skonto", f"Mit {er.skonto_prozent.normalize():f} % Skonto: {euro(er.offen - er.skonto_betrag)}"
                                   f" (Frist bis {er.skonto_bis:%d.%m.%Y})"))
        wahl += [("voll", f"Voll bezahlt: {euro(er.offen)}"), ("teil", "Teilbetrag – Betrag selbst eintragen")]
        self.fields["art"].choices = wahl
        self.initial.setdefault("art", wahl[0][0])
        komma_felder(self, ["betrag"], mindestens=2)

    def clean(self):
        daten = super().clean()
        if daten.get("art") == "teil" and not daten.get("betrag"):
            self.add_error("betrag", "Bitte den bezahlten Betrag eintragen.")
        return daten
