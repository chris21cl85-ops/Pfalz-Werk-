from django.apps import AppConfig


class LagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lager"
    verbose_name = "Bestellungen & Lager"

    def ready(self):
        from . import importer  # noqa: F401
