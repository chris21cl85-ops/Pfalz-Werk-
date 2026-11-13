from django.apps import AppConfig


class RechnungenConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rechnungen"
    verbose_name = "Rechnungen"

    def ready(self):
        from . import importer  # noqa: F401
