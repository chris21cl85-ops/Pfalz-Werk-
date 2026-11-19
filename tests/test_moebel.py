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
