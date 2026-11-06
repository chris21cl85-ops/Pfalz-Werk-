import sqlite3

import pytest
from django.core.management import call_command
from django.urls import reverse

from kern.models import Protokolleintrag
from sicherung.dienst import heute_gesichert, sicherung_anlegen, sicherung_wenn_faellig, sicherungen

pytestmark = pytest.mark.django_db(transaction=True)


def test_sicherung_ist_lesbare_datenbank_mit_daten(chef):
    pfad = sicherung_anlegen(benutzer=chef)
    assert pfad.exists()
    with sqlite3.connect(pfad) as db:
        namen = [z[0] for z in db.execute("select username from konten_benutzer")]
    assert "chef" in namen


def test_sicherung_wird_protokolliert(chef):
    pfad = sicherung_anlegen(benutzer=chef)
    assert Protokolleintrag.objects.filter(aktion="sicherung", gegenstand=pfad.name).exists()


def test_taegliche_sicherung_nur_einmal_pro_tag(db):
    assert not heute_gesichert()
    assert sicherung_wenn_faellig() is not None
    assert heute_gesichert()
    assert sicherung_wenn_faellig() is None
    assert len(sicherungen()) == 1


def test_mehrere_sicherungen_ueberschreiben_sich_nicht(db):
    a, b = sicherung_anlegen(), sicherung_anlegen()
    assert a != b and a.exists() and b.exists()


def test_befehl_sicherung(db, capsys):
    call_command("sicherung", "--wenn-faellig")
    assert "angelegt" in capsys.readouterr().out


def test_knopf_jetzt_sichern(chef_client):
    antwort = chef_client.post(reverse("sicherung:anlegen"), follow=True)
    assert "wurde angelegt" in antwort.content.decode()
    assert len(sicherungen()) == 1
