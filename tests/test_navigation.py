import pytest
from django.urls import reverse

from konten.models import Rolle
from kunden.models import Kunde

pytestmark = pytest.mark.django_db


def test_navi_auf_jeder_seite(chef_client):
    for url in ["/", reverse("kunden:liste"), reverse("sicherung:uebersicht"), reverse("protokoll")]:
        inhalt = chef_client.get(url).content.decode()
        assert 'id="navi"' in inhalt and "← Zurück" in inhalt and "⌂ Start" in inhalt


def test_navi_nicht_auf_anmeldeseite(client):
    assert 'id="navi"' not in client.get(reverse("anmelden")).content.decode()


def test_navi_zeigt_bereiche_und_ziele(chef_client):
    inhalt = chef_client.get("/").content.decode()
    for text in ["Büro &amp; Planung", "Werkstatt &amp; Material", "Geld", "Verwaltung",
                 f'href="{reverse("kunden:liste")}"', "kommt in Etappe 2"]:
        assert text in inhalt


def test_navi_mitarbeiter_ohne_verwaltung_und_geld(client, benutzer_mit_rolle):
    client.force_login(benutzer_mit_rolle(Rolle.MITARBEITER))
    inhalt = client.get(reverse("kunden:liste")).content.decode()
    assert "Verwaltung</h3>" not in inhalt and "<h3>Geld</h3>" not in inhalt
    assert "Büro &amp; Planung" in inhalt


def test_pfadangabe(chef_client):
    k = Kunde.objects.create(kundennr="K-7", name="Weber")
    inhalt = chef_client.get(reverse("kunden:detail", args=[k.pk])).content.decode()
    assert "› K-7" in inhalt and f'href="{reverse("kunden:liste")}">Kunden</a>' in inhalt


def test_blaettern_zwischen_kunden(chef_client):
    a = Kunde.objects.create(kundennr="1", name="Anton")
    b = Kunde.objects.create(kundennr="2", name="Berta")
    c = Kunde.objects.create(kundennr="3", name="Cäsar")
    inhalt = chef_client.get(reverse("kunden:detail", args=[b.pk])).content.decode()
    assert a.get_absolute_url() in inhalt and c.get_absolute_url() in inhalt and "Kunde 2 von 3" in inhalt
    erste = chef_client.get(reverse("kunden:detail", args=[a.pk])).content.decode()
    assert "‹ Vorheriger" not in erste and "Nächster ›" in erste
