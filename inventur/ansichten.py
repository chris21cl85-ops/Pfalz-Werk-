from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from kern.module import ALLE
from konten.models import Rolle
from konten.rechte import rolle_erforderlich

from . import dienst
from .formulare import InventurFormular
from .models import URSACHEN, Inventur, Position

LEITUNG = (Rolle.CHEF, Rolle.ADMIN, Rolle.MEISTER)          # Starten, Prüfen, Freigeben, Abschließen
ZAEHLEN = LEITUNG + (Rolle.MITARBEITER,)                    # wie Inventur-Rechte: Buchhaltung nur lesen
MODI = [("zaehlen", "Zählen"), ("nach", "Nachzählen"), ("frei", "Freigeben"), ("alle", "Alle Positionen")]


@rolle_erforderlich(*ALLE)
def liste(request):
    leitung = request.user.hat_rolle(*LEITUNG)
    form = InventurFormular(initial={"stichtag": timezone.localdate(), "toleranz_prozent": 2, "toleranz_wert": 50})
    if request.method == "POST" and leitung:
        form = InventurFormular(request.POST)
        if form.is_valid():
            inv = dienst.anlegen(benutzer=request.user, **form.cleaned_data)
            messages.success(request, f"{inv.invid} angelegt – Positionen prüfen und starten.")
            return redirect("inventur:detail", inv.pk)
    inventuren = [{"i": i, "d": dienst.pruefung(i)} for i in Inventur.objects.all()]
    return render(request, "inventur/liste.html", {"inventuren": inventuren, "form": form, "leitung": leitung})


@rolle_erforderlich(*ALLE)
def detail(request, pk):
    inv = get_object_or_404(Inventur, pk=pk)
    leitung = request.user.hat_rolle(*LEITUNG)
    darf_zaehlen = request.user.hat_rolle(*ZAEHLEN)
    modus = request.GET.get("modus") or ("zaehlen" if inv.status == "Aktiv" else "alle")
    if request.method == "POST":
        aktion = request.POST.get("aktion")
        try:
            if aktion == "starten" and leitung:
                n = dienst.starten(inv, request.user)
                messages.success(request, f"Inventur gestartet – Soll für {n} Positionen festgeschrieben.")
            elif aktion == "abschliessen" and leitung:
                n = dienst.abschliessen(inv, request.user)
                messages.success(request, f"Inventur abgeschlossen – {n} Korrekturbuchung(en) im Lager.")
                return redirect("inventur:detail", inv.pk)
            elif aktion in ("zaehlen", "nach", "frei", "ablehnen"):
                pos = get_object_or_404(Position, pk=request.POST.get("position"), inventur=inv)
                if aktion == "zaehlen" and darf_zaehlen:
                    dienst.zaehlen(pos, request.POST.get("menge", ""), request.user, request.POST.get("bemerkung", "").strip())
                    messages.success(request, f"{pos.material.materialnr}: {pos.ist:g} {pos.einheit} gezählt.")
                elif aktion == "nach" and darf_zaehlen:
                    dienst.nachzaehlen(pos, request.POST.get("menge", ""), request.user, request.POST.get("bemerkung", "").strip())
                    messages.success(request, f"{pos.material.materialnr} nachgezählt.")
                elif aktion in ("frei", "ablehnen") and leitung:
                    dienst.entscheiden(pos, freigeben=aktion == "frei", ursache=request.POST.get("ursache", ""),
                                       text=request.POST.get("text", ""), benutzer=request.user)
                    messages.success(request, f"{pos.material.materialnr} {pos.freigabe.lower()}.")
                else:
                    messages.error(request, "Das darfst du hier nicht.")
                naechste = _naechste(inv, modus, pos)
                return redirect(f"{request.path}?modus={modus}" + (f"#p{naechste.pk}" if naechste else ""))
            else:
                messages.error(request, "Das darfst du hier nicht.")
        except dienst.InventurFehler as fehler:
            messages.error(request, str(fehler))
        return redirect(f"{request.path}?modus={modus}")
    positionen = list(inv.positionen.select_related("material", "buchung", "inventur"))
    if modus == "zaehlen":
        zeigen = sorted(positionen, key=lambda p: (p.gezaehlt, p.lagerplatz, p.material.materialnr))
    elif modus == "nach":
        zeigen = [p for p in positionen if p.kritisch]
    elif modus == "frei":
        zeigen = [p for p in positionen if p.differenz and not p.nachzaehlung_offen]
    else:
        zeigen = positionen
    return render(request, "inventur/detail.html", {
        "inv": inv, "d": dienst.pruefung(inv), "modus": modus, "modi": MODI, "zeigen": zeigen, "leitung": leitung,
        "darf_zaehlen": darf_zaehlen, "ursachen": URSACHEN, "soll_zeigen": not inv.blind or modus != "zaehlen",
        "erste_offene": next((p.pk for p in zeigen if (modus == "zaehlen" and not p.gezaehlt)
                              or (modus == "nach" and p.nachzaehlung_offen) or (modus == "frei" and p.freigabe_offen)), None)})


def _naechste(inv, modus, nach):
    for p in inv.positionen.select_related("inventur").order_by("lagerplatz", "material__materialnr"):
        if (modus == "zaehlen" and not p.gezaehlt) or (modus == "nach" and p.nachzaehlung_offen) or \
                (modus == "frei" and p.freigabe_offen):
            return p
    return None


@rolle_erforderlich(*ALLE)
def bericht(request, pk):
    inv = get_object_or_404(Inventur, pk=pk)
    antwort = HttpResponse(dienst.bericht_pdf(inv), content_type="application/pdf")
    antwort["Content-Disposition"] = f'inline; filename="Inventurbericht_{inv.invid}.pdf"'
    return antwort
