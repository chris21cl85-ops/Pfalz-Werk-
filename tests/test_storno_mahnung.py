import datetime as dt
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest
from django.urls import reverse
from django.utils import timezone

from kern.models import Protokolleintrag
from kunden.models import Kunde
from projekte.models import Projekt
from rechnungen import dienst
from rechnungen.models import Firmendaten, Mahnung, Position, Rechnung, RechnungGesperrt
from tests.test_xrechnung import ABR, NS, SUMME, betrag, pruefe_regeln, text

pytestmark = pytest.mark.django_db
HEUTE = timezone.localdate()


@pytest.fixture(autouse=True)
def ohne_kompression(monkeypatch):
    from reportlab import rl_config
    monkeypatch.setattr(rl_config, "pageCompression", 0)


@pytest.fixture
def firma():
    fd = Firmendaten.laden()
    for feld, wert in dict(firmenname="Schreinerei Lorenz", inhaber="C. Lorenz", strasse="Hauptstr. 1", plz="67433",
                           ort="Neustadt", telefon="06321 12345", email="info@example.de",
                           iban="DE02120300000000202051", steuernummer="31/123/45678", mahngebuehr=Decimal("7.50"),
                           letzte_rechnungsnummer=0).items():
        setattr(fd, feld, wert)
    fd.save()
    return fd


@pytest.fixture
def projekt():
    kunde = Kunde.objects.create(kundennr="K-1", name="Bäckerei Weber GmbH", kundenart="Gewerbe",
                                 strasse="Gartenweg 3", plz="67434", ort="Hambach", email="buero@example.org")
    return Projekt.objects.create(projektnr="P-001", name="Ladentheke", kunde=kunde)


def rechnung(projekt, chef, heute=None, **werte):
    r = dienst.entwurf_anlegen(projekt=projekt, art=werte.pop("art", Rechnung.Art.RECHNUNG), benutzer=chef, **werte)
    if r.art == Rechnung.Art.RECHNUNG:
        Position.objects.create(rechnung=r, pos=1, text="Theke", menge=2, einheit="Stk", einzelpreis=Decimal("500"))
        Position.objects.create(rechnung=r, pos=2, text="Montage", menge=Decimal("3.5"), einheit="Std",
                                einzelpreis=Decimal("60"))
    return dienst.festschreiben(r, chef, heute=heute)


def neu(r):
    return Rechnung.objects.get(pk=r.pk)


# ------------------------------------------------------------------ Storno
def test_storno_wie_excel(firma, projekt, chef):
    alt = rechnung(projekt, chef)
    storno = dienst.stornieren(alt, chef, "falscher Betrag")
    assert storno.nummer == "RE-2026-0002" and storno.art == "Storno" and storno.storno_von == alt
    assert (storno.netto, storno.ust, storno.brutto) == (-alt.netto, -alt.ust, -alt.brutto)
    assert [p.menge for p in storno.positionen.all()] == [Decimal("-2"), Decimal("-3.5")]
    assert storno.titel == "Stornorechnung" and storno.status_text == "Storno" and storno.offen == 0
    alt = neu(alt)
    assert alt.ist_storniert and alt.status_text == "Storniert" and alt.offen == 0
    assert alt.stornorechnung == storno
    assert alt.pruefsumme_stimmt() and neu(storno).pruefsumme_stimmt()  # Original unverändert
    pdf = bytes(storno.pdf)
    assert b"Stornorechnung" in pdf and b"Hiermit stornieren wir die Rechnung RE-2026-0001" in pdf
    assert b"Gutschriftsbetrag" in pdf and b"Bitte" not in pdf
    eintrag = Protokolleintrag.objects.get(aktion="rechnung_storniert")
    assert eintrag.gegenstand == alt.nummer and "RE-2026-0002" in eintrag.details and "falscher Betrag" in eintrag.details


def test_storno_nur_einmal_und_nicht_vom_storno(firma, projekt, chef):
    alt = rechnung(projekt, chef)
    storno = dienst.stornieren(alt, chef)
    with pytest.raises(dienst.RechnungFehler, match="schon storniert"):
        dienst.stornieren(alt, chef)
    with pytest.raises(dienst.RechnungFehler, match="Stornorechnung kann nicht"):
        dienst.stornieren(storno, chef)


def test_storno_nicht_nach_zahlung(firma, projekt, chef):
    alt = rechnung(projekt, chef)
    z = dienst.zahlung_buchen(alt, art=dienst.TEIL, betrag=Decimal("100"), datum=HEUTE, benutzer=chef)
    with pytest.raises(dienst.RechnungFehler, match="Geld eingegangen"):
        dienst.stornieren(alt, chef)
    dienst.zahlung_gegenbuchen(z, benutzer=chef, grund="Rücküberweisung")
    assert dienst.stornieren(neu(alt), chef).storno_von == alt


def test_storno_bleibt_gesperrt(firma, projekt, chef):
    storno = dienst.stornieren(rechnung(projekt, chef), chef)
    storno.netto = Decimal("1")
    with pytest.raises(RechnungGesperrt):
        storno.save()


def test_stornierter_abschlag_zaehlt_nicht_fuer_schluss(firma, projekt, chef):
    a1 = rechnung(projekt, chef, art=Rechnung.Art.ABSCHLAG, auftragswert=Decimal("10000"),
                  abschlag_prozent=Decimal("30"))
    dienst.stornieren(a1, chef)
    a2 = rechnung(projekt, chef, art=Rechnung.Art.ABSCHLAG, auftragswert=Decimal("10000"),
                  abschlag_prozent=Decimal("30"))
    assert a2.abschlag_nr == 1  # der stornierte zählt nicht mit (wie Abschlaege() im Makro)
    s = dienst.entwurf_anlegen(projekt=projekt, art=Rechnung.Art.SCHLUSS, benutzer=chef,
                               auftragswert=Decimal("10000"))
    texte = list(s.positionen.values_list("text", flat=True))
    assert len(texte) == 2 and a2.nummer in texte[1] and a1.nummer not in " ".join(texte)


def test_storno_xrechnung_typ_381(firma, projekt, chef):
    alt = rechnung(projekt, chef)
    assert alt.xml  # Gewerbekunde -> automatisch mit XRechnung
    storno = dienst.stornieren(alt, chef)
    baum = ET.fromstring(bytes(storno.xml))
    pruefe_regeln(baum)
    assert text(baum, "rsm:ExchangedDocument/ram:TypeCode") == "381"
    assert betrag(baum, SUMME + "/ram:GrandTotalAmount") == alt.brutto  # Gutschrift mit positiven Beträgen
    assert text(baum, ABR + "/ram:InvoiceReferencedDocument/ram:IssuerAssignedID") == alt.nummer
    assert baum.find(ABR + "/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime", NS) is None
    mengen = [text(z, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity")
              for z in baum.findall("rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem", NS)]
    assert mengen == ["2", "3.5"]


def test_storno_ohne_xrechnung_wenn_original_ohne(firma, projekt, chef):
    alt = rechnung(projekt, chef, mit_xrechnung=False)
    assert dienst.stornieren(alt, chef).xml is None


# ------------------------------------------------------------------ Mahnungen
def test_mahnstufen_wie_excel(firma, projekt, chef):
    r = rechnung(projekt, chef, heute=HEUTE - dt.timedelta(days=30))
    assert dienst.naechste_mahnstufe(r) == 1
    m1 = dienst.mahnen(r, 1, chef)
    assert (m1.stufe, m1.gebuehr, m1.frist, m1.offen) == (1, Decimal("0"), HEUTE + dt.timedelta(days=7), r.brutto)
    assert b"Zahlungserinnerung" in bytes(m1.pdf) and b"Ihrer Aufmerksamkeit" in bytes(m1.pdf)
    r = neu(r)
    assert r.mahnstufe == 1 and "Zahlungserinnerung" in r.status_text
    assert dienst.naechste_mahnstufe(r) == 2
    dienst.mahnen(r, 2, chef)
    m3 = dienst.mahnen(r, 3, chef)
    assert m3.gebuehr == Decimal("7.50") and m3.zu_zahlen == r.brutto + Decimal("7.50")
    assert b"Mahngeb" in bytes(m3.pdf) and b"trotz Erinnerung" in bytes(m3.pdf)
    assert m3.dateiname == f"{r.nummer}_2Mahnung_{HEUTE:%Y-%m-%d}.pdf"
    assert dienst.naechste_mahnstufe(neu(r)) == 3
    assert Protokolleintrag.objects.filter(aktion="rechnung_gemahnt").count() == 3
    assert neu(r).pruefsumme_stimmt()


def test_mahnung_nutzt_offenen_betrag(firma, projekt, chef):
    r = rechnung(projekt, chef)
    dienst.zahlung_buchen(r, art=dienst.TEIL, betrag=Decimal("1000"), datum=HEUTE, benutzer=chef)
    m = dienst.mahnen(neu(r), 1, chef)
    assert m.offen == r.brutto - Decimal("1000")


def test_keine_mahnung_wenn_bezahlt_oder_storniert(firma, projekt, chef):
    r = rechnung(projekt, chef)
    dienst.zahlung_buchen(r, art=dienst.VOLL, datum=HEUTE, benutzer=chef)
    with pytest.raises(dienst.RechnungFehler, match="bezahlt"):
        dienst.mahnen(neu(r), 1, chef)
    s = rechnung(projekt, chef)
    storno = dienst.stornieren(s, chef)
    for x in (neu(s), storno):
        with pytest.raises(dienst.RechnungFehler):
            dienst.mahnen(x, 1, chef)


def test_mahnung_gesperrt(firma, projekt, chef):
    m = dienst.mahnen(rechnung(projekt, chef), 1, chef)
    with pytest.raises(RechnungGesperrt):
        m.save()
    with pytest.raises(RechnungGesperrt):
        m.delete()
    with pytest.raises(RechnungGesperrt):
        Mahnung.objects.all().delete()


# ------------------------------------------------------------------ Skonto-Frist (wie Makro)
def test_skonto_nach_frist_abgelehnt(firma, projekt, chef):
    r = rechnung(projekt, chef, zahlungsziel="14s", heute=HEUTE - dt.timedelta(days=10))
    with pytest.raises(dienst.RechnungFehler, match="Skonto-Frist"):
        dienst.zahlung_buchen(r, art=dienst.SKONTO, datum=HEUTE, benutzer=chef)
    z = dienst.zahlung_buchen(r, art=dienst.SKONTO, datum=HEUTE - dt.timedelta(days=4), benutzer=chef)
    assert z.skonto > 0


# ------------------------------------------------------------------ Oberfläche
def test_mahnen_und_pdf_ueber_seite(chef_client, firma, projekt, chef):
    r = rechnung(projekt, chef)
    seite = chef_client.get(reverse("rechnungen:detail", args=[r.pk])).content.decode()
    assert "Erinnerung / Mahnung erstellen" in seite and "7,50 € Gebühr" in seite
    antwort = chef_client.post(reverse("rechnungen:mahnen", args=[r.pk]), {"stufe": "2"}, follow=True)
    assert "1. Mahnung erstellt" in antwort.content.decode()
    m = Mahnung.objects.get()
    pdf = chef_client.get(reverse("rechnungen:mahnung_pdf", args=[m.pk]))
    assert pdf["Content-Type"] == "application/pdf" and pdf.content == bytes(m.pdf)


def test_stornieren_ueber_seite(chef_client, firma, projekt, chef):
    r = rechnung(projekt, chef)
    assert "Rechnung stornieren" in chef_client.get(reverse("rechnungen:detail", args=[r.pk])).content.decode()
    chef_client.post(reverse("rechnungen:stornieren", args=[r.pk]), {"grund": "Test"})
    assert not neu(r).ist_storniert  # ohne Haken passiert nichts
    antwort = chef_client.post(reverse("rechnungen:stornieren", args=[r.pk]), {"grund": "Test", "bestaetigt": "1"},
                               follow=True)
    inhalt = antwort.content.decode()
    assert "ist storniert" in inhalt and "Storno zu" in inhalt
    original = chef_client.get(reverse("rechnungen:detail", args=[r.pk])).content.decode()
    assert "Storniert durch" in original and "Rechnung stornieren" not in original
    liste = chef_client.get(reverse("rechnungen:liste"), {"status": "storniert"}).content.decode()
    assert r.nummer in liste and "RE-2026-0002" in liste


def test_storno_nach_zahlung_zeigt_grund(chef_client, firma, projekt, chef):
    r = rechnung(projekt, chef)
    dienst.zahlung_buchen(r, art=dienst.TEIL, betrag=Decimal("50"), datum=HEUTE, benutzer=chef)
    seite = chef_client.get(reverse("rechnungen:detail", args=[r.pk])).content.decode()
    assert "Erst die Zahlungen per Gegenbuchung aufheben" in seite
