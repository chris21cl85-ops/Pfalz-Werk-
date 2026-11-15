from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from kern.models import protokolliere
from kern.module import ALLE, WERKSTATT_LEITUNG
from konten.rechte import rolle_erforderlich
from projekte.models import ABGESCHLOSSEN, Projekt

from . import dienst
from .formulare import (ArbeitsgangFormular, EinzelFormular, PlanenFormular, QMFormular, RouteFormular,
                        RueckmeldeFormular)
from .models import Arbeitsgang, Route, Vorlage


def _leitung(benutzer):
    return benutzer.hat_rolle(*WERKSTATT_LEITUNG)


@rolle_erforderlich(*ALLE)
def uebersicht(request):
    suche = request.GET.get("suche", "").strip().lower()
    nur = request.GET.get("nur", "offen")
    projekte = (Projekt.objects.select_related("kunde").prefetch_related("arbeitsgaenge__mitarbeiter",
                "arbeitsgaenge__qm_pruefungen", "arbeitsgaenge__vorgaenger", "qm_pruefungen").order_by("-projektnr"))
    zeilen, zaehler = [], [0] * 5
    for p in projekte:
        offen = p.status.strip().lower() not in ABGESCHLOSSEN
        if nur == "offen" and not offen and not p.arbeitsgaenge.exists():
            continue
        d = dienst.stand(p)
        if nur == "mit" and d["n"] == 0:
            continue
        zaehler[d["phase"]] += 1
        if suche and suche not in f"{p.projektnr} {p.name} {p.kunde.name}".lower():
            continue
        zeilen.append({"p": p, "d": d, "schritt": dienst.SCHRITTE[d["phase"]]})
    return render(request, "produktion/uebersicht.html", {
        "zeilen": zeilen, "suche": suche, "nur": nur, "leitung": _leitung(request.user),
        "zaehler": list(zip(dienst.SCHRITTE, zaehler)), "meine": _meine_anzahl(request.user)})


def _meine_anzahl(benutzer):
    m = dienst.mitarbeiter_von(benutzer)
    return dienst.offene_fuer(m).count() if m else None


@rolle_erforderlich(*ALLE)
def projekt(request, pk):
    p = get_object_or_404(Projekt.objects.select_related("kunde"), pk=pk)
    leitung = _leitung(request.user)
    formulare = {"planen": PlanenFormular(initial={"start": dienst.werktag(timezone.localdate(), 1)}, prefix="pl"),
                 "route": RouteFormular(prefix="ro"), "einzeln": EinzelFormular(prefix="ei"), "qm": QMFormular(prefix="qm")}
    if request.method == "POST":
        aktion = request.POST.get("aktion")
        if aktion in ("planen", "route", "einzeln", "qm", "entfernen") and not leitung:
            messages.error(request, "Das darf nur Chef, Admin oder Meister.")
            return redirect("produktion:projekt", p.pk)
        try:
            if aktion == "planen":
                f = formulare["planen"] = PlanenFormular(request.POST, prefix="pl")
                if f.is_valid():
                    n = dienst.einplanen(p, f.cleaned_data["start"], f.cleaned_data["mitarbeiter"], request.user)
                    messages.success(request, f"{n} Arbeitsgänge ab {f.cleaned_data['start']:%d.%m.%Y} eingeplant.")
                    from planung.dienst import abwesend
                    ma, start = f.cleaned_data["mitarbeiter"], dienst.werktag(f.cleaned_data["start"], 0)
                    if ma and (grund := abwesend(ma, start)):
                        messages.warning(request, f"⚠ {ma.name} ist am {start:%d.%m.} abwesend ({grund}).")
                    return redirect("produktion:projekt", p.pk)
            elif aktion == "route":
                f = formulare["route"] = RouteFormular(request.POST, prefix="ro")
                if f.is_valid():
                    n = dienst.aus_route(p, f.cleaned_data["route"], f.cleaned_data["bauteil"], request.user)
                    messages.success(request, f"{n} Arbeitsgänge aus „{f.cleaned_data['route']}“ angelegt.")
                    return redirect("produktion:projekt", p.pk)
            elif aktion == "einzeln":
                f = formulare["einzeln"] = EinzelFormular(request.POST, prefix="ei")
                if f.is_valid():
                    ag = dienst.einzeln(p, f.cleaned_data["vorlage"], bauteil=f.cleaned_data["bauteil"],
                                        plan_std=f.cleaned_data["plan_std"], mitarbeiter=f.cleaned_data["mitarbeiter"],
                                        benutzer=request.user)
                    messages.success(request, f"{ag.agid} „{ag.name}“ angehängt.")
                    return redirect("produktion:projekt", p.pk)
            elif aktion == "qm":
                f = formulare["qm"] = QMFormular(request.POST, prefix="qm")
                if f.is_valid():
                    q = dienst.endkontrolle(p, bestanden=f.cleaned_data["ergebnis"] == "Bestanden",
                                            abweichung=f.cleaned_data["abweichung"], benutzer=request.user)
                    if q.ergebnis == "Bestanden":
                        messages.success(request, f"{q.qmid}: Endkontrolle bestanden – QM freigegeben.")
                    else:
                        messages.warning(request, f"{q.qmid}: nicht bestanden – Nacharbeit {q.nacharbeit_ag.agid} angelegt.")
                    return redirect("produktion:projekt", p.pk)
            elif aktion in ("starten", "rueckmelden", "entfernen"):
                ag = get_object_or_404(Arbeitsgang, pk=request.POST.get("ag"), projekt=p)
                _ag_aktion(request, ag, aktion)
                return redirect(f"{request.path}#ag-{ag.pk}" if aktion != "entfernen" else request.path)
        except dienst.ProduktionsFehler as fehler:
            messages.error(request, str(fehler))
            return redirect("produktion:projekt", p.pk)
    ags = list(p.arbeitsgaenge.select_related("mitarbeiter", "vorgaenger", "moebel").prefetch_related("qm_pruefungen")
               .order_by("pk"))
    d = dienst.stand(p)
    return render(request, "produktion/projekt.html", {
        "p": p, "d": d, "ags": ags, "leitung": leitung, "f": formulare, "rueck": RueckmeldeFormular(),
        "schritte": [(i, s) for i, s in enumerate(dienst.SCHRITTE)], "pruefungen": p.qm_pruefungen.select_related("nacharbeit_ag"),
        "moebel_ohne_ag": [m for m in p.moebel.all() if m.status == "In Stückliste"],
        "montage": getattr(p, "montage", None) if hasattr(p, "montage") else None})


def _ag_aktion(request, ag, aktion):
    if aktion == "starten":
        dienst.starten(ag, request.user)
        messages.success(request, f"„{ag.name}“ gestartet.")
    elif aktion == "rueckmelden":
        f = RueckmeldeFormular(request.POST)
        if not f.is_valid():
            raise dienst.ProduktionsFehler("Stunden als Zahl eintragen, z. B. 2,5.")
        fertig = request.POST.get("fertig") == "1"
        dienst.rueckmelden(ag, stunden=f.cleaned_data["stunden"] or 0, fertig=fertig, benutzer=request.user)
        messages.success(request, f"„{ag.name}“ " + ("fertig gemeldet." if fertig else "Zwischenstand gespeichert."))
    elif aktion == "entfernen":
        dienst.entfernen(ag, request.user)
        messages.success(request, f"{ag.agid} entfernt.")


@rolle_erforderlich(*WERKSTATT_LEITUNG)
def bearbeiten(request, pk):
    ag = get_object_or_404(Arbeitsgang.objects.select_related("projekt"), pk=pk)
    form = ArbeitsgangFormular(request.POST or None, instance=ag)
    if request.method == "POST" and form.is_valid():
        if form.has_changed():
            form.save()
            protokolliere("arbeitsgang_geaendert", ag.agid, benutzer=request.user,
                          details="geändert: " + ", ".join(form.changed_data))
            messages.success(request, f"{ag.agid} gespeichert.")
        return redirect("produktion:projekt", ag.projekt.pk)
    return render(request, "produktion/bearbeiten.html", {"form": form, "ag": ag})


@rolle_erforderlich(*ALLE)
def meine(request):
    m = dienst.mitarbeiter_von(request.user)
    if request.method == "POST" and m:
        ag = get_object_or_404(Arbeitsgang, pk=request.POST.get("ag"))
        try:
            _ag_aktion(request, ag, request.POST.get("aktion") if request.POST.get("aktion") in ("starten", "rueckmelden") else "")
        except dienst.ProduktionsFehler as fehler:
            messages.error(request, str(fehler))
        return redirect("produktion:meine")
    return render(request, "produktion/meine.html", {"m": m, "ags": dienst.offene_fuer(m) if m else [],
                                                     "rueck": RueckmeldeFormular(), "heute": timezone.localdate()})


@rolle_erforderlich(*ALLE)
def bibliothek(request):
    return render(request, "produktion/bibliothek.html", {
        "vorlagen": Vorlage.objects.all(), "routen": Route.objects.prefetch_related("schritte")})
