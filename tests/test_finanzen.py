import datetime as dt
import io
import zipfile
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from lieferanten.models import Lieferant
from projekte.models import Projekt
from rechnungen import dienst, finanzen
from rechnungen import eingang_dienst as ed
from rechnungen.models import Firmendaten, Position, Rechnung

pytestmark = pytest.mark.django_db
OKT = dt.date(2026, 10, 15)
HEUTE = timezone.localdate()


@pytest.fixture
def firma():
    fd = Firmendaten.laden()
    for feld, wert in dict(firmenname="Schreinerei Lorenz", strasse="Hauptstr. 1", plz="67433", ort="Neustadt",
                           iban="DE02120300000000202051", steuernummer="31/123/45678",
                           datev_berater="1234567", datev_mandant="54321").items():
        setattr(fd, feld, wert)
    fd.save()
    return fd


@pytest.fixture
def projekt():
    kunde = Kunde.objects.create(kundennr="K-007", name="Bäckerei Müller", kundenart="Gewerbe",
                                 strasse="Weg 1", plz="67434", ort="Hambach")
    return Projekt.objects.create(projektnr="P-001", name="Theke", kunde=kunde)


def rechnung(projekt, chef, preis="1000", heute=OKT, ziel="14s"):
    r = dienst.entwurf_anlegen(projekt=projekt, art=Rechnung.Art.RECHNUNG, benutzer=chef, zahlungsziel=ziel,
                               mit_xrechnung=False)
    Position.objects.create(rechnung=r, pos=1, text="Theke", menge=1, einheit="Stk", einzelpreis=Decimal(preis))
    return dienst.festschreiben(r, chef, heute=heute)


def beleg(chef, projekt=None, **werte):
    daten = dict(lieferant_name="Holz Wickert", lieferanten_nr="R-1", datum=OKT, kategorie="Material / Wareneingang",
                 projekt=projekt, netto=Decimal("500"), ust_satz=Decimal("19"), ziel_tage=14, skonto_prozent=None,
                 skonto_tage=None, benutzer=chef)
    daten.update(werte)
    return ed.erfassen(**daten)


# ------------------------------------------------------------------ Konten
def test_personenkonten_wie_excel():
    assert finanzen.debitor("K-007") == "10007" and finanzen.debitor("41") == "10041" and finanzen.debitor("X") == "10000"
    l = Lieferant.objects.create(name="A")
    assert finanzen.kreditor(l) == str(70000 + l.pk)


@pytest.mark.parametrize("kategorie,satz,konto,bu", [
    ("Material / Wareneingang", 19, "3400", ""), ("Material / Wareneingang", 7, "3300", ""),
    ("Material / Wareneingang", 0, "3200", ""), ("Fremdleistung", 19, "3100", "9"), ("Fahrzeug", 19, "4530", "9"),
    ("Maschinen / Werkzeug", 7, "4985", "8"), ("Büro / Verwaltung", 19, "4930", "9"), ("Sonstiges", 0, "4900", "")])
def test_sachkonten_skr03(kategorie, satz, konto, bu):
    assert finanzen.sachkonto(kategorie, Decimal(satz)) == (konto, bu)


def test_buchungszeile_wie_excel():
    zeile = finanzen.buchungszeile(Decimal("1190"), "S", "10007", "8400", OKT, "RE-2026-0001", 'Rechnung "Müller"')
    assert zeile == '1190,00;"S";"EUR";;;;10007;8400;;1510;"RE-2026-0001";;;"Rechnung Müller"'
    gedreht = finanzen.buchungszeile(Decimal("-50"), "S", "1200", "10007", OKT, "X", "Storno", bu="9")
    assert gedreht.startswith('50,00;"H"') and ';"9";' in gedreht


def test_wirtschaftsjahr(firma):
    assert finanzen.wj_beginn(firma, dt.date(2026, 10, 1)) == dt.date(2026, 1, 1)
    firma.wj_beginn = "01.07."
    assert finanzen.wj_beginn(firma, dt.date(2026, 3, 1)) == dt.date(2025, 7, 1)


# ------------------------------------------------------------------ Buchungen
def test_buchungen_des_monats(firma, projekt, chef):
    r = rechnung(projekt, chef)
    dienst.zahlung_buchen(r, art=dienst.SKONTO, datum=OKT + dt.timedelta(days=2), benutzer=chef)
    e = beleg(chef, kategorie="Fremdleistung")
    ed.bezahlen(e, art=ed.TEIL, betrag=Decimal("100"), datum=OKT, benutzer=chef, konto="Bar")
    liste, warnungen = finanzen.buchungen(2026, 10)
    arten = {b["art"]: b for b in liste}
    assert set(arten) == {"Rechnung", "Eingangsrechnung", "Zahlung Ein", "Skonto Ein", "Zahlung Aus"}
    assert (arten["Rechnung"]["konto"], arten["Rechnung"]["gegen"], arten["Rechnung"]["sh"],
            arten["Rechnung"]["betrag"]) == ("10007", "8400", "S", Decimal("1190.00"))
    assert (arten["Skonto Ein"]["konto"], arten["Skonto Ein"]["betrag"]) == ("8736", Decimal("23.80"))
    kreditor = finanzen.kreditor(e.lieferant)
    assert (arten["Eingangsrechnung"]["konto"], arten["Eingangsrechnung"]["gegen"], arten["Eingangsrechnung"]["bu"],
            arten["Eingangsrechnung"]["sh"]) == (kreditor, "3100", "9", "H")
    assert (arten["Zahlung Aus"]["konto"], arten["Zahlung Aus"]["gegen"]) == ("1000", kreditor)  # bar → Kasse
    assert arten["Zahlung Aus"]["beleg"] == "R-1" == arten["Eingangsrechnung"]["beleg"]  # gleiches Belegfeld für OP
    assert not warnungen
    assert finanzen.buchungen(2026, 9)[0] == []


def test_storno_und_kleinunternehmer(firma, projekt, chef):
    alt = rechnung(projekt, chef, ziel="14")
    storno = dienst.stornieren(alt, chef)
    liste = finanzen.buchungen(storno.datum.year, storno.datum.month)[0]
    s = next(b for b in liste if b["beleg"] == storno.nummer)
    assert s["betrag"] == Decimal("-1190.00")
    assert finanzen.buchungszeile(s["betrag"], s["sh"], s["konto"], s["gegen"], s["datum"], s["beleg"], "").startswith('1190,00;"H"')
    firma.kleinunternehmer = True
    firma.save()
    klein = rechnung(projekt, chef, ziel="14")
    assert finanzen.erloeskonto(klein) == "8195"


def test_stornierte_eingangsrechnung_wird_gegengebucht(firma, chef):
    e = beleg(chef)
    ed.erfassung_stornieren(e, benutzer=chef, grund="vertippt")
    okt = finanzen.buchungen(2026, 10)[0]
    assert [b["art"] for b in okt] == ["Eingangsrechnung"]
    jetzt = finanzen.buchungen(HEUTE.year, HEUTE.month)[0]
    gegen = [b for b in jetzt if b["art"] == "Storno Eingang"]
    assert len(gegen) == 1 and gegen[0]["betrag"] == Decimal("-595.00")


def test_doppelte_debitoren_werden_gemeldet(firma):
    Kunde.objects.create(kundennr="K-7", name="A")
    Kunde.objects.create(kundennr="7", name="B")
    assert "10007" in finanzen.buchungen(2026, 10)[1][0]


# ------------------------------------------------------------------ Datei
def test_datev_zip(firma, projekt, chef):
    r = rechnung(projekt, chef)
    beleg(chef)
    from django.core.files.uploadedfile import SimpleUploadedFile
    beleg(chef, lieferanten_nr="R-2", beleg=SimpleUploadedFile("scan.pdf", b"%PDF-1.4"))
    inhalt, info = finanzen.datev_zip(2026, 10)
    assert info == {"buchungen": 3, "belege": 2, "warnungen": []}
    z = zipfile.ZipFile(io.BytesIO(inhalt))
    namen = set(z.namelist())
    assert {"EXTF_Buchungsstapel_2026-10.csv", "Personenkonten.csv", f"Belege/{r.nummer}.pdf", "Belege/ER-0002_scan.pdf"} <= namen
    csv = z.read("EXTF_Buchungsstapel_2026-10.csv").decode("cp1252")
    zeilen = csv.split("\r\n")
    assert zeilen[0].startswith('"EXTF";700;21;"Buchungsstapel";13;')
    assert ";1234567;54321;20260101;4;20261001;20261031;" in zeilen[0]
    assert zeilen[1].startswith("Umsatz (ohne Soll/Haben-Kz);Soll/Haben-Kennzeichen")
    assert "Bäckerei Müller" in csv  # Umlaute im Windows-Zeichensatz
    assert len([z for z in zeilen if z]) == 2 + 3
    konten = z.read("Personenkonten.csv").decode("cp1252")
    assert "10007;Bäckerei Müller" in konten and "Holz Wickert" in konten
    op = z.read(next(n for n in namen if n.startswith("Offene_Posten"))).decode("cp1252")
    assert "Forderung;" + r.nummer in op and "Verbindlichkeit;ER-0001" in op


def test_ohne_beraternummer_kein_export(firma):
    firma.datev_berater = ""
    firma.save()
    with pytest.raises(ValueError, match="Berater"):
        finanzen.datev_zip(2026, 10)


# ------------------------------------------------------------------ Übersicht
def test_uebersicht(firma, projekt, chef):
    heute = dt.date(2026, 11, 20)
    rechnung(projekt, chef)                                       # Okt: 1000 netto, 190 USt, fällig 29.10.
    beleg(chef, projekt=projekt, netto=Decimal("300"))            # Okt: 57 Vorsteuer
    u = finanzen.uebersicht(heute)
    assert u["umsatz_jahr"] == Decimal("1000.00")
    assert (u["ust"], u["vorsteuer"], u["zahllast"]) == (Decimal("190.00"), Decimal("57.00"), Decimal("133.00"))
    assert u["forderungen_summe"] == Decimal("1190.00") and u["verbindlichkeiten_summe"] == Decimal("357.00")
    assert u["wochen"][0]["ein"] == Decimal("1190.00")  # überfällig → Woche 1
    assert u["wochen"][0]["start"] == dt.date(2026, 11, 16) and u["wochen"][-1]["kumuliert"] == Decimal("833.00")
    p = u["projekte"][0]
    assert (p["erloes"], p["kosten"], p["db"]) == (Decimal("1000.00"), Decimal("300.00"), Decimal("700.00"))


# ------------------------------------------------------------------ Seiten
def test_seiten_und_download(chef_client, firma, projekt, chef):
    rechnung(projekt, chef)
    seite = chef_client.get(reverse("finanzen:uebersicht")).content.decode()
    assert "Finanz-Übersicht" in seite and "Liquidität" in seite and "Deckungsbeitrag" in seite
    datev = chef_client.get(reverse("finanzen:datev"), {"monat": "2026-10"}).content.decode()
    assert "1 Buchung im Oktober 2026" in datev and "10007" in datev
    antwort = chef_client.get(reverse("finanzen:datev"), {"monat": "2026-10", "laden": "1"})
    assert antwort["Content-Type"] == "application/zip" and "DATEV_2026-10.zip" in antwort["Content-Disposition"]
    assert Protokolleintrag.objects.filter(aktion="datev_export", gegenstand="2026-10").exists()


def test_hinweis_ohne_beraternummer(chef_client):
    inhalt = chef_client.get(reverse("finanzen:datev")).content.decode()
    assert "fehlen noch die" in inhalt and "herunterladen (ZIP)" not in inhalt


def test_firmendaten_import_datev(tmp_path):
    from importe.dienst import ausfuehren
    from tests.test_rechnungen import _firmendaten_excel
    pfad = _firmendaten_excel(tmp_path / "pw.xlsx", [["DATEV Beraternummer", 1234567], ["DATEV Mandantennummer", 12],
                                                     ["Wirtschaftsjahr-Beginn (TT.MM.)", "01.01."], ["Sachkontenlänge", 4]])
    bericht = ausfuehren(pfad, probelauf=False)
    eintrag = next(b for b in bericht["blaetter"] if b["blatt"] == "Firmendaten")
    assert not eintrag["fehler"] and not eintrag.get("zusatz")
    fd = Firmendaten.laden()
    assert (fd.datev_berater, fd.datev_mandant) == ("1234567", "12")


@pytest.mark.parametrize("rolle,erlaubt", [(Rolle.ADMIN, True), (Rolle.BUCHHALTUNG, True), (Rolle.MEISTER, False),
                                           (Rolle.MITARBEITER, False)])
def test_rechte(client, benutzer_mit_rolle, rolle, erlaubt):
    client.force_login(benutzer_mit_rolle(rolle))
    for url in (reverse("finanzen:uebersicht"), reverse("finanzen:datev")):
        assert (client.get(url).status_code == 200) == erlaubt


def test_vorschau_zeigt_wie_datei(firma, projekt, chef):
    alt = rechnung(projekt, chef, ziel="14")
    storno = dienst.stornieren(alt, chef)
    b = next(x for x in finanzen.buchungen(storno.datum.year, storno.datum.month)[0] if x["beleg"] == storno.nummer)
    assert (b["datei_betrag"], b["datei_sh"]) == (Decimal("1190.00"), "H")
