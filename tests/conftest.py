import pytest

from konten.models import Benutzer, Rolle


@pytest.fixture(autouse=True)
def eigene_ordner(settings, tmp_path):
    settings.SICHERUNG_DIR = tmp_path / "sicherungen"
    settings.IMPORT_DIR = tmp_path / "importe"


@pytest.fixture
def benutzer_mit_rolle(db):
    def anlegen(rolle, name=None):
        return Benutzer.objects.create_user(username=name or rolle, password="Hobelbank-2026", rolle=rolle)
    return anlegen


@pytest.fixture
def chef(benutzer_mit_rolle):
    return benutzer_mit_rolle(Rolle.CHEF)


@pytest.fixture
def chef_client(client, chef):
    client.force_login(chef)
    return client
