from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import protokolliere


@receiver(user_logged_in)
def angemeldet(sender, request, user, **kwargs):
    protokolliere("anmeldung", user.get_username(), benutzer=user)


@receiver(user_logged_out)
def abgemeldet(sender, request, user, **kwargs):
    if user is not None:
        protokolliere("abmeldung", user.get_username(), benutzer=user)


@receiver(user_login_failed)
def anmeldung_fehlgeschlagen(sender, credentials, request=None, **kwargs):
    protokolliere("anmeldung_fehlgeschlagen", credentials.get("username", ""))
