from datetime import date, time
from decimal import Decimal

import pytest
from django.urls import reverse
from openpyxl import Workbook

from importe.dienst import ausfuehren
from konten.models import Rolle
from kunden.models import Kunde
from mitarbeiter.models import Mitarbeiter
from planung import dienst, kapazitaet
from planung.models import Abwesenheit, Termin
from produktion import dienst as produktion
from produktion.models import Vorlage
from projekte.models import Projekt
from zeiten.models import Arbeitsvertrag

pytestmark = pytest.mark.django_db
D = Decimal
MO = date(2026, 11, 16)  # Montag
FR = date(2026, 11, 20)


@pytest.fixture
def ma():
    m = Mitarbeiter.objects.create(kuerzel="D.Kaub", name="Dieter Kaub")
    Arbeitsvertrag.objects.create(vertragsid="AV-0001", mitarbeiter=m, eintritt=date(2026, 1, 1), soll_fr=D("6"))
    return m


def termin(ma, tag, von, bis, chef, aufgabe="Aufmaß"):
    return dienst.termin_anlegen(datum=tag, aufgabe=aufgabe, mitarbeiter=ma, beginn=time(von), ende=time(bis), benutzer=chef)[0]


def test_tag_status_und_konflikt(ma, chef):
    termin(ma, MO, 7, 12, chef)
    k = kapazitaet.tag(ma, MO)
    assert (k["soll"], k["gebucht"], k["rest"], k["status"], k["planung"]) == (8, 5, 3, "🟢 verfügbar", "einplanbar")
    termin(ma, MO, 11, 13, chef, "Kunde")
    k = kapazitaet.tag(ma, MO)
    assert k["konflikte"] == 1 and k["gebucht"] == 7 and k["status"] == "🟡 knapp"
    termin(ma, MO, 14, 16, chef, "Lieferung")
    assert kapazitaet.tag(ma, MO)["status"] == "🔴 überplant"
    assert "überplant (9 h gebucht bei 8 h Soll)" in kapazitaet.warnung_fuer(ma, MO)
    assert kapazitaet.tag(ma, FR)["soll"] == 6 and kapazitaet.tag(ma, date(2026, 11, 21))["status"] == "⚪ keine Sollzeit"


def test_abwesenheit_ganz_und_stunden(ma, chef):
    dienst.abwesenheit_erfassen(mitarbeiter=ma, von=MO, bis=MO, art="Urlaub", status="Freigegeben", benutzer=chef)
    assert kapazitaet.tag(ma, MO)["status"] == "🔴 abwesend" and kapazitaet.tag(ma, MO)["rest"] == 0
    dienst.abwesenheit_erfassen(mitarbeiter=ma, von=date(2026, 11, 17), bis=date(2026, 11, 17), art="Berufsschule",
                                status="Freigegeben", benutzer=chef, stunden=D("4"))
    k = kapazitaet.tag(ma, date(2026, 11, 17))
    assert (k["abw_h"], k["rest"], k["status"]) == (4, 4, "🟢 verfügbar")
    beantragt = dienst.abwesenheit_erfassen(mitarbeiter=ma, von=FR, bis=FR, art="Urlaub", status="Beantragt", benutzer=chef)
    assert kapazitaet.tag(ma, FR)["status"] == "🟢 verfügbar" and beantragt.status == "Beantragt"  # nur Freigegeben wirkt


def test_arbeitsgaenge_zaehlen_mit(ma, chef):
    p = Projekt.objects.create(projektnr="P-1", name="Küche", kunde=Kunde.objects.create(kundennr="K-1", name="W"))
    ag = produktion.einzeln(p, Vorlage.objects.get(code="PL-010"), plan_std=D("12"), mitarbeiter=ma, benutzer=chef)
    ag.plan_start, ag.plan_ende = MO, date(2026, 11, 18)
    ag.save()
    k = kapazitaet.tag(ma, date(2026, 11, 17))
    assert k["werkstatt_h"] == 4 and k["werkstatt"][0]["text"] == "P-1: Grobzuschnitt" and k["rest"] == 4
    produktion.starten(ag, chef)
    produktion.rueckmelden(ag, stunden=1, fertig=True, benutzer=chef)
    assert kapazitaet.tag(ma, date(2026, 11, 17))["werkstatt_h"] == 0  # fertig zählt nicht mehr


def test_uebersicht_und_woche(ma, chef):
    Mitarbeiter.objects.create(kuerzel="K.Otto", name="Klaus Otto")
    termin(ma, MO, 7, 15, chef)
    t = kapazitaet.tag_alle(MO)
    assert t["aktiv"] == 2 and t["soll"] == 16 and t["gebucht"] == 8 and t["auslastung"] == 50
    w = kapazitaet.woche(MO)
    assert [d["rest"] for d in w[0]["tage"]] == [0, 8, 8, 8, 6]


def test_seite_und_warnungen(ma, chef, chef_client, client, benutzer_mit_rolle):
    termin(ma, MO, 7, 15, chef)
    seite = chef_client.get(reverse("planung:kapazitaet") + "?datum=2026-11-16").content.decode()
    assert "Kapazität · Montag, 16.11.2026" in seite and "Dieter Kaub" in seite and "🟡 knapp" in seite
    antwort = chef_client.post(reverse("planung:kalender"), {"mitarbeiter": ma.pk, "datum": "2026-11-16", "art": "Sonstiges",
                                                            "aufgabe": "Extra", "beginn": "14:00", "ende": "17:00"}, follow=True)
    assert "überschneidende Termine" in antwort.content.decode() or "überplant" in antwort.content.decode()
    client.force_login(benutzer_mit_rolle(Rolle.MITARBEITER))
    assert client.get(reverse("planung:kapazitaet")).status_code == 403


def test_montage_warnt_bei_ueberplanung(ma, chef):
    team = dienst.team_anlegen(name="M1", art="Montage", benutzer=chef)
    dienst.mitglied_umschalten(team, ma, chef)
    termin(ma, MO, 7, 12, chef)
    p = Projekt.objects.create(projektnr="P-2", name="x", kunde=Kunde.objects.create(kundennr="K-2", name="W"))
    warn = dienst.montage_pruefen(p, datum=MO, beginn=time(10), ende=time(16), team=team, fahrzeug="")
    assert any("überplant" in w for w in warn)


def test_import_stunden(tmp_path, ma):
    from openpyxl.utils import column_index_from_string as c
    mappe = Workbook()
    ws = mappe.active
    ws.title = "Zeitdaten"
    for spalte, wert in {"A": "ZD-0009", "B": "D.Kaub", "C": MO, "D": MO, "E": "Berufsschule", "F": 4, "G": "Std",
                         "H": "Freigegeben", "I": "Reduziert"}.items():
        ws.cell(row=4, column=c(spalte), value=wert)
    pfad = tmp_path / "pw.xlsx"
    mappe.save(pfad)
    ausfuehren(pfad, probelauf=False)
    assert Abwesenheit.objects.get().stunden == 4 and kapazitaet.tag(ma, MO)["rest"] == 4
