import datetime as dt
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook

from importe.models import Importlauf
from material.models import Material
from tests.test_projekte_import import zeile

pytestmark = pytest.mark.django_db(transaction=True)


def excel(tmp_path, zeilen):
    mappe = Workbook()
    blatt = mappe.active
    blatt.title = "Material"
    blatt.append(["Material"]); blatt.append([]); blatt.append(["Kopf"])
    for z in zeilen:
        blatt.append(z)
    pfad = tmp_path / "pfalzwerk.xlsm"
    mappe.save(pfad)
    return pfad


VOLL = zeile({"A": "M-001", "B": "Platten", "C": "Spanplatte Eiche", "D": "m²", "E": 12.5, "F": 5,
              "H": 7, "I": "Staffelpreis ab 10", "T": "Dekor", "U": 19, "V": "2800 x 2070 mm", "W": "Ja",
              "X": "Aktiv", "Y": "Lager / Wiederbeschaffung", "AF": 20, "AH": "Halle 1", "AI": 18.9,
              "AK": "Katalogpreis", "AL": dt.datetime(2026, 10, 1)})
ZEILEN = [
    VOLL,
    zeile({"A": "M-002", "C": "Topfband", "E": "2,35", "W": "Nein", "X": "Inaktiv"}),
    zeile({"A": "M-003", "C": "Schrauben", "E": "auf Anfrage"}),
]


def pruefen(client, pfad):
    client.post(reverse("importe:uebersicht"), {"datei": SimpleUploadedFile(pfad.name, pfad.read_bytes())})
    return Importlauf.objects.latest("zeitpunkt")


def test_import_alle_spalten(chef_client, tmp_path):
    lauf = pruefen(chef_client, excel(tmp_path, ZEILEN))
    b = lauf.bericht["blaetter"][0]
    assert b["importer"] == "Material" and b["neu"] == 3 and b["fehler"] == []
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))
    m = Material.objects.get(materialnr="M-001")
    assert (m.produktgruppe, m.untergruppe, m.bezeichnung, m.einheit) == ("Platten", "Dekor", "Spanplatte Eiche", "m²")
    assert m.ek_netto == Decimal("12.5") and m.mindestbestand == 5 and m.zielbestand == 20
    assert m.lieferzeit_tage == 7 and m.staerke_mm == 19 and m.format == "2800 x 2070 mm"
    assert m.lagerartikel and m.aktiv and m.lagerplatz == "Halle 1"
    assert m.referenzpreis_brutto == Decimal("18.9") and m.preisquelle == "Katalogpreis"
    assert m.preisstand == dt.date(2026, 10, 1) and m.preis_hinweis == "Staffelpreis ab 10"
    t = Material.objects.get(materialnr="M-002")
    assert t.ek_netto == Decimal("2.35") and not t.lagerartikel and not t.aktiv
    s = Material.objects.get(materialnr="M-003")
    assert s.ek_netto is None and "EK netto aus Excel nicht lesbar: auf Anfrage" in s.hinweise


def test_fehler_und_keine_ueberschreibung(chef_client, tmp_path):
    Material.objects.create(materialnr="M-001", bezeichnung="Schon da", ek_netto=Decimal("99"))
    zeilen = ZEILEN + [zeile({"A": "M-002", "C": "Doppelt"}), zeile({"A": "M-004"})]
    lauf = pruefen(chef_client, excel(tmp_path, zeilen))
    b = lauf.bericht["blaetter"][0]
    assert b["unveraendert"] == 1 and b["neu"] == 2
    text = " ".join(b["fehler"])
    assert "doppelt" in text and "keine Bezeichnung" in text
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))
    assert Material.objects.get(materialnr="M-001").ek_netto == Decimal("99")


def test_endzeile_350(chef_client, tmp_path):
    zeilen = [zeile({"A": f"M-{i}", "C": f"Artikel {i}"}) for i in range(1, 360)]
    lauf = pruefen(chef_client, excel(tmp_path, zeilen))
    assert lauf.bericht["blaetter"][0]["zeilen"] == 347  # Zeilen 4–350
