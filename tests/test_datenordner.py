from pathlib import Path

import pytest
from django.conf import settings

import pfalzwerk.settings as s


def test_datenordner_in_tests_ist_temporaer():
    assert Path(settings.LOKAL_DIR).resolve() != (settings.BASE_DIR / "lokal").resolve()


@pytest.fixture
def umgebung(monkeypatch, tmp_path):
    monkeypatch.delenv("PFALZWERK_LOKAL", raising=False)
    heim = tmp_path / "heim"
    (heim / "Documents").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: heim)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(s, "BASE_DIR", tmp_path / "programm")
    return heim, tmp_path


def test_standard_ist_dokumente(umgebung):
    heim, _ = umgebung
    assert s._datenordner() == heim / "Documents" / "PFALZ-WERK-Daten"


def test_dokumente_gesperrt_dann_appdata(umgebung, monkeypatch):
    heim, tmp = umgebung
    echt = s._beschreibbar
    monkeypatch.setattr(s, "_beschreibbar", lambda o: False if "Documents" in str(o) else echt(o))
    assert s._datenordner() == tmp / "appdata" / "PFALZ-WERK-Daten"


def test_vorhandene_daten_haben_vorrang(umgebung):
    _, tmp = umgebung
    vorhanden = tmp / "appdata" / "PFALZ-WERK-Daten"
    vorhanden.mkdir(parents=True)
    (vorhanden / "pfalzwerk.sqlite3").write_bytes(b"")
    assert s._datenordner() == vorhanden


def test_alte_ablage_im_programmordner_hat_vorrang(umgebung):
    _, tmp = umgebung
    alt = tmp / "programm" / "lokal"
    alt.mkdir(parents=True)
    (alt / "pfalzwerk.sqlite3").write_bytes(b"")
    assert s._datenordner() == alt


def test_nirgends_schreibbar_gibt_verstaendlichen_fehler(umgebung, monkeypatch):
    monkeypatch.setattr(s, "_beschreibbar", lambda o: False)
    with pytest.raises(RuntimeError, match="keinen Ordner"):
        s._datenordner()


def test_beschreibbar_erkennt_gesperrten_ordner(tmp_path):
    datei = tmp_path / "keinordner"
    datei.write_text("x")
    assert s._beschreibbar(tmp_path / "neu") is True
    assert s._beschreibbar(datei / "unter") is False  # Elternteil ist eine Datei → OSError
