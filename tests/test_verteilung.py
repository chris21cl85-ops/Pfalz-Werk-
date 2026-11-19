"""Paket 9: Fassung zum Installieren (eingebettetes Python, Bauskript, Startlogik)."""
import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent


def _laden(name, datei):
    spec = importlib.util.spec_from_file_location(name, WURZEL / datei)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture
def start():
    return _laden("pw_start", "start.py")


@pytest.fixture
def bauen():
    return _laden("pw_bauen", "verteilung/fassung_bauen.py")


def test_ohne_eingebettetes_python_wird_umgebung_benutzt(start, tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ORDNER", tmp_path)
    assert start.eingebaut() is False


def test_eingebettetes_python_braucht_keine_installation(start, tmp_path, monkeypatch):
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "python.exe").write_bytes(b"")
    monkeypatch.setattr(start, "ORDNER", tmp_path)
    monkeypatch.setattr(start, "UMGEBUNG", tmp_path / ".umgebung")
    assert start.eingebaut() is True
    assert start.vorbereiten() == Path(sys.executable)
    assert not (tmp_path / ".umgebung").exists()  # kein venv, kein pip


def test_fassungsnummer_aus_kontext(bauen):
    from kern.kontext import FASSUNG
    assert bauen.fassung() in FASSUNG


def test_programm_ohne_tests_und_werkzeuge(bauen, tmp_path):
    bauen.programm_kopieren(tmp_path)
    namen = {p.name for p in tmp_path.iterdir()}
    assert {"manage.py", "start.py", "pfalzwerk", "moebel", "vorlagen", "ANLEITUNG.md"} <= namen
    assert not namen & {"tests", ".git", ".github", "verteilung", "conftest.py", "lokal", "dist"}
    assert not list(tmp_path.rglob("__pycache__"))
    assert not list(tmp_path.rglob("*.sqlite3"))


def test_eingebettetes_python_findet_pakete_und_programm(bauen, tmp_path):
    embed = tmp_path / "embed.zip"
    with zipfile.ZipFile(embed, "w") as z:
        z.writestr("python313._pth", "python313.zip\n.\n\n# Uncomment to run site.main() automatically\n#import site\n")
        z.writestr("python.exe", b"")
    ziel = tmp_path / "PFALZ-WERK"
    ziel.mkdir()
    py = bauen.python_einbetten(embed, ziel)
    zeilen = (py / "python313._pth").read_text(encoding="utf-8").splitlines()
    assert zeilen[:2] == ["python313.zip", "."]
    assert "Lib\\site-packages" in zeilen and ".." in zeilen
    assert zeilen[-1] == "import site" and "#import site" not in zeilen


def test_startdatei_nutzt_eingebettetes_python(bauen):
    assert "python\\python.exe start.py" in bauen.STARTDATEI
    assert "py -3" not in bauen.STARTDATEI


def test_pakete_fuer_windows_ohne_testwerkzeuge(bauen):
    namen = " ".join(bauen.PAKETE)
    assert "Django" in namen and "openpyxl" in namen and "reportlab" in namen and "tzdata" in namen
    assert "pytest" not in namen


def test_zip_enthaelt_programmordner(bauen, tmp_path):
    ordner = tmp_path / "PFALZ-WERK"
    (ordner / "kern").mkdir(parents=True)
    (ordner / "kern" / "a.py").write_text("x")
    datei = tmp_path / "f.zip"
    bauen.zip_packen(ordner, datei)
    assert zipfile.ZipFile(datei).namelist() == ["PFALZ-WERK/kern/a.py"]


def test_setup_loescht_keine_daten():
    iss = (WURZEL / "verteilung" / "PFALZ-WERK.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss
    assert '{app}\\*"' not in iss  # nie den ganzen Programmordner leeren (Notfall-Datenordner „lokal“)
    assert "German.isl" in iss


def test_startdatei_und_fassung_mit_windows_zeilenenden(bauen, tmp_path, monkeypatch):
    monkeypatch.setattr(bauen, "pakete_installieren", lambda site: None)
    monkeypatch.setattr(sys, "argv", ["x", "--ziel", str(tmp_path), "--ohne-zip"])
    bauen.main()
    bat = (tmp_path / "PFALZ-WERK" / "PFALZ-WERK starten.bat").read_bytes()
    assert b"\r\n" in bat and b"\r\r\n" not in bat
    assert (tmp_path / "PFALZ-WERK" / "FASSUNG.txt").read_bytes() == f"PFALZ-WERK Fassung {bauen.fassung()}\r\n".encode()
