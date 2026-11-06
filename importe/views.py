from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from kern.models import protokolliere
from konten.models import VERWALTUNGS_ROLLEN
from konten.rechte import rolle_erforderlich

from . import dienst
from .models import Importlauf


@rolle_erforderlich(*VERWALTUNGS_ROLLEN)
def uebersicht(request):
    if request.method == "POST":
        datei = request.FILES.get("datei")
        if not datei:
            messages.error(request, "Bitte zuerst eine Datei auswählen.")
            return redirect("importe:uebersicht")
        try:
            pfad = dienst.datei_speichern(datei)
        except dienst.ImportFehler as fehler:
            messages.error(request, str(fehler))
            return redirect("importe:uebersicht")
        lauf = Importlauf.objects.create(benutzer=request.user, dateiname=datei.name, gespeichert_als=str(pfad))
        protokolliere("import_hochgeladen", datei.name, benutzer=request.user)
        dienst.probelauf(lauf)
        return redirect("importe:lauf", pk=lauf.pk)
    return render(request, "importe/uebersicht.html", {
        "laeufe": Importlauf.objects.all()[:20],
        "importer": sorted(dienst.IMPORTER.values(), key=lambda k: k.blatt),
    })


@rolle_erforderlich(*VERWALTUNGS_ROLLEN)
def lauf(request, pk):
    return render(request, "importe/lauf.html", {"lauf": get_object_or_404(Importlauf, pk=pk)})


@require_POST
@rolle_erforderlich(*VERWALTUNGS_ROLLEN)
def uebernehmen(request, pk):
    lauf = get_object_or_404(Importlauf, pk=pk)
    try:
        dienst.uebernehmen(lauf, request.user)
        messages.success(request, "Die Daten wurden übernommen. Vorher wurde automatisch gesichert.")
    except dienst.ImportFehler as fehler:
        messages.error(request, str(fehler))
    return redirect("importe:lauf", pk=pk)
