# FEHLER – bekannte Fehler und Einschränkungen

| Nr | Datum | Bereich | Beschreibung | Status |
|----|-------|---------|--------------|--------|
| 1 | 06.11.2026 | Rechte | Ein Admin konnte auch den Chef-Zugang bearbeiten. Jetzt: nur der Chef ändert den Chef-Zugang. Auf Wunsch umkehrbar. | erledigt 07.11.2026 |
| 2 | 06.11.2026 | Start | Start per Doppelklick braucht installiertes Python 3.12+ unter Windows; ein Installer ohne Python folgt mit der Verkaufsfassung (Etappe 4). | bekannt |
| 3 | 06.11.2026 | Sicherung | Sicherungen liegen auf demselben Rechner. Für echten Schutz den Ordner `Dokumente/PFALZ-WERK-Daten/sicherungen` zusätzlich auf USB/NAS kopieren lassen (später automatisieren). | offen |
| 4 | 13.11.2026 | Start | Start brach ab: Windows ließ keinen Datenordner in „Dokumente“ anlegen (FileNotFoundError, vermutlich überwachter Ordnerzugriff/OneDrive). Jetzt automatischer Ausweichordner %LOCALAPPDATA%\\PFALZ-WERK-Daten; Startfenster zeigt den Datenordner. | behoben 13.11.2026 (Fassung 1.8) |
| 5 | 13.11.2026 | GitHub | Das Projekt `Pfalz-Werk-` ist auf GitHub **öffentlich** (laut STAND sollte es privat sein). Es stehen keine Passwörter oder Kundendaten im Code, aber der Programmcode ist für jeden sichtbar. Umstellen kann nur Chris: GitHub → Projekt → Settings → ganz unten „Change visibility“ → „Make private“. | offen |
| 6 | 13.11.2026 | Rechnungen | Eine festgeschriebene Rechnung kann noch nicht storniert werden (Storno kommt in Etappe 2, Paket 3). Test-Rechnungen verbrauchen daher eine echte Nummer und bleiben bestehen. | bekannt bis Paket 3 |
