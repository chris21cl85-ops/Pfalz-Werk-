from .module import navi_fuer

# Wird bei jeder Auslieferung erhöht – so sieht man im Navi, welche Fassung läuft
FASSUNG = "Fassung 2.1 (Etappe 2, Paket 1b)"


def navigation(request):
    """Stellt jeder Seite das Navi des angemeldeten Benutzers bereit."""
    benutzer = getattr(request, "user", None)
    if benutzer is None or not benutzer.is_authenticated:
        return {}
    return {"navi": navi_fuer(benutzer), "pfalzwerk_fassung": FASSUNG}
