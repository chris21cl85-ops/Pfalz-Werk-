from datetime import date, time, timedelta

import pytest
from django.urls import reverse
from openpyxl import Workbook

from importe.dienst import ausfuehren
from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from mitarbeiter.models import Mitarbeiter
from planung import dienst
from planung.models import Abwesenheit, Montage, Team, TeamMitglied, Termin
from produktion import dienst as produktion
from produktion.models import Vorlage
from projekte.models import Projekt

pytestmark = pytest.mark.django_db
MO = date(2026, 11, 16)  # Montag, KW 47


@pytest.fixture
def leute():
    return [Mitarbeiter.objects.create(kuerzel=k, name=n) for k, n in
            (("D.Kaub", "Dieter Kaub"), ("K.Otto", "Klaus Otto"), ("S.Bach", "Sven Bach"))]


@pytest.fixture
def team(leute, chef):
    t = dienst.team_anlegen(name="Montage 1", art="Montage", benutzer=chef)
    dienst.mitglied_umschalten(t, leute[0], chef)
    dienst.mitglied_umschalten(t, leute[1], chef)
    return t


def projekt_bereit(nr="P-2026-001", chef=None):
    """Projekt mit einem fertigen Arbeitsgang und bestandener Endkontrolle → Phase Montage."""
    kunde = Kunde.objects.get_or_create(kundennr="K-1", defaults={"name": "Weber", "strasse": "Hauptstr. 5",
                                                                  "plz": "67433", "ort": "Neustadt"})[0]
    p = Projekt.objects.create(projektnr=nr, name=f"Küche {nr[-1]}", status="Auftrag", kunde=kunde)
    ag = produktion.einzeln(p, Vorlage.objects.get(code="MO-010"), benutzer=chef)
    produktion.starten(ag, chef)
    produktion.rueckmelden(ag, stunden=2, fertig=True, benutzer=chef)
    produktion.endkontrolle(p, bestanden=True, benutzer=chef)
    assert produktion.phase(p) == 3
    return p


# ------------------------------------------------------------------ Teams
def test_team_und_mitglieder(team, leute, chef):
    assert team.teamid == "TEAM-0001" and [m.name for m in team.mitglieder()] == ["Dieter Kaub", "Klaus Otto"]
    assert TeamMitglied.objects.get(mitarbeiter=leute[0]).leitung
    assert not TeamMitglied.objects.get(mitarbeiter=leute[1]).leitung
    assert dienst.mitglied_umschalten(team, leute[0], chef) is False  # raus
    assert [m.name for m in team.mitglieder()] == ["Klaus Otto"]
    assert dienst.mitglied_umschalten(team, leute[0], chef) is True
    with pytest.raises(dienst.PlanungsFehler, match="gibt es schon"):
        dienst.team_anlegen(name="montage 1", art="Montage", benutzer=chef)


# ------------------------------------------------------------------ Abwesenheit
def test_abwesend(leute, chef):
    a = dienst.abwesenheit_erfassen(mitarbeiter=leute[0], von=MO, bis=MO + timedelta(days=2), art="Urlaub",
                                    status="Beantragt", benutzer=chef)
    assert a.zid == "ZD-0001" and a.tage == 3
    assert dienst.abwesend(leute[0], MO + timedelta(days=1)) == "Urlaub (beantragt)"
    assert dienst.abwesend(leute[0], MO + timedelta(days=3)) == ""
    dienst.abwesenheit_status(a, "Freigegeben", chef)
    assert dienst.abwesend(leute[0], MO) == "Urlaub"
    dienst.abwesenheit_status(a, "Abgelehnt", chef)
    assert dienst.abwesend(leute[0], MO) == ""
    with pytest.raises(dienst.PlanungsFehler):
        dienst.abwesenheit_erfassen(mitarbeiter=leute[0], von=MO, bis=MO - timedelta(days=1), art="Urlaub",
                                    status="Freigegeben", benutzer=chef)


# ------------------------------------------------------------------ Montage
def test_montage_planen_termine_und_fertig(team, leute, chef):
    p = projekt_bereit(chef=chef)
    m = dienst.montage_speichern(p, datum=MO, beginn=time(7), ende=time(16), team=team, fahrzeug="Transporter",
                                 adresse="Hauptstr. 5, 67433 Neustadt", benutzer=chef)
    termine = Termin.objects.filter(projekt=p, aus_montage=True)
    assert m.ergebnis == "" and termine.count() == 2 and {t.mitarbeiter for t in termine} == set(leute[:2])
    # Neu planen: alte Montage-Termine weg, neue für aktuelles Team
    dienst.mitglied_umschalten(team, leute[2], chef)
    dienst.montage_speichern(p, datum=MO + timedelta(days=1), beginn=time(8), ende=time(12), team=team, benutzer=chef)
    assert Termin.objects.filter(projekt=p, aus_montage=True).count() == 3 and Montage.objects.count() == 1
    assert not Termin.objects.filter(projekt=p, datum=MO).exists()
    dienst.montage_ergebnis(p, "Nacharbeit erforderlich", chef)
    assert produktion.phase(p) == 3
    dienst.montage_ergebnis(p, "Bestanden", chef)
    assert produktion.phase(p) == 4 and produktion.SCHRITTE[4] == "Fertig"
    assert Protokolleintrag.objects.filter(aktion="montage_umgeplant").exists()


def test_montage_pruefungen(team, leute, chef):
    p = projekt_bereit(chef=chef)
    with pytest.raises(dienst.PlanungsFehler, match="Ende"):
        dienst.montage_pruefen(p, datum=MO, beginn=time(10), ende=time(9), team=team, fahrzeug="")
    leer = dienst.team_anlegen(name="Leer", art="Montage", benutzer=chef)
    with pytest.raises(dienst.PlanungsFehler, match="keine Mitglieder"):
        dienst.montage_pruefen(p, datum=MO, beginn=time(7), ende=time(9), team=leer, fahrzeug="")
    dienst.abwesenheit_erfassen(mitarbeiter=leute[1], von=MO, bis=MO, art="Krank", status="Freigegeben", benutzer=chef)
    p2 = projekt_bereit("P-2026-002", chef=chef)
    dienst.montage_speichern(p2, datum=MO, beginn=time(7), ende=time(16), team=team, fahrzeug="PKW", benutzer=chef)
    warn = dienst.montage_pruefen(p, datum=MO, beginn=time(7), ende=time(16), team=team, fahrzeug="PKW")
    assert "Abwesend: Klaus Otto (Krank)" in warn
    assert "Montage 1 ist schon bei P-2026-002." in warn and "PKW ist schon vergeben (P-2026-002)." in warn
    nicht_bereit = Projekt.objects.create(projektnr="P-3", name="x", kunde=p.kunde)
    with pytest.raises(dienst.PlanungsFehler, match="QM"):
        dienst.montage_speichern(nicht_bereit, datum=MO, beginn=time(7), ende=time(9), team=team, benutzer=chef)


# ------------------------------------------------------------------ Kalender
def test_kalender_sammelt_alles(team, leute, chef):
    p = projekt_bereit(chef=chef)
    dienst.montage_speichern(p, datum=MO + timedelta(days=2), beginn=time(7), ende=time(16), team=team, benutzer=chef)
    ag = produktion.einzeln(p, Vorlage.objects.get(code="SL-020"), mitarbeiter=leute[2], benutzer=chef)
    ag.plan_start, ag.plan_ende = MO - timedelta(days=3), MO + timedelta(days=1)
    ag.save()
    dienst.abwesenheit_erfassen(mitarbeiter=leute[0], von=MO + timedelta(days=4), bis=MO + timedelta(days=9),
                                art="Urlaub", status="Freigegeben", benutzer=chef)
    dienst.termin_anlegen(datum=MO, aufgabe="Aufmaß Bad", mitarbeiter=leute[1], beginn=time(9), art="Aufmaß", benutzer=chef)
    ev = dienst.ereignisse(MO)
    typen = sorted((e["tag"], e["typ"], e["ma"].name if e["ma"] else None) for e in ev)
    assert (0, "f", "Sven Bach") in typen and (1, "f", "Sven Bach") in typen and (2, "f", "Sven Bach") not in typen
    assert (2, "m", "Dieter Kaub") in typen and (2, "m", "Klaus Otto") in typen
    assert len([e for e in ev if e["typ"] == "m"]) == 2  # Montageplan nicht doppelt zu den Montage-Terminen
    assert (4, "a", "Dieter Kaub") in typen and (0, "t", "Klaus Otto") in typen
    k = dienst.kalender(MO, "team")
    assert k["kw"] == 47 and [r["name"] for r in k["reihen"]] == ["Montage 1", "Ohne Team"]
    montag = k["reihen"][0]["zellen"][0]["eintraege"]
    assert {"text": "09:00 Aufmaß Bad · Klaus Otto", "typ": "t"} in montag
    assert k["reihen"][0]["zellen"][4]["typ"] == "a"
    assert "Sven Bach" in k["reihen"][1]["zellen"][0]["eintraege"][0]["text"]
    km = dienst.kalender(MO, "mitarbeiter")
    assert [r["name"] for r in km["reihen"]] == ["Dieter Kaub", "Klaus Otto", "Sven Bach"]
    kp = dienst.kalender(MO, "projekt")
    assert kp["reihen"][0]["sub"] == "P-2026-001" and kp["reihen"][-1]["name"] == "Sonstiges"


# ------------------------------------------------------------------ Seiten
def test_seiten(team, leute, chef, chef_client):
    for name in ("kalender", "teams", "abwesenheiten", "montageplan"):
        assert chef_client.get(reverse(f"planung:{name}")).status_code == 200
    assert chef_client.get(reverse("planung:kalender") + "?woche=2026-11-18&ansicht=mitarbeiter").status_code == 200
    chef_client.post(reverse("planung:teams"), {"name": "Werkstatt A", "art": "Werkstatt"})
    t = Team.objects.get(name="Werkstatt A")
    chef_client.post(reverse("planung:team", args=[t.pk]), {"aktion": "mitglied", "mitarbeiter": leute[2].pk})
    assert t.mitglieder() == [leute[2]]
    chef_client.post(reverse("planung:abwesenheiten"), {"mitarbeiter": leute[0].pk, "von": "2026-11-20", "art": "Urlaub",
                                                        "status": "Freigegeben", "hinweis": ""})
    a = Abwesenheit.objects.get()
    assert a.bis == a.von == date(2026, 11, 20) and a.status == "Freigegeben"
    chef_client.post(reverse("planung:kalender"), {"mitarbeiter": "", "team": team.pk, "datum": "2026-11-17",
                                                   "art": "Kundentermin", "aufgabe": "Besprechung", "beginn": "10:00"})
    assert Termin.objects.filter(aufgabe="Besprechung").count() == 2
    t1 = Termin.objects.filter(aufgabe="Besprechung").first()
    chef_client.post(reverse("planung:kalender") + "?woche=2026-11-16", {"aktion": "absagen", "termin": t1.pk})
    t1.refresh_from_db()
    assert t1.abgesagt
    seite = chef_client.get(reverse("planung:kalender") + "?woche=2026-11-16").content.decode()
    assert "KW 47" in seite and "Besprechung · Klaus Otto" in seite


def test_seite_montage_mit_warnung(team, leute, chef, chef_client):
    p = projekt_bereit(chef=chef)
    url = reverse("planung:montage", args=[p.pk])
    seite = chef_client.get(url).content.decode()
    assert "Hauptstr. 5, 67433 Neustadt" in seite and "Wann, wer, womit?" in seite
    dienst.abwesenheit_erfassen(mitarbeiter=leute[0], von=MO, bis=MO, art="Krank", status="Freigegeben", benutzer=chef)
    daten = {"aktion": "planen", "datum": "2026-11-16", "beginn": "07:00", "ende": "16:00", "team": team.pk,
             "fahrzeug": "Transporter", "adresse": "Hauptstr. 5", "aufgaben": "Küche", "material": "", "werkzeug": "",
             "hinweise": ""}
    antwort = chef_client.post(url, daten)
    assert "Abwesend: Dieter Kaub (Krank)" in antwort.content.decode() and not Montage.objects.exists()
    chef_client.post(url, {**daten, "trotzdem": "1"})
    assert Montage.objects.get().fahrzeug == "Transporter"
    chef_client.post(url, {"aktion": "Bestanden"})
    p = Projekt.objects.get(pk=p.pk)
    assert produktion.phase(p) == 4
    prod = chef_client.get(reverse("produktion:projekt", args=[p.pk])).content.decode()
    assert "das Projekt ist fertig" in prod


def test_rechte_mitarbeiter(client, leute, team, benutzer_mit_rolle, chef):
    zugang = benutzer_mit_rolle(Rolle.MITARBEITER, "dieter")
    leute[0].benutzer = zugang
    leute[0].save()
    client.force_login(zugang)
    assert client.get(reverse("planung:kalender")).status_code == 200
    p = projekt_bereit(chef=chef)
    assert client.get(reverse("planung:montage", args=[p.pk])).status_code == 403
    client.post(reverse("planung:teams"), {"name": "Heimlich", "art": "Montage"})
    assert not Team.objects.filter(name="Heimlich").exists()
    client.post(reverse("planung:abwesenheiten"), {"mitarbeiter": leute[0].pk, "von": "2026-12-01", "bis": "2026-12-03",
                                                   "art": "Urlaub", "status": "Freigegeben", "hinweis": ""})
    a = Abwesenheit.objects.get()
    assert a.status == "Beantragt" and a.mitarbeiter == leute[0]  # Mitarbeiter beantragen nur
    client.post(reverse("planung:abwesenheiten"), {"aktion": "status", "abwesenheit": a.pk, "status": "Freigegeben"})
    a.refresh_from_db()
    assert a.status == "Beantragt"
    client.post(reverse("planung:abwesenheiten"), {"mitarbeiter": leute[1].pk, "von": "2026-12-01", "art": "Urlaub"})
    assert Abwesenheit.objects.count() == 1  # nicht für andere


def test_einplanen_warnt_bei_abwesenheit(leute, chef, chef_client):
    p = Projekt.objects.create(projektnr="P-9", name="x", kunde=Kunde.objects.create(kundennr="K-9", name="y"))
    produktion.einzeln(p, Vorlage.objects.get(code="PL-010"), benutzer=chef)
    dienst.abwesenheit_erfassen(mitarbeiter=leute[0], von=MO, bis=MO, art="Berufsschule", status="Freigegeben", benutzer=chef)
    antwort = chef_client.post(reverse("produktion:projekt", args=[p.pk]),
                               {"aktion": "planen", "pl-start": "2026-11-16", "pl-mitarbeiter": leute[0].pk}, follow=True)
    assert "Dieter Kaub ist am 16.11. abwesend (Berufsschule)" in antwort.content.decode()


# ------------------------------------------------------------------ Import
def _blatt(mappe, name, zeilen):
    from openpyxl.utils import column_index_from_string
    ws = mappe.create_sheet(name)
    for nr, z in zeilen.items():
        for spalte, wert in z.items():
            ws.cell(row=nr, column=column_index_from_string(spalte), value=wert)


def test_import(tmp_path, leute):
    p = Projekt.objects.create(projektnr="P-2026-001", name="Küche", kunde=Kunde.objects.create(kundennr="K-1", name="W"))
    mappe = Workbook()
    mappe.remove(mappe.active)
    _blatt(mappe, "Teams", {
        3: {"A": "Team-ID", "L": "Teamname (Eingabe)"},
        4: {"A": "TEAM-0001", "B": "Montage", "J": "Aktiv", "K": "Küchen", "L": "Montage Nord"},
        5: {"A": "TEAM-0002", "B": "Montage"},  # reservierter Platz ohne Namen
        109: {"A": "Team-ID", "B": "Mitarbeiter"},
        110: {"A": "TEAM-0001", "B": "D.Kaub", "C": "Leitung", "F": "Ja"},
        111: {"A": "TEAM-0001", "B": "K.Otto", "C": "Mitglied", "F": "Ja"},
        112: {"A": "TEAM-0001", "B": "X.Unbekannt", "F": "Ja"}})
    _blatt(mappe, "Zeitdaten", {
        4: {"A": "ZD-0002", "B": "D.Kaub", "C": date(2026, 9, 10), "D": date(2026, 9, 10), "E": "Fortbildung", "H": "Freigegeben"},
        5: {"A": "ZD-0003", "B": "K.Otto", "C": date(2026, 10, 22), "D": date(2026, 10, 23), "E": "Elternzeit", "H": "Beantragt"}})
    _blatt(mappe, "Montageplan", {
        4: {"B": "P-2026-001", "C": "Hauptstr. 5", "D": date(2026, 11, 18), "E": time(7, 30), "F": 0.6875,
            "G": "TEAM-0001", "I": "Küche montieren", "L": "Transporter"}})
    _blatt(mappe, "Zeitplan", {
        4: {"A": "T-0007", "B": "D.Kaub", "C": date(2026, 11, 18), "D": time(7, 30), "E": time(16, 30), "F": "P-2026-001",
            "H": "Montage Küche", "J": "TEAM-0001", "K": "Montage", "X": "Montage"},
        5: {"B": "S.Bach", "C": date(2026, 11, 19), "H": "Aufmaß", "K": "Aufmaß"}})
    pfad = tmp_path / "pw.xlsx"
    mappe.save(pfad)
    bericht = ausfuehren(pfad, probelauf=False)
    b = {x["blatt"]: x for x in bericht["blaetter"]}
    assert b["Teams"]["neu"] == 3 and len(b["Teams"]["fehler"]) == 1
    t = Team.objects.get()
    assert (t.teamid, t.name, t.hinweis) == ("TEAM-0001", "Montage Nord", "Küchen")
    assert [m.kuerzel for m in t.mitglieder()] == ["D.Kaub", "K.Otto"]
    a = Abwesenheit.objects.get(zid="ZD-0003")
    assert a.art == "Sonstiges" and a.hinweis == "Elternzeit" and a.status == "Beantragt" and a.tage == 2
    m = Montage.objects.get()
    assert m.projekt == p and m.ende == time(16, 30) and m.team == t
    assert Termin.objects.get(terminid="T-0007").aus_montage and Termin.objects.get(aufgabe="Aufmaß").terminid == "T-0008"
    ausfuehren(pfad, probelauf=False)
    assert (Team.objects.count(), TeamMitglied.objects.count(), Abwesenheit.objects.count(), Termin.objects.count()) == (1, 2, 2, 2)
