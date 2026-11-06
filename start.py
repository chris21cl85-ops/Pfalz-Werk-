"""Startet PFALZ-WERK: Pakete prüfen, Datenbank aktualisieren, sichern, Browser öffnen."""
import os
import subprocess
import sys
import threading
import time
import venv
import webbrowser
from pathlib import Path

ORDNER = Path(__file__).resolve().parent
UMGEBUNG = ORDNER / ".umgebung"
ADRESSE = "127.0.0.1:8000"


def python_der_umgebung() -> Path:
    unter = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return UMGEBUNG / unter


def vorbereiten():
    py = python_der_umgebung()
    if not py.exists():
        print("Erster Start: richte Programmumgebung ein (einmalig, ca. 1 Minute) ...")
        venv.create(UMGEBUNG, with_pip=True)
    marke = UMGEBUNG / "pakete.txt"
    soll = (ORDNER / "requirements.txt").read_text(encoding="utf-8")
    if not marke.exists() or marke.read_text(encoding="utf-8") != soll:
        print("Installiere benötigte Pakete ...")
        subprocess.check_call([str(py), "-m", "pip", "install", "-q", "-r", str(ORDNER / "requirements.txt")])
        marke.write_text(soll, encoding="utf-8")
    return py


def main():
    py = vorbereiten()
    verwalten = [str(py), str(ORDNER / "manage.py")]
    subprocess.check_call(verwalten + ["migrate", "--noinput", "-v", "0"])
    subprocess.check_call(verwalten + ["ersteinrichtung"])
    subprocess.check_call(verwalten + ["sicherung", "--wenn-faellig"])

    def browser_oeffnen():
        time.sleep(2)
        webbrowser.open(f"http://{ADRESSE}/")

    threading.Thread(target=browser_oeffnen, daemon=True).start()
    print(f"\nPFALZ-WERK läuft unter http://{ADRESSE}/  –  Fenster offen lassen. Beenden mit Strg+C.\n")
    subprocess.call(verwalten + ["runserver", ADRESSE, "--noreload", "--insecure"])


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as fehler:
        print(f"\nFEHLER beim Start: {fehler}")
        input("Eingabetaste drücken zum Schließen ...")
        sys.exit(1)
