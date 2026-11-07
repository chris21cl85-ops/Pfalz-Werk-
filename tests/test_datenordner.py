from pathlib import Path

from django.conf import settings


def test_datenordner_liegt_nicht_im_programmordner_ausser_bei_altbestand():
    # In Tests ist der Ordner per Umgebungsvariable auf einen Temp-Ordner gesetzt
    assert Path(settings.LOKAL_DIR).resolve() != (settings.BASE_DIR / "lokal").resolve()


def test_standard_datenordner(monkeypatch, tmp_path):
    import pfalzwerk.settings as s
    monkeypatch.delenv("PFALZWERK_LOKAL", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "Documents").mkdir()
    assert s._datenordner() == tmp_path / "Documents" / "PFALZ-WERK-Daten"
