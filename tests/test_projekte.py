import datetime as dt

import pytest
from django.urls import reverse

from kern.models import Protokolleintrag
from konten.models import Rolle
from kunden.models import Kunde
from projekte.ansichten import naechste_projektnr
from projekte.models import Projekt

pytestmark = pytest.mark.django_db


@pytest.fixture
def weber():
    return Kunde.objects.create(kundennr="K-1", name="Familie Weber")


def projekt(kunde, **werte):
    daten = {"projektnr": "P-001", "name": "Einbauküche", "kunde": kunde}
    daten.update(werte)
    return Projekt.objects.create(**daten)


def test_nummernvorschlag(weber):
    assert naechste_projektnr() == "1"
    projekt(weber, projektnr="P-2026-009")
    assert naechste_projektnr() == "P-2026-010"


def test_liste_zeigt_nur_offene(chef_client, weber):
    projekt(weber)
    projekt(weber, projektnr="P-002", name="Alte Treppe", status="Abgeschlossen")
    inhalt = chef_client.get(reverse("projekte:liste")).content.decode()
    assert "Einbauküche" in inhalt and "Alte Treppe" not in inhalt
    alle = chef_client.get(reverse("projekte:liste"), {"status": "alle"}).content.decode()
    assert "Alte Treppe" in alle


@pytest.mark.parametrize("suchwort", ["küche", "P-001", "weber", "K-1"])
def test_suche(chef_client, weber, suchwort):
    projekt(weber)
    andere = Kunde.objects.create(kundennr="K-2", name="Schmitt")
    projekt(andere, projektnr="X-9", name="Treppe")
    inhalt = chef_client.get(reverse("projekte:liste"), {"suche": suchwort}).content.decode()
    assert "Einbauküche" in inhalt and "Treppe" not in inhalt


def test_projekt_anlegen_mit_protokoll(chef_client, weber):
    antwort = chef_client.post(reverse("projekte:neu"), {
        "projektnr": "P-005", "name": "Badmöbel", "kunde": weber.pk, "status": "Planung",
        "startdatum": "2026-11-01", "zieldatum": "2026-12-15"}, follow=True)
    assert "wurde angelegt" in antwort.content.decode()
    p = Projekt.objects.get(projektnr="P-005")
    assert p.kunde == weber and p.zieldatum == dt.date(2026, 12, 15)
    assert Protokolleintrag.objects.filter(aktion="projekt_angelegt").exists()


def test_neues_projekt_vom_kunden_aus_hat_kunden_vorausgewaehlt(chef_client, weber):
    inhalt = chef_client.get(reverse("projekte:neu"), {"kunde": weber.pk}).content.decode()
    assert f'<option value="{weber.pk}" selected>' in inhalt


def test_zieldatum_vor_startdatum_wird_abgelehnt(chef_client, weber):
    antwort = chef_client.post(reverse("projekte:neu"), {
        "projektnr": "P-6", "name": "X", "kunde": weber.pk, "status": "Planung",
        "startdatum": "2026-12-01", "zieldatum": "2026-11-01"})
    assert "vor dem Startdatum" in antwort.content.decode()


def test_doppelte_projektnr_abgelehnt(chef_client, weber):
    projekt(weber)
    antwort = chef_client.post(reverse("projekte:neu"), {"projektnr": "p-001", "name": "X", "kunde": weber.pk, "status": "Planung"})
    assert "schon vergeben" in antwort.content.decode()


def test_kundenwechsel_im_protokoll_mit_namen(chef_client, weber):
    p = projekt(weber)
    schmitt = Kunde.objects.create(kundennr="K-2", name="Schmitt")
    chef_client.post(reverse("projekte:bearbeiten", args=[p.pk]), {
        "projektnr": "P-001", "name": "Einbauküche", "kunde": schmitt.pk, "status": "Planung"})
    eintrag = Protokolleintrag.objects.get(aktion="projekt_geaendert")
    assert "Familie Weber" in eintrag.details and "Schmitt" in eintrag.details


def test_kunde_zeigt_seine_projekte(chef_client, weber):
    projekt(weber)
    inhalt = chef_client.get(reverse("kunden:detail", args=[weber.pk])).content.decode()
    assert "Einbauküche" in inhalt and "Projekte dieses Kunden (1)" in inhalt


def test_inaktive_kunden_nicht_fuer_neue_projekte(chef_client, weber):
    Kunde.objects.create(kundennr="K-9", name="Weggezogen", status=Kunde.Status.INAKTIV)
    inhalt = chef_client.get(reverse("projekte:neu")).content.decode()
    assert "Familie Weber" in inhalt and "Weggezogen" not in inhalt


def test_kunde_mit_projekten_kann_nicht_geloescht_werden(weber):
    from django.db.models import ProtectedError
    projekt(weber)
    with pytest.raises(ProtectedError):
        weber.delete()


def test_mitarbeiter_nur_lesen(client, benutzer_mit_rolle, weber):
    p = projekt(weber)
    client.force_login(benutzer_mit_rolle(Rolle.MITARBEITER))
    assert "Einbauküche" in client.get(reverse("projekte:detail", args=[p.pk])).content.decode()
    assert client.get(reverse("projekte:neu")).status_code == 403
    assert client.get(reverse("projekte:bearbeiten", args=[p.pk])).status_code == 403


def test_blaettern(chef_client, weber):
    a, b = projekt(weber, projektnr="P-1"), projekt(weber, projektnr="P-2")
    inhalt = chef_client.get(reverse("projekte:detail", args=[b.pk])).content.decode()
    assert a.get_absolute_url() in inhalt and "Projekt 1 von 2" in inhalt
