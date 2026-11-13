from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from kern.blaettern import aenderungen
from kern.models import protokolliere
from konten.models import Rolle
from konten.rechte import rolle_erforderlich
from projekte.models import Projekt

from . import dienst
from .formulare import EINHEITEN, FirmendatenFormular, KopfFormular, NeueRechnungFormular, PositionenFormularsatz
from .models import Firmendaten, Rechnung
from .pdf import rechnung_pdf

# Wie Darf() im Makro: Chef, Admin, Buchhaltung
BUERO = (Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG)


@rolle_erforderlich(*BUERO)
def liste(request):
    suche = request.GET.get("suche", "").strip()
    status = request.GET.get("status", "aktuell")
    rechnungen = Rechnung.objects.select_related("kunde", "projekt")
    if status == "aktuell":
        rechnungen = rechnungen.exclude(status=Rechnung.Status.VERWORFEN)
    elif status != "alle":
        rechnungen = rechnungen.filter(status=status)
    if suche:
        rechnungen = rechnungen.filter(
            Q(nummer__icontains=suche) | Q(kunde__name__icontains=suche) | Q(kunde__kundennr__icontains=suche)
            | Q(projekt__projektnr__icontains=suche) | Q(projekt__name__icontains=suche))
    fd = Firmendaten.laden()
    return render(request, "rechnungen/liste.html", {
        "seite": Paginator(rechnungen, 50).get_page(request.GET.get("seite")),
        "anzahl": rechnungen.count(), "suche": suche, "status": status,
        "stati": Rechnung.Status.choices, "firmendaten_fehlen": fd.fehlende_angaben(),
    })


@rolle_erforderlich(*BUERO)
def neu(request):
    fd = Firmendaten.laden()
    start = {"zahlungsziel": dienst.ziel_aus_firmendaten(fd)}
    projekt = Projekt.objects.filter(pk=request.GET.get("projekt") or 0).first()
    if projekt:
        start["projekt"] = projekt
        start["auftragswert"] = dienst.letzter_auftragswert(projekt)
    formular = NeueRechnungFormular(request.POST or None, initial=start)
    if request.method == "POST" and formular.is_valid():
        d = formular.cleaned_data
        try:
            rechnung = dienst.entwurf_anlegen(
                projekt=d["projekt"], art=d["art"], benutzer=request.user,
                leistungszeitraum=d["leistungszeitraum"], zahlungsziel=d["zahlungsziel"],
                auftragswert=d.get("auftragswert"), abschlag_prozent=d.get("abschlag_prozent"))
        except dienst.RechnungFehler as fehler:
            formular.add_error(None, str(fehler))
        else:
            messages.success(request, "Entwurf angelegt. Positionen prüfen, dann festschreiben.")
            return redirect("rechnungen:bearbeiten", rechnung.pk)
    return render(request, "rechnungen/neu.html", {
        "formular": formular, "firmendaten_fehlen": fd.fehlende_angaben()})


@rolle_erforderlich(*BUERO)
def detail(request, pk):
    rechnung = get_object_or_404(Rechnung.objects.select_related("kunde", "projekt"), pk=pk)
    return render(request, "rechnungen/detail.html", {
        "r": rechnung, "summen": rechnung.summen(), "positionen": rechnung.positionen.order_by("pos", "id"),
        "fehlt": dienst.pruefen(rechnung) if rechnung.ist_entwurf else [],
        "naechste_nummer": dienst.naechste_nummer_vorschau() if rechnung.ist_entwurf else "",
        "pruefsumme_ok": rechnung.pruefsumme_stimmt() if rechnung.ist_festgeschrieben else None,
    })


@rolle_erforderlich(*BUERO)
def bearbeiten(request, pk):
    rechnung = get_object_or_404(Rechnung, pk=pk)
    if not rechnung.ist_entwurf:
        messages.error(request, "Diese Rechnung ist festgeschrieben und kann nicht mehr geändert werden.")
        return redirect(rechnung)
    kopf = KopfFormular(request.POST or None, instance=rechnung)
    satz = PositionenFormularsatz(request.POST or None, instance=rechnung, prefix="pos")
    if request.method == "POST" and kopf.is_valid() and satz.is_valid():
        kopf.save()
        positionen = satz.save(commit=False)
        for p in satz.deleted_objects:
            p.delete()
        hoechste = max(rechnung.positionen.values_list("pos", flat=True), default=0)
        for p in positionen:
            if not p.pos:
                hoechste += 1
                p.pos = hoechste
            p.save()
        if kopf.has_changed() or satz.has_changed():
            protokolliere("rechnung_entwurf_geaendert", f"Entwurf {rechnung.pk}", benutzer=request.user,
                          details=aenderungen(kopf) or "Positionen geändert")
        messages.success(request, "Entwurf gespeichert.")
        if "weiter" in request.POST:
            return redirect("rechnungen:bearbeiten", rechnung.pk)
        return redirect(rechnung)
    return render(request, "rechnungen/bearbeiten.html", {
        "r": rechnung, "kopf": kopf, "satz": satz, "einheiten": EINHEITEN})


@rolle_erforderlich(*BUERO)
def festschreiben(request, pk):
    rechnung = get_object_or_404(Rechnung, pk=pk)
    if request.method != "POST":
        return redirect(rechnung)
    if not request.POST.get("bestaetigt"):
        messages.error(request, "Bitte den Haken setzen, dass die Rechnung geprüft ist.")
        return redirect(rechnung)
    try:
        rechnung = dienst.festschreiben(rechnung, request.user)
    except (dienst.RechnungFehler, dienst.RechnungGesperrt) as fehler:
        messages.error(request, str(fehler))
    else:
        messages.success(request, f"Rechnung {rechnung.nummer} ist festgeschrieben. Das PDF steht bereit.")
    return redirect(rechnung)


@rolle_erforderlich(*BUERO)
def verwerfen(request, pk):
    rechnung = get_object_or_404(Rechnung, pk=pk)
    if request.method == "POST":
        try:
            dienst.verwerfen(rechnung, request.user)
            messages.success(request, "Entwurf verworfen. Er bleibt unter „Verworfen“ sichtbar.")
        except dienst.RechnungFehler as fehler:
            messages.error(request, str(fehler))
    return redirect(rechnung)


@rolle_erforderlich(*BUERO)
def pdf(request, pk):
    rechnung = get_object_or_404(Rechnung, pk=pk)
    if rechnung.ist_festgeschrieben:
        inhalt, name = bytes(rechnung.pdf), f"{rechnung.nummer}.pdf"
        protokolliere("rechnung_pdf_abgerufen", rechnung.nummer, benutzer=request.user)
    else:
        inhalt, name = rechnung_pdf(rechnung, entwurf=True), f"Entwurf_{rechnung.pk}.pdf"
    antwort = HttpResponse(inhalt, content_type="application/pdf")
    art = "attachment" if request.GET.get("laden") else "inline"
    antwort["Content-Disposition"] = f'{art}; filename="{name}"'
    return antwort


@rolle_erforderlich(*BUERO)
def firmendaten(request):
    fd = Firmendaten.laden()
    formular = FirmendatenFormular(request.POST or None, instance=fd)
    if request.method == "POST" and formular.is_valid():
        if formular.has_changed():
            details = aenderungen(formular)
            formular.save()
            protokolliere("firmendaten_geaendert", "Firmendaten", details=details, benutzer=request.user)
            messages.success(request, "Firmendaten gespeichert.")
        else:
            messages.success(request, "Es wurde nichts geändert.")
        return redirect("rechnungen:firmendaten")
    return render(request, "rechnungen/firmendaten.html", {
        "formular": formular, "fehlt": fd.fehlende_angaben(), "naechste_nummer": dienst.naechste_nummer_vorschau()})
