"""Abläufe: Teams, Abwesenheiten, Montage planen (wie MontageZeigen/MontageSpeichern), Termine, Wochenkalender."""
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from kern.models import protokolliere
from mitarbeiter.models import Mitarbeiter

from .models import Abwesenheit, Montage, Team, TeamMitglied, Termin

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]


class PlanungsFehler(Exception):
    pass


def naechste_id(modell, feld, praefix, stellen=4) -> str:
    hoechste = 0
    for wert in modell.objects.filter(**{f"{feld}__startswith": praefix}).values_list(feld, flat=True):
        rest = wert[len(praefix):]
        if rest.isdigit():
            hoechste = max(hoechste, int(rest))
    return f"{praefix}{hoechste + 1:0{stellen}d}"


def montag(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ------------------------------------------------------------------ Abwesenheit
def abwesend(mitarbeiter, tag: date) -> str:
    """Wie Abwesend(): Zeitart, wenn der Mitarbeiter an dem Tag abwesend ist (nicht abgelehnt), sonst ""."""
    if mitarbeiter is None:
        return ""
    a = (mitarbeiter.abwesenheiten.exclude(status=Abwesenheit.Status.ABGELEHNT)
         .filter(von__lte=tag, bis__gte=tag).first())
    return (a.art + (" (beantragt)" if a.status == Abwesenheit.Status.BEANTRAGT else "")) if a else ""


def abwesenheit_erfassen(*, mitarbeiter, von, bis, art, status, hinweis="", benutzer) -> Abwesenheit:
    if bis < von:
        raise PlanungsFehler("„Bis“ liegt vor „Von“.")
    a = Abwesenheit.objects.create(zid=naechste_id(Abwesenheit, "zid", "ZD-"), mitarbeiter=mitarbeiter, von=von, bis=bis,
                                   art=art, status=status, hinweis=hinweis, erfasst_von=benutzer)
    protokolliere("abwesenheit_erfasst", a.zid, benutzer=benutzer,
                  details=f"{mitarbeiter.name}: {art} {von:%d.%m.%Y}–{bis:%d.%m.%Y} ({status})")
    return a


def abwesenheit_status(a: Abwesenheit, status, benutzer):
    alt = a.status
    a.status = status
    a.save(update_fields=["status"])
    protokolliere("abwesenheit_status", a.zid, benutzer=benutzer, details=f"{alt} → {status}")


# ------------------------------------------------------------------ Teams
def team_anlegen(*, name, art, benutzer) -> Team:
    name = (name or "").strip()
    if not name:
        raise PlanungsFehler("Teamname eintragen.")
    if Team.objects.filter(name__iexact=name).exists():
        raise PlanungsFehler(f"Ein Team „{name}“ gibt es schon.")
    t = Team.objects.create(teamid=naechste_id(Team, "teamid", "TEAM-"), name=name, art=art)
    protokolliere("team_angelegt", t.teamid, benutzer=benutzer, details=f"{name} ({art})")
    return t


def mitglied_umschalten(team: Team, mitarbeiter, benutzer) -> bool:
    """Wie PW_PRD_Mitglied: antippen = dazu / raus. Erstes Mitglied wird Leitung."""
    z = TeamMitglied.objects.filter(team=team, mitarbeiter=mitarbeiter).first()
    if z:
        z.aktiv = not z.aktiv
        if z.aktiv and not team.zuordnungen.filter(aktiv=True, leitung=True).exclude(pk=z.pk).exists():
            z.leitung = True
        z.save()
    else:
        z = TeamMitglied.objects.create(team=team, mitarbeiter=mitarbeiter,
                                        leitung=not team.zuordnungen.filter(aktiv=True, leitung=True).exists())
    protokolliere("team_mitglied", team.teamid, benutzer=benutzer,
                  details=f"{mitarbeiter.name} {'dazu' if z.aktiv else 'raus'}{' (Leitung)' if z.aktiv and z.leitung else ''}")
    return z.aktiv


# ------------------------------------------------------------------ Montage
def montage_pruefen(projekt, *, datum, beginn, ende, team, fahrzeug) -> list[str]:
    """Fehler werfen, Warnungen zurückgeben (wie MontageZeigen: abwesend, Team/Fahrzeug schon vergeben)."""
    if ende <= beginn:
        raise PlanungsFehler("Ende muss nach dem Beginn liegen.")
    if team is None:
        raise PlanungsFehler("Team wählen." if Team.objects.exists() else
                             "Noch keine Teams – erst unter „Teams“ eins anlegen.")
    mitglieder = team.mitglieder()
    if not mitglieder:
        raise PlanungsFehler(f"{team.name} hat noch keine Mitglieder.")
    warn = []
    weg = [f"{m.name} ({a})" for m in mitglieder if (a := abwesend(m, datum))]
    if weg:
        warn.append("Abwesend: " + ", ".join(weg))
    andere = Montage.objects.filter(datum=datum).exclude(projekt=projekt).select_related("projekt", "team")
    for m in andere:
        if m.team_id == team.pk:
            warn.append(f"{team.name} ist schon bei {m.projekt.projektnr}.")
        if fahrzeug and m.fahrzeug == fahrzeug:
            warn.append(f"{fahrzeug} ist schon vergeben ({m.projekt.projektnr}).")
    if datum.weekday() > 4:
        warn.append("Der Termin liegt am Wochenende.")
    return warn


def montage_speichern(projekt, *, datum, beginn, ende, team, fahrzeug="", adresse="", aufgaben="", material="",
                      werkzeug="", hinweise="", benutzer) -> Montage:
    """Montageplan + Zeitplan: je Teammitglied ein Termin (alte Montage-Termine des Projekts vorher entfernen)."""
    from produktion.dienst import phase
    if phase(projekt) < 3:
        raise PlanungsFehler("Montage kommt nach der QM-Freigabe.")
    montage_pruefen(projekt, datum=datum, beginn=beginn, ende=ende, team=team, fahrzeug=fahrzeug)
    with transaction.atomic():
        m, neu = Montage.objects.update_or_create(projekt=projekt, defaults={
            "datum": datum, "beginn": beginn, "ende": ende, "team": team, "fahrzeug": fahrzeug, "adresse": adresse,
            "aufgaben": aufgaben, "material": material, "werkzeug": werkzeug, "hinweise": hinweise, "ergebnis": "",
            "ergebnis_am": None})
        projekt.termine.filter(aus_montage=True).delete()
        for ma in team.mitglieder():
            Termin.objects.create(terminid=naechste_id(Termin, "terminid", "T-"), mitarbeiter=ma, datum=datum,
                                  beginn=beginn, ende=ende, projekt=projekt, aufgabe=f"Montage {projekt.name}"[:200],
                                  ort=adresse[:200], team=team, art=Termin.Art.MONTAGE, aus_montage=True,
                                  erfasst_von=benutzer)
    protokolliere("montage_geplant" if neu else "montage_umgeplant", projekt.projektnr, benutzer=benutzer,
                  details=f"{datum:%d.%m.%Y} {beginn:%H:%M}–{ende:%H:%M} · {team.name}" + (f" · {fahrzeug}" if fahrzeug else ""))
    return m


def montage_ergebnis(projekt, ergebnis, benutzer) -> Montage:
    m = getattr(projekt, "montage", None)
    if m is None:
        raise PlanungsFehler("Noch keine Montage geplant.")
    if ergebnis not in (Montage.Ergebnis.BESTANDEN, Montage.Ergebnis.NACHARBEIT):
        raise PlanungsFehler("Ergebnis wählen.")
    m.ergebnis, m.ergebnis_am = ergebnis, timezone.now()
    m.save(update_fields=["ergebnis", "ergebnis_am"])
    protokolliere("montage_ergebnis", projekt.projektnr, benutzer=benutzer, details=ergebnis)
    return m


# ------------------------------------------------------------------ Termine
def termin_anlegen(*, datum, aufgabe, benutzer, mitarbeiter=None, team=None, beginn=None, ende=None, projekt=None,
                   ort="", art=Termin.Art.SONSTIGES) -> list[Termin]:
    """Termin für einen Mitarbeiter oder für jedes Mitglied eines Teams."""
    if beginn and ende and ende <= beginn:
        raise PlanungsFehler("Ende muss nach dem Beginn liegen.")
    leute = [mitarbeiter] if mitarbeiter else (team.mitglieder() if team else [])
    if not leute:
        raise PlanungsFehler("Mitarbeiter oder Team (mit Mitgliedern) wählen.")
    neu = []
    with transaction.atomic():
        for ma in leute:
            neu.append(Termin.objects.create(
                terminid=naechste_id(Termin, "terminid", "T-"), mitarbeiter=ma, datum=datum, beginn=beginn, ende=ende,
                projekt=projekt, aufgabe=aufgabe[:200], ort=ort[:200], team=team, art=art, erfasst_von=benutzer))
    protokolliere("termin_angelegt", neu[0].terminid, benutzer=benutzer,
                  details=f"{datum:%d.%m.%Y} {aufgabe} · " + ", ".join(m.name for m in leute))
    return neu


def termin_absagen(t: Termin, benutzer):
    t.abgesagt = True
    t.save(update_fields=["abgesagt"])
    protokolliere("termin_abgesagt", t.terminid, benutzer=benutzer, details=t.aufgabe)


# ------------------------------------------------------------------ Kalender (wie PW_Kalender, schreibt nichts)
def _kurz(projekt):
    return (projekt.name or projekt.projektnr)[:28] if projekt else ""


def ereignisse(mo: date) -> list[dict]:
    """Alle Einträge der Woche Mo–Fr: Termine (t/m/f), Montagen, Arbeitsgänge (Plan), Abwesenheiten (a)."""
    from produktion.models import Arbeitsgang
    fr = mo + timedelta(days=4)
    liste, gesehen = [], set()

    def plus(tag, typ, text, ma, projekt, team):
        if not mo <= tag <= fr:
            return
        schluessel = (tag, typ, text, ma.pk if ma else None)
        if schluessel in gesehen:
            return
        gesehen.add(schluessel)
        liste.append({"tag": (tag - mo).days, "typ": typ, "text": text, "ma": ma, "projekt": projekt, "team": team})

    for t in Termin.objects.filter(datum__range=(mo, fr), abgesagt=False).select_related("mitarbeiter", "projekt", "team"):
        typ = {"Montage": "m", "Werkstatt": "f"}.get(t.art, "t")
        text = (f"{t.beginn:%H:%M} " if t.beginn else "") + (t.aufgabe or _kurz(t.projekt))
        plus(t.datum, typ, text, t.mitarbeiter, t.projekt, t.team)
    for m in Montage.objects.filter(datum__range=(mo, fr)).select_related("projekt", "team"):
        text = f"Montage {_kurz(m.projekt)}" + (f" · {m.fahrzeug}" if m.fahrzeug else "")
        leute = m.team.mitglieder() if m.team else []
        for ma in leute or [None]:
            if not any(e["typ"] == "m" and e["tag"] == (m.datum - mo).days and e["projekt"] == m.projekt
                       and e["ma"] == ma for e in liste):
                plus(m.datum, "m", text, ma, m.projekt, m.team)
    for ag in (Arbeitsgang.objects.filter(plan_start__isnull=False, plan_start__lte=fr)
               .select_related("projekt", "mitarbeiter")):
        bis = max(ag.plan_ende or ag.plan_start, ag.plan_start)
        if bis < mo:
            continue
        tag = max(ag.plan_start, mo)
        while tag <= min(bis, fr):
            plus(tag, "f", f"{_kurz(ag.projekt)}: {ag.name}" + (" ✓" if ag.status == "Fertig" else ""), ag.mitarbeiter,
                 ag.projekt, None)
            tag += timedelta(days=1)
    for a in Abwesenheit.objects.exclude(status=Abwesenheit.Status.ABGELEHNT).filter(von__lte=fr, bis__gte=mo) \
            .select_related("mitarbeiter"):
        tag = max(a.von, mo)
        while tag <= min(a.bis, fr):
            plus(tag, "a", a.art + (" (beantragt)" if a.status == Abwesenheit.Status.BEANTRAGT else ""), a.mitarbeiter, None, None)
            tag += timedelta(days=1)
    return liste


def kalender(mo: date, ansicht: str) -> dict:
    """Zeilen je Team / Mitarbeiter / Projekt, Spalten Mo–Fr (wie Zeilen(), Passt(), ZellText())."""
    ev = ereignisse(mo)
    zeilen = []
    if ansicht == "mitarbeiter":
        for m in Mitarbeiter.objects.filter(aktiv=True).order_by("name"):
            zeilen.append((m.name, m.rolle, lambda e, m=m: e["ma"] == m))
        if any(e["ma"] is None for e in ev):
            zeilen.append(("Nicht zugeteilt", "ohne Mitarbeiter", lambda e: e["ma"] is None))
    elif ansicht == "projekt":
        projekte = []
        for e in ev:
            if e["projekt"] and e["projekt"] not in projekte:
                projekte.append(e["projekt"])
        for p in sorted(projekte, key=lambda p: p.projektnr):
            zeilen.append((_kurz(p), p.projektnr, lambda e, p=p: e["projekt"] == p))
        zeilen.append(("Sonstiges", "ohne Projekt, Abwesenheiten", lambda e: e["projekt"] is None))
    else:
        teams = list(Team.objects.filter(aktiv=True))
        alle = set()
        for t in teams:
            leute = set(t.mitglieder())
            alle |= leute
            zeilen.append((t.name, ", ".join(m.name for m in t.mitglieder()),
                           lambda e, t=t, leute=leute: (e["ma"] in leute) or (e["team"] == t and e["ma"] is None)))
        if any(e["ma"] not in alle for e in ev) or not zeilen:
            zeilen.append(("Ohne Team", "einzeln geplant", lambda e: e["ma"] not in alle))
    reihen = []
    for name, sub, passt in zeilen:
        zellen = []
        for tag in range(5):
            eintraege = [e for e in ev if e["tag"] == tag and passt(e)]
            texte, gesehen = [], set()
            for e in eintraege:
                text = e["text"] + (f" · {e['ma'].name}" if ansicht != "mitarbeiter" and e["ma"] else "")
                if text not in gesehen:
                    gesehen.add(text)
                    texte.append({"text": text, "typ": e["typ"]})
            haupt = "a" if any(t["typ"] == "a" for t in texte) else (texte[0]["typ"] if texte else "")
            zellen.append({"eintraege": texte, "typ": haupt, "datum": mo + timedelta(days=tag)})
        reihen.append({"name": name, "sub": sub, "zellen": zellen})
    heute = timezone.localdate()
    return {"mo": mo, "fr": mo + timedelta(days=4), "kw": mo.isocalendar()[1], "reihen": reihen, "anzahl": len(ev),
            "tage": [{"name": WOCHENTAGE[i], "datum": mo + timedelta(days=i), "heute": mo + timedelta(days=i) == heute}
                     for i in range(5)]}
