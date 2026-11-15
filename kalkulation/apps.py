from django.apps import AppConfig


class KalkulationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "kalkulation"
    verbose_name = "Kalkulation & Aufträge"

    def ready(self):
        from . import importer  # noqa: F401
