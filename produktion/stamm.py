"""Startwerte wie in der Excel: Blatt „Produktion Arbeitsgangbibliothek“ und „Produktion Routenvorlagen“.
Werden per Excel-Import ergänzt bzw. aktualisiert."""

# Code, Kategorie, Arbeitsgang, Typ, Standardfolge, QM danach?, Wartezeit möglich?
BIBLIOTHEK = [
    ("VOR-010", "Vorbereitung", "Material bereitstellen", "Logistik", 10, False, False),
    ("VOR-020", "Vorbereitung", "Holzfeuchte prüfen", "QM", 20, True, False),
    ("PL-010", "Plattenzuschnitt", "Grobzuschnitt", "Arbeitszeit", 30, False, False),
    ("PL-020", "Plattenzuschnitt", "Feinzuschnitt / Formatieren", "Maschinenzeit", 40, True, False),
    ("KA-010", "Kante", "Kante anleimen", "Maschinenzeit", 50, True, False),
    ("MH-010", "Massivholz", "Grob besäumen", "Maschinenzeit", 30, False, False),
    ("MH-020", "Massivholz", "Ablängen", "Maschinenzeit", 40, False, False),
    ("MH-030", "Massivholz", "Abrichten Fläche / Winkel", "Maschinenzeit", 50, True, False),
    ("MH-040", "Massivholz", "Auf Dicke hobeln", "Maschinenzeit", 60, True, False),
    ("MH-050", "Verleimen", "Lamellen sortieren / legen", "Arbeitszeit", 70, False, False),
    ("MH-060", "Verleimen", "Verleimen / Pressen", "Arbeitszeit", 80, False, True),
    ("WZ-010", "Prozesszeit", "Abbinden / Aushärten", "Prozess-/Wartezeit", 90, False, True),
    ("CNC-010", "CNC", "CNC rüsten / Programm prüfen", "Arbeitszeit", 100, False, False),
    ("CNC-020", "CNC", "Fräsen / Bohren / Nuten / Ausschnitte", "Maschinenzeit", 110, True, False),
    ("BE-010", "Bearbeitung", "Fräsen / Bohren / Dübeln", "Arbeitszeit", 120, True, False),
    ("SL-010", "Schleifen", "Grobschliff", "Arbeitszeit", 130, False, False),
    ("SL-020", "Schleifen", "Feinschliff / Kantenschliff", "Arbeitszeit", 140, True, False),
    ("OF-010", "Oberfläche", "Beizen / Grundieren / Ölen", "Arbeitszeit", 150, False, True),
    ("OF-020", "Oberfläche", "Lackieren", "Arbeitszeit", 160, False, True),
    ("WZ-020", "Prozesszeit", "Trocknen / Aushärten", "Prozess-/Wartezeit", 170, True, True),
    ("MO-010", "Montage", "Vormontage", "Arbeitszeit", 180, True, False),
    ("MO-020", "Montage", "Beschläge montieren / einstellen", "Arbeitszeit", 190, True, False),
    ("LOG-010", "Logistik", "Verpacken / Verladen", "Logistik", 200, True, False),
    ("QM-010", "QM", "Maße / Winkel prüfen", "QM", 900, False, False),
    ("QM-020", "QM", "Bohrbild / Fräsungen prüfen", "QM", 910, False, False),
    ("QM-030", "QM", "Oberfläche / Sichtprüfung", "QM", 920, False, False),
    ("QM-040", "QM", "Funktion / Endkontrolle", "QM", 930, False, False),
    ("NA-010", "Sonderfall", "Nacharbeit", "Nacharbeit", 950, True, False),
]

# Route, Werkstoffgruppe, [(Code, Plan-Std., Wartezeit Std., Hinweis)]
ROUTEN = [
    ("Plattenmöbel Standard", "Plattenwerkstoff", [
        ("VOR-010", 0, 0, "Material vollständig prüfen"), ("PL-010", 0, 0, ""), ("PL-020", 0, 0, "Maße prüfen"),
        ("KA-010", 0, 0, "Kantenbild prüfen"), ("CNC-010", 0, 0, "Programm/Zeichnung prüfen"),
        ("CNC-020", 0, 0, "QM danach"), ("QM-020", 0, 0, "Freigabe vor Weiterbearbeitung"), ("SL-020", 0, 0, ""),
        ("MO-010", 0, 0, ""), ("MO-020", 0, 0, ""), ("QM-040", 0, 0, "Endfreigabe"), ("LOG-010", 0, 0, "")]),
    ("Massivholz verleimt", "Massivholz", [
        ("VOR-020", 0, 0, "Holzfeuchte/Materialzustand"), ("VOR-010", 0, 0, ""), ("MH-010", 0, 0, ""),
        ("MH-020", 0, 0, ""), ("MH-030", 0, 0, "Winkel/Fläche prüfen"), ("MH-040", 0, 0, "Maßkontrolle"),
        ("QM-010", 0, 0, "Freigabe vor Verleimen"), ("MH-050", 0, 0, "Bild/Farbe beachten"),
        ("MH-060", 0, 0, "Leim/Pressdruck beachten"), ("WZ-010", 0, 2, "Richtwert – Herstellerangabe hat Vorrang"),
        ("PL-020", 0, 0, ""), ("BE-010", 0, 0, "QM bei Maß-/Bohrkritik"), ("SL-010", 0, 0, ""), ("SL-020", 0, 0, ""),
        ("QM-010", 0, 0, "Vor Oberfläche"), ("OF-010", 0, 0, "Oberflächenaufbau projektabhängig"),
        ("WZ-020", 0, 8, "Richtwert – Produktdatenblatt beachten"), ("QM-030", 0, 0, "Nacharbeit bei Fehler"),
        ("MO-010", 0, 0, ""), ("QM-040", 0, 0, "Endfreigabe"), ("LOG-010", 0, 0, "")]),
    ("MDF lackiert", "MDF/Lack", [
        ("VOR-010", 0, 0, ""), ("PL-010", 0, 0, ""), ("PL-020", 0, 0, ""), ("CNC-010", 0, 0, ""),
        ("CNC-020", 0, 0, "QM danach"), ("QM-020", 0, 0, "Freigabe vor Oberfläche"),
        ("SL-010", 0, 0, "Kanten/Flächen vorbereiten"), ("OF-010", 0, 0, "Hier: Grundieren/Füllern"),
        ("WZ-020", 0, 2, "Richtwert – Produktdatenblatt beachten"), ("SL-020", 0, 0, "Zwischenschliff"),
        ("OF-020", 0, 0, "Lackaufbau projektabhängig"), ("WZ-020", 0, 8, "Richtwert – Produktdatenblatt beachten"),
        ("QM-030", 0, 0, "Nacharbeit bei Fehler"), ("MO-010", 0, 0, ""), ("MO-020", 0, 0, ""),
        ("QM-040", 0, 0, "Endfreigabe"), ("LOG-010", 0, 0, "")]),
]
