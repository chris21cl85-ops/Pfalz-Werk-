import pytest
from django.urls import reverse

from konten.models import Rolle

pytestmark = pytest.mark.django_db

VERWALTUNGSSEITEN = ["protokoll", "sicherung:uebersicht", "importe:uebersicht",
                     "admin:konten_benutzer_changelist"]


def test_startseite_zeigt_namen_und_rolle(chef_client):
    inhalt = chef_client.get("/").content.decode()
    assert "Chef" in inhalt and "Abmelden" in inhalt


def test_chef_sieht_alle_kacheln(chef_client):
    inhalt = chef_client.get("/").content.decode()
    for titel in ["Excel-Import", "Sicherung", "Protokoll", "Benutzer", "Rechnungen", "Auswertungen"]:
        assert titel in inhalt


def test_mitarbeiter_sieht_keine_verwaltung_und_kein_geld(client, benutzer_mit_rolle):
    client.force_login(benutzer_mit_rolle(Rolle.MITARBEITER))
    inhalt = client.get("/").content.decode()
    assert "Zeiterfassung" in inhalt
    for titel in ["Excel-Import", "Protokoll", "Rechnungen", "Finanzen"]:
        assert titel not in inhalt


def test_buchhaltung_sieht_rechnungen(client, benutzer_mit_rolle):
    client.force_login(benutzer_mit_rolle(Rolle.BUCHHALTUNG))
    inhalt = client.get("/").content.decode()
    assert "Rechnungen" in inhalt and "Finanzen" in inhalt and "Excel-Import" not in inhalt


@pytest.mark.parametrize("rolle", [Rolle.BUCHHALTUNG, Rolle.MEISTER, Rolle.MITARBEITER])
@pytest.mark.parametrize("seite", VERWALTUNGSSEITEN)
def test_verwaltungsseiten_sind_gesperrt(client, benutzer_mit_rolle, rolle, seite):
    client.force_login(benutzer_mit_rolle(rolle))
    assert client.get(reverse(seite)).status_code in (302, 403)


@pytest.mark.parametrize("rolle", [Rolle.CHEF, Rolle.ADMIN])
@pytest.mark.parametrize("seite", VERWALTUNGSSEITEN)
def test_verwaltungsseiten_fuer_chef_und_admin_offen(client, benutzer_mit_rolle, rolle, seite):
    client.force_login(benutzer_mit_rolle(rolle))
    assert client.get(reverse(seite)).status_code == 200


def test_benutzer_koennen_nicht_geloescht_werden(chef_client, chef):
    antwort = chef_client.get(reverse("admin:konten_benutzer_delete", args=[chef.pk]))
    assert antwort.status_code == 403
