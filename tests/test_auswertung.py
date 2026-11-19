import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse

from auswertung import dienst
from kalkulation.models import Auftrag, Kalkulation
from konten.models import Rolle
from mitarbeiter.models import Mitarbeiter
from produktion import dienst as produktion
from produktion.models import Vorlage
from rechnungen import finanzen
from tests.test_finanzen import OKT, beleg, firma, projekt, rechnung  # noqa: F401
from zeiten import dienst as zeiten
from zeiten.models import Arbeitsvertrag

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def ma():
    m = Mitarbeiter.objects.create(kuerzel="D.Kaub", name="Dieter Kaub")
    Arbeitsvertrag.objects.create(vertragsid="AV-0001", mitarbeiter=m, eintritt=dt.date(2026, 1, 1), stundenlohn=D("25"),
                                  brutto_monat=D("3000"))
    return m


@pytest.fixture
def daten(firma, projekt, chef, ma):  # noqa: F811
    """Oktober 2026: Rechnung 1.000 netto, Material-Beleg 500, Fremdleistung 100, 8 h Lohn = 200."""
    rechnung(projekt, chef)
    beleg(chef, projekt)
    beleg(chef, projekt, lieferanten_nr="R-2", kategorie="Fremdleistung", netto=D("100"))
    zeiten.buchen(mitarbeiter=ma, datum=dt.date(2026, 10, 15), stunden=8, projekt=projekt, benutzer=chef)
    zeiten.buchen(mitarbeiter=ma, datum=dt.date(2026, 10, 16), stunden=2, taetigkeit="Büro", benutzer=chef)
    return projekt


def test_jahr_und_monate(daten):
    j = dienst.jahr(2026, heute=dt.date(2026, 11, 19))
    okt = j["monate"][9]
    assert (okt["umsatz"], okt["eingang"], okt["lohn"], okt["ergebnis"]) == (D("1000"), D("600"), D("250"), D("150"))
    assert okt["h_umsatz"] == 100 and okt["h_kosten"] == 85
    assert j["umsatz"] == 1000 and j["ergebnis"] == 150 and j["marge"] == D("15.0")
    assert j["stunden"] == 10 and j["produktiv"] == D("80.0")
    assert j["monate"][11]["zukunft"] and j["wachstum"] is None


def test_nachkalkulation(daten, chef):
    p = daten
    Kalkulation.objects.create(projekt=p, material_manuell=D("400"), beschlaege=D("50"), lohn_std=D("10"),
                               lohn_satz=D("50"), fremd=D("80"), montage=D("70"))
    Auftrag.objects.create(aunr="AU-0001", projekt=p, angebot_netto=D("1500"))
    v = dienst.projekt_vergleich(p)
    zeilen = {z["name"]: z for z in v["zeilen"]}
    assert zeilen["Material + Beschläge"]["plan"] == 450 and zeilen["Material + Beschläge"]["ist"] == 500
    assert zeilen["Lohn"]["plan"] == 500 and zeilen["Lohn"]["ist"] == 200
    assert zeilen["Fremdleistungen"]["diff"] == 20 and zeilen["Fremdleistungen"]["prozent"] == D("25.0")
    assert zeilen["Gesamtkosten"]["plan"] == 1100 and v["ist"]["gesamt"] == 800
    assert v["verbraucht"] == D("72.7") and v["db"] == 200 and v["marge_plan"] == D("26.7")
    assert (v["soll_std"], v["ist_std"], v["std_prozent"]) == (10, 8, D("-20.0"))
    liste = dienst.nachkalkulation()
    assert len(liste) == 1 and liste[0]["ampel"] == "gruen"
    Kalkulation.objects.filter(projekt=p).update(material_manuell=D("50"))  # 750 kalkuliert, 800 Ist → 107 %
    assert dienst.nachkalkulation()[0]["ampel"] == "rot"


def test_ist_stunden_mit_arbeitsgang(daten, chef, ma):
    ag = produktion.einzeln(daten, Vorlage.objects.get(code="PL-010"), mitarbeiter=ma, benutzer=chef)
    zeiten.buchen(mitarbeiter=ma, datum=dt.date(2026, 10, 20), stunden=3, arbeitsgang=ag, benutzer=chef)
    assert dienst.projekt_vergleich(daten)["ist_std"] == 11  # 8 frei + 3 am Arbeitsgang (nicht doppelt)


def test_stunden_werkstatt_material(daten, ma, chef):
    s = dienst.stunden(2026, 10)
    assert s[0]["ist"] == 10 and s[0]["produktiv"] == D("80.0") and s[0]["kosten"] == 250
    assert dict(s[0]["je"]) == {"Fertigung / Werkstatt": 8, "Büro": 2}
    w = dienst.werkstatt(heute=dt.date(2026, 11, 19))
    assert w["qm_quote"] is None and w["ueberfaellig_anzahl"] == 0
    a = produktion.einzeln(daten, Vorlage.objects.get(code="MO-010"), benutzer=chef)
    a.plan_start = a.plan_ende = dt.date(2026, 11, 2)
    a.save()
    produktion.starten(a, chef)
    produktion.rueckmelden(a, stunden=1, fertig=True, benutzer=chef)
    produktion.endkontrolle(daten, bestanden=False, abweichung="Kratzer", benutzer=chef)
    w = dienst.werkstatt(heute=dt.date(2026, 11, 19))
    assert w["qm_quote"] == D("0.0") and dict(w["phasen"])["Fertigung"] == 1
    assert dienst.material()["lagerwert"] == 0


def test_loehne_in_liquiditaet(ma):
    assert finanzen.loehne_zum(dt.date(2026, 11, 30)) == 3000
    assert finanzen.loehne_zum(dt.date(2025, 12, 31)) == 0  # vor Eintritt
    u = finanzen.uebersicht(heute=dt.date(2026, 11, 19))
    woche = next(w for w in u["wochen"] if w["start"] == dt.date(2026, 11, 30))
    assert woche["loehne"] == 3000 and woche["aus"] == 3000
    assert sum(w["loehne"] for w in u["wochen"]) == 3000  # nur ein Monatsende im Zeitraum (31.12. liegt danach)


def test_db_je_projekt_mit_lohn(daten):
    u = finanzen.uebersicht(heute=dt.date(2026, 11, 19))
    p = next(x for x in u["projekte"] if x["projekt"] == daten)
    assert p["erloes"] == 1000 and p["kosten"] == 800 and p["lohn"] == 200 and p["db"] == 200


def test_seiten_und_rechte(daten, chef_client, client, benutzer_mit_rolle):
    seite = chef_client.get(reverse("auswertung:uebersicht") + "?jahr=2026&monat=2026-10").content.decode()
    assert "Umsatz 2026 netto" in seite and "P-001" in seite and "Dieter Kaub" in seite
    assert "Fertigung / Werkstatt 8 h" in seite
    detail = chef_client.get(reverse("auswertung:projekt", args=[daten.pk])).content.decode()
    assert "Kalkulation gegen Ist" in detail and "Gesamtkosten" in detail
    assert chef_client.get(reverse("auswertung:uebersicht") + "?jahr=abc&monat=x").status_code == 200
    for rolle in (Rolle.MEISTER, Rolle.BUCHHALTUNG, Rolle.MITARBEITER):
        client.force_login(benutzer_mit_rolle(rolle, f"x{rolle}"))
        assert client.get(reverse("auswertung:uebersicht")).status_code == 403
    client.force_login(benutzer_mit_rolle(Rolle.ADMIN, "admin1"))
    assert client.get(reverse("auswertung:uebersicht")).status_code == 200
