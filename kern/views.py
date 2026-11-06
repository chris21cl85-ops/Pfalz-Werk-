from django.core.paginator import Paginator
from django.shortcuts import render

from konten.models import VERWALTUNGS_ROLLEN
from konten.rechte import rolle_erforderlich

from .models import Protokolleintrag
from .module import module_fuer


def startseite(request):
    module = module_fuer(request.user)
    return render(request, "kern/startseite.html", {
        "fertig": [m for m in module if m["url"]],
        "geplant": [m for m in module if not m["url"]],
    })


@rolle_erforderlich(*VERWALTUNGS_ROLLEN)
def protokoll(request):
    seite = Paginator(Protokolleintrag.objects.all(), 50).get_page(request.GET.get("seite"))
    return render(request, "kern/protokoll.html", {"seite": seite})
