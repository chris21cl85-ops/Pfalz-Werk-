from .module import navi_fuer


def navigation(request):
    """Stellt jeder Seite das Navi des angemeldeten Benutzers bereit."""
    benutzer = getattr(request, "user", None)
    if benutzer is None or not benutzer.is_authenticated:
        return {}
    return {"navi": navi_fuer(benutzer)}
