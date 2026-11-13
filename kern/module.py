"""Alle Bereiche des Programms – für Startseite und Navi. Was noch nicht gebaut ist, zeigt seine Etappe."""
from konten.models import Rolle

ALLE = tuple(Rolle)
BUERO = (Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG)
WERKSTATT_LEITUNG = (Rolle.CHEF, Rolle.ADMIN, Rolle.MEISTER)
VERWALTUNG = (Rolle.CHEF, Rolle.ADMIN)

# Bereiche wie in der Excel-Fassung (Cockpit, Planung, Produktion, Material, Verwaltung)
BEREICHE = ["Büro & Planung", "Werkstatt & Material", "Geld", "Verwaltung"]

MODULE = [
    # (Titel, Beschreibung, Etappe, Rollen, URL-Name oder None, Bereich, Zeichen)
    ("Kunden", "Kundenstamm und Ansprechpartner", 1, ALLE, "kunden:liste", "Büro & Planung", "👥"),
    ("Projekte", "Aufträge und Baustellen", 1, ALLE, "projekte:liste", "Büro & Planung", "📁"),
    ("Möbelrechner", "Kalkulation von Möbeln", 3, WERKSTATT_LEITUNG, None, "Büro & Planung", "📐"),
    ("Zeiterfassung", "Stunden auf Projekte buchen", 4, ALLE, None, "Büro & Planung", "⏱"),
    ("Material", "Platten, Beschläge, Kanten", 1, ALLE, "material:liste", "Werkstatt & Material", "🪵"),
    ("Lieferanten", "Bezugsquellen und Konditionen", 1, BUERO + (Rolle.MEISTER,), "lieferanten:liste", "Werkstatt & Material", "🚚"),
    ("Bestellungen & Lager", "Bestellung, Wareneingang, Bestand", 3, WERKSTATT_LEITUNG, None, "Werkstatt & Material", "📦"),
    ("Produktion", "Fertigung, Qualität, Montageplan", 3, ALLE, None, "Werkstatt & Material", "🔨"),
    ("Rechnungen", "Rechnungen, XRechnung, Mahnungen", 2, BUERO, None, "Geld", "🧾"),
    ("Finanzen", "Zahlungen, Übersicht, DATEV-Export", 2, (Rolle.CHEF, Rolle.BUCHHALTUNG), None, "Geld", "💶"),
    ("Auswertungen", "Zahlen für den Chef", 4, (Rolle.CHEF,), None, "Geld", "📊"),
    ("Mitarbeiter", "Personal und Stundensätze", 1, VERWALTUNG, "mitarbeiter:liste", "Verwaltung", "🧑‍🔧"),
    ("Excel-Import", "Daten aus der Excel-Fassung übernehmen", 0, VERWALTUNG, "importe:uebersicht", "Verwaltung", "📥"),
    ("Sicherung", "Datensicherung anlegen und ansehen", 0, VERWALTUNG, "sicherung:uebersicht", "Verwaltung", "💾"),
    ("Protokoll", "Wer hat wann was gemacht", 0, VERWALTUNG, "protokoll", "Verwaltung", "📜"),
    ("Benutzer", "Zugänge und Rollen verwalten", 0, VERWALTUNG, "admin:konten_benutzer_changelist", "Verwaltung", "🔑"),
]


def module_fuer(benutzer):
    """Liefert die Bereiche, die dieser Benutzer sehen darf."""
    return [
        {"titel": t, "text": b, "etappe": e, "url": u, "bereich": ber, "zeichen": z}
        for t, b, e, rollen, u, ber, z in MODULE
        if benutzer.hat_rolle(*rollen)
    ]


def navi_fuer(benutzer):
    """Die Bereiche gruppiert für das Navi: [(Bereich, [Module ...]), ...]."""
    module = module_fuer(benutzer)
    gruppen = []
    for bereich in BEREICHE:
        eintraege = [m for m in module if m["bereich"] == bereich]
        if eintraege:
            gruppen.append((bereich, eintraege))
    return gruppen
