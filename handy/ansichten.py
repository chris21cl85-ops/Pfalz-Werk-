"""Handy-Ansichten: große Knöpfe, eine Aufgabe je Seite – wie die Handy-Dateien der Excel (Mein Tag, Arbeit,
Lieferungen, Freigaben, Zählen, Melden), aber direkt im Programm statt über OneDrive-Abgleich."""
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from kern.models import protokolliere
from kern.module import ALLE
from konten.models import Rolle
from konten.rechte import rolle_erforderlich
from produktion import dienst as produktion

from . import netz
from .models import Meldung

LEITUNG = (Rolle.CHEF, Rolle.ADMIN, Rolle.MEISTER)
FOTO_ENDUNGEN = {".jpg", ".jpeg", ".png", ".heic", ".webp"}


def _leitung(b):
    return b.hat_rolle(*LEITUNG)


def _zahl(text):
    try:
        return Decimal(str(text).replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        return None


@rolle_erforderlich(*ALLE)
def start(request):
    from inventur.models import Inventur
    from planung.models import Abwesenheit
    ma = produktion.mitarbeiter_von(request.user)
    heute = timezone.localdate()
    leitung = _leitung(request.user)
    kacheln = [{"titel": "Mein Tag", "zeichen": "🌅", "url": "handy:tag", "zahl": None}]
    if ma:
        offen = produktion.offene_fuer(ma)
        kacheln += [{"titel": "Arbeit", "zeichen": "🔨", "url": "handy:arbeit", "zahl": offen.count()},
                    {"titel": "Zeit buchen", "zeichen": "⏱", "url": "handy:zeit", "zahl": None}]
    inv = Inventur.objects.filter(status=Inventur.Status.AKTIV).first()
    if inv and not request.user.hat_rolle(Rolle.BUCHHALTUNG):
        kacheln.append({"titel": "Zählen", "zeichen": "📋", "url": "handy:zaehlen",
                        "zahl": sum(1 for p in inv.positionen.all() if not p.gezaehlt)})
    if leitung:
        from lager.models import Bestellung
        lief = [b for b in Bestellung.objects.filter(abgeschlossen=False) if b.rest_offen > 0]
        kacheln.append({"titel": "Lieferungen", "zeichen": "🚚", "url": "handy:lieferungen", "zahl": len(lief)})
        frei = Abwesenheit.objects.filter(status=Abwesenheit.Status.BEANTRAGT).count() + _auftrag_freigaben(request.user, zaehlen=True)
        kacheln.append({"titel": "Freigaben", "zeichen": "✅", "url": "handy:freigaben", "zahl": frei})
        kacheln.append({"titel": "Meldungen", "zeichen": "📣", "url": "handy:meldungen",
                        "zahl": Meldung.objects.filter(erledigt_am__isnull=True).count()})
        kacheln.append({"titel": "Zuschnitt", "zeichen": "🪚", "url": "handy:zuschnitt", "zahl": None})
    kacheln.append({"titel": "Melden", "zeichen": "⚠", "url": "handy:melden", "zahl": None})
    return render(request, "handy/start.html", {"ma": ma, "heute": heute, "kacheln": kacheln})


@rolle_erforderlich(*ALLE)
def tag(request):
    """Wie Blatt „Mein Tag“: Termine ab heute (nächste 8), dazu Arbeitsgänge von heute und Abwesenheit."""
    from planung.dienst import abwesend
    from planung.models import Termin
    ma = produktion.mitarbeiter_von(request.user)
    heute = timezone.localdate()
    termine = list(Termin.objects.filter(mitarbeiter=ma, datum__gte=heute, abgesagt=False)
                   .select_related("projekt", "projekt__kunde").order_by("datum", "beginn")[:8]) if ma else []
    ags = [a for a in produktion.offene_fuer(ma) if a.status == "In Arbeit" or (a.plan_start and a.plan_start <= heute)] if ma else []
    return render(request, "handy/tag.html", {"ma": ma, "heute": heute, "termine": termine, "ags": ags,
                                              "weg": abwesend(ma, heute) if ma else ""})


@rolle_erforderlich(*ALLE)
def arbeit(request):
    ma = produktion.mitarbeiter_von(request.user)
    if request.method == "POST" and ma:
        from produktion.models import Arbeitsgang
        ag = get_object_or_404(Arbeitsgang, pk=request.POST.get("ag"))
        try:
            if request.POST.get("aktion") == "starten":
                produktion.starten(ag, request.user)
                messages.success(request, f"▶ {ag.name} gestartet.")
            else:
                std = _zahl(request.POST.get("stunden") or "0")
                if std is None:
                    raise produktion.ProduktionsFehler("Stunden als Zahl, z. B. 2,5.")
                fertig = request.POST.get("aktion") == "fertig"
                produktion.rueckmelden(ag, stunden=std, fertig=fertig, benutzer=request.user)
                messages.success(request, f"{'✓ fertig' if fertig else 'Zwischenstand gespeichert'}: {ag.name}")
        except produktion.ProduktionsFehler as fehler:
            messages.error(request, str(fehler))
        return redirect("handy:arbeit")
    return render(request, "handy/arbeit.html", {"ma": ma, "ags": produktion.offene_fuer(ma) if ma else []})


@rolle_erforderlich(*ALLE)
def zeit(request):
    from projekte.models import ABGESCHLOSSEN, Projekt
    from zeiten import dienst as zeiten
    ma = produktion.mitarbeiter_von(request.user)
    heute = timezone.localdate()
    if request.method == "POST" and ma:
        try:
            tag_ = date.fromisoformat(request.POST.get("datum") or heute.isoformat())
            von, bis = request.POST.get("beginn"), request.POST.get("ende")
            from datetime import time as _t
            beginn = _t.fromisoformat(von) if von else None
            ende = _t.fromisoformat(bis) if bis else None
            std = _zahl(request.POST.get("stunden")) if request.POST.get("stunden") else None
            pause = int(request.POST.get("pause") or 0)
            projekt = Projekt.objects.filter(pk=request.POST.get("projekt")).first() if request.POST.get("projekt") else None
            b = zeiten.buchen(mitarbeiter=ma, datum=tag_, stunden=std, beginn=beginn, ende=ende, pause_min=pause,
                              projekt=projekt, taetigkeit=request.POST.get("taetigkeit") or "Fertigung",
                              notiz=request.POST.get("notiz", ""), benutzer=request.user)
            messages.success(request, f"{f'{b.stunden:g}'.replace('.', ',')} h am {b.datum:%d.%m.} gebucht.")
        except (ValueError, zeiten.ZeitFehler) as fehler:
            messages.error(request, str(fehler) if isinstance(fehler, zeiten.ZeitFehler) else "Eingabe prüfen (Datum/Uhrzeit).")
        return redirect("handy:zeit")
    mo = heute - timedelta(days=heute.weekday())
    woche = list(ma.zeitbuchungen.filter(datum__range=(mo, mo + timedelta(days=6)), storniert_am__isnull=True)
                 .select_related("projekt").order_by("-datum", "-beginn")) if ma else []
    soll = sum((zeiten.soll_tag(ma, mo + timedelta(days=i)) for i in range(7)), Decimal("0")) if ma else 0
    projekte = [p for p in Projekt.objects.order_by("-projektnr") if p.status.strip().lower() not in ABGESCHLOSSEN]
    from zeiten.models import Zeitbuchung
    return render(request, "handy/zeit.html", {
        "ma": ma, "heute": heute, "woche": woche, "ist": sum((b.stunden for b in woche), Decimal("0")), "soll": soll,
        "projekte": projekte, "taetigkeiten": Zeitbuchung.Taetigkeit.choices,
        "konto": zeiten.zeitkonto(ma) if ma else None})


@rolle_erforderlich(Rolle.CHEF, Rolle.ADMIN, Rolle.MEISTER, Rolle.MITARBEITER)
def zaehlen(request):
    from inventur import dienst as inventur
    from inventur.models import Inventur, Position
    inv = Inventur.objects.filter(status=Inventur.Status.AKTIV).first()
    if request.method == "POST" and inv:
        pos = get_object_or_404(Position, pk=request.POST.get("position"), inventur=inv)
        try:
            if request.POST.get("aktion") == "nach":
                inventur.nachzaehlen(pos, request.POST.get("menge", ""), request.user)
            else:
                inventur.zaehlen(pos, request.POST.get("menge", ""), request.user, request.POST.get("bemerkung", "").strip())
            messages.success(request, f"✓ {pos.material.materialnr} gespeichert.")
        except inventur.InventurFehler as fehler:
            messages.error(request, str(fehler))
        return redirect("handy:zaehlen")
    pos = list(inv.positionen.select_related("material", "inventur")) if inv else []
    offen = [p for p in pos if not p.gezaehlt]
    nach = [p for p in pos if p.nachzaehlung_offen]
    return render(request, "handy/zaehlen.html", {"inv": inv, "aktuell": offen[0] if offen else None,
                                                  "rest": len(offen), "gesamt": len(pos), "nach": nach})


@rolle_erforderlich(*LEITUNG)
def lieferungen(request):
    from lager import dienst as lager
    from lager.models import Bestellung
    if request.method == "POST":
        b = get_object_or_404(Bestellung, pk=request.POST.get("bestellung"))
        try:
            if request.POST.get("was") == "teil":
                menge = _zahl(request.POST.get("menge"))
                if not menge or menge <= 0:
                    raise lager.LagerFehler("Gelieferte Menge eintragen.")
                text = lager.wareneingang(b, was=lager.TEIL, menge=menge, benutzer=request.user)
            else:
                text = lager.wareneingang(b, was=lager.ALLES, benutzer=request.user)
            messages.success(request, text or f"{b.bnr}: Wareneingang gebucht.")
        except lager.LagerFehler as fehler:
            messages.error(request, str(fehler))
        return redirect("handy:lieferungen")
    offen = [b for b in Bestellung.objects.filter(abgeschlossen=False).select_related("material", "lieferant")
             .order_by("erwartet_am") if b.rest_offen > 0]
    return render(request, "handy/lieferungen.html", {"offen": offen, "heute": timezone.localdate()})


def _auftrag_freigaben(benutzer, zaehlen=False):
    from kalkulation.dienst import darf_freigeben
    from kalkulation.models import Auftrag
    liste = []
    for a in Auftrag.objects.select_related("projekt").exclude(status__in=["Abgeschlossen"]):
        for wer in ("chef", "meister"):
            if getattr(a, f"freigabe_{wer}") == Auftrag.Freigabe.OFFEN and darf_freigeben(benutzer, wer):
                liste.append({"a": a, "wer": wer})
    return len(liste) if zaehlen else liste


@rolle_erforderlich(*LEITUNG)
def freigaben(request):
    from kalkulation import dienst as kalk
    from kalkulation.models import Auftrag
    from planung import dienst as planung
    from planung.models import Abwesenheit
    if request.method == "POST":
        try:
            if request.POST.get("art") == "abwesenheit":
                a = get_object_or_404(Abwesenheit, pk=request.POST.get("id"))
                planung.abwesenheit_status(a, "Freigegeben" if request.POST.get("ja") == "1" else "Abgelehnt", request.user)
                messages.success(request, f"{a.mitarbeiter.name}: {a.status}.")
            elif request.POST.get("art") == "auftrag":
                a = get_object_or_404(Auftrag, pk=request.POST.get("id"))
                wert = Auftrag.Freigabe.FREIGEGEBEN if request.POST.get("ja") == "1" else Auftrag.Freigabe.ABGELEHNT
                kalk.freigabe_setzen(a, wer=request.POST.get("wer"), wert=wert, benutzer=request.user)
                messages.success(request, f"{a.aunr}: {wert}.")
        except kalk.KalkFehler as fehler:
            messages.error(request, str(fehler))
        return redirect("handy:freigaben")
    return render(request, "handy/freigaben.html", {
        "abwesenheiten": Abwesenheit.objects.filter(status=Abwesenheit.Status.BEANTRAGT).select_related("mitarbeiter"),
        "auftraege": _auftrag_freigaben(request.user)})


@rolle_erforderlich(*ALLE)
def melden(request):
    from projekte.models import ABGESCHLOSSEN, Projekt
    if request.method == "POST":
        text = (request.POST.get("text") or "").strip()
        if not text:
            messages.error(request, "Bitte kurz beschreiben, was los ist.")
            return redirect("handy:melden")
        foto = request.FILES.get("foto")
        datei = ""
        if foto:
            endung = Path(foto.name).suffix.lower()
            if endung not in FOTO_ENDUNGEN or foto.size > 15 * 1024 * 1024:
                messages.error(request, "Foto bitte als JPG/PNG/HEIC, höchstens 15 MB.")
                return redirect("handy:melden")
            ordner = Path(settings.DATEIEN_DIR) / "meldungen"
            ordner.mkdir(parents=True, exist_ok=True)
            datei = f"{timezone.localtime():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}{endung}"
            with (ordner / datei).open("wb") as aus:
                for stueck in foto.chunks():
                    aus.write(stueck)
        m = Meldung.objects.create(art=request.POST.get("art") or Meldung.Art.SONSTIGES, text=text[:500], foto=datei,
                                   projekt=Projekt.objects.filter(pk=request.POST.get("projekt")).first()
                                   if request.POST.get("projekt") else None, von=request.user)
        protokolliere("meldung", f"Meldung {m.pk}", benutzer=request.user, details=f"{m.art}: {m.text}")
        messages.success(request, "Danke – die Meldung ist im Büro angekommen.")
        return redirect("handy:start")
    projekte = [p for p in Projekt.objects.order_by("-projektnr") if p.status.strip().lower() not in ABGESCHLOSSEN]
    return render(request, "handy/melden.html", {"arten": Meldung.Art.choices, "projekte": projekte,
                                                 "eigene": Meldung.objects.filter(von=request.user)[:5]})


@rolle_erforderlich(*LEITUNG)
def meldungen(request):
    if request.method == "POST":
        m = get_object_or_404(Meldung, pk=request.POST.get("id"))
        m.erledigt_am, m.erledigt_von = timezone.now(), request.user
        m.antwort = (request.POST.get("antwort") or "").strip()[:300]
        m.save(update_fields=["erledigt_am", "erledigt_von", "antwort"])
        protokolliere("meldung_erledigt", f"Meldung {m.pk}", benutzer=request.user, details=m.antwort or "erledigt")
        messages.success(request, "Als erledigt markiert.")
        return redirect("handy:meldungen")
    alle = request.GET.get("alle") == "1"
    liste = Meldung.objects.select_related("projekt", "von", "erledigt_von")
    if not alle:
        liste = liste.filter(erledigt_am__isnull=True)
    return render(request, "handy/meldungen.html", {"liste": liste, "alle": alle})


@rolle_erforderlich(*ALLE)
def foto(request, pk):
    m = get_object_or_404(Meldung, pk=pk)
    if not m.foto or not (_leitung(request.user) or m.von_id == request.user.pk):
        raise Http404
    pfad = Path(settings.DATEIEN_DIR) / "meldungen" / Path(m.foto).name
    if not pfad.exists():
        raise Http404
    return FileResponse(pfad.open("rb"))


@rolle_erforderlich(*LEITUNG)
def zuschnitt(request):
    from moebel.models import MoebelPosition
    from projekte.models import ABGESCHLOSSEN
    liste = [p for p in MoebelPosition.objects.select_related("projekt").order_by("-gespeichert_am")[:60]
             if p.projekt.status.strip().lower() not in ABGESCHLOSSEN]
    return render(request, "handy/zuschnitt.html", {"liste": liste})


@rolle_erforderlich(*LEITUNG)
def zuschnitt_detail(request, pk):
    """Wie PW_Moebel_Zuschnitt_Handy: Teile je Material, Haken bleiben auf diesem Gerät."""
    from moebel.models import MoebelPosition
    p = get_object_or_404(MoebelPosition.objects.select_related("projekt"), pk=pk)
    gruppen, nr = {}, 0
    for t in p.ergebnis.get("teile", []):
        if t["l"] is None:
            continue
        nr += 1
        kanten = " ".join(k for k, v in (("L1", t["kl1"]), ("L2", t["kl2"]), ("B1", t["kb1"]), ("B2", t["kb2"])) if v) or "–"
        gruppen.setdefault(t["material"], []).append({**t, "nr": nr, "kanten": kanten})
    from material.models import Material
    namen = dict(Material.objects.filter(materialnr__in=gruppen).values_list("materialnr", "bezeichnung"))
    return render(request, "handy/zuschnitt_detail.html", {
        "p": p, "gruppen": [(m, namen.get(m, ""), teile) for m, teile in gruppen.items()]})


@rolle_erforderlich(Rolle.CHEF, Rolle.ADMIN)
def verbinden(request):
    if request.method == "POST":
        ein = request.POST.get("ein") == "1"
        netz.schalten(ein)
        protokolliere("handy_netz", "Handy im WLAN", benutzer=request.user, details="an" if ein else "aus")
        messages.success(request, "Gespeichert. Bitte PFALZ-WERK einmal schließen und neu starten, damit es gilt.")
        return redirect("handy:verbinden")
    adresse = netz.handy_adresse()
    return render(request, "handy/verbinden.html", {"an": netz.an(), "adresse": adresse, "qr": netz.qr_svg(adresse),
                                                    "ip": netz.eigene_ip()})
