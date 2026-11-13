"""XRechnung (CII): Inhalt, Pflichtregeln der XRechnung 3.0 (BR-DE) und Rechenregeln der EN 16931 (BR-CO).

Das Schema (XSD) und die Regeln wurden beim Bau zusätzlich gegen die offiziellen Dateien geprüft
(ConnectingEurope/eInvoicing-EN16931, itplr-kosit/xrechnung-schematron); hier stehen die wichtigsten Regeln
als eigene Tests, damit sie bei jeder Änderung mitlaufen.
"""
import re
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest
from django.urls import reverse

from kern.models import Protokolleintrag
from kunden.models import Kunde
from projekte.models import Projekt
from rechnungen import dienst
from rechnungen.formulare import iban_gueltig
from rechnungen.models import Firmendaten, Position, Rechnung
from rechnungen.xrechnung import einheitcode

pytestmark = pytest.mark.django_db
NS = {"rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
      "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
      "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"}
SKONTO_REGEX = r"(^|\r?\n)#(SKONTO)#TAGE=([0-9]+#PROZENT=[0-9]+\.[0-9]{2})(#BASISBETRAG=-?[0-9]+\.[0-9]{2})?#$"


@pytest.fixture
def firma():
    fd = Firmendaten.laden()
    for feld, wert in dict(firmenname="Schreinerei Lorenz", inhaber="C. Lorenz", strasse="Hauptstr. 1", plz="67433",
                           ort="Neustadt", telefon="06321 12345", email="info@example.de", bic="BYLADEM1001",
                           iban="DE02120300000000202051", steuernummer="31/123/45678", ust_idnr="DE123456789",
                           bank="Sparkasse").items():
        setattr(fd, feld, wert)
    fd.save()
    return fd


@pytest.fixture
def behoerde():
    kunde = Kunde.objects.create(kundennr="K-7", name="Gemeinde Musterstadt", kundenart="Behörde",
                                 email="rechnung@example.org", strasse="Rathausplatz 1", plz="67434", ort="Musterstadt")
    return Projekt.objects.create(projektnr="P-7", name="Ratssaal Möbel & Türen", kunde=kunde)


def rechnung(projekt, chef, positionen=((Decimal("2.5"), "lfm", Decimal("1234.50")), (6, "Std", Decimal("58")),),
             **werte):
    r = dienst.entwurf_anlegen(projekt=projekt, art=werte.pop("art", Rechnung.Art.RECHNUNG), benutzer=chef, **werte)
    for i, (menge, einheit, preis) in enumerate(positionen, start=1):
        Position.objects.create(rechnung=r, pos=i, text=f"Leistung <{i}> & mehr", menge=menge, einheit=einheit,
                                einzelpreis=preis)
    return r


def xml(r):
    return ET.fromstring(bytes(r.xml))


def finde(baum, pfad):
    return baum.find(pfad, NS)


def text(baum, pfad):
    e = finde(baum, pfad)
    return e.text if e is not None else None


def betrag(baum, pfad):
    return Decimal(text(baum, pfad))


ABR = "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement"
VERK = "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty"
KAEU = "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty"
SUMME = ABR + "/ram:SpecifiedTradeSettlementHeaderMonetarySummation"


def pruefe_regeln(baum):
    """Die Pflichtregeln der XRechnung 3.0 (BR-DE) und die Summenregeln der EN 16931 (BR-CO)."""
    assert text(baum, "rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID") == \
        "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"  # BR-DE-21
    assert text(baum, "rsm:ExchangedDocument/ram:TypeCode") in ("326", "380", "381", "384", "389")  # BR-DE-17
    assert finde(baum, ABR + "/ram:SpecifiedTradeSettlementPaymentMeans") is not None  # BR-DE-1
    assert finde(baum, ABR + "/ram:SpecifiedTradeSettlementPaymentMeans/ram:PayeePartyCreditorFinancialAccount/ram:IBANID") is not None  # BR-DE-23-a
    assert text(baum, "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:BuyerReference").strip()  # BR-DE-15
    for pfad in ["/ram:DefinedTradeContact/ram:PersonName",  # BR-DE-2, -5
                 "/ram:DefinedTradeContact/ram:TelephoneUniversalCommunication/ram:CompleteNumber",  # BR-DE-6
                 "/ram:DefinedTradeContact/ram:EmailURIUniversalCommunication/ram:URIID",  # BR-DE-7
                 "/ram:PostalTradeAddress/ram:CityName", "/ram:PostalTradeAddress/ram:PostcodeCode"]:  # BR-DE-3, -4
        assert (text(baum, VERK + pfad) or "").strip(), pfad
    for pfad in ["/ram:PostalTradeAddress/ram:CityName", "/ram:PostalTradeAddress/ram:PostcodeCode"]:  # BR-DE-8, -9
        assert (text(baum, KAEU + pfad) or "").strip(), pfad
    assert baum.findall(VERK + "/ram:SpecifiedTaxRegistration/ram:ID", NS)  # BR-DE-16 / BR-S-02
    for steuer in baum.iter("{%s}ApplicableTradeTax" % NS["ram"]):
        assert finde(steuer, "ram:RateApplicablePercent") is not None  # BR-DE-14
    beschreibung = text(baum, ABR + "/ram:SpecifiedTradePaymentTerms/ram:Description")
    for zeile in re.split(r"\r?\n", beschreibung):
        if zeile.strip().startswith("#"):
            assert re.search(SKONTO_REGEX, zeile.strip()), zeile  # BR-DE-18
    # EN 16931: Summen (BR-CO-10, -13, -15), Positionspreis nie negativ (BR-27)
    zeilen = baum.findall("rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem", NS)
    assert zeilen  # BR-16
    summe_zeilen = sum(betrag(z, "ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount") for z in zeilen)
    for z in zeilen:
        assert betrag(z, "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount") >= 0
        menge = Decimal(text(z, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity"))
        preis = betrag(z, "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount")
        gesamt = betrag(z, "ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount")
        assert abs(menge * preis - gesamt) <= Decimal("0.01")
    assert betrag(baum, SUMME + "/ram:LineTotalAmount") == summe_zeilen
    assert betrag(baum, SUMME + "/ram:TaxBasisTotalAmount") == summe_zeilen
    assert betrag(baum, SUMME + "/ram:GrandTotalAmount") == \
        betrag(baum, SUMME + "/ram:TaxBasisTotalAmount") + betrag(baum, SUMME + "/ram:TaxTotalAmount")
    assert betrag(baum, ABR + "/ram:ApplicableTradeTax/ram:BasisAmount") == summe_zeilen
    for e in baum.iter():
        if e.tag.endswith("Amount") and e.text:
            assert re.fullmatch(r"-?\d+\.\d{2}", e.text), (e.tag, e.text)  # höchstens 2 Nachkommastellen


# ------------------------------------------------------------------ Inhalt
def test_xrechnung_regelbesteuert_mit_skonto(firma, behoerde, chef):
    r = dienst.festschreiben(rechnung(behoerde, chef, zahlungsziel="14s",
                                      kaeufer_referenz="04011000-1234512345-06"), chef)
    assert r.mit_xrechnung and bytes(r.xml).startswith(b"<?xml")
    baum = xml(r)
    pruefe_regeln(baum)
    assert text(baum, "rsm:ExchangedDocument/ram:ID") == r.nummer
    assert text(baum, "rsm:ExchangedDocument/ram:TypeCode") == "380"
    assert text(baum, "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:BuyerReference") == \
        "04011000-1234512345-06"
    assert text(baum, KAEU + "/ram:Name") == "Gemeinde Musterstadt"
    assert betrag(baum, SUMME + "/ram:GrandTotalAmount") == r.brutto
    assert "#SKONTO#TAGE=7#PROZENT=2.00#" in text(baum, ABR + "/ram:SpecifiedTradePaymentTerms/ram:Description")
    erste = baum.find("rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem", NS)
    assert text(erste, "ram:SpecifiedTradeProduct/ram:Name") == "Leistung <1> & mehr"  # Sonderzeichen sicher
    menge = finde(erste, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity")
    assert (menge.text, menge.get("unitCode")) == ("2.5", "MTR")


def test_xrechnung_kleinunternehmer(firma, behoerde, chef):
    firma.kleinunternehmer = True
    firma.save()
    baum = xml(dienst.festschreiben(rechnung(behoerde, chef), chef))
    pruefe_regeln(baum)
    assert text(baum, ABR + "/ram:ApplicableTradeTax/ram:CategoryCode") == "E"
    assert text(baum, ABR + "/ram:ApplicableTradeTax/ram:ExemptionReason")
    assert "19 UStG" in text(baum, "rsm:ExchangedDocument/ram:IncludedNote/ram:Content")


def test_xrechnung_abschlag_und_schluss_mit_minuspositionen(firma, behoerde, chef):
    a = dienst.festschreiben(dienst.entwurf_anlegen(
        projekt=behoerde, art=Rechnung.Art.ABSCHLAG, benutzer=chef, auftragswert=Decimal("10000"),
        abschlag_prozent=Decimal("30")), chef)
    assert text(xml(a), "rsm:ExchangedDocument/ram:TypeCode") == "326"
    pruefe_regeln(xml(a))
    s = dienst.festschreiben(dienst.entwurf_anlegen(
        projekt=behoerde, art=Rechnung.Art.SCHLUSS, benutzer=chef, auftragswert=Decimal("10000"),
        zahlungsziel="0"), chef)
    baum = xml(s)
    pruefe_regeln(baum)
    zeilen = baum.findall("rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem", NS)
    abzug = zeilen[1]
    assert text(abzug, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity") == "-1"
    assert text(abzug, "ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount") == "-3000.00"
    assert betrag(baum, SUMME + "/ram:TaxBasisTotalAmount") == Decimal("7000.00")


@pytest.mark.parametrize("einheit,code", [("Stk", "C62"), ("pausch.", "C62"), ("lfm", "MTR"), ("m²", "MTK"),
                                          ("qm", "MTK"), ("Std", "HUR"), ("kg", "KGM"), ("Liter", "LTR")])
def test_einheitcodes_wie_excel(einheit, code):
    assert einheitcode(einheit) == code


# ------------------------------------------------------------------ Ablauf
def test_privatkunde_standardmaessig_ohne_xrechnung(firma, chef):
    kunde = Kunde.objects.create(kundennr="K-1", name="Familie Weber", kundenart="Privat",
                                 strasse="Gartenweg 3", plz="67434", ort="Hambach")
    p = Projekt.objects.create(projektnr="P-1", name="Küche", kunde=kunde)
    r = dienst.festschreiben(rechnung(p, chef), chef)
    assert not r.mit_xrechnung and r.xml is None


def test_xrechnung_braucht_telefon_und_email(firma, behoerde, chef):
    firma.telefon = ""
    firma.save()
    r = rechnung(behoerde, chef)
    with pytest.raises(dienst.RechnungFehler, match="Telefon"):
        dienst.festschreiben(r, chef)
    r.mit_xrechnung = False  # ohne E-Rechnung geht es
    r.save()
    assert dienst.festschreiben(r, chef).nummer


def test_xrechnung_braucht_zerlegte_kundenanschrift(firma, chef):
    kunde = Kunde.objects.create(kundennr="K-8", name="Firma Alt", kundenart="Gewerbe",
                                 adresse_original="irgendwo in der Pfalz")
    p = Projekt.objects.create(projektnr="P-8", name="Theke", kunde=kunde)
    with pytest.raises(dienst.RechnungFehler, match="Straße, PLZ und Ort"):
        dienst.festschreiben(rechnung(p, chef), chef)


def test_xml_gehoert_zur_pruefsumme(firma, behoerde, chef):
    from django.db import connection
    r = dienst.festschreiben(rechnung(behoerde, chef), chef)
    assert r.pruefsumme_stimmt()
    with connection.cursor() as c:
        c.execute("UPDATE rechnungen_rechnung SET xml = %s WHERE id = %s", [b"<falsch/>", r.pk])
    assert not Rechnung.objects.get(pk=r.pk).pruefsumme_stimmt()


def test_alte_rechnung_ohne_xml_behaelt_pruefsumme(firma, behoerde, chef):
    r = rechnung(behoerde, chef, mit_xrechnung=False)
    r = dienst.festschreiben(r, chef)
    assert r.xml is None and r.pruefsumme_stimmt()
    assert '"xml"' not in r.inhalt_fuer_pruefsumme()


def test_xml_herunterladen(chef_client, firma, behoerde, chef):
    r = dienst.festschreiben(rechnung(behoerde, chef), chef)
    seite = chef_client.get(reverse("rechnungen:detail", args=[r.pk])).content.decode()
    assert "XRechnung (XML)" in seite
    antwort = chef_client.get(reverse("rechnungen:xml", args=[r.pk]))
    assert antwort.content == bytes(r.xml)
    assert f"{r.nummer}_XRechnung.xml" in antwort["Content-Disposition"]
    assert Protokolleintrag.objects.filter(aktion="rechnung_xml_abgerufen", gegenstand=r.nummer).exists()


def test_ohne_xml_kein_download(chef_client, firma, behoerde, chef):
    r = dienst.festschreiben(rechnung(behoerde, chef, mit_xrechnung=False), chef)
    assert chef_client.get(reverse("rechnungen:xml", args=[r.pk])).status_code == 404


def test_auswahl_im_formular(chef_client, behoerde):
    basis = {"projekt": behoerde.pk, "art": "Rechnung", "zahlungsziel": "14", "leistungszeitraum": "11/2026"}
    chef_client.post(reverse("rechnungen:neu"), {**basis, "mit_xrechnung": "nein"})
    chef_client.post(reverse("rechnungen:neu"), {**basis, "mit_xrechnung": "auto", "kaeufer_referenz": "991-1"})
    ohne, mit = Rechnung.objects.order_by("id")
    assert not ohne.mit_xrechnung and mit.mit_xrechnung and mit.kaeufer_referenz == "991-1"


@pytest.mark.parametrize("iban,gueltig", [("DE02120300000000202051", True), ("DE02 1203 0000 0000 2020 51", True),
                                          ("DE02120300000000202052", False), ("XX", False)])
def test_iban_pruefziffer(iban, gueltig):
    assert iban_gueltig(iban) == gueltig


def test_firmendaten_lehnt_falsche_iban_ab(chef_client):
    antwort = chef_client.post(reverse("rechnungen:firmendaten"), {
        "firmenname": "X", "land": "DE", "zahlungsziel_tage": "14", "ust_satz": "19", "rechnungs_praefix": "RE-",
        "letzte_rechnungsnummer": "0", "mahngebuehr": "5", "iban": "DE02120300000000202052"})
    assert "IBAN ist ungültig" in antwort.content.decode()
