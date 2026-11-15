from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from importe.dienst import ausfuehren
from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from mitarbeiter.models import Mitarbeiter
from moebel import dienst as moebel
from moebel.models import MoebelPosition
from produktion import dienst
from produktion.models import Arbeitsgang, QMPruefung, Route, Vorlage
from projekte.models import Projekt
from tests.test_moebel import UNTERSCHRANK, stamm  # noqa: F401

pytestmark = pytest.mark.django_db
S = Arbeitsgang.Status


@pytest.fixture
def projekt():
    return Projekt.objects.create(projektnr="P-2026-001", name="Küche", status="Auftrag",
                                  kunde=Kunde.objects.create(kundennr="K-1", name="Weber"))


@pytest.fixture
def ma(benutzer_mit_rolle):
    m = Mitarbeiter.objects.create(kuerzel="D.Kaub", name="Dieter Kaub", stundensatz=Decimal("40"))
    m.benutzer = benutzer_mit_rolle(Rolle.MITARBEITER, "dieter")
    m.save()
    return m


def kette(projekt, *std):
    """Drei (o. ä.) Arbeitsgänge hintereinander über die Bibliothek."""
    chef = None
    return [dienst.einzeln(projekt, Vorlage.objects.get(code=c), plan_std=Decimal(s), benutzer=chef)
            for c, s in zip(["PL-010", "KA-010", "MO-010", "LOG-010"], std)]


def alle_fertig(projekt, benutzer):
    for ag in projekt.arbeitsgaenge.order_by("pk"):
        ag.refresh_from_db()
        if ag.status == S.FERTIG:
            continue
        if ag.status == S.GEPLANT:
            dienst.starten(ag, benutzer)
        dienst.rueckmelden(ag, stunden=1, fertig=True, benutzer=benutzer)


# ------------------------------------------------------------------ Grundlagen
def test_werktag():
    fr = date(2026, 11, 20)
    assert dienst.werktag(fr, 0) == fr and dienst.werktag(fr, 1) == date(2026, 11, 23)
    assert dienst.werktag(date(2026, 11, 21), 0) == date(2026, 11, 23)  # Samstag → Montag
    assert dienst.werktag(fr, 5) == date(2026, 11, 27)


def test_startwerte_bibliothek_und_routen():
    assert Vorlage.objects.count() == 28 and Vorlage.objects.get(code="WZ-020").typ == "Prozess-/Wartezeit"
    assert {r.name: r.schritte.count() for r in Route.objects.all()} == {
        "Plattenmöbel Standard": 12, "Massivholz verleimt": 21, "MDF lackiert": 17}


# ------------------------------------------------------------------ aus dem Möbelrechner
def test_arbeitsgaenge_aus_moebel(stamm, projekt, chef):  # noqa: F811
    p = moebel.speichern(projekt=projekt, eingaben=UNTERSCHRANK, benutzer=chef)
    with pytest.raises(dienst.ProduktionsFehler, match="erst"):
        dienst.aus_moebel(p, chef)
    moebel.in_stueckliste(p, chef)
    assert dienst.aus_moebel(p, chef) == 11
    ags = list(p.arbeitsgaenge.order_by("pk"))
    assert [a.code for a in ags] == ["VOR-010", "PL-010", "PL-020", "QM-010", "KA-010", "BE-010", "QM-020", "MO-010",
                                     "MO-020", "QM-040", "LOG-010"]
    assert ags[0].agid == "P-2026-001-M01-AG01" and ags[3].name == "Maße / Winkel prüfen"
    assert ags[1].vorgaenger == ags[0] and ags[0].vorgaenger is None and ags[2].reihenfolge == 30
    assert ags[4].bereich == "Spüle links (M01) - Kanten"
    p.refresh_from_db()
    assert p.status == MoebelPosition.Status.ARBEITSGAENGE
    assert dienst.aus_moebel(p, chef) == 11 and Arbeitsgang.objects.count() == 11  # geplante werden ersetzt
    erster = p.arbeitsgaenge.order_by("pk").first()
    dienst.starten(erster, chef)
    with pytest.raises(dienst.ProduktionsFehler, match="schon begonnen"):
        dienst.aus_moebel(p, chef)


# ------------------------------------------------------------------ Startfreigabe wie Spalte Z
def test_startfreigabe_kette_und_qm(projekt, chef):
    a, b, c = kette(projekt, 2, 2, 2)
    assert a.startfreigabe == "🟢 Start möglich" and b.startfreigabe == "🔒 wartet auf Vorgänger/QM"
    with pytest.raises(dienst.ProduktionsFehler, match="Startfreigabe"):
        dienst.starten(b, chef)
    dienst.starten(a, chef)
    dienst.rueckmelden(a, stunden=Decimal("1.5"), fertig=True, benutzer=chef)
    b.refresh_from_db()
    assert b.startbereit
    # QM-Prüfung zum Vorgänger gesperrt → Nachfolger wartet
    QMPruefung.objects.create(qmid="QM-0099", projekt=projekt, arbeitsgang=a, pruefer="x", datum=date.today(),
                              ergebnis="Nicht bestanden", nacharbeit_noetig=True)
    b = Arbeitsgang.objects.get(pk=b.pk)
    assert b.vorgaenger_qm == "Gesperrt" and not b.startbereit
    a = Arbeitsgang.objects.get(pk=a.pk)
    assert a.startfreigabe == "🔒 Nacharbeit/QM offen"


def test_wartezeit(projekt, chef):
    a = dienst.einzeln(projekt, Vorlage.objects.get(code="OF-020"), benutzer=chef)
    w = dienst.einzeln(projekt, Vorlage.objects.get(code="WZ-020"), benutzer=chef)
    w.wartezeit_std = Decimal("8")
    w.save()
    assert w.startfreigabe == "⚪ Wartezeit unvollständig"
    dienst.starten(a, chef)
    dienst.rueckmelden(a, stunden=1, fertig=True, benutzer=chef)
    w = Arbeitsgang.objects.get(pk=w.pk)
    assert w.startfreigabe.startswith("⏱ Prozess läuft bis")
    Arbeitsgang.objects.filter(pk=a.pk).update(fertig_am=timezone.now() - timedelta(hours=9))
    assert Arbeitsgang.objects.get(pk=w.pk).startfreigabe == "🟢 Wartezeit erfüllt"


# ------------------------------------------------------------------ Planen, Fertigung
def test_einplanen_nach_stunden(projekt, chef, ma):
    a, b, c, d = kette(projekt, 4, 6, 0, 8)
    b.mitarbeiter = Mitarbeiter.objects.create(kuerzel="K.Otto", name="Klaus Otto")
    b.save()
    assert dienst.einplanen(projekt, date(2026, 11, 20), ma, chef) == 4  # Freitag
    a, b, c, d = Arbeitsgang.objects.order_by("pk")
    assert (a.plan_start, a.plan_ende) == (date(2026, 11, 20), date(2026, 11, 20))
    assert (b.plan_start, b.plan_ende) == (date(2026, 11, 20), date(2026, 11, 23))  # 4–10 h → über das Wochenende
    assert (c.plan_start, c.plan_ende) == (date(2026, 11, 23), date(2026, 11, 23))  # 0 h zählt als 1 h
    assert (d.plan_start, d.plan_ende) == (date(2026, 11, 23), date(2026, 11, 24))
    assert a.mitarbeiter == ma and b.mitarbeiter.name == "Klaus Otto"  # nur wo leer
    assert dienst.stand(projekt)["phase"] == 1


def test_rueckmelden(projekt, chef, ma):
    a, = kette(projekt, 4)
    with pytest.raises(dienst.ProduktionsFehler):
        dienst.rueckmelden(a, stunden=1, fertig=False, benutzer=chef)
    dienst.starten(a, ma.benutzer)
    assert a.mitarbeiter == ma and a.begonnen_am is not None
    with pytest.raises(dienst.ProduktionsFehler, match="Stunden"):
        dienst.rueckmelden(a, stunden=0, fertig=False, benutzer=chef)
    dienst.rueckmelden(a, stunden=Decimal("2.5"), fertig=False, benutzer=chef)
    dienst.rueckmelden(a, stunden=Decimal("1"), fertig=True, benutzer=chef)
    assert (a.ist_std, a.status) == (Decimal("3.5"), S.FERTIG) and a.fertig_am
    assert a.lohnkosten_ist == Decimal("140.00")
    assert Protokolleintrag.objects.filter(aktion="arbeitsgang_fertig", gegenstand=a.agid).exists()


def test_entfernen_verbindet_kette(projekt, chef):
    a, b, c = kette(projekt, 1, 1, 1)
    dienst.entfernen(b, chef)
    assert Arbeitsgang.objects.get(pk=c.pk).vorgaenger == a
    dienst.starten(a, chef)
    with pytest.raises(dienst.ProduktionsFehler):
        dienst.entfernen(Arbeitsgang.objects.get(pk=a.pk), chef)


def test_route_uebernehmen(projekt, chef):
    n = dienst.aus_route(projekt, Route.objects.get(name="MDF lackiert"), "Fronten", chef)
    ags = list(projekt.arbeitsgaenge.order_by("pk"))
    assert n == 17 and ags[0].agid == "P-2026-001-AG01" and ags[-1].agid == "P-2026-001-AG17"
    trocknen = [a for a in ags if a.code == "WZ-020"]
    assert [a.wartezeit_std for a in trocknen] == [2, 8] and trocknen[0].typ == "Prozess-/Wartezeit"
    extra = dienst.einzeln(projekt, Vorlage.objects.get(code="MO-020"), benutzer=chef)
    assert extra.agid == "P-2026-001-AG18" and extra.vorgaenger == ags[-1]


# ------------------------------------------------------------------ Phase und QM
def test_phasen_und_endkontrolle_mit_nacharbeit(projekt, chef):
    assert dienst.phase(projekt) == 0
    a, b = kette(projekt, 1, 1)
    with pytest.raises(dienst.ProduktionsFehler, match="nach der Fertigung"):
        dienst.endkontrolle(projekt, bestanden=True, benutzer=chef)
    dienst.starten(a, chef)
    assert dienst.phase(projekt) == 1
    alle_fertig(projekt, chef)
    assert dienst.phase(projekt) == 2
    with pytest.raises(dienst.ProduktionsFehler, match="beschreiben"):
        dienst.endkontrolle(projekt, bestanden=False, abweichung=" ", benutzer=chef)
    q = dienst.endkontrolle(projekt, bestanden=False, abweichung="Tür klemmt", benutzer=chef)
    na = q.nacharbeit_ag
    assert q.qmid == "QM-0001" and q.freigabe == "Gesperrt" and q.arbeitsgang == b
    assert na.agid == "P-2026-001-NA01" and na.name == "Nacharbeit: Tür klemmt" and na.prioritaet == "Hoch"
    assert na.ist_nacharbeit and na.startbereit and dienst.phase(projekt) == 1  # zurück in die Fertigung
    alle_fertig(projekt, chef)
    assert dienst.stand(projekt)["qm"] == 2 and dienst.phase(projekt) == 2  # Nachprüfung nötig
    q2 = dienst.endkontrolle(projekt, bestanden=True, benutzer=chef)
    q.refresh_from_db()
    assert q2.freigabe == "Freigegeben" and q.freigabe == "Freigegeben" and q.nachpruefung == "Bestanden"
    assert dienst.stand(projekt)["qm"] == 1 and dienst.phase(projekt) == 3


# ------------------------------------------------------------------ Seiten
def test_seiten_leitung(projekt, chef_client, ma):
    url = reverse("produktion:projekt", args=[projekt.pk])
    assert chef_client.get(reverse("produktion:uebersicht")).status_code == 200
    chef_client.post(url, {"aktion": "route", "ro-route": Route.objects.get(name="Plattenmöbel Standard").pk,
                           "ro-bauteil": "Korpus"})
    assert projekt.arbeitsgaenge.count() == 12
    chef_client.post(url, {"aktion": "planen", "pl-start": "2026-11-23", "pl-mitarbeiter": ma.pk})
    assert not projekt.arbeitsgaenge.filter(plan_start__isnull=True).exists()
    erster = projekt.arbeitsgaenge.order_by("pk").first()
    chef_client.post(url, {"aktion": "starten", "ag": erster.pk})
    chef_client.post(url, {"aktion": "rueckmelden", "ag": erster.pk, "stunden": "2,5", "fertig": "1"})
    erster.refresh_from_db()
    assert (erster.status, erster.ist_std) == (S.FERTIG, Decimal("2.5"))
    seite = chef_client.get(url).content.decode()
    assert "Material bereitstellen" in seite and "✓ Fertig" in seite and "Einplanen" in seite
    chef_client.post(url, {"aktion": "einzeln", "ei-vorlage": Vorlage.objects.get(code="QM-030").pk, "ei-plan_std": "0,5"})
    assert projekt.arbeitsgaenge.count() == 13
    ag = projekt.arbeitsgaenge.order_by("pk").last()
    antwort = chef_client.post(reverse("produktion:bearbeiten", args=[ag.pk]), {
        "name": "Oberfläche prüfen", "bereich": "", "mitarbeiter": ma.pk, "plan_start": "2026-11-30",
        "plan_ende": "2026-11-30", "plan_std": "0,75", "prioritaet": "Hoch", "wartezeit_std": "0", "problem": "",
        "bemerkung": ""})
    ag.refresh_from_db()
    assert antwort.status_code == 302 and ag.plan_std == Decimal("0.75") and ag.prioritaet == "Hoch"
    chef_client.post(url, {"aktion": "entfernen", "ag": ag.pk})
    assert projekt.arbeitsgaenge.count() == 12


def test_seite_qm(projekt, chef, chef_client):
    kette(projekt, 1)
    alle_fertig(projekt, chef)
    url = reverse("produktion:projekt", args=[projekt.pk])
    antwort = chef_client.post(url, {"aktion": "qm", "qm-ergebnis": "Nicht bestanden", "qm-abweichung": ""})
    assert "Kurz beschreiben" in antwort.content.decode() and not QMPruefung.objects.exists()
    chef_client.post(url, {"aktion": "qm", "qm-ergebnis": "Nicht bestanden", "qm-abweichung": "Kratzer Front"})
    assert projekt.arbeitsgaenge.filter(ist_nacharbeit=True).count() == 1
    assert "Kratzer Front" in chef_client.get(url).content.decode()


def test_mitarbeiter_darf_rueckmelden_aber_nicht_planen(projekt, client, ma, chef):
    a, = kette(projekt, 2)
    a.mitarbeiter = ma
    a.save()
    client.force_login(ma.benutzer)
    url = reverse("produktion:projekt", args=[projekt.pk])
    antwort = client.post(url, {"aktion": "planen", "pl-start": "2026-11-23"}, follow=True)
    assert "Das darf nur Chef" in antwort.content.decode()
    assert client.get(reverse("produktion:bearbeiten", args=[a.pk])).status_code == 403
    meine = client.get(reverse("produktion:meine")).content.decode()
    assert "Plattenzuschnitt" in meine or "Grobzuschnitt" in meine
    client.post(reverse("produktion:meine"), {"aktion": "starten", "ag": a.pk})
    client.post(reverse("produktion:meine"), {"aktion": "rueckmelden", "ag": a.pk, "stunden": "3", "fertig": "1"})
    a.refresh_from_db()
    assert a.status == S.FERTIG and a.ist_std == 3
    assert "Nichts offen" in client.get(reverse("produktion:meine")).content.decode()


def test_meine_ohne_mitarbeiter(chef_client):
    assert "kein Mitarbeiter zugeordnet" in chef_client.get(reverse("produktion:meine")).content.decode()


def test_moebel_knopf_arbeitsgaenge(stamm, projekt, chef, chef_client):  # noqa: F811
    p = moebel.speichern(projekt=projekt, eingaben=UNTERSCHRANK, benutzer=chef)
    assert "Arbeitsgänge übernehmen" not in chef_client.get(p.get_absolute_url()).content.decode()
    moebel.in_stueckliste(p, chef)
    assert "M01" in chef_client.get(reverse("produktion:projekt", args=[projekt.pk])).content.decode()  # Hinweis
    chef_client.post(p.get_absolute_url(), {"aktion": "arbeitsgaenge"})
    assert p.arbeitsgaenge.count() == 11
    assert "→ in der Produktion einplanen" in chef_client.get(p.get_absolute_url()).content.decode()


def test_kachel_und_bibliothek(chef_client):
    assert reverse("produktion:uebersicht") in chef_client.get("/").content.decode()
    seite = chef_client.get(reverse("produktion:bibliothek")).content.decode()
    assert "Abbinden / Aushärten" in seite and "Massivholz verleimt" in seite


# ------------------------------------------------------------------ Import
def _blatt(mappe, name, start, zeilen):
    from openpyxl.utils import column_index_from_string
    ws = mappe.create_sheet(name)
    for _ in range(start - 1):
        ws.append([])
    for z in zeilen:
        reihe = [None] * 40
        for spalte, wert in z.items():
            reihe[column_index_from_string(spalte) - 1] = wert
        ws.append(reihe)


def test_import(tmp_path, projekt):
    Mitarbeiter.objects.create(kuerzel="D.Kaub", name="Dieter Kaub")
    mappe = Workbook()
    mappe.remove(mappe.active)
    _blatt(mappe, "Produktion Arbeitsgangbibliothe", 4, [
        {"A": "AG-CODE", "C": "Arbeitsgang"},
        {"A": "PL-010", "B": "Plattenzuschnitt", "C": "Grobzuschnitt Säge", "D": "👷 Arbeitszeit", "E": 30, "F": "Nein"},
        {"A": "XX-100", "B": "Sonder", "C": "Furnieren", "D": "⚙ Maschinenzeit", "E": 145, "F": "Ja", "G": "Ja"}])
    _blatt(mappe, "Produktion Routenvorlagen", 5, [
        {"A": "Neu|01", "B": "Furnierroute", "C": "Furnier", "D": 1, "E": "XX-100", "F": "Furnieren", "G": "⚙ Maschinenzeit", "H": 2},
        {"B": "Furnierroute", "D": 2, "E": "WZ-020", "F": "Trocknen / Aushärten", "G": "⏱ Prozess-/Wartezeit", "I": 4},
        {"B": "MDF lackiert", "D": 1, "E": "VOR-010", "F": "x"}])
    _blatt(mappe, "Produktion Arbeitsgänge", 6, [
        {"A": "P-2026-001-AG01", "C": "P-2026-001", "D": "Korpus", "E": "Zuschnitt", "F": 10, "G": "D.Kaub",
         "I": date(2026, 11, 2), "J": date(2026, 11, 3), "K": "Fertig", "L": "Mittel", "M": 4, "N": 4.5,
         "R": date(2026, 11, 3), "S": "aus Möbelrechner, PL-010", "AD": "Arbeitszeit"},
        {"A": "P-2026-001-AG02", "C": "P-2026-001", "E": "Kanten", "F": 20, "K": "Geplant", "U": "P-2026-001-AG01"},
        {"A": "P-9-AG01", "C": "P-9", "E": "x"}])
    _blatt(mappe, "Produktion QM", 5, [
        {"A": "QM-0005", "C": "P-2026-001", "D": "Gesamt", "E": "Endkontrolle", "F": "C.Lorenz", "G": date(2026, 11, 4),
         "H": "Nicht bestanden", "I": "Spalt", "J": "Ja", "M": "Gesperrt", "N": "P-2026-001-AG01"}])
    pfad = tmp_path / "pw.xlsx"
    mappe.save(pfad)
    bericht = ausfuehren(pfad, probelauf=False)
    b = {x["blatt"]: x for x in bericht["blaetter"]}
    assert b["Produktion Arbeitsgangbibliothe"]["geaendert"] == 1 and b["Produktion Arbeitsgangbibliothe"]["neu"] == 1
    assert Vorlage.objects.get(code="XX-100").wartezeit_moeglich
    assert Route.objects.get(name="Furnierroute").schritte.count() == 2
    assert Route.objects.get(name="MDF lackiert").schritte.count() == 17  # vorhandene Route bleibt
    assert len(b["Produktion Arbeitsgänge"]["fehler"]) == 1
    a1, a2 = Arbeitsgang.objects.order_by("agid")
    assert a1.mitarbeiter.name == "Dieter Kaub" and a1.ist_std == Decimal("4.5") and a1.code == "PL-010"
    assert a2.vorgaenger == a1 and timezone.localtime(a1.fertig_am).date() == date(2026, 11, 3)
    q = QMPruefung.objects.get()
    assert q.qmid == "QM-0005" and q.arbeitsgang == a1 and q.freigabe == "Gesperrt"
    assert not a2.startbereit  # Vorgänger-QM gesperrt
    ausfuehren(pfad, probelauf=False)
    assert Arbeitsgang.objects.count() == 2 and QMPruefung.objects.count() == 1
