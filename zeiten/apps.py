from django.apps import AppConfig


class ZeitenConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "zeiten"
    verbose_name = "Zeiterfassung"

    def ready(self):
        from . import importer  # noqa: F401
