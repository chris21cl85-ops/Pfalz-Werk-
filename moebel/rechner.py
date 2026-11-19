"""Möbelrechner (Stufe 1 der Excel): Korpus, Rückwand, Fachböden, Sockel, Fronten, Beschläge, Verbinder, Prüfungen,
Materialbedarf mit ganzen Platten – 1:1 nach Rechnen(), TeilNeu(), BedarfFinal() und PlattenZaehlen() im Makro
PW_Moebelrechner (20.10.2026). Reine Rechenlogik ohne Datenbankzugriff: Regeln und Materialstamm kommen als
Wörterbücher bzw. Nachschlage-Funktion herein, damit alles einzeln testbar ist.

Noch nicht enthalten (Excel-Stufen 2–6): Aufteilung in Felder/Zonen, Schubkästen, Modulbau, Rahmen + Füllung,
Massivholz/Quellmaß, Oberflächen, Arbeitsgänge, Formteile, CNC.
"""
import math
from dataclasses import dataclass, field

TYP_VORGABEN = {  # wie TypVorgabe(): B, H, T, oberer Abschluss, Sockel, Türen
    "Unterschrank": (600, 820, 560, "Traversen", "Stellfüße mit Blende", "automatisch"),
    "Oberschrank": (600, 720, 350, "Deckel", "ohne Sockel (hängend)", "automatisch"),
    "Hochschrank": (600, 2100, 560, "Deckel", "Stellfüße mit Blende", "automatisch"),
    "Kommode": (1000, 900, 450, "Deckel", "Sockelkasten", "automatisch"),
    "Regal": (800, 1800, 300, "Deckel", "ohne Sockel", "keine Tür / offen"),
}
TYPEN = list(TYP_VORGABEN)
BAUWEISEN = [("A", "A Seiten durchgehend"), ("B", "B Boden und Deckel durchgehend"), ("C", "C Boden durchgehend")]
RUECKWANDARTEN = ["eingenutet", "eingefälzt", "aufgeschraubt", "eingestellt", "ohne"]
SOCKEL = ["Stellfüße mit Blende", "Sockelkasten", "ohne Sockel", "ohne Sockel (hängend)"]
TUEREN = ["automatisch", "1 Tür", "2 Türen", "keine Tür / offen"]
TUERARTEN = ["Aufschlag", "Einlage"]
VERBINDUNGEN = ["Dübel", "Confirmat", "Lamello", "Domino"]
ABSCHLUESSE = ["Traversen", "Deckel"]
# Stufe 2: Aufteilung (Möbel-Regeln AP–AU)
ZONENARTEN = ["Tür", "Schubkasten", "Fach offen", "Blende"]
TEILUNGSREGELN = ["gleich", "Goldener Schnitt", "Fibonacci", "gestaffelt", "Raster 32", "manuell"]
KASTENSYSTEME = ["Holzkasten Unterflur", "Metallbox"]
KASTENVERBINDUNGEN = ["Dübel", "Schwalbenschwanz", "Nut und Feder", "Lamello"]
STANDARD_NENNLAENGEN = [270, 300, 350, 400, 450, 500, 550, 600]
# Stufe 3 (RegelnStufe3, Möbel-Regeln AW:BE): Oberfläche, AG-Codes, Material 1 + Menge je m² und Seite,
# Material 2 + Menge, Seiten, Schliff, Hinweis
STANDARD_OBERFLAECHEN = [
    ["beschichtet (Dekor)", "", "", 0, "", 0, 0, "-", ""],
    ["furniert, geölt", "MH-060;WZ-010;SL-010;SL-020;OF-010;WZ-020;QM-030", "OF-OSMO-HWO", 0.08, "FU-EI-06", 1.15, 2,
     "120 / 180", "Furnier beidseitig inkl. 15 % Zugabe – Holzart wählen"],
    ["furniert, lackiert", "MH-060;WZ-010;SL-010;SL-020;OF-020;WZ-020;QM-030", "OF-LACK-WB", 0.25, "FU-EI-06", 1.15, 2,
     "120 / 180 / 240", "Furnier beidseitig inkl. 15 % Zugabe"],
    ["lackiert deckend (MDF)", "SL-010;OF-010;WZ-020;SL-020;OF-020;WZ-020;QM-030", "OF-LACK-WB", 0.3, "", 0, 2,
     "180 / 240 / 320", "Grundierung + 2 x Decklack"],
    ["HPL belegt", "MH-060;WZ-010;QM-030", "KL-KONTAKT", 0.3, "HPL-RES-WEI-08", 1.1, 2, "-", "beidseitig belegen (Gegenzug)"],
    ["Massivholz geölt", "SL-010;SL-020;OF-010;WZ-020;QM-030", "OF-OSMO-HWO", 0.08, "", 0, 2, "120 / 150 / 180", ""],
    ["Massivholz lackiert", "SL-010;SL-020;OF-020;WZ-020;QM-030", "OF-LACK-WB", 0.25, "", 0, 2, "120 / 180 / 240", ""],
    ["gebeizt + lackiert", "SL-010;SL-020;OF-010;WZ-020;OF-020;WZ-020;QM-030", "OF-BEIZE", 0.1, "OF-LACK-WB", 0.25, 2,
     "120 / 180 / 240", "Probe auf Originalholz"],
]
KANTENPROFILE = ["gerade", "Fase 2 mm", "Radius 2 mm", "Radius 3 mm", "Profil nach Zeichnung"]
PLATTENBEDARF = ["ganze Platten", "Verschnittfaktor"]

# Werkstatt-Standards (RegelnAnlegen + RegelnStufe3) – werden aus „Möbel-Regeln“ übernommen, hier nur Startwerte
STANDARD_REGELN = {
    "SOCKEL_H": 100, "SOCKEL_LUFT": 3, "SOCKEL_RUECK": 50, "FUSS_ABSTAND": 600, "TRAV_B": 100,
    "FUGE_AUSSEN": 3, "FUGE_MITTE": 3, "FUGE_OBEN": 3, "FUGE_EINLAGE": 2, "TUER_MAX_B": 600, "TUER_MAX_H": 2400,
    "NUT_TIEFE": 8, "NUT_ABSTAND": 10, "FB_LUFT": 2, "FB_ABZUG_T": 20, "BODTR_JE": 4, "KANTEN_ZUGABE": 50,
    "FRAESZUGABE": 0, "VERSCHNITT": 20, "BAND_MITTE": 100, "LOCH_VORN": 37, "RASTER": 32, "DIAG_TOL": 1,
    "KIPP_LUFT": 10, "RW_DUENN": 3, "RW_DUENN_B": 1000, "RW_DUENN_H": 2000,
    "SAEGE": 4, "BESAEUM": 10, "PLATTE_L": 2800, "PLATTE_B": 2070, "SCHNELL_FAKTOR": 3,
    # Stufe 2 (RegelnStufe2): Schubkästen und Ergonomie
    "NL_RESERVE": 10, "SKL_ABZUG": 10, "SAB": 42, "ZAB": 40, "ZH_MIN": 60, "BODEN_NUT": 8, "HS_ABZUG": 13, "FEDER": 8,
    "BOX_BODEN_ABZUG": 75, "BOX_RW_ABZUG": 87, "BOX_RW_H": 70, "ERGO_SK_MAX": 1500, "ERGO_UNTEN": 150,
    "ERGO_FACH_MAX": 1900,
    # Stufe 3
    "WARTE_STD": 12, "CNC_JA": 1,
}
STANDARD_BAENDER = [(900, 2), (1600, 3), (2000, 4), (2400, 5)]           # Türhöhe bis → Bänder
STANDARD_FACHBODEN = [(16, 550), (19, 700), (22, 800), (25, 900), (99, 1000)]  # Stärke bis → Spannweite max
STANDARD_VERBINDER = {"Dübel": ("DUE-HOLZ-8X40", 150), "Confirmat": ("SCH-KONF-7X50", 150), "Lamello": ("LAM-20", 150),
                      "Domino": ("DOM-8X40", 150), "Rückwandschraube": ("SCH-SPAX-3X16", 150)}
# Beschlagsystem: Topfband, Montageplatte, Bodenträger, Sockelfuß, Sockelclip, Schrankaufhänger, Aufhängeschiene, Griff
STANDARD_SYSTEME = {
    "Neutral (Bestand)": ["BL-SCH-110", "", "BL-BODTR-5", "BL-SOCKELFUSS", "BL-SOCKELCLIP", "BL-AUFH", "BL-AUFH-SCHIENE", "BL-GRIFF"],
    "Blum": ["BL-BLUM-TB-110", "BL-BLUM-MPL", "BL-BODTR-5", "BL-SOCKELFUSS", "BL-SOCKELCLIP", "BL-AUFH", "BL-AUFH-SCHIENE", "BL-GRIFF"],
    "Hettich": ["BL-HET-TB-110", "BL-HET-MPL", "BL-BODTR-5", "BL-SOCKELFUSS", "BL-SOCKELCLIP", "BL-AUFH", "BL-AUFH-SCHIENE", "BL-GRIFF"],
    "Grass": ["BL-GRA-TB-110", "BL-GRA-MPL", "BL-BODTR-5", "BL-SOCKELFUSS", "BL-SOCKELCLIP", "BL-AUFH", "BL-AUFH-SCHIENE", "BL-GRIFF"],
}
STANDARD_MATERIAL = {"korpus": "PL-WEI-P2-19", "front": "PL-WEI-P2-19", "rueckwand": "HDF-08",
                     "kante_korpus": "ABS-W-08", "kante_front": "ABS-W-20",
                     "kasten": "MPX-BI-15", "kastenboden": "HDF-08"}  # B95/B96: Holzkasten

GRUEN, GELB, ROT = 0, 1, 2


@dataclass
class Material:
    """Was der Rechner aus dem Materialstamm braucht."""
    nr: str
    bezeichnung: str = ""
    einheit: str = ""
    staerke: float = 0
    format: str = ""
    ek: float | None = None
    aktiv: bool = True


@dataclass
class Regeln:
    werte: dict = field(default_factory=lambda: dict(STANDARD_REGELN))
    baender: list = field(default_factory=lambda: list(STANDARD_BAENDER))
    fachboden: list = field(default_factory=lambda: list(STANDARD_FACHBODEN))
    verbinder: dict = field(default_factory=lambda: dict(STANDARD_VERBINDER))
    systeme: dict = field(default_factory=lambda: dict(STANDARD_SYSTEME))
    nennlaengen: list = field(default_factory=lambda: list(STANDARD_NENNLAENGEN))
    material: dict = field(default_factory=lambda: dict(STANDARD_MATERIAL))
    oberflaechen: list = field(default_factory=lambda: [list(x) for x in STANDARD_OBERFLAECHEN])

    def oberflaeche(self, name):
        return next((o for o in self.oberflaechen if o and o[0] == name), None)

    def nennlaenge(self, max_l):
        """Größte Nennlänge, die in max_l passt (wie Nennlaenge())."""
        return int(max([n for n in self.nennlaengen if 0 < float(n) <= max_l], default=0))

    def r(self, key):
        return float(self.werte.get(key, STANDARD_REGELN[key]))

    def band_anzahl(self, hoehe):
        for bis, anzahl in self.baender:
            if hoehe <= bis:
                return int(anzahl)
        return 0  # höher als die Tabelle → Prüfung Rot

    def fachboden_grenze(self, staerke):
        for bis, spann in self.fachboden:
            if staerke <= bis:
                return float(spann)
        return 1000.0

    def verbinder_id(self, art):
        nr, abstand = self.verbinder.get(art, ("", 150))
        return nr, float(abstand or 150)

    def system_wert(self, sys, spalte):
        """Spalte 1 = Topfband … 8 = Griff (wie SystemWert()); unbekanntes System → erstes der Tabelle."""
        werte = self.systeme.get(sys) or (next(iter(self.systeme.values())) if self.systeme else [""] * 8)
        return werte[spalte - 1] if len(werte) >= spalte else ""


def kanten_dicke(nr: str) -> float:
    """ABS-W-08 → 0,8 mm; ABS-EI-20 → 2,0 mm (letztes Segment / 10)."""
    if not nr or "-" not in nr:
        return 0.0
    teil = nr.rsplit("-", 1)[1]
    return float(teil) / 10 if teil.replace(".", "", 1).isdigit() else 0.0


def platten_format(fmt: str) -> tuple[float, float]:
    """„2800 x 2070 mm“ → (2800, 2070): die ersten beiden Zahlen ≥ 500, längere zuerst."""
    zahlen, aktuell = [], ""
    for ch in (fmt or "") + " ":
        if ch.isdigit():
            aktuell += ch
        else:
            if aktuell and float(aktuell) >= 500:
                zahlen.append(float(aktuell))
            aktuell = ""
        if len(zahlen) == 2:
            break
    if len(zahlen) < 2:
        return 0.0, 0.0
    return max(zahlen), min(zahlen)


def ist_m2(einheit: str) -> bool:
    return (einheit or "").strip().lower() in ("m²", "m2", "qm")


def aufrunden(x):
    return math.ceil(x - 1e-9)


def fib(m):
    a, b = 1, 2
    if m <= 0:
        return 1
    for _ in range(2, m + 1):
        a, b = b, a + b
    return b


def teilen(gesamt, fest, regel, raster=32):
    """Wie Teilen(): feste Maße bleiben, freie Teile nach Regel (ganze mm, Raster 32 auf 32 mm);
    Rest an das unterste freie Teil. Liefert (Liste, Hinweis)."""
    n = len(fest)
    erg = [float(f) if f and f > 0 else 0.0 for f in fest]
    rest = gesamt - sum(erg)
    frei = [i for i in range(n) if erg[i] == 0]
    k = len(frei)
    if k == 0:
        return erg, (f"Feste Maße ergeben {zahl(gesamt - rest)} statt {zahl(gesamt)} mm." if abs(rest) > 0.05 else "")
    if rest <= 0:
        return erg, f"Kein Platz für die freien Teile (Rest {zahl(rest)} mm)."
    art = (regel or "gleich").lower()[:4]
    phi = (1 + math.sqrt(5)) / 2
    w = {}
    for j, i in enumerate(frei):
        w[i] = {"gold": phi ** (k - 1 - j), "fibo": fib(k - 1 - j), "gest": k - j}.get(art, 1)
    sw = sum(w.values())
    summe = 0
    for i in frei:
        erg[i] = (int(rest * w[i] / sw / raster) * raster) if art == "rast" else int(rest * w[i] / sw)
        summe += erg[i]
    erg[frei[0]] += rest - summe
    return [round(x, 1) for x in erg], ""


class Rechner:
    def __init__(self, eingaben: dict, regeln: Regeln, material):
        """material: Funktion Material-Nr. → Material oder None."""
        self.e, self.R, self._mat = eingaben, regeln, material
        self.teile, self.pruefungen, self.kennzahlen = [], [], {}
        self.bedarf, self.bedarf_grund = {}, {}
        self.varianten, self.verb_extra = [], 0
        self.ag = {}  # AG-Code → Bereich (wie gAG im Makro)

    # ---------------------------------------------------------- Hilfen
    def mat(self, nr):
        return self._mat(nr) if nr else None

    def staerke(self, nr):
        m = self.mat(nr)
        return float(m.staerke or 0) if m else 0.0

    def r(self, key):
        """Regel mit Abweichung aus der Eingabe (wie ro(): Spalte F im Rechner); leer = Regel."""
        wert = (self.e.get("abweichungen") or {}).get(key)
        return float(wert) if wert not in (None, "") else self.R.r(key)

    def pruef(self, was, status, hinweis):
        self.pruefungen.append({"pruefung": was, "status": status, "hinweis": hinweis})

    def bedarf_plus(self, nr, menge, grund):
        if not nr or menge <= 0:
            return
        self.bedarf[nr] = self.bedarf.get(nr, 0) + menge
        if grund not in self.bedarf_grund.get(nr, ""):
            self.bedarf_grund[nr] = (self.bedarf_grund[nr] + ", " + grund) if self.bedarf_grund.get(nr) else grund

    def teil(self, name, gruppe, menge, l, b, mat, kl1="", kl2="", kb1="", kb2="", maser="", bearb="", ort="",
             diag=False, hinweis=""):
        """Wie TeilNeu(): Zuschnitt = Fertigmaß − Kantendicken (+ Fräszugabe je bekanteter Seite)."""
        if menge <= 0:
            return
        fz = self.R.r("FRAESZUGABE")
        zl = l - kanten_dicke(kb1) - kanten_dicke(kb2) + (fz if kb1 else 0) + (fz if kb2 else 0)
        zb = b - kanten_dicke(kl1) - kanten_dicke(kl2) + (fz if kl1 else 0) + (fz if kl2 else 0)
        m = self.mat(mat)
        self.teile.append({
            "teil": name, "gruppe": gruppe, "menge": menge, "l": round(l, 1), "b": round(b, 1), "dicke": self.staerke(mat),
            "zl": round(zl, 1), "zb": round(zb, 1), "material": mat, "kl1": kl1, "kl2": kl2, "kb1": kb1, "kb2": kb2,
            "maser": maser, "bearbeitung": bearb, "ort": ort, "diagonale": round(math.hypot(l, b), 1) if diag else None,
            "m2": round(l * b * menge / 1_000_000, 4), "hinweis": hinweis, "einheit": m.einheit if m else ""})
        self.bedarf_plus(mat, l * b * menge / 1_000_000, "Fläche netto")
        for kante, laenge in ((kl1, l), (kl2, l), (kb1, b), (kb2, b)):
            if kante:
                self.bedarf_plus(kante, (laenge + self.R.r("KANTEN_ZUGABE")) * menge / 1000, "Kantenlänge inkl. Zugabe")

    def beschlag(self, name, gruppe, menge, nr, ort, hinweis=""):
        if menge <= 0:
            return
        if not nr:
            hinweis = (hinweis + " ⚠ keine Material-Nr. (Beschlagsystem bzw. Materialstamm prüfen)").strip()
        m = self.mat(nr)
        self.teile.append({"teil": name, "gruppe": gruppe, "menge": menge, "l": None, "b": None, "dicke": None, "zl": None,
                           "zb": None, "material": nr, "kl1": "", "kl2": "", "kb1": "", "kb2": "", "maser": "",
                           "bearbeitung": "", "ort": ort, "diagonale": None, "m2": None, "hinweis": hinweis,
                           "einheit": m.einheit if m else ""})
        if nr:
            self.bedarf_plus(nr, menge, gruppe)

    def mat_pruefen(self, nr, was):
        if not nr:
            return
        m = self.mat(nr)
        if m is None:
            self.pruef(was, ROT, f"{nr} fehlt im Materialstamm.")
        elif not m.aktiv:
            self.pruef(was, ROT, f"{nr} ist im Materialstamm nicht aktiv.")

    # ---------------------------------------------------------- Rechnen
    def rechnen(self):
        e, R = self.e, self.R
        typ = e.get("typ") or "Unterschrank"
        vorgabe = TYP_VORGABEN.get(typ, TYP_VORGABEN["Unterschrank"])
        anz = float(e.get("anzahl") or 1)
        b = float(e.get("breite") or vorgabe[0])
        h = float(e.get("hoehe") or vorgabe[1])
        tt = float(e.get("tiefe") or vorgabe[2])
        bw = (e.get("bauweise") or "A")[:1].upper()
        abschluss = e.get("abschluss") or vorgabe[3]
        mat_k, mat_f, mat_r = e.get("mat_korpus") or "", e.get("mat_front") or "", e.get("mat_rueckwand") or ""
        rw_art = (e.get("rueckwand_art") or "eingenutet").lower()
        sockel = e.get("sockel") or vorgabe[4]
        k_k, k_f = e.get("kante_korpus") or "", e.get("kante_front") or ""
        tueren = e.get("tueren") or vorgabe[5]
        tuerart = e.get("tuerart") or "Aufschlag"
        n_fb = int(e.get("fachboeden") or 0)
        verb = e.get("verbindung") or "Dübel"
        sys = e.get("beschlagsystem") or ""
        raum = float(e.get("raumhoehe") or 0)
        haengend = "ohne" in sockel.lower() and typ == "Oberschrank"
        # Stufe 2: Felder und Zonen (Feld, Zone von unten, Art, Fronthöhe, Fachböden)
        zonen_liste = [z for z in (e.get("zonen") or []) if (z.get("art") or "").strip()]
        felder = max(1, int(e.get("felder") or 1))
        zonen = felder > 1 or bool(zonen_liste)

        fa, fm, fo, fe = self.r("FUGE_AUSSEN"), self.r("FUGE_MITTE"), self.r("FUGE_OBEN"), self.r("FUGE_EINLAGE")
        nut_t, nut_a, trav = self.r("NUT_TIEFE"), self.r("NUT_ABSTAND"), self.r("TRAV_B")
        tb_max = R.r("TUER_MAX_B")

        # ---- Material
        s = self.staerke(mat_k)
        if not mat_k or self.mat(mat_k) is None:
            self.pruef("Korpusmaterial", ROT, "Korpusmaterial wählen (Material-Nr. aus dem Materialstamm).")
            return self._abschluss(anz, ohne_bedarf=True)
        if s <= 0:
            self.pruef("Korpusmaterial", ROT, f"Im Materialstamm fehlt die Stärke für {mat_k}.")
            return self._abschluss(anz, ohne_bedarf=True)
        self.mat_pruefen(mat_k, "Korpusmaterial")
        front_da = bool(mat_f) and "keine" not in tueren.lower() and typ != "Regal"
        zonen_mit_tuer = any("tür" in z["art"].lower() for z in zonen_liste) or (not zonen_liste and front_da)
        if front_da:
            self.mat_pruefen(mat_f, "Frontmaterial")
        rw_da = rw_art != "ohne"
        d_r = 0.0
        if rw_da:
            if not mat_r:
                self.pruef("Rückwand", ROT, "Rückwandmaterial wählen oder Rückwandart „ohne“.")
            self.mat_pruefen(mat_r, "Rückwandmaterial")
            d_r = self.staerke(mat_r)
        if k_k:
            self.mat_pruefen(k_k, "Kante Korpus")
        if k_f and front_da:
            self.mat_pruefen(k_f, "Kante Front")

        # ---- Grundmaße
        hs = 0.0 if "ohne" in sockel.lower() else float(e.get("sockel_h") or R.r("SOCKEL_H"))
        hk = h - hs
        boden_durch = bw in ("B", "C")
        deckel_durch = bw == "B" and abschluss == "Deckel"
        h_seite = hk - (s if boden_durch else 0) - (s if deckel_durch else 0)
        ib, ih = b - 2 * s, hk - 2 * s
        ti = {"eingenutet": tt - nut_a - d_r, "eingefälzt": tt - d_r - 1, "aufgeschraubt": tt,
              "eingestellt": tt - d_r}.get(rw_art, tt)
        tb = tt - d_r if rw_art == "eingestellt" else tt
        self.kennzahlen.update({"Korpushöhe": hk, "Plattenstärke Korpus": s, "Innenbreite": ib, "Innenhöhe": ih,
                                "Innentiefe nutzbar": ti, "Soll-Diagonale Korpus": round(math.hypot(b, hk), 1)})
        if ib <= 0 or ih <= 0 or ti <= 0:
            self.pruef("Innenmaße", ROT, "Innenbreite, Innenhöhe oder Innentiefe ist 0 oder kleiner – Außenmaße prüfen.")
            return self._abschluss(anz, ohne_bedarf=True)

        # ---- Seitenbearbeitung
        bearb = []
        falz = round(s * 2 / 3)
        if rw_art == "eingenutet":
            bearb.append(f"Nut {zahl(d_r + 0.5)} x {zahl(nut_t)} mm, {zahl(nut_a)} mm von hinten")
        if rw_art == "eingefälzt":
            bearb.append(f"Falz {falz} x {zahl(d_r + 1)} mm hinten")
        if n_fb > 0:
            bearb.append(f"Lochreihen {zahl(R.r('RASTER'))} mm, {zahl(R.r('LOCH_VORN'))} mm von vorn")
        if front_da and tuerart == "Aufschlag" and (not zonen or zonen_mit_tuer):
            bearb.append("Montageplatten-Bohrungen")
        bearb.append(f"Verbinder {verb}")
        bearb_seite = "; ".join(bearb)
        nut = "Nut wie Seite" if rw_art == "eingenutet" else ""

        # ---- Korpus
        self.teil("Seite", "Korpus", 2, h_seite, tt, mat_k, k_k, maser="senkrecht", bearb=bearb_seite, ort="Korpus")
        if boden_durch:
            self.teil("Boden", "Korpus", 1, b, tb, mat_k, k_k, "", k_k, k_k, "quer", nut, "Korpus")
        else:
            self.teil("Boden", "Korpus", 1, ib, tb, mat_k, k_k, maser="quer", bearb=nut, ort="Korpus")
        if abschluss == "Traversen":
            self.teil("Traverse vorn", "Korpus", 1, ib, trav, mat_k, k_k, maser="quer", ort="Korpus")
            self.teil("Traverse hinten", "Korpus", 1, ib, trav, mat_k, maser="quer", bearb=nut, ort="Korpus")
        elif deckel_durch:
            self.teil("Deckel", "Korpus", 1, b, tb, mat_k, k_k, "", k_k, k_k, "quer", nut, "Korpus")
        else:
            self.teil("Deckel", "Korpus", 1, ib, tb, mat_k, k_k, maser="quer", bearb=nut, ort="Korpus")

        # ---- Rückwand
        if rw_da and mat_r:
            if rw_art == "eingenutet":
                self.teil("Rückwand", "Korpus", 1, ih + 2 * nut_t - 2, ib + 2 * nut_t - 2, mat_r, bearb="in Nut schieben", ort="Korpus")
            elif rw_art == "eingefälzt":
                self.teil("Rückwand", "Korpus", 1, ih + 2 * falz - 2, ib + 2 * falz - 2, mat_r, bearb="in Falz schrauben", ort="Korpus")
            elif rw_art == "aufgeschraubt":
                self.teil("Rückwand", "Korpus", 1, hk - 4, b - 4, mat_r, bearb="hinten aufschrauben", ort="Korpus")
            elif rw_art == "eingestellt":
                self.teil("Rückwand", "Korpus", 1, ih, ib, mat_r, maser="senkrecht",
                          bearb="zwischen Seiten, Verbinder wie Boden", ort="Korpus")
            if rw_art in ("aufgeschraubt", "eingefälzt"):
                nr, abst = R.verbinder_id("Rückwandschraube")
                self.beschlag("Schrauben Rückwand", "Verbinder", aufrunden(2 * (b + hk) / abst), nr, "Korpus")
            if d_r <= R.r("RW_DUENN") and (b > R.r("RW_DUENN_B") or hk > R.r("RW_DUENN_H")):
                self.pruef("Rückwand-Aussteifung", GELB,
                           "Dünne Rückwand bei großem Korpus – stärkere Rückwand oder zusätzliche Aussteifung prüfen.")

        # ---- Fachböden (ohne Aufteilung)
        if n_fb > 0 and not zonen:
            self.teil("Fachboden", "Innenausbau", n_fb, ib - R.r("FB_LUFT"), ti - R.r("FB_ABZUG_T"), mat_k, k_k,
                      maser="quer", bearb="lose auf Bodenträgern", ort="Innenraum")
            raster = R.r("RASTER")
            rs = int(ih / (n_fb + 1) / raster + 0.5) * raster
            self.kennzahlen["Fachbodenhöhen 32er-Raster (ab OK Boden)"] = " / ".join(zahl(i * rs) for i in range(1, n_fb + 1)) + " mm"
            self.beschlag("Bodenträger", "Beschlag", n_fb * R.r("BODTR_JE"), R.system_wert(sys, 3), "Innenraum")
            spann, grenze = ib - R.r("FB_LUFT"), R.fachboden_grenze(s)
            if spann > grenze:
                self.pruef("Fachboden-Durchbiegung", ROT, f"Spannweite {zahl(spann)} mm über Grenze {zahl(grenze)} mm für "
                                                          f"{zahl(s)} mm – Mittelwand, Anleimer oder stärkere Platte.")
            elif spann > 0.85 * grenze:
                self.pruef("Fachboden-Durchbiegung", GELB, f"Spannweite {zahl(spann)} mm nahe Grenze {zahl(grenze)} mm.")
            else:
                self.pruef("Fachboden-Durchbiegung", GRUEN, f"Spannweite {zahl(spann)} mm, Grenze {zahl(grenze)} mm.")

        # ---- Sockel / Aufhängung
        luft = R.r("SOCKEL_LUFT")
        if "stellf" in sockel.lower():
            m_bl = mat_f or mat_k
            self.teil("Sockelblende", "Sockel", 1, b, hs - luft, m_bl, k_f or k_k, maser="quer", bearb="Clip-Befestigung", ort="Sockel")
            n_fuss = 4 + 2 * max(0, aufrunden((b - R.r("FUSS_ABSTAND")) / R.r("FUSS_ABSTAND")))
            self.beschlag("Sockelfuß", "Beschlag", n_fuss, R.system_wert(sys, 4), "Sockel")
            self.beschlag("Sockelblenden-Clip", "Beschlag", n_fuss / 2, R.system_wert(sys, 5), "Sockel")
        elif "kasten" in sockel.lower():
            rueck = R.r("SOCKEL_RUECK")
            self.teil("Sockel Längsteil vorn", "Sockel", 1, b, hs - luft, mat_k, k_k, maser="quer",
                      bearb=f"um {zahl(rueck)} mm zurückgesetzt", ort="Sockel")
            self.teil("Sockel Längsteil hinten", "Sockel", 1, b, hs - luft, mat_k, maser="quer", ort="Sockel")
            self.teil("Sockel Querteil", "Sockel", 2, tt - rueck - 2 * s, hs - luft, mat_k, maser="quer", ort="Sockel")
        if haengend:
            self.beschlag("Schrankaufhänger", "Beschlag", 2, R.system_wert(sys, 6), "Aufhängung")
            self.beschlag("Aufhängeschiene (m)", "Beschlag", b / 1000, R.system_wert(sys, 7), "Aufhängung")

        # ---- Felder und Zonen (Stufe 2)
        if zonen:
            boden = -1 if haengend else hs + (s + fe if tuerart == "Einlage" else 0)
            self._zonen(dict(b=b, hk=hk, s=s, ib=ib, ih=ih, ti=ti, fa=fa, fm=fm, fo=fo, fe=fe, tb_max=tb_max,
                             mat_k=mat_k, mat_f=mat_f, k_k=k_k, k_f=k_f, sys=sys, tuerart=tuerart, front_da=front_da,
                             n_fb=n_fb, verb=verb, boden=boden, felder=felder, zonen=zonen_liste))

        # ---- Fronten (ohne Aufteilung)
        if front_da and not zonen:
            if tuerart == "Einlage":
                fw, fh = ib - 2 * fe, ih - 2 * fe
            else:
                fw, fh = b - fa, hk - fo
            nt = 2 if "2" in tueren else 1 if "1" in tueren else (2 if fw > tb_max else 1)
            wb = (fw - fm) / 2 if nt == 2 else fw
            band_je = R.band_anzahl(fh)
            if band_je > 0 and wb > tb_max:
                band_je += 1
            self.teil("Tür (links/rechts)" if nt == 2 else "Tür", "Front", nt, fh, wb, mat_f, k_f, k_f, k_f, k_f,
                      "senkrecht", f"Topfbohrung Ø35, Bandmitte {zahl(R.r('BAND_MITTE'))} mm von oben/unten; Griffbohrung",
                      "Front", diag=True, hinweis="Anschlag links/rechts festlegen" if nt == 1 else "")
            self.beschlag("Topfband", "Beschlag", band_je * nt, R.system_wert(sys, 1), "Front")
            self.beschlag("Montageplatte", "Beschlag", band_je * nt, R.system_wert(sys, 2), "Front")
            self.beschlag("Griff", "Beschlag", nt, R.system_wert(sys, 8), "Front")
            self.kennzahlen["Türen"] = f"{nt} x {zahl(round(wb, 1))} x {zahl(round(fh, 1))} mm"
            if band_je == 0:
                self.pruef("Türhöhe", ROT, f"Türhöhe {zahl(fh)} mm über der Band-Tabelle – Aufteilung ändern.")
            elif fh > R.r("TUER_MAX_H"):
                self.pruef("Türhöhe", ROT, f"Türhöhe {zahl(fh)} mm über Maximum {zahl(R.r('TUER_MAX_H'))} mm.")
            elif fh / wb > 4:
                self.pruef("Türproportion", GELB, "Verhältnis Höhe/Breite über 4 – Verzugsgefahr, Rahmen oder stärkere Front prüfen.")
            else:
                self.pruef("Türen", GRUEN, f"{nt} x {zahl(round(wb, 1))} x {zahl(round(fh, 1))} mm, {band_je} Bänder je Tür")
            if nt == 1 and wb > tb_max:
                self.pruef("Türbreite", GELB, f"Tür breiter als {zahl(tb_max)} mm – zwei Türen oder schweres Band prüfen.")
            if tuerart != "Einlage":
                fugen = nt * wb + (nt - 1) * fm + fa
                if abs(fugen - b) > 0.05:
                    self.pruef("Querschnitt Fronten", ROT, f"Frontbreiten + Fugen = {zahl(fugen)} mm statt {zahl(b)} mm.")
                else:
                    self.pruef("Querschnitt Fronten", GRUEN, f"Frontbreiten + Fugen = {zahl(b)} mm")

        # ---- Verbinder (je Fuge: aufrunden(Tiefe / Abstand) + 1)
        nr, abst = R.verbinder_id(verb)
        anzahl = 2 * (aufrunden(tb / abst) + 1)
        anzahl += 4 * (aufrunden(trav / abst) + 1) if abschluss == "Traversen" else 2 * (aufrunden(tb / abst) + 1)
        if rw_art == "eingestellt":
            anzahl += 4 * (aufrunden(ih / abst) + 1) / 2
        anzahl += self.verb_extra  # Mittelwände und Zwischenböden
        self.beschlag(f"Verbinder {verb}", "Verbinder", anzahl, nr, "Korpus")

        # ---- Schnittprüfungen
        self.pruef("Querschnitt Korpus", GRUEN, f"2 x {zahl(s)} + {zahl(ib)} = {zahl(b)} mm")
        self.pruef("Höhenschnitt", GRUEN if abs(hs + hk - h) < 0.05 else ROT, f"{zahl(hs)} Sockel + {zahl(hk)} Korpus = {zahl(h)} mm")
        self.pruef("Längsschnitt", GRUEN if ti - R.r("FB_ABZUG_T") > 0 else ROT, f"Innentiefe nutzbar {zahl(ti)} mm ({rw_art})")
        if raum > 0:
            kipp = round(math.hypot(h, tt), 1)
            self.kennzahlen["Kippmaß"] = kipp
            if kipp >= raum - R.r("KIPP_LUFT"):
                self.pruef("Diagonalschnitt (Kippmaß)", ROT, f"Kippmaß {zahl(kipp)} mm – Schrank lässt sich bei {zahl(raum)} mm "
                                                             "Raumhöhe nicht aufrichten. Aufsatzschrank prüfen.")
            else:
                self.pruef("Diagonalschnitt (Kippmaß)", GRUEN, f"Kippmaß {zahl(kipp)} mm < Raumhöhe {zahl(raum)} mm")
        raster = R.r("RASTER")
        if n_fb > 0 and round(hk - s) % raster != 0:
            naechste = aufrunden((hk - s) / raster) * raster + s
            self.pruef("32er-Raster", GELB, f"Korpushöhe passt nicht ins Raster (x * {zahl(raster)} + {zahl(s)}). "
                                            f"Nächste Rasterhöhe: {zahl(naechste)} mm")
        for t in self.teile:
            if t["l"] is not None and t["material"]:
                m = self.mat(t["material"])
                fl, fb = platten_format(m.format if m else "")
                if fl > 0 and (max(t["l"], t["b"]) > fl or min(t["l"], t["b"]) > fb):
                    self.pruef("Plattenformat", ROT, f"{t['teil']} ({zahl(t['l'])} x {zahl(t['b'])} mm) größer als Platte "
                                                     f"{zahl(fl)} x {zahl(fb)} mm")
        # Stufe 3: Oberfläche, Profil, Arbeitsgänge
        self._oberflaechen(mat_k, mat_r)
        self._profil()
        self._arbeitsgaenge()
        return self._abschluss(anz)

    # ---------------------------------------------------------- Stufe 3: Oberfläche, Profil, Arbeitsgänge
    def ag_plus(self, code, bereich):
        if code not in self.ag:
            self.ag[code] = bereich
        elif bereich.lower() not in self.ag[code].lower():
            self.ag[code] += ", " + bereich

    def _oberflaechen(self, mat_k, mat_r):
        """Wie Oberflaechen(): Fläche Korpus bzw. Front × Seiten × Menge je m² → Bedarf; AG-Codes der Oberfläche."""
        for gruppe, schluessel in (("Korpus", "oberflaeche_korpus"), ("Front", "oberflaeche_front")):
            name = (self.e.get(schluessel) or "").strip()
            if not name:
                continue
            o = self.R.oberflaeche(name)
            if o is None:
                self.pruef(f"Oberfläche {gruppe}", GELB, f"{name} steht nicht in der Oberflächen-Tabelle (Werkstatt-Regeln).")
                continue
            flaeche = 0.0
            for t in self.teile:
                if t["l"] is None:
                    continue
                if gruppe == "Front" and t["gruppe"] == "Front":
                    flaeche += t["m2"]
                elif gruppe == "Korpus" and t["gruppe"] in ("Korpus", "Innenausbau", "Sockel") and \
                        (t["material"] != mat_r or mat_r == mat_k):
                    flaeche += t["m2"]
            seiten = float(o[6] or 0)
            if flaeche > 0 and seiten > 0:
                for nr, menge in ((o[2], o[3]), (o[4], o[5])):
                    if nr and float(menge or 0) > 0:
                        if self.mat(nr) is None:
                            self.pruef("Oberflächenmaterial", GELB, f"{nr} fehlt im Materialstamm (Oberflächen-Tabelle prüfen).")
                        else:
                            self.bedarf_plus(nr, flaeche * seiten * float(menge), f"Belag/Anstrich {gruppe}")
            if flaeche > 0:
                for code in str(o[1] or "").split(";"):
                    if code.strip():
                        self.ag_plus(code.strip(), gruppe)
            schliff = o[7] if o[7] not in ("", "-", None) else ""
            self.kennzahlen[f"Oberfläche {gruppe}"] = f"{name}{', Schliff ' + schliff if schliff else ''} ({flaeche:.2f} m²)".replace(".", ",")
            if o[8] and flaeche > 0:
                self.pruef(f"Oberfläche {gruppe}", GRUEN, o[8])

    def _profil(self):
        """Wie ProfilAnwenden(): Kantenprofil an allen Frontteilen vermerken."""
        pr = (self.e.get("kantenprofil") or "").strip()
        if not pr or pr.lower() == "gerade":
            return
        n = 0
        for t in self.teile:
            if t["gruppe"] == "Front" and t["l"] is not None:
                t["bearbeitung"] = (t["bearbeitung"] + "; " if t["bearbeitung"] else "") + f"Kantenprofil {pr}"
                n += 1
        if n:
            self.ag_plus("CNC-020" if self.R.r("CNC_JA") > 0 else "BE-010", "Profil Front")

    def _arbeitsgaenge(self):
        """Wie ArbeitsgaengeBilden(): automatische Arbeitsgänge aus Teilen, Kanten, Beschlägen."""
        platte = any(t["l"] is not None for t in self.teile)
        kante = any(t["kl1"] or t["kl2"] or t["kb1"] or t["kb2"] for t in self.teile)
        besch = any(t["l"] is None and t["gruppe"] == "Beschlag" for t in self.teile)
        vorher = dict(self.ag)
        self.ag = {}
        self.ag_plus("VOR-010", "Material")
        if platte:
            self.ag_plus("PL-010", "Platten")
            self.ag_plus("PL-020", "Platten")
        if kante:
            self.ag_plus("KA-010", "Kanten")
        for code, bereich in vorher.items():  # Oberfläche, Profil … in der Reihenfolge des Makros vorn
            for b in bereich.split(", "):
                self.ag_plus(code, b)
        if self.R.r("CNC_JA") > 0:
            self.ag_plus("CNC-010", "Bohrbild")
            self.ag_plus("CNC-020", "Bohrbild")
        else:
            self.ag_plus("BE-010", "Bohren/Dübeln")
        self.ag_plus("QM-020", "Bohrbild")
        self.ag_plus("MO-010", "Korpus")
        if besch:
            self.ag_plus("MO-020", "Beschläge")
        self.ag_plus("QM-010", "Maße")
        self.ag_plus("QM-040", "Endkontrolle")
        self.ag_plus("LOG-010", "Lieferung")

    # ---------------------------------------------------------- Stufe 2: Felder, Zonen, Schubkästen
    def _mat_oder_leer(self, nr):
        return nr if self.mat(nr) is not None else ""

    def _zonen(self, k):
        """Wie FeldBreiten() + RechnenZonen(): Mittelwände, Felder, Zonen je Feld von unten nach oben."""
        e, R = self.e, self.R
        s, ib = k["s"], k["ib"]
        regel = e.get("teilungsregel") or "gleich"
        mit_zb = str(e.get("zwischenboeden", "Ja")).lower() not in ("nein", "false", "0")
        k_sys = e.get("kastensystem") or "Holzkasten Unterflur"
        k_verb = e.get("kastenverbindung") or "Dübel"
        nr_v, abst = R.verbinder_id(k["verb"])
        zonen = [dict(z) for z in k["zonen"]]
        n_f = k["felder"]
        groesstes = max([int(z.get("feld") or 1) for z in zonen], default=1)
        if groesstes > n_f:
            self.pruef("Felder", GELB, f"Zone in Feld {groesstes} – Felderzahl auf {groesstes} erhöht.")
            n_f = groesstes
        n_f = min(n_f, 9)
        # Feldbreiten: feste Werte aus „400;Rest“, freie gleich verteilt
        innen = ib - (n_f - 1) * s
        tok = [t.strip() for t in str(e.get("feldbreiten") or "").replace(",", ".").split(";")]
        fest = []
        for i in range(n_f):
            try:
                fest.append(float(tok[i]) if i < len(tok) and tok[i] else 0)
            except ValueError:
                fest.append(0)
        wf, hinw = teilen(innen, fest, "gleich", R.r("RASTER"))
        if hinw:
            self.pruef("Feldbreiten", ROT, hinw)
            return
        if not zonen:  # je Feld eine Tür bzw. ein offenes Fach mit den Fachböden aus der Eingabe
            zonen = [{"feld": f, "zone": 1, "art": "Tür" if k["front_da"] else "Fach offen", "hoehe": 0,
                      "fachboeden": k["n_fb"]} for f in range(1, n_f + 1)]
        if n_f > 1:
            self.teil("Mittelwand", "Korpus", n_f - 1, k["ih"], k["ti"], k["mat_k"], k["k_k"], maser="senkrecht",
                      bearb=f"Lochreihen beidseitig; Verbinder {k['verb']}", ort="Korpus")
            self.verb_extra += (n_f - 1) * 2 * (aufrunden(k["ti"] / abst) + 1)
        summe = 2 * s + (n_f - 1) * s + sum(wf)
        liste = " / ".join(zahl(w) for w in wf)
        self.kennzahlen["Feldbreiten licht"] = liste + " mm"
        for i, w in enumerate(wf):
            if w <= 0:
                self.pruef(f"Feld {i + 1}", ROT, "Feldbreite 0 oder kleiner.")
        if abs(summe - k["b"]) > 0.05:
            self.pruef("Querschnitt Felder", ROT, f"Seiten + Mittelwände + Felder = {zahl(summe)} statt {zahl(k['b'])} mm")
        else:
            self.pruef("Querschnitt Felder", GRUEN, f"{n_f + 1} x {zahl(s)} + {liste} = {zahl(k['b'])} mm")

        for f in range(1, n_f + 1):
            eigene = sorted([z for z in zonen if min(int(z.get("feld") or 1), n_f) == f],
                            key=lambda z: float(z.get("zone") or 0))
            w = wf[f - 1]
            n = len(eigene)
            if n == 0:
                self.pruef(f"Feld {f}", GELB, "keine Zone eingetragen – Feld bleibt offen.")
                continue
            if w <= 0:
                continue
            if k["tuerart"] == "Einlage":
                front_b = w - 2 * k["fe"]
                fuge_z = s + 2 * k["fe"] if mit_zb else k["fm"]
                verfueg = k["ih"] - 2 * k["fe"] - (n - 1) * fuge_z
            else:
                front_b = (w + (s if f == 1 else s / 2) + (s if f == n_f else s / 2)
                           - (k["fa"] / 2 if f == 1 else k["fm"] / 2) - (k["fa"] / 2 if f == n_f else k["fm"] / 2))
                fuge_z = k["fm"]
                verfueg = k["hk"] - k["fo"] - (n - 1) * fuge_z
            fest_h = [float(z.get("hoehe") or 0) for z in eigene]
            hoehen, hinw = teilen(verfueg, fest_h, regel, R.r("RASTER"))
            if hinw:
                self.pruef(f"Höhenteilung Feld {f}", ROT, hinw)
                continue
            frei = sum(1 for x in fest_h if x <= 0)
            if frei and regel.lower().startswith("manu"):
                self.pruef(f"Höhenteilung Feld {f}", GELB, f"Regel manuell: {frei} Zone(n) ohne Fronthöhe wurden gleich verteilt.")
            liste = " / ".join(zahl(x) for x in hoehen)
            summe = (n - 1) * fuge_z + sum(hoehen)
            self.kennzahlen[f"Feld {f} Fronthöhen (unten zuerst)"] = f"{liste} mm ({regel})"
            self.pruef(f"Höhenteilung Feld {f}", GRUEN if abs(summe - verfueg - (n - 1) * fuge_z) < 0.05 else ROT,
                       f"{liste} + {n - 1} x {zahl(fuge_z)} Fuge = {zahl(summe)} mm")
            # Variantenvergleich (feste Fronthöhen bleiben fest)
            vergleich = []
            for name in TEILUNGSREGELN[:5]:
                hv, hw = teilen(verfueg, fest_h, name, R.r("RASTER"))
                vergleich.append({"regel": name, "text": hw or " / ".join(zahl(x) for x in hv), "gewaehlt": name == regel})
            self.varianten.append({"feld": f, "verfuegbar": verfueg, "regeln": vergleich})

            pos = k["boden"]
            fb_geprueft = False
            for j, z in enumerate(eigene):
                art = (z.get("art") or "").lower()
                fh = hoehen[j]
                ort = f"Feld {f} Zone {j + 1}"
                n_fbz = int(z.get("fachboeden") or 0)
                if pos >= 0:
                    if "schub" in art and pos + fh > R.r("ERGO_SK_MAX"):
                        self.pruef(f"Ergonomie {ort}", GELB, f"Schubkasten-Oberkante {zahl(pos + fh)} mm über Boden – schlecht "
                                                             f"einsehbar (Richtwert bis {zahl(R.r('ERGO_SK_MAX'))} mm).")
                    elif "schub" in art and pos < R.r("ERGO_UNTEN"):
                        self.pruef(f"Ergonomie {ort}", GRUEN, f"Schubkasten sehr tief ({zahl(pos)} mm) – für selten Gebrauchtes.")
                    if n_fbz > 0 and pos + fh > R.r("ERGO_FACH_MAX"):
                        self.pruef(f"Ergonomie {ort}", GELB, f"Oberstes Fach endet bei {zahl(pos + fh)} mm – nur mit Tritt erreichbar.")
                    pos += fh + fuge_z
                if "fach" not in art and not k["mat_f"]:
                    self.pruef("Frontmaterial", ROT, f"{ort}: Frontmaterial wählen.")
                elif "schub" in art:
                    self.teil("Schubkastenfront", "Front", 1, front_b, fh, k["mat_f"], k["k_f"], k["k_f"], k["k_f"], k["k_f"],
                              "quer", "Frontbefestigung lt. System; Griffbohrung", ort, diag=True)
                    self.beschlag("Griff", "Beschlag", 1, R.system_wert(k["sys"], 8), ort)
                    self._kasten(w, fh, k_sys, k_verb, ort, k)
                elif "blende" in art:
                    self.teil("Blende", "Front", 1, front_b, fh, k["mat_f"], k["k_f"], k["k_f"], k["k_f"], k["k_f"], "quer",
                              "fest von innen verschraubt", ort)
                elif "fach" not in art:
                    nt = 2 if front_b > k["tb_max"] else 1
                    wb = (front_b - k["fm"]) / 2 if nt == 2 else front_b
                    band_je = R.band_anzahl(fh)
                    if band_je > 0 and wb > k["tb_max"]:
                        band_je += 1
                    self.teil("Tür (links/rechts)" if nt == 2 else "Tür", "Front", nt, fh, wb, k["mat_f"], k["k_f"], k["k_f"],
                              k["k_f"], k["k_f"], "senkrecht",
                              f"Topfbohrung Ø35, Bandmitte {zahl(R.r('BAND_MITTE'))} mm von oben/unten; Griffbohrung", ort, diag=True)
                    self.beschlag("Topfband", "Beschlag", band_je * nt, R.system_wert(k["sys"], 1), ort)
                    self.beschlag("Montageplatte", "Beschlag", band_je * nt, R.system_wert(k["sys"], 2), ort)
                    self.beschlag("Griff", "Beschlag", nt, R.system_wert(k["sys"], 8), ort)
                    if band_je == 0:
                        self.pruef(f"Türhöhe {ort}", ROT, f"Türhöhe {zahl(fh)} mm über der Band-Tabelle.")
                    elif fh < 2 * R.r("BAND_MITTE") + 50:
                        self.pruef(f"Türhöhe {ort}", GELB, f"Tür sehr niedrig ({zahl(fh)} mm) – Klappe oder Schubkasten prüfen.")
                    elif fh / wb > 4:
                        self.pruef(f"Türproportion {ort}", GELB, "Höhe/Breite über 4 – Verzugsgefahr.")
                if n_fbz > 0 and "schub" not in art and "blende" not in art:
                    self.teil("Fachboden", "Innenausbau", n_fbz, w - R.r("FB_LUFT"), k["ti"] - R.r("FB_ABZUG_T"), k["mat_k"],
                              k["k_k"], maser="quer", bearb="lose auf Bodenträgern", ort=ort)
                    self.beschlag("Bodenträger", "Beschlag", n_fbz * R.r("BODTR_JE"), R.system_wert(k["sys"], 3), ort)
                    if not fb_geprueft:
                        fb_geprueft = True
                        spann, grenze = w - R.r("FB_LUFT"), R.fachboden_grenze(s)
                        if spann > grenze:
                            self.pruef(f"Fachboden Feld {f}", ROT, f"Spannweite {zahl(spann)} mm über Grenze {zahl(grenze)} mm.")
                        elif spann > 0.85 * grenze:
                            self.pruef(f"Fachboden Feld {f}", GELB, f"Spannweite {zahl(spann)} mm nahe Grenze {zahl(grenze)} mm.")
            if mit_zb and n > 1:
                self.teil("Zwischenboden", "Innenausbau", n - 1, w, k["ti"], k["mat_k"], k["k_k"], maser="quer",
                          bearb=f"fest, Verbinder {k['verb']}", ort=f"Feld {f}")
                self.verb_extra += (n - 1) * 2 * (aufrunden(k["ti"] / abst) + 1)

    def _kasten(self, lw, fh, k_sys, k_verb, ort, k):
        """Wie Kasten(): Schubkasten zur lichten Weite und Fronthöhe (Holzkasten Unterflur oder Metallbox)."""
        R = self.R
        nl = R.nennlaenge(k["ti"] - R.r("NL_RESERVE"))
        if nl == 0:
            self.pruef(f"Schubkasten {ort}", ROT, f"Keine Nennlänge passt in die Innentiefe {zahl(k['ti'])} mm.")
            return
        zh = fh - R.r("ZAB")
        if zh < R.r("ZH_MIN"):
            self.pruef(f"Schubkasten {ort}", ROT, f"Fronthöhe {zahl(fh)} mm zu klein (Kastenhöhe {zahl(zh)} < "
                                                  f"{zahl(R.r('ZH_MIN'))} mm).")
            return
        if "metall" in k_sys.lower():
            self.teil("Kastenboden (Box)", "Schubkasten", 1, nl - 10, lw - R.r("BOX_BODEN_ABZUG"), k["mat_k"], maser="quer",
                      bearb="in die Zargen einschrauben", ort=ort)
            self.teil("Kastenrückwand (Box)", "Schubkasten", 1, lw - R.r("BOX_RW_ABZUG"), R.r("BOX_RW_H"), k["mat_k"],
                      maser="quer", bearb="an Rückwandhalter, Höhe nach Zarge prüfen", ort=ort)
            self.beschlag(f"Zargenset NL {nl} (Paar)", "Beschlag", 1, self._mat_oder_leer(f"BL-BOX-{nl}"), ort)
            self.beschlag(f"Führung NL {nl} (Paar)", "Beschlag", 1, self._mat_oder_leer(f"BL-FUE-{nl}"), ort)
            self.pruef(f"Schubkasten {ort}", GRUEN, f"Metallbox NL {nl}, Boden {zahl(nl - 10)} x "
                                                    f"{zahl(lw - R.r('BOX_BODEN_ABZUG'))} mm")
            return
        mat_ka, mat_bo = R.material.get("kasten", ""), R.material.get("kastenboden", "")
        tk, d_b = self.staerke(mat_ka), self.staerke(mat_bo)
        if tk <= 0 or d_b <= 0:
            self.pruef("Kastenmaterial", ROT, "Kastenmaterial oder Kastenboden (Werkstatt-Regeln, Standardmaterial) "
                                              "fehlt im Materialstamm oder hat keine Stärke.")
            return
        skl = nl - R.r("SKL_ABZUG")
        kb = lw - R.r("SAB")
        nv = 0
        if "schwalben" in k_verb.lower():
            vl, bearb = kb, "Schwalbenschwanz-Zinken"
        elif "nut" in k_verb.lower():
            vl, bearb = kb - 2 * tk + 2 * R.r("FEDER"), f"Feder {zahl(R.r('FEDER'))} mm, Nut in den Seiten"
        else:
            vl, bearb = kb - 2 * tk, f"Verbinder {k_verb}"
            nr_kv, abst = R.verbinder_id(k_verb)
            nv = 4 * max(2, aufrunden(zh / abst) + 1)
        hs_h = zh - R.r("HS_ABZUG")
        nut = R.r("BODEN_NUT")
        self.teil("Kastenseite", "Schubkasten", 2, skl, zh, mat_ka, maser="längs",
                  bearb=f"Bodennut {zahl(d_b + 0.5)} x {zahl(nut)} mm; {bearb}", ort=ort)
        self.teil("Vorderstück", "Schubkasten", 1, vl, zh, mat_ka, maser="längs", bearb=f"Bodennut; {bearb}", ort=ort)
        self.teil("Hinterstück", "Schubkasten", 1, vl, hs_h, mat_ka, maser="längs", bearb=f"steht auf dem Boden; {bearb}", ort=ort)
        self.teil("Kastenboden", "Schubkasten", 1, skl - tk + nut - 1, kb - 2 * tk + 2 * nut - 1, mat_bo,
                  bearb="in Nut, hinten am Hinterstück verschraubt", ort=ort)
        if nv > 0:
            self.beschlag(f"Kastenverbinder {k_verb}", "Verbinder", nv, nr_kv, ort)
        self.beschlag(f"Führung NL {nl} (Paar)", "Beschlag", 1, self._mat_oder_leer(f"BL-FUE-{nl}"), ort,
                      f"Kasten außen {zahl(kb)} mm – Herstellermaße prüfen")
        if kb <= 2 * tk:
            self.pruef(f"Schubkasten {ort}", ROT, "Feld zu schmal für einen Kasten.")
        else:
            self.pruef(f"Schubkasten {ort}", GRUEN, f"NL {nl}, Kasten {zahl(skl)} x {zahl(kb)} x {zahl(zh)} mm ({k_verb})")

    # ---------------------------------------------------------- Anzahl + Bedarf
    def _abschluss(self, anz, ohne_bedarf=False):
        if anz != 1:  # wie MitAnzahl(): alles multiplizieren
            for t in self.teile:
                t["menge"] *= anz
                if t["m2"] is not None:
                    t["m2"] = round(t["m2"] * anz, 4)
            self.bedarf = {k: v * anz for k, v in self.bedarf.items()}
        self.kennzahlen["Anzahl"] = anz
        bedarf = [] if ohne_bedarf else self.bedarf_final()
        ampel = max((p["status"] for p in self.pruefungen), default=GRUEN)
        return {"teile": self.teile, "pruefungen": self.pruefungen, "kennzahlen": self.kennzahlen, "bedarf": bedarf,
                "varianten": self.varianten, "arbeitsgaenge": [[c, b] for c, b in self.ag.items()],
                "ampel": ampel, "kosten": round(sum(x["kosten"] or 0 for x in bedarf), 2)}

    def bedarf_final(self):
        """Wie BedarfFinal(): Platten als ganze Platten (Streifenzuschnitt), sonst + Verschnitt; Stück aufrunden."""
        vs = self.r("VERSCHNITT") / 100
        ganze = (self.e.get("plattenbedarf") or "ganze Platten").lower().startswith("ganze")
        liste, fehlt = [], []
        for nr, menge in self.bedarf.items():
            m = self.mat(nr)
            einheit = m.einheit if m else ""
            grund = self.bedarf_grund[nr]
            if "Fläche netto" in grund:
                n_pl, fl, fb, nutz, std = (self.platten_zaehlen(nr) if ist_m2(einheit) and ganze else (0, 0, 0, 0, False))
                if n_pl > 0:
                    menge = n_pl * fl * fb / 1_000_000
                    grund = (f"{n_pl} ganze Platte(n) {zahl(fl)} x {zahl(fb)} mm, Ausnutzung {nutz:.0f} %"
                             + (" (Standardformat aus Regeln)" if std else ""))
                else:
                    menge *= 1 + vs
                    grund += f" + {vs * 100:.0f} % Verschnitt"
            einheit_l = einheit.lower()
            menge = float(aufrunden(menge)) if einheit_l.startswith("stk") or einheit_l in ("paar", "set") else round(menge, 3)
            ek = m.ek if m and m.ek else None
            if ek is None:
                fehlt.append(nr)
            liste.append({"material": nr, "bezeichnung": m.bezeichnung if m else "(fehlt im Materialstamm)",
                          "einheit": einheit, "menge": menge, "grund": grund, "ek": ek,
                          "kosten": round(ek * menge, 2) if ek else None})
        kosten = sum(x["kosten"] or 0 for x in liste)
        try:
            faktor = float(str(self.e.get("schnellfaktor") or "").replace(",", ".")) or self.r("SCHNELL_FAKTOR")
        except ValueError:
            faktor = self.r("SCHNELL_FAKTOR")
        self.kennzahlen["Materialkosten netto (EK)"] = round(kosten, 2)
        self.kennzahlen[f"Schnellpreis (Material x {zahl(faktor)}) – ohne Lohn"] = round(kosten * faktor, 0)
        if fehlt:
            self.pruef("Preise", GELB, "Kein EK-Preis im Materialstamm: " + ", ".join(fehlt))
        return sorted(liste, key=lambda x: x["material"])

    def platten_zaehlen(self, nr):
        """Streifen-Zuschnitt wie PlattenZaehlen(): Teile mit Maserung bleiben längs, ohne Maserung darf gedreht werden."""
        m = self.mat(nr)
        fl, fb = platten_format(m.format if m else "")
        std = False
        if fl <= 0 or fb <= 0:
            fl, fb, std = self.R.r("PLATTE_L"), self.R.r("PLATTE_B"), True
        kerf, saum = self.R.r("SAEGE"), self.R.r("BESAEUM")
        lp, bp = fl - 2 * saum + kerf, fb - 2 * saum + kerf
        stuecke, flaeche = [], 0.0
        for t in self.teile:
            if t["l"] is not None and t["material"] == nr:
                for _ in range(int(t["menge"])):
                    stuecke.append((t["zl"] + kerf, t["zb"] + kerf, not t["maser"]))
                    flaeche += t["zl"] * t["zb"]
        if not stuecke:
            return 0, fl, fb, 0, std
        stuecke.sort(key=lambda x: (x[1], x[0]), reverse=True)  # nach Breite, dann Länge absteigend
        streifen, platten = [], []  # streifen: [breite, belegte Länge]; platten: belegte Breite
        for pl, pb, drehbar in stuecke:
            ok = False
            for a, bb in ((pl, pb), (pb, pl)) if drehbar else ((pl, pb),):
                if a <= lp and bb <= bp:
                    for st in streifen:
                        if bb <= st[0] and st[1] + a <= lp:
                            st[1] += a
                            ok = True
                            break
                    if not ok:
                        for i, belegt in enumerate(platten):
                            if belegt + bb <= bp:
                                streifen.append([bb, a])
                                platten[i] += bb
                                ok = True
                                break
                if ok:
                    break
            if not ok:
                a, bb = pl, pb
                if (a > lp or bb > bp) and drehbar:
                    a, bb = pb, pl
                if a <= lp and bb <= bp:
                    platten.append(bb)
                    streifen.append([bb, a])
        n = len(platten)
        return n, fl, fb, (flaeche / (n * fl * fb) * 100 if n else 0), std


def zahl(x) -> str:
    """Zahl ohne überflüssige Nachkommastellen, deutsches Komma (802 statt 802.0; 2,5)."""
    x = round(float(x), 1)
    return (f"{int(x)}" if x == int(x) else f"{x:.1f}").replace(".", ",")


def berechnen(eingaben: dict, regeln: Regeln, material) -> dict:
    return Rechner(eingaben, regeln, material).rechnen()
