import json
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from kern.models import protokolliere
from konten.rechte import rolle_erforderlich

from . import eingang_dienst as ed
from .ansichten import BUERO
from .dienst import RechnungFehler, euro
from .formulare import EingangFormular, EingangZahlungFormular
from .models import Eingangsrechnung


@rolle_erforderlich(*BUERO)
def liste(request):
    suche = request.GET.get("suche", "").strip()
    status = request.GET.get("status", "offen")
    belege = Eingangsrechnung.objects.select_related("lieferant", "projekt").prefetch_related("zahlungen")
    if suche:
        belege = belege.filter(Q(ernr__icontains=suche) | Q(lieferant__name__icontains=suche)
                               | Q(lieferanten_nr__icontains=suche) | Q(projekt__projektnr__icontains=suche)
                               | Q(bestellung__icontains=suche) | Q(kategorie__icontains=suche))
    alle = list(belege)
    filter_ = {
        "offen": lambda e: e.offen > Decimal("0.005"),
        "ueberfaellig": lambda e: e.ist_ueberfaellig,
        "bezahlt": lambda e: not e.ist_storniert and e.offen <= Decimal("0.005"),
        "storniert": lambda e: e.ist_storniert,
        "alle": lambda e: True,
    }.get(status, lambda e: True)
    treffer = [e for e in alle if filter_(e)]
    return render(request, "eingang/liste.html", {
        "seite": Paginator(treffer, 50).get_page(request.GET.get("seite")), "anzahl": len(treffer),
        "suche": suche, "status": status,
        "stati": [("offen", "Offen (zu bezahlen)"), ("ueberfaellig", "Überfällig"), ("bezahlt", "Bezahlt"),
                  ("storniert", "Storniert"), ("alle", "Alle")],
        "zu_zahlen": sum((e.offen for e in alle if e.offen > 0), Decimal("0")),
        "ueberfaellig": sum((e.offen for e in alle if e.ist_ueberfaellig), Decimal("0")),
        "skonto_bald": [e for e in alle if e.offen > 0 and e.skonto_moeglich(timezone.localdate())],
    })


@rolle_erforderlich(*BUERO)
def neu(request):
    formular = EingangFormular(request.POST or None, request.FILES or None)
    if request.method == "POST" and formular.is_valid():
        d = formular.cleaned_data
        try:
            er = ed.erfassen(
                lieferant_name=d["lieferant"], lieferanten_nr=d["lieferanten_nr"], datum=d["datum"],
                kategorie=d["kategorie"], projekt=d["projekt"], netto=d["netto"], ust_satz=Decimal(d["ust_satz"]),
                ziel_tage=d["ziel_tage"], skonto_prozent=d.get("skonto_prozent"), skonto_tage=d.get("skonto_tage"),
                bestellung=d["bestellung"], notiz=d["notiz"], beleg=d.get("beleg"), benutzer=request.user)
        except RechnungFehler as fehler:
            formular.add_error(None, str(fehler))
        else:
            messages.success(request, f"Erfasst: {er.ernr} – {er.lieferant.name}, {euro(er.brutto)}, "
                                      f"fällig {er.faellig:%d.%m.%Y}.")
            if "weiter" in request.POST:
                return redirect("eingang:neu")
            return redirect(er)
    vorgaben = {l.name: ed.lieferanten_vorgaben(l) for l in formular.lieferanten}
    return render(request, "eingang/neu.html", {
        "formular": formular,
        "vorgaben": json.dumps({k: {f: str(w) for f, w in v.items()} for k, v in vorgaben.items() if v}),
    })


@rolle_erforderlich(*BUERO)
def detail(request, pk):
    er = get_object_or_404(Eingangsrechnung.objects.select_related("lieferant", "projekt"), pk=pk)
    return render(request, "eingang/detail.html", {
        "e": er, "zahlungen": er.zahlungen.select_related("erfasst_von", "gegenbuchung_zu"),
        "zahlung_formular": EingangZahlungFormular(er) if er.offen > Decimal("0.005") else None,
    })


@rolle_erforderlich(*BUERO)
def zahlung(request, pk):
    er = get_object_or_404(Eingangsrechnung, pk=pk)
    if request.method != "POST":
        return redirect(er)
    formular = EingangZahlungFormular(er, request.POST)
    if formular.is_valid():
        d = formular.cleaned_data
        try:
            z = ed.bezahlen(er, art=d["art"], datum=d["datum"], betrag=d.get("betrag"), konto=d["konto"],
                            notiz=d["notiz"], benutzer=request.user)
        except RechnungFehler as fehler:
            messages.error(request, str(fehler))
        else:
            er = Eingangsrechnung.objects.get(pk=pk)
            messages.success(request, f"Zahlung {z.znr} über {euro(z.betrag)} gebucht. Status: {er.status_text}.")
    else:
        fehler = "; ".join(" ".join(e) for e in formular.errors.values())
        messages.error(request, f"Zahlung nicht gebucht – {fehler}")
    return redirect(er)


@rolle_erforderlich(*BUERO)
def stornieren(request, pk):
    er = get_object_or_404(Eingangsrechnung, pk=pk)
    if request.method == "POST":
        try:
            ed.erfassung_stornieren(er, benutzer=request.user, grund=request.POST.get("grund", ""))
            messages.success(request, f"{er.ernr} ist storniert. Bei Bedarf jetzt richtig neu erfassen.")
        except RechnungFehler as fehler:
            messages.error(request, str(fehler))
    return redirect(er)


@rolle_erforderlich(*BUERO)
def beleg(request, pk):
    er = get_object_or_404(Eingangsrechnung, pk=pk)
    if not er.beleg:
        return redirect(er)
    protokolliere("eingangsbeleg_abgerufen", er.ernr, benutzer=request.user)
    antwort = HttpResponse(bytes(er.beleg), content_type=er.beleg_typ or "application/octet-stream")
    antwort["Content-Disposition"] = f'inline; filename="{er.ernr}_{er.beleg_name}"'
    return antwort
