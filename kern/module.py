"""Kacheln der Startseite. Was noch nicht gebaut ist, zeigt seine Etappe."""
from konten.models import Rolle

ALLE = tuple(Rolle)
BUERO = (Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG)
WERKSTATT_LEITUNG = (Rolle.CHEF, Rolle.ADMIN, Rolle.MEISTER)

MODULE = [
    # (Titel, Beschreibung, Etappe, Rollen, URL-Name oder None)
    ("Kunden", "Kundenstamm und Ansprechpartner", 1, ALLE, "kunden:liste"),
    ("Projekte", "Aufträge und Baustellen", 1, ALLE, None),
    ("Material", "Platten, Beschläge, Kanten", 1, ALLE, None),
    ("Lieferanten", "Bezugsquellen und Konditionen", 1, BUERO + (Rolle.MEISTER,), None),
    ("Mitarbeiter", "Personal und Stundensätze", 1, (Rolle.CHEF, Rolle.ADMIN), None),
    ("Rechnungen", "Rechnungen, XRechnung, Mahnungen", 2, BUERO, None),
    ("Finanzen", "Zahlungen, Übersicht, DATEV-Export", 2, (Rolle.CHEF, Rolle.BUCHHALTUNG), None),
    ("Möbelrechner", "Kalkulation von Möbeln", 3, WERKSTATT_LEITUNG, None),
    ("Bestellungen & Lager", "Bestellung, Wareneingang, Bestand", 3, WERKSTATT_LEITUNG, None),
    ("Produktion", "Fertigung, Qualität, Montageplan", 3, ALLE, None),
    ("Zeiterfassung", "Stunden auf Projekte buchen", 4, ALLE, None),
    ("Auswertungen", "Zahlen für den Chef", 4, (Rolle.CHEF,), None),
    ("Excel-Import", "Daten aus der Excel-Fassung übernehmen", 0, (Rolle.CHEF, Rolle.ADMIN), "importe:uebersicht"),
    ("Sicherung", "Datensicherung anlegen und ansehen", 0, (Rolle.CHEF, Rolle.ADMIN), "sicherung:uebersicht"),
    ("Protokoll", "Wer hat wann was gemacht", 0, (Rolle.CHEF, Rolle.ADMIN), "protokoll"),
    ("Benutzer", "Zugänge und Rollen verwalten", 0, (Rolle.CHEF, Rolle.ADMIN), "admin:konten_benutzer_changelist"),
]


def module_fuer(benutzer):
    """Liefert die Kacheln, die dieser Benutzer sehen darf."""
    return [
        {"titel": t, "text": b, "etappe": e, "url": u}
        for t, b, e, rollen, u in MODULE
        if benutzer.hat_rolle(*rollen)
    ]
