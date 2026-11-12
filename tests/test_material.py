import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse

from kern.models import Protokolleintrag
from konten.models import Rolle
from material.ansichten import naechste_materialnr
from material.importer import als_ja, als_zahl, ist_aktiv
from material.models import Material

pytestmark = pytest.mark.django_db


def material(**werte):
    daten = {"materialnr": "M-001", "bezeichnung": "Spanplatte Eiche 19 mm", "produktgruppe": "Platten",
             "einheit": "m²", "ek_netto": Decimal("12.5")}
    daten.update(werte)
    return Material.objects.create(**daten)


@pytest.mark.parametrize("wert,erwartet", [
    (12.5, Decimal("12.5")), ("12,50", Decimal("12.50")), ("1.234,5", Decimal("1234.5")),
    ("19 mm", Decimal("19")), ("8,90 €", Decimal("8.90")), (None, None), ("", None), ("teuer", False),
])
def test_als_zahl(wert, erwartet):
    assert als_zahl(wert) == erwartet


def test_ja_und_aktiv():
    assert als_ja("Ja") and als_ja("WAHR") and als_ja(1) and not als_ja("Nein") and not als_ja(None)
    assert ist_aktiv("Aktiv") and ist_aktiv(None) and not ist_aktiv("Inaktiv") and not ist_aktiv("nein")


def test_nummernvorschlag():
    assert naechste_materialnr() == "1"
    material(materialnr="MAT-0099")
    assert naechste_materialnr() == "MAT-0100"


def test_liste_suche_und_gruppe(chef_client):
    material()
    material(materialnr="M-002", bezeichnung="Topfband 35 mm", produktgruppe="Beschläge", lagerplatz="Regal 4")
    seite = chef_client.get(reverse("material:liste"), {"suche": "regal 4"}).content.decode()
    assert "Topfband" in seite and "Spanplatte" not in seite
    seite = chef_client.get(reverse("material:liste"), {"gruppe": "Platten"}).content.decode()
    assert "Spanplatte" in seite and "Topfband" not in seite


def test_inaktives_ausgeblendet(chef_client):
    material(aktiv=False)
    assert "Spanplatte" not in chef_client.get(reverse("material:liste")).content.decode()
    assert "Spanplatte" in chef_client.get(reverse("material:liste"), {"alle": "1"}).content.decode()


def test_preis_deutsch_angezeigt(chef_client):
    m = material()
    assert "12,50 €" in chef_client.get(reverse("material:detail", args=[m.pk])).content.decode()


def test_anlegen_mit_komma_preis(chef_client):
    antwort = chef_client.post(reverse("material:neu"), {
        "materialnr": "M-9", "bezeichnung": "Kante ABS", "ek_netto": "0,85", "aktiv": "on"}, follow=True)
    assert "wurde angelegt" in antwort.content.decode()
    assert Material.objects.get(materialnr="M-9").ek_netto == Decimal("0.85")
    assert Protokolleintrag.objects.filter(aktion="material_angelegt").exists()


def test_negativer_preis_abgelehnt(chef_client):
    antwort = chef_client.post(reverse("material:neu"), {"materialnr": "M-9", "bezeichnung": "X", "ek_netto": "-1"})
    assert "negative" in antwort.content.decode()


def test_preisaenderung_im_protokoll(chef_client):
    m = material()
    chef_client.post(reverse("material:bearbeiten", args=[m.pk]), {
        "materialnr": "M-001", "bezeichnung": "Spanplatte Eiche 19 mm", "produktgruppe": "Platten",
        "einheit": "m²", "ek_netto": "13,90", "aktiv": "on"})
    m.refresh_from_db()
    assert m.ek_netto == Decimal("13.90")
    assert "13.90" in Protokolleintrag.objects.get(aktion="material_geaendert").details


def test_mitarbeiter_sieht_keine_einkaufspreise_und_darf_nicht_aendern(client, benutzer_mit_rolle):
    m = material()
    client.force_login(benutzer_mit_rolle(Rolle.MITARBEITER))
    detail = client.get(reverse("material:detail", args=[m.pk])).content.decode()
    assert "Spanplatte" in detail and "12,50" not in detail and "Einkaufspreis" not in detail
    assert "EK netto" not in client.get(reverse("material:liste")).content.decode()
    assert client.get(reverse("material:neu")).status_code == 403


def test_meister_darf_bearbeiten(client, benutzer_mit_rolle):
    client.force_login(benutzer_mit_rolle(Rolle.MEISTER))
    assert client.get(reverse("material:neu")).status_code == 200


def test_formular_zeigt_zahlen_ohne_ueberfluessige_nullen(chef_client):
    m = material(staerke_mm=Decimal("19.00"), mindestbestand=Decimal("2.500"))
    inhalt = chef_client.get(reverse("material:bearbeiten", args=[m.pk])).content.decode()
    assert 'value="12,50"' in inhalt and 'value="19"' in inhalt and 'value="2,5"' in inhalt


@pytest.mark.parametrize("wert,mind,erwartet", [
    (Decimal("12.5000"), 2, "12,50"), (Decimal("19.00"), 0, "19"), (Decimal("100"), 2, "100,00"),
    (Decimal("0.8500"), 2, "0,85"), (Decimal("1E+2"), 0, "100"),
])
def test_deutsche_zahl(wert, mind, erwartet):
    from material.formulare import deutsche_zahl
    assert deutsche_zahl(wert, mind) == erwartet
