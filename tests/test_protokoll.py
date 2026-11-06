import pytest

from kern.models import Protokolleintrag, ProtokollGesperrt, protokolliere

pytestmark = pytest.mark.django_db


def test_eintrag_wird_geschrieben(chef):
    e = protokolliere("test", "Gegenstand", "Details", benutzer=chef)
    assert e.benutzername == "chef" and e.zeitpunkt is not None


def test_eintrag_kann_nicht_geaendert_werden(chef):
    e = protokolliere("test", benutzer=chef)
    e.aktion = "verfälscht"
    with pytest.raises(ProtokollGesperrt):
        e.save()


def test_eintrag_kann_nicht_geloescht_werden(chef):
    e = protokolliere("test", benutzer=chef)
    with pytest.raises(ProtokollGesperrt):
        e.delete()
    with pytest.raises(ProtokollGesperrt):
        Protokolleintrag.objects.all().delete()
    with pytest.raises(ProtokollGesperrt):
        Protokolleintrag.objects.update(aktion="x")
    assert Protokolleintrag.objects.filter(aktion="test").count() == 1


def test_protokollseite_zeigt_eintraege(chef_client, chef):
    protokolliere("sonderaktion", "Werkbank 3", benutzer=chef)
    assert "Werkbank 3" in chef_client.get("/protokoll/").content.decode()
