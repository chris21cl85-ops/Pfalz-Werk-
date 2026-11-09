from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from kern.models import protokolliere
from konten.models import Rolle
from konten.rechte import rolle_erforderlich

from .formulare import KundeFormular
from .models import Kunde, naechste_kundennr

BEARBEITER = (Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG, Rolle.MEISTER)


def darf_bearbeiten(benutzer):
    return benutzer.hat_rolle(*BEARBEITER)


def liste(request):
    suche = request.GET.get("suche", "").strip()
    nur_aktive = request.GET.get("alle") != "1"
    kunden = Kunde.objects.all()
    if nur_aktive:
        kunden = kunden.filter(status=Kunde.Status.AKTIV)
    if suche:
        kunden = kunden.filter(
            Q(kundennr__icontains=suche) | Q(name__icontains=suche) | Q(ansprechpartner__icontains=suche)
            | Q(ort__icontains=suche) | Q(telefon__icontains=suche) | Q(email__icontains=suche)
            | Q(adresse_original__icontains=suche)
        )
    seite = Paginator(kunden, 50).get_page(request.GET.get("seite"))
    return render(request, "kunden/liste.html", {
        "seite": seite, "suche": suche, "nur_aktive": nur_aktive,
        "anzahl": kunden.count(), "darf_bearbeiten": darf_bearbeiten(request.user),
    })


def detail(request, pk):
    kunde = get_object_or_404(Kunde, pk=pk)
    return render(request, "kunden/detail.html", {"kunde": kunde, "darf_bearbeiten": darf_bearbeiten(request.user)})


def _aenderungen(formular):
    zeilen = []
    for feld in formular.changed_data:
        alt = formular.initial.get(feld, "")
        neu = formular.cleaned_data.get(feld, "")
        zeilen.append(f"{formular.fields[feld].label}: „{alt}“ → „{neu}“")
    return "\n".join(zeilen)


@rolle_erforderlich(*BEARBEITER)
def neu(request):
    formular = KundeFormular(request.POST or None, initial={"kundennr": naechste_kundennr(), "kundenart": "Privat"})
    if request.method == "POST" and formular.is_valid():
        kunde = formular.save()
        protokolliere("kunde_angelegt", kunde, benutzer=request.user)
        messages.success(request, f"Kunde „{kunde.name}“ wurde angelegt.")
        return redirect(kunde)
    return render(request, "kunden/formular.html", {"formular": formular, "titel": "Neuer Kunde"})


@rolle_erforderlich(*BEARBEITER)
def bearbeiten(request, pk):
    kunde = get_object_or_404(Kunde, pk=pk)
    formular = KundeFormular(request.POST or None, instance=kunde)
    if request.method == "POST" and formular.is_valid():
        if formular.has_changed():
            details = _aenderungen(formular)
            kunde = formular.save()
            protokolliere("kunde_geaendert", kunde, details=details, benutzer=request.user)
            messages.success(request, "Änderungen gespeichert.")
        else:
            messages.success(request, "Es wurde nichts geändert.")
        return redirect(kunde)
    return render(request, "kunden/formular.html", {"formular": formular, "titel": f"Kunde {kunde.kundennr} bearbeiten", "kunde": kunde})
