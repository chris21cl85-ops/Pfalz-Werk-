import pytest
from django.urls import reverse

from konten.models import Rolle

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client, benutzer_mit_rolle):
    client.force_login(benutzer_mit_rolle(Rolle.ADMIN, "admin1"))
    return client


def test_admin_kann_chef_nicht_aendern(admin_client, chef):
    url = reverse("admin:konten_benutzer_change", args=[chef.pk])
    antwort = admin_client.post(url, {"username": "chef", "rolle": Rolle.MITARBEITER})
    chef.refresh_from_db()
    assert chef.rolle == Rolle.CHEF
    assert antwort.status_code in (200, 403)


def test_admin_kann_chef_passwort_nicht_aendern(admin_client, chef):
    url = reverse("admin:auth_user_password_change", args=[chef.pk])
    admin_client.post(url, {"password1": "Neues-Passwort-9", "password2": "Neues-Passwort-9"})
    chef.refresh_from_db()
    assert chef.check_password("Hobelbank-2026")


def test_admin_kann_niemanden_zum_chef_machen(admin_client):
    inhalt = admin_client.get(reverse("admin:konten_benutzer_add")).content.decode()
    assert 'value="meister"' in inhalt
    assert 'value="chef"' not in inhalt


def test_admin_kann_mitarbeiter_aendern(admin_client, benutzer_mit_rolle):
    m = benutzer_mit_rolle(Rolle.MITARBEITER, "max")
    url = reverse("admin:konten_benutzer_change", args=[m.pk])
    assert admin_client.get(url).status_code == 200


def test_chef_kann_chef_rolle_vergeben(chef_client):
    inhalt = chef_client.get(reverse("admin:konten_benutzer_add")).content.decode()
    assert 'value="chef"' in inhalt


def test_passwortseite_des_chefs_fuer_admin_gesperrt(admin_client, chef):
    assert admin_client.get(reverse("admin:auth_user_password_change", args=[chef.pk])).status_code == 403


def test_gruppen_sind_ausgeblendet(chef_client):
    assert "Gruppen" not in chef_client.get(reverse("admin:index")).content.decode()
