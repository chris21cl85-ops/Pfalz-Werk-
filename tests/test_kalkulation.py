from decimal import Decimal

import pytest
from django.urls import reverse
from openpyxl import Workbook

from importe.dienst import ausfuehren
from kalkulation import dienst
from kalkulation.models import Auftrag, Kalkulation, Stuecklistenposition
from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from lager import dienst as lager
from lager.models import Lagerbewegung, bestand
from lieferanten.models import Lieferant
from material.models import Material
from projekte.models import Projekt
from rechnungen.dienst import letzter_auftragswert

pytestmark = pytest.mark.django_db
S = Stuecklistenposition.Status


@pytest.fixture
def projekt():
    kunde = Kunde.objects.create(kundennr="K-1", name="Weber")
    return Projekt.objects.create(projektnr="P-001", name="Regalwand", kunde=kunde, status="Auftrag")


@pytest.fixture
def platte():
    return Material.objects.create(materialnr="M-1", bezeichnung="Multiplex 18", einheit="Stk",
                                   ek_netto=Decimal("48.90"), lieferant=Lieferant.objects.create(name="Wickert"))


# ------------------------------------------------------------------ Kalkulation wie Makro
def test_kosten_und_vk_wie_excel(projekt, platte, chef):
    dienst.position_anlegen(projekt, benutzer=chef, material=platte, menge=Decimal("4"))  # 195,60
    k = Kalkulation.objects.create(projekt=projekt, beschlaege=Decimal("80"), lohn_std=Decimal("12.5"),
                                   lohn_satz=Decimal("58"), maschinen=Decimal("40"), montage=Decimal("120"),
                                   fahrt=Decimal("30"), fremd=Decimal("0"), zuschlag=Decimal("15"), risiko=Decimal("5"))
    assert k.material == Decimal("195.60") and k.lohnkosten == Decimal("725.00")
    assert k.kosten == Decimal("1190.60")
    assert k.vk == Decimal("1428.72")  # 1190,60 × 1,20


def test_geplante_positionen_zaehlen_nicht(projekt, platte, chef):
    dienst.position_anlegen(projekt, benutzer=chef, material=platte, menge=Decimal("2"), status=S.GEPLANT)
    k = Kalkulation.objects.create(projekt=projekt, material_manuell=Decimal("300"))
    assert k.material == Decimal("300")  # nur Ideen in der Stückliste → Handwert zählt
    dienst.position_anlegen(projekt, benutzer=chef, material=platte, menge=Decimal("1"))
    assert Kalkulation.objects.get(pk=k.pk).material == Decimal("48.90")


def test_freie_position_ohne_material(projekt, chef):
    p = dienst.position_anlegen(projekt, benutzer=chef, bezeichnung="Glasböden nach Maß", menge=3, ek=Decimal("35"))
    assert (p.pos, p.gesamt, p.material) == (1, Decimal("105.00"), None)
    with pytest.raises(dienst.KalkFehler):
        dienst.position_anlegen(projekt, benutzer=chef, menge=1)


# ------------------------------------------------------------------ Lager-Verbindung
def test_entnahme_bucht_lager(projekt, platte, chef):
    Lagerbewegung.objects.create(material=platte, datum="2026-11-01", art="Startbestand", menge=10)
    p = dienst.position_anlegen(projekt, benutzer=chef, material=platte, menge=Decimal("4"))
    dienst.status_setzen(p, S.ENTNOMMEN, chef)
    assert bestand(platte) == 6
    assert Lagerbewegung.objects.filter(art="Entnahme", projekt=projekt).exists()
    with pytest.raises(dienst.KalkFehler, match="zurückbuchen"):
        dienst.position_entfernen(Stuecklistenposition.objects.get(pk=p.pk), chef)
    dienst.status_setzen(p, S.BENOETIGT, chef)  # zurück → wieder eingebucht
    assert bestand(platte) == 10
    k = Kalkulation.objects.create(projekt=projekt)
    dienst.status_setzen(p, S.ENTNOMMEN, chef)
    assert k.ist_kosten == Decimal("195.60")


def test_projektbedarf_in_bestellvorschlaegen(projekt, platte, chef):
    dienst.position_anlegen(projekt, benutzer=chef, material=platte, menge=Decimal("5"))
    v = lager.vorschlaege()
    assert len(v) == 1 and v[0]["menge"] == 5 and v[0]["grund"] == "Projektbedarf"
    Lagerbewegung.objects.create(material=platte, datum="2026-11-01", art="Startbestand", menge=3)
    assert lager.vorschlaege()[0]["menge"] == 2
    lager.bestellen(material=platte, menge=2, benutzer=chef)
    assert lager.vorschlaege() == []


def test_lagerartikel_mindest_plus_bedarf(projekt, platte, chef):
    platte.lagerartikel, platte.mindestbestand, platte.zielbestand = True, Decimal("10"), Decimal("20")
    platte.save()
    Lagerbewegung.objects.create(material=platte, datum="2026-11-01", art="Startbestand", menge=15)
    assert lager.vorschlaege() == []  # 15 ≥ Mindest 10
    dienst.position_anlegen(projekt, benutzer=chef, material=platte, menge=Decimal("8"))
    v = lager.vorschlaege()[0]
    assert v["menge"] == 13 and "Projektbedarf" in v["grund"]  # Ziel 20 + Bedarf 8 − Bestand 15


def test_abgeschlossene_projekte_ohne_bedarf(projekt, platte, chef):
    dienst.position_anlegen(projekt, benutzer=chef, material=platte, menge=Decimal("5"))
    projekt.status = "Abgeschlossen"
    projekt.save()
    assert lager.vorschlaege() == []


# ------------------------------------------------------------------ Auftrag + Freigaben
def test_auftrag_und_freigaben(projekt, benutzer_mit_rolle, chef):
    a = dienst.auftrag_speichern(projekt, benutzer=chef, angebot_netto=Decimal("1500"), status="Angebot", leistung="Regalwand")
    assert a.aunr == "AU-0001" and letzter_auftragswert(projekt) == Decimal("1500")
    meister = benutzer_mit_rolle(Rolle.MEISTER)
    buchhaltung = benutzer_mit_rolle(Rolle.BUCHHALTUNG)
    with pytest.raises(dienst.KalkFehler, match="Chef"):
        dienst.freigabe_setzen(a, wer="chef", wert="Freigegeben", benutzer=meister)
    dienst.freigabe_setzen(a, wer="kunde", wert="Freigegeben", benutzer=buchhaltung)  # Kunde darf jeder eintragen
    dienst.freigabe_setzen(a, wer="chef", wert="Freigegeben", benutzer=chef)
    assert not Auftrag.objects.get(pk=a.pk).intern_freigegeben
    dienst.freigabe_setzen(a, wer="meister", wert="Freigegeben", benutzer=meister)
    assert Auftrag.objects.get(pk=a.pk).intern_freigegeben
    assert Protokolleintrag.objects.filter(aktion="auftrag_freigabe").count() == 3


def test_admin_darf_alle_freigaben(projekt, benutzer_mit_rolle, chef):
    a = dienst.auftrag_speichern(projekt, benutzer=chef, angebot_netto=1, status="Angebot")
    admin = benutzer_mit_rolle(Rolle.ADMIN)
    dienst.freigabe_setzen(a, wer="meister", wert="Rückfrage", benutzer=admin)
    assert Auftrag.objects.get(pk=a.pk).freigabe_meister == "Rückfrage"


# ------------------------------------------------------------------ Oberfläche
def test_projektseite_komplett(chef_client, projekt, platte):
    url = reverse("kalkulation:projekt", args=[projekt.pk])
    chef_client.post(url, {"aktion": "position", "material": platte.pk, "menge": "2", "status": "Benötigt"})
    chef_client.post(url, {"aktion": "kalkulation", "art": "Vorkalkulation", "beschlaege": "20,00", "lohn_std": "3",
                           "lohn_satz": "60,00", "maschinen": "0", "montage": "0", "fahrt": "0", "fremd": "0",
                           "zuschlag": "15", "risiko": "5"})
    k = Kalkulation.objects.get()
    assert k.kosten == Decimal("297.80") and k.vk == Decimal("357.36")
    seite = chef_client.get(url).content.decode()
    assert "357,36 €" in seite and "Auftrag anlegen" in seite
    chef_client.post(url, {"aktion": "auftrag", "angebot_netto": "400,00", "status": "Beauftragt", "termin": "KW 50", "leistung": "x"})
    assert Auftrag.objects.get().angebot_netto == Decimal("400")
    seite = chef_client.get(url).content.decode()
    assert "Marge 25,6 %" in seite or "Marge 25.6 %" in seite
    liste = chef_client.get(reverse("kalkulation:liste")).content.decode()
    assert "P-001" in liste and "AU-0001" in liste


def test_rechnung_schlaegt_angebot_vor(chef_client, projekt, chef):
    dienst.auftrag_speichern(projekt, benutzer=chef, angebot_netto=Decimal("12345"), status="Beauftragt")
    seite = chef_client.get(reverse("rechnungen:neu"), {"projekt": projekt.pk}).content.decode()
    assert "12345,00" in seite or "12.345,00" in seite


@pytest.mark.parametrize("rolle,erlaubt", [(Rolle.MEISTER, True), (Rolle.BUCHHALTUNG, True), (Rolle.MITARBEITER, False)])
def test_rechte(client, benutzer_mit_rolle, projekt, rolle, erlaubt):
    client.force_login(benutzer_mit_rolle(rolle))
    assert (client.get(reverse("kalkulation:liste")).status_code == 200) == erlaubt
    assert (client.get(reverse("kalkulation:projekt", args=[projekt.pk])).status_code == 200) == erlaubt


# ------------------------------------------------------------------ Import
def _blatt(mappe, name, zeilen, breite=30):
    ws = mappe.create_sheet(name)
    for _ in range(3):
        ws.append([])
    for z in zeilen:
        reihe = [None] * breite
        for spalte, wert in z.items():
            reihe[spalte] = wert
        ws.append(reihe)


def test_import(tmp_path, projekt, platte):
    mappe = Workbook()
    mappe.remove(mappe.active)
    # Stueckliste: A0 B1 C2 D3 E4 F5 G6 I8
    _blatt(mappe, "Stueckliste", [{0: 1, 1: "P-001", 2: "M-1", 3: "Multiplex 18", 4: 3, 5: "Stk", 6: 50, 8: "Entnommen"},
                                  {0: 2, 1: "P-001", 3: "Sonderbeschlag", 4: 1, 6: 12.5},
                                  {0: 3, 1: "P-999", 3: "x", 4: 1}, {1: "P-001"}])
    # Kalkulation: A0 B1 C2 D3 E4 G6 H7 I8 J9 L11 M12 U20
    _blatt(mappe, "Kalkulation", [{0: "P-001", 1: 500, 2: 80, 3: 10, 4: 55, 6: 20, 7: 100, 8: 30, 9: 0, 11: 0.15, 12: 0.05,
                                   20: "Vorkalkulation"}])
    # Auftraege: A0 B1 D3 G6 H7 I8 J9 K10 L11
    _blatt(mappe, "Auftraege", [{0: "AU-0007", 1: "P-001", 3: "Regalwand", 6: 2500, 7: "Beauftragt", 8: "Freigegeben",
                                 9: "KW 3", 10: "Erteilt", 11: "Offen"}])
    pfad = tmp_path / "pw.xlsx"
    mappe.save(pfad)
    bericht = ausfuehren(pfad, probelauf=False)
    sl = next(b for b in bericht["blaetter"] if b["blatt"] == "Stueckliste")
    assert sl["neu"] == 2 and len(sl["fehler"]) == 1
    pos = list(projekt.stueckliste.order_by("pos"))
    assert pos[0].status == "Entnommen" and pos[0].gesamt == Decimal("150.00") and pos[1].material is None
    assert bestand(platte) == 0  # Import bucht nicht doppelt ab
    k = Kalkulation.objects.get()
    assert (k.zuschlag, k.risiko, k.lohn_satz) == (Decimal("15.00"), Decimal("5.00"), Decimal("55"))
    a = Auftrag.objects.get()
    assert (a.aunr, a.status, a.freigabe_kunde, a.freigabe_chef, a.freigabe_meister) == (
        "AU-0007", "Beauftragt", "Freigegeben", "Freigegeben", "Offen")
    assert dienst.naechste_aunr() == "AU-0008"
    ausfuehren(pfad, probelauf=False)  # zweimal ändert nichts
    assert projekt.stueckliste.count() == 2 and Kalkulation.objects.count() == 1
