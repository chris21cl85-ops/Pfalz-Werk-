from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from kern.models import protokolliere
from konten.models import Rolle
from konten.rechte import rolle_erforderlich
from projekte.models import Projekt

from material.models import Material

from . import dienst, rechner
from .formulare import ABWEICHUNGEN, MoebelFormular, RegelFormular
from .models import MoebelPosition, Regelwerk

RECHTE = (Rolle.CHEF, Rolle.ADMIN, Rolle.MEISTER)
AMPEL = {rechner.GRUEN: ("grün", "Alles in Ordnung"), rechner.GELB: ("gelb", "Hinweise prüfen"),
         rechner.ROT: ("rot", "Fehler – so nicht bauen")}


def _kennzahl(name, wert):
    if not isinstance(wert, (int, float)):
        return wert
    if "kosten" in name.lower() or "preis" in name.lower():
        return f"{wert:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    return rechner.zahl(wert) + (" mm" if name not in ("Anzahl",) else "")


def _aufbereiten(ergebnis):
    """Ergebnis für die Anzeige: Teile und Beschläge getrennt, Ampeltext."""
    if not ergebnis:
        return None
    return {**ergebnis, "platten": [t for t in ergebnis["teile"] if t["l"] is not None],
            "beschlaege": [t for t in ergebnis["teile"] if t["l"] is None],
            "kennzahlen_text": [(k, _kennzahl(k, v)) for k, v in ergebnis.get("kennzahlen", {}).items()],
            "ampel_farbe": AMPEL[ergebnis["ampel"]][0], "ampel_text": AMPEL[ergebnis["ampel"]][1]}


@rolle_erforderlich(*RECHTE)
def liste(request):
    positionen = MoebelPosition.objects.select_related("projekt", "projekt__kunde").order_by("-projekt__projektnr", "pos")
    projekt = None
    if request.GET.get("projekt"):
        projekt = get_object_or_404(Projekt, pk=request.GET["projekt"])
        positionen = positionen.filter(projekt=projekt)
    return render(request, "moebel/liste.html", {"positionen": positionen, "projekt": projekt, "AMPEL": AMPEL})


def _formularseite(request, position=None):
    """Neu und Bearbeiten: „Berechnen“ zeigt die Vorschau, „Speichern“ legt eine Version an."""
    neu = position is None
    eingaben = None if neu else position.eingaben
    initial = {}
    if neu and request.GET.get("projekt"):
        initial["projekt"] = request.GET["projekt"]
    vorschau = None
    if request.method == "POST":
        form = MoebelFormular(request.POST, eingaben=eingaben, mit_projekt=neu)
        if form.is_valid():
            e = form.eingaben()
            if request.POST.get("aktion") == "speichern":
                position = dienst.speichern(projekt=form.cleaned_data["projekt"] if neu else position.projekt,
                                            eingaben=e, benutzer=request.user, position=position)
                messages.success(request, f"{position.positions_id} gespeichert (Version {position.version}).")
                return redirect(position)
            vorschau = _aufbereiten(dienst.rechnen(e))
    else:
        form = MoebelFormular(eingaben=eingaben, mit_projekt=neu, initial=initial)
    return render(request, "moebel/formular.html", {
        "form": form, "position": position, "neu": neu, "vorschau": vorschau,
        "abweichungen": [form[f"abw_{k}"] for k, _ in ABWEICHUNGEN],
        "materialnummern": list(Material.objects.filter(aktiv=True).order_by("materialnr").values_list("materialnr", flat=True)),
        "vorgaben": {t: list(v) for t, v in rechner.TYP_VORGABEN.items()}})


@rolle_erforderlich(*RECHTE)
def neu(request):
    return _formularseite(request)


@rolle_erforderlich(*RECHTE)
def bearbeiten(request, pk):
    return _formularseite(request, get_object_or_404(MoebelPosition, pk=pk))


@rolle_erforderlich(*RECHTE)
def detail(request, pk):
    position = get_object_or_404(MoebelPosition.objects.select_related("projekt", "projekt__kunde", "gespeichert_von"), pk=pk)
    if request.method == "POST":
        aktion = request.POST.get("aktion")
        if aktion == "kopieren":
            kopie = dienst.kopieren(position, request.user)
            messages.success(request, f"Variante {kopie.positions_id} angelegt – jetzt Maße oder Material ändern.")
            return redirect("moebel:bearbeiten", kopie.pk)
        if aktion == "stueckliste":
            try:
                n = dienst.in_stueckliste(position, request.user)
            except dienst.MoebelFehler as fehler:
                messages.error(request, str(fehler))
            else:
                messages.success(request, f"{n} Materialpositionen als „Geplant“ in die Stückliste von "
                                          f"{position.projekt.projektnr} übernommen.")
            return redirect(position)
        if aktion == "arbeitsgaenge":
            from produktion import dienst as produktion
            try:
                n = produktion.aus_moebel(position, request.user)
            except produktion.ProduktionsFehler as fehler:
                messages.error(request, str(fehler))
            else:
                messages.success(request, f"{n} Arbeitsgänge angelegt ({position.positions_id}-AG01 … -AG{n:02d}). "
                                          "Nächster Schritt: in der Produktion einplanen.")
            return redirect(position)
    from kalkulation.models import Stuecklistenposition
    return render(request, "moebel/detail.html", {
        "p": position, "e": position.eingaben, "erg": _aufbereiten(position.ergebnis),
        "in_liste": Stuecklistenposition.objects.filter(moebel=position).select_related("material"),
        "arbeitsgaenge": position.arbeitsgaenge.all(),
        "abweichungen": [(text, position.eingaben.get("abweichungen", {}).get(k)) for k, text in ABWEICHUNGEN
                         if position.eingaben.get("abweichungen", {}).get(k) is not None]})


@rolle_erforderlich(*RECHTE)
def pdf(request, pk):
    position = get_object_or_404(MoebelPosition.objects.select_related("projekt", "projekt__kunde"), pk=pk)
    antwort = HttpResponse(dienst.druckliste_pdf(position), content_type="application/pdf")
    art = "attachment" if request.GET.get("laden") else "inline"
    antwort["Content-Disposition"] = f'{art}; filename="Teileliste_{position.positions_id}.pdf"'
    return antwort


@rolle_erforderlich(*RECHTE)
def etiketten(request, pk):
    position = get_object_or_404(MoebelPosition.objects.select_related("projekt"), pk=pk)
    antwort = HttpResponse(dienst.etiketten_pdf(position), content_type="application/pdf")
    antwort["Content-Disposition"] = f'inline; filename="Etiketten_{position.positions_id}.pdf"'
    return antwort


@rolle_erforderlich(*RECHTE)
def regeln(request):
    regelwerk = Regelwerk.laden()
    if request.method == "POST":
        form = RegelFormular(request.POST, regelwerk=regelwerk)
        if form.is_valid():
            alt = regelwerk.als_regeln().werte
            neu_werte = form.werte()
            geaendert = [f"{k} {rechner.zahl(alt.get(k, 0))}→{rechner.zahl(v)}" for k, v in neu_werte.items()
                         if float(alt.get(k, 0)) != float(v)]
            if geaendert:
                regelwerk.werte = neu_werte
                regelwerk.im_programm_geaendert = True
                regelwerk.save()
                protokolliere("moebel_regeln_geaendert", "Möbel-Regeln", benutzer=request.user, details="; ".join(geaendert))
                messages.success(request, f"{len(geaendert)} Regel(n) gespeichert. Gilt für neue Berechnungen.")
            else:
                messages.info(request, "Keine Änderung.")
            return redirect("moebel:regeln")
    else:
        form = RegelFormular(regelwerk=regelwerk)
    return render(request, "moebel/regeln.html", {"form": form, "r": regelwerk})
