import datetime as dt

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook
from openpyxl.utils import column_index_from_string

from importe.models import Importlauf
from kunden.models import Kunde
from projekte.importer import als_datum
from projekte.models import Projekt

pytestmark = pytest.mark.django_db(transaction=True)


def zeile(werte: dict):
    """Baut eine Excel-Zeile aus {Spaltenbuchstabe: Wert}."""
    breite = max(column_index_from_string(b) for b in werte)
    z = [None] * breite
    for b, w in werte.items():
        z[column_index_from_string(b) - 1] = w
    return z


def excel(tmp_path, kunden, projekte):
    mappe = Workbook()
    mappe.remove(mappe.active)
    # Projekte absichtlich VOR Kunden – das Programm muss trotzdem erst Kunden lesen
    for name, zeilen in (("Projekte", projekte), ("Kunden", kunden)):
        blatt = mappe.create_sheet(name)
        blatt.append([name]); blatt.append([]); blatt.append(["Kopf"])
        for z in zeilen:
            blatt.append(z)
    pfad = tmp_path / "pfalzwerk.xlsm"
    mappe.save(pfad)
    return pfad


KUNDEN = [zeile({"A": "K-1", "B": "Familie Weber"}), zeile({"A": "K-2", "B": "Schmitt"})]
PROJEKTE = [
    zeile({"A": "P-001", "B": "Einbauküche", "C": "K-1", "D": "Angebot", "E": "Auftrag", "F": "Chris",
           "G": dt.datetime(2026, 11, 3), "H": "15.12.2026", "K": "Lieferzeit", "L": "Aufmaß",
           "S": "Küche", "AL": "A-77"}),
    zeile({"A": "P-002", "B": "Treppe", "C": "K-2", "S": "Treppenbau", "Y": "Treppe Holz", "G": "irgendwann"}),
]


def pruefen(client, pfad):
    client.post(reverse("importe:uebersicht"), {"datei": SimpleUploadedFile(pfad.name, pfad.read_bytes())})
    return Importlauf.objects.latest("zeitpunkt")


def blatt(lauf, name):
    return next(b for b in lauf.bericht["blaetter"] if b["blatt"] == name)


@pytest.mark.parametrize("wert,erwartet", [
    (dt.datetime(2026, 1, 2, 10, 0), dt.date(2026, 1, 2)), ("02.01.2026", dt.date(2026, 1, 2)),
    (46024, dt.date(2026, 1, 2)), ("quatsch", None), (None, None),
])
def test_als_datum(wert, erwartet):
    assert als_datum(wert) == erwartet


def test_probelauf_kunden_vor_projekten(chef_client, tmp_path):
    lauf = pruefen(chef_client, excel(tmp_path, KUNDEN, PROJEKTE))
    p = blatt(lauf, "Projekte")
    assert p["neu"] == 2 and p["fehler"] == []
    assert Projekt.objects.count() == 0 and Kunde.objects.count() == 0


def test_uebernahme_felder(chef_client, tmp_path):
    lauf = pruefen(chef_client, excel(tmp_path, KUNDEN, PROJEKTE))
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))
    p = Projekt.objects.get(projektnr="P-001")
    assert p.kunde.kundennr == "K-1" and p.name == "Einbauküche"
    assert (p.phase, p.status, p.projektpate) == ("Angebot", "Auftrag", "Chris")
    assert p.startdatum == dt.date(2026, 11, 3) and p.zieldatum == dt.date(2026, 12, 15)
    assert (p.risiko, p.naechster_schritt, p.projektart, p.anfrage_id) == ("Lieferzeit", "Aufmaß", "Küche", "A-77")
    t = Projekt.objects.get(projektnr="P-002")
    assert t.projektart == "Treppe Holz"  # Spalte Y hat Vorrang vor S
    assert t.status == "Planung" and t.startdatum is None
    assert "nicht lesbar: irgendwann" in t.hinweise


def test_fehler_kunde_fehlt_doppelt_name_fehlt(chef_client, tmp_path):
    projekte = PROJEKTE + [
        zeile({"A": "P-003", "B": "Ohne Kunde", "C": "K-99"}),
        zeile({"A": "P-001", "B": "Doppelt", "C": "K-1"}),
        zeile({"A": "P-004", "C": "K-1"}),
        zeile({"A": "P-005", "B": "Keine Kundennr"}),
    ]
    lauf = pruefen(chef_client, excel(tmp_path, KUNDEN, projekte))
    text = " ".join(blatt(lauf, "Projekte")["fehler"])
    assert "Kunde K-99 gibt es nicht" in text and "doppelt" in text
    assert "keinen Projektnamen" in text and "keine Kunden-Nr." in text
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))
    assert Projekt.objects.count() == 2


def test_zweiter_import_ueberschreibt_nichts(chef_client, tmp_path):
    lauf = pruefen(chef_client, excel(tmp_path, KUNDEN, PROJEKTE))
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))
    Projekt.objects.filter(projektnr="P-001").update(status="In Arbeit")
    lauf2 = pruefen(chef_client, excel(tmp_path, KUNDEN, PROJEKTE))
    assert blatt(lauf2, "Projekte")["unveraendert"] == 2
    chef_client.post(reverse("importe:uebernehmen", args=[lauf2.pk]))
    assert Projekt.objects.get(projektnr="P-001").status == "In Arbeit"


def test_projekt_zu_schon_vorhandenem_kunden(chef_client, tmp_path):
    Kunde.objects.create(kundennr="K-1", name="Familie Weber")
    lauf = pruefen(chef_client, excel(tmp_path, [], [PROJEKTE[0]]))
    assert blatt(lauf, "Projekte")["neu"] == 1
