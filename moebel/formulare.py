"""Eingabeformular des Möbelrechners (wie Blatt „Möbelrechner“, Stufe 1) und Regel-Seite."""
from decimal import Decimal

from django import forms

from material.models import Material
from projekte.models import Projekt
from rechnungen.formulare import komma_felder

from . import rechner
from .models import Regelwerk

# Abweichungen, die man je Möbel gelegentlich braucht (Spalte F im Rechner); leer = Werkstatt-Regel
ABWEICHUNGEN = [("FUGE_AUSSEN", "Fuge außen (mm)"), ("FUGE_MITTE", "Fuge Mitte (mm)"), ("FUGE_OBEN", "Fuge oben (mm)"),
                ("NUT_TIEFE", "Nuttiefe Rückwand (mm)"), ("NUT_ABSTAND", "Nutabstand hinten (mm)"),
                ("TRAV_B", "Traversenbreite (mm)"), ("VERSCHNITT", "Verschnitt (%)")]

ZAHLEN = ["anzahl", "breite", "hoehe", "tiefe", "sockel_h", "raumhoehe"] + [f"abw_{k}" for k, _ in ABWEICHUNGEN]


def _materialwahl(nur, aktuell=""):
    """Auswahlliste aus dem Materialstamm. nur = "platte" (m², mit Stärke) oder "kante" (Kanten/ABS)."""
    liste = []
    for m in Material.objects.filter(aktiv=True).order_by("materialnr"):
        platte = rechner.ist_m2(m.einheit) and m.staerke_mm
        kante = ("kante" in f"{m.produktgruppe} {m.untergruppe} {m.bezeichnung}".lower()
                 or m.materialnr.upper().startswith(("ABS", "KAN", "KT-")))
        if (nur == "platte" and platte) or (nur == "kante" and kante):
            staerke = f" · {m.staerke_mm.normalize():f} mm" if m.staerke_mm and nur == "platte" else ""
            liste.append((m.materialnr, f"{m.materialnr} – {m.bezeichnung}{staerke}"))
    if aktuell and aktuell not in {w for w, _ in liste}:
        liste.append((aktuell, f"{aktuell} (nicht im Materialstamm oder inaktiv)"))
    return liste


class MoebelFormular(forms.Form):
    projekt = forms.ModelChoiceField(Projekt.objects.select_related("kunde").order_by("-projektnr"), label="Projekt",
                                     empty_label="– Projekt wählen –")
    bezeichnung = forms.CharField(label="Bezeichnung (z. B. „Spüle links“)", max_length=200, required=False)
    typ = forms.ChoiceField(label="Möbeltyp", choices=[(t, t) for t in rechner.TYPEN])
    anzahl = forms.DecimalField(label="Anzahl gleicher Möbel", min_value=1, decimal_places=0, initial=1)
    breite = forms.DecimalField(label="Breite außen (mm)", min_value=50, max_value=6000, decimal_places=1)
    hoehe = forms.DecimalField(label="Höhe außen inkl. Sockel (mm)", min_value=50, max_value=3500, decimal_places=1)
    tiefe = forms.DecimalField(label="Tiefe außen (mm)", min_value=50, max_value=1500, decimal_places=1)
    bauweise = forms.ChoiceField(label="Bauweise", choices=rechner.BAUWEISEN, initial="A")
    abschluss = forms.ChoiceField(label="Oberer Abschluss", choices=[(x, x) for x in rechner.ABSCHLUESSE])
    mat_korpus = forms.ChoiceField(label="Korpusmaterial")
    kante_korpus = forms.ChoiceField(label="Kante Korpus (Vorderkanten)", required=False)
    mat_front = forms.ChoiceField(label="Frontmaterial", required=False)
    kante_front = forms.ChoiceField(label="Kante Front (rundum)", required=False)
    rueckwand_art = forms.ChoiceField(label="Rückwand", choices=[(x, x) for x in rechner.RUECKWANDARTEN])
    mat_rueckwand = forms.ChoiceField(label="Rückwandmaterial", required=False)
    sockel = forms.ChoiceField(label="Sockel", choices=[(x, x) for x in rechner.SOCKEL])
    sockel_h = forms.DecimalField(label="Sockelhöhe (mm, leer = Regel)", required=False, min_value=0, decimal_places=1)
    tueren = forms.ChoiceField(label="Türen", choices=[(x, x) for x in rechner.TUEREN])
    tuerart = forms.ChoiceField(label="Türart", choices=[(x, x) for x in rechner.TUERARTEN])
    fachboeden = forms.IntegerField(label="Fachböden (Anzahl)", min_value=0, max_value=20, initial=1)
    verbindung = forms.ChoiceField(label="Korpusverbindung", choices=[(x, x) for x in rechner.VERBINDUNGEN])
    beschlagsystem = forms.ChoiceField(label="Beschlagsystem")
    raumhoehe = forms.DecimalField(label="Raumhöhe (mm, für Kippmaß – leer = keine Prüfung)", required=False,
                                   min_value=0, decimal_places=0)

    def __init__(self, *args, eingaben=None, mit_projekt=True, **kwargs):
        regeln = Regelwerk.laden()
        std = regeln.standardmaterial or {}
        e = dict(eingaben or {})
        if not e:  # neues Möbel: Vorgaben wie TypVorgabe("Unterschrank") + Standardmaterial
            v = rechner.TYP_VORGABEN["Unterschrank"]
            e = {"typ": "Unterschrank", "anzahl": 1, "breite": v[0], "hoehe": v[1], "tiefe": v[2], "abschluss": v[3],
                 "sockel": v[4], "tueren": v[5], "bauweise": "A", "tuerart": "Aufschlag", "fachboeden": 1,
                 "verbindung": "Dübel", "rueckwand_art": "eingenutet", "mat_korpus": std.get("korpus", ""),
                 "mat_front": std.get("front", ""), "mat_rueckwand": std.get("rueckwand", ""),
                 "kante_korpus": std.get("kante_korpus", ""), "kante_front": std.get("kante_front", ""),
                 "beschlagsystem": next(iter(regeln.systeme), "")}
        initial = {k: v for k, v in e.items() if k != "abweichungen"}
        for k, wert in (e.get("abweichungen") or {}).items():
            initial[f"abw_{k}"] = wert
        for feld in ZAHLEN:  # Zahlen mit deutschem Komma anzeigen
            if isinstance(initial.get(feld), (int, float)):
                initial[feld] = rechner.zahl(initial[feld])
        kwargs.setdefault("initial", {}).update(initial)
        super().__init__(*args, **kwargs)
        for k, text in ABWEICHUNGEN:
            self.fields[f"abw_{k}"] = forms.DecimalField(label=f"{text} – Regel {rechner.zahl(regeln.als_regeln().r(k))}",
                                                         required=False, min_value=0, decimal_places=2)
        if not mit_projekt:
            del self.fields["projekt"]
        leer = [("", "– ohne –")]
        self.fields["mat_korpus"].choices = [("", "– Korpusmaterial wählen –")] + _materialwahl("platte", e.get("mat_korpus"))
        self.fields["mat_front"].choices = leer + _materialwahl("platte", e.get("mat_front"))
        self.fields["mat_rueckwand"].choices = leer + _materialwahl("platte", e.get("mat_rueckwand"))
        self.fields["kante_korpus"].choices = leer + _materialwahl("kante", e.get("kante_korpus"))
        self.fields["kante_front"].choices = leer + _materialwahl("kante", e.get("kante_front"))
        systeme = list(regeln.systeme)
        if e.get("beschlagsystem") and e["beschlagsystem"] not in systeme:
            systeme.append(e["beschlagsystem"])
        self.fields["beschlagsystem"].choices = [(s, s) for s in systeme]
        komma_felder(self, ZAHLEN)
        for feld in ("fachboeden",):
            self.fields[feld].widget.attrs["inputmode"] = "numeric"

    def eingaben(self) -> dict:
        """Formularwerte → Eingaben für den Rechner (JSON-tauglich)."""
        d = self.cleaned_data

        def z(wert):
            if wert in (None, ""):
                return None
            f = float(wert)
            return int(f) if f == int(f) else f

        e = {k: d.get(k) or "" for k in ("bezeichnung", "typ", "bauweise", "abschluss", "mat_korpus", "kante_korpus",
                                          "mat_front", "kante_front", "rueckwand_art", "mat_rueckwand", "sockel",
                                          "tueren", "tuerart", "verbindung", "beschlagsystem")}
        e["bezeichnung"] = e["bezeichnung"].strip()
        for k in ("anzahl", "breite", "hoehe", "tiefe", "sockel_h", "raumhoehe"):
            e[k] = z(d.get(k))
        e["fachboeden"] = d.get("fachboeden") or 0
        e["abweichungen"] = {k: z(d.get(f"abw_{k}")) for k, _ in ABWEICHUNGEN if d.get(f"abw_{k}") not in (None, "")}
        return e


class RegelFormular(forms.Form):
    """Werkstatt-Standards (Blatt „Möbel-Regeln“, Spalten A/B) – Zahlen; Tabellen bleiben im Excel-Import."""

    TEXTE = {
        "SOCKEL_H": "Sockelhöhe (mm)", "SOCKEL_LUFT": "Luft Sockelblende (mm)", "SOCKEL_RUECK": "Sockel Rücksprung (mm)",
        "FUSS_ABSTAND": "Abstand Stellfüße max. (mm)", "TRAV_B": "Traversenbreite (mm)", "FUGE_AUSSEN": "Fuge außen (mm)",
        "FUGE_MITTE": "Fuge Mitte (mm)", "FUGE_OBEN": "Fuge oben (mm)", "FUGE_EINLAGE": "Fuge Einlagetür (mm)",
        "TUER_MAX_B": "Türbreite max. (mm)", "TUER_MAX_H": "Türhöhe max. (mm)", "NUT_TIEFE": "Nuttiefe (mm)",
        "NUT_ABSTAND": "Nutabstand hinten (mm)", "FB_LUFT": "Luft Fachboden seitlich (mm)",
        "FB_ABZUG_T": "Fachboden Abzug Tiefe (mm)", "BODTR_JE": "Bodenträger je Fachboden",
        "KANTEN_ZUGABE": "Kantenzugabe je Kante (mm)", "FRAESZUGABE": "Fräszugabe je bekanteter Seite (mm)",
        "VERSCHNITT": "Verschnitt (%)", "BAND_MITTE": "Bandabstand von oben/unten (mm)", "LOCH_VORN": "Lochreihe vorn (mm)",
        "RASTER": "Lochraster (mm)", "DIAG_TOL": "Diagonal-Toleranz (mm)", "KIPP_LUFT": "Kippmaß Luft (mm)",
        "RW_DUENN": "Dünne Rückwand bis (mm)", "RW_DUENN_B": "… ab Breite Hinweis (mm)", "RW_DUENN_H": "… ab Höhe Hinweis (mm)",
        "SAEGE": "Sägeschnitt (mm)", "BESAEUM": "Besäumen je Seite (mm)", "PLATTE_L": "Standardplatte Länge (mm)",
        "PLATTE_B": "Standardplatte Breite (mm)", "SCHNELL_FAKTOR": "Schnellpreis-Faktor (× Material)",
    }

    def __init__(self, *args, regelwerk=None, **kwargs):
        werte = regelwerk.als_regeln().werte if regelwerk else dict(rechner.STANDARD_REGELN)
        kwargs.setdefault("initial", {}).update({k: rechner.zahl(werte.get(k, 0)) for k in self.TEXTE})
        super().__init__(*args, **kwargs)
        for k, text in self.TEXTE.items():
            self.fields[k] = forms.DecimalField(label=text, min_value=Decimal("0"), decimal_places=2,
                                                help_text=f"Startwert {rechner.zahl(rechner.STANDARD_REGELN[k])}")
        komma_felder(self, list(self.TEXTE))

    def werte(self) -> dict:
        return {k: (int(v) if v == int(v) else float(v)) for k, v in self.cleaned_data.items()}
