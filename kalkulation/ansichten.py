from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from konten.models import Rolle
from konten.rechte import rolle_erforderlich
from projekte.models import ABGESCHLOSSEN, Projekt

from . import dienst
from .formulare import AuftragFormular, KalkulationFormular, PositionFormular
from .models import Auftrag, Kalkulation, Stuecklistenposition

RECHTE = (Rolle.CHEF, Rolle.ADMIN, Rolle.BUCHHALTUNG, Rolle.MEISTER)


def marge(angebot, kosten):
    if not angebot:
        return None
    return ((Decimal(angebot) - kosten) / Decimal(angebot) * 100).quantize(Decimal("0.1"))


@rolle_erforderlich(*RECHTE)
def liste(request):
    nur = request.GET.get("nur", "offen")
    projekte = Projekt.objects.select_related("kunde", "kalkulation", "auftrag").prefetch_related("stueckliste").order_by("-projektnr")
    zeilen = []
    for p in projekte:
        if nur == "offen" and p.status.strip().lower() in ABGESCHLOSSEN:
            continue
        k = getattr(p, "kalkulation", None)
        a = getattr(p, "auftrag", None)
        if nur == "mit" and not (k or a):
            continue
        kosten = k.kosten if k else None
        zeilen.append({"p": p, "k": k, "a": a, "kosten": kosten, "vk": k.vk if k else None,
                       "marge": marge(a.angebot_netto, kosten) if a and k else None,
                       "ist": k.ist_kosten if k else None})
    return render(request, "kalkulation/liste.html", {"zeilen": zeilen, "nur": nur})


@rolle_erforderlich(*RECHTE)
def projekt(request, pk):
    p = get_object_or_404(Projekt.objects.select_related("kunde"), pk=pk)
    k = Kalkulation.objects.filter(projekt=p).first() or Kalkulation(projekt=p)
    a = Auftrag.objects.filter(projekt=p).first()
    aktion = request.POST.get("aktion") if request.method == "POST" else None
    pos_form = PositionFormular(request.POST if aktion == "position" else None)
    kalk_form = KalkulationFormular(request.POST if aktion == "kalkulation" else None, instance=k)
    start = {} if a else {"angebot_netto": k.vk if k.pk else None, "status": Auftrag.Status.ANGEBOT}
    auftrag_form = AuftragFormular(request.POST if aktion == "auftrag" else None, instance=a, initial=start)
    try:
        if aktion == "position" and pos_form.is_valid():
            d = pos_form.cleaned_data
            dienst.position_anlegen(p, benutzer=request.user, material=d["material"], bezeichnung=d["bezeichnung"],
                                    menge=d["menge"], einheit=d["einheit"], ek=d["ek"], status=d["status"])
            messages.success(request, "Position hinzugefügt.")
            return redirect("kalkulation:projekt", p.pk)
        if aktion == "status":
            pos = get_object_or_404(Stuecklistenposition, pk=request.POST.get("position"), projekt=p)
            dienst.status_setzen(pos, request.POST.get("status"), request.user)
            messages.success(request, f"Pos. {pos.pos}: Status geändert.")
            return redirect("kalkulation:projekt", p.pk)
        if aktion == "entfernen":
            pos = get_object_or_404(Stuecklistenposition, pk=request.POST.get("position"), projekt=p)
            dienst.position_entfernen(pos, request.user)
            messages.success(request, "Position entfernt.")
            return redirect("kalkulation:projekt", p.pk)
        if aktion == "kalkulation" and kalk_form.is_valid():
            k = dienst.kalkulation_speichern(kalk_form.save(commit=False), request.user)
            messages.success(request, f"Kalkulation gespeichert – Kosten {dienst.euro(k.kosten)}, VK {dienst.euro(k.vk)}.")
            return redirect("kalkulation:projekt", p.pk)
        if aktion == "auftrag" and auftrag_form.is_valid():
            d = auftrag_form.cleaned_data
            a = dienst.auftrag_speichern(p, benutzer=request.user, angebot_netto=d["angebot_netto"], status=d["status"],
                                         leistung=d["leistung"], termin=d["termin"])
            messages.success(request, f"Auftrag {a.aunr} gespeichert.")
            return redirect("kalkulation:projekt", p.pk)
        if aktion == "freigabe" and a:
            dienst.freigabe_setzen(a, wer=request.POST.get("wer"), wert=request.POST.get("wert"), benutzer=request.user)
            messages.success(request, "Freigabe gespeichert.")
            return redirect("kalkulation:projekt", p.pk)
    except dienst.KalkFehler as fehler:
        messages.error(request, str(fehler))
    positionen = list(p.stueckliste.select_related("material"))
    from lager.models import bestand
    for pos in positionen:
        pos.lager = bestand(pos.material) if pos.material_id else None
    freigaben = []
    if a:
        for wer, titel in (("kunde", "Kunde"), ("chef", "Chef"), ("meister", "Meister")):
            freigaben.append({"wer": wer, "titel": titel, "wert": getattr(a, f"freigabe_{wer}"),
                              "darf": dienst.darf_freigeben(request.user, wer)})
    return render(request, "kalkulation/projekt.html", {
        "p": p, "k": k if k.pk else None, "a": a, "positionen": positionen, "pos_form": pos_form,
        "kalk_form": kalk_form, "auftrag_form": auftrag_form, "freigaben": freigaben,
        "freigabe_werte": Auftrag.Freigabe.choices, "status_werte": Stuecklistenposition.Status.choices,
        "material_summe": sum((x.gesamt for x in positionen if x.status != "Geplant"), Decimal("0")),
        "marge": marge(a.angebot_netto, k.kosten) if a and k.pk else None,
    })
