import datetime as dt
from decimal import Decimal

import pytest
from django.db import connection
from django.urls import reverse
from openpyxl import Workbook

from importe.dienst import ausfuehren
from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from projekte.models import Projekt
from rechnungen import dienst
from rechnungen.models import Firmendaten, Position, Rechnung, RechnungGesperrt

pytestmark = pytest.mark.django_db
HEUTE = dt.date(2026, 11, 13)


@pytest.fixture(autouse=True)
def ohne_kompression(monkeypatch):
    """PDF-Text unkomprimiert, damit Tests darin suchen können."""
    from reportlab import rl_config
    monkeypatch.setattr(rl_config, "pageCompression", 0)


@pytest.fixture
def firma():
    fd = Firmendaten.laden()
    for feld, wert in dict(firmenname="Schreinerei Lorenz", strasse="Hauptstr. 1", plz="67433", ort="Neustadt",
                           iban="DE02120300000000202051", steuernummer="31/123/45678", bank="Sparkasse").items():
        setattr(fd, feld, wert)
    fd.save()
    return fd


@pytest.fixture
def projekt():
    kunde = Kunde.objects.create(kundennr="K-1", name="Familie Weber", kundenart="Privat",
                                 strasse="Gartenweg 3", plz="67434", ort="Hambach")
    return Projekt.objects.create(projektnr="P-001", name="Einbauküche", kunde=kunde)


def entwurf(projekt, chef, positionen=((Decimal("2"), Decimal("100.00")),), **werte):
    r = dienst.entwurf_anlegen(projekt=projekt, art=werte.pop("art", Rechnung.Art.RECHNUNG), benutzer=chef, **werte)
    for i, (menge, preis) in enumerate(positionen, start=1):
        Position.objects.create(rechnung=r, pos=i, text=f"Leistung {i}", menge=menge, einheit="Stk", einzelpreis=preis)
    return r


# ------------------------------------------------------------------ Nummern und Summen
def test_nummernkreis_wie_excel(firma, projekt, chef):
    r1 = dienst.festschreiben(entwurf(projekt, chef), chef, heute=HEUTE)
    r2 = dienst.festschreiben(entwurf(projekt, chef), chef, heute=HEUTE)
    assert (r1.nummer, r2.nummer) == ("RE-2026-0001", "RE-2026-0002")
    assert Firmendaten.laden().letzte_rechnungsnummer == 2


def test_nummer_setzt_letzte_nummer_aus_firmendaten_fort(firma, projekt, chef):
    firma.letzte_rechnungsnummer = 41
    firma.save()
    assert dienst.naechste_nummer_vorschau().endswith("-0042")
    assert dienst.festschreiben(entwurf(projekt, chef), chef, heute=HEUTE).nummer == "RE-2026-0042"


def test_verworfener_entwurf_verbraucht_keine_nummer(firma, projekt, chef):
    dienst.verwerfen(entwurf(projekt, chef), chef)
    assert dienst.festschreiben(entwurf(projekt, chef), chef, heute=HEUTE).nummer == "RE-2026-0001"
    assert Rechnung.objects.filter(status=Rechnung.Status.VERWORFEN, nummer__isnull=True).count() == 1


def test_summen_kaufmaennisch_gerundet(firma, projekt, chef):
    r = entwurf(projekt, chef, positionen=[(Decimal("3"), Decimal("19.99")), (Decimal("2.5"), Decimal("10.01"))])
    r = dienst.festschreiben(r, chef, heute=HEUTE)
    # 59,97 + 25,03 (25,025 gerundet) = 85,00; USt 16,15; Brutto 101,15
    assert (r.netto, r.ust, r.brutto) == (Decimal("85.00"), Decimal("16.15"), Decimal("101.15"))
    assert r.ust_satz == Decimal("19")


def test_kleinunternehmer_ohne_umsatzsteuer(firma, projekt, chef):
    firma.kleinunternehmer = True
    firma.save()
    r = dienst.festschreiben(entwurf(projekt, chef), chef, heute=HEUTE)
    assert (r.ust, r.brutto) == (Decimal("0.00"), Decimal("200.00"))
    assert b"19 UStG" in bytes(r.pdf)


@pytest.mark.parametrize("ziel,tage,skonto", [("0", 0, 0), ("14", 14, 0), ("30", 30, 0), ("14s", 14, 2)])
def test_zahlungsziel_und_faelligkeit(firma, projekt, chef, ziel, tage, skonto):
    r = dienst.festschreiben(entwurf(projekt, chef, zahlungsziel=ziel), chef, heute=HEUTE)
    assert r.faellig == HEUTE + dt.timedelta(days=tage)
    assert r.skonto_prozent == skonto


# ------------------------------------------------------------------ Festschreiben und Sperre
def test_festschreiben_setzt_alles_und_protokolliert(firma, projekt, chef):
    r = dienst.festschreiben(entwurf(projekt, chef), chef, heute=HEUTE)
    assert r.status == Rechnung.Status.OFFEN and r.ist_festgeschrieben
    assert r.datum == HEUTE and r.firma["firmenname"] == "Schreinerei Lorenz"
    assert r.empfaenger == "Familie Weber\nGartenweg 3\n67434 Hambach"
    assert bytes(r.pdf).startswith(b"%PDF") and b"RE-2026-0001" in bytes(r.pdf)
    assert r.pruefsumme_stimmt()
    eintrag = Protokolleintrag.objects.get(aktion="rechnung_festgeschrieben")
    assert eintrag.gegenstand == "RE-2026-0001" and "Brutto 238,00 €" in eintrag.details


def test_privatkunde_bekommt_aufbewahrungshinweis(firma, projekt, chef):
    r = dienst.festschreiben(entwurf(projekt, chef), chef, heute=HEUTE)
    assert b"14b UStG" in bytes(r.pdf)


def test_festgeschriebene_rechnung_ist_gesperrt(firma, projekt, chef):
    r = dienst.festschreiben(entwurf(projekt, chef), chef, heute=HEUTE)
    r.netto = Decimal("1")
    with pytest.raises(RechnungGesperrt):
        r.save()
    with pytest.raises(RechnungGesperrt):
        r.delete()
    with pytest.raises(RechnungGesperrt):
        Rechnung.objects.filter(pk=r.pk).update(netto=1)
    with pytest.raises(RechnungGesperrt):
        Rechnung.objects.all().delete()
    p = r.positionen.first()
    p.einzelpreis = Decimal("1")
    with pytest.raises(RechnungGesperrt):
        p.save()
    with pytest.raises(RechnungGesperrt):
        p.delete()
    with pytest.raises(RechnungGesperrt):
        Position.objects.create(rechnung=r, pos=9, text="nachträglich", einzelpreis=5)
    with pytest.raises(RechnungGesperrt):
        dienst.festschreiben(r, chef)


def test_manipulation_faellt_ueber_pruefsumme_auf(firma, projekt, chef):
    r = dienst.festschreiben(entwurf(projekt, chef), chef, heute=HEUTE)
    with connection.cursor() as c:  # an der Programmlogik vorbei direkt in der Datenbank ändern
        c.execute("UPDATE rechnungen_position SET einzelpreis = 1 WHERE rechnung_id = %s", [r.pk])
    assert not Rechnung.objects.get(pk=r.pk).pruefsumme_stimmt()


def test_festschreiben_ohne_firmendaten_nicht_moeglich(projekt, chef):
    r = entwurf(projekt, chef)
    with pytest.raises(dienst.RechnungFehler, match="Firmendaten"):
        dienst.festschreiben(r, chef)
    assert Rechnung.objects.get(pk=r.pk).nummer is None


def test_festschreiben_ohne_positionen_nicht_moeglich(firma, projekt, chef):
    with pytest.raises(dienst.RechnungFehler, match="Position"):
        dienst.festschreiben(entwurf(projekt, chef, positionen=[]), chef)
    assert Firmendaten.laden().letzte_rechnungsnummer == 0


def test_festschreiben_ohne_kundenanschrift_nicht_moeglich(firma, chef):
    kunde = Kunde.objects.create(kundennr="K-9", name="Ohne Adresse")
    p = Projekt.objects.create(projektnr="P-9", name="Tisch", kunde=kunde)
    with pytest.raises(dienst.RechnungFehler, match="Anschrift"):
        dienst.festschreiben(entwurf(p, chef), chef)


# ------------------------------------------------------------------ Abschlag und Schluss
def test_abschlag_und_schlussrechnung(firma, projekt, chef):
    a1 = dienst.entwurf_anlegen(projekt=projekt, art=Rechnung.Art.ABSCHLAG, benutzer=chef,
                                auftragswert=Decimal("10000"), abschlag_prozent=Decimal("30"))
    assert a1.positionen.get().einzelpreis == Decimal("3000.00")
    assert "30 % Abschlag" in a1.positionen.get().text
    a1 = dienst.festschreiben(a1, chef, heute=HEUTE)
    a2 = dienst.festschreiben(dienst.entwurf_anlegen(
        projekt=projekt, art=Rechnung.Art.ABSCHLAG, benutzer=chef, auftragswert=Decimal("10000"),
        abschlag_prozent=Decimal("50")), chef, heute=HEUTE)
    assert (a1.abschlag_nr, a2.abschlag_nr) == (1, 2)
    assert a2.titel == "2. Abschlagsrechnung" and b"632a BGB" in bytes(a2.pdf)
    assert dienst.letzter_auftragswert(projekt) == Decimal("10000")

    s = dienst.entwurf_anlegen(projekt=projekt, art=Rechnung.Art.SCHLUSS, benutzer=chef, auftragswert=Decimal("10000"))
    texte = list(s.positionen.values_list("text", flat=True))
    assert len(texte) == 3 and a1.nummer in texte[1] and a2.nummer in texte[2]
    s = dienst.festschreiben(s, chef, heute=HEUTE)
    assert s.netto == Decimal("2000.00") and s.titel == "Schlussrechnung"


def test_abschlag_ohne_auftragswert_abgelehnt(projekt, chef):
    with pytest.raises(dienst.RechnungFehler):
        dienst.entwurf_anlegen(projekt=projekt, art=Rechnung.Art.ABSCHLAG, benutzer=chef)


# ------------------------------------------------------------------ Oberfläche
def test_neue_rechnung_ueber_formular(chef_client, projekt):
    antwort = chef_client.post(reverse("rechnungen:neu"), {
        "projekt": projekt.pk, "art": "Abschlag", "abschlag_prozent": "50", "auftragswert": "12.500,00",
        "leistungszeitraum": "11/2026", "zahlungsziel": "30"}, follow=True)
    assert "Entwurf angelegt" in antwort.content.decode()
    r = Rechnung.objects.get()
    assert r.kunde == projekt.kunde and r.positionen.get().einzelpreis == Decimal("6250.00")
    assert Protokolleintrag.objects.filter(aktion="rechnung_entwurf").exists()


def test_neue_rechnung_vom_projekt_aus(chef_client, projekt):
    inhalt = chef_client.get(reverse("projekte:detail", args=[projekt.pk])).content.decode()
    assert "+ Rechnung für dieses Projekt" in inhalt
    inhalt = chef_client.get(reverse("rechnungen:neu"), {"projekt": projekt.pk}).content.decode()
    assert f'value="{projekt.pk}" selected' in inhalt


def test_positionen_mit_komma_bearbeiten(chef_client, projekt, chef):
    r = entwurf(projekt, chef, positionen=[])
    daten = {"leistungszeitraum": "10/2026", "zahlungsziel": "14",
             "pos-TOTAL_FORMS": "3", "pos-INITIAL_FORMS": "0", "pos-MIN_NUM_FORMS": "0", "pos-MAX_NUM_FORMS": "25",
             "pos-0-text": "Arbeitsplatte Eiche", "pos-0-menge": "2,5", "pos-0-einheit": "lfm",
             "pos-0-einzelpreis": "1.234,50",
             "pos-1-text": "", "pos-1-menge": "1", "pos-1-einheit": "Stk", "pos-1-einzelpreis": "",
             "pos-2-text": "", "pos-2-menge": "1", "pos-2-einheit": "Stk", "pos-2-einzelpreis": ""}
    antwort = chef_client.post(reverse("rechnungen:bearbeiten", args=[r.pk]), daten)
    assert antwort.status_code == 302
    p = r.positionen.get()
    assert (p.pos, p.menge, p.einzelpreis, p.gesamt) == (1, Decimal("2.5"), Decimal("1234.50"), Decimal("3086.25"))


def test_festschreiben_ueber_knopf_braucht_haken(chef_client, firma, projekt, chef):
    r = entwurf(projekt, chef)
    seite = chef_client.get(reverse("rechnungen:detail", args=[r.pk])).content.decode()
    assert "RE-2026-0001" in seite and "Rechnung festschreiben" in seite
    chef_client.post(reverse("rechnungen:festschreiben", args=[r.pk]))
    assert Rechnung.objects.get(pk=r.pk).nummer is None
    antwort = chef_client.post(reverse("rechnungen:festschreiben", args=[r.pk]), {"bestaetigt": "1"}, follow=True)
    inhalt = antwort.content.decode()
    assert "ist festgeschrieben" in inhalt and "Prüfsumme in Ordnung" in inhalt


def test_festgeschriebene_rechnung_nicht_bearbeitbar_ueber_seite(chef_client, firma, projekt, chef):
    r = dienst.festschreiben(entwurf(projekt, chef), chef)
    antwort = chef_client.post(reverse("rechnungen:bearbeiten", args=[r.pk]),
                               {"leistungszeitraum": "geändert", "zahlungsziel": "0"}, follow=True)
    assert "kann nicht mehr geändert werden" in antwort.content.decode()
    assert Rechnung.objects.get(pk=r.pk).leistungszeitraum != "geändert"


def test_pdf_abrufen(chef_client, firma, projekt, chef):
    r = entwurf(projekt, chef)
    vorschau = chef_client.get(reverse("rechnungen:pdf", args=[r.pk]))
    assert vorschau["Content-Type"] == "application/pdf" and b"ENTWURF" in vorschau.content
    r = dienst.festschreiben(r, chef)
    antwort = chef_client.get(reverse("rechnungen:pdf", args=[r.pk]), {"laden": "1"})
    assert antwort.content == bytes(r.pdf)
    assert "attachment" in antwort["Content-Disposition"] and "RE-2026-0001.pdf" in antwort["Content-Disposition"]


def test_liste_und_suche(chef_client, firma, projekt, chef):
    dienst.festschreiben(entwurf(projekt, chef), chef)
    dienst.verwerfen(entwurf(projekt, chef), chef)
    inhalt = chef_client.get(reverse("rechnungen:liste")).content.decode()
    assert "RE-2026-0001" in inhalt and "1 Rechnung." in inhalt
    assert "Familie Weber" in chef_client.get(reverse("rechnungen:liste"), {"suche": "weber"}).content.decode()
    assert "Keine Rechnung passt" in chef_client.get(reverse("rechnungen:liste"), {"suche": "xyz"}).content.decode()


@pytest.mark.parametrize("rolle,erlaubt", [(Rolle.CHEF, True), (Rolle.ADMIN, True), (Rolle.BUCHHALTUNG, True),
                                           (Rolle.MEISTER, False), (Rolle.MITARBEITER, False)])
def test_rechte(client, benutzer_mit_rolle, projekt, rolle, erlaubt):
    client.force_login(benutzer_mit_rolle(rolle))
    for url in [reverse("rechnungen:liste"), reverse("rechnungen:neu"), reverse("rechnungen:firmendaten")]:
        assert (client.get(url).status_code == 200) == erlaubt
    projektseite = client.get(reverse("projekte:detail", args=[projekt.pk])).content.decode()
    assert ("Rechnungen zu diesem Projekt" in projektseite) == erlaubt


# ------------------------------------------------------------------ Firmendaten
def test_firmendaten_speichern_mit_protokoll(chef_client):
    daten = {"firmenname": "Schreinerei Lorenz", "land": "DE", "zahlungsziel_tage": "14", "ust_satz": "19",
             "rechnungs_praefix": "RE-", "letzte_rechnungsnummer": "5", "mahngebuehr": "5,00",
             "iban": "de02 1203 0000 0000 2020 51", "fusstext": "Danke"}
    antwort = chef_client.post(reverse("rechnungen:firmendaten"), daten, follow=True)
    assert "Firmendaten gespeichert" in antwort.content.decode()
    fd = Firmendaten.laden()
    assert fd.iban == "DE02120300000000202051" and fd.letzte_rechnungsnummer == 5
    assert Protokolleintrag.objects.filter(aktion="firmendaten_geaendert").exists()
    daten["letzte_rechnungsnummer"] = "3"
    antwort = chef_client.post(reverse("rechnungen:firmendaten"), daten)
    assert "darf nicht kleiner werden" in antwort.content.decode()
    assert Firmendaten.laden().letzte_rechnungsnummer == 5


def test_alte_rechnung_behaelt_alte_firmendaten(firma, projekt, chef):
    r = dienst.festschreiben(entwurf(projekt, chef), chef)
    firma.firmenname = "Neuer Name GmbH"
    firma.save()
    r = Rechnung.objects.get(pk=r.pk)
    assert r.firma["firmenname"] == "Schreinerei Lorenz" and r.pruefsumme_stimmt()


def _firmendaten_excel(pfad, zeilen):
    mappe = Workbook()
    blatt = mappe.active
    blatt.title = "Firmendaten"
    blatt["A1"] = "PFALZ-WERK · FIRMENDATEN FÜR RECHNUNGEN"
    blatt.append([])
    blatt.append(["Feld", "Wert", "Hinweis"])
    for z in zeilen:
        blatt.append(z)
    mappe.save(pfad)
    return pfad


def test_import_firmendaten(tmp_path):
    fd = Firmendaten.laden()
    fd.telefon = "06321 999"  # schon im Programm gepflegt
    fd.save()
    pfad = _firmendaten_excel(tmp_path / "pw.xlsx", [
        ["Firmenname", "Schreinerei Lorenz"], ["Straße und Hausnummer", "Hauptstr. 1"], ["PLZ", 67433],
        ["Telefon", "0000"], ["IBAN", "DE02 1203 0000 0000 2020 51"], ["Kleinunternehmer (Ja/Nein)", "Nein"],
        ["USt-Satz %", 19], ["Rechnungs-Präfix", "AR-"], ["Letzte Rechnungsnummer", 12],
        ["Mahngebühr 2. Mahnung €", "7,50"], ["Logo", "logo.png"], ["Fußtext Rechnung", ""]])
    bericht = ausfuehren(pfad, probelauf=False)
    eintrag = next(b for b in bericht["blaetter"] if b["blatt"] == "Firmendaten")
    assert not eintrag["fehler"] and "Logo" in eintrag["zusatz"]
    fd = Firmendaten.laden()
    assert (fd.firmenname, fd.plz, fd.iban, fd.rechnungs_praefix) == (
        "Schreinerei Lorenz", "67433", "DE02120300000000202051", "AR-")
    assert fd.telefon == "06321 999"  # nicht überschrieben
    assert fd.letzte_rechnungsnummer == 12 and fd.mahngebuehr == Decimal("7.50")
    # Zweiter Import ändert nichts mehr; die Nummer wird nie verkleinert
    fd.letzte_rechnungsnummer = 20
    fd.save()
    ausfuehren(pfad, probelauf=False)
    assert Firmendaten.laden().letzte_rechnungsnummer == 20
