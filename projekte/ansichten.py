import re

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from kern.blaettern import aenderungen, nachbarn
from kern.models import protokolliere
from konten.models import Rolle
from konten.rechte import rolle_erforderlich
from kunden.models import Kunde

from .formulare import ProjektFormular
from .models import ABGESCHLOSSEN, Projekt

BEARBEITER = (Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG, Rolle.MEISTER)


def darf_bearbeiten(benutzer):
    return benutzer.hat_rolle(*BEARBEITER)


def _gefiltert(request):
    suche = request.GET.get("suche", "").strip()
    status = request.GET.get("status", "offen")
    projekte = Projekt.objects.select_related("kunde")
    if status == "offen":
        for s in ABGESCHLOSSEN:
            projekte = projekte.exclude(status__iexact=s)
    elif status != "alle":
        projekte = projekte.filter(status__iexact=status)
    if suche:
        projekte = projekte.filter(
            Q(projektnr__icontains=suche) | Q(name__icontains=suche) | Q(kunde__name__icontains=suche)
            | Q(kunde__kundennr__icontains=suche) | Q(projektpate__icontains=suche)
            | Q(projektart__icontains=suche) | Q(naechster_schritt__icontains=suche)
        )
    return projekte, suche, status


def liste(request):
    projekte, suche, status = _gefiltert(request)
    stati = sorted(set(Projekt.objects.values_list("status", flat=True)))
    return render(request, "projekte/liste.html", {
        "seite": Paginator(projekte, 50).get_page(request.GET.get("seite")),
        "anzahl": projekte.count(), "suche": suche, "status": status, "stati": stati,
        "darf_bearbeiten": darf_bearbeiten(request.user),
    })


def detail(request, pk):
    projekt = get_object_or_404(Projekt.objects.select_related("kunde"), pk=pk)
    darf_rechnungen = request.user.hat_rolle(Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG)
    return render(request, "projekte/detail.html", {
        "projekt": projekt, "darf_bearbeiten": darf_bearbeiten(request.user),
        "darf_rechnungen": darf_rechnungen,
        "rechnungen": projekt.rechnungen.exclude(status="Verworfen").prefetch_related("zahlungen") if darf_rechnungen else [],
        **nachbarn(Projekt.objects.order_by("-projektnr"), projekt),
    })


def naechste_projektnr() -> str:
    """Nächste freie Nummer im bisherigen Muster (z. B. P-2026-014 -> P-2026-015)."""
    muster = re.compile(r"^(?P<vorne>.*?)(?P<zahl>\d+)$")
    beste = None
    for nr in Projekt.objects.values_list("projektnr", flat=True):
        t = muster.match(nr)
        if t and (beste is None or int(t["zahl"]) > int(beste["zahl"])):
            beste = t
    if beste is None:
        return "1"
    breite = len(beste["zahl"])
    zahl = int(beste["zahl"]) + 1
    while Projekt.objects.filter(projektnr=f"{beste['vorne']}{str(zahl).zfill(breite)}").exists():
        zahl += 1
    return f"{beste['vorne']}{str(zahl).zfill(breite)}"


@rolle_erforderlich(*BEARBEITER)
def neu(request):
    start = {"projektnr": naechste_projektnr(), "status": "Planung"}
    if request.GET.get("kunde"):
        start["kunde"] = Kunde.objects.filter(pk=request.GET["kunde"]).first()
    formular = ProjektFormular(request.POST or None, initial=start)
    if request.method == "POST" and formular.is_valid():
        projekt = formular.save()
        protokolliere("projekt_angelegt", projekt, details=f"Kunde: {projekt.kunde}", benutzer=request.user)
        messages.success(request, f"Projekt „{projekt.name}“ wurde angelegt.")
        return redirect(projekt)
    return render(request, "projekte/formular.html", {"formular": formular, "titel": "Neues Projekt"})


@rolle_erforderlich(*BEARBEITER)
def bearbeiten(request, pk):
    projekt = get_object_or_404(Projekt, pk=pk)
    formular = ProjektFormular(request.POST or None, instance=projekt)
    if request.method == "POST" and formular.is_valid():
        if formular.has_changed():
            details = aenderungen(formular)
            projekt = formular.save()
            protokolliere("projekt_geaendert", projekt, details=details, benutzer=request.user)
            messages.success(request, "Änderungen gespeichert.")
        else:
            messages.success(request, "Es wurde nichts geändert.")
        return redirect(projekt)
    return render(request, "projekte/formular.html",
                  {"formular": formular, "titel": f"Projekt {projekt.projektnr} bearbeiten", "projekt": projekt})
