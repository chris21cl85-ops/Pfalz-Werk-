import datetime as dt
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from lieferanten.models import Lieferant
from projekte.models import Projekt
from rechnungen import dienst
from rechnungen import eingang_dienst as ed
from rechnungen.models import Eingangsrechnung, RechnungGesperrt, Zahlung

pytestmark = pytest.mark.django_db
HEUTE = timezone.localdate()


@pytest.fixture
def projekt():
    kunde = Kunde.objects.create(kundennr="K-1", name="Weber")
    return Projekt.objects.create(projektnr="P-001", name="Küche", kunde=kunde)


def erfassen(chef, **werte):
    daten = dict(lieferant_name="Wickert", lieferanten_nr="R-4711", datum=HEUTE, kategorie="Material / Wareneingang",
                 projekt=None, netto=Decimal("1000"), ust_satz=Decimal("19"), ziel_tage=14, skonto_prozent=None,
                 skonto_tage=None, benutzer=chef)
    daten.update(werte)
    return ed.erfassen(**daten)


# ------------------------------------------------------------------ Erfassen
def test_erfassen_wie_excel(chef, projekt):
    er = erfassen(chef, projekt=projekt, netto=Decimal("1234.56"), skonto_prozent=Decimal("2"), skonto_tage=10)
    assert er.ernr == "ER-0001"
    assert (er.ust, er.brutto) == (Decimal("234.57"), Decimal("1469.13"))
    assert er.faellig == HEUTE + dt.timedelta(days=14) and er.skonto_bis == HEUTE + dt.timedelta(days=10)
    assert er.lieferant.name == "Wickert"  # unbekannter Lieferant wird angelegt
    assert (er.offen, er.status_text) == (Decimal("1469.13"), "Offen")
    assert erfassen(chef, lieferanten_nr="R-4712").ernr == "ER-0002"
    assert Lieferant.objects.count() == 1
    eintrag = Protokolleintrag.objects.filter(aktion="eingangsrechnung_erfasst").first()
    assert eintrag and "Wickert" in eintrag.details


@pytest.mark.parametrize("satz,ust", [(Decimal("7"), Decimal("70.00")), (Decimal("0"), Decimal("0.00"))])
def test_vorsteuersaetze(chef, satz, ust):
    er = erfassen(chef, ust_satz=satz)
    assert er.ust == ust and er.brutto == Decimal("1000.00") + ust


def test_doppelte_rechnung_abgelehnt(chef):
    erfassen(chef)
    with pytest.raises(dienst.RechnungFehler, match="schon erfasst"):
        erfassen(chef, lieferant_name="wickert ", lieferanten_nr="r-4711")


def test_bekannter_lieferant_wird_genutzt(chef):
    wickert = Lieferant.objects.create(name="Holz Wickert GmbH")
    assert erfassen(chef, lieferant_name="holz wickert gmbh").lieferant == wickert


def test_vorgaben_aus_lieferantenkarte():
    l = Lieferant(name="X", zahlungsziel_tage=30, skonto="2,5 % bei 10 Tagen")
    assert ed.lieferanten_vorgaben(l) == {"ziel_tage": 30, "skonto_prozent": Decimal("2.5"), "skonto_tage": 10}
    assert ed.lieferanten_vorgaben(Lieferant(name="Y")) == {}


def test_erfasst_ist_gesperrt(chef):
    er = erfassen(chef)
    er.netto = Decimal("1")
    with pytest.raises(RechnungGesperrt):
        er.save()
    with pytest.raises(RechnungGesperrt):
        er.delete()


def test_beleg_wird_gespeichert(chef):
    pdf = SimpleUploadedFile("rechnung.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    er = erfassen(chef, beleg=pdf)
    assert bytes(er.beleg) == b"%PDF-1.4 test" and er.beleg_name == "rechnung.pdf" and er.beleg_typ == "application/pdf"
    with pytest.raises(dienst.RechnungFehler, match="PDF-Datei oder ein Foto"):
        erfassen(chef, lieferanten_nr="X", beleg=SimpleUploadedFile("virus.exe", b"MZ"))


# ------------------------------------------------------------------ Bezahlen
def test_voll_teil_und_status(chef):
    er = erfassen(chef)
    z = ed.bezahlen(er, art=ed.TEIL, betrag=Decimal("190"), datum=HEUTE, benutzer=chef)
    assert (z.richtung, z.eingangsrechnung, z.rechnung) == ("Aus", er, None)
    er = Eingangsrechnung.objects.get(pk=er.pk)
    assert (er.offen, er.status_text) == (Decimal("1000.00"), "Teilbezahlt")
    ed.bezahlen(er, art=ed.VOLL, datum=HEUTE, benutzer=chef)
    assert Eingangsrechnung.objects.get(pk=er.pk).status_text == "Bezahlt"


def test_skonto_wie_excel(chef):
    er = erfassen(chef, skonto_prozent=Decimal("3"), skonto_tage=10)
    z = ed.bezahlen(er, art=ed.SKONTO, datum=HEUTE, benutzer=chef)
    assert (z.betrag, z.skonto) == (Decimal("1154.30"), Decimal("35.70"))
    assert Eingangsrechnung.objects.get(pk=er.pk).status_text == "Bezahlt"


def test_skonto_nicht_nach_frist_oder_teilzahlung(chef):
    alt = erfassen(chef, datum=HEUTE - dt.timedelta(days=20), skonto_prozent=Decimal("2"), skonto_tage=10)
    with pytest.raises(dienst.RechnungFehler, match="Skonto ist hier nicht möglich"):
        ed.bezahlen(alt, art=ed.SKONTO, datum=HEUTE, benutzer=chef)
    neu = erfassen(chef, lieferanten_nr="R-2", skonto_prozent=Decimal("2"), skonto_tage=10)
    ed.bezahlen(neu, art=ed.TEIL, betrag=Decimal("100"), datum=HEUTE, benutzer=chef)
    with pytest.raises(dienst.RechnungFehler):
        ed.bezahlen(Eingangsrechnung.objects.get(pk=neu.pk), art=ed.SKONTO, datum=HEUTE, benutzer=chef)


def test_ueberfaellig(chef):
    er = erfassen(chef, datum=HEUTE - dt.timedelta(days=30))
    assert er.ist_ueberfaellig and er.status_text == "Überfällig"


def test_gegenbuchung_bei_eingang(chef):
    er = erfassen(chef)
    z = ed.bezahlen(er, art=ed.VOLL, datum=HEUTE, benutzer=chef)
    gegen = dienst.zahlung_gegenbuchen(z, benutzer=chef, grund="falsche Rechnung")
    assert (gegen.richtung, gegen.eingangsrechnung, gegen.betrag) == ("Aus", er, -z.betrag)
    assert Eingangsrechnung.objects.get(pk=er.pk).status_text == "Offen"


def test_zahlungsnummern_gemeinsam_mit_ausgang(chef, projekt):
    """Ein- und Ausgänge laufen wie im Blatt „Zahlungen“ in einem Nummernkreis."""
    er = erfassen(chef)
    assert ed.bezahlen(er, art=ed.TEIL, betrag=Decimal("1"), datum=HEUTE, benutzer=chef).znr == "Z-0001"
    assert dienst.naechste_znr() == "Z-0002"


# ------------------------------------------------------------------ Stornieren
def test_erfassung_stornieren(chef):
    er = erfassen(chef)
    er = ed.erfassung_stornieren(er, benutzer=chef, grund="Betrag vertippt")
    er = Eingangsrechnung.objects.get(pk=er.pk)
    assert er.ist_storniert and er.offen == 0 and er.status_text == "Storniert"
    assert erfassen(chef).ernr == "ER-0002"  # gleiche Lieferanten-Nr. darf neu erfasst werden
    with pytest.raises(RechnungGesperrt):  # danach endgültig fest
        er.storno_grund = "anders"
        er.save(update_fields=["storno_grund"])
    with pytest.raises(dienst.RechnungFehler, match="schon storniert"):
        ed.erfassung_stornieren(er, benutzer=chef, grund="nochmal")


def test_stornieren_nicht_nach_zahlung(chef):
    er = erfassen(chef)
    ed.bezahlen(er, art=ed.TEIL, betrag=Decimal("10"), datum=HEUTE, benutzer=chef)
    with pytest.raises(dienst.RechnungFehler, match="schon gezahlt"):
        ed.erfassung_stornieren(er, benutzer=chef, grund="x")


# ------------------------------------------------------------------ Oberfläche
def test_erfassen_ueber_seite(chef_client, projekt):
    antwort = chef_client.post(reverse("eingang:neu"), {
        "lieferant": "Beschlag-Profi", "lieferanten_nr": "2026-88", "datum": HEUTE.isoformat(),
        "kategorie": "Material / Wareneingang", "projekt": projekt.pk, "netto": "2.500,00", "ust_satz": "19",
        "ziel_tage": "30", "skonto_prozent": "2", "skonto_tage": "10",
        "beleg": SimpleUploadedFile("scan.jpg", b"\xff\xd8\xff", content_type="image/jpeg")}, follow=True)
    inhalt = antwort.content.decode()
    assert "Erfasst: ER-0001" in inhalt and "2.975,00 €" in inhalt
    er = Eingangsrechnung.objects.get()
    assert er.projekt == projekt and er.beleg_typ == "image/jpeg"
    beleg = chef_client.get(reverse("eingang:beleg", args=[er.pk]))
    assert beleg.content == b"\xff\xd8\xff" and beleg["Content-Type"] == "image/jpeg"


def test_doppelt_ueber_seite(chef_client, chef):
    erfassen(chef)
    antwort = chef_client.post(reverse("eingang:neu"), {
        "lieferant": "Wickert", "lieferanten_nr": "R-4711", "datum": HEUTE.isoformat(),
        "kategorie": "Sonstiges", "netto": "10", "ust_satz": "19", "ziel_tage": "14"})
    assert "schon erfasst" in antwort.content.decode() and Eingangsrechnung.objects.count() == 1


def test_bezahlen_ueber_seite(chef_client, chef):
    er = erfassen(chef, skonto_prozent=Decimal("2"), skonto_tage=10)
    seite = chef_client.get(reverse("eingang:detail", args=[er.pk])).content.decode()
    assert "Mit 2 % Skonto" in seite and "1.166,20 €" in seite
    antwort = chef_client.post(reverse("eingang:zahlung", args=[er.pk]),
                               {"art": "skonto", "datum": HEUTE.isoformat(), "konto": "Bank"}, follow=True)
    assert "Status: Bezahlt" in antwort.content.decode()


def test_liste_filter_und_summen(chef_client, chef):
    offen = erfassen(chef)
    alt = erfassen(chef, lieferanten_nr="ALT", datum=HEUTE - dt.timedelta(days=40))
    bezahlt = erfassen(chef, lieferanten_nr="BEZ")
    ed.bezahlen(bezahlt, art=ed.VOLL, datum=HEUTE, benutzer=chef)
    inhalt = chef_client.get(reverse("eingang:liste")).content.decode()
    assert offen.ernr in inhalt and alt.ernr in inhalt and bezahlt.ernr not in inhalt
    assert "2.380,00 €" in inhalt and "1.190,00 €" in inhalt  # zu bezahlen / davon überfällig
    alle = chef_client.get(reverse("eingang:liste"), {"status": "alle"}).content.decode()
    assert bezahlt.ernr in alle
    suche = chef_client.get(reverse("eingang:liste"), {"status": "alle", "suche": "ALT"}).content.decode()
    assert alt.ernr in suche and offen.ernr not in suche


def test_stornieren_ueber_seite(chef_client, chef):
    er = erfassen(chef)
    antwort = chef_client.post(reverse("eingang:stornieren", args=[er.pk]), {"grund": "doppelt"}, follow=True)
    assert "ist storniert" in antwort.content.decode()


def test_kachel_und_navi(chef_client):
    inhalt = chef_client.get("/").content.decode()
    assert "Eingangsrechnungen" in inhalt and reverse("eingang:liste") in inhalt


@pytest.mark.parametrize("rolle", [Rolle.MEISTER, Rolle.MITARBEITER])
def test_rechte(client, benutzer_mit_rolle, rolle):
    client.force_login(benutzer_mit_rolle(rolle))
    assert client.get(reverse("eingang:liste")).status_code == 403
    assert client.get(reverse("eingang:neu")).status_code == 403
    assert not Zahlung.objects.exists()


def test_lieferanten_und_projektkarte(chef_client, chef, projekt):
    er = erfassen(chef, projekt=projekt, netto=Decimal("800"))
    erfassen(chef, lieferanten_nr="R-9", projekt=projekt, netto=Decimal("200"))
    lief = chef_client.get(reverse("lieferanten:detail", args=[er.lieferant.pk])).content.decode()
    assert er.ernr in lief and "R-4711" in lief
    proj = chef_client.get(reverse("projekte:detail", args=[projekt.pk])).content.decode()
    assert "Kosten (Eingangsrechnungen)" in proj and "1.000,00 €" in proj


def test_meister_sieht_keine_belege_auf_lieferantenkarte(client, benutzer_mit_rolle, chef):
    er = erfassen(chef)
    client.force_login(benutzer_mit_rolle(Rolle.MEISTER))
    assert er.ernr not in client.get(reverse("lieferanten:detail", args=[er.lieferant.pk])).content.decode()
