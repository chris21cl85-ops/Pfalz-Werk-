from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class AnmeldungErforderlich:
    """Jede Seite außer der Anmeldung verlangt einen angemeldeten Benutzer."""

    FREI = ("/anmelden/", "/static/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        pfad = request.path
        if not request.user.is_authenticated and not pfad.startswith(self.FREI):
            return redirect(f"{reverse(settings.LOGIN_URL)}?next={pfad}")
        return self.get_response(request)
