from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from kern.blaettern import aenderungen, nachbarn
from kern.models import protokolliere
from konten.models import Rolle
from konten.rechte import rolle_erforderlich

from .formulare import MitarbeiterFormular
from .models import Mitarbeiter

VERWALTUNG = (Rolle.CHEF, Rolle.ADMIN)


@rolle_erforderlich(*VERWALTUNG)
def liste(request):
    suche = request.GET.get("suche", "").strip()
    alle = request.GET.get("alle") == "1"
    leute = Mitarbeiter.objects.select_related("benutzer")
    if not alle:
        leute = leute.filter(aktiv=True)
    if suche:
        leute = leute.filter(Q(kuerzel__icontains=suche) | Q(name__icontains=suche) | Q(rolle__icontains=suche))
    return render(request, "mitarbeiter/liste.html", {"leute": leute, "suche": suche, "alle": alle})


@rolle_erforderlich(*VERWALTUNG)
def detail(request, pk):
    m = get_object_or_404(Mitarbeiter.objects.select_related("benutzer"), pk=pk)
    return render(request, "mitarbeiter/detail.html", {"m": m, **nachbarn(Mitarbeiter.objects.order_by("name", "pk"), m)})


@rolle_erforderlich(*VERWALTUNG)
def neu(request):
    formular = MitarbeiterFormular(request.POST or None, initial={"aktiv": True, "team_taeglich_verfuegbar": True})
    if request.method == "POST" and formular.is_valid():
        m = formular.save()
        protokolliere("mitarbeiter_angelegt", m, benutzer=request.user)
        messages.success(request, f"Mitarbeiter „{m.name}“ wurde angelegt.")
        return redirect(m)
    return render(request, "mitarbeiter/formular.html", {"formular": formular, "titel": "Neuer Mitarbeiter"})


@rolle_erforderlich(*VERWALTUNG)
def bearbeiten(request, pk):
    m = get_object_or_404(Mitarbeiter, pk=pk)
    formular = MitarbeiterFormular(request.POST or None, instance=m)
    if request.method == "POST" and formular.is_valid():
        if formular.has_changed():
            details = aenderungen(formular)
            m = formular.save()
            protokolliere("mitarbeiter_geaendert", m, details=details, benutzer=request.user)
            messages.success(request, "Änderungen gespeichert.")
        else:
            messages.success(request, "Es wurde nichts geändert.")
        return redirect(m)
    return render(request, "mitarbeiter/formular.html", {"formular": formular, "titel": f"{m.name} bearbeiten", "m": m})
