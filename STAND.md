# STAND – PFALZ-WERK Neubau

Letzte Aktualisierung: 12.11.2026

## Arbeitsweise mit Chris (immer beachten)
- Chris ist Anfänger. Jede Aufgabe an Chris wird **ausdrücklich Schritt für Schritt** beschrieben:
  welche Seite/welcher Ordner, welcher Knopf, was getippt wird, was danach zu sehen ist.
- Keine Fachbegriffe ohne Erklärung. Nichts voraussetzen (auch nicht Herunterladen, Entpacken, Starten).
- Alles, was Claude selbst erledigen kann, erledigt Claude selbst. Chris bekommt nur Aufgaben,
  die wirklich nur er tun kann (auf seinem Rechner, Passwörter, echte Daten, Abnahme).
  Kleine Entscheidungen trifft Claude mit der sicheren Variante und sagt es dazu.
- Bei jeder Auslieferung die Fassungsnummer in `kern/kontext.py` (FASSUNG) erhöhen – Chris sieht sie im Navi
  oben und kann so prüfen, ob die neue Fassung läuft. Aktuell: Fassung 1.4 (Material).
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

## Etappe 1 – Kern: in Arbeit

### Paket 1: Kunden – ABGENOMMEN am 10.11.2026
- Echte Excel importiert: 2 Kunden, keine Probleme (Chris bestätigt: stimmt).
- Kundenliste mit Suche (Name, Nr., Ort, Telefon, E-Mail, Adresse), nur aktive oder alle; am Handy schlanker.
- Kundenkarte, Anlegen, Bearbeiten. Nummernvorschlag im bisherigen Muster (K-007 → K-008, 41 → 42).
- Kunden werden nie gelöscht, nur „Inaktiv“. Jede Anlage/Änderung im Protokoll mit alt → neu.
- Rechte: alle dürfen ansehen; Chef, Admin, Buchhaltung, Meister dürfen anlegen/ändern; Mitarbeiter nicht.
- Excel-Import Blatt „Kunden“ (Spalten A–I, Zeilen 4–97 wie im Makro); Adresse wird in Straße/PLZ/Ort zerlegt,
  Original bleibt gespeichert. Bestehende Nummern werden nie überschrieben. Probelauf zeigt jetzt schon
  „würde neu angelegt“ / „schon vorhanden“ und Fehler (doppelte Nr., fehlender Name, ungültige E-Mail).
- Import-Gerüst kann jetzt feste Spaltenbuchstaben und Reihenfolge (Kunden vor Projekten).

### Zwischenpaket: Navigation (Wunsch von Chris) – ABGENOMMEN am 10.11.2026
- Auf jeder Seite eine Leiste: „← Zurück“, „⌂ Start“, „☰ Navi“ und Pfadangabe (Start › Kunden › K-001).
- Navi (runder Knopf unten rechts oder Taste N): alle Bereiche auf einen Blick, gruppiert wie in der Excel
  (Büro & Planung, Werkstatt & Material, Geld, Verwaltung); nur was die Rolle darf; Künftiges grau mit Etappe.
- Kundenkarte: „‹ Vorheriger“ / „Nächster ›“ und „Kunde 2 von 3“.
- Das Navi-Rad der Excel selbst konnte Claude nicht sehen (nicht in den Makro-Dateien) – Aussehen ggf. nach
  Bildschirmfoto von Chris angleichen.

### Paket 2: Projekte – gebaut, wartet auf Abnahme durch Chris
- Projektliste mit Suche (Nr., Name, Kunde, Pate, Projektart, nächster Schritt) und Filter
  „Nur offene“ (ohne Abgeschlossen/Erledigt/Storniert/Abgerechnet/Archiviert) / „Alle“ / je Status.
- Projektkarte mit Blätterpfeilen, Link zum Kunden; Anlegen/Bearbeiten mit Nummernvorschlag,
  Datumsauswahl, Vorschlagslisten für Status/Projektart/Pate (freie Eingabe bleibt möglich).
- Kundenkarte zeigt die Projekte des Kunden und „+ Neues Projekt für diesen Kunden“.
- Kunden mit Projekten sind technisch gegen Löschen geschützt; inaktive Kunden nicht für neue Projekte wählbar.
- Änderungen im Protokoll (Kundenwechsel mit Namen).
- Excel-Import Blatt „Projekte“ (A–AL, Zeilen 4–300 wie im Makro); Kunden werden immer zuerst gelesen;
  Fehler: fehlender/unbekannter Kunde, doppelte Nr., fehlender Name. Unlesbares Datum → Hinweis im Projekt.
- 127 automatische Tests, alle grün.
- Startprobleme 12.11.: alte Fassung lief noch; Startprogramm erkennt das jetzt und schreibt FEHLERBERICHT.txt.
  Danach lief Fassung 1.3 bei Chris („läuft“). Import der echten Projekte noch nicht von Chris gemeldet.

### Paket 3: Material – gebaut, wartet auf Abnahme durch Chris
- Materialliste mit Suche (Nr., Bezeichnung, Gruppe, Untergruppe, Format, Lagerplatz), Filter Produktgruppe,
  nur aktive / alle; Materialkarte mit Blätterpfeilen; Anlegen/Bearbeiten mit Komma-Zahlen, Vorschlagslisten.
- Einkaufs- und Referenzpreise sehen nur Chef, Admin, Buchhaltung, Meister (nicht Mitarbeiter).
- Material wird nie gelöscht, nur inaktiv; Änderungen (auch Preise) im Protokoll.
- Excel-Import Blatt „Material“, Zeilen 4–350, Spalten wie Makro PFALZ_WERK_SQL_MaterialLager (DEV-28.9A):
  A Nr, B Produktgruppe, C Bezeichnung, D Einheit, E EK netto, F Mindestbestand, H Lieferzeit, I Preishinweis,
  T Untergruppe, U Stärke, V Format, W Lagerartikel (Ja/Wahr/1/X), X Aktiv (Inaktiv/Nein/0 = inaktiv),
  Y Beschaffungsart, AF Zielbestand, AH Lagerplatz, AI Referenzpreis brutto, AK Preisquelle, AL Preisstand.
  Unlesbare Zahlen/Daten → leer + Hinweis im Material (Makro setzte stillschweigend 0).
- Noch NICHT übernommen (Etappe 3, Lager): Blatt „Lager“ – A Material-Nr., D Bestand, E Reserviert, I Lagerort.
- 158 automatische Tests, alle grün.

### Offen
- Abnahme Projekte und Material durch Chris inkl. Import mit der echten Excel.
- Paket 4: Lieferanten, danach Mitarbeiter (Excel-Aufbau dieser Blätter noch unbekannt – kein Makro in Drive gefunden).

## Nächstes Paket
Etappe 1, Paket 4: **Lieferanten** – Excel-Aufbau des Blatts klären (Bildschirmfoto der Kopfzeile von Chris oder Makro).

### Vorlage: Excel-Fassung (aus Makro PFALZ_WERK_SQL_Erstuebertragung.bas, Stand DEV-28.4)
Excel-Datei liegt in Chris' Google Drive: „Pfalz-Werk_Weniger_Buero_mehr_Handwerk_aktuell.xlsm“ (ca. 9 MB,
zu groß zum direkten Einlesen in der Sitzung – Import läuft im Programm auf Chris' Rechner).
Daten ab Zeile 4 (Kopf vermutlich Zeile 3). Zuordnung nach **Spaltenbuchstaben**, nicht nach Überschrift.

Blatt **Kunden** (Zeilen 4–97):
| Spalte | Inhalt | Regel |
|---|---|---|
| A | Kunden-Nr. | Pflicht, eindeutig |
| B | Name / Firma | Pflicht |
| C | Ansprechpartner | |
| D | Telefon | |
| E | E-Mail | |
| F | Adresse (ein Feld, Original behalten) | |
| G | Kundenart | leer → „Unbekannt“ |
| I | Hinweise | |
Status neuer Kunden: „Aktiv“. Bestehende Nummern werden beim Import übersprungen, nicht überschrieben.

Blatt **Projekte** (Zeilen 4–300):
| Spalte | Inhalt | Regel |
|---|---|---|
| A | Projekt-Nr. | Pflicht, eindeutig |
| B | Projektname | Pflicht |
| C | Kunden-Nr. | Pflicht, muss als Kunde existieren |
| D | Phase | |
| E | Status | leer → „Planung“ |
| F | Projektpate | |
| G / H | Startdatum / Zieldatum | |
| K | Risiko | |
| L | Nächster Schritt | |
| Y, sonst S | Projektart | leer → „Nicht zugeordnet“ |
| AL | Anfrage-ID | |
Reihenfolge beim Import: erst Kunden, dann Projekte; alles in einem Rutsch oder gar nicht.
