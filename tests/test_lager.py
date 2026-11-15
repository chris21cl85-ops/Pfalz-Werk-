import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from importe.dienst import ausfuehren
from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from lager import dienst
from lager.models import Bestellung, Gesperrt, Lagerbewegung, Wareneingang, bestand
from lieferanten.models import Lieferant
from material.models import Material
from projekte.models import Projekt
from rechnungen import eingang_dienst as ed

pytestmark = pytest.mark.django_db
HEUTE = timezone.localdate()


@pytest.fixture
def wickert():
    return Lieferant.objects.create(name="Holz Wickert")


@pytest.fixture
def platte(wickert):
    return Material.objects.create(materialnr="M-001", bezeichnung="Spanplatte 19 mm", einheit="Stk", lieferant=wickert,
                                   lagerartikel=True, mindestbestand=Decimal("10"), zielbestand=Decimal("30"),
                                   ek_netto=Decimal("25.50"), lieferzeit_tage=5, lagerplatz="Regal A")


def start(material, menge, benutzer=None):
    return Lagerbewegung.objects.create(material=material, datum=HEUTE, art=Lagerbewegung.Art.START, menge=menge)


# ------------------------------------------------------------------ Vorschläge
def test_vorschlag_wie_excel(platte):
    start(platte, Decimal("4"))
    v = dienst.vorschlaege()
    assert len(v) == 1 and v[0]["menge"] == Decimal("26") and v[0]["wert"] == Decimal("663.00")  # Ziel 30 − 4


def test_kein_vorschlag_wenn_genug_bestellt(platte, chef):
    start(platte, Decimal("4"))
    dienst.bestellen(material=platte, menge=Decimal("6"), benutzer=chef)  # 4 + 6 = 10 = Mindest
    assert dienst.vorschlaege() == []


def test_vorschlag_beruecksichtigt_offene_bestellung(platte, chef):
    start(platte, Decimal("2"))
    dienst.bestellen(material=platte, menge=Decimal("5"), benutzer=chef)
    assert dienst.vorschlaege()[0]["menge"] == Decimal("23")  # 30 − 2 − 5


def test_nur_lagerartikel_mit_mindestbestand(wickert):
    Material.objects.create(materialnr="M-9", bezeichnung="Sonderteil", lieferant=wickert, lagerartikel=False,
                            mindestbestand=Decimal("5"))
    Material.objects.create(materialnr="M-8", bezeichnung="Ohne Mindest", lieferant=wickert, lagerartikel=True)
    assert dienst.vorschlaege() == []


def test_alle_vorschlaege_bestellen(platte, chef):
    ohne = Material.objects.create(materialnr="M-2", bezeichnung="Kante", lagerartikel=True, mindestbestand=Decimal("5"))
    erledigt, uebersprungen = dienst.alle_vorschlaege_bestellen(chef)
    assert [b.material for b in erledigt] == [platte] and erledigt[0].art == "Automatisch"
    assert erledigt[0].freigegeben_von == "Automatik"
    assert len(uebersprungen) == 1 and "kein Lieferant" in uebersprungen[0] and ohne.bezeichnung in uebersprungen[0]


# ------------------------------------------------------------------ Bestellen
def test_bestellen(platte, chef):
    b = dienst.bestellen(material=platte, menge=Decimal("20"), benutzer=chef, grund="Projekt X")
    assert (b.bnr, b.lieferant.name, b.einheit, b.status_text) == ("B-0001", "Holz Wickert", "Stk", "unterwegs")
    assert b.erwartet_am == HEUTE + dt.timedelta(days=5)  # Lieferzeit aus dem Material
    assert dienst.bestellen(material=platte, menge=1, benutzer=chef).bnr == "B-0002"
    assert Protokolleintrag.objects.filter(aktion="bestellung_angelegt", gegenstand="B-0001").exists()


def test_ohne_lieferant_keine_bestellung(chef):
    m = Material.objects.create(materialnr="M-3", bezeichnung="Leim")
    with pytest.raises(dienst.LagerFehler, match="kein Lieferant"):
        dienst.bestellen(material=m, menge=1, benutzer=chef)


# ------------------------------------------------------------------ Wareneingang
def test_alles_da_und_einlagern(platte, chef):
    start(platte, Decimal("3"))
    b = dienst.bestellen(material=platte, menge=Decimal("20"), benutzer=chef)
    text = dienst.wareneingang(b, was=dienst.ALLES, benutzer=chef, einlagern=True)
    assert "+20" in text and "eingelagert" in text
    b = Bestellung.objects.get(pk=b.pk)
    assert (b.geliefert, b.eingelagert, b.rest_offen, b.status_text) == (20, 20, 0, "geliefert")
    assert not b.ist_offen and bestand(platte) == Decimal("23")


def test_teillieferung_spaeter_einlagern(platte, chef):
    b = dienst.bestellen(material=platte, menge=Decimal("20"), benutzer=chef)
    dienst.wareneingang(b, was=dienst.TEIL, menge=Decimal("8"), benutzer=chef, einlagern=False)
    b = Bestellung.objects.get(pk=b.pk)
    assert (b.geliefert, b.rest_offen, b.zu_lagern, b.status_text) == (8, 12, 8, "teilweise")
    assert bestand(platte) == 0
    dienst.wareneingang(b, was=dienst.ALLES, benutzer=chef, einlagern=False)
    b = Bestellung.objects.get(pk=b.pk)
    assert b.status_text == "einlagern"
    dienst.einlagern(b, chef)
    b = Bestellung.objects.get(pk=b.pk)
    assert b.status_text == "geliefert" and bestand(platte) == 20
    with pytest.raises(dienst.LagerFehler, match="nichts einzulagern"):
        dienst.einlagern(b, chef)


def test_mehr_geliefert_braucht_bestaetigung(platte, chef):
    b = dienst.bestellen(material=platte, menge=Decimal("10"), benutzer=chef)
    with pytest.raises(dienst.LagerFehler, match="bestätigen"):
        dienst.wareneingang(b, was=dienst.TEIL, menge=Decimal("12"), benutzer=chef)
    dienst.wareneingang(b, was=dienst.TEIL, menge=Decimal("12"), benutzer=chef, mehr_bestaetigt=True)
    assert bestand(platte) == 12


def test_noch_nichts_setzt_liefertermin(platte, chef):
    b = dienst.bestellen(material=platte, menge=Decimal("10"), benutzer=chef, erwartet_am=HEUTE - dt.timedelta(days=3))
    assert b.status_text == "überfällig"
    dienst.wareneingang(b, was=dienst.NICHTS, termin=HEUTE + dt.timedelta(days=2), benutzer=chef)
    b = Bestellung.objects.get(pk=b.pk)
    assert b.erwartet_am == HEUTE + dt.timedelta(days=2) and b.status_text == "unterwegs" and b.geliefert == 0


def test_abschliessen(platte, chef):
    b = dienst.bestellen(material=platte, menge=Decimal("10"), benutzer=chef)
    dienst.wareneingang(b, was=dienst.TEIL, menge=Decimal("4"), benutzer=chef)
    dienst.abschliessen(b, chef, "Lieferant hat nicht mehr")
    b = Bestellung.objects.get(pk=b.pk)
    assert b.status_text == "abgeschlossen" and not b.ist_offen
    assert dienst.offene_menge(platte) == 0  # Rest zählt nicht mehr als offen
    with pytest.raises(dienst.LagerFehler):
        dienst.wareneingang(b, was=dienst.ALLES, benutzer=chef)


# ------------------------------------------------------------------ Lager
def test_korrektur_bucht_differenz(platte, chef):
    start(platte, Decimal("10"))
    bew = dienst.korrektur(platte, neuer_bestand=Decimal("7"), benutzer=chef, grund="gezählt")
    assert bew.menge == Decimal("-3") and bew.art == "Korrektur" and bestand(platte) == 7
    assert dienst.korrektur(platte, neuer_bestand=Decimal("7"), benutzer=chef, grund="nochmal") is None
    with pytest.raises(dienst.LagerFehler, match="Grund"):
        dienst.korrektur(platte, neuer_bestand=Decimal("5"), benutzer=chef, grund=" ")
    assert Protokolleintrag.objects.filter(aktion="lager_korrektur").count() == 1


def test_buchungen_gesperrt(platte, chef):
    bew = start(platte, Decimal("1"))
    bew.menge = 5
    with pytest.raises(Gesperrt):
        bew.save()
    with pytest.raises(Gesperrt):
        bew.delete()
    b = dienst.bestellen(material=platte, menge=Decimal("1"), benutzer=chef)
    dienst.wareneingang(b, was=dienst.ALLES, benutzer=chef)
    with pytest.raises(Gesperrt):
        Wareneingang.objects.first().delete()


# ------------------------------------------------------------------ Abgleich Eingangsrechnung
def test_abgleich_wie_excel(platte, chef):
    b = dienst.bestellen(material=platte, menge=Decimal("10"), benutzer=chef)  # Bestellwert 255,00 €
    assert dienst.abgleich(b.bnr, Decimal("256")).startswith("✓ passt")       # Toleranz max(0,50; 2 % = 5,10)
    assert "Abweichung +20,00 €" in dienst.abgleich(b.bnr, Decimal("275"))
    assert "gibt es nicht" in dienst.abgleich("B-9999", 1)
    er = ed.erfassen(lieferant_name="Holz Wickert", lieferanten_nr="R-1", datum=HEUTE, kategorie="Material / Wareneingang",
                     projekt=None, netto=Decimal("255"), ust_satz=Decimal("19"), ziel_tage=14, skonto_prozent=None,
                     skonto_tage=None, benutzer=chef, bestellung=b.bnr)
    assert er.abgleich.startswith("✓")


# ------------------------------------------------------------------ Oberfläche
def test_uebersicht_und_vorschlag_bestellen(chef_client, platte):
    start(platte, Decimal("4"))
    seite = chef_client.get(reverse("lager:uebersicht")).content.decode()
    assert "Spanplatte 19 mm" in seite and 'value="26"' in seite
    antwort = chef_client.post(reverse("lager:vorschlag"), {"material": platte.pk, "menge": "25,5"}, follow=True)
    assert "Bestellung B-0001 angelegt" in antwort.content.decode()
    assert Bestellung.objects.get().menge == Decimal("25.5")


def test_neue_bestellung_fuer_projekt(chef_client, platte):
    kunde = Kunde.objects.create(kundennr="K-1", name="Weber")
    p = Projekt.objects.create(projektnr="P-1", name="Küche", kunde=kunde)
    antwort = chef_client.post(reverse("lager:neu"), {"material": platte.pk, "menge": "12", "projekt": p.pk}, follow=True)
    assert "Bestellung B-0001 angelegt" in antwort.content.decode()
    assert Bestellung.objects.get().art == "Projekt"


def test_wareneingang_ueber_seite(chef_client, platte, chef):
    b = dienst.bestellen(material=platte, menge=Decimal("20"), benutzer=chef)
    seite = chef_client.get(reverse("lager:bestellung", args=[b.pk])).content.decode()
    assert "Wareneingang buchen" in seite and "Alles da – 20 Stk" in seite
    chef_client.post(reverse("lager:bestellung", args=[b.pk]), {"was": "teil", "menge": "5", "datum": HEUTE.isoformat(),
                                                                "einlagern": "spaeter", "termin": HEUTE.isoformat()})
    seite = chef_client.get(reverse("lager:bestellung", args=[b.pk])).content.decode()
    assert "noch nicht im Lager gebucht" in seite
    chef_client.post(reverse("lager:bestellung", args=[b.pk]), {"aktion": "einlagern"})
    assert bestand(platte) == 5


def test_bestand_und_lagerkarte(chef_client, platte):
    start(platte, Decimal("4"))
    liste = chef_client.get(reverse("lager:bestand"), {"nur": "knapp"}).content.decode()
    assert "Spanplatte" in liste and "unter Mindest" in liste
    antwort = chef_client.post(reverse("lager:lagerkarte", args=[platte.pk]), {"neuer_bestand": "6", "grund": "gezählt"},
                               follow=True)
    assert "Bestand korrigiert" in antwort.content.decode() and bestand(platte) == 6
    karte = chef_client.get(reverse("material:detail", args=[platte.pk])).content.decode()
    assert "Lagerbestand" in karte and "Lagerkarte" in karte


@pytest.mark.parametrize("rolle,erlaubt", [(Rolle.MEISTER, True), (Rolle.ADMIN, True), (Rolle.BUCHHALTUNG, False),
                                           (Rolle.MITARBEITER, False)])
def test_rechte(client, benutzer_mit_rolle, rolle, erlaubt):
    client.force_login(benutzer_mit_rolle(rolle))
    for url in (reverse("lager:uebersicht"), reverse("lager:bestand"), reverse("lager:neu")):
        assert (client.get(url).status_code == 200) == erlaubt


# ------------------------------------------------------------------ Import
def _excel(pfad, lager=(), bestellungen=()):
    mappe = Workbook()
    l = mappe.active
    l.title = "Lager"
    for _ in range(3):
        l.append([])
    for z in lager:
        l.append(z)
    b = mappe.create_sheet("Bestellungen")
    for _ in range(3):
        b.append([])
    for z in bestellungen:
        zeile = [None] * 45
        for spalte, wert in z.items():
            zeile[spalte] = wert
        b.append(zeile)
    mappe.save(pfad)
    return pfad


def test_import_lager_und_bestellungen(tmp_path, platte):
    # Spalten (0-basiert): A0 B1 C2 D3 E4 F5 G6 H7 J9 M12 AO40 AS44
    pfad = _excel(tmp_path / "pw.xlsx",
                  lager=[["M-001", "Spanplatte", "Stk", 14, 0, 14, 10, "ok", "Halle 2"], ["", None], ["M-999", "x", "", 3]],
                  bestellungen=[
                      {0: "B-0007", 2: "M-001", 3: "Holz Wickert", 4: dt.datetime(2026, 10, 1), 5: 20, 6: "Stk",
                       7: dt.datetime(2026, 10, 8), 9: dt.datetime(2026, 10, 7), 12: 20, 40: 20, 44: "abgeschlossen"},
                      {0: "B-0008", 2: "M-001", 3: "Holz Wickert", 4: dt.datetime(2026, 11, 1), 5: 10, 12: 4, 40: 0},
                      {17: "Vorschlagszeile ohne ID"}])
    bericht = ausfuehren(pfad, probelauf=False)
    lager = next(x for x in bericht["blaetter"] if x["blatt"] == "Lager")
    assert lager["neu"] == 1 and len(lager["fehler"]) == 1 and "M-999" in lager["fehler"][0]
    platte.refresh_from_db()
    assert bestand(platte) == 14 and platte.lagerplatz == "Regal A"  # Lagerplatz nicht überschrieben
    b7, b8 = Bestellung.objects.get(bnr="B-0007"), Bestellung.objects.get(bnr="B-0008")
    assert b7.status_text == "abgeschlossen" and b7.bestellt_am == dt.date(2026, 10, 1)
    assert (b8.geliefert, b8.eingelagert, b8.zu_lagern, b8.rest_offen) == (4, 0, 4, 6)
    assert dienst.naechste_bnr() == "B-0009"
    # zweiter Import ändert nichts (keine doppelten Startbestände/Bestellungen)
    ausfuehren(pfad, probelauf=False)
    assert bestand(platte) == 14 and Bestellung.objects.count() == 2


def test_kennzahl_einlagern_zaehlt_teillieferungen(chef_client, platte, chef):
    b = dienst.bestellen(material=platte, menge=Decimal("20"), benutzer=chef)
    dienst.wareneingang(b, was=dienst.TEIL, menge=Decimal("5"), benutzer=chef, einlagern=False)
    seite = chef_client.get(reverse("lager:uebersicht"))
    assert seite.context["anzahl_einlagern"] == 1
