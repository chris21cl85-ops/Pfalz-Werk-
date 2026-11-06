import pytest
from django.urls import reverse

from kern.models import Protokolleintrag
from konten.models import Benutzer, Rolle

pytestmark = pytest.mark.django_db


def test_ohne_anmeldung_wird_zur_anmeldung_umgeleitet(client):
    antwort = client.get("/")
    assert antwort.status_code == 302
    assert antwort.url.startswith(reverse("anmelden"))


def test_anmeldeseite_ist_deutsch(client):
    inhalt = client.get(reverse("anmelden")).content.decode()
    assert "Anmelden" in inhalt and "Passwort" in inhalt


def test_anmelden_mit_richtigem_passwort(client, chef):
    antwort = client.post(reverse("anmelden"), {"username": "chef", "password": "Hobelbank-2026"})
    assert antwort.status_code == 302
    assert client.get("/").status_code == 200


def test_falsches_passwort_wird_abgelehnt_und_protokolliert(client, chef):
    antwort = client.post(reverse("anmelden"), {"username": "chef", "password": "falsch"})
    assert antwort.status_code == 200
    assert "stimmt nicht" in antwort.content.decode()
    assert Protokolleintrag.objects.filter(aktion="anmeldung_fehlgeschlagen", gegenstand="chef").exists()


def test_passwort_wird_nur_gehasht_gespeichert(chef):
    chef.refresh_from_db()
    assert "Hobelbank-2026" not in chef.password
    assert chef.password.startswith(("pbkdf2_", "argon2", "bcrypt", "scrypt"))


def test_anmeldung_und_abmeldung_werden_protokolliert(client, chef):
    client.post(reverse("anmelden"), {"username": "chef", "password": "Hobelbank-2026"})
    client.post(reverse("abmelden"))
    aktionen = list(Protokolleintrag.objects.values_list("aktion", flat=True))
    assert "anmeldung" in aktionen and "abmeldung" in aktionen


def test_deaktivierter_benutzer_kann_sich_nicht_anmelden(client, benutzer_mit_rolle):
    b = benutzer_mit_rolle(Rolle.MEISTER)
    b.is_active = False
    b.save()
    client.post(reverse("anmelden"), {"username": b.username, "password": "Hobelbank-2026"})
    assert client.get("/").status_code == 302


@pytest.mark.parametrize("rolle,verwaltung", [
    (Rolle.CHEF, True), (Rolle.ADMIN, True), (Rolle.BUCHHALTUNG, False),
    (Rolle.MEISTER, False), (Rolle.MITARBEITER, False),
])
def test_nur_chef_und_admin_duerfen_verwalten(benutzer_mit_rolle, rolle, verwaltung):
    b = benutzer_mit_rolle(rolle)
    assert b.darf_verwalten is verwaltung
    assert b.is_staff is verwaltung


def test_es_gibt_genau_fuenf_rollen():
    assert {r.label for r in Rolle} == {"Chef", "Admin", "Buchhaltung", "Meister", "Mitarbeiter"}


def test_ersteinrichtung_legt_chef_an(monkeypatch):
    from django.core.management import call_command
    eingaben = iter(["chris", "Chris", "Muster"])
    monkeypatch.setattr("builtins.input", lambda *_: next(eingaben))
    monkeypatch.setattr("getpass.getpass", lambda *_: "Hobelbank-2026")
    call_command("ersteinrichtung")
    b = Benutzer.objects.get(username="chris")
    assert b.rolle == Rolle.CHEF and b.is_superuser and b.check_password("Hobelbank-2026")


def test_ersteinrichtung_tut_nichts_wenn_benutzer_existieren(chef, monkeypatch):
    from django.core.management import call_command
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("darf nicht fragen"))
    call_command("ersteinrichtung")
    assert Benutzer.objects.count() == 1
