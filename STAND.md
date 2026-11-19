# STAND – PFALZ-WERK Neubau

Letzte Aktualisierung: 19.11.2026

## Arbeitsweise mit Chris (immer beachten)
- Chris ist Anfänger. Jede Aufgabe an Chris wird **ausdrücklich Schritt für Schritt** beschrieben:
  welche Seite/welcher Ordner, welcher Knopf, was getippt wird, was danach zu sehen ist.
- Keine Fachbegriffe ohne Erklärung. Nichts voraussetzen (auch nicht Herunterladen, Entpacken, Starten).
- Alles, was Claude selbst erledigen kann, erledigt Claude selbst. Chris bekommt nur Aufgaben,
  die wirklich nur er tun kann (auf seinem Rechner, Passwörter, echte Daten, Abnahme).
  Kleine Entscheidungen trifft Claude mit der sicheren Variante und sagt es dazu.
- In jeder „So testest du es“-Anleitung zuerst den Download-Schritt nennen (ANLEITUNG Teil B) – die Startdatei
  lädt keine neue Fassung (am 13.11. bei Fassung 2.0–2.2 vergessen → Chris sah weiter 1.8).
- Bei jeder Auslieferung die Fassungsnummer in `kern/kontext.py` (FASSUNG) erhöhen – Chris sieht sie im Navi
  oben und kann so prüfen, ob die neue Fassung läuft. Aktuell: Fassung 5.5 (Etappe 5, Paket 6 Kapazität).
- **Excel-Aufbau aller 120 Blätter** (von Chris, Stand 04.11.2026): `doku/EXCEL_AUFBAU_aller_Blaetter.txt` –
  vor jedem neuen Paket dort nachsehen, statt Chris nach Bildschirmfotos zu fragen.
- Grundanleitung zum Installieren, Herunterladen und Starten: `ANLEITUNG.md`.
- Achtung GitHub: Das Programm liegt in **`chris21cl85-ops/Pfalz-Werk-`** (mit Bindestrich am Ende).
  `chris21cl85-ops/Pfalz-Werk` (ohne Bindestrich) ist ein leeres Projekt – dort nichts ablegen.

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
- Datenordner getrennt vom Programm: Dokumente/PFALZ-WERK-Daten; ist „Dokumente“ von Windows gesperrt,
  automatisch %LOCALAPPDATA%\PFALZ-WERK-Daten (Fassung 1.8). Vorhandene Datenbank hat immer Vorrang.
  Das Startfenster zeigt „Daten und Sicherungen liegen in: …“.
- Passwörter nur gehasht (Django PBKDF2), Mindestlänge 8.
- Protokoll: unveränderbar, nicht löschbar; erfasst Anmeldung, Fehlversuche, Abmeldung, Sicherung, Import.
- Sicherung: täglich automatisch beim Start, Knopf „Jetzt sichern“, vor jedem Import; Kopie wird auf
  Beschädigung geprüft; alte Sicherungen werden nie gelöscht.
- Import-Gerüst: Excel hochladen → Probelauf (zeigt Blätter, Zeilen, Probleme) → „Daten übernehmen“
  (vorher Sicherung, danach Protokoll). Echte Blätter werden in Etappe 1 angebunden.
- 64 automatische Tests, alle grün.
- Auf GitHub: `chris21cl85-ops/Pfalz-Werk-`, Zweig `main` (laut GitHub am 13.11.2026 **öffentlich** – siehe FEHLER.md Nr. 5).

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

## Etappe 1 – Kern: ABGENOMMEN am 13.11.2026 (Fassung 1.8, echter Import ok)

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

### Paket 2: Projekte – ABGENOMMEN am 13.11.2026 (echter Import ok)
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

### Paket 3: Material – ABGENOMMEN am 13.11.2026 (echter Import ok)
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

### Paket 4+5: Lieferanten und Mitarbeiter – ABGENOMMEN am 13.11.2026
- Lieferanten: Liste/Suche, Karte mit allem Material des Lieferanten, Anlegen/Bearbeiten (Adresse, Portal,
  unsere Kunden-Nr., Zahlungsziel, Skonto). Sehen/bearbeiten: Chef, Admin, Buchhaltung, Meister.
  Ein eigenes Lieferanten-Blatt gibt es in der Excel nicht – Lieferanten entstehen beim Import aus
  Material-Spalte G; bei schon vorhandenem Material wird ein fehlender Lieferant ergänzt (sonst nichts geändert).
- Material hat jetzt ein Feld „Lieferant“ (Auswahl im Formular, Anzeige auf der Karte).
- Mitarbeiter (nur Chef/Admin): Kürzel, Name, Rolle im Betrieb, Telefon, Team-täglich verfügbar, Montage leiten,
  Verfügbarkeit, Arbeitstage/-zeit, Eintritt, Wochenstunden, Urlaub, Stundensatz (für Kalkulation, von Hand),
  Verknüpfung mit Programm-Zugang. Ausgeschiedene = inaktiv, nie löschen.
- Import Blatt „Mitarbeiter“ (A–J, ab Zeile 4) + „Dashboard Steuerung“ (A, AB, AD, AJ ab Zeile 6, füllt nur
  leere Felder). PINs werden nicht übernommen; eine PIN im Hinweistext wird geschwärzt.
- Import-Bericht zeigt „+ x ergänzt“ und neu angelegte Lieferanten; Blattvorschau (Zeilen 1–5) für alle
  nicht angebundenen Blätter, damit der Excel-Aufbau ohne Excel sichtbar ist.
- Nachtrag 13.11. (Fassung 1.7): Mitarbeiter auch M Arbeitszeitmodell, N Einsatzmuster, O Abwesenheit/
  Einschränkung; Formelzeilen ohne Kürzel/Name werden still übersprungen (Blatt hat ~1000 Formelzeilen).
- Noch nicht übernommene Excel-Spalten (bei Bedarf nachziehen): Kunden H „Seit“, K „Kuerzel“;
  Material AE Meldebestand, AG Bestell-/Gebindegröße, AJ Referenzpreis netto, AM Preisart, AN Verlässlichkeit.
- 175 automatische Tests, alle grün.

## Etappe 2 – Geld: ABGENOMMEN am 15.11.2026

### Paket 1a: Rechnungen (Firmendaten, Entwurf, Festschreiben, PDF) – ABGENOMMEN am 13.11.2026 („kann weiter gehen“)
Fachliche Vorlage: Makro `PW_Rechnung.bas` (Drive, Stand 26.10.2026), vollständig gelesen.
- Neue Kachel „Rechnungen“ und „Firmendaten“ (Bereich Geld). Rechte wie `Darf()` im Makro: Chef, Admin, Buchhaltung.
  Meister/Mitarbeiter sehen Rechnungen nicht (auch nicht auf der Projektkarte).
- **Firmendaten** (20 Felder wie FDNAMEN im Makro): Firma, Inhaber, Adresse, Telefon, E-Mail, Steuernr., USt-IdNr.,
  IBAN/BIC/Bank, Zahlungsziel, Kleinunternehmer, USt-Satz, Präfix, letzte Rechnungsnummer, Fußtext, Mahngebühr.
  Pflicht für Rechnungen: Firma, Straße, PLZ, Ort, IBAN, Steuernr. oder USt-IdNr. Letzte Nummer darf nur steigen.
  Excel-Import Blatt „Firmendaten“ (A Feld, B Wert, ab Zeile 4), Zuordnung über Feldnamen; füllt nur leere Felder;
  unbekannte Feldnamen werden im Import-Bericht genannt (Excel hat 24 Zeilen, Makro nutzt 20).
- **Ablauf**: „+ Neue Rechnung“ (oder von der Projektkarte) → Art wählen → **Entwurf** (ohne Nummer, frei änderbar,
  Vorschau-PDF mit Aufdruck ENTWURF) → Haken „geprüft“ → **Festschreiben**.
  - Arten wie im Makro: Rechnung (Positionen frei, max. 25), Abschlagsrechnung (x % vom Auftragswert, Text wie Makro,
    § 632a BGB), Schlussrechnung (Auftragswert minus alle festgeschriebenen Abschläge als Minuspositionen).
    Den Auftragswert gibt man von Hand ein (Blatt „Aufträge“ gibt es im Programm noch nicht); er wird fürs Projekt
    gemerkt und bei der nächsten Rechnung vorgeschlagen.
  - Zahlungsziele wie Makro: sofort / 14 / 30 Tage / 14 Tage mit 2 % Skonto in 7 Tagen. Vorbelegung aus Firmendaten.
  - Beim Festschreiben: Nummer `Präfix + Jahr + - + 4 Stellen` (RE-2026-0001), fortlaufend über die Firmendaten-Nummer
    (wie B21 im Makro, keine Lücken, keine Doppelten); Datum, Fälligkeit, Summen (Position auf Cent, USt auf Netto),
    Kopie von Firmen- und Kundenanschrift, PDF und **Prüfsumme** (SHA-256 über Inhalt + PDF) werden gespeichert.
  - Danach **gesperrt**: Ändern/Löschen von Rechnung und Positionen ist technisch unmöglich (auch an der Oberfläche
    vorbei). Prüfsumme wird auf der Rechnungsseite angezeigt (✔ / ✖ bei Manipulation).
  - Entwürfe werden nicht gelöscht, sondern „verworfen“ (bekommen nie eine Nummer).
  - PDF wie Drucken() im Makro: Briefkopf, Absenderzeile, Anschrift, Angaben rechts, Positionstabelle, Summen,
    Zahlungstext mit Fälligkeit/Skonto, § 19 UStG (Kleinunternehmer), § 14b UStG (Privatkunden), Fußtext,
    Fußzeile mit Firma/Bank/Steuernummer. PDF liegt in der Datenbank → ist in jeder Sicherung enthalten.
  - Protokoll: Entwurf angelegt/geändert/verworfen, festgeschrieben (mit Beträgen und Prüfsumme), PDF abgerufen,
    Firmendaten geändert.
- Neues Paket `reportlab` (PDF) – wird beim Start automatisch installiert.
- 213 automatische Tests, alle grün.

### So testest du es (Paket 1a)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Die Startdatei allein lädt nichts nach!
Im Navi oben muss die neue Fassungsnummer stehen.
1. Kachel **Firmendaten** → alle Felder ausfüllen (echte Daten tippst du selbst) → „Speichern“.
   Oder: Excel-Import erneut durchlaufen lassen → Firmendaten werden aus der Excel übernommen.
2. Ein Projekt öffnen → unten „+ Rechnung für dieses Projekt“ → Art „Rechnung“ → „Entwurf anlegen“ →
   eine Position eintragen (z. B. „Test“, Menge 1, Preis 100,00) → „Speichern“.
3. „Vorschau-PDF“ → PDF mit rotem Aufdruck ENTWURF prüfen.
4. Haken „geprüft“ setzen → „Rechnung festschreiben“ → Nummer RE-2026-…, „PDF ansehen“, grüner Haken „Prüfsumme“.
   Hinweis: Eine festgeschriebene Test-Rechnung verbraucht eine echte Nummer und bleibt für immer (Storno kommt in
   Paket 3). Zum Testen am besten erst mit einer Kopie arbeiten – oder bewusst die erste echte Rechnung nehmen.
5. „Abschlagsrechnung“ mit Auftragswert 10.000,00 und 30 % → Entwurf zeigt 3.000,00 € netto.

### Paket 1b: XRechnung – ABGENOMMEN am 13.11.2026 („passt“)
Vorlage: `XmlSchreiben()`, `Einheitcode()`, `AdrXml()` aus `PW_Rechnung.bas` – Aufbau 1:1 übernommen
(UN/CEFACT CII, XRechnung 3.0, Kennung `urn:xeinkauf.de:kosit:xrechnung_3.0`, Peppol-Prozess).
- Pro Rechnung Auswahl „E-Rechnung (XRechnung)“: automatisch (Firmen/Behörden ja, Privatkunden nein), ja, nein.
  Im Entwurf als Haken änderbar. Neues Feld „Leitweg-ID / Bestellzeichen des Kunden“ (BT-10); leer = Kunden-Nr.
- XML wird beim Festschreiben erzeugt, in der Datenbank gespeichert (also in jeder Sicherung) und gehört zur
  Prüfsumme. Ältere Rechnungen ohne XML behalten ihre Prüfsumme unverändert.
- Knopf „⬇ XRechnung (XML)“ auf der Rechnungsseite; Abruf wird protokolliert.
- Wie im Makro: Typ 380 Rechnung / 326 Abschlag; Kleinunternehmer = Steuerkategorie E mit Befreiungsgrund;
  Skonto im Pflichtformat `#SKONTO#TAGE=7#PROZENT=2.00#`; Abzüge als negative Menge bei positivem Preis;
  Einheiten: lfm/m→MTR, m²/qm→MTK, m³→MTQ, Std→HUR, kg→KGM, l→LTR, sonst C62.
- Vor dem Festschreiben geprüft: Firmendaten Telefon + E-Mail + Steuernr./USt-IdNr.; Kunde braucht Straße, PLZ, Ort
  in eigenen Feldern.
- IBAN wird in den Firmendaten jetzt auf die Prüfziffer geprüft (Regel BR-DE-19).
- **Prüfung**: Beim Bau alle Beispiele (Rechnung mit Skonto, Abschlag, Schluss mit Abzügen, Kleinunternehmer)
  gegen das offizielle CII-Schema D16B geprüft → gültig. Alle Pflichtregeln BR-DE der XRechnung 3.0 und die
  Summenregeln der EN 16931 sind als automatische Tests nachgebaut. Das offizielle KoSIT-Prüfprogramm (Java)
  durfte in der Sitzung nicht laufen → siehe FEHLER.md Nr. 7 (einmal von Chris prüfen lassen).
- 237 automatische Tests, alle grün.

### So testest du es (Paket 1b)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Die Startdatei allein lädt nichts nach!
Im Navi oben muss die neue Fassungsnummer stehen.
1. Firmendaten: Telefon und E-Mail müssen ausgefüllt sein.
2. Einen Kunden öffnen, der eine Firma ist (Kundenart nicht „Privat“) und Straße, PLZ, Ort hat → Projekt →
   „+ Rechnung für dieses Projekt“ → bei „E-Rechnung“ steht „Automatisch“ → Entwurf anlegen, Position eintragen.
3. Auf der Rechnungsseite steht „E-Rechnung: ja“. Festschreiben → Knopf „⬇ XRechnung (XML)“ erscheint.
4. Prüfen beim Amt (kostenlos, ohne Anmeldung): Im Browser die Seite des offiziellen Prüfdienstes öffnen,
   z. B. „xrechnung validator online“ suchen (Anbieter KoSIT oder ein bekannter Anbieter wie „ERPEL“ / „Belegmeister“),
   die heruntergeladene XML-Datei hochladen → Ergebnis muss „gültig / valid“ sein. Ergebnis an Claude melden.
5. Eine Rechnung für einen Privatkunden anlegen → „E-Rechnung: nein (nur PDF)“.

### Paket 2: Zahlungen – ABGENOMMEN am 13.11.2026 (Fassung 2.2 läuft bei Chris)
Vorlage: `ZahlungBuchen()` und Zahlungsteil von `Zusammenfassung()` in `PW_Rechnung.bas`.
- Neue Tabelle Zahlungen wie Blatt „Zahlungen“: Z-Nr. (Z-0001 fortlaufend), Datum, Richtung „Ein“, Rechnung, Betrag,
  Skonto, Konto (Bank/Bar), erfasst von/am, Notiz.
- Auf der Rechnungsseite „Zahlung buchen“ mit drei Möglichkeiten wie im Makro: voller offener Betrag /
  mit Skonto (offen minus Skonto auf Brutto, Rest als Skonto → erledigt; nur wenn Skonto angeboten) / Teilbetrag.
  Datum nicht in der Zukunft. Nach dem Buchen Meldung mit neuem Status.
- Bezahlt, Offen und Status werden immer aus den Zahlungen **berechnet** (wie die Formeln P/Q/R im Blatt);
  die festgeschriebene Rechnung wird nie verändert. Status: Offen, Teilbezahlt, Bezahlt, Überzahlt, „· überfällig“
  (Fälligkeit vorbei und noch offen).
- Zahlungen sind gesperrt (nie ändern, nie löschen). Vertippt? → „Gegenbuchung“ mit Grund (Minusbuchung, die die
  falsche Zahlung aufhebt), dann richtig neu buchen. Alles im Protokoll.
- Rechnungsliste: Spalte „Offen“, Status farbig, Kasten „Offen gesamt / davon überfällig“ (antippbar),
  Filter Unbezahlt / Überfällig / Bezahlt / Entwürfe / Verworfen. Projektkarte zeigt Offen je Rechnung.
- **Fehler Nr. 9 behoben** (aus Paket 1a): Bei Skonto-Rechnungen zeigte die Prüfsumme nach dem Neuladen fälschlich
  „stimmt nicht“. Schon festgeschriebene Skonto-Rechnungen werden wieder als in Ordnung erkannt.
- 259 automatische Tests, alle grün.

### So testest du es (Paket 2)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Die Startdatei allein lädt nichts nach!
Im Navi oben muss die neue Fassungsnummer stehen.
1. Kachel „Rechnungen“ → eine festgeschriebene Rechnung öffnen → unten „Zahlungen“: Offen = Rechnungsbetrag.
2. „Teilbetrag“ wählen → z. B. 100,00 eintippen → Datum lassen → „Zahlung buchen“ → Status „Teilbezahlt“, Offen kleiner.
3. Bei Z-0001 „vertippt?“ antippen → Grund „Test“ → „Gegenbuchung“ → Offen wieder wie vorher, beide Zeilen grau.
4. „Voller offener Betrag“ → „Zahlung buchen“ → Status „Bezahlt“ (grün), Formular verschwindet.
5. Rechnungsliste → Auswahl „Unbezahlt (offen)“ / „Bezahlt“ ausprobieren; oben steht „Offen gesamt“.
Hinweis: Mit einer echten Rechnung testen ist in Ordnung – Testbuchungen lassen sich per Gegenbuchung aufheben
(bleiben aber sichtbar, wie in der Buchhaltung üblich).

### Paket 3: Mahnungen + Storno – GEBAUT 13.11.2026, Abnahme offen
Vorlage: `Mahnen()`, `Stornieren()`, Mahnteil von `Drucken()`, Statusformeln P/Q/R und Kachel-Regeln aus `PW_Rechnung.bas`.
- **Storno** (Abschnitt „Rechnung stornieren …“ auf der Rechnungsseite, Haken + Grund): Stornorechnung mit nächster
  Nummer, gleiche Positionen mit negativer Menge, Beträge negativ, Bezug „Storno zu“. PDF „Stornorechnung“
  („Hiermit stornieren wir die Rechnung … vollständig“, „Gutschriftsbetrag“, ohne Zahlungsaufforderung).
  XRechnung nur wenn das Original eine hatte: Typ 381, Beträge positiv, Verweis auf Original (Schema geprüft).
  Original bleibt unverändert und zeigt „Storniert durch …“; Offen = 0 (wie Formel Q).
  Regeln wie Makro: nicht bei Storno, nicht doppelt, nicht wenn schon Geld eingegangen (erst Gegenbuchung).
  Stornierte Abschläge zählen nicht mehr (Abschlag-Nr. und Schlussrechnung).
- **Mahnen** (Abschnitt „Erinnern / Mahnen“, solange offen): Zahlungserinnerung / 1. Mahnung / 2. Mahnung
  (+ Mahngebühr aus Firmendaten); nächste Stufe vorausgewählt; neue Frist heute + 7 Tage; PDF wie Makro
  (zusätzlich Anrede „Sehr geehrte Damen und Herren,“ und Grußformel). Mahnungen sind eigene, gesperrte Datensätze
  mit PDF; Status zeigt die letzte Stufe („Offen · überfällig · 1. Mahnung“). Hinweis, wenn noch nicht fällig.
  Mahngebühr steht nur im Schreiben, wird nicht als Forderung gebucht (wie Makro).
- Skonto nur innerhalb der Skonto-Frist (Zahlungsdatum ≤ Rechnungsdatum + 7 Tage) – wie im Makro.
- Rechnungsliste: Filter „Storniert / Storno“.
- 274 automatische Tests, alle grün.

### So testest du es (Paket 3)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 2.3“ stehen.
1. Offene Rechnung öffnen → „Erinnern / Mahnen“ → „Zahlungserinnerung“ ist ausgewählt → „Erinnerung / Mahnung
   erstellen“ → Zeile mit „📄 PDF“ erscheint → PDF ansehen. Status in der Liste zeigt „Zahlungserinnerung“.
2. Nochmal → jetzt ist „1. Mahnung“ vorausgewählt. Bei „2. Mahnung“ steht die Mahngebühr im PDF.
3. Achtung, Storno ist endgültig und verbraucht eine Nummer – nur mit einer Test-Rechnung oder einer, die
   wirklich falsch ist: „Rechnung stornieren …“ aufklappen → Grund → Haken → „Stornieren“ → Stornorechnung erscheint.
4. Zurück zum Original (Link „Storno zu“) → „Storniert durch …“, Offen 0, kein Mahn-/Zahlungsbereich mehr.
5. Rechnungsliste → Auswahl „Storniert / Storno“.

### Zwischenpaket Design – ABGENOMMEN am 15.11.2026 („Der Hammer!“)
Wunsch: an Excel angelehnt, „futuristischer, moderner, fließende Übergänge und Farben“.
- Nur Aussehen (`vorlagen/basis.html`, Startseite, Anmeldung, `kern/module.py` Farben, `kern/views.py` Kennzahlen);
  keine Fachlogik geändert, alle Tests grün.
- Farbwelt: Grün der Excel-Formulare (RGB 53,107,74) als Grundton, Verläufe Richtung Türkis; Bereichsfarben
  Büro Blau-Türkis, Werkstatt Holz/Orange, Geld Grün, Verwaltung Violett. Hintergrund mit weichen Farbflächen.
- Kopfzeile mit Farbverlauf und Logo, Navigationsleiste halb durchsichtig, Karten/Tabellen abgerundet,
  Knöpfe mit Verlauf und Anheben beim Darüberfahren, Auswahlfelder als Karten (gewählte grün hervorgehoben),
  Seiten blenden weich ein; „Bewegung reduzieren“ in Windows wird beachtet.
- Startseite: Kennzahlen (offene Rechnungen, davon überfällig – nur Chef/Admin/Buchhaltung –, offene Projekte;
  antippbar), Kacheln nach Bereichen mit farbigen Symbolen, Hinweis „x überfällig“ an der Rechnungs-Kachel.
- Navi als **Rad**: Ziele gleichmäßig auf dem Ring, Bereiche als farbige Viertel, Startseite in der Mitte, dreht sich
  beim Öffnen auf, passt sich der Fenstergröße an. Auf dem Handy (schmal) als farbige Kachelliste.
- Offen: Excel-Bildschirmfotos hat Chris noch nicht geschickt – bei Bedarf Feinabstimmung nachziehen.
- Symbole sind Windows-Emojis, sehen auf Chris' PC etwas anders aus als auf den Vorschaubildern.

### So testest du es (Design)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 2.4“ stehen.
1. Anmeldeseite und Startseite ansehen: Kennzahlen oben, Kacheln nach Bereichen, Maus über eine Kachel fahren.
2. Runden „Navi“-Knopf unten rechts (oder Taste N) → Rad öffnet sich → ein Ziel anklicken.
3. Rechnungen, Kunden, eine Rechnung öffnen: alles im neuen Aussehen, alles funktioniert wie vorher.
4. Am Handy (gleiches WLAN, falls eingerichtet) oder Browserfenster schmal ziehen → Navi als Kachelliste.

### Paket 4: Eingangsrechnungen – ABGENOMMEN am 15.11.2026 („passt“)
Vorlage: `PW_Eingang.bas` (Erfassen, Bezahlen, DoppelteNr, Statusformeln P/Q/R, KATEGORIEN) – vollständig gelesen.
- Neue Kachel „Eingangsrechnungen“ (Geld; Chef/Admin/Buchhaltung wie `Darf()`).
- Erfassen: Beleg-Nr. ER-0001 fortlaufend; Lieferant (Auswahl oder neuer Name → Lieferant wird angelegt),
  Rechnungs-Nr. des Lieferanten, Datum, Kategorie (6 wie Makro), Projekt oder „Gemeinkosten“, Netto,
  Vorsteuer 19/7/0 %, Zahlungsziel, Skonto % + Frist, Bestell-Nr. (nur Text), Beleg (PDF/JPG/PNG, max. 15 MB,
  in der Datenbank → in jeder Sicherung), Notiz. Vorsteuer/Brutto/Fälligkeit/Skonto-bis automatisch;
  Zahlungsziel/Skonto werden aus der Lieferantenkarte vorgeschlagen. Doppelte (Lieferant + Nr.) abgelehnt.
  „Erfassen und nächste“ für mehrere Belege hintereinander.
- Nach dem Erfassen gesperrt. Fehler → „Erfassung stornieren“ mit Grund (bleibt sichtbar, zählt nicht, Offen 0;
  nur solange nichts bezahlt ist), dann neu erfassen.
- Bezahlen (Zahlung „Aus“ im gemeinsamen Nummernkreis Z-…): mit Skonto (nur innerhalb der Frist und vor der
  ersten Zahlung, wie Makro), voll, Teilbetrag; Gegenbuchung wie bei Ausgangsrechnungen.
- Status wie Formel R: Offen / Teilbezahlt / Überfällig / Bezahlt (+ Storniert).
- Liste: Standard „Offen (zu bezahlen)“ wie im Makro, Kennzahlen „Zu bezahlen“, „davon überfällig“,
  „Skonto noch möglich bei …“; Hinweis „Skonto bis …“ je Zeile; Suche und Filter.
- Lieferantenkarte zeigt dessen Eingangsrechnungen; Projektkarte zeigt „Kosten (Eingangsrechnungen)“ mit Summe netto.
- Noch NICHT: Abgleich mit Bestellungen (Makro `Abgleich()`: Abweichung > max(0,50 €; 2 %)) → kommt mit
  Bestellungen in Etappe 3. Belege-Ordner im Dateisystem (Makro kopierte nach Belege\Jahr) nicht nötig.
- 302 automatische Tests, alle grün.

### So testest du es (Paket 4)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 2.5“ stehen.
1. Kachel „Eingangsrechnungen“ → „+ Neue Eingangsrechnung“ → Lieferant auswählen oder neu eintippen,
   Nummer, Netto (z. B. 1.000,00) → unter Netto erscheint sofort der Bruttobetrag → Beleg (PDF/Foto) wählen →
   „Erfassen“.
2. Dieselbe Rechnung nochmal erfassen → Meldung „schon erfasst“.
3. Beleg öffnen (📎), dann „Bezahlen“ → mit Skonto / voll / Teilbetrag → Status ändert sich.
4. Projekt öffnen, dem die Rechnung zugeordnet ist → unten „Kosten (Eingangsrechnungen)“.
5. Eine Test-Erfassung über „Falsch erfasst? Erfassung stornieren …“ wieder aufheben.

### Paket 5: Finanz-Übersicht + DATEV-Export – ABGENOMMEN am 15.11.2026 („los gehts“)
Vorlage: `PW_FIN_Cockpit`/`CockpitBauen`, `PW_FIN_Export`, `Debitor`, `Kreditor`, `Sachkonto`, `zeile` aus `PW_Eingang.bas`.
- Kachel „Finanzen“ (Chef/Admin/Buchhaltung wie `Darf()`): Kennzahlen Umsatz Jahr netto, offene Forderungen,
  offene Verbindlichkeiten (je mit Anzahl überfällig), USt-Zahllast Vormonat (USt − Vorsteuer, nach Rechnungsdatum);
  Liquidität 6 Wochen ab Montag (Woche 1 inkl. Überfälligem); Deckungsbeitrag je Projekt (Rechnungen netto −
  Eingangsrechnungen netto, berechnet statt Blatt „Finanzen (Vorbereitung)“); Listen offene Forderungen/Verbindlichkeiten.
  Noch ohne Löhne (Makro nahm Brutto aus „Arbeitsverträge“ zum Monatsende) → kommt mit Etappe 4.
- Firmendaten: neue Felder DATEV Beraternummer, Mandantennummer, Wirtschaftsjahr-Beginn, Sachkontenlänge
  (= Excel-Zeilen 24–27, werden jetzt auch importiert; nicht Teil der Rechnungs-Kopie).
- DATEV-Export (Seite mit Monatsauswahl, Standard Vormonat, Vorschau aller Buchungen): ZIP mit
  `EXTF_Buchungsstapel_JJJJ-MM.csv` (Kopf wie Makro: EXTF 700/21/Version 13, Windows-Zeichensatz, CRLF),
  `Offene_Posten_….csv`, `Personenkonten.csv`, `Belege/` (Rechnungs-PDFs, XRechnungen, Eingangsbelege). Protokolliert.
  Buchungen wie Makro: Rechnung brutto S Debitor an 8400/8300/8195; Eingangsrechnung brutto H Kreditor an Sachkonto;
  Zahlung Ein S 1200 an Debitor (+ Skonto); Zahlung Aus H 1200 an Kreditor (+ Skonto); negative Beträge drehen S/H.
  Verbesserungen gegenüber Makro (bitte vom Steuerberater bestätigen lassen):
  BU-Schlüssel 9/8 bei Aufwandskonten ohne Vorsteuer-Automatik (3100, 4530, 4985, 4930, 4900); Material 0 % → 3200;
  Skonto-Konten nach Steuersatz (8736/8731/8730, 3736/3731/3730); Bar → Kasse 1000; Kreditor = 70000 + Programm-Nr.
  des Lieferanten (bleibt stabil); Belegfeld 1 bei Eingangsrechnung und deren Zahlung = Rechnungs-Nr. des Lieferanten
  (für den OP-Ausgleich); stornierte Eingangsrechnung im Storno-Monat gegengebucht; Warnung bei doppelten Debitoren.
  Spaltenkopf nur die ersten 14 DATEV-Spalten (wie Makro) – Probe-Import beim Steuerberater nötig (FEHLER Nr. 10).
- 326 automatische Tests, alle grün.

### So testest du es (Paket 5)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 2.6“ stehen.
1. Kachel „Finanzen“ → Kennzahlen, Liquidität, Deckungsbeitrag ansehen – passen die Zahlen zu deinen Testbuchungen?
2. Firmendaten → DATEV Beraternummer und Mandantennummer eintragen (vom Steuerberater) → Speichern.
3. Finanzen → „▶ DATEV-Export“ → Monat wählen → Vorschau prüfen → „Export … herunterladen (ZIP)“.
4. ZIP öffnen: CSV-Dateien und Ordner „Belege“ ansehen. Die ZIP einmal an den Steuerberater schicken mit der Bitte
   um einen Probe-Import („Buchungsstapel EXTF, SKR03 – bitte prüfen, ob es sauber einliest“).

## Etappe 3 – Werkstatt: IN ARBEIT

### Paket 1: Bestellungen, Wareneingang, Lagerbestand – weitergegeben am 15.11.2026 (Chris: „a und dann b“, kein Fehler gemeldet)
Vorlage: `PW_Bestellassistent.bas`, `PW_Wareneingang.bas`, `PW_Bestellart.bas` (Drive, 20.10.2026), Blätter
„Bestellungen“ (49), „Lager“ (52), „Lagerbewegungen“ (69). Neue App `lager`.
- Kachel „Bestellungen & Lager“ (Chef, Admin, Meister – wie `Berechtigt()`; Freigabe-Anfrage für andere Rollen
  entfällt, da nur Berechtigte den Bereich sehen).
- **Lagerbestand** = Summe der Lagerbewegungen (Journal, nur anfügen, nie ändern/löschen): Startbestand,
  Wareneingang (eingelagert), Korrektur/Inventur, Entnahme (Entnahme-Oberfläche folgt mit Produktion).
  Lagerbestandsliste (Filter Lagerartikel / unter Mindest / alles), Lagerkarte je Material mit Bewegungen,
  Bestellungen und „Bestand korrigieren“ (gezählter Wert → Differenz wird gebucht, Grund Pflicht, Protokoll).
  Materialkarte zeigt Lagerbestand + Link.
- **Bestellvorschläge** (wie Spalten V–AE): aktive Lagerartikel mit Mindestbestand, bei denen Bestand + offene
  Bestellmenge < Mindestbestand. Vorschlag = Ziel (Zielbestand, mind. Mindestbestand) − Bestand − offen, auf ganze
  Einheiten aufgerundet; Menge änderbar; „Bestellen“ je Zeile oder „Alle Vorschläge bestellen“ (Bestellart
  Automatisch, Entscheider „Automatik“). Ohne Lieferant im Materialstamm keine Bestellung (wie `LiefFehlt`).
  Nicht übernommen: Projekt-Bedarf (Spalten Y/Z aus Stückliste) → mit Möbelrechner/Stückliste.
- **Bestellungen**: B-0001 fortlaufend; Material, Lieferant (aus Material), Menge, Einheit, Projekt (optional),
  Bestellart (Automatisch/Manuell/Projekt), Grund, erwarteter Termin (leer = heute + Lieferzeit). Liste mit Suche,
  Filter offen/erledigt. „Rest kommt nicht mehr“ → abschließen (Grund, Protokoll).
- **Wareneingang** (wie Assistent): „Alles da“ / „Teillieferung“ (Menge) / „Noch nichts“ (neuer Liefertermin,
  Vorschlag heute + 2), dann „Gleich einlagern“ / „Später“; mehr als bestellt nur mit Bestätigung; später
  „Jetzt einlagern“. Status wie `StatusText()`: unterwegs / teilweise / überfällig / einlagern / geliefert /
  abgeschlossen. Übersicht mit Kennzahlen (Vorschläge + Wert, offene Lieferungen, überfällig, warten aufs Einlagern).
- **Abgleich Eingangsrechnung ↔ Bestellung** (wie `Abgleich()` in PW_Eingang): Bestellwert = Menge × EK netto;
  „✓ passt“ bei Abweichung ≤ max(0,50 €; 2 %), sonst „Abweichung ±x €“. Im Erfassen-Formular Auswahlliste offener
  Bestellungen.
- **Excel-Import**: Blatt „Lager“ (A Material-ID, D Istbestand → Startbestand nur wenn noch keine Bewegung;
  I Lagerort → Lagerplatz nur wenn leer) und „Bestellungen“ (nur Zeilen mit „B-…“: A, B Projekt, C Material,
  D Lieferant, E bestellt, F Menge, G Einheit, H erwartet, J Wareneingang am, M geliefert kumuliert,
  AO eingelagert kumuliert, AS Status „abgeschlossen“). Vorhandene Nummern nie überschrieben; zweimal importieren
  ändert nichts.
- 351 automatische Tests, alle grün.

### So testest du es (Etappe 3, Paket 1)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 3.0“ stehen.
1. Excel-Import erneut durchlaufen lassen → im Bericht erscheinen „Lagerbestand“ und „Bestellungen“.
2. Kachel „Bestellungen & Lager“ → Bestellvorschläge prüfen (stimmen Mindest-/Zielbestände?) → einen Vorschlag
   „Bestellen“.
3. Bei der neuen Bestellung „Wareneingang“ → „Teillieferung“ 1 Stück, „Später“ → Hinweis „angekommen, aber noch
   nicht im Lager“ → „Jetzt einlagern“.
4. „Lagerbestand“ → ein Material öffnen → „Bestand korrigieren“ → gezählten Wert eintragen.
5. Eingangsrechnung erfassen mit dieser Bestell-Nr. → auf der Rechnung steht „✓ passt zur Bestellung“ bzw. die Abweichung.

### Paket 2a: Stückliste, Kalkulation, Auftrag & Freigaben – weitergegeben am 15.11.2026 (Chris: „weiter gehts“)
Chris wünscht „a (Möbelrechner/Kalkulation) und dann b (Produktion)“. a ist zu groß für ein Paket → geteilt:
2a Stückliste + Kalkulation + Auftrag (dieses Paket), 2b Möbelrechner (Korpus → Teileliste → Stückliste).
Vorlage: `PW_Auftraege.bas` (Entwurf(), Speichern, Freigaben/Darf()), Blätter „Stueckliste“ (48), „Kalkulation“ (50),
„Auftraege“ (37). Neue App `kalkulation`.
- Kachel „Kalkulation & Aufträge“ (Chef, Admin, Buchhaltung, Meister): Übersicht je Projekt mit Kosten, kalk. VK,
  Angebot, Marge (< 15 % rot wie Makro), Ist-Kosten, Auftrag/Status. Projektkarte: Knopf „Stückliste, Kalkulation & Auftrag“.
- **Stückliste** je Projekt: Material aus Stamm (EK/Einheit übernommen) oder freie Position; Menge, EK, Gesamt,
  Lagerbestand (rot, wenn zu wenig). Status Geplant (Idee) / Benötigt (→ Bestellvorschläge) / Entnommen (bucht
  Lagerentnahme mit Projekt; zurückstellen bucht wieder ein). Entnommenes nicht entfernbar. Protokoll.
- **Bestellvorschläge erweitert** um Projektbedarf („Aktiver Bedarf“): Bestand + offen − Bedarf < Mindest (bzw. < 0
  ohne Lagerhaltung) → Vorschlag = Ziel + Bedarf − Bestand − offen; Grund „Projektbedarf“; abgeschlossene Projekte zählen nicht.
- **Kalkulation** (wie Entwurf()): Kosten = Material (Stückliste ohne „Geplant“, sonst Handwert) + Beschläge +
  Std × €/Std + Maschine + Montage + Fahrt + Fremd; VK = Kosten × (1 + Zuschlag % + Risiko %) gerundet; Art Vor/Zwischen/Nach.
  Standard Zuschlag 15 %, Risiko 5 % (änderbar). Ist-Kosten (Nachkalkulation) = Eingangsrechnungen netto + Entnahmen
  (Löhne folgen mit Zeiterfassung, Etappe 4).
- **Auftrag** AU-0001 je Projekt: Angebot netto (Vorschlag = kalk. VK), Status Angebot/Beauftragt/In Arbeit/
  Abgeschlossen, Lieferung/Montage, Leistung. Freigaben Kunde (jeder) / Chef (nur Chef) / Meister (nur Meister),
  Admin alles; „intern freigegeben“ = Chef + Meister (wie Makro). Rechnungen: Auftragswert-Vorschlag = Angebot netto.
- **Import**: Stueckliste (A Pos, B Projekt, C Material, D Bezeichnung, E Menge, F Einheit, G EK, I Status; Entnommen
  wird nicht noch einmal abgebucht), Kalkulation (A, B Material, C, D, E, G–J, L/M Zuschlag/Risiko als 0,15 oder 15,
  U Art), Auftraege (A, B, D, G, H, I, J, K, L; „Erteilt“ = Freigegeben). Je Projekt nur einmal, nie überschrieben.
- Nicht übernommen: Blatt „Kalkulationsvergleich“ (61), Fertigungs-Stückliste/Stücklisten-Transfer (76/77) und
  Freigabe-Workflow „Ideenplanung“ aus Modul2 → bei Bedarf später; Kalkulationsänderungen stehen im Protokoll.
- 366 automatische Tests, alle grün.

### So testest du es (Etappe 3, Paket 2a)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 3.1“ stehen.
1. Excel-Import erneut durchlaufen lassen → Stückliste, Kalkulation, Aufträge erscheinen im Bericht.
2. Kachel „Kalkulation & Aufträge“ → stimmen Kosten/VK deiner Projekte mit der Excel überein?
3. Ein Projekt öffnen → Position hinzufügen (Status „Benötigt“) → unter „Bestellungen & Lager“ erscheint der Bedarf als Vorschlag.
4. Kalkulation ausfüllen → „Kalkulation speichern“ → VK erscheint → „Auftrag anlegen“ (Preis = VK vorgeschlagen).
5. Freigaben: als Chef „Freigegeben“ bei Chef; Meister-Zeile ist für den Chef grau.

### Paket 2b: Möbelrechner – weitergegeben am 15.11.2026 (Chris: „dann weiter mit Teil B“)
Vorlage: `PW_Moebelrechner.bas` (Stufe 1: TypVorgabe, TeilNeu, BedarfFinal, PlattenZaehlen, Prüfungen, RegelnAnlegen),
Blätter „Möbel-Regeln“, „Möbel-Positionen“, „Möbelrechner“, „Möbel-Druck“. Neue App `moebel`.
- Kachel „Möbelrechner“ (Chef, Admin, Meister). Aus „Kalkulation & Aufträge“ je Projekt: „📐 Möbelrechner“ / „+ Möbel rechnen“.
- **Eingabe** in 4 Karten: Möbel (Projekt, Bezeichnung, Typ Unterschrank/Oberschrank/Hochschrank/Kommode/Regal, Anzahl,
  B×H×T), Aufbau (Bauweise A/B/C, Abschluss Traversen/Deckel, Sockel, Sockelhöhe, Rückwandart, Verbindung, Raumhöhe),
  Material (Auswahl aus Materialstamm: Platten in m² mit Stärke, Kanten), Türen & Innenleben (Türen, Aufschlag/Einlage,
  Fachböden, Beschlagsystem). Typwahl setzt die Standardmaße. „Abweichende Regeln“ (Fugen, Nut, Traverse, Verschnitt) je Möbel.
- **Berechnen (Vorschau)** ohne Speichern; **Speichern** legt Position M01, M02 … je Projekt an (ID wie Excel
  P-…-M01), jede Änderung = neue Version, Protokoll.
- **Ergebnis**: Ampel grün/gelb/rot, Prüfungen (Fachboden-Durchbiegung, Türgröße/Bänder, Querschnitte, Höhen-/Längsschnitt,
  Kippmaß, 32er-Raster, Plattenformat, fehlendes Material/Preis), Teileliste (Fertig- und Zuschnittmaß minus Kante,
  Kanten L1/L2/B1/B2, Maserung, Bearbeitung, Einbauort), Beschläge & Verbinder nach Beschlagsystem, Materialbedarf
  (Platten als ganze Platten mit Ausnutzung, Kanten inkl. Zugabe, Stück aufgerundet), Materialkosten, Kennzahlen.
  Nachgerechnet: Unterschrank 600×820×560 → Seite 720×560, Rückwand 696×576, Tür 717×597 (Zuschnitt 713×593), 18 Dübel.
- **In Stückliste übernehmen** (wie PW_Moebel_In_Stueckliste): Bedarf als „Geplant“; erneutes Übernehmen ersetzt die
  geplanten Zeilen dieses Möbels. Gesperrt bei roter Ampel oder wenn Zeilen schon „Benötigt/Entnommen“ sind.
  Nach Änderung steht das Möbel wieder auf „Gespeichert“ (neu übernehmen).
- **Als Variante kopieren**, **Teileliste drucken (PDF)** A4 quer mit Abhak-Spalte wie „Möbel-Druck“.
- **Werkstatt-Regeln**: Zahlen-Regeln im Programm änderbar (Protokoll); Tabellen (Bänder, Fachboden, Verbinder,
  Beschlagsysteme, Standardmaterial) aus Excel-Import „Möbel-Regeln“. Im Programm geänderte Zahlen überschreibt der Import nicht.
- Noch NICHT übernommen (Excel Stufen 2–6): Zonen/Schubkästen, Modulbau, Rahmen+Füllung, Massivholz, Oberflächen,
  Arbeitsgänge, Formteile, CNC-Export, Etiketten, Import alter „Möbel-Positionen“ → bei Bedarf eigene Pakete.
- 387 automatische Tests, alle grün.

### So testest du es (Etappe 3, Paket 2b)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 3.2“ stehen.
1. Excel-Import erneut durchlaufen lassen → im Bericht steht „Möbel-Regeln“ mit Anzahl Regeln/Beschlagsysteme.
2. Kachel „Möbelrechner“ → „+ Neues Möbel“ → Projekt wählen, Unterschrank 600 × 820 × 560, dein Korpusmaterial →
   „Berechnen (Vorschau)“ → stimmen Teileliste und Zuschnittmaße mit deinem Excel-Möbelrechner überein?
3. „Speichern“ → „In Stückliste übernehmen“ → in „Kalkulation & Aufträge“ stehen die Zeilen als „Geplant“ (📐).
4. „Teileliste drucken (PDF)“ und „Als Variante kopieren“ ausprobieren.
5. Absichtlich falsch: Fachböden bei Breite 1200 und 2 Türen → Ampel rot, Übernahme gesperrt.

### Paket 3a: Produktion + QM – weitergegeben am 15.11.2026 (Chris: „Kann weiter gehen“)
Teil (b) ist zu groß für ein Paket → 3a Produktion + QM (dieses), 3b Teams, Montageplan, Abwesenheiten, Kalender.
Vorlage: `PW_Produktion.bas` (Produktions-Assistent Planen → Fertigung → QM → Montage → Fertig), `PW_Moebel_Arbeitsgaenge`
im Möbelrechner, Blätter „Produktion Arbeitsgänge“ (Formeln Spalten V–AJ), „Produktion QM“ (Formel O),
„Produktion Arbeitsgangbibliothe(k)“, „Produktion Routenvorlagen“. Neue App `produktion`.
- Kachel „Produktion“ (alle Rollen): Projekte mit aktuellem Schritt, Zähler je Schritt, Suche; „Meine Arbeitsgänge“.
- **Arbeitsgänge** entstehen (a) im Möbelrechner mit „Arbeitsgänge übernehmen“ (erst nach Stückliste; Codes wie
  ArbeitsgaengeBilden: VOR-010, PL-010/020, KA-010, BE-010 bzw. CNC bei Regel CNC_JA, QM-010/020/040, MO-010/020,
  LOG-010, Sortierung nach Standardfolge; IDs P-…-M01-AG01; geplante werden ersetzt, begonnene sperren),
  (b) aus einer **Routenvorlage** (Plattenmöbel Standard, Massivholz verleimt, MDF lackiert – Startwerte aus der Excel),
  (c) einzeln aus der **Arbeitsgangbibliothek** (28 Codes). Vorgänger-Kette automatisch.
- **Startfreigabe** wie Spalte Z: 🟢 Start möglich, wenn Vorgänger fertig und seine QM-Prüfung freigegeben (oder keine);
  🔒 wartet; 🔒 Nacharbeit/QM offen; Wartezeit-Arbeitsgänge (Trocknen) ⏱ bis Vorgänger-fertig + Wartezeit.
- **Einplanen** (Chef/Admin/Meister): Startdatum + Mitarbeiter (nur wo leer) → Plan-Start/-Ende nach Plan-Stunden,
  8 h/Tag, ohne Wochenende (0 h zählt als 1 h, wie Makro). Arbeitsgang bearbeiten/entfernen (nur geplant, ohne Stunden).
- **Fertigung** (alle): Starten (nur bei grüner Freigabe; Mitarbeiter = eigener, falls leer), Rückmelden mit Stunden
  (Zwischenstand oder Fertig). Lohnkosten Ist = Ist-Std. × Stundensatz (Anzeige; fließt noch nicht in die Kalkulation).
- **QM-Endkontrolle** (Chef/Admin/Meister) nach allen fertigen Arbeitsgängen: Bestanden → freigegeben; Nicht bestanden →
  Arbeitsgang „Nacharbeit: …“ (P-…-NA01, Priorität hoch, morgen, letzter Mitarbeiter), Projekt zurück in die Fertigung.
  Verbesserung zur Excel: Die spätere bestandene Nachprüfung schließt die alte gesperrte Prüfung (Nacharbeit erledigt,
  Nachprüfung bestanden) – in der Excel blieb sie gesperrt.
- **Import**: Bibliothek (aktualisiert Codes), Routenvorlagen (nur neue Routen), Arbeitsgänge (A–U, AD, AE; Vorgänger
  am Ende verknüpft; vorhandene AG-IDs nie überschrieben), QM (A–N). Mitarbeiter über Kürzel oder Name.
- Noch nicht: Montageplan, Teams, Abwesenheits-Warnung beim Planen, Kalender (→ 3b); „Produktion Fertigungsroute“ als
  eigenes Blatt (Route wird direkt zu Arbeitsgängen), Handy-Ableger (dafür „Meine Arbeitsgänge“ im Browser).
- 404 automatische Tests, alle grün.

### So testest du es (Etappe 3, Paket 3a)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 3.3“ stehen.
1. Excel-Import erneut → im Bericht: Arbeitsgangbibliothek, Routenvorlagen, Arbeitsgänge, QM-Prüfungen.
2. Möbelrechner: ein Möbel „In Stückliste übernehmen“ → „Arbeitsgänge übernehmen“ → 11 Arbeitsgänge.
3. Kachel „Produktion“ → Projekt → „Einplanen“ mit Startdatum und Mitarbeiter → Plan-Daten erscheinen.
4. Ersten Arbeitsgang „▶ Starten“, Stunden eintragen (z. B. 2,5) → „✓ Fertig“ → der nächste wird grün.
5. Alle fertig → QM „Nicht bestanden“ mit Mangel → Nacharbeit erscheint; fertig melden → QM „Bestanden“ → Schritt „Montage“.
6. Optional: Mitarbeiter-Zugang mit Mitarbeiter verknüpfen → als dieser anmelden → „Meine Arbeitsgänge“.

### Paket 3b: Teams, Montageplan, Abwesenheiten, Kalender – weitergegeben am 19.11.2026 (Chris: „Kann weiter gehen mit Etappe 4“)
Vorlage: `PW_Produktion.bas` (MontageZeigen/MontageSpeichern, Teams/Mitglied), `PW_Kalender.bas` (Sammeln, Zeilen, Passt),
Blätter „Teams“, „Zeitdaten“, „Montageplan“, „Zeitplan“. Neue App `planung`.
- Kachel „Montage & Kalender“ (alle) mit Reitern Woche · Montageplan · Teams · Abwesenheiten.
- **Teams** (TEAM-0001 …): anlegen, Teamart, Mitglieder antippen = dazu/raus (erstes Mitglied = Leitung),
  Abwesenheiten der Woche auf den Kacheln.
- **Abwesenheiten** (ZD-0001 …): Urlaub, Krank, Fortbildung, Berufsschule, Zeitausgleich, Sonstiges; Status
  Beantragt/Freigegeben/Abgelehnt. Chef/Admin/Meister tragen ein und geben frei; Mitarbeiter beantragen nur für sich.
  Wirkt wie Abwesend(): alles außer „Abgelehnt“ (beantragt wird so markiert).
- **Montage** je Projekt (erst nach QM-Freigabe): Datum, Beginn/Ende, Team, Fahrzeug (Transporter/PKW/Anhänger + eigene),
  Adresse (Vorschlag Kundenadresse), Aufgaben, Material, Werkzeug, Hinweise. Vorher Warnungen wie im Makro:
  abwesende Teammitglieder, Team oder Fahrzeug am Tag schon vergeben, Wochenende → „Trotzdem eintragen“ möglich.
  Speichern legt je Teammitglied einen Termin an (alte Montage-Termine des Projekts werden ersetzt).
  Ergebnis „Montage bestanden“ → Schritt **Fertig** (weiter zur Schlussrechnung); „Nacharbeit erforderlich“ → bleibt offen.
- **Montageplan**: Liste ab letzter Woche (oder alle), oben „Bereit zur Montage“ (QM frei, noch kein Termin).
- **Wochenkalender** Mo–Fr, KW, Woche vor/zurück/heute, Ansicht nach Teams, Mitarbeiter oder Projekten; liest Termine,
  Montageplan, eingeplante Arbeitsgänge (Planstart–Planende) und Abwesenheiten, Farben wie Excel; ändert nichts.
  Termine von Hand (Mitarbeiter oder ganzes Team, Art, Projekt, Ort) eintragen und absagen (bleiben gespeichert).
- Produktion: Abwesenheits-Warnung beim Einplanen; Montage-Abschnitt auf der Projektseite.
- **Import**: Teams (Zeilen 4–100, Mitglieder ab 110; Plätze ohne Namen übersprungen), Zeitdaten, Montageplan
  (je Projekt eine Montage), Zeitplan. Mitarbeiter über Kürzel oder Name. Vorhandenes wird nie überschrieben.
- Nicht übernommen: Personal-Gate/Kapazität (Soll/Gebucht/Rest h), Monatsansicht, Handy-Ableger, Kalender-Rechte-Blatt.
- 414 automatische Tests, alle grün.

### So testest du es (Etappe 3, Paket 3b)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 3.4“ stehen.
1. Excel-Import erneut → im Bericht: Teams, Abwesenheiten (Zeitdaten), Montageplan, Zeitplan.
2. „Montage & Kalender“ → Teams → „+ Neues Team“ → Mitarbeiter antippen.
3. Abwesenheiten → für einen Mitarbeiter Urlaub nächste Woche eintragen.
4. Ein Projekt mit bestandener QM: Produktion → „🚚 Montage planen“ → Tag des Urlaubs wählen → Warnung erscheint →
   anderen Tag oder „Trotzdem eintragen“ → im Kalender steht die Montage bei jedem Teammitglied.
5. Kalender: zwischen Teams / Mitarbeiter / Projekte umschalten, Woche vor und zurück.
6. Montage → „✓ Montage bestanden“ → in der Produktion steht „Fertig“.

## Etappe 4 – Zeit & Zahlen: IN ARBEIT
Aufteilung: 4a Zeiterfassung + Arbeitsverträge (dieses Paket), 4b Auswertungen für den Chef (inkl. Löhne in der
Liquidität), danach Verkaufsfassung/Installer (FEHLER Nr. 2).
Die Excel hat keinen eigenen Stundenzettel: Projektstunden kamen nur aus „Produktion Arbeitsgänge“ (Ist-Std.),
Soll und Urlaub aus „Arbeitsverträge“, Abwesenheiten aus „Zeitdaten“ (PW_Personal.bas). Das Programm führt das zusammen.

### Paket 4a: Zeiterfassung + Arbeitsverträge – weitergegeben am 19.11.2026 (Chris: „mach weiter mit 4b“, Gesamttest am Schluss)
Neue App `zeiten`.
- **Arbeitsverträge** (Kachel unter Verwaltung; Chef/Admin ändern, Buchhaltung liest, Meister/Mitarbeiter nicht):
  Vertragsart, Status, Eintritt, Befristung, Probezeit, Soll Mo–Fr, Urlaub/Jahr, Zeitkonto-Startwert, Brutto/Monat,
  Stundenlohn, Kündigungsfrist, Tätigkeit, Arbeitsort. Hinweise: kein Vertrag, Probezeit endet (30 Tage),
  Befristung endet (60 Tage), Eintritt fehlt, Stundenlohn fehlt. Protokoll ohne Beträge. Import Blatt „Arbeitsvertraege“.
- **Zeiterfassung** (Kachel für alle): „Meine Zeiten“ – Woche mit Soll/Ist je Tag, Buchen mit Von/Bis/Pause oder nur
  Stunden, Projekt, Arbeitsgang (★ = mir zugeteilt), Tätigkeit, Notiz; Zeitkonto und Resturlaub.
  Büro (Chef/Admin/Meister/Buchhaltung): Monatsübersicht aller Mitarbeiter (Soll, Ist, Abwesenheit, Saldo, Zeitkonto,
  Urlaub), Monat je Mitarbeiter mit Tagesliste und Buchungen, Buchen für andere (Chef/Admin/Meister),
  **Stundenzettel als PDF** mit Unterschriftszeilen, **Monat abschließen** (Chef/Admin; danach gesperrt),
  Abschluss aufheben nur Chef (protokolliert).
- **Regeln**: Soll aus dem Vertrag (sonst Wochenstunden/5, sonst 8 h); Wochenende und Feiertage Rheinland-Pfalz
  (inkl. Fronleichnam, Allerheiligen) = 0. Freigegebener Urlaub/Krank/Fortbildung/Berufsschule = erfüllte Soll-Zeit,
  Zeitausgleich nicht. Zeitkonto = Startwert + Monatssalden ab dem späteren von Eintritt und erster Buchung.
  Urlaub genommen = Arbeitstage ohne Feiertage. Buchungen max. 16 h/Tag, nicht in der Zukunft.
  Stornieren nur mit Grund – die Buchung bleibt sichtbar (durchgestrichen).
- **Verknüpfungen**: Rückmelden in der Produktion bucht die Stunden automatisch als Zeit (Quelle „Produktion“).
  Lohnkosten Ist = Stunden × Stundenlohn zum Buchungszeitpunkt (+ Ist-Stunden aus der Excel ohne Buchung ×
  aktueller Stundenlohn) → erscheint in der Produktion und in der **Nachkalkulation** (Ist-Kosten jetzt inkl. Löhne).
- Behoben nebenbei: Wert 0 beim Excel-Import (FEHLER Nr. 11).
- 427 automatische Tests, alle grün.

### So testest du es (Etappe 4, Paket 4a)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 4.1“ stehen.
1. Excel-Import erneut → im Bericht „Arbeitsverträge“ (Administrator wird übersprungen).
2. Kachel „Arbeitsverträge“ → stimmen Soll-Stunden, Urlaub und Stundenlohn? Warnhinweise prüfen.
3. Kachel „Zeiterfassung“ → „Meine Zeiten“ → eine Zeit mit Von/Bis und Pause buchen, eine nur mit Stunden (z. B. 7,5).
4. Übersicht → Mitarbeiter → Monat ansehen → „Stundenzettel (PDF)“.
5. Vormonat eines Mitarbeiters öffnen → „🔒 Monat abschließen“ → Buchen in diesem Monat geht nicht mehr.
6. Produktion: einen Arbeitsgang mit Stunden rückmelden → die Zeit steht danach auch in der Zeiterfassung;
   Kalkulation & Aufträge → „Ist-Kosten“ enthalten jetzt die Löhne.

### Paket 4b: Auswertungen für den Chef – weitergegeben am 19.11.2026 (Gesamttest am Schluss)
Vorlage: Blätter „Cockpit“, „Finanz-Cockpit“ (Löhne zum Monatsende), „Kalkulationsvergleich“, Dashboards
(Produktion/Material). Neue App `auswertung` (nur lesen).
- Kachel „Auswertungen“ (Chef, Admin): Jahr wählbar (5 Jahre). Kennzahlen: Umsatz netto mit Vorjahresvergleich bis
  zum gleichen Tag, Kosten (Eingangsrechnungen + Löhne), Ergebnis vor Gemeinkosten mit Marge, gebuchte Stunden mit
  Anteil auf Projekte. Balken Umsatz/Kosten je Monat (ohne Internet, Zahlen auch als Tabelle).
- **Nachkalkulation je Projekt** (wie „Kalkulationsvergleich“): Angebot, kalkulierte Kosten, Ist-Kosten, % verbraucht
  mit Ampel (gelb ab 85 %, rot über 100 %), Stunden Ist/Soll, Erlös, DB. Projektseite: Kostenarten Material+Beschläge,
  Lohn, Fremdleistungen, Maschine/Montage/Fahrt/Sonstiges – kalkuliert gegen Ist mit Abweichung.
  (Die Excel unterschied Vor-/Zwischen-/Nachkalkulation als drei Spalten; im Programm gibt es eine Kalkulation
  mit Art – verglichen wird sie mit dem echten Ist.)
- **Stunden je Mitarbeiter** im Monat: Ist/Soll, Auslastung (inkl. Abwesenheit), Anteil auf Projekte, je Tätigkeit.
- **Werkstatt**: Projekte je Schritt, QM beim ersten Mal bestanden (%), überfällige Arbeitsgänge, Montagen 14 Tage.
- **Material**: Lagerwert zum EK, offene Bestellungen mit Wert, Artikel unter Mindestbestand.
- **Finanzen**: Liquidität jetzt mit Löhnen (Brutto/Monat aktiver Arbeitsverträge zum Monatsende, wie Excel, ohne
  Arbeitgeberanteile); Deckungsbeitrag je Projekt zieht Lohnkosten Ist ab.
- Damit sind alle Kacheln gebaut (kein „kommt in Etappe …“ mehr).
- 434 automatische Tests, alle grün.

### So testest du es (Etappe 4, Paket 4b)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B: „Code“ → „Download ZIP“ →
entpacken) und im NEUEN Ordner `PFALZ-WERK starten.bat` doppelklicken. Im Navi oben muss „Fassung 4.2“ stehen.
1. Kachel „Auswertungen“ → stimmt der Umsatz des Jahres mit deinen Rechnungen überein? Monatsbalken ansehen.
2. Nachkalkulation: ein Projekt mit Kalkulation antippen → Kalkuliert gegen Ist je Kostenart prüfen.
3. Stunden: Monat eines Mitarbeiters mit der Zeiterfassung vergleichen.
4. Finanzen → Liquidität: am Monatsende stehen „davon Löhne“ (Brutto aus den Arbeitsverträgen).

## Gesamttest (Wunsch von Chris, 19.11.2026)
Chris testet alles am Schluss. Bis dahin werden alle Pakete ohne Einzelabnahme weitergegeben.

## Etappe 5 – Ausbau: IN ARBEIT
Reihenfolge laut Chris (19.11.2026): **Möbelrechner → Kapazitätsplanung → Inventur → Handy-Ansichten →
Fassung zum Installieren**. Möbelrechner-Ausbau geteilt: 5a Aufteilung (Stufe 2), 5b Oberflächen + Kantenprofil +
Änderungsverfolgung (Stufe 3), 5c Massivholz, Rahmen + Füllung, Modulbau, Formteile (Stufe 4/5), 5d CNC-Export (Stufe 6).

### Paket 5a: Möbelrechner Aufteilung (Stufe 2) – GEBAUT 19.11.2026
Vorlage: `PW_Moebelrechner.bas` RechnenZonen, Teilen, Fib, Kasten, FeldBreiten, VariantenSammeln, Etiketten_Drucken,
RegelnStufe2.
- Neue Karte „5 · Aufteilung“: Felder (Mittelwände), Feldbreiten („400;Rest“), Teilungsregel (gleich, Goldener Schnitt,
  Fibonacci, gestaffelt, Raster 32, manuell), Zwischenböden Ja/Nein, Schubkastensystem (Holzkasten Unterflur / Metallbox),
  Kastenverbindung (Dübel, Schwalbenschwanz, Nut und Feder, Lamello); Zonentabelle Feld · Zone (1 = unten) · Art
  (Tür, Schubkasten, Fach offen, Blende) · Fronthöhe (leer = Regel) · Fachböden. Typ „Kommode“ setzt 3 Schubkästen
  im Goldenen Schnitt (wie Neue Position).
- Rechnen wie Makro: Fronthöhen je Feld nach Regel (Rest an die unterste freie Zone), Frontbreiten je Feld (Aufschlag
  mit halber Mittelwand und halben Fugen; Einlage), Türen je Zone (2 Türen über max. Türbreite), Fachböden je Zone
  mit Durchbiegung, Zwischenböden, Mittelwände + Verbinder. **Schubkasten**: Nennlänge (größte, die in Innentiefe −
  Reserve passt), Holzkasten mit Seiten, Vorder-/Hinterstück, Boden in Nut, Kastenverbinder, Führung BL-FUE-NL;
  Metallbox mit Boden, Rückwand, Zargenset BL-BOX-NL. Prüfungen: Querschnitt Felder, Höhenteilung, Ergonomie
  (Schubkasten zu hoch/tief, Fach nur mit Tritt), Nennlänge, Kastenhöhe.
- **Variantenvergleich** der Teilungsregeln je Feld im Ergebnis (gewählte Regel markiert).
- **Etiketten (PDF)**: je Plattenteil und Stück, 3 × 7 je A4 (70 × 42 mm).
- Werkstatt-Regeln: 14 neue Zahlen (Schubkasten, Box, Ergonomie), Nennlängen, Kastenmaterial/-boden;
  Import aus „Möbel-Regeln“ (Spalte AP, Zeilen 95/96).
- Nicht übernommen: Führungen/Zargen werden nicht automatisch im Materialstamm angelegt (Makro tat das) – fehlen sie,
  steht beim Beschlag „keine Material-Nr.“; bitte im Materialstamm anlegen (BL-FUE-400 usw.) oder per Import.
- 441 automatische Tests, alle grün.

### So testest du es (Etappe 5, Paket 5a)
Vorher: neue Fassung **von GitHub herunterladen** (ANLEITUNG.md Teil B), im NEUEN Ordner starten, Fassung „5.1“.
1. Möbelrechner → Neues Möbel → Typ „Kommode“ → Zonentabelle hat 3 Schubkästen → Berechnen → Fronthöhen und
   Kastenmaße mit der Excel vergleichen; Variantenvergleich ansehen.
2. Unterschrank 1200 breit, 2 Felder, Feldbreiten „400;Rest“, Feld 1 Schubkasten unten + Tür oben, Feld 2 Fach offen.
3. Speichern → „Etiketten (PDF)“.

### Paket 5b: Möbelrechner Oberfläche, Profil, Änderungen (Stufe 3) – GEBAUT 19.11.2026
Vorlage: Oberflaechen, ProfilAnwenden, ArbeitsgaengeBilden, BedarfFinal (Plattenbedarf), AenderungPruefen, RegelnStufe3.
- Karte „5 · Oberfläche & Kalkulation“: Oberfläche Korpus / Front (Tabelle aus den Werkstatt-Regeln, 8 Startwerte wie
  Excel: beschichtet, furniert geölt/lackiert, lackiert deckend, HPL, Massivholz geölt/lackiert, gebeizt + lackiert),
  Kantenprofil Front, Plattenbedarf (ganze Platten / Verschnittfaktor), eigener Schnellpreis-Faktor.
- Oberfläche: Fläche (Korpus inkl. Innenausbau/Sockel, ohne fremde Rückwand; bzw. Front) × Seiten × Menge je m² →
  Materialbedarf; fehlt das Material im Stamm → gelber Hinweis. AG-Codes der Oberfläche (Schleifen, Ölen, Trocknen …)
  gehen in die Arbeitsgänge. Kantenprofil wird an allen Frontteilen vermerkt (+ CNC-020 bzw. BE-010).
- Arbeitsgänge kommen jetzt direkt aus dem Rechner. Neue Regeln **CNC_JA = 1** (wie Excel: Bohren/Fräsen auf der CNC →
  CNC-010/CNC-020 statt BE-010; 0 = von Hand) und **WARTE_STD = 12** (Wartezeit für Trocknen/Aushärten).
  Damit 12 statt 11 Arbeitsgänge beim Standard-Unterschrank – gleiche Reihenfolge wie in Chris' Excel.
- Änderungsverfolgung: jede Änderung „Feld: alt -> neu“ (+ Materialkosten) an der Position, neueste zuerst.
  War die Position schon in der Stückliste → Warnung auf Möbel- und Kalkulationsseite, bis neu übernommen.
- Import Oberflächen-Tabelle (Möbel-Regeln AW:BE).
- 446 automatische Tests, alle grün.

### So testest du es (Etappe 5, Paket 5b)
Fassung „5.2“ herunterladen (ANLEITUNG Teil B).
1. Möbel bearbeiten → Oberfläche Front „furniert, geölt“ → Berechnen → Bedarf Öl/Furnier, Kennzahl Oberfläche.
2. Speichern einer schon übernommenen Position → Warnung „nach der Übernahme geändert“, Änderungsliste unten.
3. Werkstatt-Regeln → Tabelle Oberflächen ansehen; CNC_JA auf 0 → Arbeitsgänge mit „Fräsen / Bohren / Dübeln“.

### Paket 5c: Möbelrechner Massivholz, Rahmen + Füllung, Modulbau, Formteile (Stufe 4/5) – GEBAUT 19.11.2026
Vorlage: MassivInfo, QuellWert/QuellMass, TuerTeile, KT, FeldBreiten (Modul), FormteilZeile, FormBau, RegelnStufe4/5.
- **Massivholz** (Material mit Einheit m³): Leimholz aus Lamellen (breiter als 120 mm → Lamellen à ca. 80 mm),
  Bedarf als Grobvolumen mit Zugaben (Länge/Breite/Dicke) + Reserve, Arbeitsgänge Massivholz/Leimholz,
  Quellmaß quer zur Faser mit Warnung (bewegliche Befestigung) – Quellwerte-Tabelle in den Werkstatt-Regeln
  (Import Möbel-Regeln AI:AJ, z. B. MH-EI → 0,36). Fehlt der Wert → gelber Hinweis.
  (Die Excel nahm die Zugaben aus dem Blatt „Bauteilzerlegung“, falls dort ausgefüllt; das Programm nutzt die Regeln.)
- **Türkonstruktion** Platte oder **Rahmen + Füllung** (Karte 4): Höhen- und Querfriese mit Zapfen, Füllung in Nut mit
  Luft, Prüfung Füllung arbeitet quer; Füllungsmaterial aus den Regeln (leer = Frontmaterial).
- **Modulbau** (Bauweise M): je Feld ein eigener Korpus – Boden/Deckel/Traversen/Rückwand je Modul, Modulseiten statt
  Mittelwand, Korpusverbinder (BL-KORPUSVERB), Verbinder je Modul, Fronten je Modul.
- **Formteile** (Karte 7, bis 6 je Möbel): Ausschneiden, Segmentbau, Eingesägt (Kerben), Biegeplatte, Formverleimung,
  Dämpfen – Bogen innen/außen, Sehne/Stich, Lagen/Segmente/Kerben, Zuschnitt, Prüfung (Mindestradius, R/t, Kurzfaser,
  Kerbenabstand), Teile in der Teileliste, Leim, Formenbau (Positiv/Negativ aus Formmaterial), Arbeitsgänge.
- 27 neue Werkstatt-Regeln (Massivholz, Rahmen, Formteile); Standardmaterial Füllung/Form/Leim (Import Zeilen 97–99).
- Nicht übernommen: Blatt „Bauteilzerlegung“ (eigenes Werkzeug der Excel) und der Knopf „An Bauteilzerlegung“.
- 452 automatische Tests, alle grün.

### So testest du es (Etappe 5, Paket 5c)
Fassung „5.3“ herunterladen (ANLEITUNG Teil B).
1. Möbel mit Korpusmaterial aus Massivholz (Einheit m³) → Hinweise Lamellen/Quellmaß, Bedarf in m³.
2. Türkonstruktion „Rahmen + Füllung“ → Friese und Füllung in der Teileliste.
3. Bauweise „M Modulbau“ mit 2 Feldern → Modulseiten, Teile je Modul.
4. Karte 7: Bogenzarge Formverleimung R 400, 90°, Höhe 120, Dicke 12, Pappelsperrholz → Lagen, Form, Leim.

### Paket 5d: Möbelrechner CNC-Export + Maßvorschläge (Stufe 6) – GEBAUT 19.11.2026
Vorlage: PW_Moebel_CNC_Export, BohrbildTeil, BohrPlus, Dxf*, MassVorschlaege, Stufe6.
- Knopf „CNC-Export (ZIP)“ auf der Möbelseite (nicht bei roter Ampel): Teileliste.csv, Bohrbild.csv,
  Parameterliste.csv (UTF-8, Semikolon, Dezimalpunkt wie Excel „0.0##“), je Plattenteil eine DXF (Kontur, Bohrungen
  als Kreise je Durchmesser-Layer, Rückwandnut, Beschriftung) und LIESMICH. Die Excel schrieb einen Ordner neben die
  Arbeitsmappe – im Browser kommt eine ZIP-Datei zum Herunterladen.
- Bohrbild-Vorschlag: Seiten/Mittelwände Lochreihen vorn/hinten im Raster, Verbinder Boden/Deckel, Montageplatten,
  Rückwandnut; Türen/Höhenfriese Topfbohrungen; Böden/Deckel/Traversen/Zwischenböden Dübel in der Kante.
  8 neue Werkstatt-Regeln (LOCH_UNTEN, LOCH_HINTEN, TOPF_D, TOPF_TIEFE, TOPF_ABST, DUEBEL_D, DUEBEL_T_FL, DUEBEL_T_KA).
- Maßvorschlag Tiefe (grüner Hinweis): wie viele Streifen aus der Plattenbreite gehen und welche Tiefe ohne
  Mehrverschnitt möglich wäre.
- Zuschnittliste fürs Handy folgt mit den Handy-Ansichten (Paket 8).
- **Möbelrechner damit vollständig (Stufen 1–6)** bis auf Bauteilzerlegung und SQL-Sync der Excel.
- 454 automatische Tests, alle grün.

### Paket 6: Kapazitätsplanung – GEBAUT 19.11.2026
Vorlage: Blätter „Einsatzplanung“ (O–V, X–AG), „Personal-Leitstand“, Zeitplan-Formeln M (Terminkonflikt),
P/Q (Verfügbarkeit, Planungshinweis), AA–AE (Dauer, Tagessoll, Gebucht, Rest), Zeitdaten F/G/I (Umfang, Einheit, Auswirkung).
- Reiter „📊 Kapazität“ unter Montage & Kalender (Chef, Admin, Meister): Tag wählbar; je Mitarbeiter Soll (Vertrag),
  Abwesenheit, gebucht, Rest, Status (verfügbar / knapp unter 2 h / überplant / abwesend / keine Sollzeit) mit
  Planungshinweis (einplanbar / nur kurze Aufgabe / nicht einplanen), was geplant ist, überschneidende Termine rot.
  Kennzahlen: verfügbar, Soll/gebucht, freie Stunden, Auslastung, Terminkonflikte. Wochenübersicht Mo–Fr mit freien
  Stunden je Mitarbeiter (Farben).
- Neu gegenüber der Excel: eingeplante Arbeitsgänge der Produktion zählen als gebucht (Plan-Stunden gleich auf die
  Werktage verteilt); fertige nicht.
- Abwesenheiten mit **Stunden je Tag** (z. B. Berufsschule 4 h) = reduziert statt ganzer Tag; Import aus Zeitdaten F/G/I.
  Nur freigegebene Abwesenheiten mindern die Kapazität (wie Excel).
- Warnungen: Termin eintragen (überplant, Überschneidung, abwesend, keine Sollzeit), Montage planen (Teammitglied
  überplant – die alten Montage-Termine desselben Projekts zählen beim Umplanen nicht), Produktion einplanen.
- 461 automatische Tests, alle grün.

## Nächstes Paket
**7 Inventur** (Blätter Inventur Leitstand/Start/Zählaufträge/Erfassung/Nachzählung/Abweichungen/Abschluss/Bericht/
Historie/Einstellungen), dann 8 Handy-Ansichten, 9 Installer. Drive-Ordner-ID 1dl_KNq7_YZOrSU2ZJVyOGWRQLiT7bmv3.

### Vorlage Mitarbeiter (aus Makros MeinTag_Sync2 und Vertragsfreigabe, 13.11.2026)
- Mitarbeiterliste steht im Blatt **„Dashboard Steuerung“**, Zeilen 6–205:
  A Kürzel (z. B. „CL“), B Name (z. B. „C.Lorenz“), M PIN (für die App „Mein Tag“),
  AB Eintrittsdatum, AD Wochenstunden, AJ Urlaub; AC, AE–AI, AK = weitere Vertragswerte (Bedeutung offen).
- Vertragswerte kommen aus Blatt „Arbeitsverträge“ (ab Zeile 8): A Vertrags-ID, B Mitarbeiter, E Status,
  F→AB, G→AC, I→AD, J→AE, K→AF, L→AG, M→AH, N→AI, O→AJ, P→AK; Übernahme nur mit Freigabe + Protokoll.
- PINs werden NICHT importiert (Regel: PINs gibt nur Chris ein).
- Arbeitsgänge (Etappe 3/4) im Blatt „Produktion Arbeitsgänge“ ab Zeile 6: A AG-ID, C Projekt-ID,
  E Arbeitsgang, G Mitarbeiter (Name oder Kürzel), K Status (Offen/In Arbeit/Fertig/Blockiert),
  M Plan-Std., N Ist-Std., Q Begonnen am, R Fertig am.

### Vorlage Lieferanten
- Kein Makro gefunden. Laut Bildschirmfoto (13.11.) steht im Blatt **„Material“, Spalte G „Lieferant“**
  (Name, z. B. „Wickert“) – wird bisher nicht importiert. Beim Lieferanten-Paket: Lieferanten aus G anlegen
  und Material verknüpfen. Weitere Material-Überschriften Zeile 3: J Lagerbestand, K Reserviert(?).
- Es gibt KEIN eigenes Blatt „Lieferanten“ (Blattliste 13.11. geprüft). Blatt „Mitarbeiter“: siehe Paket 5.


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
