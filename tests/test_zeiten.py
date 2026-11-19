from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from importe.dienst import ausfuehren
from kalkulation.models import Kalkulation
from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from mitarbeiter.models import Mitarbeiter
from planung import dienst as planung
from produktion import dienst as produktion
from produktion.models import Vorlage
from projekte.models import Projekt
from zeiten import dienst
from zeiten.feiertage import arbeitstage, feiertag, ostersonntag
from zeiten.models import Arbeitsvertrag, Monatsabschluss, Zeitbuchung

pytestmark = pytest.mark.django_db
D = Decimal
OKT = date(2026, 10, 5)  # Montag, Monat liegt ganz in der Vergangenheit


@pytest.fixture
def ma():
    return Mitarbeiter.objects.create(kuerzel="D.Kaub", name="Dieter Kaub", stundensatz=D("40"))


@pytest.fixture
def vertrag(ma):
    return Arbeitsvertrag.objects.create(vertragsid="AV-0001", mitarbeiter=ma, eintritt=date(2026, 1, 1),
                                         soll_fr=D("6"), urlaub_jahr=D("30"), zeitkonto_start=D("12.5"),
                                         stundenlohn=D("25"))


@pytest.fixture
def projekt():
    return Projekt.objects.create(projektnr="P-2026-001", name="Küche", status="Auftrag",
                                  kunde=Kunde.objects.create(kundennr="K-1", name="Weber"))


# ------------------------------------------------------------------ Feiertage, Soll
def test_feiertage_rlp():
    assert ostersonntag(2026) == date(2026, 4, 5) and ostersonntag(2027) == date(2027, 3, 28)
    assert feiertag(date(2026, 6, 4)) == "Fronleichnam" and feiertag(date(2026, 11, 1)) == "Allerheiligen"
    assert feiertag(date(2026, 8, 15)) == ""  # Mariä Himmelfahrt nicht in RLP
    assert arbeitstage(date(2026, 12, 21), date(2026, 12, 31)) == 8


def test_soll_tag(ma, vertrag):
    assert dienst.soll_tag(ma, OKT) == 8 and dienst.soll_tag(ma, OKT + timedelta(days=4)) == 6  # Freitag 6 h
    assert dienst.soll_tag(ma, date(2026, 10, 3)) == 0 and dienst.soll_tag(ma, date(2026, 6, 4)) == 0
    vertrag.eintritt = date(2026, 10, 7)
    vertrag.save()
    ma = Mitarbeiter.objects.get(pk=ma.pk)
    assert dienst.soll_tag(ma, OKT) == 0
    ohne = Mitarbeiter.objects.create(kuerzel="T", name="Teilzeit", wochenstunden=D("30"))
    assert dienst.soll_tag(ohne, OKT) == 6
    assert dienst.soll_tag(Mitarbeiter.objects.create(kuerzel="X", name="X"), OKT) == 8


# ------------------------------------------------------------------ Buchen, Storno
def test_buchen_und_storno(ma, vertrag, projekt, chef):
    b = dienst.buchen(mitarbeiter=ma, datum=OKT, beginn=time(7), ende=time(15, 30), pause_min=60, projekt=projekt,
                      benutzer=chef)
    assert b.stunden == D("7.50") and b.satz == D("25") and b.kosten == D("187.50")
    for kwargs, text in [({"stunden": 0}, "Stunden"), ({"stunden": 17}, "16 Stunden"),
                         ({"beginn": time(9), "ende": time(8)}, "nach"),
                         ({"beginn": time(8), "ende": time(9), "pause_min": 60}, "Pause")]:
        with pytest.raises(dienst.ZeitFehler, match=text):
            dienst.buchen(mitarbeiter=ma, datum=OKT, benutzer=chef, **kwargs)
    with pytest.raises(dienst.ZeitFehler, match="Zukunft"):
        dienst.buchen(mitarbeiter=ma, datum=timezone.localdate() + timedelta(days=3), stunden=1, benutzer=chef)
    with pytest.raises(dienst.ZeitFehler, match="Grund"):
        dienst.stornieren(b, " ", chef)
    dienst.stornieren(b, "falscher Tag", chef)
    assert b.storniert_am and Zeitbuchung.objects.count() == 1  # bleibt gespeichert
    assert dienst.monat(ma, 2026, 10)["summe"]["ist"] == 0
    assert Protokolleintrag.objects.filter(aktion="zeit_storniert").exists()


def test_buchen_auf_arbeitsgang(ma, projekt, chef):
    ag = produktion.einzeln(projekt, Vorlage.objects.get(code="PL-010"), benutzer=chef)
    andere = Projekt.objects.create(projektnr="P-2", name="x", kunde=projekt.kunde)
    with pytest.raises(dienst.ZeitFehler, match="anderen Projekt"):
        dienst.buchen(mitarbeiter=ma, datum=OKT, stunden=2, projekt=andere, arbeitsgang=ag, benutzer=chef)
    b = dienst.buchen(mitarbeiter=ma, datum=OKT, stunden=D("2.5"), arbeitsgang=ag, benutzer=chef)
    ag.refresh_from_db()
    assert b.projekt == projekt and ag.ist_std == D("2.5")
    dienst.stornieren(b, "doppelt", chef)
    ag.refresh_from_db()
    assert ag.ist_std == 0


def test_rueckmelden_bucht_zeit(ma, projekt, chef):
    ag = produktion.einzeln(projekt, Vorlage.objects.get(code="MO-010"), mitarbeiter=ma, benutzer=chef)
    produktion.starten(ag, chef)
    produktion.rueckmelden(ag, stunden=D("3"), fertig=True, benutzer=chef)
    ag.refresh_from_db()
    b = Zeitbuchung.objects.get()
    assert (b.mitarbeiter, b.stunden, b.quelle, b.taetigkeit, b.arbeitsgang) == (ma, D("3"), "Produktion", "Montage", ag)
    assert ag.ist_std == 3 and ag.status == "Fertig"


# ------------------------------------------------------------------ Monat, Zeitkonto, Urlaub, Abschluss
def test_monat_zeitkonto_urlaub(ma, vertrag, chef):
    for i in range(5):  # Woche 5.–9.10.: Mo–Do 9 h, Fr 6 h → +4 h
        dienst.buchen(mitarbeiter=ma, datum=OKT + timedelta(days=i), stunden=9 if i < 4 else 6, benutzer=chef)
    planung.abwesenheit_erfassen(mitarbeiter=ma, von=date(2026, 10, 12), bis=date(2026, 10, 16), art="Urlaub",
                                 status="Freigegeben", benutzer=chef)
    planung.abwesenheit_erfassen(mitarbeiter=ma, von=date(2026, 10, 19), bis=date(2026, 10, 19), art="Zeitausgleich",
                                 status="Freigegeben", benutzer=chef)
    m = dienst.monat(ma, 2026, 10)
    tage = [t for t in m["tage"] if t["soll"]]
    assert len(tage) == 22
    soll = sum(t["soll"] for t in tage)
    assert soll == D("166")  # 22 Arbeitstage: 17 × Mo–Do à 8 h + 5 Freitage à 6 h
    assert m["summe"]["gutschrift"] == 8 * 4 + 6  # Urlaub-Woche
    assert m["summe"]["ist"] == 42
    assert m["summe"]["saldo"] == D("42") + 38 - 166
    assert dienst.urlaub(ma, 2026) == {"anspruch": D("30"), "genommen": 5, "beantragt": 0, "rest": D("25")}
    # Zeitkonto: Start 12,5 + Saldo Oktober (Konto beginnt mit der ersten Buchung im Oktober)
    assert dienst.zeitkonto(ma, date(2026, 10, 1)) == D("12.5") + m["summe"]["saldo"]


def test_abschluss_sperrt(ma, vertrag, chef):
    b = dienst.buchen(mitarbeiter=ma, datum=OKT, stunden=8, benutzer=chef)
    heute = timezone.localdate()
    with pytest.raises(dienst.ZeitFehler, match="letzten Tag"):
        dienst.abschliessen(ma, heute.year, heute.month, chef)
    a = dienst.abschliessen(ma, 2026, 10, chef)
    assert a.ist == 8 and a.soll == 166
    with pytest.raises(dienst.ZeitFehler, match="abgeschlossen"):
        dienst.buchen(mitarbeiter=ma, datum=OKT, stunden=1, benutzer=chef)
    with pytest.raises(dienst.ZeitFehler, match="abgeschlossen"):
        dienst.stornieren(b, "x", chef)
    dienst.wieder_oeffnen(a, chef)
    assert not Monatsabschluss.objects.exists()
    assert Protokolleintrag.objects.filter(aktion="zeit_monat_geoeffnet").exists()


# ------------------------------------------------------------------ Lohnkosten in der Nachkalkulation
def test_lohn_ist_und_kalkulation(ma, vertrag, projekt, chef):
    dienst.buchen(mitarbeiter=ma, datum=OKT, stunden=4, projekt=projekt, benutzer=chef)  # 4 × 25 = 100
    vertrag.stundenlohn = D("30")
    vertrag.save()
    ma = Mitarbeiter.objects.get(pk=ma.pk)
    ag = produktion.einzeln(projekt, Vorlage.objects.get(code="PL-010"), mitarbeiter=ma, benutzer=chef)
    ag.ist_std = D("5")  # Altbestand aus der Excel ohne Buchung
    ag.save()
    dienst.buchen(mitarbeiter=ma, datum=OKT, stunden=2, arbeitsgang=ag, benutzer=chef)  # 2 × 30 = 60, ag jetzt 7 h
    assert dienst.lohn_ist(projekt) == D("100") + D("60") + 5 * D("30")
    k = Kalkulation.objects.create(projekt=projekt)
    assert k.ist_kosten == D("310.00")
    assert produktion.stand(projekt)["lohn"] == D("310.00")


# ------------------------------------------------------------------ Seiten
def test_meine_zeiten(client, ma, vertrag, projekt, benutzer_mit_rolle):
    zugang = benutzer_mit_rolle(Rolle.MITARBEITER, "dieter")
    client.force_login(zugang)
    assert "kein Mitarbeiter zugeordnet" in client.get(reverse("zeiten:meine")).content.decode()
    ma.benutzer = zugang
    ma.save()
    assert client.get(reverse("zeiten:start"))["Location"] == reverse("zeiten:meine")
    url = reverse("zeiten:meine")
    seite = client.get(url).content.decode()
    assert "Zeitkonto" in seite and "Urlaub" in seite
    client.post(url, {"datum": "2026-10-05", "stunden": "7,5", "projekt": projekt.pk, "taetigkeit": "Fertigung",
                      "pause_min": "0"})
    client.post(url, {"datum": "2026-10-06", "beginn": "07:00", "ende": "16:00", "pause_min": "45", "taetigkeit": "Montage"})
    assert sorted(Zeitbuchung.objects.values_list("stunden", flat=True)) == [D("7.50"), D("8.25")]
    antwort = client.post(url, {"datum": "2026-10-07", "beginn": "07:00", "taetigkeit": "Fertigung"})
    assert "Von und Bis zusammen" in antwort.content.decode()
    b = Zeitbuchung.objects.first()
    client.post(url, {"aktion": "storno", "buchung": b.pk, "grund": "falsch"})
    assert Zeitbuchung.objects.get(pk=b.pk).storniert_am
    assert client.get(reverse("zeiten:uebersicht")).status_code == 403
    assert client.get(reverse("zeiten:vertraege")).status_code == 403


def test_buero_seiten(chef_client, ma, vertrag, chef):
    dienst.buchen(mitarbeiter=ma, datum=OKT, stunden=8, benutzer=chef)
    assert chef_client.get(reverse("zeiten:start"))["Location"] == reverse("zeiten:uebersicht")
    seite = chef_client.get(reverse("zeiten:uebersicht") + "?monat=2026-10").content.decode()
    assert "Oktober 2026" in seite and "Dieter Kaub" in seite
    url = reverse("zeiten:mitarbeiter", args=[ma.pk]) + "?monat=2026-10"
    chef_client.post(url, {"aktion": "buchen", "datum": "2026-10-06", "stunden": "4", "taetigkeit": "Büro", "pause_min": "0"})
    assert ma.zeitbuchungen.count() == 2
    chef_client.post(url, {"aktion": "abschliessen"})
    assert Monatsabschluss.objects.filter(mitarbeiter=ma).exists()
    assert "abgeschlossen am" in chef_client.get(url).content.decode()
    pdf = chef_client.get(reverse("zeiten:stundenzettel", args=[ma.pk]) + "?monat=2026-10")
    assert pdf.content.startswith(b"%PDF")
    chef_client.post(url, {"aktion": "oeffnen"})
    assert not Monatsabschluss.objects.exists()


def test_vertraege(chef_client, client, ma, benutzer_mit_rolle):
    seite = chef_client.get(reverse("zeiten:vertraege")).content.decode()
    assert "kein Vertrag erfasst" in seite
    daten = {"art": "Befristet", "status": "Aktiv", "eintritt": "2026-03-01", "befristet_bis": "", "probezeit_bis": "",
             "soll_mo": "8", "soll_di": "8", "soll_mi": "8", "soll_do": "8", "soll_fr": "5,5", "urlaub_jahr": "28",
             "zeitkonto_start": "-3,5", "brutto_monat": "3.200,00", "stundenlohn": "19,50", "kuendigungsfrist": "",
             "taetigkeit": "Schreiner", "arbeitsort": "Werkstatt", "vermerk": ""}
    antwort = chef_client.post(reverse("zeiten:vertrag", args=[ma.pk]), daten)
    assert "Enddatum" in antwort.content.decode()
    chef_client.post(reverse("zeiten:vertrag", args=[ma.pk]), {**daten, "befristet_bis": "2026-12-31"})
    v = Arbeitsvertrag.objects.get()
    assert (v.vertragsid, v.soll_woche, v.brutto_monat, v.zeitkonto_start) == ("AV-0001", D("37.5"), D("3200"), D("-3.5"))
    assert "Befristung endet 31.12.2026" in chef_client.get(reverse("zeiten:vertraege")).content.decode()
    eintrag = Protokolleintrag.objects.get(aktion="vertrag_angelegt")
    assert "3200" not in eintrag.details and "brutto_monat (Betrag)" in eintrag.details
    client.force_login(benutzer_mit_rolle(Rolle.BUCHHALTUNG))
    assert client.get(reverse("zeiten:vertraege")).status_code == 200
    assert client.get(reverse("zeiten:vertrag", args=[ma.pk])).status_code == 403
    client.force_login(benutzer_mit_rolle(Rolle.MEISTER))
    assert client.get(reverse("zeiten:vertraege")).status_code == 403
    assert client.get(reverse("zeiten:uebersicht")).status_code == 200


def test_import(tmp_path, ma):
    from openpyxl.utils import column_index_from_string
    mappe = Workbook()
    ws = mappe.active
    ws.title = "Arbeitsvertraege"
    zeilen = {7: {"A": "Vertrags-ID", "B": "Mitarbeiter"},
              8: {"A": "AV-0001", "B": "Administrator", "D": "Unbefristet"},
              9: {"A": "AV-0003", "B": "D.Kaub", "D": "Teilzeit", "E": "Aktiv", "F": date(2025, 4, 1), "J": 6, "K": 6,
                  "L": 6, "M": 6, "N": 0, "O": 24, "P": 7.5, "Q": 1900, "R": 16.5, "T": "Geselle"},
              10: {"A": "AV-0004", "B": "Z.Niemand"}}
    for nr, z in zeilen.items():
        for s, w in z.items():
            ws.cell(row=nr, column=column_index_from_string(s), value=w)
    pfad = tmp_path / "pw.xlsx"
    mappe.save(pfad)
    bericht = ausfuehren(pfad, probelauf=False)
    b = next(x for x in bericht["blaetter"] if x["blatt"] == "Arbeitsvertraege")
    assert b["neu"] == 1 and len(b["fehler"]) == 1
    v = Arbeitsvertrag.objects.get()
    assert (v.art, v.soll_woche, v.soll_fr, v.zeitkonto_start, v.stundenlohn) == ("Teilzeit", 24, 0, D("7.5"), D("16.5"))
    assert dienst.soll_tag(ma, OKT + timedelta(days=4)) == 0
    ausfuehren(pfad, probelauf=False)
    assert Arbeitsvertrag.objects.count() == 1
