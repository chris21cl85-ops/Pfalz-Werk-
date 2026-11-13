"""PDF einer Rechnung – Aufbau wie Drucken() im Makro PW_Rechnung (A4 hoch, Arial/Helvetica 10)."""
import datetime as dt
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

GRUEN = colors.Color(53 / 255, 107 / 255, 74 / 255)
KOPF_HG = colors.Color(231 / 255, 236 / 255, 232 / 255)
LINIE = colors.Color(220 / 255, 225 / 255, 222 / 255)
GRAU = colors.Color(90 / 255, 90 / 255, 90 / 255)


def _stil(name, **werte):
    basis = {"fontName": "Helvetica", "fontSize": 10, "leading": 13}
    basis.update(werte)
    return ParagraphStyle(name, **basis)


NORMAL = _stil("normal")
KLEIN = _stil("klein", fontSize=8, leading=10, textColor=GRAU)
ABSENDER = _stil("absender", fontSize=7, leading=9)
FIRMA = _stil("firma", fontName="Helvetica-Bold", fontSize=16, leading=20)
TITEL = _stil("titel", fontName="Helvetica-Bold", fontSize=14, leading=18)
ZELLE = _stil("zelle", fontSize=9, leading=11)
ZELLE_R = _stil("zelle_r", fontSize=9, leading=11, alignment=TA_RIGHT)


def _p(text, stil=NORMAL):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), stil)


def euro(betrag) -> str:
    text = f"{Decimal(betrag):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} €"


def menge_text(menge) -> str:
    """Menge wie Excel-Format #,##0.## (1 statt 1,000; 2,5 statt 2,500)."""
    d = Decimal(menge).normalize()
    text = f"{d:f}"
    if "." in text:
        ganz, rest = text.split(".")
    else:
        ganz, rest = text, ""
    ganz = f"{int(ganz):,}".replace(",", ".") if ganz.lstrip("-").isdigit() else ganz
    if text.startswith("-") and not ganz.startswith("-"):
        ganz = "-" + ganz
    return f"{ganz},{rest}" if rest else ganz


def iban_text(iban: str) -> str:
    """DE02120300000000202051 -> „DE02 1203 0000 0000 2020 51“ (besser lesbar)."""
    iban = (iban or "").replace(" ", "")
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))


def _ja(wert) -> bool:
    return wert is True or str(wert).lower() in ("true", "ja", "1")


def briefkopf(fd, empfaenger, meta, breite):
    """Briefkopf, Absenderzeile, Anschrift links und Angaben rechts (wie Drucken() im Makro)."""
    teile = [_p(fd.get("firmenname", ""), FIRMA)]
    kontakt = f"{fd.get('strasse', '')}  ·  {fd.get('plz', '')} {fd.get('ort', '')}"
    if fd.get("telefon"):
        kontakt += f"  ·  Tel. {fd['telefon']}"
    if fd.get("email"):
        kontakt += f"  ·  {fd['email']}"
    teile += [_p(kontakt, KLEIN), Spacer(1, 0.8 * cm)]
    absender = f"<u>{escape(fd.get('firmenname', ''))} · {escape(fd.get('strasse', ''))} · " \
               f"{escape(fd.get('plz', ''))} {escape(fd.get('ort', ''))}</u>"
    anschrift = [Paragraph(absender, ABSENDER), Spacer(1, 2), _p(empfaenger)]
    meta_tabelle = Table([[_p(a, KLEIN), _p(b, ZELLE_R)] for a, b in meta], colWidths=[3.2 * cm, 3.8 * cm])
    meta_tabelle.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                      ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                      ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                      ("TOPPADDING", (0, 0), (-1, -1), 1),
                                      ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    block = Table([[anschrift, meta_tabelle]], colWidths=[breite - 7 * cm, 7 * cm])
    block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return teile + [block, Spacer(1, 1 * cm)]


def seitenfuss(fd, entwurf=False):
    """Fußzeile in drei Spalten wie im Makro (Firma | Bank | Steuer), ggf. Aufdruck ENTWURF."""
    links = fd.get("firmenname", "") + (f" · Inh. {fd['inhaber']}" if fd.get("inhaber") else "")
    links2 = f"{fd.get('strasse', '')}, {fd.get('plz', '')} {fd.get('ort', '')}"
    mitte = fd.get("bank", "")
    mitte2 = f"IBAN {iban_text(fd.get('iban', ''))}" + (f" · BIC {fd['bic']}" if fd.get("bic") else "")
    rechts = f"St.-Nr. {fd['steuernummer']}" if fd.get("steuernummer") else ""
    rechts2 = f"USt-IdNr. {fd['ust_idnr']}" if fd.get("ust_idnr") else ""

    def seite(leinwand, dokument):
        leinwand.saveState()
        leinwand.setFont("Helvetica", 7)
        leinwand.setFillColor(GRAU)
        y = 1.6 * cm
        leinwand.drawString(2 * cm, y, links)
        leinwand.drawString(2 * cm, y - 9, links2)
        leinwand.drawCentredString(A4[0] / 2, y, mitte)
        leinwand.drawCentredString(A4[0] / 2, y - 9, mitte2)
        leinwand.drawRightString(A4[0] - 1.5 * cm, y, rechts)
        leinwand.drawRightString(A4[0] - 1.5 * cm, y - 9, rechts2)
        leinwand.drawRightString(A4[0] - 1.5 * cm, 0.8 * cm, f"Seite {dokument.page}")
        if entwurf:
            leinwand.setFont("Helvetica-Bold", 60)
            leinwand.setFillColor(colors.Color(0.8, 0.2, 0.2, alpha=0.18))
            leinwand.translate(A4[0] / 2, A4[1] / 2)
            leinwand.rotate(40)
            leinwand.drawCentredString(0, 0, "ENTWURF")
            leinwand.setFont("Helvetica-Bold", 16)
            leinwand.drawCentredString(0, -40, "keine gültige Rechnung")
        leinwand.restoreState()
    return seite


def _tabellenstil():
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), KOPF_HG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, GRUEN),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINIE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])


def rechnung_pdf(rechnung, entwurf: bool = False) -> bytes:
    """Erzeugt das PDF. Bei ``entwurf=True`` eine Vorschau mit Aufdruck „ENTWURF“ (ohne Nummer)."""
    from .dienst import empfaenger_text
    from .models import Firmendaten, Rechnung

    fd = rechnung.firma or Firmendaten.laden().als_kopie()
    heute = timezone.localdate()
    datum = rechnung.datum or heute
    nummer = rechnung.nummer or "ENTWURF"
    summen = rechnung.summen()
    tage = rechnung.ziel_tage if rechnung.ziel_tage is not None else {"0": 0, "30": 30}.get(rechnung.zahlungsziel, 14)
    faellig = rechnung.faellig or datum + dt.timedelta(days=tage)
    skonto = rechnung.skonto_prozent or (Decimal("2") if rechnung.zahlungsziel == "14s" else Decimal("0"))
    skonto_tage = rechnung.skonto_tage or (7 if rechnung.zahlungsziel == "14s" else 0)
    kleinunternehmer = _ja(fd.get("kleinunternehmer"))
    kundentyp = rechnung.kundentyp or rechnung.kunde.kundenart
    titel = rechnung.titel
    storno = rechnung.art == Rechnung.Art.STORNO

    puffer = BytesIO()
    doc = SimpleDocTemplate(puffer, pagesize=A4, leftMargin=2 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=2.6 * cm,
                            title=f"{titel} {nummer}", author=fd.get("firmenname", ""))
    breite = A4[0] - 3.5 * cm
    teile = []

    meta = [
        ("Rechnungs-Nr.", nummer),
        ("Datum", f"{datum:%d.%m.%Y}"),
        ("Kunden-Nr.", rechnung.kunde.kundennr),
        ("Projekt", rechnung.projekt.projektnr),
        ("Leistungszeitraum", rechnung.leistungszeitraum or f"{datum:%d.%m.%Y}"),
    ]
    teile += briefkopf(fd, rechnung.empfaenger or empfaenger_text(rechnung.kunde), meta, breite)

    teile += [_p(f"{titel} Nr. {nummer}", TITEL), Spacer(1, 0.4 * cm),
              _p(f"Hiermit stornieren wir die Rechnung {rechnung.storno_von.nummer} vollständig:" if storno
                 else "Für unsere Leistungen berechnen wir Ihnen:"), Spacer(1, 0.3 * cm)]

    # Positionen
    zeilen = [[_p(t, ZELLE) if i < 2 else _p(t, ZELLE_R) for i, t in
               enumerate(["Pos", "Beschreibung", "Menge", "Einheit", "Einzelpreis", "Gesamt"])]]
    for p in rechnung.positionen.order_by("pos", "id"):
        zeilen.append([_p(p.pos, ZELLE), _p(p.text, ZELLE), _p(menge_text(p.menge), ZELLE_R),
                       _p(p.einheit, ZELLE_R), _p(euro(p.einzelpreis), ZELLE_R), _p(euro(p.gesamt), ZELLE_R)])
    spalten = [1.0 * cm, breite - 10.6 * cm, 1.8 * cm, 2.0 * cm, 2.9 * cm, 2.9 * cm]
    tabelle = Table(zeilen, colWidths=spalten, repeatRows=1)
    tabelle.setStyle(_tabellenstil())
    teile += [tabelle, Spacer(1, 0.4 * cm)]

    # Summen
    if kleinunternehmer or not summen["ust_satz"]:
        ust_zeile = ("Umsatzsteuer", euro(0))
    else:
        satz = Decimal(summen["ust_satz"]).normalize()
        ust_zeile = (f"zzgl. {satz:f} % USt", euro(summen["ust"]))
    summen_zeilen = [("Summe netto", euro(summen["netto"])), ust_zeile,
                     ("Gutschriftsbetrag" if storno else "Rechnungsbetrag", euro(summen["brutto"]))]
    summen_daten = [[_p(a, ZELLE_R), _p(b, ZELLE_R)] for a, b in summen_zeilen[:2]]
    summen_daten.append([Paragraph(f"<b>{escape(t)}</b>", ZELLE_R) for t in summen_zeilen[2]])
    summen_tabelle = Table(summen_daten, colWidths=[breite - 2.9 * cm, 2.9 * cm])
    summen_tabelle.setStyle(TableStyle([("LINEABOVE", (0, 2), (-1, 2), 0.8, colors.black)]))
    teile += [summen_tabelle, Spacer(1, 0.6 * cm)]

    # Zahlungshinweis und Pflichttexte
    konto = iban_text(fd.get("iban", "")) + (f" bei der {fd['bank']}" if fd.get("bank") else "")
    if tage == 0:
        zahlung = "Bitte überweisen Sie den Rechnungsbetrag sofort ohne Abzug"
    else:
        zahlung = f"Bitte überweisen Sie den Rechnungsbetrag bis zum {faellig:%d.%m.%Y} ohne Abzug"
    zahlung += f" auf unser Konto {konto}. Verwendungszweck: {nummer}."
    if skonto:
        bis = datum + dt.timedelta(days=skonto_tage)
        betrag = (Decimal(summen["brutto"]) * skonto / 100).quantize(Decimal("0.01"))
        zahlung += f" Bei Zahlung bis {bis:%d.%m.%Y} gewähren wir {skonto.normalize():f} % Skonto ({euro(betrag)})."
    absaetze = [] if storno else [zahlung]
    if rechnung.art == Rechnung.Art.ABSCHLAG:
        absaetze.append("Abschlagsrechnung gemäß § 632a BGB. Die Endabrechnung erfolgt mit der Schlussrechnung.")
    if kleinunternehmer:
        absaetze.append("Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.")
    if "rivat" in (kundentyp or "") and not storno:
        absaetze.append("Bitte bewahren Sie diese Rechnung zwei Jahre auf (§ 14b UStG).")
    if fd.get("fusstext"):
        absaetze.append(fd["fusstext"])
    for a in absaetze:
        teile += [_p(a), Spacer(1, 0.3 * cm)]

    seite = seitenfuss(fd, entwurf)

    doc.build(teile, onFirstPage=seite, onLaterPages=seite)
    return puffer.getvalue()


MAHN_TEXT = {
    1: "sicher ist es Ihrer Aufmerksamkeit entgangen: Zu unserer folgenden Rechnung konnten wir noch keinen "
       "Zahlungseingang feststellen.",
    2: "leider konnten wir zu unserer folgenden Rechnung trotz Erinnerung noch keinen Zahlungseingang feststellen.",
    3: "leider konnten wir zu unserer folgenden Rechnung trotz Erinnerung noch keinen Zahlungseingang feststellen.",
}


def mahnung_pdf(mahnung, fd) -> bytes:
    """Zahlungserinnerung / Mahnung – Aufbau wie der Mahnteil von Drucken() im Makro."""
    r = mahnung.rechnung
    firma = fd.als_kopie()
    titel = mahnung.get_stufe_display()
    puffer = BytesIO()
    doc = SimpleDocTemplate(puffer, pagesize=A4, leftMargin=2 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=2.6 * cm,
                            title=f"{titel} zu {r.nummer}", author=firma.get("firmenname", ""))
    breite = A4[0] - 3.5 * cm
    meta = [("Rechnungs-Nr.", r.nummer), ("Datum", f"{mahnung.datum:%d.%m.%Y}"),
            ("Kunden-Nr.", r.kunde.kundennr), ("Projekt", r.projekt.projektnr),
            ("Rechnung vom", f"{r.datum:%d.%m.%Y}")]
    teile = briefkopf(firma, r.empfaenger, meta, breite)
    teile += [_p(titel, TITEL), Spacer(1, 0.4 * cm), _p("Sehr geehrte Damen und Herren,"), Spacer(1, 0.2 * cm),
              _p(MAHN_TEXT[mahnung.stufe]), Spacer(1, 0.4 * cm)]
    zeilen = [[_p(t, ZELLE) if i == 0 else _p(t, ZELLE_R) for i, t in enumerate(["Rechnung", "fällig seit", "offen"])],
              [_p(f"{r.nummer} vom {r.datum:%d.%m.%Y}  ({euro(r.brutto)})", ZELLE),
               _p(f"{r.faellig:%d.%m.%Y}", ZELLE_R), _p(euro(mahnung.offen), ZELLE_R)]]
    if mahnung.gebuehr:
        zeilen.append([_p("Mahngebühr", ZELLE), _p("", ZELLE_R), _p(euro(mahnung.gebuehr), ZELLE_R)])
    tabelle = Table(zeilen, colWidths=[breite - 5.8 * cm, 2.9 * cm, 2.9 * cm])
    tabelle.setStyle(_tabellenstil())
    summe = Table([[Paragraph("<b>Zu zahlen</b>", ZELLE_R), Paragraph(f"<b>{escape(euro(mahnung.zu_zahlen))}</b>", ZELLE_R)]],
                  colWidths=[breite - 2.9 * cm, 2.9 * cm])
    summe.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black)]))
    teile += [tabelle, Spacer(1, 0.3 * cm), summe, Spacer(1, 0.6 * cm)]
    teile += [_p(f"Bitte überweisen Sie den Betrag bis zum {mahnung.frist:%d.%m.%Y} auf unser Konto "
                 f"{iban_text(firma.get('iban', ''))}. Verwendungszweck: {r.nummer}. Sollten Sie bereits gezahlt "
                 "haben, betrachten Sie dieses Schreiben bitte als gegenstandslos."), Spacer(1, 0.3 * cm),
              _p("Mit freundlichen Grüßen"), Spacer(1, 0.2 * cm), _p(firma.get("firmenname", ""))]
    doc.build(teile, onFirstPage=seitenfuss(firma), onLaterPages=seitenfuss(firma))
    return puffer.getvalue()
