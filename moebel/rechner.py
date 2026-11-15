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

# Werkstatt-Standards (RegelnAnlegen + RegelnStufe3) – werden aus „Möbel-Regeln“ übernommen, hier nur Startwerte
STANDARD_REGELN = {
    "SOCKEL_H": 100, "SOCKEL_LUFT": 3, "SOCKEL_RUECK": 50, "FUSS_ABSTAND": 600, "TRAV_B": 100,
    "FUGE_AUSSEN": 3, "FUGE_MITTE": 3, "FUGE_OBEN": 3, "FUGE_EINLAGE": 2, "TUER_MAX_B": 600, "TUER_MAX_H": 2400,
    "NUT_TIEFE": 8, "NUT_ABSTAND": 10, "FB_LUFT": 2, "FB_ABZUG_T": 20, "BODTR_JE": 4, "KANTEN_ZUGABE": 50,
    "FRAESZUGABE": 0, "VERSCHNITT": 20, "BAND_MITTE": 100, "LOCH_VORN": 37, "RASTER": 32, "DIAG_TOL": 1,
    "KIPP_LUFT": 10, "RW_DUENN": 3, "RW_DUENN_B": 1000, "RW_DUENN_H": 2000,
    "SAEGE": 4, "BESAEUM": 10, "PLATTE_L": 2800, "PLATTE_B": 2070, "SCHNELL_FAKTOR": 3,
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
                     "kante_korpus": "ABS-W-08", "kante_front": "ABS-W-20"}

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


class Rechner:
    def __init__(self, eingaben: dict, regeln: Regeln, material):
        """material: Funktion Material-Nr. → Material oder None."""
        self.e, self.R, self._mat = eingaben, regeln, material
        self.teile, self.pruefungen, self.kennzahlen = [], [], {}
        self.bedarf, self.bedarf_grund = {}, {}

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
            hinweis = (hinweis + " ⚠ keine Material-Nr. im Beschlagsystem hinterlegt").strip()
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
        if front_da and tuerart == "Aufschlag":
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

        # ---- Fachböden
        if n_fb > 0:
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

        # ---- Fronten
        if front_da:
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
        return self._abschluss(anz)

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
                "ampel": ampel, "kosten": round(sum(x["kosten"] or 0 for x in bedarf), 2)}

    def bedarf_final(self):
        """Wie BedarfFinal(): Platten als ganze Platten (Streifenzuschnitt), sonst + Verschnitt; Stück aufrunden."""
        vs = self.r("VERSCHNITT") / 100
        liste, fehlt = [], []
        for nr, menge in self.bedarf.items():
            m = self.mat(nr)
            einheit = m.einheit if m else ""
            grund = self.bedarf_grund[nr]
            if "Fläche netto" in grund:
                n_pl, fl, fb, nutz, std = (self.platten_zaehlen(nr) if ist_m2(einheit) else (0, 0, 0, 0, False))
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
