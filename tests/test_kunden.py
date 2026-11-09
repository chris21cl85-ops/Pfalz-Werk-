import pytest
from django.urls import reverse

from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde, adresse_zerlegen, naechste_kundennr

pytestmark = pytest.mark.django_db


def kunde(**werte):
    daten = {"kundennr": "K-001", "name": "Schreiner Müller", "ort": "Neustadt"}
    daten.update(werte)
    return Kunde.objects.create(**daten)


# --- Adresse zerlegen -------------------------------------------------------

@pytest.mark.parametrize("text,erwartet", [
    ("Hauptstr. 5, 67433 Neustadt", ("Hauptstr. 5", "67433", "Neustadt")),
    ("Weinstraße 12\n67480 Edenkoben", ("Weinstraße 12", "67480", "Edenkoben")),
    ("Am Berg 3 67434 Neustadt an der Weinstraße", ("Am Berg 3", "67434", "Neustadt an der Weinstraße")),
    ("67433 Neustadt", ("", "67433", "Neustadt")),
    ("irgendwo im Wald", ("", "", "")),
    ("", ("", "", "")),
])
def test_adresse_zerlegen(text, erwartet):
    a = adresse_zerlegen(text)
    assert (a["strasse"], a["plz"], a["ort"]) == erwartet


# --- Nummernvorschlag -------------------------------------------------------

def test_erste_kundennr_ist_1():
    assert naechste_kundennr() == "1"


def test_kundennr_folgt_dem_muster():
    kunde(kundennr="K-007")
    kunde(kundennr="K-012", name="B")
    assert naechste_kundennr() == "K-013"


def test_kundennr_rein_numerisch():
    kunde(kundennr="41")
    assert naechste_kundennr() == "42"


# --- Liste und Suche --------------------------------------------------------

def test_liste_zeigt_aktive_kunden(chef_client):
    kunde()
    kunde(kundennr="K-002", name="Alte Firma", status=Kunde.Status.INAKTIV)
    inhalt = chef_client.get(reverse("kunden:liste")).content.decode()
    assert "Schreiner Müller" in inhalt and "Alte Firma" not in inhalt
    assert "Alte Firma" in chef_client.get(reverse("kunden:liste") + "?alle=1").content.decode()


@pytest.mark.parametrize("suchwort", ["müller", "K-001", "Neustadt", "0632"])
def test_suche(chef_client, suchwort):
    kunde(telefon="06321 12345")
    kunde(kundennr="K-002", name="Holzbau Schmitt", ort="Landau")
    inhalt = chef_client.get(reverse("kunden:liste"), {"suche": suchwort}).content.decode()
    assert "Schreiner Müller" in inhalt and "Holzbau Schmitt" not in inhalt


def test_startseite_kachel_kunden_ist_aktiv(chef_client):
    assert reverse("kunden:liste") in chef_client.get("/").content.decode()


# --- Anlegen und Bearbeiten -------------------------------------------------

def test_kunde_anlegen_mit_protokoll(chef_client):
    antwort = chef_client.post(reverse("kunden:neu"), {
        "kundennr": "1", "name": "Familie Weber", "kundenart": "Privat", "plz": "67433",
        "ort": "Neustadt", "status": "Aktiv"}, follow=True)
    assert "wurde angelegt" in antwort.content.decode()
    k = Kunde.objects.get(kundennr="1")
    assert k.name == "Familie Weber"
    assert Protokolleintrag.objects.filter(aktion="kunde_angelegt").exists()


def test_doppelte_kundennr_wird_abgelehnt(chef_client):
    kunde()
    antwort = chef_client.post(reverse("kunden:neu"), {"kundennr": "k-001", "name": "X", "status": "Aktiv"})
    assert "schon vergeben" in antwort.content.decode()
    assert Kunde.objects.count() == 1


def test_falsche_plz_wird_abgelehnt(chef_client):
    antwort = chef_client.post(reverse("kunden:neu"), {"kundennr": "9", "name": "X", "plz": "674", "status": "Aktiv"})
    assert "5 Ziffern" in antwort.content.decode()


def test_bearbeiten_protokolliert_alt_und_neu(chef_client):
    k = kunde(telefon="111")
    chef_client.post(reverse("kunden:bearbeiten", args=[k.pk]), {
        "kundennr": "K-001", "name": "Schreiner Müller", "telefon": "222", "ort": "Neustadt", "status": "Aktiv"})
    k.refresh_from_db()
    assert k.telefon == "222"
    eintrag = Protokolleintrag.objects.get(aktion="kunde_geaendert")
    assert "„111“ → „222“" in eintrag.details


def test_kunde_kann_nicht_geloescht_werden_nur_inaktiv(chef_client):
    k = kunde()
    chef_client.post(reverse("kunden:bearbeiten", args=[k.pk]), {
        "kundennr": "K-001", "name": "Schreiner Müller", "status": "Inaktiv"})
    k.refresh_from_db()
    assert k.status == "Inaktiv" and Kunde.objects.count() == 1


# --- Rechte ----------------------------------------------------------------

@pytest.mark.parametrize("rolle", [Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG, Rolle.MEISTER])
def test_bearbeiter_rollen(client, benutzer_mit_rolle, rolle):
    client.force_login(benutzer_mit_rolle(rolle))
    assert client.get(reverse("kunden:neu")).status_code == 200


def test_mitarbeiter_darf_ansehen_aber_nicht_aendern(client, benutzer_mit_rolle):
    k = kunde()
    client.force_login(benutzer_mit_rolle(Rolle.MITARBEITER))
    assert client.get(reverse("kunden:liste")).status_code == 200
    detail = client.get(reverse("kunden:detail", args=[k.pk])).content.decode()
    assert "Schreiner Müller" in detail and "Bearbeiten" not in detail
    assert client.get(reverse("kunden:neu")).status_code == 403
    assert client.post(reverse("kunden:bearbeiten", args=[k.pk]), {"name": "X"}).status_code == 403
