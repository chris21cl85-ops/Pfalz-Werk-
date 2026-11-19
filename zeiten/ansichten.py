from datetime import date, timedelta

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from kern.models import protokolliere
from kern.module import ALLE
from konten.models import Rolle
from konten.rechte import rolle_erforderlich
from mitarbeiter.models import Mitarbeiter
from produktion.dienst import mitarbeiter_von

from . import dienst
from .formulare import BuchungFormular, VertragFormular
from .models import Arbeitsvertrag, Monatsabschluss, Zeitbuchung

LEITUNG = (Rolle.CHEF, Rolle.ADMIN, Rolle.MEISTER)
BUERO = LEITUNG + (Rolle.BUCHHALTUNG,)
VERWALTUNG = (Rolle.CHEF, Rolle.ADMIN)
VERTRAG_LESEN = VERWALTUNG + (Rolle.BUCHHALTUNG,)


def _monat_aus(request):
    try:
        j, m = (int(x) for x in request.GET.get("monat", "").split("-"))
        return date(j, m, 1)
    except (ValueError, TypeError):
        return timezone.localdate().replace(day=1)


def _nachbarn(erster: date):
    vor = (erster - timedelta(days=1)).replace(day=1)
    nach = (erster + timedelta(days=32)).replace(day=1)
    return f"{vor:%Y-%m}", f"{nach:%Y-%m}"


def _buchen_aus(request, form, ma):
    d = form.cleaned_data
    return dienst.buchen(mitarbeiter=ma, datum=d["datum"], stunden=d["stunden"], beginn=d["beginn"], ende=d["ende"],
                         pause_min=d["pause_min"] or 0, projekt=d["projekt"], arbeitsgang=d["arbeitsgang"],
                         taetigkeit=d["taetigkeit"], notiz=d["notiz"], benutzer=request.user)


def _storno(request, ma):
    b = get_object_or_404(Zeitbuchung, pk=request.POST.get("buchung"), mitarbeiter=ma)
    dienst.stornieren(b, request.POST.get("grund", ""), request.user)
    messages.success(request, f"Buchung vom {b.datum:%d.%m.%Y} ({b.stunden:g} h) storniert.")


@rolle_erforderlich(*ALLE)
def start(request):
    if request.user.hat_rolle(*BUERO):
        return redirect("zeiten:uebersicht")
    return redirect("zeiten:meine")


@rolle_erforderlich(*ALLE)
def meine(request):
    ma = mitarbeiter_von(request.user)
    if ma is None:
        return render(request, "zeiten/meine.html", {"ma": None})
    try:
        tag = date.fromisoformat(request.GET.get("woche", ""))
    except ValueError:
        tag = timezone.localdate()
    mo = tag - timedelta(days=tag.weekday())
    form = BuchungFormular(mitarbeiter=ma, initial={"datum": timezone.localdate(), "pause_min": 0})
    if request.method == "POST":
        try:
            if request.POST.get("aktion") == "storno":
                _storno(request, ma)
                return redirect(request.get_full_path())
            form = BuchungFormular(request.POST, mitarbeiter=ma)
            if form.is_valid():
                b = _buchen_aus(request, form, ma)
                messages.success(request, f"{b.stunden:g} h am {b.datum:%d.%m.%Y} gebucht.")
                return redirect(f"{request.path}?woche={b.datum.isoformat()}")
        except dienst.ZeitFehler as fehler:
            messages.error(request, str(fehler))
    so = mo + timedelta(days=6)
    buchungen = ma.zeitbuchungen.filter(datum__range=(mo, so)).select_related("projekt", "arbeitsgang").order_by("datum", "beginn")
    tage = []
    for i in range(7):
        d = mo + timedelta(days=i)
        eigene = [b for b in buchungen if b.datum == d]
        tage.append({"datum": d, "soll": dienst.soll_tag(ma, d), "buchungen": eigene,
                     "ist": sum((b.stunden for b in eigene if not b.storniert_am), dienst.NULL),
                     "feiertag": dienst.feiertag(d), "abwesend": dienst._abwesenheiten(ma, d, d).get(d, ""),
                     "heute": d == timezone.localdate()})
    return render(request, "zeiten/meine.html", {
        "ma": ma, "form": form, "tage": tage, "mo": mo, "so": so, "kw": mo.isocalendar()[1],
        "soll": sum((t["soll"] for t in tage), dienst.NULL), "ist": sum((t["ist"] for t in tage), dienst.NULL),
        "vor": (mo - timedelta(days=7)).isoformat(), "nach": (mo + timedelta(days=7)).isoformat(),
        "konto": dienst.zeitkonto(ma), "urlaub": dienst.urlaub(ma, timezone.localdate().year)})


@rolle_erforderlich(*BUERO)
def uebersicht(request):
    erster = _monat_aus(request)
    zeilen = []
    for ma in Mitarbeiter.objects.filter(aktiv=True).order_by("name"):
        m = dienst.monat(ma, erster.year, erster.month)
        zeilen.append({"ma": ma, "s": m["summe"], "abgeschlossen": m["abgeschlossen"],
                       "konto": dienst.zeitkonto(ma, erster), "urlaub": dienst.urlaub(ma, erster.year),
                       "vertrag": dienst.vertrag(ma)})
    vor, nach = _nachbarn(erster)
    return render(request, "zeiten/uebersicht.html", {"zeilen": zeilen, "erster": erster, "vor": vor, "nach": nach,
                                                      "name": f"{dienst.MONATE[erster.month - 1]} {erster.year}"})


@rolle_erforderlich(*BUERO)
def mitarbeiter(request, pk):
    ma = get_object_or_404(Mitarbeiter, pk=pk)
    erster = _monat_aus(request)
    leitung = request.user.hat_rolle(*LEITUNG)
    darf_abschluss = request.user.hat_rolle(*VERWALTUNG)
    form = BuchungFormular(mitarbeiter=ma, initial={"datum": min(timezone.localdate(), dienst.monatsgrenzen(
        erster.year, erster.month)[1]), "pause_min": 0})
    if request.method == "POST":
        aktion = request.POST.get("aktion")
        try:
            if aktion == "storno" and leitung:
                _storno(request, ma)
            elif aktion == "abschliessen" and darf_abschluss:
                a = dienst.abschliessen(ma, erster.year, erster.month, request.user)
                messages.success(request, f"Monat abgeschlossen – Zeitkonto {a.zeitkonto:g} h.")
            elif aktion == "oeffnen" and request.user.hat_rolle(Rolle.CHEF):
                dienst.wieder_oeffnen(get_object_or_404(Monatsabschluss, mitarbeiter=ma, monat=erster), request.user)
                messages.warning(request, "Abschluss aufgehoben – Buchungen sind wieder änderbar (im Protokoll vermerkt).")
            elif aktion == "buchen" and leitung:
                form = BuchungFormular(request.POST, mitarbeiter=ma)
                if not form.is_valid():
                    raise dienst.ZeitFehler("Bitte die Eingaben prüfen.")
                b = _buchen_aus(request, form, ma)
                messages.success(request, f"{b.stunden:g} h am {b.datum:%d.%m.%Y} für {ma.name} gebucht.")
            else:
                messages.error(request, "Das darfst du hier nicht.")
            return redirect(f"{request.path}?monat={erster:%Y-%m}")
        except dienst.ZeitFehler as fehler:
            messages.error(request, str(fehler))
    m = dienst.monat(ma, erster.year, erster.month)
    buchungen = ma.zeitbuchungen.filter(datum__range=(m["von"], m["bis"])).select_related(
        "projekt", "arbeitsgang", "erfasst_von").order_by("datum", "beginn")
    vor, nach = _nachbarn(erster)
    return render(request, "zeiten/mitarbeiter.html", {
        "ma": ma, "m": m, "buchungen": buchungen, "form": form, "leitung": leitung, "darf_abschluss": darf_abschluss,
        "darf_oeffnen": request.user.hat_rolle(Rolle.CHEF), "erster": erster, "vor": vor, "nach": nach,
        "konto": dienst.zeitkonto(ma, erster), "urlaub": dienst.urlaub(ma, erster.year), "vertrag": dienst.vertrag(ma),
        "monat_vorbei": m["bis"] < timezone.localdate()})


@rolle_erforderlich(*BUERO)
def stundenzettel(request, pk):
    ma = get_object_or_404(Mitarbeiter, pk=pk)
    erster = _monat_aus(request)
    antwort = HttpResponse(dienst.stundenzettel_pdf(ma, erster.year, erster.month), content_type="application/pdf")
    antwort["Content-Disposition"] = f'inline; filename="Stundenzettel_{ma.kuerzel}_{erster:%Y-%m}.pdf"'
    return antwort


@rolle_erforderlich(*VERTRAG_LESEN)
def vertraege(request):
    heute = timezone.localdate()
    zeilen = []
    for ma in Mitarbeiter.objects.filter(aktiv=True).order_by("name"):
        v = dienst.vertrag(ma)
        warn = []
        if v is None:
            warn.append("kein Vertrag erfasst")
        else:
            if v.probezeit_bis and heute <= v.probezeit_bis <= heute + timedelta(days=30):
                warn.append(f"Probezeit endet {v.probezeit_bis:%d.%m.%Y}")
            if v.befristet_bis and v.befristet_bis <= heute + timedelta(days=60):
                warn.append(f"Befristung {'endete' if v.befristet_bis < heute else 'endet'} {v.befristet_bis:%d.%m.%Y}")
            if not v.eintritt:
                warn.append("Eintritt fehlt")
            if not v.stundenlohn and not ma.stundensatz:
                warn.append("Stundenlohn fehlt (Lohnkosten = 0)")
        zeilen.append({"ma": ma, "v": v, "warn": warn})
    return render(request, "zeiten/vertraege.html", {"zeilen": zeilen, "darf": request.user.hat_rolle(*VERWALTUNG)})


@rolle_erforderlich(*VERWALTUNG)
def vertrag(request, pk):
    ma = get_object_or_404(Mitarbeiter, pk=pk)
    v = dienst.vertrag(ma)
    if v is None:
        from planung.dienst import naechste_id
        v = Arbeitsvertrag(mitarbeiter=ma, vertragsid=naechste_id(Arbeitsvertrag, "vertragsid", "AV-"),
                           eintritt=ma.eintritt, urlaub_jahr=ma.urlaubstage or 30, stundenlohn=ma.stundensatz)
        if ma.wochenstunden:
            tag = (ma.wochenstunden / 5).quantize(dienst.Decimal("0.01"))
            v.soll_mo = v.soll_di = v.soll_mi = v.soll_do = v.soll_fr = tag
    neu = v.pk is None
    form = VertragFormular(request.POST or None, instance=v)
    if request.method == "POST" and form.is_valid():
        geheim = {"brutto_monat", "stundenlohn"}
        geaendert = [f for f in form.changed_data]
        form.save()
        protokolliere("vertrag_angelegt" if neu else "vertrag_geaendert", v.vertragsid, benutzer=request.user,
                      details=f"{ma.name}: " + (", ".join(f + (" (Betrag)" if f in geheim else "") for f in geaendert) or "–"))
        messages.success(request, f"Vertrag {v.vertragsid} für {ma.name} gespeichert.")
        return redirect("zeiten:vertraege")
    return render(request, "zeiten/vertrag.html", {"form": form, "ma": ma, "v": v, "neu": neu})
