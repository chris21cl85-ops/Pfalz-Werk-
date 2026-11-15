"""Abläufe: Stückliste pflegen (mit Lagerentnahme), Kalkulation speichern, Auftrag + Freigaben (wie PW_Auftraege)."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from kern.models import protokolliere
from konten.models import Rolle
from lager.models import Lagerbewegung

from .models import Auftrag, Kalkulation, Stuecklistenposition

S = Stuecklistenposition.Status


class KalkFehler(Exception):
    pass


def euro(x) -> str:
    from rechnungen.dienst import euro as e
    return e(x)


def naechste_aunr() -> str:
    hoechste = 0
    for nr in Auftrag.objects.values_list("aunr", flat=True):
        try:
            hoechste = max(hoechste, int(nr.split("-")[-1]))
        except ValueError:
            pass
    return f"AU-{hoechste + 1:04d}"


@transaction.atomic
def position_anlegen(projekt, *, benutzer, material=None, bezeichnung="", menge, einheit="", ek=None,
                     status=S.BENOETIGT, notiz="") -> Stuecklistenposition:
    if material is None and not bezeichnung.strip():
        raise KalkFehler("Bitte Material wählen oder eine Bezeichnung eintragen.")
    if Decimal(menge) <= 0:
        raise KalkFehler("Bitte eine Menge größer 0 eintragen.")
    menge = Decimal(menge)
    ek = Decimal(ek) if ek is not None else None
    pos = max(projekt.stueckliste.values_list("pos", flat=True), default=0) + 1
    p = Stuecklistenposition(projekt=projekt, pos=pos, material=material, menge=menge, notiz=notiz,
                             bezeichnung=bezeichnung.strip() or material.bezeichnung,
                             einheit=einheit or (material.einheit if material else ""),
                             ek=ek if ek is not None else (material.ek_netto if material else None), status=S.GEPLANT)
    p.save()
    if status != S.GEPLANT:
        status_setzen(p, status, benutzer, protokoll=False)
    protokolliere("stueckliste_neu", projekt.projektnr, benutzer=benutzer,
                  details=f"Pos. {p.pos}: {p.menge.normalize():f} {p.einheit} {p.bezeichnung} ({status})")
    return p


@transaction.atomic
def status_setzen(position, status, benutzer, protokoll=True) -> Stuecklistenposition:
    """Statuswechsel; „Entnommen“ bucht das Material aus dem Lager, zurück bucht es wieder ein."""
    p = Stuecklistenposition.objects.select_for_update().get(pk=position.pk)
    alt = p.status
    if alt == status:
        return p
    heute = timezone.localdate()
    if status == S.ENTNOMMEN and p.material_id:
        Lagerbewegung.objects.create(material=p.material, datum=heute, art=Lagerbewegung.Art.ENTNAHME,
                                     menge=-Decimal(p.menge), projekt=p.projekt, erfasst_von=benutzer,
                                     notiz=f"Stückliste {p.projekt.projektnr} Pos. {p.pos}")
    if alt == S.ENTNOMMEN and p.material_id:
        Lagerbewegung.objects.create(material=p.material, datum=heute, art=Lagerbewegung.Art.KORREKTUR,
                                     menge=Decimal(p.menge), projekt=p.projekt, erfasst_von=benutzer,
                                     notiz=f"Rückbuchung Stückliste {p.projekt.projektnr} Pos. {p.pos}")
    p.status = status
    p.save(update_fields=["status", "geaendert_am"])
    if protokoll:
        protokolliere("stueckliste_status", p.projekt.projektnr, benutzer=benutzer,
                      details=f"Pos. {p.pos} {p.bezeichnung}: {alt} → {status}")
    return p


def position_entfernen(position, benutzer):
    if position.status == S.ENTNOMMEN:
        raise KalkFehler("Entnommenes Material erst zurückbuchen (Status ändern), dann entfernen.")
    protokolliere("stueckliste_entfernt", position.projekt.projektnr, benutzer=benutzer,
                  details=f"Pos. {position.pos}: {position.menge.normalize():f} {position.einheit} {position.bezeichnung}")
    position.delete()


def kalkulation_speichern(kalkulation, benutzer) -> Kalkulation:
    kalkulation.save()
    k = kalkulation
    protokolliere("kalkulation_gespeichert", k.projekt.projektnr, benutzer=benutzer, details=(
        f"{k.art}: Kosten {euro(k.kosten)} (Material {euro(k.material)}, Lohn {k.lohn_std} h × {euro(k.lohn_satz)}) · "
        f"Zuschlag {k.zuschlag} % · Risiko {k.risiko} % · VK {euro(k.vk)}"))
    return k


DARF_FREIGEBEN = {"kunde": None, "chef": Rolle.CHEF, "meister": Rolle.MEISTER}


def darf_freigeben(benutzer, wer) -> bool:
    """Wie Darf() im Makro: Kunde jeder, Chef nur Chef, Meister nur Meister, Admin alles."""
    if benutzer.is_superuser or benutzer.rolle == Rolle.ADMIN:
        return True
    rolle = DARF_FREIGEBEN[wer]
    return rolle is None or benutzer.rolle == rolle


def auftrag_speichern(projekt, *, benutzer, angebot_netto, status, leistung="", termin="") -> Auftrag:
    if Decimal(angebot_netto) <= 0:
        raise KalkFehler("Bitte den Angebotspreis (netto) eintragen.")
    a = Auftrag.objects.filter(projekt=projekt).first()
    neu = a is None
    if neu:
        a = Auftrag(aunr=naechste_aunr(), projekt=projekt, angelegt_von=benutzer)
    a.angebot_netto, a.status, a.leistung, a.termin = Decimal(angebot_netto), status, leistung, termin
    a.save()
    protokolliere("auftrag_angelegt" if neu else "auftrag_geaendert", a.aunr, benutzer=benutzer,
                  details=f"Projekt {projekt.projektnr} · {euro(a.angebot_netto)} · {a.status}" + (f" · {termin}" if termin else ""))
    return a


def freigabe_setzen(auftrag, *, wer, wert, benutzer) -> Auftrag:
    if wer not in DARF_FREIGEBEN:
        raise KalkFehler("Unbekannte Freigabe.")
    if not darf_freigeben(benutzer, wer):
        raise KalkFehler(f"Die {'Chef' if wer == 'chef' else 'Meister'}-Freigabe darf nur der {'Chef' if wer == 'chef' else 'Meister'} setzen.")
    if wert not in Auftrag.Freigabe.values:
        raise KalkFehler("Unbekannter Wert.")
    feld = f"freigabe_{wer}"
    alt = getattr(auftrag, feld)
    setattr(auftrag, feld, wert)
    auftrag.save(update_fields=[feld, "geaendert_am"])
    protokolliere("auftrag_freigabe", auftrag.aunr, benutzer=benutzer, details=f"{wer.capitalize()}: {alt} → {wert}")
    return auftrag
