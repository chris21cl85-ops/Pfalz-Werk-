import datetime as dt

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from kern.models import protokolliere
from konten.rechte import rolle_erforderlich

from . import finanzen
from .ansichten import BUERO
from .models import Firmendaten

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]


@rolle_erforderlich(*BUERO)
def uebersicht(request):
    return render(request, "finanzen/uebersicht.html", finanzen.uebersicht())


def _monat(request):
    jahr, monat = finanzen.vormonat()
    wert = request.GET.get("monat", "")
    try:
        jahr, monat = (int(x) for x in wert.split("-"))
        dt.date(jahr, monat, 1)
    except (ValueError, TypeError):
        pass
    return jahr, monat


@rolle_erforderlich(*BUERO)
def datev(request):
    jahr, monat = _monat(request)
    fd = Firmendaten.laden()
    if request.GET.get("laden"):
        try:
            inhalt, info = finanzen.datev_zip(jahr, monat)
        except ValueError as fehler:
            messages.error(request, str(fehler))
            return redirect(f"{request.path}?monat={jahr}-{monat:02d}")
        protokolliere("datev_export", f"{jahr}-{monat:02d}", benutzer=request.user,
                      details=f"{info['buchungen']} Buchungen, {info['belege']} Belege")
        antwort = HttpResponse(inhalt, content_type="application/zip")
        antwort["Content-Disposition"] = f'attachment; filename="DATEV_{jahr}-{monat:02d}.zip"'
        return antwort
    liste, warnungen = finanzen.buchungen(jahr, monat)
    heute = timezone.localdate()
    auswahl = []
    j, m = heute.year, heute.month
    for _ in range(24):
        auswahl.append((f"{j}-{m:02d}", f"{MONATE[m - 1]} {j}"))
        j, m = (j, m - 1) if m > 1 else (j - 1, 12)
    return render(request, "finanzen/datev.html", {
        "monat_wert": f"{jahr}-{monat:02d}", "monat_text": f"{MONATE[monat - 1]} {jahr}", "auswahl": auswahl,
        "buchungen": liste, "warnungen": warnungen, "fd": fd,
        "fehlt": not fd.datev_berater or not fd.datev_mandant,
    })
