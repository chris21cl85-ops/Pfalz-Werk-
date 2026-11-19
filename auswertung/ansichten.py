from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from konten.models import Rolle
from konten.rechte import rolle_erforderlich
from projekte.models import Projekt
from zeiten.dienst import MONATE

from . import dienst

RECHTE = (Rolle.CHEF, Rolle.ADMIN)


@rolle_erforderlich(*RECHTE)
def uebersicht(request):
    heute = timezone.localdate()
    try:
        jahr = int(request.GET.get("jahr", heute.year))
    except ValueError:
        jahr = heute.year
    try:
        j, m = (int(x) for x in request.GET.get("monat", "").split("-"))
    except ValueError:
        j, m = heute.year, heute.month
    alle = request.GET.get("alle") == "1"
    return render(request, "auswertung/uebersicht.html", {
        "j": dienst.jahr(jahr), "nk": dienst.nachkalkulation(nur_offene=not alle), "alle": alle,
        "stunden": dienst.stunden(j, m), "stunden_name": f"{MONATE[m - 1]} {j}", "stunden_monat": f"{j}-{m:02d}",
        "w": dienst.werkstatt(), "mat": dienst.material(), "jahre": list(range(heute.year, heute.year - 5, -1))})


@rolle_erforderlich(*RECHTE)
def projekt(request, pk):
    p = get_object_or_404(Projekt.objects.select_related("kunde"), pk=pk)
    return render(request, "auswertung/projekt.html", {"v": dienst.projekt_vergleich(p), "p": p})
