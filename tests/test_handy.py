from datetime import date, time
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from handy import netz
from handy.models import Meldung
from inventur import dienst as inventur
from kalkulation.models import Auftrag
from konten.models import Rolle
from kunden.models import Kunde
from lager import dienst as lager
from lager.models import Lagerbewegung, bestand
from material.models import Material
from mitarbeiter.models import Mitarbeiter
from planung import dienst as planung
from planung.models import Abwesenheit
from produktion import dienst as produktion
from produktion.models import Vorlage
from projekte.models import Projekt
from zeiten.models import Zeitbuchung

pytestmark = pytest.mark.django_db


@pytest.fixture
def chef_browser(chef):
    from django.test import Client
    c = Client()
    c.force_login(chef)
    return c


@pytest.fixture
def projekt():
    return Projekt.objects.create(projektnr="P-1", name="Küche", status="Auftrag",
                                  kunde=Kunde.objects.create(kundennr="K-1", name="Weber"))


@pytest.fixture
def geselle(client, benutzer_mit_rolle):
    u = benutzer_mit_rolle(Rolle.MITARBEITER, "dieter")
    ma = Mitarbeiter.objects.create(kuerzel="D.Kaub", name="Dieter Kaub", benutzer=u)
    client.force_login(u)
    return ma


def test_start_kacheln_je_rolle(client, geselle, chef_browser):
    chef_client = chef_browser
    seite = client.get(reverse("handy:start")).content.decode()
    assert "Hallo Dieter Kaub" in seite and "Arbeit" in seite and "Zeit buchen" in seite and "Melden" in seite
    assert "Lieferungen" not in seite and "Freigaben" not in seite
    chef = chef_client.get(reverse("handy:start")).content.decode()
    assert "Lieferungen" in chef and "Freigaben" in chef and "Handy im WLAN einrichten" in chef
    assert "kein Mitarbeiter zugeordnet" in chef_client.get(reverse("handy:arbeit")).content.decode()


def test_mein_tag_arbeit_zeit(client, geselle, projekt, chef):
    heute = timezone.localdate()
    planung.termin_anlegen(datum=heute, aufgabe="Aufmaß Bad", mitarbeiter=geselle, beginn=time(9), ende=time(10),
                           ort="Hauptstr. 5 Neustadt", projekt=projekt, art="Aufmaß", benutzer=chef)
    ag = produktion.einzeln(projekt, Vorlage.objects.get(code="PL-010"), mitarbeiter=geselle, benutzer=chef)
    seite = client.get(reverse("handy:tag")).content.decode()
    assert "Aufmaß Bad" in seite and "Route öffnen" in seite
    client.post(reverse("handy:arbeit"), {"ag": ag.pk, "aktion": "starten"})
    client.post(reverse("handy:arbeit"), {"ag": ag.pk, "aktion": "fertig", "stunden": "2,5"})
    ag.refresh_from_db()
    assert ag.status == "Fertig" and ag.ist_std == Decimal("2.5")
    assert Zeitbuchung.objects.get().quelle == "Produktion"
    client.post(reverse("handy:zeit"), {"datum": heute.isoformat(), "stunden": "1,5", "projekt": projekt.pk,
                                        "taetigkeit": "Montage", "pause": "0"})
    assert Zeitbuchung.objects.filter(taetigkeit="Montage", stunden=Decimal("1.5")).exists()
    antwort = client.post(reverse("handy:zeit"), {"datum": heute.isoformat(), "stunden": "20", "pause": "0"}, follow=True)
    assert "16 Stunden" in antwort.content.decode()


def test_zaehlen_auf_dem_handy(client, geselle, chef):
    m = Material.objects.create(materialnr="PL-1", bezeichnung="Platte", einheit="Stk", lagerartikel=True, ek_netto=10)
    Lagerbewegung.objects.create(material=m, datum=date(2026, 1, 1), art="Startbestand", menge=5, erfasst_von=chef)
    assert "keine Inventur" in client.get(reverse("handy:zaehlen")).content.decode()
    inv = inventur.anlegen(benutzer=chef, stichtag=date(2026, 12, 31), art="Vollinventur", lagerbereich="", verantwortlich="",
                           blind=True, toleranz_prozent=Decimal("2"), toleranz_wert=Decimal("50"), hinweis="")
    inventur.starten(inv, chef)
    seite = client.get(reverse("handy:zaehlen")).content.decode()
    assert "PL-1" in seite and "Soll 5" not in seite
    pos = inv.positionen.get()
    client.post(reverse("handy:zaehlen"), {"position": pos.pk, "aktion": "zaehlen", "menge": "4"})
    pos.refresh_from_db()
    assert pos.ist == 4 and pos.zaehler == "Dieter Kaub"
    assert "Alles gezählt" in client.get(reverse("handy:zaehlen")).content.decode()


def test_lieferungen_und_freigaben(chef_browser, chef, projekt, geselle):
    chef_client = chef_browser
    from lieferanten.models import Lieferant
    m = Material.objects.create(materialnr="BL-1", bezeichnung="Topfband", einheit="Stk", ek_netto=2,
                                lieferant=Lieferant.objects.create(name="Würth"))
    b = lager.bestellen(material=m, menge=Decimal("10"), benutzer=chef)
    chef_client.post(reverse("handy:lieferungen"), {"bestellung": b.pk, "was": "teil", "menge": "4"})
    assert bestand(m) == 4
    chef_client.post(reverse("handy:lieferungen"), {"bestellung": b.pk, "was": "alles"})
    assert bestand(m) == 10
    a = planung.abwesenheit_erfassen(mitarbeiter=geselle, von=date(2026, 12, 1), bis=date(2026, 12, 3), art="Urlaub",
                                     status="Beantragt", benutzer=chef)
    au = Auftrag.objects.create(aunr="AU-0001", projekt=projekt, angebot_netto=1000)
    seite = chef_client.get(reverse("handy:freigaben")).content.decode()
    assert "Dieter Kaub" in seite and "AU-0001" in seite and "Chef-Freigabe" in seite
    chef_client.post(reverse("handy:freigaben"), {"art": "abwesenheit", "id": a.pk, "ja": "1"})
    chef_client.post(reverse("handy:freigaben"), {"art": "auftrag", "id": au.pk, "wer": "chef", "ja": "1"})
    assert Abwesenheit.objects.get().status == "Freigegeben" and Auftrag.objects.get().freigabe_chef == "Freigegeben"
    antwort = chef_client.post(reverse("handy:freigaben"), {"art": "auftrag", "id": au.pk, "wer": "meister", "ja": "1"}, follow=True)
    assert "darf nur der Meister" in antwort.content.decode()


def test_melden_mit_foto_und_erledigen(client, geselle, chef_browser, projekt, settings, tmp_path):
    chef_client = chef_browser
    settings.DATEIEN_DIR = tmp_path / "dateien"
    bild = SimpleUploadedFile("bruch.jpg", b"\xff\xd8\xff\xe0test", content_type="image/jpeg")
    client.post(reverse("handy:melden"), {"art": "Bruch / Schaden", "projekt": projekt.pk, "text": "Front zerkratzt",
                                          "foto": bild})
    m = Meldung.objects.get()
    assert m.projekt == projekt and m.foto.endswith(".jpg") and (tmp_path / "dateien" / "meldungen" / m.foto).exists()
    assert client.get(reverse("handy:foto", args=[m.pk])).status_code == 200
    falsch = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
    antwort = client.post(reverse("handy:melden"), {"text": "x", "foto": falsch}, follow=True)
    assert "JPG/PNG" in antwort.content.decode() and Meldung.objects.count() == 1
    assert client.get(reverse("handy:meldungen")).status_code == 403
    assert "Front zerkratzt" in chef_client.get(reverse("handy:meldungen")).content.decode()
    chef_client.post(reverse("handy:meldungen"), {"id": m.pk, "antwort": "neue Front bestellt"})
    m.refresh_from_db()
    assert m.erledigt_am and m.antwort == "neue Front bestellt"
    assert "✓ erledigt" in client.get(reverse("handy:melden")).content.decode()


def test_zuschnitt(chef_client, chef, projekt):
    from tests.test_moebel import UNTERSCHRANK
    from moebel import dienst as moebel
    for nr, bez, s in (("PL-WEI-P2-19", "Spanplatte", 19), ("HDF-08", "HDF", 8)):
        Material.objects.create(materialnr=nr, bezeichnung=bez, einheit="m²", staerke_mm=s, format="2800 x 2070 mm")
    p = moebel.speichern(projekt=projekt, eingaben=UNTERSCHRANK, benutzer=chef)
    assert p.positions_id in chef_client.get(reverse("handy:zuschnitt")).content.decode()
    seite = chef_client.get(reverse("handy:zuschnitt_detail", args=[p.pk])).content.decode()
    assert "713 × 593" in seite and "localStorage" in seite and "PL-WEI-P2-19 Spanplatte" in seite


def test_verbinden_schalter_und_qr(chef_client, client, benutzer_mit_rolle, settings, tmp_path):
    settings.HANDY_SCHALTER = tmp_path / "handy_im_netz.txt"
    assert not netz.an() and netz.bindeadresse() == "127.0.0.1:8000"
    seite = chef_client.get(reverse("handy:verbinden")).content.decode()
    assert "AUS" in seite and "<svg" not in seite
    chef_client.post(reverse("handy:verbinden"), {"ein": "1"})
    assert netz.an() and netz.bindeadresse() == "0.0.0.0:8000"
    seite = chef_client.get(reverse("handy:verbinden")).content.decode()
    assert "<svg" in seite and ":8000/handy/" in seite
    from django.core.management import call_command
    from io import StringIO
    aus = StringIO()
    call_command("netzadresse", stdout=aus)
    assert aus.getvalue().splitlines()[0] == "0.0.0.0:8000" and "/handy/" in aus.getvalue()
    chef_client.post(reverse("handy:verbinden"), {"ein": "0"})
    assert not netz.an()
    client.force_login(benutzer_mit_rolle(Rolle.MEISTER))
    assert client.get(reverse("handy:verbinden")).status_code == 403
