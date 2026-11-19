from decimal import Decimal

import pytest
from django.urls import reverse
from openpyxl import Workbook

from importe.dienst import ausfuehren
from kalkulation.models import Stuecklistenposition
from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from material.models import Material
from moebel import dienst, rechner
from moebel.models import MoebelPosition, Regelwerk
from projekte.models import Projekt

pytestmark = pytest.mark.django_db
S = Stuecklistenposition.Status

UNTERSCHRANK = {"typ": "Unterschrank", "bezeichnung": "Spüle links", "anzahl": 1, "breite": 600, "hoehe": 820,
                "tiefe": 560, "bauweise": "A", "abschluss": "Traversen", "sockel": "Stellfüße mit Blende",
                "tueren": "automatisch", "tuerart": "Aufschlag", "fachboeden": 1, "verbindung": "Dübel",
                "rueckwand_art": "eingenutet", "mat_korpus": "PL-WEI-P2-19", "mat_front": "PL-WEI-P2-19",
                "mat_rueckwand": "HDF-08", "kante_korpus": "ABS-W-08", "kante_front": "ABS-W-20", "beschlagsystem": "Blum"}


@pytest.fixture
def stamm(db):
    def m(nr, bez, einheit, staerke=None, ek=None, fmt="", gruppe=""):
        return Material.objects.create(materialnr=nr, bezeichnung=bez, einheit=einheit, format=fmt, produktgruppe=gruppe,
                                       staerke_mm=Decimal(str(staerke)) if staerke else None,
                                       ek_netto=Decimal(str(ek)) if ek is not None else None)
    m("PL-WEI-P2-19", "Spanplatte weiß 19", "m²", 19, 12.5, "2800 x 2070 mm", "Platten")
    m("HDF-08", "HDF 8", "m²", 8, 6, "2800 x 2070 mm", "Platten")
    m("ABS-W-08", "ABS weiß 0,8", "lfm", ek=0.3, gruppe="Kanten")
    m("ABS-W-20", "ABS weiß 2", "lfm", ek=0.6, gruppe="Kanten")
    for nr in ("BL-BODTR-5", "BL-SOCKELFUSS", "BL-SOCKELCLIP", "BL-BLUM-TB-110", "BL-BLUM-MPL", "BL-GRIFF", "DUE-HOLZ-8X40"):
        m(nr, nr, "Stk", ek=0.5, gruppe="Beschläge")


@pytest.fixture
def projekt():
    return Projekt.objects.create(projektnr="P-2026-001", name="Küche", status="Auftrag",
                                  kunde=Kunde.objects.create(kundennr="K-1", name="Weber"))


def teil(erg, name):
    return next(t for t in erg["teile"] if t["teil"] == name)


# ------------------------------------------------------------------ Rechnen wie Makro (Stufe 1)
def test_unterschrank_masse(stamm):
    erg = dienst.rechnen(UNTERSCHRANK)
    seite, rw, tuer = teil(erg, "Seite"), teil(erg, "Rückwand"), teil(erg, "Tür")
    assert (seite["menge"], seite["l"], seite["b"]) == (2, 720, 560)
    assert (rw["l"], rw["b"]) == (696, 576)
    assert (tuer["l"], tuer["b"], tuer["zl"], tuer["zb"]) == (717, 597, 713, 593)  # Zuschnitt minus 2-mm-Kante
    assert teil(erg, "Verbinder Dübel")["menge"] == 18 and teil(erg, "Topfband")["menge"] == 2
    assert erg["ampel"] == rechner.GELB  # 32er-Raster-Hinweis
    raster = next(p for p in erg["pruefungen"] if p["pruefung"] == "32er-Raster")
    assert "723" in raster["hinweis"]
    platte = next(b for b in erg["bedarf"] if b["material"] == "PL-WEI-P2-19")
    assert platte["menge"] == pytest.approx(5.796) and "1 ganze Platte" in platte["grund"]


def test_anzahl_multipliziert(stamm):
    erg = dienst.rechnen({**UNTERSCHRANK, "anzahl": 3})
    assert teil(erg, "Seite")["menge"] == 6 and teil(erg, "Verbinder Dübel")["menge"] == 54


def test_rot_ohne_korpusmaterial_und_bei_zu_breitem_fachboden(stamm):
    assert dienst.rechnen({**UNTERSCHRANK, "mat_korpus": ""})["ampel"] == rechner.ROT
    erg = dienst.rechnen({**UNTERSCHRANK, "breite": 1200, "tueren": "2 Türen"})
    fb = next(p for p in erg["pruefungen"] if p["pruefung"] == "Fachboden-Durchbiegung")
    assert fb["status"] == rechner.ROT and erg["ampel"] == rechner.ROT


def test_abweichung_ueberschreibt_regel(stamm):
    normal = teil(dienst.rechnen(UNTERSCHRANK), "Tür")
    breit = teil(dienst.rechnen({**UNTERSCHRANK, "abweichungen": {"FUGE_AUSSEN": 5}}), "Tür")
    assert breit["b"] == normal["b"] - 2  # Fuge außen 5 statt 3 mm (je Seite die Hälfte)


def test_regel_aus_regelwerk(stamm):
    rw = Regelwerk.laden()
    rw.werte = {**rw.werte, "SOCKEL_H": 150}
    rw.save()
    assert teil(dienst.rechnen(UNTERSCHRANK), "Seite")["l"] == 670


# ------------------------------------------------------------------ Speichern, Version, Variante
def test_speichern_version_und_variante(stamm, projekt, chef):
    p = dienst.speichern(projekt=projekt, eingaben=UNTERSCHRANK, benutzer=chef)
    assert (p.pos, p.positions_id, p.version, p.bezeichnung) == ("M01", "P-2026-001-M01", 1, "Spüle links")
    assert p.ergebnis["kosten"] > 0
    dienst.speichern(projekt=projekt, eingaben=UNTERSCHRANK, benutzer=chef, position=p)
    assert p.version == 1  # unverändert → keine neue Version
    dienst.speichern(projekt=projekt, eingaben={**UNTERSCHRANK, "breite": 450}, benutzer=chef, position=p)
    assert p.version == 2
    kopie = dienst.kopieren(p, chef)
    assert kopie.pos == "M02" and kopie.bezeichnung == "Spüle links (Variante)" and kopie.eingaben["breite"] == 450
    assert Protokolleintrag.objects.filter(aktion="moebel_angelegt").count() == 2
    assert Protokolleintrag.objects.filter(aktion="moebel_geaendert").count() == 2


# ------------------------------------------------------------------ In die Stückliste
def test_in_stueckliste_ersetzt_geplante(stamm, projekt, chef):
    p = dienst.speichern(projekt=projekt, eingaben=UNTERSCHRANK, benutzer=chef)
    n = dienst.in_stueckliste(p, chef)
    zeilen = Stuecklistenposition.objects.filter(moebel=p)
    assert n == zeilen.count() == len(p.ergebnis["bedarf"]) and all(z.status == S.GEPLANT for z in zeilen)
    assert p.status == MoebelPosition.Status.STUECKLISTE
    platte = zeilen.get(material__materialnr="PL-WEI-P2-19")
    assert platte.menge == Decimal("5.796") and platte.ek == Decimal("12.5")
    dienst.speichern(projekt=projekt, eingaben={**UNTERSCHRANK, "fachboeden": 0}, benutzer=chef, position=p)
    assert p.status == MoebelPosition.Status.ENTWURF  # nach Änderung neu übernehmen
    dienst.in_stueckliste(p, chef)
    assert Stuecklistenposition.objects.filter(moebel=p, material__materialnr="BL-BODTR-5").count() == 0
    assert Stuecklistenposition.objects.filter(moebel=p).count() == n - 1


def test_keine_uebernahme_bei_rot_oder_weiterverarbeitet(stamm, projekt, chef):
    rot = dienst.speichern(projekt=projekt, eingaben={**UNTERSCHRANK, "mat_korpus": ""}, benutzer=chef)
    with pytest.raises(dienst.MoebelFehler, match="Rot"):
        dienst.in_stueckliste(rot, chef)
    p = dienst.speichern(projekt=projekt, eingaben=UNTERSCHRANK, benutzer=chef)
    dienst.in_stueckliste(p, chef)
    Stuecklistenposition.objects.filter(moebel=p).update(status=S.BENOETIGT)
    with pytest.raises(dienst.MoebelFehler, match="weiterverarbeitet"):
        dienst.in_stueckliste(p, chef)
    assert Stuecklistenposition.objects.filter(moebel=p, status=S.BENOETIGT).exists()


def test_geplant_zaehlt_nicht_in_kalkulation(stamm, projekt, chef):
    from kalkulation.models import Kalkulation
    p = dienst.speichern(projekt=projekt, eingaben=UNTERSCHRANK, benutzer=chef)
    dienst.in_stueckliste(p, chef)
    assert Kalkulation.objects.create(projekt=projekt, material_manuell=Decimal("99")).material == Decimal("99")


# ------------------------------------------------------------------ Seiten
def test_seiten_neu_berechnen_speichern(stamm, projekt, chef_client):
    daten = {k: v for k, v in UNTERSCHRANK.items()}
    daten.update({"projekt": projekt.pk, "breite": "600", "hoehe": "820", "tiefe": "560,0", "anzahl": "1"})
    seite = chef_client.get(reverse("moebel:neu") + f"?projekt={projekt.pk}")
    assert seite.status_code == 200 and "PL-WEI-P2-19 – Spanplatte weiß 19" in seite.content.decode()
    vorschau = chef_client.post(reverse("moebel:neu"), {**daten, "aktion": "berechnen"})
    text = vorschau.content.decode()
    assert "Vorschau – noch nicht gespeichert" in text and "713 × 593" in text and MoebelPosition.objects.count() == 0
    antwort = chef_client.post(reverse("moebel:neu"), {**daten, "aktion": "speichern"})
    p = MoebelPosition.objects.get()
    assert antwort.status_code == 302 and antwort["Location"] == p.get_absolute_url()
    assert p.eingaben["tiefe"] == 560 and p.eingaben["abweichungen"] == {}
    detail = chef_client.get(p.get_absolute_url()).content.decode()
    assert "P-2026-001-M01" in detail and "Ampel gelb" in detail and "Teileliste" in detail
    # Bearbeiten mit Abweichung und deutschem Komma
    chef_client.post(reverse("moebel:bearbeiten", args=[p.pk]), {**daten, "abw_FUGE_AUSSEN": "2,5", "aktion": "speichern"})
    p.refresh_from_db()
    assert p.version == 2 and p.eingaben["abweichungen"] == {"FUGE_AUSSEN": 2.5}
    assert chef_client.get(reverse("moebel:bearbeiten", args=[p.pk])).status_code == 200


def test_seiten_fehler_im_formular(stamm, projekt, chef_client):
    antwort = chef_client.post(reverse("moebel:neu"), {**UNTERSCHRANK, "projekt": projekt.pk, "breite": "abc",
                                                       "aktion": "speichern"})
    assert antwort.status_code == 200 and "Bitte die rot markierten Felder prüfen" in antwort.content.decode()
    assert MoebelPosition.objects.count() == 0


def test_seiten_detail_aktionen_und_pdf(stamm, projekt, chef, chef_client):
    p = dienst.speichern(projekt=projekt, eingaben=UNTERSCHRANK, benutzer=chef)
    chef_client.post(p.get_absolute_url(), {"aktion": "stueckliste"})
    assert Stuecklistenposition.objects.filter(moebel=p).exists()
    kalk = chef_client.get(reverse("kalkulation:projekt", args=[projekt.pk])).content.decode()
    assert "aus Möbelrechner" in kalk and "Möbelrechner (1 Möbel)" in kalk
    antwort = chef_client.post(p.get_absolute_url(), {"aktion": "kopieren"})
    assert antwort.status_code == 302 and MoebelPosition.objects.count() == 2
    pdf = chef_client.get(reverse("moebel:pdf", args=[p.pk]))
    assert pdf["Content-Type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    liste = chef_client.get(reverse("moebel:liste") + f"?projekt={projekt.pk}").content.decode()
    assert "P-2026-001-M02" in liste and "Spüle links (Variante)" in liste


def test_rote_ampel_meldung_auf_seite(stamm, projekt, chef, chef_client):
    p = dienst.speichern(projekt=projekt, eingaben={**UNTERSCHRANK, "mat_korpus": ""}, benutzer=chef)
    antwort = chef_client.post(p.get_absolute_url(), {"aktion": "stueckliste"}, follow=True)
    assert "keine Übernahme" in antwort.content.decode()


def test_regeln_seite(chef_client):
    seite = chef_client.get(reverse("moebel:regeln"))
    assert seite.status_code == 200 and "Sockelhöhe" in seite.content.decode()
    daten = {k: rechner.zahl(v) for k, v in rechner.STANDARD_REGELN.items()}
    daten["SOCKEL_H"] = "120"
    daten["FUGE_AUSSEN"] = "2,5"
    chef_client.post(reverse("moebel:regeln"), daten)
    rw = Regelwerk.laden()
    assert rw.werte["SOCKEL_H"] == 120 and rw.werte["FUGE_AUSSEN"] == 2.5 and rw.im_programm_geaendert
    assert Protokolleintrag.objects.filter(aktion="moebel_regeln_geaendert").exists()


@pytest.mark.parametrize("rolle,erwartet", [(Rolle.MEISTER, 200), (Rolle.ADMIN, 200), (Rolle.BUCHHALTUNG, 403),
                                            (Rolle.MITARBEITER, 403)])
def test_rechte(client, benutzer_mit_rolle, rolle, erwartet):
    client.force_login(benutzer_mit_rolle(rolle))
    assert client.get(reverse("moebel:liste")).status_code == erwartet
    assert client.get(reverse("moebel:regeln")).status_code == erwartet


def test_kachel_auf_startseite(chef_client):
    assert reverse("moebel:liste") in chef_client.get("/").content.decode()


# ------------------------------------------------------------------ Import „Möbel-Regeln“
def _regelmappe(pfad):
    mappe = Workbook()
    ws = mappe.active
    ws.title = "Möbel-Regeln"
    for _ in range(3):
        ws.append([])
    ws.append(["SOCKEL_H", 110] + [None] * 12 + ["Häfele", "HAE-TB", "HAE-MPL", "BL-BODTR-5", "", "", "", "", "",
                                                  None, 1000, 2, None, 19, 650, None, "Dübel", "DUE-10", 128])
    ws.append(["Korpus", "PL-EI-19"])
    mappe.save(pfad)


def test_import_regeln(tmp_path):
    pfad = tmp_path / "pw.xlsx"
    _regelmappe(pfad)
    ausfuehren(pfad, probelauf=False)
    rw = Regelwerk.laden()
    assert rw.werte["SOCKEL_H"] == 110 and rw.systeme == {"Häfele": ["HAE-TB", "HAE-MPL", "BL-BODTR-5", "", "", "", "", ""]}
    assert rw.baender == [[1000, 2]] and rw.fachboden == [[19, 650]] and rw.verbinder == {"Dübel": ["DUE-10", 128]}
    assert rw.standardmaterial["korpus"] == "PL-EI-19" and rw.standardmaterial["front"] == "PL-WEI-P2-19"


def test_import_laesst_im_programm_geaenderte_zahlen(tmp_path):
    rw = Regelwerk.laden()
    rw.werte = {**rw.werte, "SOCKEL_H": 130}
    rw.im_programm_geaendert = True
    rw.save()
    pfad = tmp_path / "pw.xlsx"
    _regelmappe(pfad)
    ausfuehren(pfad, probelauf=False)
    rw = Regelwerk.laden()
    assert rw.werte["SOCKEL_H"] == 130 and "Häfele" in rw.systeme


def test_import_regelwert_null(tmp_path):
    """Eine Regel mit Wert 0 (z. B. Kippmaß-Luft 0) muss übernommen werden – früher wurde 0 als „leer“ gelesen."""
    mappe = Workbook()
    ws = mappe.active
    ws.title = "Möbel-Regeln"
    for _ in range(3):
        ws.append([])
    ws.append(["KIPP_LUFT", 0])
    pfad = tmp_path / "pw.xlsx"
    mappe.save(pfad)
    ausfuehren(pfad, probelauf=False)
    assert Regelwerk.laden().werte["KIPP_LUFT"] == 0


# ------------------------------------------------------------------ Stufe 2: Aufteilung
@pytest.fixture
def kastenholz(stamm):
    Material.objects.create(materialnr="MPX-BI-15", bezeichnung="Multiplex Birke 15", einheit="m²",
                            staerke_mm=Decimal("15"), ek_netto=Decimal("30"), format="2500 x 1250 mm")
    Material.objects.create(materialnr="BL-FUE-400", bezeichnung="Führung NL 400 (Paar)", einheit="Paar",
                            ek_netto=Decimal("18"))


KOMMODE = {**UNTERSCHRANK, "typ": "Kommode", "bezeichnung": "Kommode Flur", "breite": 1000, "hoehe": 900, "tiefe": 450,
           "abschluss": "Deckel", "sockel": "Sockelkasten", "fachboeden": 0, "teilungsregel": "Goldener Schnitt",
           "zonen": [{"feld": 1, "zone": i, "art": "Schubkasten"} for i in (1, 2, 3)]}


def test_teilen_regeln():
    assert rechner.teilen(791, [0, 0, 0], "gleich") == ([265, 263, 263], "")
    assert rechner.teilen(791, [0, 0, 0], "Goldener Schnitt")[0] == [396, 244, 151]
    assert rechner.teilen(791, [0, 0, 0], "Fibonacci")[0] == [397, 263, 131]
    assert rechner.teilen(791, [0, 0, 0], "Raster 32")[0] == [279, 256, 256]
    assert rechner.teilen(791, [0, 200, 0], "gleich")[0] == [296, 200, 295]
    assert rechner.teilen(500, [300, 300], "gleich")[1].startswith("Feste Maße ergeben 600")
    assert "Kein Platz" in rechner.teilen(500, [300, 300, 0], "gleich")[1]


def test_kommode_schubkaesten(kastenholz):
    erg = dienst.rechnen(KOMMODE)
    fronten = [t for t in erg["teile"] if t["teil"] == "Schubkastenfront"]
    assert [(t["l"], t["b"]) for t in fronten] == [(997, 396), (997, 244), (997, 151)]
    seite = next(t for t in erg["teile"] if t["teil"] == "Kastenseite")
    boden = next(t for t in erg["teile"] if t["teil"] == "Kastenboden")
    assert (seite["l"], seite["b"], seite["material"]) == (390, 356, "MPX-BI-15")  # NL 400 − 10, Front − 40
    assert (boden["l"], boden["b"]) == (382, 905)
    assert teil(erg, "Zwischenboden")["menge"] == 2
    fuehrung = [t for t in erg["teile"] if t["teil"] == "Führung NL 400 (Paar)"]
    assert len(fuehrung) == 3 and fuehrung[0]["material"] == "BL-FUE-400"
    assert erg["kennzahlen"]["Feld 1 Fronthöhen (unten zuerst)"] == "396 / 244 / 151 mm (Goldener Schnitt)"
    assert [r["regel"] for r in erg["varianten"][0]["regeln"] if r["gewaehlt"]] == ["Goldener Schnitt"]
    assert not any("Tür" in t["teil"] for t in erg["teile"]) and erg["ampel"] != rechner.ROT


def test_felder_mittelwand_und_feste_breite(kastenholz):
    e = {**UNTERSCHRANK, "breite": 1200, "felder": 2, "feldbreiten": "400;Rest", "zonen": [
        {"feld": 1, "zone": 1, "art": "Schubkasten", "hoehe": 200}, {"feld": 1, "zone": 2, "art": "Tür", "fachboeden": 1},
        {"feld": 2, "zone": 1, "art": "Fach offen", "fachboeden": 2}]}
    erg = dienst.rechnen(e)
    assert teil(erg, "Mittelwand")["menge"] == 1 and erg["kennzahlen"]["Feldbreiten licht"] == "400 / 743 mm"
    q = next(p for p in erg["pruefungen"] if p["pruefung"] == "Querschnitt Felder")
    assert q["status"] == rechner.GRUEN
    front = teil(erg, "Schubkastenfront")
    assert front["b"] == 200 and front["l"] == 400 + 19 + 9.5 - 1.5 - 1.5  # Aufschlag: halbe Mittelwand, halbe Fugen
    fb = [t for t in erg["teile"] if t["teil"] == "Fachboden"]
    assert sorted(t["menge"] for t in fb) == [1, 2] and teil(erg, "Bodenträger")["menge"] in (4, 8)
    assert "Montageplatten-Bohrungen" in teil(erg, "Seite")["bearbeitung"]


def test_metallbox_und_fehler(kastenholz):
    box = dienst.rechnen({**KOMMODE, "kastensystem": "Metallbox"})
    assert teil(box, "Kastenboden (Box)")["b"] == 962 - 75 and not any(t["teil"] == "Kastenseite" for t in box["teile"])
    flach = dienst.rechnen({**KOMMODE, "tiefe": 250})
    assert any(p["status"] == rechner.ROT and "Nennlänge" in p["hinweis"] for p in flach["pruefungen"])
    niedrig = dienst.rechnen({**KOMMODE, "zonen": KOMMODE["zonen"] + [{"feld": 1, "zone": 4, "art": "Schubkasten", "hoehe": 80}],
                              "teilungsregel": "gleich"})
    assert any("zu klein" in p["hinweis"] for p in niedrig["pruefungen"])


def test_ergonomie_hochschrank(kastenholz):
    e = {**UNTERSCHRANK, "typ": "Hochschrank", "hoehe": 2300, "abschluss": "Deckel", "zonen": [
        {"feld": 1, "zone": 1, "art": "Tür", "hoehe": 700}, {"feld": 1, "zone": 2, "art": "Schubkasten", "hoehe": 200},
        {"feld": 1, "zone": 3, "art": "Schubkasten", "hoehe": 200}, {"feld": 1, "zone": 4, "art": "Tür", "fachboeden": 2}]}
    erg = dienst.rechnen(e)
    texte = [p["hinweis"] for p in erg["pruefungen"] if p["pruefung"].startswith("Ergonomie")]
    assert any("nur mit Tritt" in t for t in texte)


def test_formular_mit_zonen(kastenholz, projekt, chef_client):
    daten = {k: v for k, v in KOMMODE.items() if k != "zonen"}
    daten.update({"projekt": projekt.pk, "breite": "1000", "hoehe": "900", "tiefe": "450", "anzahl": "1", "felder": "1",
                  "zwischenboeden": "Ja", "kastensystem": "Holzkasten Unterflur", "kastenverbindung": "Dübel",
                  "z0_feld": "1", "z0_zone": "1", "z0_art": "Schubkasten", "z1_feld": "1", "z1_zone": "2",
                  "z1_art": "Schubkasten", "z1_hoehe": "250,5", "z2_art": "Schubkasten", "aktion": "speichern"})
    chef_client.post(reverse("moebel:neu"), daten)
    p = MoebelPosition.objects.get()
    assert [z["art"] for z in p.eingaben["zonen"]] == ["Schubkasten"] * 3 and p.eingaben["zonen"][1]["hoehe"] == 250.5
    assert p.eingaben["zonen"][2]["zone"] == 3  # leere Zonennummer = Zeile
    seite = chef_client.get(reverse("moebel:bearbeiten", args=[p.pk])).content.decode()
    assert 'value="250,5"' in seite
    detail = chef_client.get(p.get_absolute_url()).content.decode()
    assert "Teilungsregeln im Vergleich" in detail and "Feld 1 · Zone 2" in detail
    pdf = chef_client.get(reverse("moebel:etiketten", args=[p.pk]))
    assert pdf["Content-Type"] == "application/pdf" and pdf.content.startswith(b"%PDF")


def test_import_nennlaengen_und_kastenmaterial(tmp_path):
    from openpyxl.utils import column_index_from_string
    mappe = Workbook()
    ws = mappe.active
    ws.title = "Möbel-Regeln"
    ws.cell(row=4, column=column_index_from_string("AP"), value=350)
    ws.cell(row=5, column=column_index_from_string("AP"), value=500)
    ws.cell(row=95, column=1, value="Kastenmaterial (Holzkasten)")
    ws.cell(row=95, column=2, value="MPX-BI-12")
    pfad = tmp_path / "pw.xlsx"
    mappe.save(pfad)
    ausfuehren(pfad, probelauf=False)
    rw = Regelwerk.laden()
    assert rw.nennlaengen == [350, 500] and rw.als_regeln().material["kasten"] == "MPX-BI-12"
    assert rw.als_regeln().material["kastenboden"] == "HDF-08"


# ------------------------------------------------------------------ Stufe 3: Oberfläche, Profil, Änderungen
@pytest.fixture
def oel(stamm):
    Material.objects.create(materialnr="OF-OSMO-HWO", bezeichnung="Hartwachsöl", einheit="l", ek_netto=Decimal("40"))


def test_oberflaeche_bedarf_und_arbeitsgaenge(oel):
    erg = dienst.rechnen({**UNTERSCHRANK, "oberflaeche_front": "furniert, geölt"})
    tuer = teil(erg, "Tür")
    oel_bedarf = next(b for b in erg["bedarf"] if b["material"] == "OF-OSMO-HWO")
    front_m2 = sum(t["m2"] for t in erg["teile"] if t["gruppe"] == "Front")
    assert oel_bedarf["menge"] == pytest.approx(round(front_m2 * 2 * 0.08, 3)) and "Belag/Anstrich Front" in oel_bedarf["grund"]
    assert any("FU-EI-06 fehlt" in p["hinweis"] for p in erg["pruefungen"])  # Furnier nicht im Stamm → gelb
    codes = dict(erg["arbeitsgaenge"])
    assert codes["OF-010"] == "Front" and codes["WZ-020"] == "Front" and "CNC-010" in codes
    assert "Schliff 120 / 180" in erg["kennzahlen"]["Oberfläche Front"] and tuer is not None
    unbekannt = dienst.rechnen({**UNTERSCHRANK, "oberflaeche_korpus": "Gold"})
    assert any("nicht in der Oberflächen-Tabelle" in p["hinweis"] for p in unbekannt["pruefungen"])


def test_profil_plattenbedarf_faktor(stamm):
    erg = dienst.rechnen({**UNTERSCHRANK, "kantenprofil": "Radius 2 mm", "plattenbedarf": "Verschnittfaktor",
                          "schnellfaktor": 2.5})
    assert "Kantenprofil Radius 2 mm" in teil(erg, "Tür")["bearbeitung"]
    assert "Kantenprofil" not in teil(erg, "Seite")["bearbeitung"]
    platte = next(b for b in erg["bedarf"] if b["material"] == "PL-WEI-P2-19")
    assert "Verschnitt" in platte["grund"] and "ganze Platte" not in platte["grund"]
    assert "Schnellpreis (Material x 2,5) – ohne Lohn" in erg["kennzahlen"]


def test_cnc_regel(stamm):
    rw = Regelwerk.laden()
    rw.werte = {**rw.werte, "CNC_JA": 0}
    rw.save()
    codes = dict(dienst.rechnen(UNTERSCHRANK)["arbeitsgaenge"])
    assert "BE-010" in codes and "CNC-010" not in codes


def test_aenderungsverfolgung(stamm, projekt, chef, chef_client):
    p = dienst.speichern(projekt=projekt, eingaben=UNTERSCHRANK, benutzer=chef)
    dienst.in_stueckliste(p, chef)
    dienst.speichern(projekt=projekt, eingaben={**UNTERSCHRANK, "breite": 450, "tueren": "1 Tür"}, benutzer=chef, position=p)
    p.refresh_from_db()
    assert p.stueckliste_veraltet and p.version == 2
    text = p.aenderungen[0]["text"]
    assert "Breite: 600 -> 450" in text and "Türen: automatisch -> 1 Tür" in text and "Materialkosten" in text
    seite = chef_client.get(reverse("kalkulation:projekt", args=[projekt.pk])).content.decode()
    assert "Nach der Übernahme geändert" in seite
    assert "Breite: 600 -&gt; 450" in chef_client.get(p.get_absolute_url()).content.decode()
    dienst.in_stueckliste(p, chef)
    p.refresh_from_db()
    assert not p.stueckliste_veraltet


def test_import_oberflaechen(tmp_path):
    from openpyxl.utils import column_index_from_string as c
    mappe = Workbook()
    ws = mappe.active
    ws.title = "Möbel-Regeln"
    ws.cell(row=3, column=c("AW"), value="Oberfläche")
    for spalte, wert in {"AW": "Wachs", "AX": "SL-020;OF-010", "AY": "OF-WACHS", "AZ": 0.05, "BC": 1, "BD": "180"}.items():
        ws.cell(row=4, column=c(spalte), value=wert)
    pfad = tmp_path / "pw.xlsx"
    mappe.save(pfad)
    ausfuehren(pfad, probelauf=False)
    assert Regelwerk.laden().oberflaechen == [["Wachs", "SL-020;OF-010", "OF-WACHS", 0.05, "", 0, 1, "180", ""]]


# ------------------------------------------------------------------ Stufe 4/5: Massivholz, Rahmen, Modulbau, Formteile
@pytest.fixture
def massiv(stamm):
    Material.objects.create(materialnr="MH-EI-26", bezeichnung="Eiche massiv 26", einheit="m³", staerke_mm=Decimal("26"),
                            ek_netto=Decimal("2400"))
    Material.objects.create(materialnr="SPH-PO-04", bezeichnung="Pappelsperrholz 4", einheit="m²", staerke_mm=Decimal("4"),
                            ek_netto=Decimal("9"))
    Material.objects.create(materialnr="MDF-ROH-19", bezeichnung="MDF roh 19", einheit="m²", staerke_mm=Decimal("19"),
                            ek_netto=Decimal("7"))
    Material.objects.create(materialnr="KL-PVAC-D3", bezeichnung="Weißleim D3", einheit="kg", ek_netto=Decimal("6"))
    Material.objects.create(materialnr="MH-BU-52", bezeichnung="Buche massiv 52", einheit="m³", staerke_mm=Decimal("52"),
                            ek_netto=Decimal("1800"))


def test_massivholz_lamellen_grobvolumen_quellmass(massiv):
    regal = {**UNTERSCHRANK, "typ": "Regal", "hoehe": 1800, "tiefe": 300, "breite": 800, "abschluss": "Deckel",
             "sockel": "ohne Sockel", "tueren": "keine Tür / offen", "mat_korpus": "MH-EI-26", "kante_korpus": "",
             "fachboeden": 0, "rueckwand_art": "ohne"}
    erg = dienst.rechnen(regal)
    seite = teil(erg, "Seite")
    assert "Leimholz aus 4 Lamellen à 75 mm" in seite["hinweis"]
    assert any("fehlt das Quellmaß" in p["hinweis"] for p in erg["pruefungen"])
    holz = next(b for b in erg["bedarf"] if b["material"] == "MH-EI-26")
    grob_seite = 4 * (1800 + 100) * (75 + 7) * (26 + 7) * 2 / 1e9 * 1.1
    assert holz["menge"] > grob_seite and "Grobvolumen" in holz["grund"]
    assert {"MH-050", "MH-060", "WZ-010"} <= set(dict(erg["arbeitsgaenge"]))
    rw = Regelwerk.laden()
    rw.quellwerte = [["MH-EI", 0.36]]
    rw.save()
    erg = dienst.rechnen(regal)
    assert "arbeitet quer ca. 4,3 mm" in teil(erg, "Seite")["hinweis"]  # 300 × 0,36 % × 4 %
    assert any(p["pruefung"] == "Quellmaß Seite" and p["status"] == rechner.GELB for p in erg["pruefungen"])


def test_rahmen_und_fuellung(stamm):
    erg = dienst.rechnen({**UNTERSCHRANK, "tuerkonstruktion": "Rahmen + Füllung"})
    namen = {t["teil"]: t for t in erg["teile"]}
    assert (namen["Tür – Höhenfries"]["menge"], namen["Tür – Höhenfries"]["l"], namen["Tür – Höhenfries"]["b"]) == (2, 717, 60)
    assert (namen["Tür – Querfries"]["l"], namen["Tür – Füllung"]["l"], namen["Tür – Füllung"]["b"]) == (497, 613, 493)
    assert "Tür" not in namen and "BE-010" in dict(erg["arbeitsgaenge"])


def test_modulbau(stamm):
    e = {**UNTERSCHRANK, "breite": 1200, "bauweise": "M", "felder": 2}
    erg = dienst.rechnen(e)
    assert teil(erg, "Modulseite")["menge"] == 2 and not any(t["teil"] == "Mittelwand" for t in erg["teile"])
    assert teil(erg, "Boden Modul 1")["l"] == 562 and teil(erg, "Boden Modul 2")["l"] == 562
    assert teil(erg, "Korpusverbinder")["menge"] == 4 and erg["kennzahlen"]["Feldbreiten licht"] == "562 / 562 mm"
    tueren = [t for t in erg["teile"] if t["teil"] == "Tür"]
    assert [t["b"] for t in tueren] == [597, 597]
    q = next(p for p in erg["pruefungen"] if p["pruefung"] == "Querschnitt Felder")
    assert q["status"] == rechner.GRUEN and "(Modulbau)" in q["hinweis"]


def test_formteile(massiv):
    e = {**UNTERSCHRANK, "formteile": [
        {"bezeichnung": "Bogenzarge", "verfahren": "Formverleimung (Lagen)", "radius": 400, "winkel": 90, "hoehe": 120,
         "dicke": 12, "material": "SPH-PO-04", "anzahl": 1, "form_da": "Nein"},
        {"bezeichnung": "Korpusrundung", "verfahren": "Eingesägt (Kerben)", "radius": 300, "winkel": 90, "hoehe": 720,
         "dicke": 19, "material": "PL-WEI-P2-19", "anzahl": 1},
        {"bezeichnung": "Handlauf", "verfahren": "Dämpfen (Massivholz)", "radius": 600, "winkel": 90, "hoehe": 60,
         "dicke": 45, "material": "MH-BU-52", "anzahl": 1, "form_da": "Ja"},
        {"bezeichnung": "Fehler", "verfahren": "Segmentbau", "radius": 0, "winkel": 90, "hoehe": 10, "dicke": 10}]}
    erg = dienst.rechnen(e)
    f = {x["bezeichnung"]: x for x in erg["formteile"]}
    assert f["Bogenzarge"]["lagen"] == "3 Lagen à 4 mm" and f["Bogenzarge"]["status"] == rechner.GRUEN
    assert [t["teil"] for t in erg["teile"] if t["teil"].startswith("Bogenzarge Lage")] == [f"Bogenzarge Lage {i}" for i in (1, 2, 3)]
    assert teil(erg, "Form Bogenzarge")["material"] == "MDF-ROH-19"
    assert any(b["material"] == "KL-PVAC-D3" for b in erg["bedarf"])
    assert f["Korpusrundung"]["lagen"] == "9 Kerben" and f["Korpusrundung"]["hinweis"].startswith("Kerbenabstand 55,7")
    assert "Nur mit Biegeband" in f["Handlauf"]["hinweis"] and "108 min" in f["Handlauf"]["hinweis"]
    assert not any(t["teil"] == "Form Handlauf" for t in erg["teile"])  # Form vorhanden
    assert f["Fehler"]["status"] == rechner.ROT and erg["ampel"] == rechner.ROT
    assert erg["kennzahlen"]["Formteile"] == 4


def test_formular_formteil_und_tuer(massiv, projekt, chef_client):
    daten = {k: v for k, v in UNTERSCHRANK.items()}
    daten.update({"projekt": projekt.pk, "breite": "600", "hoehe": "820", "tiefe": "560", "anzahl": "1",
                  "tuerkonstruktion": "Rahmen + Füllung", "f0_bezeichnung": "Bogenzarge",
                  "f0_verfahren": "Formverleimung (Lagen)", "f0_radius": "400", "f0_winkel": "90", "f0_hoehe": "120",
                  "f0_dicke": "12,5", "f0_material": "SPH-PO-04", "f0_anzahl": "2", "f0_form_da": "Nein", "aktion": "speichern"})
    chef_client.post(reverse("moebel:neu"), daten)
    p = MoebelPosition.objects.get()
    assert p.eingaben["tuerkonstruktion"] == "Rahmen + Füllung" and p.eingaben["formteile"][0]["dicke"] == 12.5
    assert p.ergebnis["formteile"][0]["bezeichnung"] == "Bogenzarge"
    seite = chef_client.get(reverse("moebel:bearbeiten", args=[p.pk])).content.decode()
    assert 'value="12,5"' in seite and "materialnummern" in seite
    assert "Formteile" in chef_client.get(p.get_absolute_url()).content.decode()


def test_import_quellwerte(tmp_path):
    from openpyxl.utils import column_index_from_string as c
    mappe = Workbook()
    ws = mappe.active
    ws.title = "Möbel-Regeln"
    ws.cell(row=4, column=c("AI"), value="MH-EI")
    ws.cell(row=4, column=c("AJ"), value=0.36)
    ws.cell(row=97, column=1, value="Füllungsmaterial (leer = Frontmaterial)")
    ws.cell(row=97, column=2, value="FU-EI-06")
    pfad = tmp_path / "pw.xlsx"
    mappe.save(pfad)
    ausfuehren(pfad, probelauf=False)
    rw = Regelwerk.laden()
    assert rw.quellwerte == [["MH-EI", 0.36]] and rw.als_regeln().material["fuellung"] == "FU-EI-06"
