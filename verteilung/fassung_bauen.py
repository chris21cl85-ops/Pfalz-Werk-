"""Baut die Fassung zum Installieren (Windows, ohne vorher installiertes Python).

Ergebnis in --ziel (Standard: dist/):
  PFALZ-WERK/                      Programmordner mit eingebettetem Python (python/), allen Paketen und Startdatei
  PFALZ-WERK-<Fassung>-Windows.zip derselbe Ordner gepackt (zum Entpacken ohne Setup)
Das Setup-Programm (PFALZ-WERK-Setup.exe) baut danach Inno Setup aus verteilung/PFALZ-WERK.iss.

Aufruf (auf GitHub automatisch, siehe .github/workflows/fassung.yml):
  python verteilung/fassung_bauen.py --embed python-3.13.1-embed-amd64.zip
Ohne --embed wird nur der Programmteil + Pakete gebaut (zum Prüfen unter Linux).
"""
import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
WEGLASSEN = {".git", ".github", "tests", "dist", "verteilung", "__pycache__", ".umgebung", ".pytest_cache", "doku",
             "conftest.py", "pytest.ini", "starten.sh", "FEHLERBERICHT.txt", "PFALZ-WERK starten.bat"}
# Laufzeit-Pakete (ohne Test-Werkzeuge); tzdata braucht Django unter Windows (keine Zeitzonen-Datenbank im System)
PAKETE = ["Django>=5.2,<6", "openpyxl>=3.1,<4", "reportlab>=4.0,<6", "tzdata"]

STARTDATEI = """@echo off
title PFALZ-WERK
cd /d "%~dp0"
set PYTHONUTF8=1
python\\python.exe start.py
if errorlevel 1 pause
"""


def fassung() -> str:
    text = (WURZEL / "kern" / "kontext.py").read_text(encoding="utf-8")
    treffer = re.search(r'FASSUNG = "Fassung ([0-9.]+)', text)
    return treffer.group(1) if treffer else "0"


def programm_kopieren(ziel: Path):
    def ignorieren(ordner, namen):
        return [n for n in namen if n in WEGLASSEN or n.endswith((".pyc", ".log"))]
    for eintrag in WURZEL.iterdir():
        if eintrag.name in WEGLASSEN or eintrag.name.startswith("."):
            continue
        if eintrag.is_dir():
            shutil.copytree(eintrag, ziel / eintrag.name, ignore=ignorieren)
        else:
            shutil.copy2(eintrag, ziel / eintrag.name)


def python_einbetten(embed_zip: Path, ziel: Path):
    """Eingebettetes Python entpacken und so einstellen, dass es site-packages und den Programmordner findet."""
    py = ziel / "python"
    with zipfile.ZipFile(embed_zip) as z:
        z.extractall(py)
    pth = next(py.glob("python3*._pth"))
    zeilen = [z for z in pth.read_text(encoding="utf-8").splitlines() if z.strip() and z.strip() != "#import site"]
    zeilen = [z for z in zeilen if z.strip() != "import site"]
    pth.write_text("\n".join(zeilen + ["Lib\\site-packages", "..", "import site"]) + "\n", encoding="utf-8")
    return py


def pakete_installieren(site: Path, python_version="3.13"):
    site.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                           "--target", str(site), "--platform", "win_amd64", "--python-version", python_version,
                           "--implementation", "cp", "--only-binary=:all:", "--upgrade", *PAKETE])


def zip_packen(ordner: Path, datei: Path):
    with zipfile.ZipFile(datei, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(ordner.rglob("*")):
            if f.is_file():
                z.write(f, Path(ordner.name) / f.relative_to(ordner))


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--embed", type=Path, help="python-3.x.y-embed-amd64.zip von python.org")
    a.add_argument("--ziel", type=Path, default=WURZEL / "dist")
    a.add_argument("--ohne-zip", action="store_true")
    args = a.parse_args()
    nummer = fassung()
    programm = args.ziel / "PFALZ-WERK"
    if programm.exists():
        shutil.rmtree(programm)
    programm.mkdir(parents=True)
    print(f"PFALZ-WERK Fassung {nummer}: Programm kopieren …")
    programm_kopieren(programm)
    # write_bytes: unter Windows würde write_text aus \r\n ein \r\r\n machen
    (programm / "PFALZ-WERK starten.bat").write_bytes(STARTDATEI.replace("\n", "\r\n").encode("ascii"))
    (programm / "FASSUNG.txt").write_bytes(f"PFALZ-WERK Fassung {nummer}\r\n".encode("utf-8"))
    if args.embed:
        print("Python einbetten …")
        py = python_einbetten(args.embed, programm)
        site = py / "Lib" / "site-packages"
    else:
        site = programm / "python" / "Lib" / "site-packages"
    print("Pakete für Windows holen …")
    pakete_installieren(site)
    if not args.ohne_zip:
        datei = args.ziel / f"PFALZ-WERK-{nummer}-Windows.zip"
        print(f"Packen: {datei.name} …")
        zip_packen(programm, datei)
    print(f"Fertig: {programm}")


if __name__ == "__main__":
    main()
