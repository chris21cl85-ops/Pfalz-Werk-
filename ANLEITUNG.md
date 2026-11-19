# Anleitung für Chris – Schritt für Schritt

Diese Anleitung setzt kein Vorwissen voraus. Jeder Schritt sagt, **wo** du klickst und **was** du siehst.

---

## Neu ab Fassung 5.8: Setup-Programm (empfohlen – ohne Python, ohne Entpacken)

Damit brauchst du die Teile A und B nicht mehr. Das Setup bringt alles mit, was das Programm braucht.

1. Öffne **https://github.com/chris21cl85-ops/Pfalz-Werk-** (vorher bei GitHub angemeldet sein).
2. Rechts neben der Dateiliste steht der Abschnitt **„Releases“**. Klicke darunter auf die neueste
   **„PFALZ-WERK Fassung …“** (grünes Schild „Latest“).
3. Unter **„Assets“** auf **`PFALZ-WERK-Setup-….exe`** klicken. Die Datei landet in **Downloads**.
4. **Doppelklick** auf die Datei.
5. Kommt ein blaues Fenster „Der Computer wurde durch Windows geschützt“:
   **„Weitere Informationen“** → **„Trotzdem ausführen“**.
   (Das kommt, weil das Programm nicht bei Microsoft gekauft/signiert ist – es ist trotzdem deins.)
6. Im Setup: **„Weiter“** → Haken bei **„Verknüpfung auf dem Desktop anlegen“** lassen → **„Weiter“** →
   **„Installieren“** → **„Fertigstellen“**. Administratorrechte sind nicht nötig.
7. PFALZ-WERK startet sofort – weiter bei **Teil C, Schritt 3**.
   Künftig startest du es mit dem Symbol **„PFALZ-WERK“** auf dem Desktop oder im Startmenü.

**Bei einer neuen Fassung:** Neues Setup genauso herunterladen und installieren – es ersetzt das alte Programm.
Deine Daten (Ordner **Dokumente → PFALZ-WERK-Daten**) bleiben erhalten, auch beim Deinstallieren.

**Ohne Setup (Notlösung):** Unter „Assets“ gibt es auch **`PFALZ-WERK-…-Windows.zip`**. Rechtsklick →
„Alle extrahieren …“ → im Ordner **PFALZ-WERK** Doppelklick auf **`PFALZ-WERK starten.bat`**. Auch dafür
braucht es kein Python.

> Die Teile A und B unten gelten nur noch, falls du das Programm wie bisher als Quelltext-ZIP startest.

---

## A. Einmalig: Python installieren (ca. 5 Minuten)

PFALZ-WERK braucht das Programm „Python“. Das musst du nur ein einziges Mal installieren.

1. Öffne im Browser die Seite **https://www.python.org/downloads/**
2. Klicke auf den großen gelben Knopf **„Download Python 3.…“** (die Zahl ist egal, Hauptsache 3.12 oder höher).
3. Die Datei landet in deinem Ordner **Downloads**. Doppelklicke sie.
4. **WICHTIG:** Im ersten Fenster ganz unten den Haken setzen bei
   **„Add python.exe to PATH“**.
5. Klicke auf **„Install Now“**. Falls Windows fragt „Möchten Sie zulassen, dass …“ → **Ja**.
6. Warte, bis **„Setup was successful“** erscheint → **Close**.

Fertig. Das musst du nie wieder machen.

---

## B. Programm von GitHub herunterladen

Das machst du jedes Mal, wenn Claude eine neue Fassung hochgeladen hat.

1. Öffne **https://github.com/chris21cl85-ops/Pfalz-Werk-** (vorher bei GitHub angemeldet sein).
2. Klicke auf den grünen Knopf **„<> Code“** (rechts oberhalb der Dateiliste).
3. Im aufklappenden Fenster ganz unten: **„Download ZIP“**.
4. Öffne deinen Ordner **Downloads**. Dort liegt **Pfalz-Werk--main.zip**.
5. **Rechtsklick** auf die Datei → **„Alle extrahieren …“** → **„Extrahieren“**.
6. Es öffnet sich ein Ordner. Darin ist noch ein Ordner **Pfalz-Werk--main** – öffne ihn.
   Du siehst Dateien wie `PFALZ-WERK starten.bat`, `README.md`, `STAND.md`.

**Tipp:** Verschiebe diesen Ordner z. B. auf den Desktop, damit du ihn wiederfindest.

> **Bei einer neuen Fassung:** Einfach neu herunterladen und den neuen Ordner starten.
> Deine Daten liegen getrennt vom Programm – meist im Ordner **Dokumente → PFALZ-WERK-Daten**.
> Sperrt Windows diesen Ordner, nimmt das Programm automatisch einen anderen. Wo genau, steht beim Start
> im schwarzen Fenster („Daten und Sicherungen liegen in: …“). Die Daten bleiben bei jedem Update erhalten. Den alten Programmordner kannst du danach selbst löschen.

---

## C. Programm starten

1. Im Ordner **Doppelklick** auf **`PFALZ-WERK starten.bat`**.
2. Falls ein blaues Fenster „Der Computer wurde durch Windows geschützt“ erscheint:
   auf **„Weitere Informationen“** klicken → **„Trotzdem ausführen“**.
3. Ein **schwarzes Fenster** öffnet sich. Beim allerersten Mal dauert es 1–2 Minuten
   (es richtet sich ein). **Nicht schließen.**
4. **Nur beim allerersten Start** fragt das schwarze Fenster nach dem Chef-Zugang:
   - `Benutzername:` → z. B. `chris` tippen → **Enter**
   - `Vorname:` → tippen → **Enter**
   - `Nachname:` → tippen → **Enter**
   - `Passwort:` → tippen → **Enter**. **Beim Tippen erscheint nichts – das ist Absicht.**
     Mindestens 8 Zeichen, nicht nur Zahlen.
   - `Passwort wiederholen:` → nochmal genau gleich tippen → **Enter**
5. Danach öffnet sich der Browser mit der Anmeldeseite von PFALZ-WERK.
   Falls nicht: im Browser **http://127.0.0.1:8000** eintippen.
6. Benutzername und Passwort eingeben → **Anmelden**.

**Beenden:** Das schwarze Fenster schließen (oben rechts auf das **X**).
Solange das schwarze Fenster offen ist, läuft das Programm.

---

## D. Wenn etwas nicht klappt

- Schreib Claude **genau, was auf dem Bildschirm steht** – am besten ein **Bildschirmfoto**:
  Tasten **Windows + Umschalt + S** gleichzeitig drücken → Bereich mit der Maus aufziehen →
  im Chat mit **Strg + V** einfügen.
- Du kannst nichts kaputt machen: Deine Daten werden täglich gesichert.
