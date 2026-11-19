from datetime import date, time, timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from kern.module import ALLE, WERKSTATT_LEITUNG
from konten.rechte import rolle_erforderlich
from mitarbeiter.models import Mitarbeiter
from produktion import dienst as produktion
from projekte.models import Projekt

from . import dienst
from .formulare import AbwesenheitFormular, MontageFormular, TeamFormular, TerminFormular
from .models import Abwesenheit, Montage, Team, Termin

ANSICHTEN = [("team", "Teams"), ("mitarbeiter", "Mitarbeiter"), ("projekt", "Projekte")]


def _leitung(benutzer):
    return benutzer.hat_rolle(*WERKSTATT_LEITUNG)


@rolle_erforderlich(*ALLE)
def kalender(request):
    try:
        tag = date.fromisoformat(request.GET.get("woche", ""))
    except ValueError:
        tag = timezone.localdate()
    mo = dienst.montag(tag)
    ansicht = request.GET.get("ansicht", "team")
    if ansicht not in dict(ANSICHTEN):
        ansicht = "team"
    leitung = _leitung(request.user)
    form = TerminFormular(initial={"datum": mo if mo > timezone.localdate() else timezone.localdate()})
    if request.method == "POST" and leitung:
        if request.POST.get("aktion") == "absagen":
            t = get_object_or_404(Termin, pk=request.POST.get("termin"))
            dienst.termin_absagen(t, request.user)
            messages.success(request, f"Termin {t.terminid} abgesagt.")
            return redirect(request.get_full_path())
        form = TerminFormular(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                neu = dienst.termin_anlegen(datum=d["datum"], aufgabe=d["aufgabe"], mitarbeiter=d["mitarbeiter"],
                                            team=d["team"] if not d["mitarbeiter"] else None, beginn=d["beginn"],
                                            ende=d["ende"], projekt=d["projekt"], ort=d["ort"], art=d["art"],
                                            benutzer=request.user)
            except dienst.PlanungsFehler as fehler:
                messages.error(request, str(fehler))
            else:
                messages.success(request, f"{len(neu)} Termin(e) am {d['datum']:%d.%m.%Y} eingetragen.")
                from .kapazitaet import warnung_fuer
                for t in neu:
                    w = warnung_fuer(t.mitarbeiter, t.datum)
                    if w:
                        messages.warning(request, "⚠ " + w)
                return redirect(f"{request.path}?woche={dienst.montag(d['datum']).isoformat()}&ansicht={ansicht}")
    k = dienst.kalender(mo, ansicht)
    termine = (Termin.objects.filter(datum__range=(mo, k["fr"]), abgesagt=False, aus_montage=False)
               .select_related("mitarbeiter", "projekt").order_by("datum", "beginn"))
    return render(request, "planung/kalender.html", {
        "k": k, "ansicht": ansicht, "ansichten": ANSICHTEN, "leitung": leitung, "form": form, "termine": termine,
        "vor": (mo - timedelta(days=7)).isoformat(), "nach": (mo + timedelta(days=7)).isoformat(),
        "heute": dienst.montag(timezone.localdate()).isoformat(), "heute_tag": timezone.localdate()})


@rolle_erforderlich(*WERKSTATT_LEITUNG)
def kapazitaet(request):
    """Wie Einsatzplanung / Personal-Leitstand: Tag je Mitarbeiter + Wochenübersicht der Rest-Stunden."""
    from . import kapazitaet as k
    try:
        tag = date.fromisoformat(request.GET.get("datum", ""))
    except ValueError:
        tag = timezone.localdate()
    mo = dienst.montag(tag)
    return render(request, "planung/kapazitaet.html", {
        "t": k.tag_alle(tag), "tag": tag, "woche": k.woche(mo), "mo": mo,
        "wochentage": [mo + timedelta(days=i) for i in range(5)],
        "vor": (tag - timedelta(days=1)).isoformat(), "nach": (tag + timedelta(days=1)).isoformat()})


@rolle_erforderlich(*ALLE)
def teams(request):
    leitung = _leitung(request.user)
    form = TeamFormular()
    if request.method == "POST" and leitung:
        form = TeamFormular(request.POST)
        if form.is_valid():
            try:
                t = dienst.team_anlegen(name=form.cleaned_data["name"], art=form.cleaned_data["art"], benutzer=request.user)
            except dienst.PlanungsFehler as fehler:
                form.add_error("name", str(fehler))
            else:
                messages.success(request, f"Team „{t.name}“ angelegt – jetzt Mitglieder antippen.")
                return redirect("planung:team", t.pk)
    mo = dienst.montag(timezone.localdate())
    zeilen = []
    for t in Team.objects.filter(aktiv=True):
        leute = t.mitglieder()
        weg = sum(1 for m in leute if any(dienst.abwesend(m, mo + timedelta(days=i)) for i in range(5)))
        zeilen.append({"t": t, "leute": leute, "weg": weg})
    return render(request, "planung/teams.html", {"zeilen": zeilen, "form": form, "leitung": leitung})


@rolle_erforderlich(*ALLE)
def team(request, pk):
    t = get_object_or_404(Team, pk=pk)
    leitung = _leitung(request.user)
    if request.method == "POST" and leitung:
        if request.POST.get("aktion") == "mitglied":
            m = get_object_or_404(Mitarbeiter, pk=request.POST.get("mitarbeiter"))
            dabei = dienst.mitglied_umschalten(t, m, request.user)
            messages.success(request, f"{m.name} {'ist jetzt im Team' if dabei else 'ist raus'}.")
        elif request.POST.get("aktion") == "art" and request.POST.get("art"):
            t.art = request.POST["art"]
            t.save(update_fields=["art"])
            messages.success(request, "Teamart gespeichert.")
        return redirect("planung:team", t.pk)
    mo = dienst.montag(timezone.localdate())
    dabei = {z.mitarbeiter_id: z for z in t.zuordnungen.filter(aktiv=True)}
    leute = []
    for m in Mitarbeiter.objects.filter(aktiv=True).order_by("name"):
        weg = next((f"{a} {['Mo', 'Di', 'Mi', 'Do', 'Fr'][i]}" for i in range(5)
                    if (a := dienst.abwesend(m, mo + timedelta(days=i)))), "")
        leute.append({"m": m, "dabei": m.pk in dabei, "leitung": m.pk in dabei and dabei[m.pk].leitung, "weg": weg})
    from .models import TEAMARTEN
    return render(request, "planung/team.html", {"t": t, "leute": leute, "leitung": leitung, "arten": TEAMARTEN,
                                                 "montagen": t.montagen.filter(datum__gte=timezone.localdate())
                                                 .select_related("projekt")})


@rolle_erforderlich(*ALLE)
def abwesenheiten(request):
    leitung = _leitung(request.user)
    eigener = produktion.mitarbeiter_von(request.user)
    form = AbwesenheitFormular(leitung=leitung, eigener=eigener)
    if request.method == "POST":
        if request.POST.get("aktion") == "status" and leitung:
            a = get_object_or_404(Abwesenheit, pk=request.POST.get("abwesenheit"))
            if request.POST.get("status") in Abwesenheit.Status.values:
                dienst.abwesenheit_status(a, request.POST["status"], request.user)
                messages.success(request, f"{a.zid}: {a.status}.")
            return redirect("planung:abwesenheiten")
        form = AbwesenheitFormular(request.POST, leitung=leitung, eigener=eigener)
        if (leitung or eigener) and form.is_valid():
            d = form.cleaned_data
            a = dienst.abwesenheit_erfassen(mitarbeiter=d["mitarbeiter"], von=d["von"], bis=d["bis"], art=d["art"],
                                            status=d.get("status") or Abwesenheit.Status.BEANTRAGT, hinweis=d["hinweis"],
                                            benutzer=request.user, stunden=d.get("stunden"))
            messages.success(request, f"{a.zid} eingetragen ({a.status}).")
            return redirect("planung:abwesenheiten")
    liste = Abwesenheit.objects.select_related("mitarbeiter")
    if request.GET.get("alle") != "1":
        liste = liste.filter(bis__gte=timezone.localdate() - timedelta(days=30))
    if not leitung:
        liste = liste.filter(mitarbeiter=eigener) if eigener else liste.none()
    return render(request, "planung/abwesenheiten.html", {"liste": liste, "form": form, "leitung": leitung,
                                                          "eigener": eigener, "alle": request.GET.get("alle") == "1"})


@rolle_erforderlich(*ALLE)
def montageplan(request):
    alle = request.GET.get("alle") == "1"
    montagen = Montage.objects.select_related("projekt", "projekt__kunde", "team")
    if not alle:
        montagen = montagen.filter(datum__gte=timezone.localdate() - timedelta(days=7))
    bereit = [p for p in Projekt.objects.filter(montage__isnull=True).prefetch_related("arbeitsgaenge", "qm_pruefungen")
              if p.arbeitsgaenge.exists() and produktion.phase(p) == 3]
    return render(request, "planung/montageplan.html", {"montagen": montagen, "alle": alle, "bereit": bereit,
                                                        "leitung": _leitung(request.user)})


@rolle_erforderlich(*WERKSTATT_LEITUNG)
def montage(request, pk):
    """Montage eines Projekts planen / Ergebnis eintragen (wie Schritt „Montage“ im Produktions-Assistenten)."""
    p = get_object_or_404(Projekt.objects.select_related("kunde"), pk=pk)
    m = getattr(p, "montage", None) if hasattr(p, "montage") else None
    ph = produktion.phase(p)
    warnungen = []
    k = p.kunde
    vorschlag = {"datum": produktion.werktag(timezone.localdate(), 1), "beginn": time(7), "ende": time(16),
                 "adresse": ", ".join(x for x in (k.strasse, f"{k.plz} {k.ort}".strip()) if x),
                 "aufgaben": f"Montage {p.name}"}
    form = MontageFormular(instance=m, initial=None if m else vorschlag)
    if request.method == "POST":
        aktion = request.POST.get("aktion")
        try:
            if aktion in ("Bestanden", "Nacharbeit erforderlich"):
                dienst.montage_ergebnis(p, aktion, request.user)
                if aktion == "Bestanden":
                    messages.success(request, "Montage bestanden – das Projekt ist fertig. Weiter zur Schlussrechnung.")
                else:
                    messages.warning(request, "Nacharbeit erforderlich – Montageplan bleibt offen. Neu planen, wenn klar ist wann.")
                return redirect("planung:montage", p.pk)
            form = MontageFormular(request.POST, instance=m)
            if form.is_valid():
                d = form.cleaned_data
                warnungen = dienst.montage_pruefen(p, datum=d["datum"], beginn=d["beginn"], ende=d["ende"],
                                                   team=d["team"], fahrzeug=d["fahrzeug"])
                if not warnungen or request.POST.get("trotzdem") == "1":
                    neu = dienst.montage_speichern(p, benutzer=request.user, **d)
                    messages.success(request, f"Montage am {neu.datum:%d.%m.%Y} eingetragen – steht im Kalender für "
                                              + ", ".join(x.name for x in neu.team.mitglieder()) + ".")
                    return redirect("planung:montage", p.pk)
        except dienst.PlanungsFehler as fehler:
            messages.error(request, str(fehler))
    return render(request, "planung/montage.html", {
        "p": p, "m": m, "form": form, "warnungen": warnungen, "phase": ph,
        "schritte": list(enumerate(produktion.SCHRITTE)), "neu_planen": request.GET.get("neu") == "1" or m is None
        or bool(warnungen) or form.errors, "termine": p.termine.filter(aus_montage=True).select_related("mitarbeiter")})
