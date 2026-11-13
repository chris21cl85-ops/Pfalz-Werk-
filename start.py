"""Startet PFALZ-WERK: Pakete prüfen, Datenbank aktualisieren, sichern, Browser öffnen."""
import os
import socket
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


def laeuft_schon() -> bool:
    """Prüft, ob schon ein PFALZ-WERK (z. B. eine alte Fassung) auf dem Port läuft."""
    host, port = ADRESSE.split(":")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, int(port))) == 0


def schritt(befehl, was):
    """Führt einen Schritt aus. Bei Fehler: verständliche Meldung + Fehlertext in Datei."""
    ergebnis = subprocess.run(befehl, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if ergebnis.stdout:
        print(ergebnis.stdout, end="")
    if ergebnis.returncode != 0:
        datei = ORDNER / "FEHLERBERICHT.txt"
        datei.write_text(f"Schritt: {was}\nBefehl: {befehl}\n\n{ergebnis.stdout}\n{ergebnis.stderr}", encoding="utf-8")
        letzte = [z for z in ergebnis.stderr.strip().splitlines() if z.strip()][-1:] or ["(keine Meldung)"]
        print(f"\nFEHLER bei: {was}")
        print(f"Ursache: {letzte[0]}")
        print(f"\nDer vollständige Fehlertext steht in:\n  {datei}")
        print("Bitte diese Datei an Claude schicken (oder ein Bildschirmfoto dieses Fensters).")
        raise SystemExit(1)


def main():
    if laeuft_schon():
        print("PFALZ-WERK läuft bereits in einem anderen Fenster (vielleicht eine ältere Fassung).")
        print("Bitte ALLE schwarzen PFALZ-WERK-Fenster schließen und dann erneut starten.")
        raise SystemExit(1)
    py = vorbereiten()
    verwalten = [str(py), str(ORDNER / "manage.py")]
    schritt(verwalten + ["datenordner"], "Datenordner finden")
    schritt(verwalten + ["migrate", "--noinput", "-v", "0"], "Datenbank aktualisieren")
    subprocess.check_call(verwalten + ["ersteinrichtung"])  # fragt evtl. nach Eingaben, daher direkt
    schritt(verwalten + ["sicherung", "--wenn-faellig"], "Tägliche Sicherung")

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
    except SystemExit as ende:
        if ende.code:
            input("\nEingabetaste drücken zum Schließen ...")
        raise
