from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from inventur import dienst
from inventur.models import Inventur, Position
from kern.models import Protokolleintrag
from konten.models import Rolle
from lager.models import Lagerbewegung, bestand
from material.models import Material
from mitarbeiter.models import Mitarbeiter

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def lager(chef):
    def m(nr, platz, menge, ek):
        x = Material.objects.create(materialnr=nr, bezeichnung=nr, einheit="Stk", lagerartikel=True, lagerplatz=platz,
                                    ek_netto=D(ek))
        Lagerbewegung.objects.create(material=x, datum=date(2026, 1, 1), art="Startbestand", menge=D(menge), erfasst_von=chef)
        return x
    return [m("PL-1", "Regal A", 10, "40"), m("BL-1", "Regal B", 200, "0.10"), m("KA-1", "Regal A", 5, "2")]


@pytest.fixture
def zweiter(benutzer_mit_rolle):
    u = benutzer_mit_rolle(Rolle.MITARBEITER, "kurt")
    Mitarbeiter.objects.create(kuerzel="K.Otto", name="Klaus Otto", benutzer=u)
    return u


def neue(chef, **werte):
    return dienst.anlegen(benutzer=chef, stichtag=date(2026, 12, 31), art="Vollinventur", lagerbereich="", verantwortlich="",
                          blind=True, toleranz_prozent=D("2"), toleranz_wert=D("50"), hinweis="", **werte)


def test_start_snapshot_und_bereich(lager, chef):
    inv = neue(chef)
    assert inv.invid == "INV-2026-001" and inv.status == "Vorbereitung"
    assert dienst.starten(inv, chef) == 3
    assert {p.material.materialnr: p.soll for p in inv.positionen.all()} == {"PL-1": 10, "BL-1": 200, "KA-1": 5}
    with pytest.raises(dienst.InventurFehler, match="läuft schon"):
        dienst.starten(inv, chef)
    teil = dienst.anlegen(benutzer=chef, stichtag=date(2027, 1, 5), art="Teilinventur", lagerbereich="Regal A",
                          verantwortlich="", blind=False, toleranz_prozent=D("2"), toleranz_wert=D("50"), hinweis="")
    assert teil.invid == "INV-2027-001"
    with pytest.raises(dienst.InventurFehler, match="andere Inventur"):
        dienst.starten(teil, chef)


def test_ablauf_mit_nachzaehlung_vier_augen_und_buchung(lager, chef, zweiter):
    inv = neue(chef)
    dienst.starten(inv, chef)
    pl, bl, ka = (inv.positionen.get(material__materialnr=n) for n in ("PL-1", "BL-1", "KA-1"))
    dienst.zaehlen(pl, "9", chef)            # −10 % → kritisch
    dienst.zaehlen(bl, "199", chef)           # −0,5 %, −0,10 € → nur prüfen
    dienst.zaehlen(ka, "5", chef)             # OK
    pl, bl, ka = (Position.objects.get(pk=p.pk) for p in (pl, bl, ka))
    assert (pl.status, bl.status, ka.status) == ("🔴 Nachzählung", "🟡 prüfen", "🟢 OK")
    assert pl.nachzaehlung_offen and not pl.freigabe_offen and bl.freigabe_offen and not ka.freigabe_offen
    with pytest.raises(dienst.InventurFehler, match="Vier-Augen"):
        dienst.nachzaehlen(pl, "9", chef)
    with pytest.raises(dienst.InventurFehler, match="kritische"):
        dienst.nachzaehlen(bl, "199", zweiter)
    dienst.nachzaehlen(pl, "8,5", zweiter)
    pl = Position.objects.get(pk=pl.pk)
    assert pl.nachzaehler == "Klaus Otto" and pl.freigabe_ist == D("8.5") and pl.status == "🟡 Differenz bestätigt"
    assert not dienst.pruefung(inv)["bereit"]
    with pytest.raises(dienst.InventurFehler, match="abschlussbereit"):
        dienst.abschliessen(inv, chef)
    with pytest.raises(dienst.InventurFehler, match="Ursache"):
        dienst.entscheiden(pl, freigeben=True, ursache="", text="", benutzer=chef)
    dienst.entscheiden(pl, freigeben=True, ursache="Bruch / Verschnitt", text="Ecke gebrochen", benutzer=chef)
    dienst.entscheiden(bl, freigeben=False, ursache="Zählfehler", text="", benutzer=chef)
    d = dienst.pruefung(inv)
    assert d["bereit"] and d["buchungen"] == 1 and d["wert"] == D("-60.00")
    # Während der Inventur wurde 1 Platte entnommen – die Korrektur bucht nur die Differenz zum Snapshot
    Lagerbewegung.objects.create(material=pl.material, datum=date(2026, 12, 30), art="Entnahme", menge=D("-1"), erfasst_von=chef)
    assert dienst.abschliessen(inv, chef) == 1
    inv.refresh_from_db()
    pl = Position.objects.get(pk=pl.pk)
    assert inv.status == "Abgeschlossen" and pl.buchung.menge == D("-1.5") and "Inventur INV-2026-001" in pl.buchung.notiz
    assert bestand(pl.material) == D("7.5") and bestand(bl.material) == 200  # abgelehnt → keine Buchung
    with pytest.raises(dienst.InventurFehler):
        dienst.zaehlen(ka, "4", chef)
    assert Protokolleintrag.objects.filter(aktion="inventur_abgeschlossen").exists()
    assert dienst.bericht_pdf(inv).startswith(b"%PDF")


def test_zaehlen_regeln(lager, chef):
    inv = neue(chef)
    with pytest.raises(dienst.InventurFehler, match="gestartet"):
        dienst.zaehlen(Position(inventur=inv, material=lager[0], soll=1), "1", chef)
    dienst.starten(inv, chef)
    p = inv.positionen.first()
    for falsch in ("-1", "abc"):
        with pytest.raises(dienst.InventurFehler):
            dienst.zaehlen(p, falsch, chef)
    dienst.zaehlen(p, "3", chef)
    dienst.zaehlen(p, "4", chef)  # Korrektur vor der Nachzählung erlaubt, protokolliert
    assert Protokolleintrag.objects.filter(aktion="inventur_gezaehlt", details__contains="vorher 3").exists()


def test_null_soll_wird_kritisch(lager, chef):
    inv = neue(chef)
    dienst.starten(inv, chef)
    p = inv.positionen.get(material__materialnr="KA-1")
    p.soll = 0
    p.save()
    dienst.zaehlen(p, "1", chef)
    assert Position.objects.get(pk=p.pk).kritisch


def test_seiten_und_rechte(lager, chef, chef_client, client, benutzer_mit_rolle, zweiter):
    chef_client.post(reverse("inventur:liste"), {"art": "Vollinventur", "stichtag": "2026-12-31", "lagerbereich": "",
                                                 "verantwortlich": "Chef", "blind": "on", "toleranz_prozent": "2",
                                                 "toleranz_wert": "50", "hinweis": ""})
    inv = Inventur.objects.get()
    url = reverse("inventur:detail", args=[inv.pk])
    assert "noch in Vorbereitung" in chef_client.get(url).content.decode()
    chef_client.post(url, {"aktion": "starten"})
    seite = chef_client.get(url + "?modus=zaehlen").content.decode()
    assert "PL-1" in seite and "Soll 10" not in seite  # Blindzählung
    pl = inv.positionen.get(material__materialnr="PL-1")
    client.force_login(zweiter)
    client.post(url + "?modus=zaehlen", {"aktion": "zaehlen", "position": pl.pk, "menge": "10"})
    assert Position.objects.get(pk=pl.pk).ist == 10
    client.post(url + "?modus=frei", {"aktion": "frei", "position": pl.pk, "ursache": "Schwund"})
    assert Position.objects.get(pk=pl.pk).freigabe == ""  # Mitarbeiter darf nicht freigeben
    client.force_login(benutzer_mit_rolle(Rolle.BUCHHALTUNG))
    client.post(url, {"aktion": "zaehlen", "position": pl.pk, "menge": "3"})
    assert Position.objects.get(pk=pl.pk).ist == 10  # Buchhaltung nur lesen
    assert client.get(reverse("inventur:bericht", args=[inv.pk])).content.startswith(b"%PDF")
    assert "alle" in chef_client.get(url + "?modus=alle").content.decode().lower()
