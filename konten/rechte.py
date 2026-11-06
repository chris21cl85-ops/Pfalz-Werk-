"""Rollenprüfung für Ansichten."""
from functools import wraps

from django.core.exceptions import PermissionDenied


def rolle_erforderlich(*rollen):
    """Lässt nur angemeldete Benutzer mit einer der Rollen durch, sonst Fehler 403."""

    def dekorator(ansicht):
        @wraps(ansicht)
        def gepruefte_ansicht(request, *args, **kwargs):
            if not request.user.is_authenticated or not request.user.hat_rolle(*rollen):
                raise PermissionDenied("Für diese Seite fehlt Ihnen die Berechtigung.")
            return ansicht(request, *args, **kwargs)

        return gepruefte_ansicht

    return dekorator
