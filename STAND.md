# STAND – PFALZ-WERK Neubau

Letzte Aktualisierung: 09.11.2026

## Arbeitsweise mit Chris (immer beachten)
- Chris ist Anfänger. Jede Aufgabe an Chris wird **ausdrücklich Schritt für Schritt** beschrieben:
  welche Seite/welcher Ordner, welcher Knopf, was getippt wird, was danach zu sehen ist.
- Keine Fachbegriffe ohne Erklärung. Nichts voraussetzen (auch nicht Herunterladen, Entpacken, Starten).
- Alles, was Claude selbst erledigen kann, erledigt Claude selbst. Chris bekommt nur Aufgaben,
  die wirklich nur er tun kann (auf seinem Rechner, Passwörter, echte Daten, Abnahme).
  Kleine Entscheidungen trifft Claude mit der sicheren Variante und sagt es dazu.
- Grundanleitung zum Installieren, Herunterladen und Starten: `ANLEITUNG.md`.

## Etappe 0 – Fundament: ABGENOMMEN am 09.11.2026

### Erledigt
- Projektgerüst Django 5.2, SQLite im Datenordner (nicht im Git), geheimer Schlüssel wird beim ersten Start erzeugt.
- Start per Doppelklick (`PFALZ-WERK starten.bat`): richtet Umgebung ein, aktualisiert Datenbank,
  fragt beim allerersten Start den Chef-Zugang ab (Passwort tippt Chris), sichert, öffnet Browser.
- Anmeldung/Abmeldung/Passwort ändern, alles auf Deutsch. Ohne Anmeldung ist jede Seite gesperrt.
- Fünf Rollen: Chef, Admin, Buchhaltung, Meister, Mitarbeiter. Startseite zeigt je Rolle nur passende Kacheln;
  noch nicht gebaute Bereiche erscheinen grau mit Etappe.
- Benutzerverwaltung (Chef/Admin) unter „Benutzer“; Benutzer werden deaktiviert, nicht gelöscht.
- Chef-Schutz: Nur der Chef darf den Chef-Zugang ändern und die Rolle Chef vergeben (Admin nicht).
- Datenordner getrennt vom Programm: Dokumente/PFALZ-WERK-Daten (Update ohne Kopieren).
- Passwörter nur gehasht (Django PBKDF2), Mindestlänge 8.
- Protokoll: unveränderbar, nicht löschbar; erfasst Anmeldung, Fehlversuche, Abmeldung, Sicherung, Import.
- Sicherung: täglich automatisch beim Start, Knopf „Jetzt sichern“, vor jedem Import; Kopie wird auf
  Beschädigung geprüft; alte Sicherungen werden nie gelöscht.
- Import-Gerüst: Excel hochladen → Probelauf (zeigt Blätter, Zeilen, Probleme) → „Daten übernehmen“
  (vorher Sicherung, danach Protokoll). Echte Blätter werden in Etappe 1 angebunden.
- 64 automatische Tests, alle grün.
- Auf GitHub: `chris21cl85-ops/Pfalz-Werk-` (privat), Zweig `main`.

### Abnahme
- Von Chris am 09.11.2026 abgenommen („passt“). Programm läuft auf seinem Rechner.
- Klickweg „Mitarbeiter anlegen / als Mitarbeiter anmelden“ hat Chris nicht selbst durchgeklickt;
  ist durch automatische Tests abgedeckt. Beim ersten echten Mitarbeiter-Zugang kurz mitprüfen.
- Excel-Import wird mit der echten Excel-Datei zu Beginn von Etappe 1 getestet.

### So testest du es
Vorher einmalig `ANLEITUNG.md` Teil A bis C durchgehen.
1. Doppelklick `PFALZ-WERK starten.bat` → Chef-Zugang anlegen → Browser öffnet die Anmeldung → anmelden.
2. Kachel „Benutzer“ → „Benutzer hinzufügen“ → z. B. „max“ als Mitarbeiter anlegen → abmelden,
   als max anmelden → nur Werkstatt-Kacheln, keine Verwaltung.
3. Als Chef: „Sicherung“ → „Jetzt sichern“ → neue Zeile in der Liste; Speicherort wird angezeigt.
4. Als Chef: „Excel-Import“ → PFALZ-WERK-Excel wählen → „Datei prüfen“ → Liste der Tabellenblätter mit Zeilenzahl.
5. Als Chef: „Protokoll“ → Anmeldungen, Fehlversuch (vorher falsches Passwort tippen), Sicherung sind sichtbar.

## Nächstes Paket
Etappe 1, Paket 1: **Kunden** – Datenmodell, Liste/Suche/Anlegen/Bearbeiten, Import aus dem Excel-Blatt
„Kunden“. Dafür braucht Claude die Excel-Datei: Chris legt sie in Google Drive ab
(Claude liest sie dort über die Google-Drive-Verbindung).
