from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from konten.models import VERWALTUNGS_ROLLEN
from konten.rechte import rolle_erforderlich

from .dienst import SicherungFehler, sicherung_anlegen, sicherungen


@rolle_erforderlich(*VERWALTUNGS_ROLLEN)
def uebersicht(request):
    return render(request, "sicherung/uebersicht.html", {"sicherungen": sicherungen()})


@require_POST
@rolle_erforderlich(*VERWALTUNGS_ROLLEN)
def anlegen(request):
    try:
        pfad = sicherung_anlegen(benutzer=request.user)
        messages.success(request, f"Sicherung „{pfad.name}“ wurde angelegt.")
    except (SicherungFehler, OSError) as fehler:
        messages.error(request, f"Sicherung fehlgeschlagen: {fehler}")
    return redirect("sicherung:uebersicht")
