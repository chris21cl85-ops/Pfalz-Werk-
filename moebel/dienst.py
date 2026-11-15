"""Abläufe des Möbelrechners: Rechnen, Speichern (Version), Kopieren (Variante), In Stückliste, Druckliste."""
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.db import transaction
from django.utils import timezone

from kern.models import protokolliere
from material.models import Material

from . import rechner
from .models import MoebelPosition, Regelwerk


class MoebelFehler(Exception):
    pass


def materialstamm():
    """Materialstamm als Nachschlage-Funktion für den Rechner."""
    stamm = {m.materialnr: rechner.Material(
        nr=m.materialnr, bezeichnung=m.bezeichnung, einheit=m.einheit, staerke=float(m.staerke_mm or 0),
        format=m.format, ek=float(m.ek_netto) if m.ek_netto is not None else None, aktiv=m.aktiv)
        for m in Material.objects.all()}
    return lambda nr: stamm.get(nr) or next((v for k, v in stamm.items() if k.lower() == (nr or "").lower()), None)


def rechnen(eingaben: dict) -> dict:
    return rechner.berechnen(eingaben, Regelwerk.laden().als_regeln(), materialstamm())


def naechste_pos(projekt) -> str:
    """M01, M02 … je Projekt (wie NaechstePos())."""
    hoechste = 0
    for pos in projekt.moebel.values_list("pos", flat=True):
        ziffern = "".join(z for z in pos if z.isdigit())
        hoechste = max(hoechste, int(ziffern or 0))
    return f"M{hoechste + 1:02d}"


def speichern(*, projekt, eingaben, benutzer, position=None) -> MoebelPosition:
    ergebnis = rechnen(eingaben)
    bez = (eingaben.get("bezeichnung") or eingaben.get("typ") or "Möbel").strip()
    with transaction.atomic():
        if position is None:
            position = MoebelPosition(projekt=projekt, pos=naechste_pos(projekt), gespeichert_von=benutzer)
            aktion = "moebel_angelegt"
        else:
            if position.eingaben != eingaben:
                position.version += 1
                position.status = MoebelPosition.Status.ENTWURF  # Stückliste muss neu übernommen werden
            aktion = "moebel_geaendert"
        position.bezeichnung, position.eingaben, position.ergebnis = bez, eingaben, ergebnis
        position.gespeichert_von = benutzer
        position.save()
    protokolliere(aktion, position.positions_id, benutzer=benutzer, details=(
        f"{bez} {position.masse} · {len(ergebnis['teile'])} Zeilen · Material {ergebnis['kosten']:.2f} € · "
        f"Ampel {['grün', 'gelb', 'rot'][ergebnis['ampel']]} · Version {position.version}"))
    return position


def kopieren(position, benutzer) -> MoebelPosition:
    """Wie PW_Moebel_Position_Kopieren: gleiche Eingaben unter neuer Positionsnummer (Variante)."""
    eingaben = dict(position.eingaben)
    eingaben["bezeichnung"] = f"{position.bezeichnung} (Variante)"
    return speichern(projekt=position.projekt, eingaben=eingaben, benutzer=benutzer)


def in_stueckliste(position, benutzer) -> int:
    """Wie PW_Moebel_In_Stueckliste: Materialbedarf als „Geplant“ in die Stückliste; frühere geplante Zeilen dieser
    Position werden ersetzt. Bei roter Ampel oder schon weiterverarbeiteten Zeilen keine Übernahme."""
    from kalkulation.models import Stuecklistenposition
    ergebnis = rechnen(position.eingaben)  # neu rechnen wie im Makro
    if ergebnis["ampel"] == rechner.ROT:
        raise MoebelFehler("Die Prüfung zeigt Rot – keine Übernahme. Erst die roten Punkte beheben.")
    alt = Stuecklistenposition.objects.filter(moebel=position)
    weiter = alt.exclude(status=Stuecklistenposition.Status.GEPLANT)
    if weiter.exists():
        raise MoebelFehler(f"Material dieser Position ist in der Stückliste schon weiterverarbeitet (Status "
                           f"{weiter.first().status}). Änderung bitte direkt in der Stückliste klären.")
    stamm = {m.materialnr: m for m in Material.objects.filter(materialnr__in=[b["material"] for b in ergebnis["bedarf"]])}
    with transaction.atomic():
        alt.delete()
        pos = max(position.projekt.stueckliste.values_list("pos", flat=True), default=0)
        n = 0
        for b in ergebnis["bedarf"]:
            if b["menge"] <= 0:
                continue
            pos += 1
            m = stamm.get(b["material"])
            Stuecklistenposition.objects.create(
                projekt=position.projekt, pos=pos, material=m, menge=Decimal(str(b["menge"])),
                bezeichnung=b["bezeichnung"] if m else f"{b['material']} (fehlt im Materialstamm)",
                einheit=b["einheit"] or "Stk", ek=m.ek_netto if m else None, status=Stuecklistenposition.Status.GEPLANT,
                moebel=position, notiz=f"Möbelrechner {position.positions_id}: {b['grund']}"[:300])
            n += 1
        position.ergebnis = ergebnis
        position.status = MoebelPosition.Status.STUECKLISTE
        position.save(update_fields=["ergebnis", "status", "gespeichert_am"])
    protokolliere("moebel_in_stueckliste", position.positions_id, benutzer=benutzer,
                  details=f"{n} Materialpositionen (Status Geplant) in Projekt {position.projekt.projektnr}")
    return n


def druckliste_pdf(position) -> bytes:
    """Teile- und Beschlagliste wie Blatt „Möbel-Druck“ (A4 quer)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    e, erg = position.eingaben, position.ergebnis
    klein = ParagraphStyle("k", fontName="Helvetica", fontSize=8, leading=10)
    fett = ParagraphStyle("f", fontName="Helvetica-Bold", fontSize=14, leading=18)
    normal = ParagraphStyle("n", fontName="Helvetica", fontSize=9, leading=12)

    def p(text, stil=klein):
        return Paragraph(escape(str(text if text is not None else "")), stil)

    puffer = BytesIO()
    doc = SimpleDocTemplate(puffer, pagesize=landscape(A4), leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.2 * cm, title=f"Teileliste {position.positions_id}")
    kopf = [p(f"Teile- und Beschlagliste · {position.positions_id}  {position.bezeichnung}", fett),
            p(f"PROJEKT {position.projekt.projektnr} · {position.projekt.name}    KUNDE {position.projekt.kunde.name}    "
              f"MÖBEL {e.get('typ', '')} · {position.masse}    KORPUS / FRONT {e.get('mat_korpus', '')} / {e.get('mat_front', '')}"
              f"    Anzahl {e.get('anzahl') or 1} · Version {position.version} · gedruckt {timezone.localtime():%d.%m.%Y %H:%M}", normal),
            Spacer(1, 0.3 * cm)]
    zeilen = [[p(t) for t in ("Nr.", "Teil", "Stk", "Fertig L × B", "Zuschnitt L × B", "St.", "Material", "Kanten",
                              "Maserung", "Bearbeitung / Einbauort", "✓")]]
    nr = 0
    for t in erg.get("teile", []):
        if t["l"] is None:
            continue
        nr += 1
        kanten = " / ".join(k for k in (t["kl1"], t["kl2"], t["kb1"], t["kb2"]) if k) or "–"
        zeilen.append([p(nr), p(t["teil"]), p(f"{t['menge']:g}"), p(f"{t['l']:g} × {t['b']:g}"),
                       p(f"{t['zl']:g} × {t['zb']:g}"), p(f"{t['dicke']:g}"), p(t["material"]), p(kanten), p(t["maser"]),
                       p("; ".join(x for x in (t["bearbeitung"], t["ort"], t["hinweis"]) if x)), p("☐")])
    for t in erg.get("teile", []):
        if t["l"] is None:
            nr += 1
            zeilen.append([p(nr), p(t["teil"]), p(f"{t['menge']:g}"), p(""), p(""), p(""), p(t["material"] or "–"),
                           p(""), p(""), p("; ".join(x for x in (t["ort"], t["hinweis"]) if x)), p("☐")])
    breiten = [1.0, 4.2, 1.1, 2.6, 2.6, 1.0, 3.2, 3.6, 1.9, 5.6, 0.8]
    tabelle = Table(zeilen, colWidths=[b * cm for b in breiten], repeatRows=1)
    tabelle.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(231 / 255, 236 / 255, 232 / 255)),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.Color(53 / 255, 107 / 255, 74 / 255)),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.Color(.85, .87, .86)), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    teile = kopf + [tabelle, Spacer(1, 0.4 * cm)]
    rot = [x for x in erg.get("pruefungen", []) if x["status"] > 0]
    if rot:
        teile.append(p("Prüfhinweise: " + " · ".join(f"{'ROT' if x['status'] == 2 else 'gelb'}: {x['pruefung']} – {x['hinweis']}"
                                                       for x in rot), normal))
    teile.append(p("Fachliche Vorplanung – ersetzt kein Aufmaß und keine konstruktive Detailprüfung.", klein))
    doc.build(teile)
    return puffer.getvalue()
