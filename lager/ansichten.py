from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from kern.module import WERKSTATT_LEITUNG
from konten.rechte import rolle_erforderlich
from material.models import Material

from . import dienst
from .formulare import BestellFormular, KorrekturFormular, WareneingangFormular
from .models import Bestellung, Lagerbewegung, bestand

RECHTE = WERKSTATT_LEITUNG  # Chef, Admin, Meister (wie Berechtigt() im Bestellassistent)


def _offene():
    return [b for b in Bestellung.objects.filter(abgeschlossen=False).select_related("material", "lieferant", "projekt")
            .prefetch_related("wareneingaenge", "lagerbewegungen") if b.ist_offen]


@rolle_erforderlich(*RECHTE)
def uebersicht(request):
    offene = sorted(_offene(), key=lambda b: ({"überfällig": 0, "einlagern": 1, "teilweise": 2}.get(b.status_text, 3),
                                              b.erwartet_am or b.bestellt_am))
    vorschlaege = dienst.vorschlaege()
    return render(request, "lager/uebersicht.html", {
        "vorschlaege": vorschlaege, "offene": offene,
        "anzahl_ueberfaellig": sum(1 for b in offene if b.status_text == "überfällig"),
        "anzahl_einlagern": sum(1 for b in offene if b.zu_lagern > 0),
        "vorschlag_wert": sum((v["wert"] or 0 for v in vorschlaege), Decimal("0")),
    })


@rolle_erforderlich(*RECHTE)
def vorschlag_bestellen(request):
    if request.method != "POST":
        return redirect("lager:uebersicht")
    if request.POST.get("alle"):
        erledigt, uebersprungen = dienst.alle_vorschlaege_bestellen(request.user)
        if erledigt:
            messages.success(request, f"{len(erledigt)} Bestellung(en) angelegt: " + ", ".join(b.bnr for b in erledigt))
        for text in uebersprungen:
            messages.error(request, text)
        return redirect("lager:uebersicht")
    material = get_object_or_404(Material, pk=request.POST.get("material"))
    try:
        from rechnungen.formulare import deutsch_lesen
        menge = Decimal(deutsch_lesen(request.POST.get("menge", "")).replace(",", "."))
        b = dienst.bestellen(material=material, menge=menge, benutzer=request.user, art=Bestellung.Art.AUTOMATISCH,
                             grund="unter Mindestbestand")
    except (dienst.LagerFehler, ArithmeticError, ValueError) as fehler:
        messages.error(request, str(fehler) if isinstance(fehler, dienst.LagerFehler) else "Bitte eine gültige Menge eintragen.")
    else:
        messages.success(request, f"Bestellung {b.bnr} angelegt: {dienst.zahl(b.menge)} {b.einheit} {material.bezeichnung} "
                                  f"bei {b.lieferant.name}.")
    return redirect("lager:uebersicht")


@rolle_erforderlich(*RECHTE)
def bestellungen(request):
    suche = request.GET.get("suche", "").strip()
    status = request.GET.get("status", "offen")
    qs = Bestellung.objects.select_related("material", "lieferant", "projekt").prefetch_related("wareneingaenge", "lagerbewegungen")
    if suche:
        qs = qs.filter(Q(bnr__icontains=suche) | Q(material__bezeichnung__icontains=suche) | Q(material__materialnr__icontains=suche)
                       | Q(lieferant__name__icontains=suche) | Q(projekt__projektnr__icontains=suche))
    liste = [b for b in qs if {"offen": b.ist_offen, "erledigt": not b.ist_offen}.get(status, True)]
    return render(request, "lager/bestellungen.html", {
        "seite": Paginator(liste, 50).get_page(request.GET.get("seite")), "anzahl": len(liste), "suche": suche, "status": status})


@rolle_erforderlich(*RECHTE)
def neu(request):
    start = {}
    if request.GET.get("material"):
        start["material"] = Material.objects.filter(pk=request.GET["material"]).first()
    if request.GET.get("projekt"):
        from projekte.models import Projekt
        start["projekt"] = Projekt.objects.filter(pk=request.GET["projekt"]).first()
    formular = BestellFormular(request.POST or None, initial=start)
    if request.method == "POST" and formular.is_valid():
        d = formular.cleaned_data
        try:
            b = dienst.bestellen(material=d["material"], menge=d["menge"], benutzer=request.user,
                                 art=Bestellung.Art.PROJEKT if d["projekt"] else Bestellung.Art.MANUELL,
                                 projekt=d["projekt"], erwartet_am=d["erwartet_am"], grund=d["grund"], notiz=d["notiz"])
        except dienst.LagerFehler as fehler:
            formular.add_error(None, str(fehler))
        else:
            messages.success(request, f"Bestellung {b.bnr} angelegt.")
            return redirect(b)
    return render(request, "lager/neu.html", {"formular": formular})


@rolle_erforderlich(*RECHTE)
def bestellung(request, pk):
    b = get_object_or_404(Bestellung.objects.select_related("material", "lieferant", "projekt"), pk=pk)
    formular = WareneingangFormular(b, request.POST or None)
    if request.method == "POST":
        aktion = request.POST.get("aktion")
        try:
            if aktion == "einlagern":
                messages.success(request, dienst.einlagern(b, request.user))
                return redirect(b)
            if aktion == "abschliessen":
                messages.success(request, dienst.abschliessen(b, request.user, request.POST.get("grund", "")))
                return redirect(b)
            if formular.is_valid():
                d = formular.cleaned_data
                messages.success(request, dienst.wareneingang(
                    b, was=d["was"], benutzer=request.user, menge=d.get("menge"), einlagern=d["einlagern"] == "ja",
                    datum=d.get("datum"), termin=d.get("termin"), mehr_bestaetigt=d.get("mehr"), notiz=d["notiz"]))
                return redirect(b)
        except dienst.LagerFehler as fehler:
            messages.error(request, str(fehler))
    return render(request, "lager/bestellung.html", {
        "b": b, "formular": formular, "eingaenge": b.wareneingaenge.select_related("erfasst_von"),
        "bewegungen": b.lagerbewegungen.select_related("erfasst_von"),
        "bestand": bestand(b.material),
    })


@rolle_erforderlich(*RECHTE)
def bestandsliste(request):
    suche = request.GET.get("suche", "").strip()
    nur = request.GET.get("nur", "lager")
    bestaende = dict(Lagerbewegung.objects.values_list("material").annotate(s=Sum("menge")).values_list("material", "s"))
    qs = Material.objects.filter(aktiv=True).order_by("bezeichnung")
    if suche:
        qs = qs.filter(Q(bezeichnung__icontains=suche) | Q(materialnr__icontains=suche) | Q(lagerplatz__icontains=suche)
                       | Q(produktgruppe__icontains=suche))
    zeilen = []
    for m in qs:
        ist = bestaende.get(m.pk) or Decimal("0")
        unter = bool(m.mindestbestand and ist < m.mindestbestand)
        if nur == "lager" and not (m.lagerartikel or m.pk in bestaende):
            continue
        if nur == "knapp" and not unter:
            continue
        zeilen.append({"m": m, "bestand": ist, "unter": unter})
    return render(request, "lager/bestand.html", {
        "zeilen": zeilen, "suche": suche, "nur": nur, "knapp": sum(1 for z in zeilen if z["unter"])})


@rolle_erforderlich(*RECHTE)
def lagerkarte(request, pk):
    m = get_object_or_404(Material, pk=pk)
    formular = KorrekturFormular(request.POST or None, initial={"neuer_bestand": bestand(m)})
    if request.method == "POST" and formular.is_valid():
        try:
            bew = dienst.korrektur(m, neuer_bestand=formular.cleaned_data["neuer_bestand"], benutzer=request.user,
                                   grund=formular.cleaned_data["grund"])
            messages.success(request, "Bestand korrigiert." if bew else "Bestand war schon richtig – nichts gebucht.")
            return redirect("lager:lagerkarte", m.pk)
        except dienst.LagerFehler as fehler:
            messages.error(request, str(fehler))
    return render(request, "lager/lagerkarte.html", {
        "m": m, "bestand": bestand(m), "offen": dienst.offene_menge(m), "formular": formular,
        "bewegungen": m.lagerbewegungen.select_related("bestellung", "erfasst_von")[:200],
        "bestellungen": m.bestellungen.prefetch_related("wareneingaenge", "lagerbewegungen")[:50],
    })
