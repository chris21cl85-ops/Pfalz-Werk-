from .module import navi_fuer

# Wird bei jeder Auslieferung erhöht – so sieht man im Navi, welche Fassung läuft
FASSUNG = "Fassung 1.8 (Etappe 1 komplett)"


def navigation(request):
    """Stellt jeder Seite das Navi des angemeldeten Benutzers bereit."""
    benutzer = getattr(request, "user", None)
    if benutzer is None or not benutzer.is_authenticated:
        return {}
    return {"navi": navi_fuer(benutzer), "pfalzwerk_fassung": FASSUNG}
