import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook

from importe.models import Importlauf
from kunden.models import Kunde

pytestmark = pytest.mark.django_db(transaction=True)


def excel_wie_pfalzwerk(tmp_path, kundenzeilen, weitere_blaetter=("Start", "Projekte")):
    """Baut eine Excel im Aufbau der alten Fassung: Kopf in Zeile 3, Daten ab Zeile 4, Spalten A–I."""
    mappe = Workbook()
    mappe.remove(mappe.active)
    for name in weitere_blaetter:
        mappe.create_sheet(name).append(["nur Test"])
    blatt = mappe.create_sheet("Kunden")
    blatt.append(["PFALZ-WERK Kunden"])
    blatt.append([])
    blatt.append(["Nr", "Name", "Ansprechpartner", "Telefon", "E-Mail", "Adresse", "Kundenart", "H", "Hinweise"])
    for z in kundenzeilen:
        blatt.append(z)
    pfad = tmp_path / "Pfalz-Werk_aktuell.xlsm"
    mappe.save(pfad)
    return pfad


ZEILEN = [
    [1.0, "Familie Weber", "Anna Weber", 6321123456.0, "weber@example.de", "Hauptstr. 5, 67433 Neustadt", "Privat", None, "Küche 2025"],
    ["K-2", "Holzbau Schmitt GmbH", None, "06341 999", None, "Industriestr. 1\n76829 Landau", "", None, None],
    [None, None, None, None, None, None, None, None, None],
    ["K-3", "Kunde ohne Adresse", None, None, None, None, "Gewerbe", None, None],
]


def hochladen_und_pruefen(client, pfad):
    datei = SimpleUploadedFile(pfad.name, pfad.read_bytes())
    client.post(reverse("importe:uebersicht"), {"datei": datei})
    return Importlauf.objects.latest("zeitpunkt")


def test_probelauf_erkennt_kundenblatt_und_speichert_nichts(chef_client, tmp_path):
    lauf = hochladen_und_pruefen(chef_client, excel_wie_pfalzwerk(tmp_path, ZEILEN))
    kunden = next(b for b in lauf.bericht["blaetter"] if b["blatt"] == "Kunden")
    assert kunden["importer"] == "Kunden"
    assert kunden["zeilen"] == 3 and kunden["neu"] == 3 and kunden["fehler"] == []
    assert Kunde.objects.count() == 0


def test_uebernahme_liest_spalten_richtig(chef_client, tmp_path):
    lauf = hochladen_und_pruefen(chef_client, excel_wie_pfalzwerk(tmp_path, ZEILEN))
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))
    weber = Kunde.objects.get(kundennr="1")
    assert weber.name == "Familie Weber"
    assert weber.ansprechpartner == "Anna Weber"
    assert weber.telefon == "6321123456"
    assert weber.email == "weber@example.de"
    assert (weber.strasse, weber.plz, weber.ort) == ("Hauptstr. 5", "67433", "Neustadt")
    assert weber.adresse_original == "Hauptstr. 5, 67433 Neustadt"
    assert weber.hinweise == "Küche 2025" and weber.kundenart == "Privat" and weber.status == "Aktiv"
    schmitt = Kunde.objects.get(kundennr="K-2")
    assert schmitt.kundenart == "Unbekannt" and schmitt.ort == "Landau"
    assert Kunde.objects.count() == 3


def test_zweiter_import_ueberschreibt_nichts(chef_client, tmp_path):
    lauf = hochladen_und_pruefen(chef_client, excel_wie_pfalzwerk(tmp_path, ZEILEN))
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))
    Kunde.objects.filter(kundennr="1").update(telefon="geändert im Programm")
    lauf2 = hochladen_und_pruefen(chef_client, excel_wie_pfalzwerk(tmp_path, ZEILEN))
    kunden = next(b for b in lauf2.bericht["blaetter"] if b["blatt"] == "Kunden")
    assert kunden["neu"] == 0 and kunden["unveraendert"] == 3
    chef_client.post(reverse("importe:uebernehmen", args=[lauf2.pk]))
    assert Kunde.objects.get(kundennr="1").telefon == "geändert im Programm"


def test_fehler_werden_gemeldet_und_uebersprungen(chef_client, tmp_path):
    zeilen = ZEILEN + [
        ["K-2", "Doppelt", None, None, None, None, None, None, None],
        ["K-9", None, None, None, None, None, None, None, None],
        [None, "Name ohne Nummer", None, None, None, None, None, None, None],
        ["K-10", "Falsche Mail", None, None, "keine-mail", None, None, None, None],
    ]
    lauf = hochladen_und_pruefen(chef_client, excel_wie_pfalzwerk(tmp_path, zeilen))
    kunden = next(b for b in lauf.bericht["blaetter"] if b["blatt"] == "Kunden")
    text = " ".join(kunden["fehler"])
    assert "doppelt" in text and "keinen Namen" in text and "Kunden-Nr. fehlt" in text and "ungültig" in text
    assert len(kunden["fehler"]) == 4
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))
    assert Kunde.objects.count() == 3


def test_zeilen_nach_97_werden_wie_in_excel_ignoriert(chef_client, tmp_path):
    zeilen = [[f"K-{i}", f"Kunde {i}"] + [None] * 7 for i in range(1, 100)]  # Zeilen 4 bis 102
    lauf = hochladen_und_pruefen(chef_client, excel_wie_pfalzwerk(tmp_path, zeilen))
    kunden = next(b for b in lauf.bericht["blaetter"] if b["blatt"] == "Kunden")
    assert kunden["zeilen"] == 94  # Zeilen 4–97


def test_import_seite_nennt_kundenblatt(chef_client):
    assert "Blatt „Kunden“" in chef_client.get(reverse("importe:uebersicht")).content.decode()
