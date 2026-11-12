import re

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from kern.blaettern import aenderungen, nachbarn
from kern.models import protokolliere
from konten.models import Rolle
from konten.rechte import rolle_erforderlich

from .formulare import MaterialFormular
from .models import Material

BEARBEITER = (Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG, Rolle.MEISTER)


def darf_bearbeiten(benutzer):
    return benutzer.hat_rolle(*BEARBEITER)


def darf_preise_sehen(benutzer):
    # Einkaufspreise sind Betriebsinterna – Mitarbeiter sehen sie nicht
    return benutzer.hat_rolle(*BEARBEITER)


def liste(request):
    suche = request.GET.get("suche", "").strip()
    gruppe = request.GET.get("gruppe", "")
    alle = request.GET.get("alle") == "1"
    material = Material.objects.all()
    if not alle:
        material = material.filter(aktiv=True)
    if gruppe:
        material = material.filter(produktgruppe=gruppe)
    if suche:
        material = material.filter(
            Q(materialnr__icontains=suche) | Q(bezeichnung__icontains=suche) | Q(produktgruppe__icontains=suche)
            | Q(untergruppe__icontains=suche) | Q(format__icontains=suche) | Q(lagerplatz__icontains=suche)
        )
    gruppen = sorted(set(Material.objects.values_list("produktgruppe", flat=True)) - {""})
    return render(request, "material/liste.html", {
        "seite": Paginator(material, 50).get_page(request.GET.get("seite")), "anzahl": material.count(),
        "suche": suche, "gruppe": gruppe, "gruppen": gruppen, "alle": alle,
        "darf_bearbeiten": darf_bearbeiten(request.user), "preise": darf_preise_sehen(request.user),
    })


def detail(request, pk):
    material = get_object_or_404(Material, pk=pk)
    return render(request, "material/detail.html", {
        "m": material, "darf_bearbeiten": darf_bearbeiten(request.user), "preise": darf_preise_sehen(request.user),
        **nachbarn(Material.objects.order_by("produktgruppe", "bezeichnung", "pk"), material),
    })


def naechste_materialnr() -> str:
    muster = re.compile(r"^(?P<vorne>.*?)(?P<zahl>\d+)$")
    beste = None
    for nr in Material.objects.values_list("materialnr", flat=True):
        t = muster.match(nr)
        if t and (beste is None or int(t["zahl"]) > int(beste["zahl"])):
            beste = t
    if beste is None:
        return "1"
    breite, zahl = len(beste["zahl"]), int(beste["zahl"]) + 1
    while Material.objects.filter(materialnr=f"{beste['vorne']}{str(zahl).zfill(breite)}").exists():
        zahl += 1
    return f"{beste['vorne']}{str(zahl).zfill(breite)}"


@rolle_erforderlich(*BEARBEITER)
def neu(request):
    formular = MaterialFormular(request.POST or None, initial={"materialnr": naechste_materialnr(), "aktiv": True})
    if request.method == "POST" and formular.is_valid():
        material = formular.save()
        protokolliere("material_angelegt", material, benutzer=request.user)
        messages.success(request, f"Material „{material.bezeichnung}“ wurde angelegt.")
        return redirect(material)
    return render(request, "material/formular.html", {"formular": formular, "titel": "Neues Material"})


@rolle_erforderlich(*BEARBEITER)
def bearbeiten(request, pk):
    material = get_object_or_404(Material, pk=pk)
    formular = MaterialFormular(request.POST or None, instance=material)
    if request.method == "POST" and formular.is_valid():
        if formular.has_changed():
            details = aenderungen(formular)
            material = formular.save()
            protokolliere("material_geaendert", material, details=details, benutzer=request.user)
            messages.success(request, "Änderungen gespeichert.")
        else:
            messages.success(request, "Es wurde nichts geändert.")
        return redirect(material)
    return render(request, "material/formular.html",
                  {"formular": formular, "titel": f"Material {material.materialnr} bearbeiten", "m": material})
