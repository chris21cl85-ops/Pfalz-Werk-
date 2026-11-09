from django.apps import AppConfig


class KundenConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "kunden"
    verbose_name = "Kunden"

    def ready(self):
        from . import importer  # noqa: F401  (Importer für das Blatt „Kunden“ anmelden)
