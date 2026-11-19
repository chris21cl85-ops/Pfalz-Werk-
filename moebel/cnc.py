"""CNC-Export wie PW_Moebel_CNC_Export: Teileliste.csv, Bohrbild.csv, Parameterliste.csv und je Plattenteil eine DXF
(Kontur, Bohrungen, Rückwandnut). Bohrbild ist ein Vorschlag nach den Werkstatt-Regeln – vor der CNC-Übernahme prüfen."""
import io
import re
import zipfile

from . import rechner
from .models import Regelwerk

UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def zp(x) -> str:
    """Dezimalpunkt für CNC/DXF (wie ZahlP: 0.0##)."""
    t = f"{float(x or 0):.3f}".rstrip("0")
    return t + "0" if t.endswith(".") else t


def ascii_text(s: str) -> str:
    return (s or "").translate(UMLAUTE).encode("ascii", "replace").decode()


def dateiname(s: str) -> str:
    return re.sub(r'[\\\\/:*?"<>| ]', "_", ascii_text(s))


def linie(x1, y1, x2, y2, layer):
    return f"0\r\nLINE\r\n8\r\n{layer}\r\n10\r\n{zp(x1)}\r\n20\r\n{zp(y1)}\r\n30\r\n0\r\n11\r\n{zp(x2)}\r\n21\r\n{zp(y2)}\r\n31\r\n0\r\n"


def kreis(x, y, r, layer):
    return f"0\r\nCIRCLE\r\n8\r\n{layer}\r\n10\r\n{zp(x)}\r\n20\r\n{zp(y)}\r\n30\r\n0\r\n40\r\n{zp(r)}\r\n"


def text(x, y, h, t):
    return f"0\r\nTEXT\r\n8\r\nTEXT\r\n10\r\n{zp(x)}\r\n20\r\n{zp(y)}\r\n30\r\n0\r\n40\r\n{zp(h)}\r\n1\r\n{t}\r\n"


class Bohrbild:
    def __init__(self, regeln: rechner.Regeln, verb_abstand, s, d_r):
        self.R, self.abst, self.s, self.d_r = regeln, verb_abstand or 150, s or 19, d_r
        self.csv = []

    def plus(self, tid, teil, flaeche, x, y, dm, tiefe, art, dxf):
        self.csv.append([tid, teil, flaeche, zp(x), zp(y), "", "", zp(dm), zp(tiefe), art])
        if "kante" not in flaeche.lower():
            dxf.append(kreis(x, y, dm / 2, "BOHRUNG_D" + zp(dm).replace(".", "_")))

    def teil(self, tid, teil, l, b, bearb, dxf):
        """Wie BohrbildTeil(): X entlang L (0 = unten/links), Y entlang B (0 = vorn bzw. Bandseite)."""
        R, nm = self.R, teil.lower()
        if ("seite" in nm or "mittelwand" in nm) and not nm.startswith("kasten"):
            if "lochreihe" in bearb.lower():
                x = R.r("LOCH_UNTEN")
                while x <= l - R.r("LOCH_UNTEN") + 0.01:
                    self.plus(tid, teil, "Fläche", x, R.r("LOCH_VORN"), 5, 12, "Lochreihe vorn", dxf)
                    self.plus(tid, teil, "Fläche", x, b - R.r("LOCH_HINTEN"), 5, 12, "Lochreihe hinten", dxf)
                    x += R.r("RASTER")
            n = rechner.aufrunden((b - 64) / self.abst) + 1
            for i in range(n):
                y = 32 + i * (b - 64) / max(1, n - 1)
                self.plus(tid, teil, "Fläche", self.s / 2, y, R.r("DUEBEL_D"), R.r("DUEBEL_T_FL"), "Verbinder Boden", dxf)
                self.plus(tid, teil, "Fläche", l - self.s / 2, y, R.r("DUEBEL_D"), R.r("DUEBEL_T_FL"),
                          "Verbinder Deckel/Traverse", dxf)
            if "montageplatten" in bearb.lower():
                nb = max(2, R.band_anzahl(l))
                for i in range(nb):
                    x = R.r("BAND_MITTE") + i * (l - 2 * R.r("BAND_MITTE")) / (nb - 1)
                    self.plus(tid, teil, "Fläche", x - 16, R.r("LOCH_VORN"), 5, 12, "Montageplatte", dxf)
                    self.plus(tid, teil, "Fläche", x + 16, R.r("LOCH_VORN"), 5, 12, "Montageplatte", dxf)
            if "nut " in bearb.lower():
                breite = self.d_r + 0.5
                y = b - R.r("NUT_ABSTAND") - breite / 2
                self.csv.append([tid, teil, "Fläche", "0", zp(y), zp(l), zp(y), zp(breite), zp(R.r("NUT_TIEFE")),
                                 "Nut Rückwand (X1;Y1;X2;Y2;Breite;Tiefe)"])
                dxf.append(linie(0, y - breite / 2, l, y - breite / 2, "NUT") + linie(0, y + breite / 2, l, y + breite / 2, "NUT"))
        elif nm.startswith("tür") or "höhenfries" in nm:
            nb = max(2, R.band_anzahl(l))
            for i in range(nb):
                x = R.r("BAND_MITTE") + i * (l - 2 * R.r("BAND_MITTE")) / (nb - 1)
                self.plus(tid, teil, "Fläche innen", x, R.r("TOPF_ABST"), R.r("TOPF_D"), R.r("TOPF_TIEFE"), "Topfband", dxf)
        elif nm.startswith(("boden", "deckel", "traverse", "zwischenboden")):
            n = rechner.aufrunden((b - 64) / self.abst) + 1
            for i in range(n):
                y = b / 2 if b < 100 else 32 + i * (b - 64) / max(1, n - 1)
                self.plus(tid, teil, "Kante links", 0, y, R.r("DUEBEL_D"), R.r("DUEBEL_T_KA"), "Verbinder", dxf)
                self.plus(tid, teil, "Kante rechts", l, y, R.r("DUEBEL_D"), R.r("DUEBEL_T_KA"), "Verbinder", dxf)
                if b < 100:
                    break


def _csv(zeilen) -> bytes:
    return ("\r\n".join(";".join(str(z).replace(";", ",") for z in zeile) for zeile in zeilen) + "\r\n").encode("utf-8-sig")


def export_zip(position, ergebnis) -> tuple[bytes, int]:
    """ZIP mit allen Dateien; liefert (Bytes, Anzahl DXF)."""
    from .dienst import materialstamm
    regeln = Regelwerk.laden().als_regeln()
    e = position.eingaben
    mat = materialstamm()
    m_k, m_r = mat(e.get("mat_korpus")), mat(e.get("mat_rueckwand"))
    _, abst = regeln.verbinder_id(e.get("verbindung") or "Dübel")
    bohr = Bohrbild(regeln, abst, m_k.staerke if m_k else 19, m_r.staerke if m_r else 0)
    pid = position.positions_id
    teile = [["Teile-ID", "Teil", "Gruppe", "Menge", "Fertig L", "Fertig B", "Dicke", "Zuschnitt L", "Zuschnitt B",
              "Material-ID", "Kante L1", "Kante L2", "Kante B1", "Kante B2", "Maserung", "Bearbeitung", "Einbauort"]]
    puffer = io.BytesIO()
    n_dxf = 0
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        nr = 0
        for t in ergebnis.get("teile", []):
            if t["l"] is None:
                continue
            nr += 1
            tid = f"{pid}-{nr}"
            teile.append([tid, t["teil"], t["gruppe"], f"{t['menge']:g}", zp(t["l"]), zp(t["b"]), zp(t["dicke"]), zp(t["zl"]),
                          zp(t["zb"]), t["material"], t["kl1"], t["kl2"], t["kb1"], t["kb2"], t["maser"], t["bearbeitung"],
                          t["ort"]])
            l, b = float(t["l"]), float(t["b"])
            dxf = ["0\r\nSECTION\r\n2\r\nENTITIES\r\n", linie(0, 0, l, 0, "KONTUR"), linie(l, 0, l, b, "KONTUR"),
                   linie(l, b, 0, b, "KONTUR"), linie(0, b, 0, 0, "KONTUR"),
                   text(5, b + 10, 10, ascii_text(f"{tid} {t['teil']} {zp(l)} x {zp(b)} x {zp(t['dicke'])}"))]
            bohr.teil(tid, t["teil"], l, b, t["bearbeitung"] or "", dxf)
            dxf.append("0\r\nENDSEC\r\n0\r\nEOF\r\n")
            z.writestr(f"{dateiname(tid + '_' + t['teil'])}.dxf", "".join(dxf).encode("ascii", "replace"))
            n_dxf += 1
        z.writestr("Teileliste.csv", _csv(teile))
        z.writestr("Bohrbild.csv", _csv([["Teile-ID", "Teil", "Flaeche", "X", "Y", "X2", "Y2", "Durchmesser/Breite", "Tiefe",
                                           "Art"]] + bohr.csv))
        from .dienst import BESCHRIFTUNG, _wert
        par = [["Parameter", "Wert"], ["Position-ID", pid]] + [[BESCHRIFTUNG.get(k, k), _wert(k, v)] for k, v in e.items()]
        z.writestr("Parameterliste.csv", _csv(par))
        z.writestr("LIESMICH.txt", ("Bohrbild ist ein Vorschlag nach den Werkstatt-Regeln (PFALZ-WERK Möbelrechner) - vor der "
                                     "CNC-Übernahme prüfen.\r\nKoordinaten: X entlang Länge, Y entlang Breite (0 = vorn bzw. "
                                     "Bandseite), Maße in mm, Dezimalpunkt.\r\n").encode("utf-8-sig"))
    return puffer.getvalue(), n_dxf
