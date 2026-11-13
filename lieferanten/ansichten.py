from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from kern.blaettern import aenderungen, nachbarn
from kern.models import protokolliere
from konten.models import Rolle
from konten.rechte import rolle_erforderlich

from .formulare import LieferantFormular
from .models import Lieferant

LESER = (Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG, Rolle.MEISTER)


@rolle_erforderlich(*LESER)
def liste(request):
    suche = request.GET.get("suche", "").strip()
    alle = request.GET.get("alle") == "1"
    lieferanten = Lieferant.objects.annotate(anzahl_material=Count("material")).order_by("name")
    if not alle:
        lieferanten = lieferanten.filter(aktiv=True)
    if suche:
        lieferanten = lieferanten.filter(Q(name__icontains=suche) | Q(ansprechpartner__icontains=suche)
                                         | Q(ort__icontains=suche) | Q(telefon__icontains=suche))
    return render(request, "lieferanten/liste.html", {
        "seite": Paginator(lieferanten, 50).get_page(request.GET.get("seite")),
        "anzahl": lieferanten.count(), "suche": suche, "alle": alle,
    })


@rolle_erforderlich(*LESER)
def detail(request, pk):
    lieferant = get_object_or_404(Lieferant, pk=pk)
    return render(request, "lieferanten/detail.html", {
        "l": lieferant, "material": lieferant.material.order_by("bezeichnung"),
        **nachbarn(Lieferant.objects.order_by("name", "pk"), lieferant),
    })


@rolle_erforderlich(*LESER)
def neu(request):
    formular = LieferantFormular(request.POST or None, initial={"aktiv": True})
    if request.method == "POST" and formular.is_valid():
        lieferant = formular.save()
        protokolliere("lieferant_angelegt", lieferant, benutzer=request.user)
        messages.success(request, f"Lieferant „{lieferant.name}“ wurde angelegt.")
        return redirect(lieferant)
    return render(request, "lieferanten/formular.html", {"formular": formular, "titel": "Neuer Lieferant"})


@rolle_erforderlich(*LESER)
def bearbeiten(request, pk):
    lieferant = get_object_or_404(Lieferant, pk=pk)
    formular = LieferantFormular(request.POST or None, instance=lieferant)
    if request.method == "POST" and formular.is_valid():
        if formular.has_changed():
            details = aenderungen(formular)
            lieferant = formular.save()
            protokolliere("lieferant_geaendert", lieferant, details=details, benutzer=request.user)
            messages.success(request, "Änderungen gespeichert.")
        else:
            messages.success(request, "Es wurde nichts geändert.")
        return redirect(lieferant)
    return render(request, "lieferanten/formular.html",
                  {"formular": formular, "titel": f"{lieferant.name} bearbeiten", "l": lieferant})
