import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook

from importe import dienst
from importe.models import Importlauf
from kern.models import Protokolleintrag
from sicherung.dienst import sicherungen

pytestmark = pytest.mark.django_db(transaction=True)

GESPEICHERT = []


@pytest.fixture
def test_importer():
    """Ein Beispiel-Importer, wie er ab Etappe 1 für echte Blätter gebaut wird."""
    GESPEICHERT.clear()
    vorher = dict(dienst.IMPORTER)

    @dienst.registrieren
    class TestKunden(dienst.Importer):
        blatt = "Kunden"
        titel = "Kunden (Test)"
        pflichtspalten = ("Nr", "Name")

        def zeile_uebernehmen(self, zeile):
            GESPEICHERT.append(zeile)
            return "neu"

    yield TestKunden
    dienst.IMPORTER.clear()
    dienst.IMPORTER.update(vorher)


def excel(tmp_path, blaetter):
    mappe = Workbook()
    mappe.remove(mappe.active)
    for titel, zeilen in blaetter.items():
        blatt = mappe.create_sheet(titel)
        for z in zeilen:
            blatt.append(z)
    pfad = tmp_path / "pfalzwerk.xlsx"
    mappe.save(pfad)
    return pfad


def hochladen(client, pfad, name="pfalzwerk.xlsx"):
    datei = SimpleUploadedFile(name, pfad.read_bytes())
    return client.post(reverse("importe:uebersicht"), {"datei": datei}, follow=True)


def test_probelauf_zeigt_blaetter_ohne_zu_speichern(chef_client, tmp_path, test_importer):
    pfad = excel(tmp_path, {"Kunden": [["Nr", "Name"], [1, "Müller"], [2, ""], [None, None]],
                            "Notizen": [["x"], [1]]})
    antwort = hochladen(chef_client, pfad)
    inhalt = antwort.content.decode()
    assert "Kunden (Test)" in inhalt and "Notizen" in inhalt and "Zeile 3" in inhalt
    lauf = Importlauf.objects.get()
    assert lauf.status == Importlauf.Status.PROBELAUF
    kunden = lauf.bericht["blaetter"][0]
    assert kunden["zeilen"] == 2 and len(kunden["fehler"]) == 1 and kunden["neu"] == 1


def test_uebernahme_sichert_vorher_und_protokolliert(chef_client, tmp_path, test_importer):
    hochladen(chef_client, excel(tmp_path, {"Kunden": [["Nr", "Name"], [1, " Müller "], [2, "Schmitt"]]}))
    lauf = Importlauf.objects.get()
    GESPEICHERT.clear()
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))
    lauf.refresh_from_db()
    assert lauf.status == Importlauf.Status.UEBERNOMMEN
    assert [z["Name"] for z in GESPEICHERT] == ["Müller", "Schmitt"]
    assert lauf.bericht["blaetter"][0]["neu"] == 2
    assert len(sicherungen()) == 1
    assert Protokolleintrag.objects.filter(aktion="import").exists()


def test_uebernahme_ohne_erkanntes_blatt_wird_abgelehnt(chef_client, tmp_path):
    hochladen(chef_client, excel(tmp_path, {"Irgendwas": [["a"], [1]]}))
    lauf = Importlauf.objects.get()
    antwort = chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]), follow=True)
    assert "kein übernehmbares" in antwort.content.decode()
    assert sicherungen() == []


def test_falsche_dateiart_wird_abgelehnt(chef_client, tmp_path):
    pfad = tmp_path / "liste.csv"
    pfad.write_text("a;b")
    antwort = hochladen(chef_client, pfad, name="liste.csv")
    assert "Excel-Datei" in antwort.content.decode()
    assert not Importlauf.objects.exists()


def test_kaputte_excel_datei_gibt_verstaendliche_meldung(chef_client, tmp_path):
    pfad = tmp_path / "kaputt.xlsx"
    pfad.write_bytes(b"kein excel")
    antwort = hochladen(chef_client, pfad, name="kaputt.xlsx")
    assert "lässt sich nicht öffnen" in antwort.content.decode()
    assert Importlauf.objects.get().status == Importlauf.Status.FEHLER
