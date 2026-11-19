"""Abläufe der Inventur wie PW_Inventur.bas (PW_INV_Starten, PW_INV_Speichern) und Blatt „Inventur Abschluss“."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from kern.models import protokolliere

from .models import URSACHEN, Inventur, Position


class InventurFehler(Exception):
    pass


def _name(benutzer):
    from produktion.dienst import benutzername
    return benutzername(benutzer)


def naechste_invid(jahr: int) -> str:
    praefix = f"INV-{jahr}-"
    hoechste = 0
    for x in Inventur.objects.filter(invid__startswith=praefix).values_list("invid", flat=True):
        if x[len(praefix):].isdigit():
            hoechste = max(hoechste, int(x[len(praefix):]))
    return f"{praefix}{hoechste + 1:03d}"


def anlegen(*, benutzer, **werte) -> Inventur:
    inv = Inventur.objects.create(invid=naechste_invid(werte["stichtag"].year), **werte)
    protokolliere("inventur_angelegt", inv.invid, benutzer=benutzer,
                  details=f"{inv.get_art_display()}, Stichtag {inv.stichtag:%d.%m.%Y}, Bereich {inv.lagerbereich or 'alle'}")
    return inv


def starten(inv: Inventur, benutzer) -> int:
    """Wie PW_INV_Starten: Soll-Bestand (und EK) festschreiben, Status Aktiv."""
    from lager.models import bestand
    from material.models import Material
    if inv.status != Inventur.Status.VORBEREITUNG:
        raise InventurFehler("Die Inventur läuft schon oder ist abgeschlossen.")
    if Inventur.objects.filter(status=Inventur.Status.AKTIV).exclude(pk=inv.pk).exists():
        raise InventurFehler("Es läuft schon eine andere Inventur – erst diese abschließen.")
    artikel = Material.objects.filter(aktiv=True, lagerartikel=True)
    if inv.lagerbereich:
        artikel = artikel.filter(lagerplatz__iexact=inv.lagerbereich.strip())
    with transaction.atomic():
        n = 0
        for m in artikel.order_by("lagerplatz", "materialnr"):
            Position.objects.create(inventur=inv, material=m, lagerplatz=m.lagerplatz, einheit=m.einheit,
                                    soll=bestand(m), ek=m.ek_netto)
            n += 1
        if n == 0:
            raise InventurFehler("Keine Lagerartikel in diesem Bereich (Material: „Lagerartikel“ ankreuzen).")
        inv.status, inv.gestartet_am, inv.gestartet_von = Inventur.Status.AKTIV, timezone.now(), benutzer
        inv.save(update_fields=["status", "gestartet_am", "gestartet_von"])
    protokolliere("inventur_gestartet", inv.invid, benutzer=benutzer, details=f"Soll für {n} Positionen festgeschrieben")
    return n


def _menge(wert) -> Decimal:
    try:
        m = Decimal(str(wert).replace(",", "."))
    except Exception:
        raise InventurFehler("Menge als Zahl eintragen, z. B. 12 oder 3,5.")
    if m < 0:
        raise InventurFehler("Eine Menge kann nicht negativ sein.")
    return m


def zaehlen(pos: Position, menge, benutzer, bemerkung="") -> Position:
    if pos.inventur.status != Inventur.Status.AKTIV:
        raise InventurFehler("Gezählt wird erst, wenn die Inventur gestartet ist.")
    if pos.nach_ist is not None or pos.freigabe:
        raise InventurFehler("Diese Position ist schon nachgezählt bzw. entschieden – nicht mehr änderbar.")
    alt = pos.ist
    pos.ist, pos.zaehler, pos.gezaehlt_am = _menge(menge), _name(benutzer), timezone.now()
    if bemerkung:
        pos.bemerkung = bemerkung[:250]
    pos.save(update_fields=["ist", "zaehler", "gezaehlt_am", "bemerkung"])
    protokolliere("inventur_gezaehlt", f"{pos.inventur.invid} {pos.material.materialnr}", benutzer=benutzer,
                  details=f"{pos.ist:g} {pos.einheit}" + (f" (vorher {alt:g})" if alt is not None else ""))
    return pos


def nachzaehlen(pos: Position, menge, benutzer, bemerkung="") -> Position:
    """Vier-Augen: Nachzähler muss ein anderer sein als der Erstzähler."""
    if not pos.kritisch or pos.ist is None:
        raise InventurFehler("Nur kritische Abweichungen werden nachgezählt.")
    if pos.freigabe:
        raise InventurFehler("Schon entschieden.")
    name = _name(benutzer)
    if name.lower() == (pos.zaehler or "").lower():
        raise InventurFehler("Du hast die Erstzählung gemacht – die Nachzählung muss ein anderer Mitarbeiter übernehmen "
                             "(Vier-Augen).")
    pos.nach_ist, pos.nachzaehler, pos.nach_am = _menge(menge), name, timezone.now()
    pos.nach_bemerkung = (bemerkung or "")[:250]
    pos.save(update_fields=["nach_ist", "nachzaehler", "nach_am", "nach_bemerkung"])
    protokolliere("inventur_nachgezaehlt", f"{pos.inventur.invid} {pos.material.materialnr}", benutzer=benutzer,
                  details=f"Erst {pos.ist:g}, nach {pos.nach_ist:g} {pos.einheit}")
    return pos


def entscheiden(pos: Position, *, freigeben: bool, ursache: str, text: str, benutzer) -> Position:
    if not pos.freigabe_offen:
        raise InventurFehler("Hier ist nichts freizugeben (keine Abweichung, Nachzählung offen oder schon entschieden).")
    if ursache not in URSACHEN:
        raise InventurFehler("Ursache antippen.")
    pos.ursache = ursache + (f" – {text.strip()}" if text and text.strip() else "")
    pos.pruefer, pos.freigabe_am = _name(benutzer), timezone.now()
    pos.freigabe = Position.Freigabe.FREIGEGEBEN if freigeben else Position.Freigabe.ABGELEHNT
    pos.save(update_fields=["ursache", "pruefer", "freigabe", "freigabe_am"])
    protokolliere("inventur_freigabe", f"{pos.inventur.invid} {pos.material.materialnr}", benutzer=benutzer,
                  details=f"{pos.freigabe}: {pos.ursache}; Korrektur {pos.korrektur:g} {pos.einheit} ({pos.wert_freigabe} €)")
    return pos


def pruefung(inv: Inventur) -> dict:
    """Wie Blatt „Inventur Abschluss“: Prüfpunkte und Gesamtstatus."""
    p = list(inv.positionen.select_related("material", "inventur"))
    d = {"positionen": len(p), "gezaehlt": sum(x.gezaehlt for x in p),
         "nachzaehlung_offen": sum(x.nachzaehlung_offen for x in p), "freigaben_offen": sum(x.freigabe_offen for x in p),
         "abweichungen": sum(1 for x in p if x.differenz), "kritisch": sum(x.kritisch for x in p),
         "buchungen": sum(1 for x in p if x.korrektur and not x.buchung_id),
         "wert": sum((x.wert_freigabe for x in p if x.freigabe != Position.Freigabe.ABGELEHNT), Decimal("0")),
         "wert_plus": sum((x.wert_freigabe for x in p if x.freigabe == "Freigegeben" and x.wert_freigabe > 0), Decimal("0")),
         "wert_minus": sum((x.wert_freigabe for x in p if x.freigabe == "Freigegeben" and x.wert_freigabe < 0), Decimal("0"))}
    d["bereit"] = (inv.status == Inventur.Status.AKTIV and d["positionen"] > 0 and d["gezaehlt"] == d["positionen"]
                   and not d["nachzaehlung_offen"] and not d["freigaben_offen"])
    return d


def abschliessen(inv: Inventur, benutzer) -> int:
    """Korrekturen der freigegebenen Abweichungen als Lagerbewegung (Differenz zum Snapshot) buchen, dann abschließen."""
    from lager.models import Lagerbewegung
    if not pruefung(inv)["bereit"]:
        raise InventurFehler("Noch nicht abschlussbereit – erst alle Positionen zählen, nachzählen und freigeben.")
    n = 0
    with transaction.atomic():
        for pos in inv.positionen.select_related("material", "inventur"):
            if pos.korrektur and not pos.buchung_id:
                pos.buchung = Lagerbewegung.objects.create(
                    material=pos.material, datum=timezone.localdate(), art=Lagerbewegung.Art.KORREKTUR, menge=pos.korrektur,
                    notiz=f"Inventur {inv.invid}: {pos.ursache}"[:300], erfasst_von=benutzer)
                pos.save(update_fields=["buchung"])
                n += 1
        inv.status, inv.abgeschlossen_am, inv.abgeschlossen_von = Inventur.Status.ABGESCHLOSSEN, timezone.now(), benutzer
        inv.save(update_fields=["status", "abgeschlossen_am", "abgeschlossen_von"])
    protokolliere("inventur_abgeschlossen", inv.invid, benutzer=benutzer, details=f"{n} Korrekturbuchungen")
    return n


def bericht_pdf(inv: Inventur) -> bytes:
    """Wie Blatt „Inventur Bericht“ (A4)."""
    from io import BytesIO
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    d = pruefung(inv)
    kl = ParagraphStyle("k", fontName="Helvetica", fontSize=8, leading=10)
    nm = ParagraphStyle("n", fontName="Helvetica", fontSize=9.5, leading=13)
    fe = ParagraphStyle("f", fontName="Helvetica-Bold", fontSize=15, leading=19)

    def p(t, s=kl):
        return Paragraph(escape(str(t)), s)

    def z(x):
        return "" if x is None else f"{x:g}".replace(".", ",")

    def e(x):
        return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    status = ("Abgeschlossen" if inv.status == "Abgeschlossen" else "Vorläufiger Bericht – offene Punkte"
              if not d["bereit"] else "abschlussbereit")
    puffer = BytesIO()
    doc = SimpleDocTemplate(puffer, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.3 * cm,
                            bottomMargin=1.3 * cm, title=f"Inventurbericht {inv.invid}")
    kopf = [[p("Inventur-ID", nm), p(inv.invid, nm), p("Stichtag", nm), p(f"{inv.stichtag:%d.%m.%Y}", nm)],
            [p("Typ", nm), p(inv.get_art_display(), nm), p("Bereich", nm), p(inv.lagerbereich or "Alle", nm)],
            [p("Verantwortlich", nm), p(inv.verantwortlich or "–", nm), p("Zählmodus", nm), p("Blindzählung" if inv.blind else "offen", nm)],
            [p("Positionen", nm), p(d["positionen"], nm), p("Gezählt", nm), p(d["gezaehlt"], nm)],
            [p("Abweichungen", nm), p(d["abweichungen"], nm), p("Kritisch", nm), p(d["kritisch"], nm)],
            [p("Wertdifferenz", nm), p(e(d["wert"]), nm), p("Offene Freigaben", nm), p(d["freigaben_offen"], nm)],
            [p("Abgeschlossen", nm), p(f"{timezone.localtime(inv.abgeschlossen_am):%d.%m.%Y %H:%M}" if inv.abgeschlossen_am else "–", nm),
             p("Status", nm), p(status, nm)]]
    t1 = Table(kopf, colWidths=[3.5 * cm, 5.5 * cm, 3.5 * cm, 5.5 * cm])
    t1.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.Color(.85, .87, .86))]))
    zeilen = [[p(x) for x in ("Material", "Bezeichnung", "Soll", "Erst", "Nach", "Diff.", "Wert €", "Ursache / Freigabe")]]
    for x in inv.positionen.select_related("material").order_by("material__materialnr"):
        if x.differenz:
            zeilen.append([p(x.material.materialnr), p(x.material.bezeichnung[:40]), p(z(x.soll)), p(z(x.ist)),
                           p(z(x.nach_ist)), p(z((x.freigabe_ist or 0) - x.soll)), p(e(x.wert_freigabe)),
                           p(f"{x.freigabe or 'offen'} {x.ursache} {x.pruefer}".strip())])
    t2 = Table(zeilen, colWidths=[2.4 * cm, 4.2 * cm, 1.4 * cm, 1.4 * cm, 1.4 * cm, 1.4 * cm, 1.8 * cm, 4 * cm], repeatRows=1)
    t2.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.Color(231 / 255, 236 / 255, 232 / 255)),
                            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.Color(.85, .87, .86)), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    teile = [p(f"Inventurbericht {inv.invid}", fe), p(f"gedruckt {timezone.localtime():%d.%m.%Y %H:%M}", kl), Spacer(1, 0.3 * cm), t1,
             Spacer(1, 0.5 * cm), p("Abweichungen", ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11, leading=14)),
             t2 if len(zeilen) > 1 else p("Keine Abweichungen.", nm), Spacer(1, 1.2 * cm),
             p("_______________________________          _______________________________", nm),
             p("Zählverantwortlich                                                Chef / Meister", kl)]
    doc.build(teile)
    return puffer.getvalue()
