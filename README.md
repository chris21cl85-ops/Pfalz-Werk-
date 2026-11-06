# PFALZ-WERK

Betriebsprogramm für die Schreinerei – Neubau der Excel/VBA-Fassung als Browser-Programm
(Python + Django, SQLite).

## Starten
- **Windows:** Doppelklick auf `PFALZ-WERK starten.bat` (Python 3.12 oder neuer muss installiert sein).
- **Mac/Linux:** `./starten.sh`

Beim ersten Start wird die Umgebung eingerichtet und der Chef-Zugang abgefragt.
Danach öffnet sich der Browser unter http://127.0.0.1:8000/. Das schwarze Fenster offen lassen.

## Wo liegen die Daten?
Alles Betriebliche liegt im Ordner `lokal/` (nicht in GitHub):
Datenbank, geheimer Schlüssel, Sicherungen (`lokal/sicherungen/`), hochgeladene Importdateien.

## Tests
```
pip install -r requirements.txt
python -m pytest
```
Ein roter Test stoppt die Auslieferung.

## Stand
Siehe `STAND.md` und `FEHLER.md`.
