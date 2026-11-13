# FEHLER – bekannte Fehler und Einschränkungen

| Nr | Datum | Bereich | Beschreibung | Status |
|----|-------|---------|--------------|--------|
| 1 | 06.11.2026 | Rechte | Ein Admin konnte auch den Chef-Zugang bearbeiten. Jetzt: nur der Chef ändert den Chef-Zugang. Auf Wunsch umkehrbar. | erledigt 07.11.2026 |
| 2 | 06.11.2026 | Start | Start per Doppelklick braucht installiertes Python 3.12+ unter Windows; ein Installer ohne Python folgt mit der Verkaufsfassung (Etappe 4). | bekannt |
| 3 | 06.11.2026 | Sicherung | Sicherungen liegen auf demselben Rechner. Für echten Schutz den Ordner `Dokumente/PFALZ-WERK-Daten/sicherungen` zusätzlich auf USB/NAS kopieren lassen (später automatisieren). | offen |
| 4 | 13.11.2026 | Start | Start brach ab: Windows ließ keinen Datenordner in „Dokumente“ anlegen (FileNotFoundError, vermutlich überwachter Ordnerzugriff/OneDrive). Jetzt automatischer Ausweichordner %LOCALAPPDATA%\\PFALZ-WERK-Daten; Startfenster zeigt den Datenordner. | behoben 13.11.2026 (Fassung 1.8) |
| 5 | 13.11.2026 | GitHub | Das Projekt `Pfalz-Werk-` ist auf GitHub **öffentlich** (laut STAND sollte es privat sein). Es stehen keine Passwörter oder Kundendaten im Code, aber der Programmcode ist für jeden sichtbar. Umstellen kann nur Chris: GitHub → Projekt → Settings → ganz unten „Change visibility“ → „Make private“. | offen |
| 6 | 13.11.2026 | Rechnungen | Eine festgeschriebene Rechnung kann noch nicht storniert werden. Seit Fassung 2.3 per Storno möglich; Test-Rechnungen und ihr Storno verbrauchen trotzdem Nummern und bleiben sichtbar (GoBD). | erledigt 13.11.2026 (Fassung 2.3) |
| 7 | 13.11.2026 | XRechnung | Die XML-Dateien sind gegen das offizielle Schema geprüft und alle Pflichtregeln (BR-DE, EN 16931 Summen) sind als Tests nachgebaut. Das offizielle KoSIT-Prüfprogramm konnte in der Bau-Umgebung nicht ausgeführt werden. Bitte eine echte XRechnung einmal in einem Online-Prüfdienst hochladen (siehe STAND.md, Paket 1b, Schritt 4). | offen – Prüfung durch Chris |
| 8 | 13.11.2026 | XRechnung | Rechnungen, die vor Fassung 2.1 festgeschrieben wurden, haben keine XRechnung und bekommen auch keine mehr (sie sind gesperrt). Falls nötig: stornieren und neu ausstellen (geht seit Fassung 2.3). | bekannt |
| 9 | 13.11.2026 | Rechnungen | Bei Rechnungen mit Skonto zeigte die Rechnungsseite nach dem Neuladen „Prüfsumme stimmt nicht“, obwohl nichts verändert war (Skonto wurde einmal als „2“, einmal als „2.00“ eingerechnet). Behoben; bereits festgeschriebene Skonto-Rechnungen werden wieder als in Ordnung erkannt. | behoben 13.11.2026 (Fassung 2.2) |
