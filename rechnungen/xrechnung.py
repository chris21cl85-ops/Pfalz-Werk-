"""XRechnung 3.0 im Format UN/CEFACT CII – Aufbau 1:1 wie XmlSchreiben() im Makro PW_Rechnung
(dort mit dem KoSIT-Prüfprogramm geprüft). Reihenfolge der Elemente ist vom Standard vorgegeben – nicht umsortieren.
"""
from decimal import Decimal
from xml.etree import ElementTree as ET

RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
ET.register_namespace("rsm", RSM)
ET.register_namespace("ram", RAM)
ET.register_namespace("udt", UDT)

KLEINUNTERNEHMER_TEXT = "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."


def einheitcode(einheit: str) -> str:
    """Einheit -> UN/ECE-Code wie Einheitcode() im Makro (unbekannt = C62 „Stück“)."""
    e = (einheit or "").lower().replace(".", "").strip()
    if e in ("m", "lfm", "lfdm"):
        return "MTR"
    if e in ("m2", "m²", "qm"):
        return "MTK"
    if e in ("m3", "m³", "cbm"):
        return "MTQ"
    if e in ("h", "std", "stunde", "stunden"):
        return "HUR"
    if e == "kg":
        return "KGM"
    if e in ("l", "liter"):
        return "LTR"
    return "C62"


def dez(betrag) -> str:
    """Betrag mit Punkt und zwei Nachkommastellen (wie Dez() im Makro)."""
    return f"{Decimal(betrag):.2f}"


def zahl(wert) -> str:
    """Menge ohne überflüssige Nullen, nie in Exponentschreibweise (2.500 -> 2.5, 1.000 -> 1)."""
    text = f"{Decimal(wert).normalize():f}"
    return text


def datum(d) -> str:
    return f"{d:%Y%m%d}"


NAMENSRAUM = {"rsm": RSM, "ram": RAM, "udt": UDT}


def _el(eltern, name, text=None, **attribute):
    """Kindelement anlegen, z. B. _el(x, "ram:ID", "RE-2026-0001")."""
    praefix, kurz = name.split(":")
    e = ET.SubElement(eltern, "{" + NAMENSRAUM[praefix] + "}" + kurz, attribute)
    if text is not None:
        e.text = str(text)
    return e


def _datum_el(eltern, name, d):
    _el(_el(eltern, name), "udt:DateTimeString", datum(d), format="102")


def _adresse(eltern, strasse, plz, ort, land):
    a = _el(eltern, "ram:PostalTradeAddress")
    if plz:
        _el(a, "ram:PostcodeCode", plz)
    if strasse:
        _el(a, "ram:LineOne", strasse)
    if ort:
        _el(a, "ram:CityName", ort)
    _el(a, "ram:CountryID", (land or "DE").upper())


def _ja(wert) -> bool:
    return wert is True or str(wert).lower() in ("true", "ja", "1")


def xrechnung_xml(rechnung) -> bytes:
    """Erzeugt die XRechnung (UTF-8, ohne BOM) aus einer festgeschriebenen Rechnung."""
    fd = rechnung.firma
    kunde = rechnung.kunde
    nr = rechnung.nummer
    kleinunternehmer = _ja(fd.get("kleinunternehmer"))
    satz = Decimal(rechnung.ust_satz or 0)
    kat = "E" if kleinunternehmer or satz == 0 else "S"
    satz_text = dez(0 if kat == "E" else satz)
    typ = "326" if rechnung.art == "Abschlag" else "380"

    wurzel = ET.Element(f"{{{RSM}}}CrossIndustryInvoice")
    kontext = _el(wurzel, "rsm:ExchangedDocumentContext")
    _el(_el(kontext, "ram:BusinessProcessSpecifiedDocumentContextParameter"), "ram:ID",
        "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0")
    _el(_el(kontext, "ram:GuidelineSpecifiedDocumentContextParameter"), "ram:ID",
        "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0")

    dok = _el(wurzel, "rsm:ExchangedDocument")
    _el(dok, "ram:ID", nr)
    _el(dok, "ram:TypeCode", typ)
    _datum_el(dok, "ram:IssueDateTime", rechnung.datum)
    if kleinunternehmer:
        _el(_el(dok, "ram:IncludedNote"), "ram:Content", KLEINUNTERNEHMER_TEXT)

    handel = _el(wurzel, "rsm:SupplyChainTradeTransaction")
    for i, p in enumerate(rechnung.positionen.order_by("pos", "id"), start=1):
        zeile = _el(handel, "ram:IncludedSupplyChainTradeLineItem")
        _el(_el(zeile, "ram:AssociatedDocumentLineDocument"), "ram:LineID", i)
        _el(_el(zeile, "ram:SpecifiedTradeProduct"), "ram:Name", p.text)
        preis = Decimal(p.einzelpreis)
        _el(_el(_el(zeile, "ram:SpecifiedLineTradeAgreement"), "ram:NetPriceProductTradePrice"),
            "ram:ChargeAmount", dez(abs(preis)))
        menge = Decimal(p.menge) * (-1 if preis < 0 else 1)  # negativer Preis -> negative Menge (Preis ist nie negativ)
        _el(_el(zeile, "ram:SpecifiedLineTradeDelivery"), "ram:BilledQuantity", zahl(menge),
            unitCode=einheitcode(p.einheit))
        abrechnung = _el(zeile, "ram:SpecifiedLineTradeSettlement")
        steuer = _el(abrechnung, "ram:ApplicableTradeTax")
        _el(steuer, "ram:TypeCode", "VAT")
        _el(steuer, "ram:CategoryCode", kat)
        _el(steuer, "ram:RateApplicablePercent", satz_text)
        _el(_el(abrechnung, "ram:SpecifiedTradeSettlementLineMonetarySummation"), "ram:LineTotalAmount",
            dez(p.gesamt))

    # Verkäufer / Käufer
    vereinbarung = _el(handel, "ram:ApplicableHeaderTradeAgreement")
    _el(vereinbarung, "ram:BuyerReference", rechnung.kaeufer_referenz or kunde.kundennr)
    verkaeufer = _el(vereinbarung, "ram:SellerTradeParty")
    ust_id = (fd.get("ust_idnr") or "").replace(" ", "")
    _el(verkaeufer, "ram:ID", ust_id or fd.get("steuernummer") or fd.get("firmenname"))
    _el(verkaeufer, "ram:Name", fd.get("firmenname"))
    kontakt = _el(verkaeufer, "ram:DefinedTradeContact")
    _el(kontakt, "ram:PersonName", fd.get("inhaber") or fd.get("firmenname"))
    _el(_el(kontakt, "ram:TelephoneUniversalCommunication"), "ram:CompleteNumber", fd.get("telefon"))
    _el(_el(kontakt, "ram:EmailURIUniversalCommunication"), "ram:URIID", fd.get("email"))
    _adresse(verkaeufer, fd.get("strasse"), fd.get("plz"), fd.get("ort"), fd.get("land"))
    _el(_el(verkaeufer, "ram:URIUniversalCommunication"), "ram:URIID", fd.get("email"), schemeID="EM")
    if fd.get("steuernummer"):
        _el(_el(verkaeufer, "ram:SpecifiedTaxRegistration"), "ram:ID", fd["steuernummer"], schemeID="FC")
    if ust_id:
        _el(_el(verkaeufer, "ram:SpecifiedTaxRegistration"), "ram:ID", ust_id, schemeID="VA")
    kaeufer = _el(vereinbarung, "ram:BuyerTradeParty")
    _el(kaeufer, "ram:ID", kunde.kundennr)
    _el(kaeufer, "ram:Name", kunde.name)
    _adresse(kaeufer, kunde.strasse, kunde.plz, kunde.ort, "DE")
    if kunde.email:
        _el(_el(kaeufer, "ram:URIUniversalCommunication"), "ram:URIID", kunde.email, schemeID="EM")

    lieferung = _el(handel, "ram:ApplicableHeaderTradeDelivery")
    _datum_el(_el(lieferung, "ram:ActualDeliverySupplyChainEvent"), "ram:OccurrenceDateTime", rechnung.datum)

    # Abrechnung
    abr = _el(handel, "ram:ApplicableHeaderTradeSettlement")
    _el(abr, "ram:PaymentReference", nr)
    _el(abr, "ram:InvoiceCurrencyCode", "EUR")
    zahlart = _el(abr, "ram:SpecifiedTradeSettlementPaymentMeans")
    _el(zahlart, "ram:TypeCode", "58")  # SEPA-Überweisung
    konto = _el(zahlart, "ram:PayeePartyCreditorFinancialAccount")
    _el(konto, "ram:IBANID", (fd.get("iban") or "").replace(" ", ""))
    _el(konto, "ram:AccountName", fd.get("firmenname"))
    if fd.get("bic"):
        _el(_el(zahlart, "ram:PayeeSpecifiedCreditorFinancialInstitution"), "ram:BICID", fd["bic"].replace(" ", ""))
    steuer = _el(abr, "ram:ApplicableTradeTax")
    _el(steuer, "ram:CalculatedAmount", dez(rechnung.ust))
    _el(steuer, "ram:TypeCode", "VAT")
    if kat == "E":
        _el(steuer, "ram:ExemptionReason", "Kleinunternehmer gemäß § 19 UStG")
    _el(steuer, "ram:BasisAmount", dez(rechnung.netto))
    _el(steuer, "ram:CategoryCode", kat)
    _el(steuer, "ram:RateApplicablePercent", satz_text)
    bedingungen = _el(abr, "ram:SpecifiedTradePaymentTerms")
    if rechnung.ziel_tage == 0:
        text = "Zahlbar sofort ohne Abzug."
    else:
        text = f"Zahlbar bis {rechnung.faellig:%d.%m.%Y} ohne Abzug."
    if rechnung.skonto_prozent:
        # Skonto im Format der XRechnung: #SKONTO#TAGE=7#PROZENT=2.00# + Zeilenumbruch
        text += f"\n#SKONTO#TAGE={rechnung.skonto_tage}#PROZENT={dez(rechnung.skonto_prozent)}#\n"
    _el(bedingungen, "ram:Description", text)
    _datum_el(bedingungen, "ram:DueDateDateTime", rechnung.faellig)
    summe = _el(abr, "ram:SpecifiedTradeSettlementHeaderMonetarySummation")
    _el(summe, "ram:LineTotalAmount", dez(rechnung.netto))
    _el(summe, "ram:TaxBasisTotalAmount", dez(rechnung.netto))
    _el(summe, "ram:TaxTotalAmount", dez(rechnung.ust), currencyID="EUR")
    _el(summe, "ram:GrandTotalAmount", dez(rechnung.brutto))
    _el(summe, "ram:DuePayableAmount", dez(rechnung.brutto))

    ET.indent(wurzel, space=" ")
    return ET.tostring(wurzel, encoding="UTF-8", xml_declaration=True)


def fehlende_angaben(rechnung, fd) -> list[str]:
    """Was XRechnung zusätzlich braucht (wie Zusammenfassung() im Makro: Telefon und E-Mail)."""
    fehlt = []
    if not fd.telefon.strip():
        fehlt.append("Telefon")
    if not fd.email.strip():
        fehlt.append("E-Mail")
    if not fd.steuernummer.strip() and not fd.ust_idnr.strip():
        fehlt.append("Steuernummer oder USt-IdNr.")
    meldungen = []
    if fehlt:
        meldungen.append("Für die E-Rechnung fehlt in den Firmendaten noch: " + ", ".join(fehlt)
                         + " – oder den Haken „E-Rechnung“ entfernen.")
    k = rechnung.kunde
    if not (k.strasse and k.plz and k.ort):
        meldungen.append(f"Für die E-Rechnung braucht der Kunde {k.kundennr} Straße, PLZ und Ort in eigenen Feldern.")
    return meldungen
