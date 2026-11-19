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

ZAHLEN = ["anzahl", "breite", "hoehe", "tiefe", "sockel_h", "raumhoehe", "schnellfaktor"] + \
    [f"abw_{k}" for k, _ in ABWEICHUNGEN]
ZONEN_ZEILEN = 12  # wie Zonentabelle A39:E58 (dort 20 Zeilen)
FORM_ZEILEN = 6
FORM_FELDER = ["bezeichnung", "verfahren", "radius", "winkel", "hoehe", "dicke", "material", "anzahl", "lagenmass", "form_da"]


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
    tuerkonstruktion = forms.ChoiceField(label="Türkonstruktion", required=False,
                                         choices=[(x, x) for x in rechner.TUERKONSTRUKTIONEN])
    fachboeden = forms.IntegerField(label="Fachböden (Anzahl)", min_value=0, max_value=20, initial=1)
    verbindung = forms.ChoiceField(label="Korpusverbindung", choices=[(x, x) for x in rechner.VERBINDUNGEN])
    beschlagsystem = forms.ChoiceField(label="Beschlagsystem")
    raumhoehe = forms.DecimalField(label="Raumhöhe (mm, für Kippmaß – leer = keine Prüfung)", required=False,
                                   min_value=0, decimal_places=0)
    # Stufe 3: Oberfläche / Kalkulation
    oberflaeche_korpus = forms.ChoiceField(label="Oberfläche Korpus", required=False)
    oberflaeche_front = forms.ChoiceField(label="Oberfläche Front", required=False)
    kantenprofil = forms.ChoiceField(label="Kantenprofil Front", required=False, choices=[(x, x) for x in rechner.KANTENPROFILE])
    plattenbedarf = forms.ChoiceField(label="Plattenbedarf", required=False, choices=[(x, x) for x in rechner.PLATTENBEDARF])
    schnellfaktor = forms.DecimalField(label="Schnellpreis-Faktor (leer = Regel)", required=False, min_value=0,
                                       decimal_places=2)
    # Stufe 2: Aufteilung
    felder = forms.IntegerField(label="Felder (Mittelwände = Felder − 1)", min_value=1, max_value=9, initial=1,
                                required=False)
    feldbreiten = forms.CharField(label="Feldbreiten licht mm (leer = gleich; z. B. 400;Rest)", required=False,
                                  max_length=60)
    teilungsregel = forms.ChoiceField(label="Teilungsregel Fronthöhen", choices=[(x, x) for x in rechner.TEILUNGSREGELN], required=False)
    zwischenboeden = forms.ChoiceField(label="Zwischenböden zwischen Zonen", choices=[("Ja", "Ja"), ("Nein", "Nein")], required=False)
    kastensystem = forms.ChoiceField(label="Schubkastensystem", choices=[(x, x) for x in rechner.KASTENSYSTEME], required=False)
    kastenverbindung = forms.ChoiceField(label="Kastenverbindung (Holzkasten)",
                                         choices=[(x, x) for x in rechner.KASTENVERBINDUNGEN], required=False)

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
        initial = {k: v for k, v in e.items() if k not in ("abweichungen", "zonen")}
        initial.setdefault("felder", 1)
        initial.setdefault("teilungsregel", "gleich")
        initial.setdefault("zwischenboeden", "Ja")
        for i, z in enumerate((e.get("zonen") or [])[:ZONEN_ZEILEN]):
            for feld in ("feld", "zone", "art", "hoehe", "fachboeden"):
                if z.get(feld) not in (None, "", 0) or feld == "art":
                    initial[f"z{i}_{feld}"] = z.get(feld)
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
        for i in range(ZONEN_ZEILEN):
            self.fields[f"z{i}_feld"] = forms.IntegerField(min_value=1, max_value=9, required=False)
            self.fields[f"z{i}_zone"] = forms.IntegerField(min_value=1, max_value=20, required=False)
            self.fields[f"z{i}_art"] = forms.ChoiceField(required=False, choices=[("", "–")] + [(x, x) for x in rechner.ZONENARTEN])
            self.fields[f"z{i}_hoehe"] = forms.DecimalField(min_value=0, max_value=3000, decimal_places=1, required=False)
            self.fields[f"z{i}_fachboeden"] = forms.IntegerField(min_value=0, max_value=10, required=False)
            for teil in ("feld", "zone", "hoehe", "fachboeden"):
                self.fields[f"z{i}_{teil}"].widget.attrs.update({"inputmode": "numeric", "style": "min-width:0"})
        for i, ft in enumerate((e.get("formteile") or [])[:FORM_ZEILEN]):
            for feld in FORM_FELDER:
                if ft.get(feld) not in (None, ""):
                    initial[f"f{i}_{feld}"] = ft.get(feld)
        for i in range(FORM_ZEILEN):
            self.fields[f"f{i}_bezeichnung"] = forms.CharField(required=False, max_length=80)
            self.fields[f"f{i}_verfahren"] = forms.ChoiceField(required=False, choices=[("", "–")] + [(x, x) for x in rechner.FORMVERFAHREN])
            for feld, maxi in (("radius", 10000), ("winkel", 360), ("hoehe", 5000), ("dicke", 500), ("lagenmass", 100)):
                self.fields[f"f{i}_{feld}"] = forms.DecimalField(required=False, min_value=0, max_value=maxi, decimal_places=2)
            self.fields[f"f{i}_material"] = forms.CharField(required=False, max_length=40,
                                                            widget=forms.TextInput(attrs={"list": "materialnummern"}))
            self.fields[f"f{i}_anzahl"] = forms.IntegerField(required=False, min_value=1, max_value=999)
            self.fields[f"f{i}_form_da"] = forms.ChoiceField(required=False, choices=[("Nein", "Nein"), ("Ja", "Ja")])
            for feld in ("radius", "winkel", "hoehe", "dicke", "lagenmass", "anzahl"):
                self.fields[f"f{i}_{feld}"].widget.attrs.update({"inputmode": "decimal", "style": "min-width:0"})
        self.initial.update({k: v for k, v in initial.items() if k.startswith("f") and k[1:2].isdigit()})
        if not mit_projekt:
            del self.fields["projekt"]
        leer = [("", "– ohne –")]
        self.fields["mat_korpus"].choices = [("", "– Korpusmaterial wählen –")] + _materialwahl("platte", e.get("mat_korpus"))
        self.fields["mat_front"].choices = leer + _materialwahl("platte", e.get("mat_front"))
        self.fields["mat_rueckwand"].choices = leer + _materialwahl("platte", e.get("mat_rueckwand"))
        self.fields["kante_korpus"].choices = leer + _materialwahl("kante", e.get("kante_korpus"))
        self.fields["kante_front"].choices = leer + _materialwahl("kante", e.get("kante_front"))
        namen = [o[0] for o in (regeln.oberflaechen or []) if o and o[0]]
        for k in ("oberflaeche_korpus", "oberflaeche_front"):
            wahl = [("", "– keine Angabe –")] + [(n, n) for n in namen]
            if e.get(k) and e[k] not in namen:
                wahl.append((e[k], f"{e[k]} (nicht mehr in der Tabelle)"))
            self.fields[k].choices = wahl
        systeme = list(regeln.systeme)
        if e.get("beschlagsystem") and e["beschlagsystem"] not in systeme:
            systeme.append(e["beschlagsystem"])
        self.fields["beschlagsystem"].choices = [(s, s) for s in systeme]
        komma_felder(self, ZAHLEN + [f"z{i}_hoehe" for i in range(ZONEN_ZEILEN)]
                     + [f"f{i}_{k}" for i in range(FORM_ZEILEN) for k in ("radius", "winkel", "hoehe", "dicke", "lagenmass")])
        for feld in ("fachboeden",):
            self.fields[feld].widget.attrs["inputmode"] = "numeric"

    def formteil_zeilen(self):
        return [[self[f"f{i}_{t}"] for t in FORM_FELDER] for i in range(FORM_ZEILEN)]

    def zonen_zeilen(self):
        """Für die Vorlage: je Zeile die fünf Felder."""
        return [[self[f"z{i}_{t}"] for t in ("feld", "zone", "art", "hoehe", "fachboeden")] for i in range(ZONEN_ZEILEN)]

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
        for k in ("anzahl", "breite", "hoehe", "tiefe", "sockel_h", "raumhoehe", "schnellfaktor"):
            e[k] = z(d.get(k))
        for k, std in (("oberflaeche_korpus", ""), ("oberflaeche_front", ""), ("kantenprofil", "gerade"),
                       ("plattenbedarf", "ganze Platten")):
            e[k] = (d.get(k) or "").strip() or std
        e["fachboeden"] = d.get("fachboeden") or 0
        e["felder"] = d.get("felder") or 1
        for k, std in (("feldbreiten", ""), ("teilungsregel", "gleich"), ("zwischenboeden", "Ja"),
                       ("kastensystem", "Holzkasten Unterflur"), ("kastenverbindung", "Dübel")):
            e[k] = (d.get(k) or "").strip() or std
        e["zonen"] = []
        for i in range(ZONEN_ZEILEN):
            if d.get(f"z{i}_art"):
                e["zonen"].append({"feld": d.get(f"z{i}_feld") or 1, "zone": d.get(f"z{i}_zone") or (i + 1),
                                   "art": d[f"z{i}_art"], "hoehe": z(d.get(f"z{i}_hoehe")) or 0,
                                   "fachboeden": d.get(f"z{i}_fachboeden") or 0})
        e["tuerkonstruktion"] = d.get("tuerkonstruktion") or "Platte"
        e["formteile"] = []
        for i in range(FORM_ZEILEN):
            if d.get(f"f{i}_verfahren") or (d.get(f"f{i}_bezeichnung") or "").strip():
                ft = {k: d.get(f"f{i}_{k}") for k in FORM_FELDER}
                for k in ("radius", "winkel", "hoehe", "dicke", "lagenmass"):
                    ft[k] = z(ft[k]) or 0
                ft["anzahl"] = ft["anzahl"] or 1
                ft["bezeichnung"] = (ft["bezeichnung"] or "").strip()
                ft["material"] = (ft["material"] or "").strip()
                ft["form_da"] = ft["form_da"] or "Nein"
                e["formteile"].append(ft)
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
        "NL_RESERVE": "Nennlänge: max. Innentiefe minus (mm)", "SKL_ABZUG": "Holzkasten: Seite = Nennlänge minus (mm)",
        "SAB": "Holzkasten außen = lichte Weite minus (mm)", "ZAB": "Kastenhöhe = Fronthöhe minus (mm)",
        "ZH_MIN": "Kleinste Kastenhöhe (mm)", "BODEN_NUT": "Holzkasten: Bodennut Tiefe (mm)",
        "HS_ABZUG": "Hinterstück niedriger als Seite (mm)", "FEDER": "Nut und Feder: Federlänge je Seite (mm)",
        "BOX_BODEN_ABZUG": "Metallbox: Boden = lichte Weite minus (mm)",
        "BOX_RW_ABZUG": "Metallbox: Rückwand = lichte Weite minus (mm)", "BOX_RW_H": "Metallbox: Rückwandhöhe (mm)",
        "ERGO_SK_MAX": "Ergonomie: Schubkasten-Oberkante max. (mm)", "ERGO_UNTEN": "Ergonomie: Schubkasten sehr tief unter (mm)",
        "ERGO_FACH_MAX": "Ergonomie: Fach darüber nur mit Tritt (mm)",
        "MH_LAM_B": "Massivholz: Ziel-Lamellenbreite (mm)", "MH_LAM_MAX": "Massivholz: breiter → Leimholz (mm)",
        "MH_RESERVE": "Massivholz: Reserve Grobvolumen (%)", "MH_DELTA_U": "Massivholz: Holzfeuchte-Änderung (%)",
        "MH_QUELL_MAX": "Massivholz: Hinweis ab Quellmaß (mm)", "MH_ZUG_L": "Massivholz: Zugabe Länge (mm)",
        "MH_ZUG_B": "Massivholz: Zugabe Breite je Lamelle (mm)", "MH_ZUG_D": "Massivholz: Zugabe Dicke (mm)",
        "RAHMEN_B": "Rahmen + Füllung: Friesbreite (mm)", "RAHMEN_ZAPFEN": "Rahmen: Zapfentiefe je Seite (mm)",
        "FUELL_NUT": "Füllung: Nuttiefe (mm)", "FUELL_LUFT": "Füllung: Luft je Seite (mm)",
        "SEG_WINKEL_MAX": "Segmentbau: größter Segmentwinkel (°)", "SEG_ZUGABE": "Segment/Rohling: Zugabe (mm)",
        "KERF_B": "Einsägen: Schnittbreite (mm)", "KERF_REST": "Einsägen: Reststeg außen (mm)",
        "FORM_ZUGABE": "Formteile: Zugabe je Ende (mm)", "FORM_LAGE": "Formverleimung: Lagendicke ohne Stärke (mm)",
        "BIEG_R_FAKTOR": "Biegeplatte: Mindestradius = Faktor × Lage", "FURN_R_FAKTOR": "Formverleimung: Mindestradius = Faktor × Lage",
        "LEIM_KG_M2": "Leimauftrag je Fuge (kg/m²)", "DAEMPF_RT_BAND": "Dämpfen: kleinstes R/t mit Biegeband",
        "DAEMPF_RT_FREI": "Dämpfen: ab R/t ohne Biegeband", "DAEMPF_MIN_JE_MM": "Dämpfzeit je mm Dicke (min)",
        "RUECKFED": "Dämpfen: Rückfederung (%)", "KURZFASER_W": "Ausschneiden Massivholz: Kurzfaser ab (°)",
        "FORM_RAND": "Formenbau: Rand um das Formteil (mm)",
        "WARTE_STD": "Wartezeit Trocknen/Aushärten bei AG-Übernahme (Std.)", "CNC_JA": "Bohren/Fräsen auf CNC (1 = ja, 0 = von Hand)",
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
