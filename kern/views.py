from django.core.paginator import Paginator
from django.shortcuts import render

from konten.models import VERWALTUNGS_ROLLEN
from konten.rechte import rolle_erforderlich

from .models import Protokolleintrag
from .module import module_fuer


def kennzahlen(benutzer) -> dict:
    """Zahlen oben auf der Startseite. Geldbeträge nur für Chef, Admin, Buchhaltung."""
    from decimal import Decimal

    from konten.models import Rolle
    from projekte.models import ABGESCHLOSSEN, Projekt
    projekte = Projekt.objects.all()
    for s in ABGESCHLOSSEN:
        projekte = projekte.exclude(status__iexact=s)
    zahlen = {"offene_projekte": projekte.count()}
    if benutzer.hat_rolle(Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG):
        from rechnungen.models import Rechnung
        offen = ueberfaellig = Decimal("0")
        anzahl_ueberfaellig = 0
        for r in Rechnung.objects.filter(festgeschrieben_am__isnull=False).prefetch_related("zahlungen"):
            betrag = r.offen
            if betrag > 0:
                offen += betrag
                if r.ist_ueberfaellig:
                    ueberfaellig += betrag
                    anzahl_ueberfaellig += 1
        zahlen.update(geld=True, offen=offen, ueberfaellig=ueberfaellig, anzahl_ueberfaellig=anzahl_ueberfaellig)
    return zahlen


def startseite(request):
    from .module import BEREICHE
    module = module_fuer(request.user)
    zahlen = kennzahlen(request.user)
    for m in module:
        if m["titel"] == "Rechnungen" and zahlen.get("anzahl_ueberfaellig"):
            m["hinweis"] = f"{zahlen['anzahl_ueberfaellig']} überfällig"
    fertig = [m for m in module if m["url"]]
    gruppen = [(b, [m for m in fertig if m["bereich"] == b]) for b in BEREICHE]
    return render(request, "kern/startseite.html", {
        "gruppen": [(b, ms) for b, ms in gruppen if ms],
        "fertig": fertig,
        "geplant": [m for m in module if not m["url"]],
        "zahlen": zahlen,
    })


@rolle_erforderlich(*VERWALTUNGS_ROLLEN)
def protokoll(request):
    seite = Paginator(Protokolleintrag.objects.all(), 50).get_page(request.GET.get("seite"))
    return render(request, "kern/protokoll.html", {"seite": seite})
