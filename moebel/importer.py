"""Import Blatt „Möbel-Regeln“ (wie RegelnAnlegen im Makro): A/B Schlüssel/Wert (Zeilen 4–120),
O–W Beschlagsysteme, Y/Z Bänder je Türhöhe, AB/AC Fachboden-Grenzen, AE–AG Verbinder, A90–A94/B Standardmaterial.
Zahlen-Regeln nur, solange sie im Programm nicht von Hand geändert wurden; Tabellen immer."""
from importe.dienst import Importer, als_text, registrieren
from material.importer import als_zahl

from .models import Regelwerk

STANDARD_NAMEN = {"korpus": "korpus", "front": "front", "rückwand": "rueckwand", "kante korpus": "kante_korpus",
                  "kante front": "kante_front", "kastenmaterial (holzkasten)": "kasten",
                  "kastenboden (holzkasten)": "kastenboden"}


@registrieren
class MoebelRegelImporter(Importer):
    blatt = "Möbel-Regeln"
    titel = "Möbel-Regeln (Werkstatt-Standards)"
    reihenfolge = 70
    spalten = {"A": "key", "B": "wert", "O": "sys", "P": "s1", "Q": "s2", "R": "s3", "S": "s4", "T": "s5", "U": "s6",
               "V": "s7", "W": "s8", "Y": "band_h", "Z": "band_n", "AB": "fb_s", "AC": "fb_max", "AE": "v_art",
               "AF": "v_nr", "AG": "v_abst", "AP": "nl"}
    startzeile = 4
    endzeile = 120

    def __init__(self):
        self.rw = Regelwerk.laden()
        self.gesperrt = self.rw.im_programm_geaendert
        self.neu = {"werte": {}, "systeme": {}, "baender": [], "fachboden": [], "verbinder": {}, "standardmaterial": {},
                    "nennlaengen": []}

    def zeile_uebernehmen(self, z):
        key = als_text(z["key"])
        if key and key.upper() == key and " " not in key and als_zahl(z["wert"]) is not None and als_zahl(z["wert"]) is not False:
            self.neu["werte"][key] = float(als_zahl(z["wert"]))
        elif key.lower() in STANDARD_NAMEN and als_text(z["wert"]):
            self.neu["standardmaterial"][STANDARD_NAMEN[key.lower()]] = als_text(z["wert"])
        if als_text(z["sys"]) and als_text(z["sys"]) != "Beschlagsystem":
            self.neu["systeme"][als_text(z["sys"])] = [als_text(z[f"s{i}"]) for i in range(1, 9)]
        if als_zahl(z["band_h"]) and als_zahl(z["band_n"]):
            self.neu["baender"].append([float(als_zahl(z["band_h"])), int(als_zahl(z["band_n"]))])
        if als_zahl(z["fb_s"]) and als_zahl(z["fb_max"]):
            self.neu["fachboden"].append([float(als_zahl(z["fb_s"])), float(als_zahl(z["fb_max"]))])
        nl = als_zahl(z["nl"])
        if nl and nl is not False and nl > 0:
            self.neu["nennlaengen"].append(float(nl))
        if als_text(z["v_art"]) and als_text(z["v_nr"]):
            self.neu["verbinder"][als_text(z["v_art"])] = [als_text(z["v_nr"]), float(als_zahl(z["v_abst"]) or 150)]
        for feld, wert in self.neu.items():
            if wert and not (self.gesperrt and feld == "werte"):  # im Programm geänderte Zahlen bleiben
                aktuell = getattr(self.rw, feld)
                if isinstance(aktuell, dict) and feld in ("werte", "standardmaterial"):
                    aktuell = {**aktuell, **wert}
                else:
                    aktuell = wert
                setattr(self.rw, feld, aktuell)
        self.rw.save()
        return "geaendert"

    def zusatz(self):
        vorsatz = ("Zahlen-Regeln wurden im Programm geändert und bleiben; Tabellen aus der Excel übernommen. "
                   if self.gesperrt else "")
        return vorsatz + (f"{len(self.neu['werte'])} Regeln, {len(self.neu['systeme'])} Beschlagsysteme, "
                f"{len(self.neu['baender'])} Band-Stufen, {len(self.neu['verbinder'])} Verbinder")
