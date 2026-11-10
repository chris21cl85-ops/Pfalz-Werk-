import socket
import subprocess
import sys

import pytest

import start


def test_erkennt_laufendes_programm(monkeypatch):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    monkeypatch.setattr(start, "ADRESSE", f"127.0.0.1:{s.getsockname()[1]}")
    try:
        assert start.laeuft_schon()
    finally:
        s.close()
    assert not start.laeuft_schon()


def test_fehlerbericht_wird_geschrieben(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(start, "ORDNER", tmp_path)
    with pytest.raises(SystemExit):
        start.schritt([sys.executable, "-c", "import sys; sys.exit('Datenbank ist gesperrt')"], "Testschritt")
    ausgabe = capsys.readouterr().out
    assert "FEHLER bei: Testschritt" in ausgabe and "Datenbank ist gesperrt" in ausgabe
    assert "Datenbank ist gesperrt" in (tmp_path / "FEHLERBERICHT.txt").read_text(encoding="utf-8")


def test_erfolgreicher_schritt(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ORDNER", tmp_path)
    start.schritt([sys.executable, "-c", "print('ok')"], "Testschritt")
    assert not (tmp_path / "FEHLERBERICHT.txt").exists()
