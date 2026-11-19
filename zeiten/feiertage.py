"""Gesetzliche Feiertage in Rheinland-Pfalz (Pfalz) – zählen nicht als Soll-Arbeitstag."""
from datetime import date, timedelta
from functools import lru_cache


def ostersonntag(jahr: int) -> date:
    """Gaußsche Osterformel (Spencer/Meeus)."""
    a, b, c = jahr % 19, jahr // 100, jahr % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    monat = (h + l_ - 7 * m + 114) // 31
    tag = (h + l_ - 7 * m + 114) % 31 + 1
    return date(jahr, monat, tag)


@lru_cache(maxsize=64)
def feiertage(jahr: int) -> dict[date, str]:
    o = ostersonntag(jahr)
    return {
        date(jahr, 1, 1): "Neujahr", o - timedelta(days=2): "Karfreitag", o + timedelta(days=1): "Ostermontag",
        date(jahr, 5, 1): "Tag der Arbeit", o + timedelta(days=39): "Christi Himmelfahrt",
        o + timedelta(days=50): "Pfingstmontag", o + timedelta(days=60): "Fronleichnam",
        date(jahr, 10, 3): "Tag der Deutschen Einheit", date(jahr, 11, 1): "Allerheiligen",
        date(jahr, 12, 25): "1. Weihnachtstag", date(jahr, 12, 26): "2. Weihnachtstag",
    }


def feiertag(tag: date) -> str:
    return feiertage(tag.year).get(tag, "")


def arbeitstage(von: date, bis: date) -> int:
    """Mo–Fr ohne Feiertage (wie Arbeitstage() im Makro, zusätzlich ohne Feiertage)."""
    n, d = 0, von
    while d <= bis:
        if d.weekday() < 5 and not feiertag(d):
            n += 1
        d += timedelta(days=1)
    return n
