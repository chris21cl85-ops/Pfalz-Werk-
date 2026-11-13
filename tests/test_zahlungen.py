import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from projekte.models import Projekt
from rechnungen import dienst
from rechnungen.models import Firmendaten, Position, Rechnung, Zahlung, ZahlungGesperrt

pytestmark = pytest.mark.django_db
HEUTE = timezone.localdate()


@pytest.fixture
def firma():
    fd = Firmendaten.laden()
    for feld, wert in dict(firmenname="Schreinerei Lorenz", strasse="Hauptstr. 1", plz="67433", ort="Neustadt",
                           iban="DE02120300000000202051", steuernummer="31/123/45678").items():
        setattr(fd, feld, wert)
    fd.save()
    return fd


@pytest.fixture
def projekt():
    kunde = Kunde.objects.create(kundennr="K-1", name="Familie Weber", kundenart="Privat",
                                 strasse="Gartenweg 3", plz="67434", ort="Hambach")
    return Projekt.objects.create(projektnr="P-001", name="Einbauküche", kunde=kunde)


def offene_rechnung(projekt, chef, preis="1000", zahlungsziel="14", heute=None):
    """Festgeschriebene Rechnung über 1.190,00 € brutto."""
    r = dienst.entwurf_anlegen(projekt=projekt, art=Rechnung.Art.RECHNUNG, benutzer=chef, zahlungsziel=zahlungsziel)
    Position.objects.create(rechnung=r, pos=1, text="Küche", menge=1, einheit="pausch.", einzelpreis=Decimal(preis))
    return dienst.festschreiben(r, chef, heute=heute)


def neu(r):
    return Rechnung.objects.get(pk=r.pk)


# ------------------------------------------------------------------ Buchen
def test_voller_betrag(firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    assert (r.offen, r.status_text) == (Decimal("1190.00"), "Offen")
    z = dienst.zahlung_buchen(r, art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    assert (z.znr, z.betrag, z.skonto, z.richtung) == ("Z-0001", Decimal("1190.00"), Decimal("0.00"), "Ein")
    r = neu(r)
    assert (r.bezahlt, r.offen, r.status_text) == (Decimal("1190.00"), Decimal("0.00"), "Bezahlt")
    eintrag = Protokolleintrag.objects.get(aktion="zahlung_gebucht")
    assert eintrag.gegenstand == r.nummer and "Z-0001" in eintrag.details and "Bezahlt" in eintrag.details


def test_teilzahlungen(firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    dienst.zahlung_buchen(r, art=dienst.TEIL, betrag=Decimal("500"), datum=HEUTE, benutzer=chef)
    r = neu(r)
    assert (r.offen, r.status_text) == (Decimal("690.00"), "Teilbezahlt")
    z = dienst.zahlung_buchen(r, art=dienst.VOLL, datum=HEUTE, benutzer=chef)  # Rest
    assert z.betrag == Decimal("690.00") and z.znr == "Z-0002"
    assert neu(r).status_text == "Bezahlt"


def test_skonto_wie_excel(firma, projekt, chef):
    r = offene_rechnung(projekt, chef, zahlungsziel="14s")
    assert r.skonto_betrag == Decimal("23.80") and r.skonto_bis == r.datum + dt.timedelta(days=7)
    z = dienst.zahlung_buchen(r, art=dienst.SKONTO, datum=HEUTE, benutzer=chef)
    assert (z.betrag, z.skonto) == (Decimal("1166.20"), Decimal("23.80"))
    r = neu(r)
    assert (r.offen, r.skonto_gesamt, r.status_text) == (Decimal("0.00"), Decimal("23.80"), "Bezahlt")


def test_skonto_ohne_angebot_abgelehnt(firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    with pytest.raises(dienst.RechnungFehler, match="kein Skonto"):
        dienst.zahlung_buchen(r, art=dienst.SKONTO, datum=HEUTE, benutzer=chef)


def test_ueberzahlung_wird_angezeigt(firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    dienst.zahlung_buchen(r, art=dienst.TEIL, betrag=Decimal("1200"), datum=HEUTE, benutzer=chef)
    r = neu(r)
    assert (r.offen, r.status_text) == (Decimal("-10.00"), "Überzahlt")


def test_bezahlte_rechnung_nimmt_keine_zahlung_mehr(firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    dienst.zahlung_buchen(r, art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    with pytest.raises(dienst.RechnungFehler, match="vollständig bezahlt"):
        dienst.zahlung_buchen(r, art=dienst.TEIL, betrag=Decimal("1"), datum=HEUTE, benutzer=chef)


def test_keine_zahlung_auf_entwurf_oder_in_zukunft(firma, projekt, chef):
    entwurf = dienst.entwurf_anlegen(projekt=projekt, art=Rechnung.Art.RECHNUNG, benutzer=chef)
    with pytest.raises(dienst.RechnungFehler, match="festgeschriebenen"):
        dienst.zahlung_buchen(entwurf, art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    r = offene_rechnung(projekt, chef)
    with pytest.raises(dienst.RechnungFehler, match="Zukunft"):
        dienst.zahlung_buchen(r, art=dienst.VOLL, datum=HEUTE + dt.timedelta(days=1), benutzer=chef)


def test_ueberfaellig(firma, projekt, chef):
    r = offene_rechnung(projekt, chef, heute=HEUTE - dt.timedelta(days=30))
    assert r.ist_ueberfaellig and r.status_text == "Offen · überfällig"
    dienst.zahlung_buchen(r, art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    assert not neu(r).ist_ueberfaellig


def test_rechnung_bleibt_beim_zahlen_unveraendert(firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    dienst.zahlung_buchen(r, art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    assert neu(r).pruefsumme_stimmt()


# ------------------------------------------------------------------ Sperre und Gegenbuchung
def test_zahlung_nicht_aenderbar_oder_loeschbar(firma, projekt, chef):
    z = dienst.zahlung_buchen(offene_rechnung(projekt, chef), art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    z.betrag = Decimal("1")
    with pytest.raises(ZahlungGesperrt):
        z.save()
    with pytest.raises(ZahlungGesperrt):
        z.delete()
    with pytest.raises(ZahlungGesperrt):
        Zahlung.objects.all().delete()
    with pytest.raises(ZahlungGesperrt):
        Zahlung.objects.filter(pk=z.pk).update(betrag=1)


def test_gegenbuchung(firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    falsch = dienst.zahlung_buchen(r, art=dienst.TEIL, betrag=Decimal("119"), datum=HEUTE, benutzer=chef)
    gegen = dienst.zahlung_gegenbuchen(falsch, benutzer=chef, grund="Betrag vertippt")
    assert (gegen.znr, gegen.betrag, gegen.gegenbuchung_zu) == ("Z-0002", Decimal("-119.00"), falsch)
    r = neu(r)
    assert (r.offen, r.status_text) == (Decimal("1190.00"), "Offen")
    assert Zahlung.objects.count() == 2  # nichts gelöscht
    with pytest.raises(dienst.RechnungFehler, match="schon gegengebucht"):
        dienst.zahlung_gegenbuchen(falsch, benutzer=chef, grund="nochmal")
    with pytest.raises(dienst.RechnungFehler):
        dienst.zahlung_gegenbuchen(gegen, benutzer=chef, grund="Gegenbuchung der Gegenbuchung")
    assert Protokolleintrag.objects.filter(aktion="zahlung_gegengebucht").exists()


def test_gegenbuchung_braucht_grund(firma, projekt, chef):
    z = dienst.zahlung_buchen(offene_rechnung(projekt, chef), art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    with pytest.raises(dienst.RechnungFehler, match="Grund"):
        dienst.zahlung_gegenbuchen(z, benutzer=chef, grund="  ")


# ------------------------------------------------------------------ Oberfläche
def test_zahlung_ueber_seite_buchen(chef_client, firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    seite = chef_client.get(reverse("rechnungen:detail", args=[r.pk])).content.decode()
    assert "Zahlung buchen" in seite and "1.190,00 €" in seite
    antwort = chef_client.post(reverse("rechnungen:zahlung", args=[r.pk]), {
        "art": "teil", "betrag": "1.000,50", "datum": HEUTE.isoformat(), "konto": "Bar", "notiz": "bar auf Baustelle"},
        follow=True)
    inhalt = antwort.content.decode()
    assert "Z-0001" in inhalt and "Teilbezahlt" in inhalt
    z = Zahlung.objects.get()
    assert (z.betrag, z.konto, z.notiz, z.erfasst_von) == (Decimal("1000.50"), "Bar", "bar auf Baustelle", chef)


def test_teilbetrag_ohne_betrag_abgelehnt(chef_client, firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    antwort = chef_client.post(reverse("rechnungen:zahlung", args=[r.pk]),
                               {"art": "teil", "datum": HEUTE.isoformat(), "konto": "Bank"}, follow=True)
    assert "nicht gebucht" in antwort.content.decode() and not Zahlung.objects.exists()


def test_gegenbuchung_ueber_seite(chef_client, firma, projekt, chef):
    z = dienst.zahlung_buchen(offene_rechnung(projekt, chef), art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    antwort = chef_client.post(reverse("rechnungen:gegenbuchung", args=[z.pk]), {"grund": "falsche Rechnung"},
                               follow=True)
    assert "aufgehoben" in antwort.content.decode()
    assert neu(z.rechnung).status_text == "Offen"


def test_bezahlte_rechnung_zeigt_kein_formular(chef_client, firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    dienst.zahlung_buchen(r, art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    seite = chef_client.get(reverse("rechnungen:detail", args=[r.pk])).content.decode()
    assert "Zahlung buchen" not in seite and "Bezahlt" in seite


def test_liste_filter_und_summen(chef_client, firma, projekt, chef):
    alt = offene_rechnung(projekt, chef, heute=HEUTE - dt.timedelta(days=40))   # überfällig
    offen = offene_rechnung(projekt, chef)                                       # offen
    bezahlt = offene_rechnung(projekt, chef)
    dienst.zahlung_buchen(bezahlt, art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    inhalt = chef_client.get(reverse("rechnungen:liste")).content.decode()
    assert "2.380,00 €" in inhalt and "davon überfällig" in inhalt  # offen gesamt
    unbezahlt = chef_client.get(reverse("rechnungen:liste"), {"status": "unbezahlt"}).content.decode()
    assert alt.nummer in unbezahlt and offen.nummer in unbezahlt and bezahlt.nummer not in unbezahlt
    ueber = chef_client.get(reverse("rechnungen:liste"), {"status": "ueberfaellig"}).content.decode()
    assert alt.nummer in ueber and offen.nummer not in ueber
    nur_bezahlt = chef_client.get(reverse("rechnungen:liste"), {"status": "bezahlt"}).content.decode()
    assert bezahlt.nummer in nur_bezahlt and offen.nummer not in nur_bezahlt


def test_projektkarte_zeigt_offen(chef_client, firma, projekt, chef):
    r = offene_rechnung(projekt, chef)
    dienst.zahlung_buchen(r, art=dienst.TEIL, betrag=Decimal("190"), datum=HEUTE, benutzer=chef)
    inhalt = chef_client.get(reverse("projekte:detail", args=[projekt.pk])).content.decode()
    assert "1.000,00 €" in inhalt and "Teilbezahlt" in inhalt


@pytest.mark.parametrize("rolle", [Rolle.MEISTER, Rolle.MITARBEITER])
def test_nur_buero_darf_zahlungen_buchen(client, benutzer_mit_rolle, firma, projekt, chef, rolle):
    r = offene_rechnung(projekt, chef)
    client.force_login(benutzer_mit_rolle(rolle))
    antwort = client.post(reverse("rechnungen:zahlung", args=[r.pk]),
                          {"art": "voll", "datum": HEUTE.isoformat(), "konto": "Bank"})
    assert antwort.status_code == 403 and not Zahlung.objects.exists()
